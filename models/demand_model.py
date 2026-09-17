"""Historical festival demand model with a deterministic demo anchor."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from config import DEMO_MODE, HISTORICAL_DATA_PATH


FEATURES = [
    "recent_sales_30m",
    "previous_sales_30m",
    "festival_day",
    "hour",
    "minute_of_day",
    "second_of_minute",
    "minutes_to_close",
    "seconds_to_close",
    "minutes_to_festival_end",
    "precipitation_probability",
    "temperature",
    "event_ending_soon",
    "discount_rate",
    "category_code",
    "price_k",
    "campus_scale",
]
CATEGORY_CODES = {"food": 0, "drink": 1, "dessert": 2}
HISTORICAL_REQUIRED_COLUMNS = {
    "festival_year",
    "university_id",
    "student_count",
    "menu_category",
    "price",
    "observation_timestamp",
    "target_window_end",
    "festival_day",
    "hour",
    "minute_of_day",
    "second_of_minute",
    "minutes_to_close",
    "seconds_to_close",
    "minutes_to_festival_end",
    "recent_sales_30m",
    "previous_sales_30m",
    "precipitation_probability",
    "temperature",
    "event_ending_soon",
    "discount_rate",
    "future_sales_30m",
}


def _synthetic_training_frame(seed: int = 42, rows: int = 640) -> tuple[pd.DataFrame, pd.Series]:
    """Generate synthetic training examples; never represented as real sales."""
    rng = np.random.default_rng(seed)
    recent = rng.integers(4, 55, rows)
    previous = np.maximum(1, recent + rng.integers(-14, 15, rows))
    festival_day = rng.integers(1, 4, rows)
    hour = rng.integers(16, 22, rows)
    minute_of_day = hour * 60 + rng.choice([0, 30], rows)
    second_of_minute = rng.integers(0, 60, rows)
    minutes = rng.integers(30, 361, rows)
    seconds_to_close = minutes * 60 - second_of_minute
    minutes_to_festival_end = minutes + (3 - festival_day) * 360
    rain = rng.integers(0, 101, rows)
    temperature = rng.integers(16, 31, rows)
    event_end = rng.integers(0, 2, rows)
    discount = rng.choice([0, 0, 0, 10, 20, 30], rows)
    category = rng.integers(0, 3, rows)

    trend = (recent - previous) * 0.28
    rain_factor = np.where(category == 1, -0.05, -0.13) * rain
    event_factor = event_end * -3.8
    discount_factor = recent * (discount / 100) * 1.35
    category_factor = np.choose(category, [1.0, 1.12, 0.84])
    target = (recent + trend + rain_factor + event_factor + discount_factor) * category_factor
    target += rng.normal(0, 2.2, rows)
    target = np.clip(target, 1, None)

    frame = pd.DataFrame(
        {
            "recent_sales_30m": recent,
            "previous_sales_30m": previous,
            "festival_day": festival_day,
            "hour": hour,
            "minute_of_day": minute_of_day,
            "second_of_minute": second_of_minute,
            "minutes_to_close": minutes,
            "seconds_to_close": seconds_to_close,
            "minutes_to_festival_end": minutes_to_festival_end,
            "precipitation_probability": rain,
            "temperature": temperature,
            "event_ending_soon": event_end,
            "discount_rate": discount,
            "category_code": category,
            "price_k": rng.choice([3.0, 4.0, 5.0, 6.0], rows),
            "campus_scale": rng.choice([0.9, 1.5, 2.2], rows),
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
    result["campus_scale"] = result["student_count"].astype(float) / 10000
    return result


def training_data() -> tuple[pd.DataFrame, pd.Series, str]:
    try:
        history = load_historical_data()
        years = sorted(history["festival_year"].astype(int).unique().tolist())
        label = f"{years[0]}–{years[-1]} Historical Festival Data"
        if "data_class" in history and history["data_class"].astype(str).str.contains("SYNTHETIC").any():
            label += " (Sample / Synthetic)"
        return history[FEATURES], history["future_sales_30m"], label
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
    model = GradientBoostingRegressor(
        random_state=42, n_estimators=120, max_depth=3, learning_rate=0.045, loss="huber"
    )
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
    seconds_to_close = max(1800, int((close - now).total_seconds()))
    minutes_to_close = max(30, seconds_to_close // 60)
    return {
        "festival_day": festival_day,
        "minutes_to_close": minutes_to_close,
        "seconds_to_close": seconds_to_close,
        "minutes_to_festival_end": max(30, (total_days - festival_day) * daily_minutes + minutes_to_close),
    }


def _feature_row(state: dict[str, Any], context: dict[str, Any]) -> pd.DataFrame:
    now = context["now"]
    timing = _festival_timing_features(state, now)
    forecast = context.get("weather", {}).get("forecast_1h", {})
    events = context.get("events", [])
    ending_soon = any(
        0 <= (pd.Timestamp(event["end_time"]).to_pydatetime() - now).total_seconds() <= 3600
        for event in events
    )
    return pd.DataFrame(
        [
            {
                "recent_sales_30m": state["recent_sales_30m"],
                "previous_sales_30m": state["previous_sales_30m"],
                "festival_day": timing["festival_day"],
                "hour": now.hour,
                "minute_of_day": now.hour * 60 + now.minute,
                "second_of_minute": now.second,
                "minutes_to_close": timing["minutes_to_close"],
                "seconds_to_close": timing["seconds_to_close"],
                "minutes_to_festival_end": timing["minutes_to_festival_end"],
                "precipitation_probability": float(forecast.get("precipitation_probability", 0)),
                "temperature": float(forecast.get("temperature", 20)),
                "event_ending_soon": int(ending_soon),
                "discount_rate": int(state.get("active_discount_rate", 0)),
                "category_code": CATEGORY_CODES.get(state.get("category", "food"), 0),
                "price_k": int(state.get("price", 0)) / 1000,
                "campus_scale": int(state.get("student_count", 10000)) / 10000,
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

    # The fixed seed scenario is calibrated for a reliable 3–5 minute presentation.
    # It is visibly marked as a simulation everywhere and is not claimed as evidence.
    if DEMO_MODE and state["booth_id"] == "booth-chicken":
        if state.get("student_response_simulated") and state.get("active_discount_rate", 0) >= 20:
            next_30, next_60, until_close = 34, 67, 165
            model_source += " + Demo Simulation intervention calibration"
        else:
            next_30, next_60, until_close = 16, 33, 110
            model_source += " + Demo Simulation baseline calibration"

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
        f"축제 {int(feature['festival_day'])}일 차 · 전체 종료까지 {int(feature['minutes_to_festival_end'])}분",
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
