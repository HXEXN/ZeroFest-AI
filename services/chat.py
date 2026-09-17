"""Grounded operations copilot over the live ZeroFest database.

The language model is deliberately an optional explanation layer. Every number
and recommended action is assembled from the current database first, so the
chat remains useful in a public demo without an API key and cannot invent an
operational state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import ACTION_LABELS, DB_PATH, OPENAI_MODEL
from services import database as db


def _snapshot(db_path: Path | str) -> list[dict[str, Any]]:
    keys = [
        "booth_id", "booth_name", "zone", "menu_name", "current_stock",
        "recent_sales_30m", "previous_sales_30m", "total_sales", "expected_remaining",
        "risk_level", "predicted_sales_30m", "predicted_sales_60m", "estimated_stockout_at",
        "minutes_to_stockout", "stockout_before_close", "action_type", "drivers",
    ]
    return [{key: row.get(key) for key in keys} for row in db.dashboard_rows(db_path)]


def _target(question: str, rows: list[dict[str, Any]], booth_id: str | None) -> dict[str, Any]:
    if booth_id:
        scoped = next((row for row in rows if row["booth_id"] == booth_id), None)
        if scoped:
            return scoped
    mentioned = next(
        (
            row for row in rows
            if str(row["menu_name"]) in question
            or str(row["booth_name"]) in question
            or f"{row['zone']}구역" in question
        ),
        None,
    )
    if mentioned:
        return mentioned
    priority = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    return max(
        rows,
        key=lambda row: (priority.get(str(row.get("risk_level")), -1), int(row.get("expected_remaining") or 0)),
    )


def _stockout_label(row: dict[str, Any]) -> str:
    timestamp = row.get("estimated_stockout_at")
    if not timestamp:
        return "행사 종료 전 품절 예상 없음"
    return f"{str(timestamp)[11:16]}경 품절 예상(약 {int(row.get('minutes_to_stockout') or 0)}분 후)"


def _grounded_answer(
    question: str,
    rows: list[dict[str, Any]],
    booth_id: str | None,
    db_path: Path | str,
) -> tuple[str, list[str]]:
    if not rows:
        return "분석할 부스 데이터가 없습니다.", ["운영 DB · 데이터 없음"]
    row = _target(question, rows, booth_id)
    pending = db.get_actions(row["booth_id"], "PENDING", db_path)
    action_names = [ACTION_LABELS.get(item["action_type"], item["action_type"]) for item in pending]
    weather = db.get_weather_context(db_path).get("forecast_1h", {})
    evidence = [
        f"{row['zone']}구역 {row['booth_name']} · 현재 재고 {int(row['current_stock'])}개",
        f"최근 30분 {int(row['recent_sales_30m'])}개 · 다음 30분 예측 {int(row['predicted_sales_30m'] or 0)}개",
        f"종료 예상 잔여 {int(row['expected_remaining'] or 0)}개 · {row['risk_level']}",
    ]
    q = question.replace(" ", "").lower()

    if any(token in q for token in ["요약", "브리핑", "현황", "상황"]):
        high = sum(item.get("risk_level") == "HIGH" for item in rows)
        total_stock = sum(int(item.get("current_stock") or 0) for item in rows)
        total_remaining = sum(int(item.get("expected_remaining") or 0) for item in rows)
        answer = (
            f"현재 전체 재고는 **{total_stock}개**, 종료 예상 잔여는 **{total_remaining}개**이며 "
            f"HIGH 위험 부스는 **{high}곳**입니다. 우선 대응 대상은 **{row['zone']}구역 "
            f"{row['booth_name']}**로, 예상 잔여 {row['expected_remaining']}개입니다. "
            f"대기 Action은 {', '.join(action_names) if action_names else '없음'}이며 실행 전 운영자 승인이 필요합니다."
        )
    elif any(token in q for token in ["품절", "소진", "언제다", "몇시"]):
        answer = (
            f"**{row['menu_name']}**는 현재 재고 {row['current_stock']}개, 1시간 예상 판매 "
            f"{row['predicted_sales_60m']}개 기준으로 **{_stockout_label(row)}**입니다. "
            "판매·재고 입력이 바뀌면 즉시 재예측해야 합니다."
        )
    elif any(token in q for token in ["날씨", "비", "강수"]):
        answer = (
            f"1시간 뒤 강수확률은 **{int(weather.get('precipitation_probability') or 0)}%**, "
            f"예상 강수량은 **{float(weather.get('rainfall') or 0):g}mm**입니다. "
            f"이를 포함한 모델 예측에서 {row['menu_name']} 종료 잔여는 {row['expected_remaining']}개, "
            f"위험도는 **{row['risk_level']}**입니다."
        )
        evidence.append(f"{weather.get('provider', 'Weather')} · 1시간 예보")
    elif any(token in q for token in ["action", "액션", "추천", "뭘해야", "조치"]):
        answer = (
            f"**{row['zone']}구역 {row['booth_name']}**의 현재 추천은 "
            f"**{', '.join(action_names) if action_names else '현 상태 유지'}**입니다. "
            f"종료 예상 잔여 {row['expected_remaining']}개와 {row['risk_level']} 위험도를 기준으로 생성됐습니다. "
            "채팅은 실행하지 않으며, 운영자 화면에서 근거를 확인한 뒤 승인해야 합니다."
        )
    elif any(token in q for token in ["왜", "이유", "근거", "할인"]):
        answer = (
            f"{row['menu_name']}는 최근 30분 판매가 {row['recent_sales_30m']}개이고 현재 재고는 "
            f"{row['current_stock']}개입니다. 날씨·공연·판매속도를 반영하면 종료 예상 잔여가 "
            f"{row['expected_remaining']}개여서 **{row['risk_level']}**로 판단했습니다. "
            f"현재 대기 제안은 {', '.join(action_names) if action_names else '없음'}이며 최종 실행은 운영자가 승인합니다."
        )
    elif any(token in q for token in ["어디", "이동", "보내", "이관"]):
        candidates = sorted(
            (item for item in rows if item["booth_id"] != row["booth_id"]),
            key=lambda item: int(item.get("recent_sales_30m") or 0),
            reverse=True,
        )
        destination = candidates[0] if candidates else row
        answer = (
            f"최근 30분 수요가 가장 높은 후보는 **{destination['zone']}구역 {destination['booth_name']}**"
            f"({destination['recent_sales_30m']}개)입니다. 다만 메뉴·보관 조건이 같은 공용 재고인지 확인해야 하며, "
            "실제 이관은 운영자가 승인해야 합니다."
        )
        evidence.append(f"이관 후보 최근 30분 판매 · {destination['recent_sales_30m']}개")
    elif any(token in q for token in ["위험", "가장", "우선"]):
        answer = (
            f"현재 우선 대응 대상은 **{row['zone']}구역 {row['booth_name']}**입니다. "
            f"재고 {row['current_stock']}개 중 종료 시 {row['expected_remaining']}개가 남을 것으로 예측되어 "
            f"위험도는 **{row['risk_level']}**입니다. {_stockout_label(row)}입니다."
        )
    else:
        answer = (
            f"선택 범위의 핵심 상태는 **{row['zone']}구역 {row['booth_name']} · "
            f"{row['risk_level']} · 예상 잔여 {row['expected_remaining']}개**입니다. "
            "위험 우선순위, 할인 근거, 품절 예상 시각, 날씨 영향 또는 추천 Action을 질문해 주세요."
        )
    return answer, evidence


def ask_operations(
    question: str,
    booth_id: str | None = None,
    db_path: Path | str = DB_PATH,
) -> tuple[str, str, list[str]]:
    """Answer from a frozen live snapshot, optionally scoped to one booth."""
    rows = _snapshot(db_path)
    fallback, evidence = _grounded_answer(question, rows, booth_id, db_path)
    if not os.getenv("OPENAI_API_KEY"):
        return fallback, "Grounded Operations Engine", evidence
    try:
        from openai import OpenAI

        payload = {"booths": rows, "weather": db.get_weather_context(db_path), "scope": booth_id}
        prompt = (
            "당신은 ZeroFest 축제 운영 Copilot이다. DATA에 있는 값만 근거로 한국어 4문장 이내로 답하라. "
            "수치·위험판정은 바꾸지 말고, 모르면 모른다고 하며, Action 실행에는 운영자 승인이 필요하다고 명시하라.\n"
            f"DATA={json.dumps(payload, ensure_ascii=False, default=str)}\nQUESTION={question}"
        )
        response = OpenAI().responses.create(model=OPENAI_MODEL, input=prompt)
        return response.output_text, f"{OPENAI_MODEL} · grounded explanation", evidence
    except Exception:
        return fallback, "Grounded Operations Engine · LLM fallback", evidence


def ask_admin(question: str, db_path: Path | str = DB_PATH) -> tuple[str, str]:
    """Backward-compatible admin API used by tests and the compact dashboard."""
    answer, source, _ = ask_operations(question, db_path=db_path)
    legacy_source = "Grounded local fallback" if source == "Grounded Operations Engine" else source
    return answer, legacy_source
