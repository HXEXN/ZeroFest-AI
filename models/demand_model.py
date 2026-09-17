"""Festival demand model. Every number the UI shows comes from this model."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from config import HISTORICAL_DATA_PATH


# Time is represented once, by minutes_to_close. hour, minute_of_day,
# seconds_to_close and minutes_to_festival_end were exact or near-exact
# restatements of it (|r| up to 1.000) and are deliberately absent.
FEATURES = [
    "recent_sales_30m",
    "previous_sales_30m",
    "recent_tickets_30m",
    "current_stock",
    "initial_stock",
    "minutes_to_close",
    "festival_day",
    "is_weekend",
    "event_ending_soon",
    "precipitation_probability",
    "temperature",
    "discount_rate",
    "new_discount_rate",
    "category_code",
    "campus_scale",
]
# One definition of the estimator, shared by inference, the MLOps pipeline and
# the training script, so a hyperparameter can never drift between them.
MODEL_PARAMS = {
    "random_state": 42,
    "n_estimators": 120,
    "max_depth": 4,
    "learning_rate": 0.045,
    "loss": "huber",
}
# A discount younger than one observation window is not yet reflected in
# recent_sales_30m. Separating it from the running rate is what lets the model
# answer "what happens if I discount now" instead of only "what is happening".
NEW_DISCOUNT_MAX_AGE_MINUTES = 30
CATEGORY_CODES = {"food": 0, "drink": 1, "dessert": 2}
# Campus size enters the model as a population ratio against a reference campus,
# so training and inference compute it from student_count the same way.
REFERENCE_STUDENT_COUNT = 15000


def campus_scale(student_count: Any) -> float:
    return round(float(student_count) / REFERENCE_STUDENT_COUNT, 4)

# Rows whose 30-minute target window was truncated by a stockout. Zero sales
# there means "nothing left to sell", not "nobody wanted it", so they are
# dropped from training rather than taught to the model as zero demand.
CENSORED_FLAG_COLUMN = "censored_window_flag"
HISTORICAL_REQUIRED_COLUMNS = {
    "festival_year",
    "university_id",
    "student_count",
    "campus_scale",
    "menu_category",
    "price",
    "observation_timestamp",
    "target_window_end",
    "festival_day",
    "day_of_week",
    "is_weekend",
    "minutes_to_close",
    "recent_sales_30m",
    "previous_sales_30m",
    "recent_tickets_30m",
    "current_stock",
    "initial_stock",
    "stockout_flag",
    "precipitation_probability",
    "temperature",
    "event_ending_soon",
    "discount_rate",
    "discount_elapsed_minutes",
    "future_sales_30m",
    CENSORED_FLAG_COLUMN,
}


def _synthetic_training_frame(seed: int = 42, rows: int = 640) -> tuple[pd.DataFrame, pd.Series]:
    """Generate synthetic training examples; never represented as real sales."""
    rng = np.random.default_rng(seed)
    recent = rng.integers(4, 55, rows)
    previous = np.maximum(1, recent + rng.integers(-14, 15, rows))
    recent_tickets = np.maximum(1, (recent / rng.uniform(1.8, 2.8, rows)).round().astype(int))
    festival_day = rng.integers(1, 4, rows)
    minutes = rng.integers(30, 361, rows)
    initial_stock = rng.integers(90, 320, rows)
    current_stock = np.maximum(1, initial_stock - rng.integers(0, 260, rows))
    is_weekend = rng.integers(0, 2, rows)
    rain = rng.integers(0, 101, rows)
    temperature = rng.integers(16, 31, rows)
    event_end = rng.integers(0, 2, rows)
    discount = rng.choice([0, 0, 0, 10, 20, 30], rows)
    discount_elapsed = np.where(discount > 0, rng.choice([0, 30, 60, 90], rows), 0)
    category = rng.integers(0, 3, rows)

    trend = (recent - previous) * 0.28
    rain_factor = np.where(category == 1, -0.05, -0.13) * rain
    event_factor = event_end * 3.8
    discount_factor = recent * (discount / 100) * 1.35 * np.where(discount_elapsed == 0, 1.0, 0.4)
    category_factor = np.choose(category, [1.0, 1.12, 0.84])
    target = (recent + trend + rain_factor + event_factor + discount_factor) * category_factor
    target += rng.normal(0, 2.2, rows)
    target = np.clip(target, 1, None)

    frame = pd.DataFrame(
        {
            "recent_sales_30m": recent,
            "previous_sales_30m": previous,
            "recent_tickets_30m": recent_tickets,
            "current_stock": current_stock,
            "initial_stock": initial_stock,
            "minutes_to_close": minutes,
            "festival_day": festival_day,
            "is_weekend": is_weekend,
            "event_ending_soon": event_end,
            "precipitation_probability": rain,
            "temperature": temperature,
            "discount_rate": discount,
            "new_discount_rate": np.where(discount_elapsed == 0, discount, 0),
            "category_code": category,
            "campus_scale": rng.choice([0.82, 1.0, 1.14], rows),
        }
    )
    return frame, pd.Series(target, name="future_sales_30m")


@lru_cache(maxsize=1)
def load_historical_data() -> pd.DataFrame:
    """Load 2023–2025 history from the configured adapter path.

    The repository default is explicitly synthetic. A real institution can set
    HISTORICAL_DATA_PATH to a CSV with the same contract.
    """
    frame = pd.read_csv(HISTORICAL_DATA_PATH)
    missing = HISTORICAL_REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Historical dataset is missing columns: {sorted(missing)}")
    result = frame.copy()
    result["category_code"] = result["menu_category"].map(CATEGORY_CODES).fillna(0).astype(int)
    result["price_k"] = result["price"].astype(float) / 1000
    result["new_discount_rate"] = result["discount_rate"].where(
        result["discount_elapsed_minutes"] < NEW_DISCOUNT_MAX_AGE_MINUTES, 0
    ).astype(int)
    return result


def uncensored(history: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose target window was truncated by a stockout.

    Sales are censored demand: once stock hits zero the observed quantity stops
    tracking what students wanted. Training on those zeros teaches the model to
    predict no demand exactly when a booth has already sold out.
    """
    if CENSORED_FLAG_COLUMN not in history.columns:
        return history
    return history[history[CENSORED_FLAG_COLUMN] == 0]


