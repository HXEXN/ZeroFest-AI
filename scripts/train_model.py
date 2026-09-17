#!/usr/bin/env python3
"""Train and report hold-out performance on explicitly synthetic examples."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.ensemble import GradientBoostingRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402

from models.demand_model import FEATURES, load_historical_data  # noqa: E402


if __name__ == "__main__":
    history = load_historical_data()
    train = history[history["festival_year"] < history["festival_year"].max()]
    test = history[history["festival_year"] == history["festival_year"].max()]
    x_train, y_train = train[FEATURES], train["future_sales_30m"]
    x_test, y_test = test[FEATURES], test["future_sales_30m"]
    model = GradientBoostingRegressor(
        random_state=42, n_estimators=120, max_depth=3, learning_rate=0.045, loss="huber"
    )
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    print("Dataset: 2023–2025 Sample / Synthetic Historical Festival Dataset")
    print(f"Rows: {len(history):,} · train {len(train):,} · time-holdout {len(test):,}")
    print(f"Hold-out MAE: {mean_absolute_error(y_test, prediction):.2f} items / 30m")
    print(f"Hold-out R²: {r2_score(y_test, prediction):.3f}")
