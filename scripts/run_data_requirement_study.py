#!/usr/bin/env python3
"""Answer "how much data does this model actually need?" with an experiment.

Three questions, one corpus of independently simulated festivals:

  1. Learning curve  - how does hold-out accuracy move as the number of distinct
     festivals grows? The unit is the festival, not the row: rows inside one
     festival share its weather, crowd and menus, so a thousand rows from one
     festival are worth far less than a thousand rows from many.
  2. Scale           - what does going from a 12-booth to a 30-booth festival buy?
  3. Transfer        - if only one real festival is ever available, does
     pre-training on synthetic festivals reduce what that real one has to carry?

Every model here is trained and scored on festivals it has never seen.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.ensemble import GradientBoostingRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402

from models.demand_model import FEATURES, MODEL_PARAMS, CATEGORY_CODES, NEW_DISCOUNT_MAX_AGE_MINUTES  # noqa: E402
from scripts.prepare_final_training_data import simulate_festival  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
RESULT_PATH = OUTPUT_DIR / "data_requirement_study.json"
CURVE_PATH = OUTPUT_DIR / "data_requirement_learning_curve.csv"

TRAIN_POOL_SIZE = 24
TEST_POOL_SIZE = 8
CURVE_POINTS = (1, 2, 3, 4, 6, 8, 12, 16, 24)
REPEATS = 5
CAMPUS_SIZES = (9000, 12000, 15000, 18000, 22000, 27000)
BASE_SEED = 770000
# The "real" festival is drawn with a shifted demand level and an unseen campus
# size, so transfer is measured against a festival that is not simply another
# draw from the training distribution.
REAL_DEMAND_SHIFT = 1.35
REAL_STUDENT_COUNT = 31000


def _derive(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the columns the model expects but the corpus stores in raw form."""
    result = frame.copy()
    result["category_code"] = result["menu_category"].map(CATEGORY_CODES).fillna(0).astype(int)
    result["new_discount_rate"] = result["discount_rate"].where(
        result["discount_elapsed_minutes"] < NEW_DISCOUNT_MAX_AGE_MINUTES, 0
    ).astype(int)
    return result[result["censored_window_flag"] == 0]


def build_corpus(count: int, year: int, seed_offset: int, profile: str, label: str) -> list[pd.DataFrame]:
    festivals: list[pd.DataFrame] = []
    rng = np.random.default_rng(BASE_SEED + seed_offset)
    for index in range(count):
        students = int(rng.choice(CAMPUS_SIZES))
        frame = simulate_festival(
            year=year,
            university_id=f"{label}-{index:02d}",
            student_count=students,
            seed=BASE_SEED + seed_offset + index * 13,
            profile=profile,
            run_id=f"{label}-{index:02d}",
        )
        festivals.append(_derive(frame))
    return festivals


def _fit(train: pd.DataFrame) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(train[FEATURES], train["future_sales_30m"])
    return model


def _score(model: GradientBoostingRegressor, test: pd.DataFrame) -> dict[str, float]:
    predicted = model.predict(test[FEATURES])
    actual = test["future_sales_30m"]
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
    }


def learning_curve(train_pool: list[pd.DataFrame], test: pd.DataFrame) -> pd.DataFrame:
    baseline_mae = float(mean_absolute_error(test["future_sales_30m"], test["recent_sales_30m"]))
    baseline_r2 = float(r2_score(test["future_sales_30m"], test["recent_sales_30m"]))
    rows: list[dict[str, float]] = []
    for size in CURVE_POINTS:
        if size > len(train_pool):
            continue
        for repeat in range(REPEATS):
            rng = np.random.default_rng(BASE_SEED + size * 100 + repeat)
            picked = rng.choice(len(train_pool), size=size, replace=False)
            train = pd.concat([train_pool[i] for i in picked], ignore_index=True)
            metrics = _score(_fit(train), test)
            rows.append({
                "festivals": size,
                "repeat": repeat,
                "rows": len(train),
                "baseline_mae": baseline_mae,
                "baseline_r2": baseline_r2,
                **metrics,
            })
        print(f"  {size:>2} festivals -> MAE {np.mean([r['mae'] for r in rows if r['festivals'] == size]):.3f}")
    return pd.DataFrame(rows)


