"""Student-facing benefits that route demand toward at-risk inventory."""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions
from components.map import festival_map
from components.ui import configure_page, page_header, sidebar
from services import database as db


configure_page("학생", "🎓")
db.initialize_database()
ensure_predictions()
sidebar("학생")
page_header(
    "STUDENT · BENEFIT FIRST",
    "지금 더 재미있고, 더 알뜰한 축제",
    "할인과 보상으로 학생에게 직접적인 혜택을 제공하고, 그 선택이 자연스럽게 잔여재고를 줄입니다.",
)

promotions = db.get_active_promotions()
reward = db.get_reward_progress()
st.markdown("### 지금 받을 수 있는 혜택")
if not promotions:
    st.markdown(
        """<div class="zf-card" style="text-align:center;padding:2.2rem">
        <div style="font-size:2.5rem">✨</div><h3>아직 마감 할인이 없어요</h3>
        <p class="zf-muted">AI 추천을 부스 운영자가 승인하면 여기에 즉시 표시됩니다.</p></div>""",
        unsafe_allow_html=True,
    )
    st.page_link("pages/operator.py", label="Demo: 운영자 할인 승인하러 가기", icon="🧑‍🍳")
else:
    columns = st.columns(min(3, len(promotions)))
    for idx, promo in enumerate(promotions):
        with columns[idx % len(columns)]:
            st.markdown(
                f"""<div class="zf-card" style="border:2px solid #f97316;box-shadow:0 10px 25px -5px rgba(249,115,22,.16)">
                  <div class="zf-kicker">🔥 마감 할인 · {promo['zone']} ZONE</div>
                  <h2 style="margin:.4rem 0">{promo['menu_name']}</h2>
                  <div><s style="color:#94a3b8">{promo['price']:,}원</s>
                  <b class="zf-numeric" style="font-size:1.7rem;color:#9a3412;margin-left:.5rem">{promo['sale_price']:,}원</b></div>
                  <p class="zf-muted">{promo['booth_name']} · 운영자 승인 완료 · 1시간 한정</p>
                </div>""",
                unsafe_allow_html=True,
            )

st.markdown("### 축제 지도")
events = db.get_event_context()
stage = next((item["event_name"] for item in events if item["zone"] == "Main Stage"), None)
festival_map(db.dashboard_rows(), promotions, stage_name=stage)
st.caption("구역과 혜택 표시는 실제 부스 상태에서 계산합니다. 정밀 위치나 개인정보는 수집하지 않습니다.")

tab_quiz, tab_stamp = st.tabs(["Quiz 보상 · P1", "Stamp Tour · P2"])
with tab_quiz:
    st.markdown("**Q. ZeroFest AI가 줄이려는 것은 무엇일까요?**")
    answer = st.radio("정답 선택", ["축제의 재미", "예상 잔여재고", "공연 시간"], horizontal=True, label_visibility="collapsed")
    if st.button("정답 확인"):
        if answer == "예상 잔여재고":
            reward = db.complete_quiz()
            st.success("정답! A구역 혜택 쿠폰이 발급·저장되었습니다. (Demo Coupon)")
        else:
            st.warning("한 번 더 생각해 보세요!")
    if int(reward.get("quiz_completed") or 0):
        st.code(f"{reward['coupon_code']} · Demo Coupon", language=None)
with tab_stamp:
    st.markdown("**C구역 방문 시 Stamp ×2**")
    stamps = int(reward.get("stamps") or 0)
    st.progress(stamps / 5, text=f"{stamps} / 5 stamps")
    if stamps < 5 and st.button("📍 C구역 QR 스캔 데모", width="stretch"):
        db.add_stamp()
        st.rerun()
    elif stamps >= 5:
        st.success(f"스탬프 완주! 쿠폰 `{reward['coupon_code']}`이 발급되었습니다.")
    st.caption("스탬프와 쿠폰 상태는 Demo DB에 저장되며 새로고침 후에도 유지됩니다.")

if promotions:
    st.page_link("pages/simulation.py", label="할인 이후 학생 반응 시뮬레이션 →", icon="🧪")
