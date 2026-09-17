"""Student-facing benefits that route demand toward at-risk inventory."""

from __future__ import annotations

from datetime import datetime
from html import escape
import streamlit as st

from agents.graph import ensure_predictions, run_workflow
from components.map import festival_map
from components.ui import MOBILE_NAV, configure_page, mobile_bottom_nav, mobile_header, sidebar
from services import database as db


configure_page("학생", "🎓", mobile=True)
db.initialize_database()
ensure_predictions()
sidebar("학생")

# 1. 시간 및 데이터 동기화
demo_now = db.get_demo_time()
demo_time_str = demo_now.strftime("%H:%M")
real_now = datetime.now()
real_time_str = real_now.strftime("%H:%M:%S")

# 축제 운영시간 (16:00 ~ 22:00) 잔여 시간 계산
close_time = demo_now.replace(hour=22, minute=0, second=0)
mins_to_close = max(0, int((close_time - demo_now).total_seconds() // 60))
close_str = f"{mins_to_close // 60}시간 {mins_to_close % 60}분" if mins_to_close >= 60 else f"{mins_to_close}분"

# 기상 정보 연동
weather_ctx = db.get_weather_context()
curr_weather = weather_ctx.get("current", {})
forecast_weather = weather_ctx.get("forecast_1h", {})
precip_prob = int(forecast_weather.get("precipitation_probability", 0))
curr_temp = float(curr_weather.get("temperature", 23.0))

# 공연 및 이벤트 정보 연동
events = db.get_event_context()
main_stage_event = next((e for e in events if e.get("zone") == "Main Stage"), None)
stage_name = main_stage_event["event_name"] if main_stage_event else "Main Stage"
stage_schedule = None
if main_stage_event:
    s_dt = datetime.fromisoformat(main_stage_event["start_time"])
    e_dt = datetime.fromisoformat(main_stage_event["end_time"])
    if s_dt <= demo_now <= e_dt:
        mins_remaining = max(0, int((e_dt - demo_now).total_seconds() // 60))
        stage_schedule = f"{s_dt.strftime('%H:%M')}~{e_dt.strftime('%H:%M')} · 🟢 LIVE 진행 중 ({mins_remaining}분 남음)"
    else:
        stage_schedule = f"{s_dt.strftime('%H:%M')}~{e_dt.strftime('%H:%M')} · 3,000명 밀집"

# 프로모션 및 리워드 상태
promotions = db.get_active_promotions()
reward = db.get_reward_progress()
stamps = int(reward.get("stamps") or 0)
quiz_done = bool(reward.get("quiz_completed"))
coupon_code = reward.get("coupon_code")
rows = db.dashboard_rows()

# 2. 상단 모바일 헤더 및 실시간 상태 바
mobile_header("ZeroFest 학생", "ASTRA 대동제 · 실시간 혜택 & 부스 지도", f"● LIVE {demo_time_str}", "학")

weather_icon = "🌧️" if precip_prob >= 60 else "⛅"
weather_text = f"20:00 비 예보 ({precip_prob}% 우산 챙기세요!)" if precip_prob >= 60 else f"{curr_temp:g}°C 쾌청"
st.markdown(
    f"""
    <div class="zf-time-bar">
      <div>
        <span style="font-weight:900;color:#166534">🎪 축제 현장 {demo_time_str}</span>
        <span style="color:#64748b;margin-left:4px">마감까지 {close_str}</span>
      </div>
      <div>
        <span style="color:#9a3412;font-weight:800">{weather_icon} {weather_text}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 3. 웰컴 히어로 카드
st.markdown(
    """
    <section class="zf-mobile-card mint" style="padding:16px 18px;margin:6px 0 14px">
      <div class="zf-mobile-row">
        <span class="zf-eyebrow">◉ STUDENT PORTAL · ZERO-WASTE</span>
        <span class="zf-status"><span class="zf-dot"></span>실시간 연동</span>
      </div>
      <div class="zf-mobile-h1" style="font-size:21px;margin:6px 0 4px">
        맛있게 즐기고,<br><span style="color:#047857">착하게 할인받자!</span>
      </div>
      <div class="zf-caption">
        AI 마감 타임세일과 혜택 쿠폰으로 잔여 재고를 줄이는 스마트 축제
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

# 4. 🔥 실시간 마감 타임세일 (Flash Sale)
st.markdown(
    '<div class="zf-section-title"><strong>🔥 실시간 마감 타임세일</strong><span class="zf-pill high">AI HOT DEAL</span></div>',
    unsafe_allow_html=True,
)

if not promotions:
    st.markdown(
        """
        <div class="zf-mobile-card" style="text-align:center;padding:18px 14px;border:1.5px dashed #cbd5e1">
          <div style="font-size:2rem;margin-bottom:6px">⏳</div>
          <div style="font-weight:850;font-size:15px;color:#1e293b">현재 대기 중인 마감 타임세일이 없습니다</div>
          <div class="zf-caption" style="margin-top:4px">
            AI가 실시간 판매 속도와 20시 비 예보를 분석하여 잔여 재고 발생 시 1초 만에 마감 할인을 오픈합니다.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("⚡ [Demo] 닭꼬치 20% 마감할인 열어보기", type="primary", width="stretch"):
        db.activate_promotion("booth-chicken", 20)
        run_workflow("booth-chicken")
        st.toast("🔥 닭꼬치 20% 마감할인이 시작되었습니다!", icon="🍗")
        st.rerun()
else:
    for promo in promotions:
        end_dt = datetime.fromisoformat(promo["end_time"])
        mins_left = max(0, int((end_dt - demo_now).total_seconds() // 60))
        discount_won = promo["price"] - promo["sale_price"]

        emoji = "🍗" if "닭" in promo["menu_name"] or "치킨" in promo["menu_name"] else "🍢"
        if "와플" in promo["menu_name"]:
            emoji = "🧇"
        elif "에이드" in promo["menu_name"] or "음료" in promo["menu_name"]:
            emoji = "🥤"
        elif "떡볶이" in promo["menu_name"]:
            emoji = "🥘"

        st.markdown(
            f"""
            <div class="zf-sale-card">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="zf-sale-badge">🔥 {promo['discount_rate']}% 마감할인</span>
                <span class="zf-sale-timer">⏰ {mins_left}분 남음 (종료 {end_dt.strftime('%H:%M')})</span>
              </div>
              <div style="display:flex;align-items:baseline;justify-content:space-between;margin:8px 0 4px">
                <div style="font-size:19px;font-weight:900;color:#131b2e">{emoji} {escape(promo['menu_name'])}</div>
                <div class="zf-pill medium">{escape(promo['zone'])} ZONE</div>
              </div>
              <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px">
                <s style="color:#94a3b8;font-size:13px">{promo['price']:,}원</s>
                <b class="zf-numeric" style="font-size:22px;color:#c2410c;font-weight:900">{promo['sale_price']:,}원</b>
                <span style="font-size:11px;color:#059669;font-weight:800">({discount_won:,}원 즉시 절약)</span>
              </div>
              <div class="zf-caption" style="display:flex;justify-content:space-between;border-top:1px dashed #fed7aa;padding-top:8px">
                <span>📍 {escape(promo['booth_name'])}</span>
                <span style="color:#c2410c;font-weight:800">운영자 승인 완료 · 한정 수량</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# 4. 🗺️ 실시간 축제 지도 (Zone Map)
st.markdown(
    '<div class="zf-section-title"><strong>🗺️ 실시간 축제 지도</strong><span class="zf-pill low">스마트 존</span></div>',
    unsafe_allow_html=True,
)
festival_map(rows, promotions, stage_name=stage_name, stage_schedule=stage_schedule, admin=False)
st.caption("구역과 혜택 표시는 실시간 부스 상태에서 자동 계산됩니다. (개인위치 미수집)")

# 5. 🍔 축제 먹거리 부스 둘러보기 (Food Directory)
st.markdown(
    '<div class="zf-section-title"><strong>🍔 축제 먹거리 부스</strong><span class="zf-pill low">실시간 메뉴</span></div>',
    unsafe_allow_html=True,
)

cat_filter = st.radio(
    "카테고리 선택",
    ["전체", "🍱 식사", "🧇 디저트", "🥤 음료"],
    horizontal=True,
    label_visibility="collapsed",
    key="student_food_category_filter",
)

category_map = {"🍱 식사": "food", "🧇 디저트": "dessert", "🥤 음료": "drink"}
filtered_rows = rows
if cat_filter in category_map:
    filtered_rows = [r for r in rows if r.get("category") == category_map[cat_filter]]

for r in filtered_rows:
    b_emoji = "🍱"
    if r.get("category") == "dessert":
        b_emoji = "🧇"
    elif r.get("category") == "drink":
        b_emoji = "🥤"
    elif "닭" in r.get("menu_name", ""):
        b_emoji = "🍗"
    elif "떡" in r.get("menu_name", ""):
        b_emoji = "🥘"

    b_promo = next((p for p in promotions if p["booth_id"] == r["booth_id"]), None)
    if b_promo:
        price_html = f'<s>{r["price"]:,}원</s> <b style="color:#c2410c;font-size:15px;font-weight:900">{b_promo["sale_price"]:,}원</b>'
        stock_pill = f'<span class="zf-pill high">🔥 {b_promo["discount_rate"]}% 세일</span>'
    else:
        price_html = f'<b style="color:#131b2e;font-size:15px;font-weight:850">{r["price"]:,}원</b>'
        stock = int(r.get("current_stock", 0))
        stock_pill = f'<span class="zf-pill low">주문 가능 ({stock}개)</span>' if stock > 30 else f'<span class="zf-pill medium">잔여 소량 ({stock}개)</span>'

    total_sales = int(r.get("total_sales", 0))
    st.markdown(
        f"""
        <div class="zf-booth-row">
          <div style="display:flex;align-items:center;gap:10px;min-width:0">
            <div style="font-size:24px;line-height:1">{b_emoji}</div>
            <div style="min-width:0">
              <div style="font-weight:850;font-size:14px;color:#131b2e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(r['menu_name'])}</div>
              <div style="font-size:11px;color:#64748b">{escape(r['booth_name'])} · {escape(r['zone'])}구역</div>
              <div style="font-size:10px;color:#047857;margin-top:2px;font-weight:750">오늘 {total_sales}개 판매</div>
            </div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div>{price_html}</div>
            <div style="margin-top:4px">{stock_pill}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 6. 🎁 학생 참여 리워드: 퀴즈 & 스탬프 투어 (탭 리셋 버그 없는 세그먼트)
st.markdown(
    '<div class="zf-section-title"><strong>🎁 학생 혜택 존</strong><span class="zf-pill low">리워드</span></div>',
    unsafe_allow_html=True,
)

reward_mode = st.radio(
    "혜택 종류",
    ["📝 1,000원 퀴즈 쿠폰", "💮 스탬프 투어"],
    horizontal=True,
    label_visibility="collapsed",
    key="student_reward_mode_select",
)

if reward_mode == "📝 1,000원 퀴즈 쿠폰":
    if quiz_done:
        st.markdown(
            f"""
            <div class="zf-coupon-ticket">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="zf-sale-badge">✅ 쿠폰 발급 완료</span>
                <span style="font-size:11px;color:#166534;font-weight:850">1,000원 즉시 할인</span>
              </div>
              <div style="font-size:20px;font-weight:900;color:#131b2e;letter-spacing:-0.03em;margin:8px 0 2px">
                {escape(coupon_code or 'ZERO-A-1000')}
              </div>
              <div class="zf-caption" style="color:#047857">A구역 청춘 닭꼬치 전용 · 결제 시 제시</div>
              <div class="zf-coupon-barcode"></div>
              <div style="font-size:10px;color:#64748b;text-align:center">📱 결제 시 이 바코드를 부스 운영자에게 보여주세요</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="zf-mobile-card" style="padding:14px">
              <div style="font-weight:850;font-size:14px;color:#131b2e;margin-bottom:6px">Q. ZeroFest AI가 줄이려는 것은 무엇일까요?</div>
              <div class="zf-caption" style="margin-bottom:8px">정답을 맞히시면 A구역 1,000원 즉시 할인 쿠폰을 드립니다!</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        answer = st.radio(
            "퀴즈 보기",
            ["축제의 재미", "예상 잔여재고", "공연 시간"],
            horizontal=True,
            label_visibility="collapsed",
            key="student_quiz_radio_answer",
        )
        if st.button("정답 확인 및 쿠폰 받기", type="primary", width="stretch"):
            if answer == "예상 잔여재고":
                db.complete_quiz()
                st.toast("🎉 정답입니다! 1,000원 할인 쿠폰 발급 완료", icon="🎟️")
                st.balloons()
                st.rerun()
            else:
                st.warning("한 번 더 생각해 보세요! (힌트: 남는 음식/재고를 줄여요)")

else:  # 💮 스탬프 투어
    st.markdown(
        f"""
        <div class="zf-mobile-card" style="padding:14px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="font-weight:850;font-size:14px;color:#131b2e">축제 구역 방문 스탬프</div>
            <span class="zf-pill {'low' if stamps >= 5 else 'medium'}">{stamps} / 5 달성</span>
          </div>
          <div class="zf-caption" style="margin-top:4px">
            {'🎉 5개 스탬프 완주! 무료 음료 쿠폰이 언락되었습니다.' if stamps >= 5 else f'앞으로 {5 - stamps}개 더 모으면 무료 음료 쿠폰 증정!'}
          </div>
          <div class="zf-stamp-grid">
            <div class="zf-stamp-item {'active' if stamps >= 1 else ''}">
              <span>{'💮' if stamps >= 1 else '⭕'}</span><div class="zf-stamp-num">1번</div>
            </div>
            <div class="zf-stamp-item {'active' if stamps >= 2 else ''}">
              <span>{'💮' if stamps >= 2 else '⭕'}</span><div class="zf-stamp-num">2번</div>
            </div>
            <div class="zf-stamp-item {'active' if stamps >= 3 else ''}">
              <span>{'💮' if stamps >= 3 else '⭕'}</span><div class="zf-stamp-num">3번</div>
            </div>
            <div class="zf-stamp-item {'active' if stamps >= 4 else ''}">
              <span>{'💮' if stamps >= 4 else '⭕'}</span><div class="zf-stamp-num">4번</div>
            </div>
            <div class="zf-stamp-item {'active' if stamps >= 5 else ''}">
              <span>{'💮' if stamps >= 5 else '⭕'}</span><div class="zf-stamp-num">5번</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if stamps < 5:
        if st.button("📍 [데모] C구역 QR 스캔하기 (+1 스탬프)", width="stretch", key="student_stamp_add_btn"):
            db.add_stamp()
            st.toast(f"📍 C구역 QR 스캔 완료! (스탬프 {stamps + 1}/5)", icon="💮")
            st.rerun()
    else:
        st.markdown(
            f"""
            <div class="zf-coupon-ticket">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="zf-sale-badge">🏆 스탬프 완주 쿠폰</span>
                <span style="font-size:11px;color:#166534;font-weight:850">전 부스 무료 음료권</span>
              </div>
              <div style="font-size:20px;font-weight:900;color:#131b2e;letter-spacing:-0.03em;margin:8px 0 2px">
                {escape(coupon_code or 'ZERO-STAMP-FREE')}
              </div>
              <div class="zf-caption" style="color:#047857">축제 내 모든 음료 부스에서 교환 가능</div>
              <div class="zf-coupon-barcode"></div>
              <div style="font-size:10px;color:#64748b;text-align:center">축제 현장 부스 결제 시 제시하세요</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# 7. ⚡ 심사위원 / 시연자 데모 헬퍼
with st.expander("🧪 Demo 빠른 제어 (심사 / 시연용)", expanded=False):
    st.caption("시연을 위한 원클릭 데이터 조작 도구입니다. 실제 축제 운영 상태와 즉시 동기화됩니다.")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if promotions:
            if st.button("할인 강제 종료", width="stretch", key="demo_end_promo_btn"):
                for p in promotions:
                    db.end_promotion(p["booth_id"])
                st.toast("마감 할인이 종료되었습니다.", icon="⏹️")
                st.rerun()
        else:
            if st.button("닭꼬치 20% 마감할인 승인", width="stretch", key="demo_start_promo_btn"):
                db.activate_promotion("booth-chicken", 20)
                run_workflow("booth-chicken")
                st.toast("🔥 닭꼬치 20% 마감할인이 승인되었습니다!", icon="🍗")
                st.rerun()
    with col_d2:
        if st.button("학생 반응 시뮬레이션 →", width="stretch", key="demo_sim_btn"):
            if promotions:
                res = db.simulate_student_response()
                run_workflow("booth-chicken")
                st.toast(f"⚡ 학생 구매 {res['sold']}개 반영 · 19:30으로 재예측 완료!", icon="📈")
                st.rerun()
            else:
                st.warning("먼저 마감 할인을 승인해주세요.")

    if st.button("↻ Demo 전체 초기화", width="stretch", key="demo_reset_all_btn"):
        db.reset_demo()
        st.session_state.clear()
        st.toast("↻ 데모 상태가 초기화되었습니다.", icon="✨")
        st.rerun()

# 8. 모바일 하단 네비게이션
mobile_bottom_nav(MOBILE_NAV, "student")

