"""Mobile-first admin control tower wired to live ZeroFest state."""

from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from agents.graph import analyze_all, ensure_predictions
from components.charts import remaining_by_booth
from components.ui import configure_page, mobile_bottom_nav, mobile_header
from config import ACTION_LABELS
from services import database as db
from services.chat import ask_operations


configure_page("총괄 관제", "📊", mobile=True)
db.initialize_database()
ensure_predictions()
mobile_header("ZeroFest Admin", "2026 ASTRA 축제기획단 통합관제", "AI 연동", "총")

rows = db.dashboard_rows()
total_sales = sum(int(row["total_sales"]) for row in rows)
total_stock = sum(int(row["current_stock"]) for row in rows)
expected_waste = sum(int(row.get("expected_remaining") or 0) for row in rows)
high_count = sum(row.get("risk_level") == "HIGH" for row in rows)
weather = db.get_weather_context().get("forecast_1h", {})
events = db.get_event_context()
view = str(st.query_params.get("view", "dashboard"))


@st.dialog("AI 상세 근거 질의", width="large")
def ai_chat_dialog(booth_id: str) -> None:
    focus_row = next(row for row in rows if row["booth_id"] == booth_id)
    st.caption(f"{focus_row['zone']}구역 {focus_row['booth_name']} · 현재 운영 DB 근거")
    suggestions = ["왜 이 부스가 가장 위험해?", "20% 할인 근거를 알려줘", "재고는 언제 소진돼?", "어디로 이관해야 해?"]
    choice = st.selectbox("빠른 질문", suggestions)
    question = st.text_input("질문", value=choice)
    if st.button("AI에게 질문", type="primary", width="stretch"):
        answer, source, evidence = ask_operations(question, booth_id=booth_id)
        st.markdown(answer)
        with st.expander("사용한 실시간 근거", expanded=True):
            for item in evidence:
                st.markdown(f"- {item}")
        st.caption(source)


