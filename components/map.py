"""Privacy-safe zone map driven by the live booth state.

The layout is deliberately schematic: zones, not coordinates. Booth latitude and
longitude exist in the database but are never rendered, and nothing here reads a
visitor's location. What the map does show — how many booths a zone has, its
worst waste risk, whether a discount is live — comes from the same rows the
dashboard uses, so the map cannot disagree with the numbers next to it.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

RISK_STYLE = {
    "HIGH": ("#ef4444", "#fef2f2", "위험"),
    "MEDIUM": ("#f59e0b", "#fffbeb", "주의"),
    "LOW": ("#10b981", "#ecfdf5", "안정"),
}
RISK_ORDER = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


def _zone_summary(rows: list[dict[str, Any]], promotions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    discounted_zones = {item["zone"] for item in promotions}
    zones: dict[str, dict[str, Any]] = {}
    for row in rows:
        zone = str(row.get("zone", "-"))
        entry = zones.setdefault(zone, {"zone": zone, "booths": 0, "remaining": 0, "risk": "LOW", "menus": []})
        entry["booths"] += 1
        entry["remaining"] += int(row.get("expected_remaining") or 0)
        entry["menus"].append(str(row.get("menu_name", "")))
        risk = str(row.get("risk_level") or "LOW")
        if RISK_ORDER.get(risk, 0) > RISK_ORDER.get(entry["risk"], 0):
            entry["risk"] = risk
    for entry in zones.values():
        entry["discounted"] = entry["zone"] in discounted_zones
    return sorted(zones.values(), key=lambda item: item["zone"])


def festival_map(
    rows: list[dict[str, Any]],
    promotions: list[dict[str, Any]] | None = None,
    stage_name: str | None = None,
    admin: bool = False,
) -> None:
    summary = _zone_summary(rows, promotions or [])
    if not summary:
        st.info("표시할 부스가 없습니다.")
        return

    cards = []
    for entry in summary:
        border, background, label = RISK_STYLE.get(entry["risk"], RISK_STYLE["LOW"])
        if entry["discounted"]:
            badge = '<div style="margin-top:.35rem;font-weight:800;color:#c2410c">🔥 마감 할인 진행 중</div>'
        elif admin:
            badge = f'<div style="margin-top:.35rem;color:#475569">예상 잔여 {entry["remaining"]}개</div>'
        else:
            badge = f'<div style="margin-top:.35rem;color:#475569">부스 {entry["booths"]}곳</div>'
        menus = " · ".join(dict.fromkeys(m for m in entry["menus"] if m))[:34]
        cards.append(
            f"""<div style="flex:1;min-width:150px;background:{background};border:2px solid {border};
                        border-radius:16px;padding:14px;box-shadow:0 8px 18px #0001">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <b style="font-size:1.05rem">{entry['zone']} ZONE</b>
                <span style="font-size:.7rem;font-weight:800;color:{border}">{label}</span>
              </div>
              <div style="font-size:.82rem;color:#334155;margin-top:.3rem">{menus}</div>
              {badge}
            </div>"""
        )

    stage = stage_name or "Main Stage"
    st.markdown(
        f"""
        <div style="border-radius:18px;background:linear-gradient(145deg,#eaedff,#f2f3ff);
                    border:1px solid #d8def8;padding:20px">
          <div style="background:#102a22;color:white;border-radius:16px;padding:14px;text-align:center;
                      font-weight:800;margin-bottom:16px">🎤 {stage}
            <br><small style="color:#a7f3d0">공연 구역 · 혼잡</small></div>
          <div style="display:flex;gap:12px;flex-wrap:wrap">{''.join(cards)}</div>
          <div style="margin-top:14px;color:#547268;font-size:.78rem">
            구역 단위 표시 · 정밀 위치 추적 없음</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
