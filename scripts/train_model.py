#!/usr/bin/env python3
"""Train and report hold-out performance on explicitly synthetic examples."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.ensemble import GradientBoostingRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402

from models.demand_model import FEATURES, MODEL_PARAMS, load_historical_data, uncensored  # noqa: E402


if __name__ == "__main__":
    raw = load_historical_data()
    history = uncensored(raw)
    train = history[history["festival_year"] < history["festival_year"].max()]
    test = history[history["festival_year"] == history["festival_year"].max()]
    model = GradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(train[FEATURES], train["future_sales_30m"])
    prediction = model.predict(test[FEATURES])
    actual = test["future_sales_30m"]
    baseline = test["recent_sales_30m"]

    print("Dataset: 2023–2025 Final Synthetic Festival Training Dataset")
    print(f"Rows: {len(raw):,} · censored dropped {len(raw) - len(history):,} · usable {len(history):,}")
    print(f"Split: train {len(train):,} (2023–2024) · time-holdout {len(test):,} ({int(test['festival_year'].iloc[0])})")
    print(f"Features: {len(FEATURES)}")
    print()
    print(f"Baseline (persistence)  MAE {mean_absolute_error(actual, baseline):6.2f} · R² {r2_score(actual, baseline):6.3f}")
    print(f"GradientBoosting        MAE {mean_absolute_error(actual, prediction):6.2f} · R² {r2_score(actual, prediction):6.3f}")