def training_data() -> tuple[pd.DataFrame, pd.Series, str]:
    try:
        history = load_historical_data()
        years = sorted(history["festival_year"].astype(int).unique().tolist())
        label = f"{years[0]}–{years[-1]} Historical Festival Data"
        if "data_class" in history and history["data_class"].astype(str).str.contains("SYNTHETIC").any():
            label += " (Sample / Synthetic)"
        usable = uncensored(history)
        return usable[FEATURES], usable["future_sales_30m"], label
    except Exception:
        features, target = _synthetic_training_frame()
        return features, target, "Generated Synthetic Fallback"


def training_metadata() -> dict[str, Any]:
    try:
        history = load_historical_data()
        return {
            "path": str(HISTORICAL_DATA_PATH),
            "rows": len(history),
            "years": sorted(history["festival_year"].astype(int).unique().tolist()),
            "universities": int(history["university_id"].nunique()),
            "data_class": str(history.get("data_class", pd.Series(["UNDECLARED"])).iloc[0]),
            "status": "READY",
        }
    except Exception as exc:
        return {
            "path": str(HISTORICAL_DATA_PATH), "rows": 0, "years": [], "universities": 0,
            "data_class": "FALLBACK", "status": f"ERROR: {type(exc).__name__}",
        }


@lru_cache(maxsize=1)
def _trained_model() -> Any:
    from sklearn.ensemble import GradientBoostingRegressor

    features, target, _ = training_data()
    model = GradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(features[FEATURES], target)
    return model


