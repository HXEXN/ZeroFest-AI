from __future__ import annotations

from datetime import datetime

from agents.graph import run_workflow
from agents.rules import action_candidates
from models.waste_risk import classify_waste_risk
from services import database as db
from services.chat import ask_admin
from services.mlops import data_quality_report, run_training_pipeline
from models.demand_model import (
    FEATURES,
    _feature_row,
    load_historical_data,
    predict_demand,
    uncensored,
)


def test_risk_thresholds_are_explainable():
    assert classify_waste_risk(9, 100)["risk_level"] == "LOW"
    assert classify_waste_risk(10, 100)["risk_level"] == "MEDIUM"
    assert classify_waste_risk(30, 100)["risk_level"] == "HIGH"


def test_closed_loop_discount_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / "demo.db"
    db.reset_demo(path)

    before = run_workflow("booth-chicken", db_path=path)
    # Tree implementations can place this boundary demo in MEDIUM or HIGH;
    # both must enter the human-approved intervention path.
    assert before["prediction"]["risk_level"] in {"MEDIUM", "HIGH"}
    baseline_remaining = before["prediction"]["expected_remaining"]

    discount = next(
        item for item in db.get_actions("booth-chicken", "PENDING", path)
        if item["action_type"] == "DISCOUNT"
    )
    executed = run_workflow("booth-chicken", [discount["action_id"]], path)
    assert "DISCOUNT" in executed["executed_actions"]
    promotion = db.get_active_promotions(path)[0]
    assert promotion["price"] == 6000
    assert promotion["sale_price"] == 4800

    # Approving the discount must move the forecast, not just the student screen.
    approved = executed["prediction"]
    assert approved["predicted_sales_30m"] > before["prediction"]["predicted_sales_30m"]
    assert approved["expected_remaining"] < baseline_remaining

    response = db.simulate_student_response(path)
    assert response["sold"] > 0
    after = run_workflow("booth-chicken", db_path=path)
    # The re-prediction reads a changed world: stock fell and the clock advanced.
    assert after["booth"]["current_stock"] == 180 - response["sold"]
    assert db.get_demo_time(path).isoformat() == response["to"] + ":00"
    assert after["prediction"]["expected_remaining"] < baseline_remaining
    assert db.get_intervention_baseline("booth-chicken", path)["expected_remaining"] == baseline_remaining


def test_predictions_have_no_hardcoded_demo_path(tmp_path):
    """No booth may receive a scripted number; every value comes from the model."""
    path = tmp_path / "nohardcode.db"
    db.reset_demo(path)
    for booth in db.get_booths(path):
        result = run_workflow(booth["booth_id"], db_path=path)
        assert "Demo Simulation" not in result["prediction"]["model_source"]
        assert result["prediction"]["model_source"].startswith("GradientBoostingRegressor")


def test_student_response_requires_an_approved_discount(tmp_path):
    import pytest

    path = tmp_path / "noapproval.db"
    db.reset_demo(path)
    run_workflow("booth-chicken", db_path=path)
    with pytest.raises(ValueError):
        db.simulate_student_response(path)


def test_model_reproduces_the_designed_discount_elasticity():
    """A freshly approved discount must raise the forecast by the designed lift."""
    from models.demand_model import _trained_model, uncensored

    history = uncensored(load_historical_data())
    sample = history[history["discount_rate"] == 0].head(400).copy()
    model = _trained_model()
    base = model.predict(sample[FEATURES]).mean()
    treated = sample.assign(discount_rate=20, new_discount_rate=20)
    lift = model.predict(treated[FEATURES]).mean() / base - 1
    assert 0.12 < lift < 0.30


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
    remaining = db.get_latest_prediction("booth-chicken", path)["expected_remaining"]
    assert f"{remaining}개" in answer
    assert "운영자가 승인" in answer
    assert engine == "Grounded local fallback"


def test_one_press_is_one_order(tmp_path):
    """Ticket count must be an observation, not sales volume divided by a constant."""
    path = tmp_path / "tickets.db"
    db.reset_demo(path)
    before = db.get_booth_state("booth-chicken", path)
    db.record_sale("booth-chicken", 3, db_path=path)
    db.record_sale("booth-chicken", 2, db_path=path)
    after = db.get_booth_state("booth-chicken", path)
    assert after["recent_sales_30m"] == before["recent_sales_30m"] + 5
    assert after["recent_tickets_30m"] == before["recent_tickets_30m"] + 2
    assert after["current_stock"] == before["current_stock"] - 5
    assert "recent_tickets_30m" in FEATURES


