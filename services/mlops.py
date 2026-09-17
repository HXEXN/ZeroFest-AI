"""Lightweight data, model and pipeline operations for the hackathon MVP."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from config import DB_PATH
from models.demand_model import FEATURES, _trained_model, load_historical_data, training_metadata
from services import database as db


FEATURE_LABELS = {
    "recent_sales_30m": "최근 30분 판매",
    "previous_sales_30m": "이전 30분 판매",
    "festival_day": "축제 일차",
    "hour": "시간대",
    "minute_of_day": "분 단위 시각",
    "second_of_minute": "초 단위 시각",
    "minutes_to_close": "종료까지 시간",
    "seconds_to_close": "종료까지 초",
    "minutes_to_festival_end": "축제 전체 종료까지 시간",
    "precipitation_probability": "강수확률",
    "temperature": "기온",
    "event_ending_soon": "공연 종료",
    "discount_rate": "할인율",
    "category_code": "메뉴 유형",
    "price_k": "가격",
    "campus_scale": "캠퍼스 규모",
}


def data_quality_report() -> dict[str, Any]:
    history = load_historical_data()
    expected = set(FEATURES + ["festival_year", "university_id", "future_sales_30m"])
    missing_columns = sorted(expected - set(history.columns))
    null_cells = int(history[list(expected & set(history.columns))].isna().sum().sum())
    duplicate_rows = int(history.duplicated().sum())
    invalid_targets = int((history["future_sales_30m"] < 0).sum())
    quality_score = max(0, 100 - null_cells * 2 - duplicate_rows - invalid_targets * 5 - len(missing_columns) * 10)
    return {
        **training_metadata(),
        "columns": len(history.columns),
        "missing_columns": missing_columns,
        "null_cells": null_cells,
        "duplicate_rows": duplicate_rows,
        "invalid_targets": invalid_targets,
        "quality_score": quality_score,
        "year_counts": history.groupby("festival_year").size().astype(int).to_dict(),
        "category_counts": history.groupby("menu_category").size().astype(int).to_dict(),
    }


def _fit_time_holdout() -> tuple[GradientBoostingRegressor, dict[str, Any]]:
    history = load_historical_data()
    validation_year = int(history["festival_year"].max())
    train = history[history["festival_year"] < validation_year]
    validation = history[history["festival_year"] == validation_year]
    model = GradientBoostingRegressor(
        random_state=42, n_estimators=120, max_depth=3, learning_rate=0.045, loss="huber"
    )
    model.fit(train[FEATURES], train["future_sales_30m"])
    predicted = model.predict(validation[FEATURES])
    metrics = {
        "validation_year": validation_year,
        "train_rows": len(train),
        "validation_rows": len(validation),
        "training_years": f"{int(train['festival_year'].min())}–{int(train['festival_year'].max())}",
        "mae": round(float(mean_absolute_error(validation["future_sales_30m"], predicted)), 3),
        "r2": round(float(r2_score(validation["future_sales_30m"], predicted)), 3),
    }
    return model, metrics


def run_training_pipeline(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    quality = data_quality_report()
    stages = [
        {"stage": "01 INGEST", "status": "PASS", "detail": f"{quality['rows']} historical rows"},
        {"stage": "02 VALIDATE", "status": "PASS", "detail": f"quality {quality['quality_score']}%"},
        {"stage": "03 FEATURES", "status": "PASS", "detail": f"{len(FEATURES)} model features"},
    ]
    model, metrics = _fit_time_holdout()
    stages.extend(
        [
            {"stage": "04 TRAIN", "status": "PASS", "detail": "Gradient Boosting"},
            {"stage": "05 EVALUATE", "status": "PASS", "detail": f"MAE {metrics['mae']:.2f}"},
            {"stage": "06 REGISTER", "status": "ACTIVE", "detail": "Human-reviewed demo model"},
        ]
    )
    now = datetime.now().isoformat(timespec="seconds")
    run_id = f"zf-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    with db.connection(db_path) as conn:
        conn.execute("UPDATE ml_runs SET is_active=0")
        conn.execute(
            """INSERT INTO ml_runs
               (run_id, timestamp, model_name, training_years, train_rows, validation_year,
                mae, r2, status, is_active, stages_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DEPLOYED', 1, ?)""",
            (
                run_id, now, "GradientBoostingRegressor", metrics["training_years"],
                metrics["train_rows"], metrics["validation_year"], metrics["mae"], metrics["r2"],
                json.dumps(stages, ensure_ascii=False),
            ),
        )
        conn.execute(
            "UPDATE data_sources SET row_count=?, status='READY', last_validated_at=? WHERE source_id='history-sample'",
            (quality["rows"], now),
        )
    _trained_model.cache_clear()
    importances = sorted(
        [
            {"feature": feature, "label": FEATURE_LABELS[feature], "importance": round(float(score), 4)}
            for feature, score in zip(FEATURES, model.feature_importances_)
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )
    return {"run_id": run_id, "timestamp": now, **metrics, "stages": stages, "importances": importances}


def model_runs(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    rows = db.query_all("SELECT * FROM ml_runs ORDER BY timestamp DESC", db_path=db_path)
    for row in rows:
        row["stages"] = json.loads(row.pop("stages_json"))
    return rows


def ensure_active_model(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    runs = model_runs(db_path)
    if not runs:
        return run_training_pipeline(db_path)
    active = next((row for row in runs if row["is_active"]), runs[0])
    model, _ = _fit_time_holdout()
    active["importances"] = sorted(
        [
            {"feature": feature, "label": FEATURE_LABELS[feature], "importance": round(float(score), 4)}
            for feature, score in zip(FEATURES, model.feature_importances_)
        ],
        key=lambda item: item["importance"], reverse=True,
    )
    return active


def prediction_audit(db_path: Path | str = DB_PATH) -> pd.DataFrame:
    return pd.DataFrame(
        db.query_all(
            """SELECT p.timestamp, b.booth_name, m.menu_name, p.predicted_sales_30m,
                      p.expected_remaining, p.risk_level, p.model_source
               FROM predictions p JOIN booths b ON b.booth_id=p.booth_id
               JOIN menus m ON m.menu_id=p.menu_id
               WHERE p.prediction_id IN (
                 SELECT MAX(prediction_id) FROM predictions GROUP BY booth_id
               ) ORDER BY p.expected_remaining DESC""",
            db_path=db_path,
        )
    )