def transfer_study(
    synthetic_pool: list[pd.DataFrame], real_train: pd.DataFrame, real_test: pd.DataFrame
) -> list[dict[str, object]]:
    """Compare three ways to serve a campus that has one real festival at most."""
    synthetic = pd.concat(synthetic_pool, ignore_index=True)
    synthetic_model = _fit(synthetic)
    results: list[dict[str, object]] = [
        {
            "strategy": "합성만 (실데이터 0)",
            "real_festivals": 0.0,
            "real_rows": 0,
            **_score(synthetic_model, real_test),
        }
    ]
    for fraction in (0.25, 0.5, 1.0):
        subset = real_train.head(int(len(real_train) * fraction))
        results.append({
            "strategy": f"실데이터만 ({fraction:.0%})",
            "real_festivals": fraction,
            "real_rows": len(subset),
            **_score(_fit(subset), real_test),
        })
        # Transfer: keep the synthetic model and learn only its residual on the
        # real rows. The real festival has to explain the gap, not the whole world.
        residual = subset["future_sales_30m"] - synthetic_model.predict(subset[FEATURES])
        corrector = GradientBoostingRegressor(**{**MODEL_PARAMS, "n_estimators": 60})
        corrector.fit(subset[FEATURES], residual)
        corrected = synthetic_model.predict(real_test[FEATURES]) + corrector.predict(real_test[FEATURES])
        results.append({
            "strategy": f"합성 사전학습 + 실데이터 보정 ({fraction:.0%})",
            "real_festivals": fraction,
            "real_rows": len(subset),
            "mae": float(mean_absolute_error(real_test["future_sales_30m"], corrected)),
            "r2": float(r2_score(real_test["future_sales_30m"], corrected)),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-festivals", type=int, default=TRAIN_POOL_SIZE)
    parser.add_argument("--test-festivals", type=int, default=TEST_POOL_SIZE)
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Simulating {args.train_festivals} training + {args.test_festivals} hold-out festivals ...")
    train_pool = build_corpus(args.train_festivals, 2024, 0, "mvp", "train")
    test_pool = build_corpus(args.test_festivals, 2025, 5000, "mvp", "test")
    test = pd.concat(test_pool, ignore_index=True)
    print(f"  corpus: {sum(len(f) for f in train_pool):,} train rows · {len(test):,} hold-out rows")

    print("Learning curve ...")
    curve = learning_curve(train_pool, test)
    curve.to_csv(CURVE_PATH, index=False)

    print("Scale study (12 booths vs 30 booths) ...")
    large_pool = build_corpus(6, 2024, 9000, "full", "large")
    small = pd.concat(train_pool[:6], ignore_index=True)
    large = pd.concat(large_pool, ignore_index=True)
    scale = [
        {"profile": "mvp · 12부스 × 4메뉴", "festivals": 6, "rows": len(small), **_score(_fit(small), test)},
        {"profile": "full · 30부스 × 8메뉴", "festivals": 6, "rows": len(large), **_score(_fit(large), test)},
    ]
    for row in scale:
        print(f"  {row['profile']}: {row['rows']:,} rows -> MAE {row['mae']:.3f}")

    print("Transfer study ...")
    real = build_corpus(1, 2025, 7000, "mvp", "real")[0]
    real = real.assign(
        student_count=REAL_STUDENT_COUNT,
        campus_scale=round(REAL_STUDENT_COUNT / 15000, 4),
        future_sales_30m=(real["future_sales_30m"] * REAL_DEMAND_SHIFT).round().astype(int),
    )
    split = len(real) // 2
    transfer = transfer_study(train_pool, real.iloc[:split], real.iloc[split:])
    for row in transfer:
        print(f"  {row['strategy']:<34} MAE {row['mae']:.3f}  R2 {row['r2']:.3f}")

    summary = curve.groupby("festivals").agg(
        rows=("rows", "mean"), mae=("mae", "mean"), mae_std=("mae", "std"),
        r2=("r2", "mean"), r2_std=("r2", "std"),
    ).reset_index()
    payload = {
        "train_festivals": args.train_festivals,
        "test_festivals": args.test_festivals,
        "test_rows": len(test),
        "baseline_mae": float(curve["baseline_mae"].iloc[0]),
        "baseline_r2": float(curve["baseline_r2"].iloc[0]),
        "curve": summary.to_dict(orient="records"),
        "scale": scale,
        "transfer": transfer,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nWrote {RESULT_PATH}")
    print(f"Wrote {CURVE_PATH}")


if __name__ == "__main__":
    main()