def test_recent_sales_is_a_window_not_the_last_row(tmp_path):
    """Two small orders must add up, not overwrite each other."""
    path = tmp_path / "window.db"
    db.reset_demo(path)
    baseline = db.get_booth_state("booth-chicken", path)["recent_sales_30m"]
    for _ in range(4):
        db.record_sale("booth-chicken", 1, db_path=path)
    assert db.get_booth_state("booth-chicken", path)["recent_sales_30m"] == baseline + 4


def test_existing_database_is_migrated_in_place(tmp_path):
    """A database created before a column was added must keep working.

    CREATE TABLE IF NOT EXISTS leaves an old database on its old schema, so the
    app only breaks for people who already have one -- never in a test that
    starts from scratch.
    """
    import sqlite3

    path = tmp_path / "legacy.db"
    db.reset_demo(path)
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE sales_snapshots DROP COLUMN ticket_count")
    db.initialize_database(path)
    state = db.get_booth_state("booth-chicken", path)
    assert state["recent_sales_30m"] > 0
    assert state["recent_tickets_30m"] >= 1


def test_admin_surfaces_real_agent_actions(tmp_path):
    """The dashboard must show what the agent queued, not a fixed list."""
    path = tmp_path / "actions.db"
    db.reset_demo(path)
    run_workflow("booth-chicken", db_path=path)
    high = {item["action_type"] for item in db.get_actions("booth-chicken", "PENDING", path)}
    assert "DISCOUNT" in high
    for action in db.get_actions("booth-chicken", "PENDING", path):
        assert action["reason"]


def test_medium_risk_still_offers_a_human_approved_discount(tmp_path):
    path = tmp_path / "medium-actions.db"
    db.reset_demo(path)
    booth = db.get_booth_state("booth-chicken", path)
    candidates = action_candidates(
        booth,
        {"risk_level": "MEDIUM", "expected_remaining": 45},
        str(path),
    )
    assert "DISCOUNT" in {item["action_type"] for item in candidates}


def test_zone_map_is_computed_from_booth_state(tmp_path):
    from components.map import _zone_summary

    path = tmp_path / "map.db"
    db.reset_demo(path)
    for booth in db.get_booths(path):
        run_workflow(booth["booth_id"], db_path=path)
    zones = _zone_summary(db.dashboard_rows(path), [])
    assert {z["zone"] for z in zones} == {"A", "B", "C"}
    assert next(z for z in zones if z["zone"] == "B")["booths"] == 2
    assert next(z for z in zones if z["zone"] == "A")["risk"] in {"MEDIUM", "HIGH"}
    assert all(not z["discounted"] for z in zones)


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
    assert set(history["data_class"]) == {"SYNTHETIC_FINAL_TRAINING"}
    assert set(history["festival_day"]) == {1, 2, 3}
    assert {"festival_day", "minutes_to_close", "current_stock", "initial_stock", "temperature"}.issubset(FEATURES)
    assert "new_discount_rate" in FEATURES
    assert {"observation_timestamp", "target_window_end"}.issubset(history.columns)
    # Redundant restatements of the clock must stay out of the model contract.
    assert not {"hour", "minute_of_day", "second_of_minute", "seconds_to_close"} & set(FEATURES)


def test_each_campus_year_is_an_independent_simulation():
    history = load_historical_data()
    cells = history.groupby(["festival_year", "university_id"]).size()
    assert len(cells) == 9
    # Copied runs would make the hold-out a transform of the training years.
    assert history[FEATURES].duplicated().mean() < 0.05


def test_censored_rows_are_excluded_from_training():
    history = load_historical_data()
    usable = uncensored(history)
    assert history["censored_window_flag"].sum() > 0
    assert usable["censored_window_flag"].sum() == 0
    # Once truncated windows are gone, zero-demand targets are rare, not the norm.
    assert (usable["future_sales_30m"] == 0).mean() < 0.05


def test_stage_schedule_is_active_in_the_history():
    history = load_historical_data()
    assert history["event_ending_soon"].nunique() == 2
    ending = history.groupby("event_ending_soon")["future_sales_30m"].mean()
    assert ending[1] > ending[0]


def test_discount_is_randomly_assigned_and_present():
    history = load_historical_data()
    assert (history["discount_rate"] > 0).mean() > 0.10
    assert set(history["discount_rate"].unique()) >= {0, 10, 20, 30}


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
    assert feature["minutes_to_close"] == 104
    assert feature["temperature"] == 21
    assert feature["current_stock"] == 1
    assert feature["is_weekend"] == 1
    assert feature["campus_scale"] == 1.0
    assert list(feature.index) == FEATURES
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
