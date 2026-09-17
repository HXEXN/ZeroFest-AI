"""Executable LangGraph workflow with a dependency-safe sequential fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from config import DB_PATH
from models.demand_model import predict_demand
from models.waste_risk import classify_waste_risk
from services import database as db
from services.weather import get_weather
from agents.rules import action_candidates


class WorkflowState(TypedDict, total=False):
    booth_id: str
    db_path: str
    approved_action_ids: list[str]
    booth: dict[str, Any]
    context: dict[str, Any]
    prediction: dict[str, Any]
    conditions: dict[str, Any]
    candidates: list[dict[str, str]]
    waiting_for_operator: bool
    executed_actions: list[str]
    monitor_message: str
    workflow_engine: str


def load_current_state(state: WorkflowState) -> dict[str, Any]:
    path = state["db_path"]
    booth = db.get_booth_state(state["booth_id"], path)
    return {
        "booth": booth,
        "context": {
            "now": db.get_demo_time(path),
            "weather": get_weather(path),
            "events": db.get_event_context(path),
        },
    }


def predict_demand_node(state: WorkflowState) -> dict[str, Any]:
    return {"prediction": predict_demand(state["booth"], state["context"])}


def calculate_waste_risk(state: WorkflowState) -> dict[str, Any]:
    result = classify_waste_risk(
        state["prediction"]["expected_remaining"], state["booth"]["current_stock"]
    )
    return {"prediction": {**state["prediction"], **result}}


def check_operational_conditions(state: WorkflowState) -> dict[str, Any]:
    feature = state["prediction"].get("feature_snapshot", {})
    return {
        "conditions": {
            "sales_declining": state["booth"]["recent_sales_30m"] < state["booth"]["previous_sales_30m"],
            "rain_within_hour": feature.get("precipitation_probability", 0) >= 60,
            "event_ending_soon": bool(feature.get("event_ending_soon", 0)),
        }
    }


def generate_action_candidates(state: WorkflowState) -> dict[str, Any]:
    return {
        "candidates": action_candidates(state["booth"], state["prediction"], state["db_path"])
    }


def operator_approval(state: WorkflowState) -> dict[str, Any]:
    approvals = state.get("approved_action_ids", [])
    return {"waiting_for_operator": bool(state["candidates"]) and not approvals}


def execute_action(state: WorkflowState) -> dict[str, Any]:
    executed: list[str] = []
    for action_id in state.get("approved_action_ids", []):
        action = db.get_action(action_id, state["db_path"])
        if not action or action["booth_id"] != state["booth_id"] or action["status"] != "PENDING":
            continue
        db.mark_action(action_id, "APPROVED", state["db_path"])
        if action["action_type"] == "DISCOUNT":
            # Freeze the pre-intervention forecast so the before/after comparison
            # is against what the model actually said before anything was applied.
            db.record_intervention_baseline(state["booth_id"], state["db_path"])
            db.activate_promotion(state["booth_id"], 20, state["db_path"])
        elif action["action_type"] == "STOP_COOKING":
            db.set_setting(f"cooking_halted:{state['booth_id']}", "1", state["db_path"])
        elif action["action_type"] == "PROMOTION":
            db.set_setting(f"promotion_ready:{state['booth_id']}", "1", state["db_path"])
        elif action["action_type"] == "TRANSFER":
            db.set_setting(f"transfer_candidate:{state['booth_id']}", "B", state["db_path"])
        db.mark_action(action_id, "EXECUTED", state["db_path"])
        executed.append(action["action_type"])
    return {"executed_actions": executed, "waiting_for_operator": False}


def monitor_result(state: WorkflowState) -> dict[str, Any]:
    return {
        "monitor_message": "승인된 Action을 반영했습니다. 학생 반응 이후 재예측할 수 있습니다."
    }


def re_predict(state: WorkflowState) -> dict[str, Any]:
    refreshed = db.get_booth_state(state["booth_id"], state["db_path"])
    prediction = predict_demand(refreshed, state["context"])
    risk = classify_waste_risk(prediction["expected_remaining"], refreshed["current_stock"])
    return {"booth": refreshed, "prediction": {**prediction, **risk}}


NODES = [
    load_current_state,
    predict_demand_node,
    calculate_waste_risk,
    check_operational_conditions,
    generate_action_candidates,
    operator_approval,
]


def _build_langgraph():
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(WorkflowState)
    workflow.add_node("load_current_state", load_current_state)
    workflow.add_node("predict_demand", predict_demand_node)
    workflow.add_node("calculate_waste_risk", calculate_waste_risk)
    workflow.add_node("check_operational_conditions", check_operational_conditions)
    workflow.add_node("generate_action_candidates", generate_action_candidates)
    workflow.add_node("operator_approval", operator_approval)
    workflow.add_node("execute_action", execute_action)
    workflow.add_node("monitor_result", monitor_result)
    workflow.add_node("re_predict", re_predict)
    workflow.add_edge(START, "load_current_state")
    workflow.add_edge("load_current_state", "predict_demand")
    workflow.add_edge("predict_demand", "calculate_waste_risk")
    workflow.add_edge("calculate_waste_risk", "check_operational_conditions")
    workflow.add_edge("check_operational_conditions", "generate_action_candidates")
    workflow.add_edge("generate_action_candidates", "operator_approval")
    workflow.add_conditional_edges(
        "operator_approval",
        lambda state: "execute" if state.get("approved_action_ids") else "wait",
        {"execute": "execute_action", "wait": END},
    )
    workflow.add_edge("execute_action", "monitor_result")
    workflow.add_edge("monitor_result", "re_predict")
    workflow.add_edge("re_predict", END)
    return workflow.compile()


def _run_sequential(state: WorkflowState) -> WorkflowState:
    for node in NODES:
        state.update(node(state))
    if state.get("approved_action_ids"):
        state.update(execute_action(state))
        state.update(monitor_result(state))
        state.update(re_predict(state))
    state["workflow_engine"] = "Sequential fallback (LangGraph dependency unavailable)"
    return state


def run_workflow(
    booth_id: str,
    approved_action_ids: list[str] | None = None,
    db_path: Path | str = DB_PATH,
) -> WorkflowState:
    path = str(db_path)
    initial: WorkflowState = {
        "booth_id": booth_id,
        "db_path": path,
        "approved_action_ids": approved_action_ids or [],
    }
    try:
        graph = _build_langgraph()
        result: WorkflowState = graph.invoke(initial)
        result["workflow_engine"] = "LangGraph StateGraph"
    except Exception as exc:
        result = _run_sequential(initial)
        result["fallback_reason"] = f"LangGraph unavailable: {type(exc).__name__}"

    db.save_prediction(booth_id, result["prediction"], path)
    if not approved_action_ids:
        db.replace_pending_actions(booth_id, result["candidates"], path)
    return result


def analyze_all(db_path: Path | str = DB_PATH) -> list[WorkflowState]:
    return [run_workflow(item["booth_id"], db_path=db_path) for item in db.get_booths(db_path)]


def ensure_predictions(db_path: Path | str = DB_PATH) -> None:
    if not db.query_one("SELECT 1 FROM predictions LIMIT 1", db_path=db_path):
        analyze_all(db_path)
