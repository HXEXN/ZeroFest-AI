"""Configurable, explainable waste-risk classification."""

from __future__ import annotations

from config import RISK_HIGH_THRESHOLD, RISK_LOW_THRESHOLD


def classify_waste_risk(
    expected_remaining: int,
    current_stock: int,
    low_threshold: float = RISK_LOW_THRESHOLD,
    high_threshold: float = RISK_HIGH_THRESHOLD,
) -> dict[str, float | str]:
    """Classify risk from projected remaining/current stock ratio.

    Keeping this deterministic makes the operational decision auditable even
    when the upstream ML model changes.
    """
    ratio = expected_remaining / max(current_stock, 1)
    if ratio < low_threshold:
        level = "LOW"
    elif ratio < high_threshold:
        level = "MEDIUM"
    else:
        level = "HIGH"
    return {
        "risk_level": level,
        "remaining_ratio": round(ratio, 3),
        "low_threshold": low_threshold,
        "high_threshold": high_threshold,
    }

