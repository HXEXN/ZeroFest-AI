"""Grounded admin chat with an optional LLM explanation layer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import DB_PATH, OPENAI_MODEL
from services import database as db


def _snapshot(db_path: Path | str) -> list[dict[str, Any]]:
    keys = [
        "booth_id", "booth_name", "zone", "menu_name", "current_stock", "recent_sales_30m",
        "expected_remaining", "risk_level", "predicted_sales_60m", "action_type",
    ]
    return [{key: row.get(key) for key in keys} for row in db.dashboard_rows(db_path)]


def _grounded_fallback(question: str, rows: list[dict[str, Any]]) -> str:
    priority = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    high = sorted(
        rows,
        key=lambda row: (priority.get(str(row.get("risk_level")), -1), int(row.get("expected_remaining") or 0)),
        reverse=True,
    )
    target = next((row for row in rows if row["menu_name"] in question or row["booth_name"] in question), None)
    if "가장" in question or "위험" in question:
        row = high[0]
        return (
            f"현재 폐기위험이 가장 높은 곳은 **{row['zone']}구역 {row['booth_name']}**입니다. "
            f"재고 {row['current_stock']}개 중 종료 시 {row['expected_remaining']}개가 남을 것으로 예측되어 "
            f"위험도는 **{row['risk_level']}**입니다."
        )
    if "왜" in question or "이유" in question:
        row = target or high[0]
        return (
            f"{row['menu_name']}는 최근 30분 판매가 {row['recent_sales_30m']}개이고 현재 재고는 "
            f"{row['current_stock']}개입니다. 1시간 뒤 강수확률과 공연 종료 영향을 반영하면 "
            f"예상 잔여가 {row['expected_remaining']}개여서 할인을 권장합니다. 이는 예측이며 최종 실행은 운영자가 승인합니다."
        )
    if "어디" in question or "이동" in question or "보내" in question:
        return "최근 판매가 증가 중인 **B구역**을 우선 후보로 권장합니다. 이동 가능한 공용 재고인지 확인한 뒤 운영자가 결정해 주세요."
    return "현재 데이터 기준으로 폐기위험, 재고, 할인 이유 또는 재고 이동 후보를 질문해 주세요. 확인되지 않은 정보는 답변하지 않습니다."


def ask_admin(question: str, db_path: Path | str = DB_PATH) -> tuple[str, str]:
    rows = _snapshot(db_path)
    fallback = _grounded_fallback(question, rows)
    if not os.getenv("OPENAI_API_KEY"):
        return fallback, "Grounded local fallback"
    try:
        from openai import OpenAI

        prompt = (
            "당신은 ZeroFest 축제 운영 AI다. 아래 JSON의 값만 근거로 한국어 4문장 이내로 답하라. "
            "모르는 정보는 모른다고 하고, 모든 Action은 운영자 승인이 필요하다고 명시하라.\n"
            f"DATA={json.dumps(rows, ensure_ascii=False)}\nQUESTION={question}"
        )
        response = OpenAI().responses.create(model=OPENAI_MODEL, input=prompt)
        return response.output_text, f"{OPENAI_MODEL} grounded explanation"
    except Exception:
        return fallback, "Grounded local fallback (LLM unavailable)"