def risk_class(level: str) -> str:
    return {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(level, "low")


def render_weather() -> None:
    event_name = events[0]["event_name"] if events else "공연 일정 없음"
    st.markdown(
        f"""
        <div class="zf-weather">
          <div class="zf-mobile-row"><b>🌧 강수확률 {int(weather.get('precipitation_probability') or 0)}%</b>
          <span class="zf-pill high">19:50 비</span></div>
          <div class="zf-caption" style="color:#9f1239">{float(weather.get('temperature') or 0):g}°C · 예상 강수 {float(weather.get('rainfall') or 0):g}mm · {escape(event_name)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("기상 영향 상세 보기"):
        st.write("우천 예보를 수요 Feature로 반영하며, 날씨 자체를 AI가 예측하지 않습니다.")
        st.dataframe(pd.DataFrame([weather]), hide_index=True, width="stretch")


def render_kpis() -> None:
    st.markdown(
        f"""
        <div class="zf-kpi-grid">
          <div class="zf-kpi"><div class="zf-kpi-label">총 누적 판매량</div><div class="zf-kpi-value">{total_sales:,}<small>개</small></div><div class="zf-kpi-note zf-mint-text">+ 실시간 집계</div></div>
          <div class="zf-kpi"><div class="zf-kpi-label">현재 전체 재고</div><div class="zf-kpi-value">{total_stock:,}<small>개</small></div><div class="zf-kpi-note">● {len(rows)}개 부스 실시간</div></div>
          <div class="zf-kpi"><div class="zf-kpi-label">예측 잔여 폐기량</div><div class="zf-kpi-value" style="color:#9a3412">{expected_waste}<small>개</small></div><div class="zf-kpi-note">위험 관리 중</div></div>
          <div class="zf-kpi danger"><div class="zf-kpi-label zf-danger-text">폐기 위험 부스</div><div class="zf-kpi-value zf-danger-text">{high_count}<small>곳</small></div><div class="zf-kpi-note zf-danger-text">HIGH 집중 모니터</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_decision() -> None:
    focus = max(rows, key=lambda row: int(row.get("expected_remaining") or 0))
    pending = db.get_actions(focus["booth_id"], "PENDING")
    projected = max(0, round(int(focus["expected_remaining"]) * 0.26))
    before_width = min(100, int(focus["expected_remaining"]))
    after_width = min(100, projected)
    st.markdown(
        f"""
        <section class="zf-mobile-card">
          <div class="zf-mobile-row"><span class="zf-pill low">🧠 LangGraph AI Agent 분석 완료</span><span class="zf-caption">{db.get_demo_time():%H:%M} 기준</span></div>
          <span class="zf-pill high" style="margin-top:8px">폐기위험 {escape(str(focus['risk_level']))}</span>
          <div class="zf-mobile-h1" style="font-size:24px">현재 {escape(str(focus['zone']))}구역 {escape(str(focus['menu_name']))} 부스의 폐기 위험이 가장 높습니다</div>
          <div class="zf-caption">비 예보와 임계 초과 재고에 겹쳐 조기 판매 전략 실행이 요구됩니다.</div>
          <div style="background:#f1f3ff;border-radius:12px;padding:10px;margin-top:12px">
            <div class="zf-eyebrow">🔍 Explainable AI 판단 근거</div>
            {''.join(f'<div class="zf-signal"><b>{i:02d}</b><span>{escape(str(driver))}</span></div>' for i, driver in enumerate(focus.get('drivers', []), 1))}
          </div>
          <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:11px;padding:10px;margin-top:10px">
            <div class="zf-eyebrow" style="color:#9a3412">AI 예측 시뮬레이션</div>
            <div class="zf-caption">현 상태 방치 시 잔여 <b>{focus['expected_remaining']}개</b> 발생</div>
            <div class="zf-caption zf-danger-text"><b>예상 손실액 약 {int(focus['expected_remaining']) * int(focus['price']):,}원</b></div>
          </div>
          <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:11px;padding:10px;margin-top:10px">
            <div class="zf-eyebrow">⚙ AI 추천 솔루션 액션</div>
            {''.join(f'<div class="zf-action-row">{escape(ACTION_LABELS.get(item["action_type"], item["action_type"]))}</div>' for item in pending[:4])}
            <div class="zf-caption" style="margin-top:8px">세일 적용 잔여 시뮬레이션</div>
            <div class="zf-progress"><i style="width:{before_width}%;background:#dc2626"></i></div>
            <div class="zf-progress" style="margin-top:5px"><i style="width:{after_width}%;background:#10b981"></i></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if st.button("▷ 부스에 AI 권고 전송", type="primary", width="stretch"):
        db.set_setting(f"admin_broadcast:{focus['booth_id']}", datetime.now().isoformat())
        st.success("운영자 POS에 권고와 근거를 전송했습니다.")
    if st.button("💬 AI 상세 근거 질의", width="stretch"):
        ai_chat_dialog(focus["booth_id"])
    st.page_link("pages/operator.py", label="운영자 승인 화면 열기", icon="🏪", width="stretch")


def render_booths() -> None:
    st.markdown('<div class="zf-section-title"><strong>● 실시간 부스 관제 현황</strong><span class="zf-pill low">원격 제어 가능</span></div>', unsafe_allow_html=True)
    for row in rows:
        action = ACTION_LABELS.get(row.get("action_type"), row.get("action_type") or "현재 운영 유지")
        st.markdown(
            f"""
            <article class="zf-mobile-card">
              <div class="zf-booth-head"><div><span class="zf-pill medium">{escape(str(row['zone']))}구역</span>
              <b style="margin-left:6px">{escape(str(row['booth_name']))}</b></div>
              <span class="zf-pill {risk_class(str(row.get('risk_level')))}">● {escape(str(row.get('risk_level')))}</span></div>
              <div class="zf-kpi-grid" style="margin-bottom:5px">
                <div style="text-align:center"><span class="zf-caption">판매량</span><br><b>{int(row['total_sales'])}개</b></div>
                <div style="text-align:center"><span class="zf-caption">현재재고</span><br><b>{int(row['current_stock'])}개</b></div>
              </div>
              <div class="zf-action-row">🪄 AI: {escape(str(action))}</div>
            </article>
            """,
            unsafe_allow_html=True,
        )


if view == "dashboard":
    render_weather()
    render_kpis()
    render_ai_decision()
    render_booths()
elif view == "decision":
    render_ai_decision()
elif view == "booths":
    render_booths()
else:
    st.markdown('<div class="zf-section-title"><strong>ESG 운영 통계</strong><span class="zf-pill low">LIVE</span></div>', unsafe_allow_html=True)
    render_kpis()
    st.plotly_chart(remaining_by_booth(rows), width="stretch", config={"displayModeBar": False})
    if st.button("모든 부스 지금 재예측", type="primary", width="stretch"):
        analyze_all()
        st.rerun()

st.markdown(
    '<div class="zf-mobile-card" style="background:#eef2ff"><b>⚙ ZeroFest AI Engine Core</b>'
    '<div class="zf-caption">Agent Pipeline · Human Approval · Grounded Copilot</div></div>',
    unsafe_allow_html=True,
)

mobile_bottom_nav(
    [
        ("dashboard", "종합 관제", "▦", "/admin?view=dashboard"),
        ("decision", "의사결정 AI", "🧠", "/admin?view=decision"),
        ("booths", "전체 부스", "▰", "/admin?view=booths"),
        ("esg", "ESG 통계", "▥", "/admin?view=esg"),
    ],
    view if view in {"dashboard", "decision", "booths", "esg"} else "dashboard",
)
