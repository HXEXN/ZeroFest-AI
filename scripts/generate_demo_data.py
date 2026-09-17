#!/usr/bin/env python3
"""Validate committed sample CSVs and rebuild the local demo database."""

from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.graph import analyze_all  # noqa: E402
from services.database import reset_demo  # noqa: E402


if __name__ == "__main__":
    names = [
        "sample_sales.csv", "sample_inventory.csv", "sample_weather.csv",
        "sample_events.csv", "sample_historical_sales.csv",
    ]
    for name in names:
        path = ROOT / "data" / name
        with path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise RuntimeError(f"No rows in {name}")
        print(f"Validated {name}: {len(rows)} sample rows")
    reset_demo()
    analyze_all()
    print("SQLite demo state rebuilt. All records are sample/synthetic.")
