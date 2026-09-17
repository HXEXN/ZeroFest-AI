"""ZeroFest AI landing page."""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions
from components.ui import configure_page, demo_banner, flow_strip
from services.database import initialize_database


configure_page("시작", "🌿")
st.markdown(
    "<style>[data-testid='stSidebar']{display:none;}"
    "[data-testid='stSidebarCollapsedControl']{display:none;}</style>",
    unsafe_allow_html=True,
)
initialize_database()
ensure_predictions()

left, right = st.columns([1.3, 0.7], gap="large")
with left:
    st.markdown('<div class="zf-kicker">AI FESTIVAL OPERATING SYSTEM</div>', unsafe_allow_html=True)
    st.markdown('<div class="zf-hero">남기 전에,<br>축제를 바꿉니다.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="zf-subtitle">판매·재고·날씨·공연 데이터를 읽고 AI Agent가 운영 Action을 제안합니다. '
        '운영자가 승인한 할인은 학생 수요를 움직이고, 결과는 다시 예측에 반영됩니다.</div>',
        unsafe_allow_html=True,
    )
    flow_strip()
    demo_banner()
    st.markdown(
        '<span class="zf-provenance">2023–2025 과거 축제 이력 Adapter · Sample / Synthetic</span>',
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        """
        <div class="zf-card" style="margin-top:1.5rem;padding:1.5rem">
          <div class="zf-kicker">LIVE DEMO · 19:00</div>
          <h2 style="margin:.4rem 0;color:#102a22">A구역 닭꼬치</h2>
          <div style="font-size:2.6rem;font-weight:850;color:#ef4444">180 <small style="font-size:1rem">재고</small></div>
          <p class="zf-muted">최근 판매 감소 · 1시간 뒤 강수 80% · 공연 종료 예정</p>
          <div class="zf-risk-high">예상 잔여 70 · HIGH</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### 역할별 분리 진입")
col1, col2, col3, col4 = st.columns(4, gap="medium")
roles = [
    (col1, "📊", "학생회", "축제 전체 Supply / Demand와 폐기위험을 관리합니다.", "pages/admin.py", "Control Tower 열기"),
    (col2, "🧑‍🍳", "부스 운영자", "바쁜 현장에서 원클릭 입력하고 AI Action을 승인합니다.", "pages/operator.py", "내 부스 열기"),
    (col3, "🎓", "학생", "지금 받을 수 있는 할인과 축제 지도를 확인합니다.", "pages/student.py", "학생 혜택 보기"),
    (col4, "🧠", "AI 운영", "과거 데이터, 학습 파이프라인과 Agent를 관리합니다.", "pages/ai_ops.py", "AI Ops 열기"),
]
for column, icon, title, body, page, label in roles:
    with column:
        st.markdown(
            f'<div class="zf-card"><div style="font-size:2rem">{icon}</div><h3>{title}</h3><p class="zf-muted">{body}</p></div>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=label, width="stretch")

st.divider()
st.caption("ZeroFest AI · EST AI Challengers 2기 Hackathon MVP · Sample / Synthetic Festival Dataset")
