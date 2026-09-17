"""Student council control-tower dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from agents.graph import analyze_all, ensure_predictions
from components.charts import remaining_by_booth
from components.ui import configure_page, flow_strip, page_header, sidebar
from config import ACTION_LABELS
from services.chat import ask_admin
from services.database import dashboard_rows, get_weather_context, initialize_database


configure_page("학생회 Control Tower", "📊")
initialize_database()
ensure_predictions()
sidebar("학생회")
page_header(
    "ADMIN · FESTIVAL CONTROL TOWER",
    "축제 전체를 한눈에, Action은 근거 있게",
    "개별 부스를 넘어 축제 전체의 공급과 수요를 관리합니다. 예측은 ML이, 위험판정은 규칙이, 실행 결정은 사람이 맡습니다.",
)
flow_strip()

rows = dashboard_rows()
total_sales = sum(int(row["total_sales"]) for row in rows)
total_stock = sum(int(row["current_stock"]) for row in rows)
expected_waste = sum(int(row.get("expected_remaining") or 0) for row in rows)
high_count = sum(row.get("risk_level") == "HIGH" for row in rows)

m1, m2, m3, m4 = st.columns(4)
m1.metric("누적 판매", f"{total_sales:,}개")
m2.metric("현재 재고", f"{total_stock:,}개")
m3.metric("예상 잔여", f"{expected_waste:,}개", help="행사 종료 시점 예측값")
m4.metric("HIGH 위험 부스", f"{high_count}곳")

weather = get_weather_context()
forecast = weather["forecast_1h"]
st.info(
    f"🌧️ **Mock Weather** · 1시간 뒤 강수확률 {int(forecast['precipitation_probability'])}% · "
    f"예상 강수 {forecast['rainfall']}mm  |  🎤 메인 공연 20:00 종료 예정"
)

tab_overview, tab_agent, tab_chat = st.tabs(["전체 현황", "AI Agent", "운영 AI Chat"])
with tab_overview:
    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "부스": f"{row['zone']} · {row['booth_name']}",
                "메뉴": row["menu_name"],
                "판매": int(row["total_sales"]),
                "재고": int(row["current_stock"]),
                "30분 예측": int(row.get("predicted_sales_30m") or 0),
                "예상 잔여": int(row.get("expected_remaining") or 0),
                "위험": row.get("risk_level", "-"),
                "AI Action": ACTION_LABELS.get(row.get("action_type"), row.get("action_type", "-")),
            }
        )
    st.dataframe(
        pd.DataFrame(table_rows), hide_index=True, width="stretch",
        column_config={
            "판매": st.column_config.NumberColumn(format="%d개"),
            "재고": st.column_config.NumberColumn(format="%d개"),
            "30분 예측": st.column_config.NumberColumn(format="%d개"),
            "예상 잔여": st.column_config.ProgressColumn(min_value=0, max_value=180, format="%d개"),
        },
    )
    st.plotly_chart(remaining_by_booth(rows), width="stretch", config={"displayModeBar": False})
    if st.button("모든 부스 지금 재예측", type="primary"):
        with st.spinner("판매·재고·날씨·공연 데이터를 분석하는 중..."):
            analyze_all()
        st.rerun()

with tab_agent:
    focus = max(rows, key=lambda row: int(row.get("expected_remaining") or 0))
    left, right = st.columns([0.9, 1.1])
    with left:
        st.markdown("#### 우선 대응 부스")
        st.markdown(
            f"""<div class="zf-card"><div class="zf-kicker">{focus['zone']} ZONE</div>
            <h3>{focus['booth_name']} · {focus['menu_name']}</h3>
            <div style="font-size:2.3rem;font-weight:850;color:#ef4444">{focus['expected_remaining']}개</div>
            <p class="zf-muted">행사 종료 예상 잔여 · 현재 재고 {focus['current_stock']}개</p>
            <span class="zf-risk-{focus['risk_level'].lower()}">{focus['risk_level']}</span></div>""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("#### 판단 근거")
        for driver in focus.get("drivers", []):
            st.markdown(f"- {driver}")
        st.markdown("#### 추천 Action")
        if focus.get("risk_level") == "HIGH":
            st.markdown("1. 추가 조리 중단\n2. B구역 재고 이동 검토\n3. 운영자 승인 후 20% 할인\n4. 학생 프로모션 노출")
        elif focus.get("risk_level") == "MEDIUM":
            st.markdown("1. 추가 조리 보류\n2. 15분 후 판매 추이 재확인")
        else:
            st.success("개입 후 폐기위험이 LOW로 안정화되었습니다. 현재 운영을 유지합니다.")
        st.caption("LLM은 설명만 담당하며 판매량 예측·위험판정·실행 승인에는 관여하지 않습니다.")
        st.page_link("pages/operator.py", label="운영자 승인 화면으로 →", icon="🧑‍🍳")

with tab_chat:
    st.markdown("#### 실제 예측 DB에 근거한 운영 Q&A")
    suggestions = ["지금 가장 폐기 위험이 높은 부스 알려줘", "왜 닭꼬치를 할인해야 돼?", "재고는 어디로 보내?"]
    selected = st.selectbox("질문 예시", ["직접 입력"] + suggestions, label_visibility="collapsed")
    question = st.text_input("질문", value="" if selected == "직접 입력" else selected, placeholder="예: 왜 닭꼬치를 할인해야 돼?")
    if st.button("데이터에 근거해 답변", type="primary", disabled=not question.strip()):
        answer, source = ask_admin(question.strip())
        st.session_state["last_admin_answer"] = (question, answer, source)
    if "last_admin_answer" in st.session_state:
        saved_question, answer, source = st.session_state["last_admin_answer"]
        with st.chat_message("user"):
            st.write(saved_question)
        with st.chat_message("assistant"):
            st.markdown(answer)
            st.caption(f"응답 엔진 · {source}")
