#!/usr/bin/env python3
"""Generate reproducible 2023–2025 cross-campus synthetic history.

The output is a model-development fixture, never represented as observed sales.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "sample_historical_sales.csv"


def build_history() -> pd.DataFrame:
    rng = np.random.default_rng(20260910)
    campuses = [
        ("zero-univ", 15000, 1.00),
        ("hanbit-univ", 22000, 1.14),
        ("mirae-univ", 9000, 0.82),
    ]
    menus = [
        ("food", 6000, 1.00),
        ("food", 5000, 0.88),
        ("drink", 3000, 1.18),
        ("dessert", 4000, 0.72),
    ]
    records: list[dict[str, int | float | str]] = []
    for year in [2023, 2024, 2025]:
        year_growth = 1 + (year - 2023) * 0.035
        for campus_id, student_count, campus_factor in campuses:
            for menu_index, (category, base_price, menu_factor) in enumerate(menus):
                for festival_day in [1, 2, 3]:
                    previous = int(rng.integers(9, 25))
                    day_factor = {1: 0.92, 2: 1.10, 3: 0.82}[festival_day]
                    festival_date = datetime(year, 5, 22) + timedelta(days=festival_day - 1)
                    for slot in range(360):
                        observed_at = festival_date.replace(hour=16, minute=0, second=slot % 60) + timedelta(minutes=slot)
                        target_window_end = observed_at + timedelta(minutes=30)
                        hour = observed_at.hour
                        rain = int(rng.choice([5, 15, 25, 45, 70, 85]))
                        temperature = float(rng.integers(17, 29))
                        event_ending = int(observed_at.hour in {19, 21} and observed_at.minute == 30)
                        discount = int(rng.choice([0, 0, 0, 10, 20]))
                        peak = 1.25 if hour in {18, 19} else (0.76 if hour == 21 else 1.0)
                        temperature_factor = 1 + max(0, temperature - 23) * 0.025 if category == "drink" else 1.0
                        recent = max(
                            2,
                            int(
                                (18 + menu_index * 2 + rng.normal(0, 4))
                                * campus_factor * menu_factor * day_factor * peak * year_growth
                                * temperature_factor * (1 - rain / 260)
                            ),
                        )
                        category_weather = 0.92 if category == "drink" else 0.84
                        target = max(
                            1,
                            int(
                                (recent * 0.72 + previous * 0.28)
                                * (category_weather if rain >= 70 else 1.0)
                                * (0.86 if event_ending else 1.0)
                                * (1 + discount / 72)
                                + rng.normal(0, 1.8)
                            ),
                        )
                        records.append(
                            {
                                "festival_year": year,
                                "university_id": campus_id,
                                "student_count": student_count,
                                "menu_category": category,
                                "price": base_price + (year - 2023) * 200,
                                "observation_timestamp": observed_at.isoformat(),
                                "target_window_end": target_window_end.isoformat(),
                                "festival_day": festival_day,
                                "hour": hour,
                                "minute_of_day": observed_at.hour * 60 + observed_at.minute,
                                "second_of_minute": observed_at.second,
                                "minutes_to_close": int((festival_date.replace(hour=22, minute=0, second=0) - observed_at).total_seconds() / 60),
                                "seconds_to_close": int((festival_date.replace(hour=22, minute=0, second=0) - observed_at).total_seconds()),
                                "minutes_to_festival_end": int(((festival_date + timedelta(days=3 - festival_day)).replace(hour=22, minute=0, second=0) - observed_at).total_seconds() / 60),
                                "recent_sales_30m": recent,
                                "previous_sales_30m": previous,
                                "precipitation_probability": rain,
                                "temperature": temperature,
                                "event_ending_soon": event_ending,
                                "discount_rate": discount,
                                "future_sales_30m": target,
                                "data_class": "SYNTHETIC_HISTORY",
                            }
                        )
                        previous = recent
    return pd.DataFrame(records)


if __name__ == "__main__":
    frame = build_history()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    print(f"Generated {len(frame)} synthetic historical rows at {OUTPUT}")
    print(f"Years: {frame['festival_year'].min()}–{frame['festival_year'].max()}")
