"""Judge-friendly end-to-end before/after simulation."""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions, run_workflow
from components.charts import before_after
from components.ui import configure_page, flow_strip, page_header, sidebar
from services import database as db


configure_page("Before / After", "🧪")
db.initialize_database()
ensure_predictions()
sidebar("AI Simulation")
page_header(
    "END-TO-END · JUDGE DEMO",
    "예측에서 끝나지 않는 Closed Loop",
    "Action이 학생 수요를 바꾸고 예상 잔여를 낮춘 뒤 다시 예측되는 전체 흐름을 한 화면에서 확인합니다.",
)
flow_strip()

state = db.get_booth_state("booth-chicken")
prediction = db.get_latest_prediction("booth-chicken") or {}
promotions = [item for item in db.get_active_promotions() if item["booth_id"] == "booth-chicken"]
simulated = state["student_response_simulated"]
before = 70
after = int(prediction.get("expected_remaining", 15 if simulated else before)) if simulated else before

status_cols = st.columns(5)
steps = [
    ("1", "위험 감지", True),
    ("2", "AI Action", True),
    ("3", "운영자 승인", bool(promotions)),
    ("4", "학생 노출", bool(promotions)),
    ("5", "재예측", simulated),
]
for column, (number, label, done) in zip(status_cols, steps):
    column.markdown(
        f'<div class="zf-card" style="text-align:center;border-color:{"#10b981" if done else "#dce9e3"}">'
        f'<div style="font-size:1.4rem">{"✓" if done else number}</div><b>{label}</b></div>',
        unsafe_allow_html=True,
    )

left, right = st.columns([1.2, 0.8], gap="large")
with left:
    st.plotly_chart(before_after(before, after), width="stretch", config={"displayModeBar": False})
    st.caption("시뮬레이션 예측값 비교이며 실제 폐기 감소 실증 수치가 아닙니다.")
with right:
    st.markdown("#### 19:00 · A구역 닭꼬치")
    st.markdown("- 현재 재고 **180개**\n- 최근 30분 판매 감소\n- 1시간 뒤 강수확률 **80%**\n- 메인 공연 종료 예정")
    st.error("AI 적용 전 · 예상 잔여 **70개** · HIGH")
    if promotions and not simulated:
        st.success("20% 할인이 학생 화면에 노출되었습니다.")
        if st.button("학생 반응 발생 → 재예측", type="primary", width="stretch"):
            db.simulate_student_response()
            run_workflow("booth-chicken")
            st.rerun()
    elif simulated:
        st.success(f"AI Action 후 · 예상 잔여 **{after}개** · LOW")
        st.caption("할인 노출에 따른 추가 수요를 가정한 Demo Simulation입니다.")
    else:
        st.warning("먼저 운영자 화면에서 20% 할인을 승인해 주세요.")
        st.page_link("pages/operator.py", label="할인 승인하러 가기", icon="🧑‍🍳")

st.divider()
st.markdown("### 발표용 3분 시나리오")
st.markdown(
    "1. **Admin**에서 닭꼬치 예상 잔여 70개·HIGH와 판단 근거를 확인합니다.\n"
    "2. **Operator**에서 20% 할인 Action을 승인합니다.\n"
    "3. **Student**에서 6,000원 → 4,800원 마감 할인을 확인합니다.\n"
    "4. 이 화면에서 학생 반응을 실행하면 예상 잔여가 70개 → 15개로 재예측됩니다."
)
