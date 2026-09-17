#!/usr/bin/env python3
"""Generate causally consistent synthetic festival data for ZeroFest MVPs.

The script preserves three grains:
  * master: festival, booth, and menu attributes known before the event
  * events: sparse sale, discount, and stockout records with second timestamps
  * minute snapshots: operational observations at every minute
  * features: 30-minute prediction snapshots without future-information leakage
  * second snapshots: complete booth state series at every second
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROFILES = {"mvp": (12, 4), "full": (30, 8)}  # booths, menus per booth
BAKERY_PATH = Path.home() / ".cache/kagglehub/datasets/matthieugimbert/french-bakery-daily-sales/versions/1/Bakery sales.csv"


def _menu(category: str, index: int) -> tuple[str, int, float]:
    catalog = {
        "food": [("닭꼬치", 6000, 1.00), ("떡볶이", 5000, 0.92), ("핫도그", 4500, 0.85)],
        "drink": [("아이스티", 3500, 1.08), ("에이드", 4000, 1.10), ("커피", 3000, 0.80)],
        "dessert": [("와플", 4500, 0.74), ("츄러스", 4000, 0.70), ("쿠키", 3000, 0.64)],
    }
    return catalog[category][index % len(catalog[category])]


DAY_MINUTES = 360  # 16:00–22:00
STAGE_PRE = (60, 120)  # 17:00–18:00
STAGE_MAIN = (120, 240)  # 18:00–20:00
STAGE_AFTER = (240, 300)  # 20:00–21:00
EVENT_ENDING_WINDOW = 60  # minutes before the main stage ends


# Party size grows when a crowd moves together. Deriving tickets by dividing
# sales by a constant would make ticket count a restatement of sales volume and
# carry no information of its own; drawing parties explicitly does.
GROUP_SIZE_FACTOR = {"normal": 1.00, "pre_stage": 1.10, "main_stage": 1.25, "after_stage": 1.05}


def _stage(minute: int) -> tuple[str, float, float]:
    """Map minutes elapsed since the 16:00 opening to the performance schedule.

    The offset is measured from the opening, never from midnight: comparing it
    against a wall-clock minute-of-day silently disables every stage.
    """
    if STAGE_MAIN[0] <= minute < STAGE_MAIN[1]:
        return "main_stage", 1.22, 1.42
    if STAGE_PRE[0] <= minute < STAGE_PRE[1]:
        return "pre_stage", 1.10, 1.18
    if STAGE_AFTER[0] <= minute < STAGE_AFTER[1]:
        return "after_stage", 0.95, 1.18
    return "normal", 1.00, 0.72


def _festival_contexts(rng: np.random.Generator, total_days: int = 3) -> dict[int, list[dict[str, float | int | str]]]:
    """Draw the weather for the whole festival, stratifying how many days are wet.

    A three-day festival is too short for an i.i.d. wet-day draw to reliably
    produce both conditions, and a file where every day rains teaches the model
    nothing about rain. The number of wet days is therefore sampled first and
    then assigned to days at random.
    """
    wet_day_count = int(rng.choice([0, 1, 1, 2]))
    wet_days = set(rng.choice(np.arange(1, total_days + 1), size=wet_day_count, replace=False).tolist())
    return {day: _day_context(day in wet_days, rng) for day in range(1, total_days + 1)}


def _day_context(is_wet_day: bool, rng: np.random.Generator) -> list[dict[str, float | int | str]]:
    """Draw one weather realization per festival day, shared by every booth.

    Weather is a property of the festival, not of a booth, so it is sampled once
    per (day, minute) and looked up. Drawing it inside the per-menu loop would
    give concurrent booths different rain at the same timestamp.
    """
    base_temperature = float(rng.normal(21.0, 2.4))
    rain_scale = float(rng.gamma(2.0, 0.55)) if is_wet_day else 0.0
    temperature_noise = 0.0
    rain_noise = 0.0
    rows: list[dict[str, float | int | str]] = []
    for minute in range(DAY_MINUTES):
        hour = 16 + minute // 60
        phase, performance, peak = _stage(minute)
        # AR(1) noise keeps weather smooth over time instead of flickering minute to minute.
        temperature_noise = 0.82 * temperature_noise + float(rng.normal(0, 0.38))
        rain_noise = 0.85 * rain_noise + float(rng.normal(0, 0.32))
        # Evening cooling is a mild drift, not the dominant term, so temperature
        # stays a weather variable rather than an alias of the clock.
        temperature = base_temperature - 2.4 * (minute / (DAY_MINUTES - 1)) + temperature_noise
        rain_mm = max(0.0, rain_scale * (1 + 0.45 * rain_noise)) if rain_scale else max(0.0, 0.06 * rain_noise)
        crowd_index = min(1.0, max(0.15, 0.34 * peak * performance * (1 - min(rain_mm, 3) * 0.06) + float(rng.normal(0, 0.035))))
        rows.append({
            "hour": hour,
            "minute_of_day": hour * 60 + minute % 60,
            "temperature_c": round(float(temperature), 1),
            "rain_mm": round(float(rain_mm), 2),
            "crowd_index": round(float(crowd_index), 3),
            "performance_phase": phase,
            "performance_multiplier": performance,
            "peak_multiplier": peak,
            "event_ending_soon": int(STAGE_MAIN[1] - EVENT_ENDING_WINDOW <= minute < STAGE_MAIN[1]),
            "is_wet_day": int(rain_scale > 0),
        })
    return rows


def _bakery_calibration() -> dict[str, object]:
    """Extract time, ticket, and price patterns from the analysed bakery dataset."""
    if not BAKERY_PATH.exists():
        return {"hour_multiplier": {}, "items_per_ticket": 2.5, "price_eur_median": 1.2, "source": "fallback"}
    frame = pd.read_csv(BAKERY_PATH, usecols=["time", "ticket_number", "Quantity", "unit_price"])
    frame["hour"] = frame["time"].str.split(":").str[0].astype(int)
    hour_volume = frame.groupby("hour")["Quantity"].sum()
    hour_multiplier = (hour_volume / hour_volume.mean()).to_dict()
    ticket_items = frame.groupby("ticket_number")["Quantity"].sum().median()
    prices = frame["unit_price"].str.replace(" €", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    return {
        "hour_multiplier": {int(hour): float(value) for hour, value in hour_multiplier.items()},
        "items_per_ticket": float(ticket_items),
        "price_eur_median": float(prices.median()),
        "source": "Kaggle French Bakery Daily Sales",
    }


# One menu at one booth sells on the order of 150-250 units across a 6-hour
# festival day, i.e. well under one unit per minute at the base rate.
BASE_MINUTE_DEMAND = 0.55
DAY_FACTORS = {1: 0.92, 2: 1.13, 3: 0.86}
DISCOUNT_BLOCK = 30  # discounts switch on the 30-minute snapshot grid
DISCOUNT_FIRST_BLOCK = 120  # not before 18:00; nobody discounts at opening
DISCOUNT_BLOCK_PROBABILITY = 0.4
DISCOUNT_RATES = (10, 20, 30)
DISCOUNT_TREATED_DAYS = (1, 2)  # treated days per menu, out of a 3-day festival


def _expected_demand(
    context: dict[str, float | int | str],
    category: str,
    booth_factor: float,
    menu_factor: float,
    day_factor: float,
    discount: int,
    bakery_hour_factor: float,
    demand_scale: float = 1.0,
) -> float:
    """Latent (uncensored) demand rate for one minute, before the stock constraint."""
    weather_factor = 1 - min(float(context["rain_mm"]), 4) * (0.035 if category == "drink" else 0.065)
    temperature_factor = 1 + max(float(context["temperature_c"]) - 23, 0) * (0.028 if category == "drink" else -0.012)
    discount_factor = 1 + discount / 95
    expected = BASE_MINUTE_DEMAND * demand_scale * booth_factor * menu_factor * float(context["peak_multiplier"]) * float(context["performance_multiplier"])
    expected *= 0.72 + 0.28 * bakery_hour_factor
    expected *= weather_factor * temperature_factor * discount_factor * day_factor
    return expected


def build_dataset(
    profile: str = "mvp", seed: int = 20260917, include_seconds: bool = True, demand_scale: float = 1.0
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    booth_count, menus_per_booth = PROFILES[profile]
    rng = np.random.default_rng(seed)
    festival_id = "zerofest-synthetic-2026"
    start = datetime(2026, 5, 20, 16, 0, 0)
    master_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    minute_rows: list[dict[str, object]] = []
    snapshot_rows: list[dict[str, object]] = []
    calibration = _bakery_calibration()
    base_party_size = max(1.2, float(calibration["items_per_ticket"]))
    # Weather belongs to the festival, so every booth on a given day shares it.
    day_contexts_by_day = _festival_contexts(rng, total_days=len(DAY_FACTORS))

    for booth_idx in range(booth_count):
        booth_id = f"B{booth_idx + 1:02d}"
        booth_factor = float(rng.uniform(0.72, 1.28))
        zone = chr(ord("A") + booth_idx % 4)
        for menu_idx in range(menus_per_booth):
            category = ("food", "drink", "dessert")[(booth_idx + menu_idx) % 3]
            # The within-category pick must not reuse the index that chose the
            # category: doing so pins every category to one item, so only three
            # of the nine menus are ever generated and price becomes a perfect
            # restatement of category.
            name, base_price, menu_factor = _menu(category, booth_idx)
            menu_id = f"{booth_id}-M{menu_idx + 1:02d}"
            # Stock is prepared against expected demand, not drawn independently of it.
            # A coverage ratio spanning 1.0 makes both stockouts and leftovers occur,
            # which is what a waste-prevention model has to learn from.
            baseline_demand = float(np.mean([
                sum(
                    _expected_demand(
                        day_contexts_by_day[day][minute], category, booth_factor, menu_factor,
                        DAY_FACTORS[day], 0, float(calibration["hour_multiplier"].get(16 + minute // 60, 1.0)),
                        demand_scale,
                    )
                    for minute in range(DAY_MINUTES)
                )
                for day in DAY_FACTORS
            ]))
            stock_coverage = float(rng.uniform(0.85, 1.45))
            initial_stock = int(max(40, round(baseline_demand * stock_coverage)))
            # Block randomization: every menu appears in both arms across the
            # three days, so booth and menu popularity cancel within the menu
            # instead of only balancing on average across menus.
            treated_count = int(rng.choice(DISCOUNT_TREATED_DAYS))
            treated_days = set(
                rng.choice(np.arange(1, len(DAY_FACTORS) + 1), size=treated_count, replace=False).tolist()
            )
            # A treated day gets a sequence of on/off discount blocks rather than a
            # single switch that stays on. Operators turn promotions on and off, and
            # every on-switch is an observation where the discount is not yet inside
            # recent_sales_30m -- the only rows that identify what applying one does.
            candidate_blocks = list(range(DISCOUNT_FIRST_BLOCK, DAY_MINUTES, DISCOUNT_BLOCK))
            discount_plan: dict[int, tuple[int, set[int]]] = {}
            for day in sorted(treated_days):
                rate = int(rng.choice(DISCOUNT_RATES))
                blocks = {block for block in candidate_blocks if rng.random() < DISCOUNT_BLOCK_PROBABILITY}
                if not blocks:
                    blocks = {int(rng.choice(candidate_blocks))}
                discount_plan[day] = (rate, blocks)
            master_rows.append({
                "festival_id": festival_id,
                "booth_id": booth_id,
                "menu_id": menu_id,
                "booth_zone": zone,
                "menu_name": name,
                "menu_category": category,
                "base_price_krw": base_price,
                "unit_cost_krw": int(base_price * rng.uniform(0.38, 0.55)),
                "initial_stock": initial_stock,
                "stock_coverage": round(stock_coverage, 3),
                "expected_daily_demand": round(baseline_demand, 1),
                "booth_factor": round(booth_factor, 3),
                "menu_factor": menu_factor,
                "data_class": "SYNTHETIC_MASTER",
            })

            for festival_day in range(1, 4):
                day_start = start + timedelta(days=festival_day - 1)
                stock = initial_stock
                day_sales: list[int] = []
                day_tickets: list[int] = []
                day_latent: list[int] = []
                day_contexts = day_contexts_by_day[festival_day]
                day_discounts: list[int] = []
                # The discount is assigned at random, independent of stock and sales.
                # A state-triggered discount would be confounded with the risk that
                # triggered it, making its effect unidentifiable from the data.
                in_discount_arm = festival_day in discount_plan
                assigned_rate, discount_blocks = discount_plan.get(festival_day, (0, set()))
                discount_run_start: int | None = None
                day_discount_age: list[int] = []
                # Demand and event records are simulated for every operating minute.
                for minute in range(DAY_MINUTES):
                    timestamp = day_start + timedelta(minutes=minute)
                    context = day_contexts[minute]
                    discount = assigned_rate if (minute // DISCOUNT_BLOCK) * DISCOUNT_BLOCK in discount_blocks else 0
                    if not discount:
                        discount_run_start = None
                    elif discount_run_start is None:
                        discount_run_start = minute
                    day_discount_age.append(minute - discount_run_start if discount else 0)
                    bakery_hour_factor = float(calibration["hour_multiplier"].get(int(context["hour"]), 1.0))
                    expected = _expected_demand(
                        context, category, booth_factor, menu_factor,
                        DAY_FACTORS[festival_day], discount, bakery_hour_factor, demand_scale,
                    )
                    # Parties arrive; each party buys several items. Sales are the
                    # sum over parties, so ticket count and items-per-ticket are
                    # observations in their own right rather than sales / constant.
                    mean_party = base_party_size * float(GROUP_SIZE_FACTOR[str(context["performance_phase"])])
                    latent_tickets = int(rng.poisson(max(expected / mean_party, 0.02)))
                    latent_demand = int(
                        sum(1 + rng.poisson(max(mean_party - 1, 0.05)) for _ in range(latent_tickets))
                    )
                    sold = min(latent_demand, stock)
                    # A stockout cuts parties served in the same proportion as items.
                    sold_tickets = latent_tickets if sold == latent_demand else int(
                        round(latent_tickets * sold / max(latent_demand, 1))
                    )
                    stock -= sold
                    day_sales.append(sold)
                    day_tickets.append(sold_tickets)
                    day_latent.append(latent_demand)
                    day_discounts.append(discount)

                    if discount and day_discount_age[minute] == 0:
                        event_rows.append({
                            "event_id": f"{menu_id}-{festival_day}-{minute}-discount",
                            "festival_id": festival_id, "booth_id": booth_id, "menu_id": menu_id,
                            "event_timestamp": timestamp.isoformat(timespec="seconds"),
                            "event_type": "DISCOUNT_APPLIED", "quantity": 0, "stock_after": stock,
                            "discount_rate": discount, "data_class": "SYNTHETIC_EVENT",
                        })
                    if sold:
                        for sale_number in range(sold):
                            seconds = int(rng.integers(0, 60))
                            event_rows.append({
                                "event_id": f"{menu_id}-{festival_day}-{minute}-{sale_number}",
                                "festival_id": festival_id, "booth_id": booth_id, "menu_id": menu_id,
                                "event_timestamp": (timestamp + timedelta(seconds=seconds)).isoformat(timespec="seconds"),
                                "event_type": "SALE", "quantity": 1, "stock_after": stock + sold - sale_number - 1,
                                "discount_rate": discount, "data_class": "SYNTHETIC_EVENT",
                            })
                    if stock == 0 and sold:
                        event_rows.append({
                            "event_id": f"{menu_id}-{festival_day}-{minute}-stockout",
                            "festival_id": festival_id, "booth_id": booth_id, "menu_id": menu_id,
                            "event_timestamp": timestamp.isoformat(timespec="seconds"),
                            "event_type": "STOCKOUT", "quantity": 0, "stock_after": 0,
                            "discount_rate": discount, "data_class": "SYNTHETIC_EVENT",
                        })

                sales = np.asarray(day_sales)
                tickets = np.asarray(day_tickets)
                latent = np.asarray(day_latent)
                # Targets begin after the prediction timestamp, preventing leakage.
                next_30 = np.array([sales[index + 1:index + 31].sum() for index in range(DAY_MINUTES)])
                # The uncensored counterpart exists only because the world is simulated.
                # It is never a model input; it is what makes the censoring bias measurable.
                next_30_latent = np.array([latent[index + 1:index + 31].sum() for index in range(DAY_MINUTES)])
                final_stock = initial_stock - sales.sum()
                stock_running = initial_stock - np.cumsum(sales)
                # Only model inputs are materialized every 30 minutes.
                for minute in range(0, DAY_MINUTES, 30):
                    timestamp = day_start + timedelta(minutes=minute)
                    context = day_contexts[minute]
                    recent_5 = int(sales[max(0, minute - 4):minute + 1].sum())
                    recent_30 = int(sales[max(0, minute - 29):minute + 1].sum())
                    previous_30 = int(sales[max(0, minute - 59):max(0, minute - 29)].sum())
                    future = int(next_30[minute])
                    future_latent = int(next_30_latent[minute])
                    rate = max(future / 30, 0.01)
                    current_stock = int(stock_running[minute])
                    minutes_to_stockout = int(np.ceil(current_stock / rate)) if current_stock else 0
                    expected_leftover = max(0, current_stock - int(round(future * (DAY_MINUTES - minute) / 30 * 0.82)))
                    snapshot_rows.append({
                        "festival_id": festival_id, "festival_day": festival_day,
                        "booth_id": booth_id, "menu_id": menu_id, "booth_zone": zone,
                        "snapshot_timestamp": timestamp.isoformat(timespec="seconds"),
                        "hour": context["hour"], "minute_of_day": context["minute_of_day"],
                        "second_of_minute": 0, "minutes_to_close": DAY_MINUTES - 1 - minute,
                        "is_weekend": int(timestamp.weekday() >= 5),
                        "day_of_week": int(timestamp.weekday()),
                        "menu_category": category, "price_krw": base_price,
                        "initial_stock": initial_stock, "current_stock": current_stock,
                        "recent_sales_5m": recent_5, "recent_sales_30m": recent_30,
                        "previous_sales_30m": previous_30,
                        "recent_tickets_30m": int(tickets[max(0, minute - 29):minute + 1].sum()),
                        "discount_rate": day_discounts[minute],
                        # How long the discount has been running. At 0 the recent-sales
                        # window is still entirely pre-discount, which is exactly the
                        # situation an operator faces when approving one. Without this,
                        # a model reads an active discount as already priced into
                        # recent_sales_30m and predicts almost no uplift from applying it.
                        "discount_elapsed_minutes": day_discount_age[minute],
                        "discount_arm": int(in_discount_arm), "assigned_discount_rate": assigned_rate,
                        "temperature_c": context["temperature_c"], "rain_mm": context["rain_mm"],
                        "crowd_index": context["crowd_index"], "performance_phase": context["performance_phase"],
                        "event_ending_soon": int(context["event_ending_soon"]),
                        "next_30m_sales_qty": future, "next_30m_latent_qty": future_latent,
                        "censored_window_flag": int(future_latent > future),
                        "minutes_to_stockout": minutes_to_stockout,
                        "expected_leftover_qty": expected_leftover,
                        "stockout_flag": int(current_stock == 0), "final_leftover_qty": int(final_stock),
                        "bakery_calibration_source": calibration["source"],
                        "data_class": "SYNTHETIC_FEATURE_SNAPSHOT",
                    })
                for minute in range(DAY_MINUTES):
                    timestamp = day_start + timedelta(minutes=minute)
                    context = day_contexts[minute]
                    minute_rows.append({
                        "festival_id": festival_id, "festival_day": festival_day, "booth_id": booth_id, "menu_id": menu_id,
                        "observation_timestamp": timestamp.isoformat(timespec="seconds"),
                        "hour": context["hour"], "minute_of_day": context["minute_of_day"],
                        "is_weekend": int(timestamp.weekday() >= 5), "month": timestamp.month,
                        "price_krw": base_price, "avg_unit_price_krw": base_price,
                        "current_stock": int(stock_running[minute]), "sales_qty_1m": int(sales[minute]),
                        "ticket_count_1m": int(tickets[minute]),
                        "recent_sales_30m": int(sales[max(0, minute - 29):minute + 1].sum()),
                        "previous_sales_30m": int(sales[max(0, minute - 59):max(0, minute - 29)].sum()),
                        "discount_rate": day_discounts[minute], "temperature_c": context["temperature_c"],
                        "rain_mm": context["rain_mm"], "crowd_index": context["crowd_index"],
                        "performance_phase": context["performance_phase"], "next_30m_sales_qty": int(next_30[minute]),
                        "event_ending_soon": int(context["event_ending_soon"]),
                        "stockout_flag": int(stock_running[minute] == 0),
                        "bakery_calibration_source": calibration["source"], "data_class": "SYNTHETIC_MINUTE_SNAPSHOT",
                    })
    master = pd.DataFrame(master_rows)
    events = pd.DataFrame(event_rows)
    minute = pd.DataFrame(minute_rows)
    snapshots = pd.DataFrame(snapshot_rows)
    minute["observation_timestamp"] = pd.to_datetime(minute["observation_timestamp"])
    booth_keys = ["festival_id", "booth_id", "observation_timestamp"]
    minute["booth_ticket_count_1m"] = minute.groupby(booth_keys)["ticket_count_1m"].transform("sum")
    minute["booth_unique_menu_count_1m"] = minute.assign(_sold=minute["sales_qty_1m"] > 0).groupby(booth_keys)["_sold"].transform("sum")
    booth_minute = minute[
        ["festival_id", "festival_day", "booth_id", "observation_timestamp", "booth_ticket_count_1m", "booth_unique_menu_count_1m"]
    ].drop_duplicates()
    booth_minute = booth_minute.sort_values(["booth_id", "festival_day", "observation_timestamp"])
    booth_minute["booth_ticket_count_30m"] = booth_minute.groupby(["booth_id", "festival_day"])["booth_ticket_count_1m"].transform(
        lambda series: series.rolling(30, min_periods=1).sum().astype(int)
    )
    feature_keys = ["festival_id", "festival_day", "booth_id"]
    snapshots["snapshot_timestamp"] = pd.to_datetime(snapshots["snapshot_timestamp"])
    snapshots = snapshots.merge(
        booth_minute[[*feature_keys, "observation_timestamp", "booth_ticket_count_30m", "booth_unique_menu_count_1m"]],
        left_on=[*feature_keys, "snapshot_timestamp"],
        right_on=[*feature_keys, "observation_timestamp"],
        how="left",
    ).drop(columns=["observation_timestamp"])
    snapshots["snapshot_timestamp"] = snapshots["snapshot_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    minute["observation_timestamp"] = minute["observation_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    second = _build_second_snapshots(master, events, minute) if include_seconds else pd.DataFrame()
    return master, events, minute, snapshots, second


def _build_second_snapshots(master: pd.DataFrame, events: pd.DataFrame, minute: pd.DataFrame) -> pd.DataFrame:
    """Materialize second-level booth state while retaining menu detail in the event log."""
    sale_events = events.loc[events["event_type"] == "SALE"].copy()
    sale_events["event_timestamp"] = pd.to_datetime(sale_events["event_timestamp"])
    minute_frame = minute.copy()
    minute_frame["observation_timestamp"] = pd.to_datetime(minute_frame["observation_timestamp"])
    initial_stock = master.groupby("booth_id")["initial_stock"].sum().to_dict()
    frames: list[pd.DataFrame] = []
    for booth_id in sorted(master["booth_id"].unique()):
        booth_minutes = minute_frame.loc[minute_frame["booth_id"] == booth_id]
        for day in sorted(booth_minutes["festival_day"].unique()):
            day_minutes = (
                booth_minutes.loc[booth_minutes["festival_day"] == day]
                .groupby("observation_timestamp", as_index=True)
                .agg({
                    "festival_id": "first", "temperature_c": "mean", "rain_mm": "mean",
                    "crowd_index": "mean", "performance_phase": "first",
                })
            )
            start = day_minutes.index.min()
            seconds = pd.date_range(start, periods=360 * 60, freq="s")
            day_sales = sale_events.loc[(sale_events["booth_id"] == booth_id) & (sale_events["event_timestamp"].dt.date == start.date())]
            per_second_sales = day_sales.groupby("event_timestamp")["quantity"].sum().reindex(seconds, fill_value=0).astype(int)
            minute_index = seconds.floor("min")
            reference = day_minutes.reindex(minute_index)
            frames.append(pd.DataFrame({
                "festival_id": reference["festival_id"].to_numpy(),
                "festival_day": day,
                "booth_id": booth_id,
                "observation_timestamp": seconds.strftime("%Y-%m-%dT%H:%M:%S"),
                "sales_qty_1s": per_second_sales.to_numpy(),
                "current_stock": int(initial_stock[booth_id]) - per_second_sales.cumsum().to_numpy(),
                "temperature_c": reference["temperature_c"].to_numpy(),
                "rain_mm": reference["rain_mm"].to_numpy(),
                "crowd_index": reference["crowd_index"].to_numpy(),
                "performance_phase": reference["performance_phase"].to_numpy(),
                "data_class": "SYNTHETIC_SECOND_SNAPSHOT",
            }))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="mvp")
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument(
        "--with-seconds",
        action="store_true",
        help="per-second booth state as well (about 780k rows / 80MB, nothing reads it by default)",
    )
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    master, events, minute, snapshots, second = build_dataset(
        args.profile, args.seed, include_seconds=args.with_seconds
    )
    master.to_csv(DATA_DIR / "synthetic_festival_master.csv", index=False)
    events.to_csv(DATA_DIR / "synthetic_festival_event_log.csv", index=False)
    minute.to_csv(DATA_DIR / "synthetic_festival_minute_snapshot.csv", index=False)
    snapshots.to_csv(DATA_DIR / "synthetic_festival_feature_snapshot.csv", index=False)
    seconds_path = DATA_DIR / "synthetic_festival_second_snapshot.csv"
    if args.with_seconds:
        second.to_csv(seconds_path, index=False)
    elif seconds_path.exists():
        # A file left over from an earlier run would describe a different world.
        seconds_path.unlink()
    print(
        f"Generated {len(master):,} master rows, {len(events):,} events, "
        f"{len(minute):,} minute rows, {len(snapshots):,} feature rows"
        + (f", {len(second):,} second rows" if args.with_seconds else " (second-level: --with-seconds)")
    )


if __name__ == "__main__":
    main()
