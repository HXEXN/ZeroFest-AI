#!/usr/bin/env python3
"""Build the final synthetic 2023–2025 training table from 30-minute snapshots.

Each (festival year, campus) cell is an independent simulation run with its own
seed. Copying one run and rescaling its target would make the 2025 hold-out a
deterministic transform of the training years, so a model could score near
perfectly without generalizing at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_synthetic_festival_data import build_dataset  # noqa: E402

OUTPUT = ROOT / "data" / "final_training_dataset.csv"
YEARS = (2023, 2024, 2025)
REFERENCE_STUDENT_COUNT = 15000
CAMPUSES = ("zero-univ", 15000), ("hanbit-univ", 22000), ("mirae-univ", 9000)
BASE_SEED = 20260917
YEAR_GROWTH = 0.035
PRICE_INFLATION = 0.025
FINAL_COLUMNS = [
    "training_row_id", "run_id", "festival_year", "university_id", "student_count", "campus_scale",
    "booth_id", "menu_id", "booth_zone", "menu_category", "price",
    "observation_timestamp", "target_window_end",
    "festival_day", "day_of_week", "is_weekend", "minutes_to_close",
    "recent_sales_5m", "recent_sales_30m", "previous_sales_30m", "recent_tickets_30m",
    "current_stock", "initial_stock", "stockout_flag",
    "booth_ticket_count_30m", "booth_unique_menu_count_1m",
    "precipitation_probability", "temperature", "event_ending_soon", "discount_rate",
    "discount_elapsed_minutes", "discount_arm", "assigned_discount_rate",
    "future_sales_30m", "future_latent_30m", "censored_window_flag", "data_class",
]


def _run_seed(year: int, campus_index: int) -> int:
    """A distinct seed per cell so no two campus-years share a random stream."""
    return BASE_SEED + (year - YEARS[0]) * 100 + campus_index * 7 + 1


def simulate_festival(
    year: int,
    university_id: str,
    student_count: int,
    seed: int,
    profile: str = "mvp",
    run_id: str | None = None,
) -> pd.DataFrame:
    """Run one independent festival simulation and map it to the training schema.

    This is the unit of data the model actually learns from. Rows inside one
    festival share its weather, its crowd and its menus, so a hundred rows from
    one festival are worth far less than a hundred rows from a hundred festivals.
    """
    campus_scale = round(student_count / REFERENCE_STUDENT_COUNT, 4)
    year_growth = 1 + (year - YEARS[0]) * YEAR_GROWTH
    # Campus size and year-on-year growth drive demand inside the simulation,
    # so prepared stock responds to them as it would in a real festival.
    _, _, _, snapshots, _ = build_dataset(
        profile=profile,
        seed=seed,
        include_seconds=False,
        demand_scale=campus_scale * year_growth,
    )
    frame = snapshots.copy()
    timestamp = pd.to_datetime(frame["snapshot_timestamp"]).map(lambda value: value.replace(year=year))
    target_end = timestamp + pd.to_timedelta(30, unit="m")
    identifier = run_id or f"{year}-{university_id}"
    frame["festival_year"] = year
    frame["university_id"] = university_id
    frame["student_count"] = student_count
    frame["campus_scale"] = campus_scale
    frame["run_id"] = identifier
    frame["training_row_id"] = [f"{identifier}-{index}" for index in frame.index]
    frame["price"] = frame["price_krw"].astype(float) * (1 + (year - YEARS[0]) * PRICE_INFLATION)
    frame["observation_timestamp"] = timestamp.dt.strftime("%Y-%m-%dT%H:%M:%S")
    frame["target_window_end"] = target_end.dt.strftime("%Y-%m-%dT%H:%M:%S")
    # Calendar features follow the festival's actual year, not the template year.
    frame["day_of_week"] = timestamp.dt.weekday.astype(int)
    frame["is_weekend"] = (timestamp.dt.weekday >= 5).astype(int)
    frame["precipitation_probability"] = (frame["rain_mm"].astype(float) * 25).clip(0, 100).round().astype(int)
    frame["temperature"] = frame["temperature_c"].astype(float)
    frame["future_sales_30m"] = frame["next_30m_sales_qty"].astype(int)
    frame["future_latent_30m"] = frame["next_30m_latent_qty"].astype(int)
    frame["data_class"] = "SYNTHETIC_FINAL_TRAINING"
    return frame[FINAL_COLUMNS]


def build_final_training_data() -> pd.DataFrame:
    frames = [
        simulate_festival(year, university_id, student_count, _run_seed(year, campus_index))
        for year in YEARS
        for campus_index, (university_id, student_count) in enumerate(CAMPUSES)
    ]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    output = build_final_training_data()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    censored = output["censored_window_flag"].mean()
    print(f"Created {len(output):,} rows at {OUTPUT}")
    print(f"Independent simulation runs: {len(YEARS) * len(CAMPUSES)} · censored target windows: {censored:.1%}")