def _festival_timing_features(state: dict[str, Any], now: Any) -> dict[str, int]:
    """Build short-festival timing features; year stays validation metadata only."""
    total_days = max(1, int(state.get("festival_total_days", 3)))
    try:
        festival_start = pd.Timestamp(state.get("festival_date")).date()
    except (TypeError, ValueError):
        festival_start = now.date()
    festival_day = min(total_days, max(1, (now.date() - festival_start).days + 1))
    start_hour, start_minute = map(int, str(state.get("festival_start_time", "16:00")).split(":"))
    end_hour, end_minute = map(int, str(state.get("festival_end_time", "22:00")).split(":"))
    daily_minutes = max(30, (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute))
    close = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    minutes_to_close = max(30, int((close - now).total_seconds()) // 60)
    return {
        "festival_day": festival_day,
        "minutes_to_close": minutes_to_close,
        "daily_minutes": daily_minutes,
    }


def _discount_elapsed_minutes(state: dict[str, Any], now: Any) -> int:
    """Minutes an approved discount has been live, 0 when none is running."""
    if not int(state.get("active_discount_rate", 0)):
        return 0
    started_at = state.get("discount_started_at")
    if not started_at:
        return 0
    try:
        elapsed = (now - pd.Timestamp(started_at).to_pydatetime()).total_seconds() // 60
    except (TypeError, ValueError):
        return 0
    return int(max(0, elapsed))


def _feature_row(state: dict[str, Any], context: dict[str, Any]) -> pd.DataFrame:
    now = context["now"]
    timing = _festival_timing_features(state, now)
    forecast = context.get("weather", {}).get("forecast_1h", {})
    events = context.get("events", [])
    discount_rate = int(state.get("active_discount_rate", 0))
    ending_soon = any(
        0 <= (pd.Timestamp(event["end_time"]).to_pydatetime() - now).total_seconds() <= 3600
        for event in events
    )
    return pd.DataFrame(
        [
            {
                "recent_sales_30m": state["recent_sales_30m"],
                "previous_sales_30m": state["previous_sales_30m"],
                "recent_tickets_30m": int(state.get("recent_tickets_30m", 0)),
                "current_stock": int(state["current_stock"]),
                "initial_stock": int(state.get("initial_stock", state["current_stock"])),
                "minutes_to_close": timing["minutes_to_close"],
                "festival_day": timing["festival_day"],
                "is_weekend": int(now.weekday() >= 5),
                "event_ending_soon": int(ending_soon),
                "precipitation_probability": float(forecast.get("precipitation_probability", 0)),
                "temperature": float(forecast.get("temperature", 20)),
                "discount_rate": discount_rate,
                "new_discount_rate": (
                    discount_rate
                    if _discount_elapsed_minutes(state, now) < NEW_DISCOUNT_MAX_AGE_MINUTES
                    else 0
                ),
                "category_code": CATEGORY_CODES.get(state.get("category", "food"), 0),
                "campus_scale": campus_scale(state.get("student_count", REFERENCE_STUDENT_COUNT)),
            }
        ]
    )


def predict_demand(state: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    row = _feature_row(state, context)
    feature = row.iloc[0]
    _, _, training_label = training_data()
    model_source = f"GradientBoostingRegressor · {training_label}"

    try:
        next_30 = max(1, int(round(float(_trained_model().predict(row[FEATURES])[0]))))
    except Exception:
        # A transparent heuristic keeps the demo available if sklearn cannot load.
        trend_rate = 0.65 * float(feature["recent_sales_30m"]) + 0.35 * float(feature["previous_sales_30m"])
        weather_factor = 1 - min(float(feature["precipitation_probability"]), 90) / 260
        discount_factor = 1 + float(feature["discount_rate"]) / 80
        next_30 = max(1, int(round(trend_rate * weather_factor * discount_factor)))
        model_source = "Transparent heuristic fallback"

    minutes_to_close = int(feature["minutes_to_close"])
    next_60 = int(round(next_30 * 1.86))
    until_close = int(round(next_30 * (minutes_to_close / 30) * 0.82))

    current_stock = int(state["current_stock"])
    until_close = min(current_stock, max(0, until_close))
    expected_remaining = max(0, current_stock - until_close)
    minutes_to_stockout = max(0, int(np.ceil(current_stock / max(next_30 / 30, 0.01))))
    stockout_before_close = current_stock == 0 or minutes_to_stockout <= minutes_to_close
    estimated_stockout_at = (
        (context["now"] + timedelta(minutes=minutes_to_stockout)).isoformat(timespec="seconds")
        if stockout_before_close else None
    )
    rain = int(float(feature["precipitation_probability"]))
    trend_pct = round(
        (int(state["recent_sales_30m"]) - int(state["previous_sales_30m"]))
        / max(int(state["previous_sales_30m"]), 1)
        * 100
    )
    drivers = [
        f"최근 30분 판매 {state['recent_sales_30m']}개 ({trend_pct:+d}%)",
        f"축제 {int(feature['festival_day'])}일 차 · 당일 종료까지 {int(feature['minutes_to_close'])}분",
        f"1시간 뒤 강수확률 {rain}%",
        "메인 공연 종료가 1시간 이내" if feature["event_ending_soon"] else "공연 종료 영향 낮음",
    ]
    if state.get("active_discount_rate"):
        drivers.append(f"승인된 {state['active_discount_rate']}% 할인 반영")
    if state.get("student_response_simulated"):
        drivers.append("학생 반응 시뮬레이션 반영")
    if stockout_before_close:
        drivers.append(f"현재 판매속도 유지 시 약 {minutes_to_stockout}분 후 품절 예상")
    else:
        drivers.append("현재 판매속도 기준 당일 종료 전 품절 예상 없음")
    return {
        "predicted_sales_30m": next_30,
        "predicted_sales_60m": next_60,
        "predicted_sales_until_close": until_close,
        "expected_remaining": expected_remaining,
        "minutes_to_stockout": minutes_to_stockout if stockout_before_close else None,
        "estimated_stockout_at": estimated_stockout_at,
        "stockout_before_close": stockout_before_close,
        "model_source": model_source,
        "drivers": drivers,
        "feature_snapshot": row.iloc[0].to_dict(),
    }
