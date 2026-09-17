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


STUDENT_STYLE = {
    "HIGH": ("#f97316", "#fff7ed", "🔥 마감 특가"),
    "MEDIUM": ("#f59e0b", "#fffbeb", "⚡ 혜택 임박"),
    "LOW": ("#10b981", "#ecfdf5", "✨ 부스 운영"),
}


def festival_map(
    rows: list[dict[str, Any]],
    promotions: list[dict[str, Any]] | None = None,
    stage_name: str | None = None,
    stage_schedule: str | None = None,
    admin: bool = False,
) -> None:
    summary = _zone_summary(rows, promotions or [])
    if not summary:
        st.info("표시할 부스가 없습니다.")
        return

    style_map = RISK_STYLE if admin else STUDENT_STYLE
    cards = []
    for entry in summary:
        border, background, label = style_map.get(entry["risk"], style_map["LOW"])
        if entry["discounted"]:
            badge = '<div style="margin-top:.35rem;font-weight:850;font-size:.76rem;color:#ea580c">🔥 타임세일 중!</div>'
        elif admin:
            badge = f'<div style="margin-top:.35rem;color:#475569;font-size:.76rem">예상 잔여 {entry["remaining"]}개</div>'
        else:
            badge = f'<div style="margin-top:.35rem;color:#64748b;font-size:.74rem">부스 {entry["booths"]}곳 · 주문가능</div>'
        menus = " · ".join(dict.fromkeys(m for m in entry["menus"] if m))[:24]
        cards.append(
            f"""<div style="background:{background};border:1.5px solid {border};
                        border-radius:14px;padding:10px 11px;box-shadow:0 2px 6px rgba(0,0,0,.04);box-sizing:border-box">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <b style="font-size:.95rem;color:#1e293b">{entry['zone']} ZONE</b>
                <span style="font-size:.68rem;font-weight:850;color:{border}">{label}</span>
              </div>
              <div style="font-size:.75rem;color:#475569;margin-top:.25rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{menus}">{menus}</div>
              {badge}
            </div>"""
        )

    stage = stage_name or "Main Stage"
    schedule_sub = stage_schedule or "공연 구역 · 3,000명 밀집"
    st.markdown(
        f"""
        <div style="border-radius:18px;background:linear-gradient(145deg,#eaedff,#f2f3ff);
                    border:1px solid #d8def8;padding:14px;box-sizing:border-box">
          <div style="background:#102a22;color:white;border-radius:14px;padding:11px 14px;text-align:center;
                      font-weight:800;margin-bottom:12px">🎤 {stage}
            <br><small style="color:#a7f3d0;font-size:.75rem">{schedule_sub}</small></div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px;box-sizing:border-box">{''.join(cards)}</div>
          <div style="margin-top:10px;color:#547268;font-size:.73rem;display:flex;justify-content:space-between;align-items:center">
            <span>구역 단위 표시 · 위치 추적 없음</span>
            <span>{"관리자 모드" if admin else "학생 혜택 연동"}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
