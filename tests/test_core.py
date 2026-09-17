from __future__ import annotations

from datetime import datetime

from agents.graph import run_workflow
from models.waste_risk import classify_waste_risk
from services import database as db
from services.chat import ask_admin
from services.mlops import data_quality_report, run_training_pipeline
from models.demand_model import FEATURES, _feature_row, load_historical_data, predict_demand


def test_risk_thresholds_are_explainable():
    assert classify_waste_risk(9, 100)["risk_level"] == "LOW"
    assert classify_waste_risk(10, 100)["risk_level"] == "MEDIUM"
    assert classify_waste_risk(30, 100)["risk_level"] == "HIGH"


def test_closed_loop_discount_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / "demo.db"
    db.reset_demo(path)

    before = run_workflow("booth-chicken", db_path=path)
    assert before["prediction"]["expected_remaining"] == 70
    assert before["prediction"]["risk_level"] == "HIGH"

    discount = next(
        item for item in db.get_actions("booth-chicken", "PENDING", path)
        if item["action_type"] == "DISCOUNT"
    )
    executed = run_workflow("booth-chicken", [discount["action_id"]], path)
    assert "DISCOUNT" in executed["executed_actions"]
    promotion = db.get_active_promotions(path)[0]
    assert promotion["price"] == 6000
    assert promotion["sale_price"] == 4800

    db.simulate_student_response(path)
    after = run_workflow("booth-chicken", db_path=path)
    assert after["prediction"]["expected_remaining"] == 15
    assert after["prediction"]["risk_level"] == "LOW"


def test_langgraph_and_ml_are_primary_engines(tmp_path):
    import pytest

    pytest.importorskip("langgraph")
    path = tmp_path / "engines.db"
    db.reset_demo(path)
    result = run_workflow("booth-chicken", db_path=path)
    assert result["workflow_engine"] == "LangGraph StateGraph"
    assert result["prediction"]["model_source"].startswith("GradientBoostingRegressor")


def test_grounded_chat_uses_current_prediction(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / "chat.db"
    db.reset_demo(path)
    for booth in db.get_booths(path):
        run_workflow(booth["booth_id"], db_path=path)
    answer, engine = ask_admin("왜 닭꼬치를 할인해야 돼?", path)
    assert "70개" in answer
    assert "운영자가 승인" in answer
    assert engine == "Grounded local fallback"


def test_register_booth_minimum_fields(tmp_path):
    path = tmp_path / "register.db"
    db.reset_demo(path)
    booth_id = db.register_booth("별빛 부스", "C", "핫도그", 4500, 80, db_path=path)
    state = db.get_booth_state(booth_id, path)
    assert state["zone"] == "C"
    assert state["price"] == 4500
    assert state["current_stock"] == 80


def test_historical_training_adapter_is_time_scoped():
    history = load_historical_data()
    assert sorted(history["festival_year"].unique().tolist()) == [2023, 2024, 2025]
    assert history["university_id"].nunique() == 3
    assert set(history["data_class"]) == {"SYNTHETIC_HISTORY"}
    assert set(history["festival_day"]) == {1, 2, 3}
    assert {"festival_day", "minute_of_day", "second_of_minute", "seconds_to_close", "minutes_to_festival_end", "temperature"}.issubset(FEATURES)
    assert {"observation_timestamp", "target_window_end"}.issubset(history.columns)
    assert history["second_of_minute"].between(0, 59).all()


def test_short_festival_features_are_used_for_inference():
    state = {
        "recent_sales_30m": 20,
        "previous_sales_30m": 18,
        "festival_date": "2026-05-22",
        "festival_start_time": "16:00",
        "festival_end_time": "22:00",
        "festival_total_days": 3,
        "category": "drink",
        "price": 3000,
        "student_count": 15000,
        "booth_id": "booth-test",
        "current_stock": 1,
    }
    context = {
        "now": datetime(2026, 5, 24, 20, 15, 45),
        "weather": {"forecast_1h": {"precipitation_probability": 70, "temperature": 21}},
        "events": [],
    }
    feature = _feature_row(state, context).iloc[0]
    assert feature["festival_day"] == 3
    assert feature["minute_of_day"] == 1215
    assert feature["second_of_minute"] == 45
    assert feature["minutes_to_close"] == 104
    assert feature["seconds_to_close"] == 6255
    assert feature["minutes_to_festival_end"] == 104
    assert feature["temperature"] == 21
    prediction = predict_demand(state, context)
    assert prediction["stockout_before_close"] is True
    assert prediction["estimated_stockout_at"]
    assert prediction["minutes_to_stockout"] is not None


def test_mlops_pipeline_registers_active_model(tmp_path):
    path = tmp_path / "mlops.db"
    db.reset_demo(path)
    report = data_quality_report()
    run = run_training_pipeline(path)
    assert report["quality_score"] == 100
    assert run["training_years"] == "2023–2024"
    assert run["validation_year"] == 2025
    saved = db.query_one("SELECT * FROM ml_runs WHERE is_active=1", db_path=path)
    assert saved and saved["status"] == "DEPLOYED"
