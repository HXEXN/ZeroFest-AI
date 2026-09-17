"""One-click booth operations and human-in-the-loop approval."""

from __future__ import annotations

import streamlit as st
from datetime import datetime

from agents.graph import ensure_predictions, run_workflow
from components.ui import MOBILE_NAV, configure_page, mobile_bottom_nav, mobile_header, page_header, risk_badge, sidebar
from config import ACTION_LABELS
from services import database as db


configure_page("부스 운영자", "🧑‍🍳", mobile=True)
st.markdown(
    "<style>div.stButton>button{min-height:56px;font-size:.96rem}"
    "button[kind='primary']{background:#9a3412!important;border-color:#9a3412!important}</style>",
    unsafe_allow_html=True,
)
db.initialize_database()
ensure_predictions()
sidebar("부스 운영자")
mobile_header("ZeroFest POS", "원터치 주문 입력과 Action 승인", "POS LIVE", "POS")
page_header(
    "OPERATOR · HUMAN IN THE LOOP",
    "바쁜 순간엔, 세 번의 탭이면 충분합니다",
    "판매 입력 → AI 추천 확인 → 최종 승인. AI는 제안하고 운영자가 결정합니다.",
)

booths = db.get_booths()
labels = {item["booth_id"]: f"{item['zone']}구역 · {item['booth_name']} ({item['menu_name']})" for item in booths}
default_index = [item["booth_id"] for item in booths].index("booth-chicken")
booth_id = st.selectbox("내 부스", list(labels), format_func=labels.get, index=default_index)
state = db.get_booth_state(booth_id)
prediction = db.get_latest_prediction(booth_id) or {}

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("오늘 판매", f"{state['total_sales']}개", f"최근 30분 {state['recent_tickets_30m']}팀")
m2.metric("현재 재고", f"{state['current_stock']}개")
m3.metric("1시간 예상 판매", f"{prediction.get('predicted_sales_60m', 0)}개")
stockout_at = prediction.get("estimated_stockout_at")
stockout_label = datetime.fromisoformat(stockout_at).strftime("%H:%M") if stockout_at else "없음"
m4.metric("품절 예상 시각", stockout_label)
m5.metric("종료 예상 잔여", f"{prediction.get('expected_remaining', 0)}개")

left, right = st.columns([0.82, 1.18], gap="large")
with left:
    st.markdown("#### 원클릭 운영 입력")
    st.caption("한 번 누르면 한 팀의 주문입니다. 판매량과 재고, 주문 건수가 함께 기록됩니다.")
    sale_cols = st.columns(3)
    for column, quantity in zip(sale_cols, [1, 5, 10]):
        if column.button(f"{quantity}개 주문", width="stretch", key=f"sale-{booth_id}-{quantity}"):
            # One press is one party. Recording parties separately from items is
            # what lets the model see basket size, not just sales volume.
            db.record_sale(booth_id, quantity)
            run_workflow(booth_id)
            st.rerun()
    stock_cols = st.columns(2)
    if stock_cols[0].button("재고 −10", width="stretch", key=f"minus-{booth_id}"):
        db.adjust_stock(booth_id, -10)
        run_workflow(booth_id)
        st.rerun()
    if stock_cols[1].button("추가 준비 +10", width="stretch", key=f"plus-{booth_id}"):
        db.adjust_stock(booth_id, 10)
        run_workflow(booth_id)
        st.rerun()
    with st.form(f"exact-stock-{booth_id}"):
        exact_stock = st.number_input(
            "실재고 직접 입력", min_value=0, value=int(state["current_stock"]), step=1,
            help="실사한 수량으로 재고 스냅샷을 교정합니다.",
        )
        if st.form_submit_button("실재고 적용", width="stretch"):
            db.set_stock(booth_id, int(exact_stock))
            run_workflow(booth_id)
            st.session_state["operator_notice"] = f"실재고를 {int(exact_stock)}개로 교정했습니다."
            st.rerun()
    st.caption("입력값은 Demo SQLite 상태에만 저장됩니다.")

