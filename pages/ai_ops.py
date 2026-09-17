"""Dedicated data, ML, model registry and AI Agent operations console."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.graph import analyze_all, ensure_predictions
from components.ui import configure_page, flow_strip, page_header, sidebar
from config import OPENAI_MODEL
from models.demand_model import FEATURES, HISTORICAL_REQUIRED_COLUMNS, load_historical_data
from services import database as db
from services.mlops import (
    data_quality_report,
    ensure_active_model,
    model_runs,
    prediction_audit,
    run_training_pipeline,
)


configure_page("AI · ML · Data Operations", "🧠")
db.initialize_database()
ensure_predictions()
sidebar("AI · ML · Data Ops")
page_header(
    "AI ENGINE CORE · GOVERNED OPERATIONS",
    "데이터부터 Agent까지, 한곳에서 추적하고 관리합니다",
    "과거 축제 데이터의 품질, 시간 순서 검증, 모델 버전, LangGraph 실행과 Human Approval 상태를 분리해 관찰합니다.",
)

quality = data_quality_report()
active = ensure_active_model()

st.markdown(
    '<span class="zf-provenance">⚠ SAMPLE / SYNTHETIC HISTORY · 실제 전년도 판매 실적 아님</span>',
    unsafe_allow_html=True,
)
st.caption(
    "현재 Adapter는 2023–2025년 3개 가상 대학의 합성 과거 기록을 사용합니다. "
    "실데이터 CSV는 HISTORICAL_DATA_PATH로 동일 Schema에 연결할 수 있습니다."
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("과거 학습 레코드", f"{quality['rows']:,}")
m2.metric("대학 / 연도", f"{quality['universities']} / {len(quality['years'])}")
m3.metric("Data Quality", f"{quality['quality_score']}%")
m4.metric("2025 Hold-out MAE", f"{float(active['mae']):.2f}개")
m5.metric("Model Status", "ACTIVE" if active.get("is_active", 1) else "READY")

tab_pipeline, tab_data, tab_model, tab_agent = st.tabs(
    ["Pipeline Control", "Data Registry", "Model Registry", "Agent & Audit"]
)

with tab_pipeline:
    left, right = st.columns([1.45, 0.55], gap="large")
    with left:
        st.markdown("#### Historical-to-Live 학습 파이프라인")
        stages = active.get("stages", [])
        if stages:
            stage_columns = st.columns(3)
            for idx, stage in enumerate(stages):
                with stage_columns[idx % 3]:
                    st.markdown(
                        f'<div class="zf-stage"><div class="zf-stage-pass">● {stage["status"]}</div>'
                        f'<b>{stage["stage"]}</b><div class="zf-muted">{stage["detail"]}</div></div>',
                        unsafe_allow_html=True,
                    )
        flow_strip()
    with right:
        st.markdown("#### 실행 제어")
        st.caption("새 학습은 2023–2024로 학습하고 2025를 시간 순서 Hold-out으로 검증합니다.")
        if st.button("전체 Pipeline 다시 실행", type="primary", width="stretch"):
            with st.spinner("수집 → 검증 → 학습 → 평가 → 등록 중..."):
                result = run_training_pipeline()
            st.session_state["pipeline_notice"] = result["run_id"]
            st.rerun()
        if "pipeline_notice" in st.session_state:
            st.success(f"등록 완료 · {st.session_state.pop('pipeline_notice')}")
        st.info("배포 기준\n\n- Schema PASS\n- Null 0\n- MAE 기록\n- 사람 검토 후 ACTIVE")

with tab_data:
    st.markdown("#### Data Contract & Quality Gate")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Null cells", quality["null_cells"])
    q2.metric("중복 행", quality["duplicate_rows"])
    q3.metric("잘못된 Target", quality["invalid_targets"])
    q4.metric("Model Features", len(FEATURES))
    history = load_historical_data()
    chart_left, chart_right = st.columns(2)
    year_frame = pd.DataFrame(
        [{"연도": str(year), "레코드": count} for year, count in quality["year_counts"].items()]
    )
    category_frame = pd.DataFrame(
        [{"메뉴 유형": name, "레코드": count} for name, count in quality["category_counts"].items()]
    )
    year_chart = px.bar(year_frame, x="연도", y="레코드", color_discrete_sequence=["#166534"], text="레코드")
    year_chart.update_layout(height=285, margin=dict(l=10, r=10, t=25, b=10), paper_bgcolor="rgba(0,0,0,0)")
    category_chart = px.pie(
        category_frame, names="메뉴 유형", values="레코드",
        color_discrete_sequence=["#166534", "#10b981", "#f97316"], hole=.55,
    )
    category_chart.update_layout(height=285, margin=dict(l=10, r=10, t=25, b=10), paper_bgcolor="rgba(0,0,0,0)")
    chart_left.plotly_chart(year_chart, width="stretch", config={"displayModeBar": False})
    chart_right.plotly_chart(category_chart, width="stretch", config={"displayModeBar": False})
    with st.expander("과거 학습 데이터 Sample 및 Schema", expanded=False):
        visible = [
            "festival_year", "university_id", "menu_category", "recent_sales_30m",
            "precipitation_probability", "event_ending_soon", "discount_rate", "future_sales_30m",
        ]
        st.dataframe(history[visible].head(24), hide_index=True, width="stretch")
        st.code(" · ".join(FEATURES), language=None)
    st.markdown("#### 실제 전년도 CSV 연결 전 검증")
    uploaded = st.file_uploader(
        "동일 Schema의 후보 CSV를 업로드하면 저장하거나 배포하기 전에 품질만 검사합니다.",
        type=["csv"],
    )
    if uploaded is not None:
        try:
            candidate = pd.read_csv(uploaded)
            missing = sorted(HISTORICAL_REQUIRED_COLUMNS - set(candidate.columns))
            if missing:
                st.error(f"Schema FAIL · 누락 Column: {', '.join(missing)}")
            else:
                st.success(
                    f"Schema PASS · {len(candidate):,}행 · Null {int(candidate.isna().sum().sum()):,}개 · "
                    "아직 Active Model에는 반영되지 않았습니다."
                )
                st.dataframe(candidate.head(10), hide_index=True, width="stretch")
        except Exception as exc:
            st.error(f"CSV를 읽을 수 없습니다: {type(exc).__name__}")

with tab_model:
    st.markdown("#### Active Model · Explainability")
    model_left, model_right = st.columns([1.2, .8], gap="large")
    importances = pd.DataFrame(active["importances"])
    importance_chart = px.bar(
        importances.sort_values("importance"), x="importance", y="label", orientation="h",
        color="importance", color_continuous_scale=["#d1fae5", "#166534"],
        labels={"importance": "Feature importance", "label": ""},
    )
    importance_chart.update_layout(
        height=390, margin=dict(l=10, r=10, t=20, b=10), coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    model_left.plotly_chart(importance_chart, width="stretch", config={"displayModeBar": False})
    with model_right:
        st.markdown(
            f"""<div class="zf-card"><div class="zf-kicker">ACTIVE MODEL</div>
            <h3>Gradient Boosting</h3>
            <div class="zf-numeric" style="font-size:1.8rem;color:#166534">R² {float(active['r2']):.3f}</div>
            <p class="zf-muted">Train {active['training_years']} · Validate {active['validation_year']}<br>
            MAE {float(active['mae']):.2f}개 / 30분 · {active['train_rows']} train rows</p>
            <span class="zf-risk-low">DEPLOYED</span></div>""",
            unsafe_allow_html=True,
        )
        st.warning("R²와 MAE는 합성 데이터 검증값입니다. 실제 성능 주장에 사용할 수 없습니다.")
    runs = model_runs()
    if runs:
        registry = pd.DataFrame(runs)[
            ["run_id", "timestamp", "model_name", "training_years", "validation_year", "mae", "r2", "status"]
        ]
        st.dataframe(registry, hide_index=True, width="stretch")

with tab_agent:
    st.markdown("#### LangGraph Agent · 상태와 감사 로그")
    flow_strip()
    a1, a2, a3 = st.columns(3)
    a1.metric("Workflow", "LangGraph")
    a2.metric("LLM 설명 모드", OPENAI_MODEL if os.getenv("OPENAI_API_KEY") else "Grounded Local")
    a3.metric("자동 실행", "OFF · 승인 필수")
    status_left, status_right = st.columns([.7, 1.3], gap="large")
    actions = db.query_all(
        "SELECT action_type, status, COUNT(*) AS count FROM agent_actions GROUP BY action_type, status ORDER BY status"
    )
    with status_left:
        st.markdown("**Guardrails**")
        st.success("✓ ML이 수요 수치 예측")
        st.success("✓ 규칙 엔진이 위험도 판정")
        st.success("✓ 운영자 승인 전 Action 대기")
        st.success("✓ LLM은 설명만 담당")
        if st.button("전체 부스 Agent 재실행", width="stretch"):
            analyze_all()
            st.rerun()
    with status_right:
        st.markdown("**Action Queue**")
        st.dataframe(pd.DataFrame(actions), hide_index=True, width="stretch")
    st.markdown("**Latest Prediction Audit**")
    st.dataframe(prediction_audit(), hide_index=True, width="stretch")
    st.caption("모든 할인·조리중단·재고이동 실행은 AgentAction의 PENDING → APPROVED → EXECUTED 이력으로 남습니다.")
