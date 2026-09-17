"""Deterministic action policy applied after ML prediction."""

from __future__ import annotations

from typing import Any

from services.database import get_booth_state, get_booths


def action_candidates(
    booth: dict[str, Any], prediction: dict[str, Any], db_path: str
) -> list[dict[str, str]]:
    risk = prediction["risk_level"]
    candidates: list[dict[str, str]] = []
    if risk == "LOW":
        return [{"action_type": "MAINTAIN", "reason": "예상 잔여비율이 10% 미만입니다."}]

    candidates.append(
        {
            "action_type": "STOP_COOKING",
            "reason": f"종료 시 {prediction['expected_remaining']}개가 남을 것으로 예측되어 추가 조리를 보류합니다.",
        }
    )
    if risk == "MEDIUM":
        candidates.append({"action_type": "MONITOR", "reason": "판매 추이를 15분 후 다시 확인합니다."})
        return candidates

    candidates.append(
        {
            "action_type": "DISCOUNT",
            "reason": "폐기위험 HIGH이며 최근 판매가 감소해 운영자 승인 후 20% 할인을 권장합니다.",
        }
    )
    other_b_demand = [
        get_booth_state(item["booth_id"], db_path)
        for item in get_booths(db_path)
        if item["zone"] == "B" and item["booth_id"] != booth["booth_id"]
    ]
    if other_b_demand and max(item["recent_sales_30m"] for item in other_b_demand) > booth["recent_sales_30m"]:
        candidates.append(
            {
                "action_type": "TRANSFER",
                "reason": "B구역 최근 수요가 더 높아 이동 가능한 공용 재고가 있다면 재배치를 검토합니다.",
            }
        )
    candidates.append(
        {
            "action_type": "PROMOTION",
            "reason": "학생 화면 노출로 수요를 유도하되 할인 실행은 운영자 승인이 필요합니다.",
        }
    )
    return candidates

