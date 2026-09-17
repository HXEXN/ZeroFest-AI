"""Mobile-first ZeroFest role gateway matching the Stitch reference."""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions, run_workflow
from components.ui import MOBILE_NAV, configure_page, mobile_bottom_nav, mobile_header
from services import database as db


configure_page("게이트웨이", "🌿", mobile=True)
db.initialize_database()
ensure_predictions()

mobile_header("ZeroFest AI", "ASTRA 축제 포털 · 2026", "REALTIME", "ZF")

st.markdown(
    """
    <section class="zf-mobile-card mint" style="padding:20px;overflow:hidden;position:relative">
      <div class="zf-mobile-row"><span class="zf-eyebrow">◉ ASTRA 2026 AI FESTIVAL INTELLIGENCE</span>
      <span class="zf-status"><span class="zf-dot"></span>SYNC</span></div>
      <div class="zf-mobile-h1">축제를 더 많이 팔고,<br><span style="color:#047857">덜 버리게.</span></div>
      <div class="zf-caption">실시간 AI 수요 예측 & 폐기 방지 OS</div>
      <div style="height:132px;margin-top:15px;border-radius:13px;overflow:hidden;position:relative;
        background:linear-gradient(135deg,#063d2d,#0b6b4c 45%,#f97316);">
        <div style="position:absolute;inset:0;background:radial-gradient(circle at 70% 25%,rgba(255,255,255,.22),transparent 30%);"></div>
        <div style="position:absolute;left:15px;right:15px;bottom:13px;display:flex;
                    justify-content:space-between;align-items:flex-end;gap:10px">
          <div style="color:white;font-weight:900;font-size:13px;line-height:1.25">⚡ FESTIVAL<br>CORE OS LIVE</div>
          <div style="color:#a7f3d0;font-weight:900;font-size:13px;line-height:1.25;text-align:right">
            ASTRA-CAMPUS<br>01</div>
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

rows = db.dashboard_rows()
total_stock = sum(int(row["current_stock"]) for row in rows)
expected_remaining = sum(int(row.get("expected_remaining") or 0) for row in rows)
high_count = sum(row.get("risk_level") == "HIGH" for row in rows)
weather = db.get_weather_context().get("forecast_1h", {})

st.markdown(
    f"""
    <div class="zf-section-title"><strong>📡 실시간 관제 텔레메트리</strong><span class="zf-pill low">초 단위 동기화</span></div>
    <div class="zf-kpi-grid">
      <div class="zf-kpi"><div class="zf-kpi-label">운영 부스 현황</div><div class="zf-kpi-value">{len(rows)}곳</div><div class="zf-kpi-note zf-mint-text">● 실시간 참여</div></div>
      <div class="zf-kpi danger"><div class="zf-kpi-label">폐기 위험 부스</div><div class="zf-kpi-value zf-danger-text">{high_count}곳</div><div class="zf-kpi-note zf-danger-text">즉각 대응 필요</div></div>
      <div class="zf-kpi"><div class="zf-kpi-label">예상 잔여 재고</div><div class="zf-kpi-value zf-mint-text">{expected_remaining}개</div><div class="zf-kpi-note">총 재고 {total_stock}개</div></div>
      <div class="zf-kpi"><div class="zf-kpi-label">기상 레이더</div><div class="zf-kpi-value">{float(weather.get('temperature') or 0):g}°C</div><div class="zf-kpi-note" style="color:#9a3412">강수 {int(weather.get('precipitation_probability') or 0)}% 사전대응</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

state = db.get_booth_state("booth-chicken")
prediction = db.get_latest_prediction("booth-chicken") or {}
baseline = int(prediction.get("expected_remaining") or 0)
projected_after = max(0, round(baseline * 0.26))
reduction = (baseline - projected_after) / max(1, baseline)

with st.container(border=True):
    st.markdown(
        f"""
        <div class="zf-mobile-row"><span class="zf-pill low">⚡ LIVE DEMO</span><span class="zf-status">5 SEC LOOP</span></div>
        <div class="zf-mobile-h2" style="margin-top:11px">⚡ 5초 AI 폐기 방지 루프</div>
        <div class="zf-caption">위험 감지부터 타임세일 소비까지 자율 자동화 Demo</div>
        <div class="zf-action-row" style="margin-top:12px;text-align:center">
          재고 {state['current_stock']} → AI 잔여 {baseline} 예측 → 20% 세일<br>
          <b>학생 완판 연동 · 잔여 {projected_after}개 (폐기 {reduction:.1%}↓)</b>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("▶ 시뮬레이터 시작", type="primary", width="stretch"):
        run_workflow("booth-chicken")
        discount = next(
            (
                item
                for item in db.get_actions("booth-chicken", "PENDING")
                if item["action_type"] == "DISCOUNT"
            ),
            None,
        )

        if discount:
            run_workflow("booth-chicken", [discount["action_id"]])

        if db.get_active_promotions():
            response = db.simulate_student_response()
            run_workflow("booth-chicken")
            st.session_state["gateway_loop_result"] = response
            st.rerun()

    # 시연용 초기화: DB를 19:00 초기 상태로 복원하고 세션 결과도 제거
    if st.button("↻ 시뮬레이터 초기화", width="stretch"):
        with st.spinner("19:00 초기 상태로 복원하는 중..."):
            db.reset_demo()
        st.session_state.clear()
        st.rerun()

    if "gateway_loop_result" in st.session_state:
        response = st.session_state["gateway_loop_result"]
        st.success(
            f"루프 완료 · {response['sold']}개 판매 반영 · "
            f"{response['to'][-5:]} 상태로 재예측"
        )

st.markdown('<div class="zf-section-title"><strong>🛡 권한별 게이트웨이</strong><span class="zf-pill medium">ROLE ISOLATION</span></div>', unsafe_allow_html=True)

roles = [
    ("🛡", "총괄 관리자", "MASTER", "축제 통합 관제망 및 AI 제어", "전체 부스 실시간 관제와 폐기 타임세일 최종 승인", "pages/admin.py", "🔑 관리자 접속하기"),
    ("🏪", "부스 운영자 POS", "OPERATOR", "1초 판매 등록 & 동적할인 승인", "원터치 판매·실재고 교정·AI 할인 추천", "pages/operator.py", "🏪 POS 시작하기"),
    ("🎟", "일반 학생 / 방문객", "PUBLIC", "핫딜 알림 · 스마트 지도 · 스탬프", "부스별 할인과 폐기 방지 타임세일 쿠폰", "pages/student.py", "🎉 학생 포털 입장"),
]
for icon, title, badge, subtitle, body, page, button in roles:
    with st.container(border=True):
        st.markdown(
            f'<div class="zf-booth-head"><div class="zf-mobile-h2">{icon} {title}</div><span class="zf-pill low">{badge}</span></div>'
            f'<div class="zf-eyebrow" style="margin-top:6px">{subtitle}</div><p class="zf-caption">{body}</p>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=button, width="stretch")

st.markdown(
    '<div class="zf-mobile-card" style="background:#eef2ff"><b>🛡 권한 격리 세션 Zero Trust</b>'
    '<div class="zf-caption">각 역할은 독립 보안 세션으로 접속하며 실행 권한은 분리됩니다.</div></div>',
    unsafe_allow_html=True,
)

mobile_bottom_nav(MOBILE_NAV, "gateway")