with right:
    st.markdown("#### AI Recommendation")
    st.markdown(risk_badge(prediction.get("risk_level", "LOW")), unsafe_allow_html=True)
    st.markdown(
        f"**종료 시 {prediction.get('expected_remaining', 0)}개 잔여 예상**  \n"
        f"30분 {prediction.get('predicted_sales_30m', 0)}개 · 1시간 {prediction.get('predicted_sales_60m', 0)}개 판매 예측"
    )
    if prediction.get("stockout_before_close"):
        st.warning(
            f"⚠️ 현재 판매속도 유지 시 **{stockout_label} 품절 예상** · "
            f"약 {prediction.get('minutes_to_stockout', 0)}분 후"
        )
    else:
        st.info("현재 판매속도 기준, 당일 행사 종료 전 품절 예상은 없습니다.")
    with st.expander("예측 근거 보기", expanded=True):
        for driver in prediction.get("drivers", []):
            st.markdown(f"- {driver}")
        st.caption(f"Model · {prediction.get('model_source', 'prediction unavailable')}")
    st.page_link(
        "pages/chat.py", label="✨ 이 예측을 AI에게 질문하기", icon="💬", width="stretch"
    )

st.divider()
st.markdown("#### 승인 대기 Action")
pending = db.get_actions(booth_id, "PENDING")
if not pending:
    st.success("현재 승인 대기 Action이 없습니다.")
for action in pending:
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"**{ACTION_LABELS.get(action['action_type'], action['action_type'])}**  ")
        st.caption(action["reason"])
    with c2:
        button_type = "primary" if action["action_type"] == "DISCOUNT" else "secondary"
        if st.button("승인", key=action["action_id"], type=button_type, width="stretch"):
            result = run_workflow(booth_id, approved_action_ids=[action["action_id"]])
            st.session_state["operator_notice"] = (
                f"{ACTION_LABELS.get(action['action_type'], action['action_type'])}을 승인·반영했습니다."
            )
            st.rerun()
if "operator_notice" in st.session_state:
    st.success(st.session_state.pop("operator_notice"))

active = [item for item in db.get_active_promotions() if item["booth_id"] == booth_id]
if active:
    promo = active[0]
    st.success(
        f"🔥 학생 화면 노출 중 · {promo['menu_name']} {promo['price']:,}원 → {promo['sale_price']:,}원 ({promo['discount_rate']}% 할인)"
    )
    st.page_link("pages/student.py", label="학생 화면에서 확인 →", icon="🎓")
    if st.button("타임세일 종료", width="stretch"):
        db.end_promotion(booth_id)
        run_workflow(booth_id)
        st.session_state["operator_notice"] = "타임세일을 종료하고 정가 운영으로 전환했습니다."
        st.rerun()

history = [item for item in db.get_actions(booth_id) if item["status"] == "EXECUTED"]
with st.expander("승인 이력"):
    if history:
        for item in history[:6]:
            st.write(f"✅ {ACTION_LABELS.get(item['action_type'], item['action_type'])} · {item['executed_at']}")
    else:
        st.caption("아직 승인된 Action이 없습니다.")

st.divider()
with st.expander("＋ 새 부스 등록 (P0)"):
    with st.form("register-booth", clear_on_submit=True):
        name_col, zone_col = st.columns([2, 1])
        booth_name = name_col.text_input("부스명", placeholder="예: 별빛 핫도그")
        zone = zone_col.selectbox("구역", ["A", "B", "C"])
        menu_name = st.text_input("대표 메뉴", placeholder="예: 수제 핫도그")
        price_col, stock_col = st.columns(2)
        price = price_col.number_input("판매가격", min_value=100, value=5000, step=100)
        initial_stock = stock_col.number_input("초기재고", min_value=0, value=100, step=10)
        submitted = st.form_submit_button("부스 등록", type="primary", width="stretch")
        if submitted:
            try:
                new_id = db.register_booth(booth_name, zone, menu_name, int(price), int(initial_stock))
                run_workflow(new_id)
                st.success("부스를 등록했습니다.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

mobile_bottom_nav(MOBILE_NAV, "")
