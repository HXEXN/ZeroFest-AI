"""Live POS-linked end-to-end simulation.

Operator POS writes sales/inventory and immediately runs the ML/agent workflow.
This page does not require a manual refresh button. A Streamlit fragment polls
the shared SQLite state every 2 seconds so the currently selected POS booth,
sales, inventory, prediction, actions, and promotion state appear automatically.
"""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions, run_workflow
from components.charts import before_after
from components.ui import (
    MOBILE_NAV,
    configure_page,
    flow_strip,
    mobile_bottom_nav,
    mobile_header,
    page_header,
    sidebar,
)
from services import database as db


configure_page("Before / After", "🧪", mobile=True)

db.initialize_database()
ensure_predictions()
sidebar("AI Simulation")

mobile_header(
    "ZeroFest 시뮬레이터",
    "POS → 예측 → 승인 → 반응 → 재예측",
    "LIVE",
    "시",
)

page_header(
    "END-TO-END · LIVE DEMO",
    "POS 입력이 시뮬레이션에 자동 반영됩니다",
    "운영자 POS의 판매·재고와 선택 부스를 실시간으로 읽어 같은 ML·Agent 흐름을 보여줍니다.",
)

flow_strip()

st.markdown(
    """
    <style>
    .sim-live-bar {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:10px 12px;
        margin:8px 0 12px;
        border:1px solid #bbf7d0;
        border-radius:14px;
        background:#f0fdf4;
    }
    .sim-live-left {
        min-width:0;
    }
    .sim-live-title {
        color:#065f46;
        font-size:12px;
        font-weight:850;
    }
    .sim-live-booth {
        margin-top:3px;
        color:#131b2e;
        font-size:14px;
        font-weight:850;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
    }
    .sim-live-badge {
        flex:0 0 auto;
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:5px 8px;
        border-radius:999px;
        background:#d1fae5;
        color:#047857;
        font-size:10px;
        font-weight:900;
    }
    .sim-live-dot {
        width:7px;
        height:7px;
        border-radius:50%;
        background:#10b981;
        box-shadow:0 0 0 3px #a7f3d0;
    }

    @media (max-width: 440px) {
        /* 기존 5열/2단 고정 레이아웃이 좁은 화면에서 깨지지 않도록 완화 */
        .sim-live-bar {
            align-items:flex-start;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _valid_active_booth() -> tuple[str, dict[str, str]]:
    """Read the POS-selected booth from shared SQLite state."""
    booths = db.get_booths()
    booth_ids = [item["booth_id"] for item in booths]
    labels = {
        item["booth_id"]: (
            f"{item['zone']}구역 · "
            f"{item['booth_name']} "
            f"({item['menu_name']})"
        )
        for item in booths
    }

    active = db.get_setting("active_booth_id", "booth-chicken")
    if active not in booth_ids:
        active = "booth-chicken" if "booth-chicken" in booth_ids else booth_ids[0]
        db.set_setting("active_booth_id", active)

    return active, labels


@st.fragment(run_every="2s")
def live_simulation() -> None:
    """Refresh only the simulation surface every 2 seconds."""
    booth_id, labels = _valid_active_booth()

    # Keep this session aligned too, while SQLite remains the cross-page source.
    st.session_state["active_booth_id"] = booth_id

    state = db.get_booth_state(booth_id)
    prediction = db.get_latest_prediction(booth_id) or {}
    baseline = db.get_intervention_baseline(booth_id)
    promotions = [
        item
        for item in db.get_active_promotions()
        if item["booth_id"] == booth_id
    ]

    # student_response_simulated is historically a global demo flag.
    # Bind it to the booth that actually ran the response to prevent another
    # POS booth from incorrectly showing the "re-predicted" step as complete.
    simulated = (
        db.get_setting("student_response_simulated", "0") == "1"
        and db.get_setting("student_response_booth", "") == booth_id
    )

    sync_check = db.verify_pos_sim_sync(booth_id)
    sync_event = sync_check.get("event") or {}

    current_remaining = int(prediction.get("expected_remaining", 0))
    current_risk = str(prediction.get("risk_level", "-"))

    before_remaining = (
        int(baseline["expected_remaining"])
        if baseline
        else current_remaining
    )
    before_risk = (
        str(baseline["risk_level"])
        if baseline
        else current_risk
    )

    st.markdown(
        f"""
        <div class="sim-live-bar">
            <div class="sim-live-left">
                <div class="sim-live-title">POS 자동 연동</div>
                <div class="sim-live-booth">{labels.get(booth_id, booth_id)}</div>
            </div>
            <div class="sim-live-badge">
                <span class="sim-live-dot"></span>
                2초 LIVE
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "POS에서 부스를 바꾸거나 판매·재고를 입력하면 별도 버튼 없이 이 화면에 자동 반영됩니다."
    )

    if sync_check["sync_ok"]:
        st.success(
            f"✅ SYNC OK · POS 이벤트 {sync_event.get('event_id')} · "
            f"DB rev {sync_check['runtime_revision']}"
        )
    elif not sync_check["event_seen"]:
        st.info(
            "동기화 대기 · POS에서 판매 또는 재고 변경을 한 번 실행하면 자동 검증이 시작됩니다."
        )
    elif not sync_check["same_booth"]:
        st.warning(
            f"POS 마지막 이벤트는 {sync_event.get('booth_id')} 부스입니다. "
            f"현재 Simulation은 {booth_id} 부스를 보고 있습니다."
        )
    else:
        failed = []
        if not sync_check["wal_ok"]:
            failed.append("WAL")
        if not sync_check["revision_ok"]:
            failed.append("revision")
        if not sync_check["state_ok"]:
            failed.append("판매/재고")
        if not sync_check["prediction_ok"]:
            failed.append("예측")
        st.error(
            "❌ SYNC CHECK · " + ", ".join(failed or ["상태 불일치"])
        )

    with st.expander("SQLite 동기화 상세 진단", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Journal",
            str(sync_check.get("journal_mode", "-")).upper(),
        )
        c2.metric(
            "Revision",
            str(sync_check.get("runtime_revision", "-")),
        )
        c3.metric(
            "Server",
            str(sync_check.get("server_instance_id", "-")),
        )

        st.markdown(
            f"- WAL: **{'PASS' if sync_check['wal_ok'] else 'FAIL'}**  \n"
            f"- POS 이벤트 조회: **{'PASS' if sync_check['event_seen'] else 'WAIT'}**  \n"
            f"- 동일 부스: **{'PASS' if sync_check['same_booth'] else 'FAIL'}**  \n"
            f"- Revision 반영: **{'PASS' if sync_check['revision_ok'] else 'FAIL'}**  \n"
            f"- 판매·재고 반영: **{'PASS' if sync_check['state_ok'] else 'FAIL'}**  \n"
            f"- 최신 예측 조회: **{'PASS' if sync_check['prediction_ok'] else 'FAIL'}**"
        )

        if sync_event:
            st.caption(
                f"POS event={sync_event.get('event_id')} · "
                f"POS server={sync_event.get('server_instance_id')} · "
                f"Simulation server={sync_check.get('server_instance_id')}"
            )
            st.write(
                {
                    "POS event booth": sync_event.get("booth_id"),
                    "POS event total_sales": sync_event.get("total_sales"),
                    "POS event current_stock": sync_event.get("current_stock"),
                    "Simulation total_sales": state.get("total_sales"),
                    "Simulation current_stock": state.get("current_stock"),
                    "POS revision before marker": sync_event.get("revision_before_event"),
                    "Simulation revision": sync_check.get("runtime_revision"),
                }
            )

            if (
                sync_event.get("server_instance_id")
                and sync_event.get("server_instance_id")
                != sync_check.get("server_instance_id")
            ):
                st.warning(
                    "POS와 Simulation 요청이 서로 다른 Streamlit 서버 인스턴스에서 처리되고 있습니다. "
                    "이 경우 로컬 SQLite 파일은 인스턴스 간 공유되지 않을 수 있습니다."
                )

    # -------------------------------------------------------------
    # Closed-loop stages
    # -------------------------------------------------------------
    status_cols = st.columns(5)
    steps = [
        ("1", "위험 감지", bool(prediction)),
        ("2", "AI Action", bool(prediction)),
        ("3", "운영자 승인", bool(promotions)),
        ("4", "학생 노출", bool(promotions)),
        ("5", "재예측", bool(simulated)),
    ]

    for column, (number, label, done) in zip(status_cols, steps):
        column.markdown(
            f'<div class="zf-card" style="text-align:center;'
            f'border-color:{"#10b981" if done else "#dce9e3"}">'
            f'<div style="font-size:1.4rem">{"✓" if done else number}</div>'
            f'<b>{label}</b></div>',
            unsafe_allow_html=True,
        )

    # -------------------------------------------------------------
    # Live POS / forecast state
    # -------------------------------------------------------------
    st.markdown(f"#### {db.get_demo_time():%H:%M} · {state['zone']}구역 {state['menu_name']}")

    k1, k2 = st.columns(2)
    k1.metric("누적 판매", f"{int(state['total_sales']):,}개")
    k2.metric("현재 재고", f"{int(state['current_stock']):,}개")

    k3, k4 = st.columns(2)
    k3.metric("최근 30분 판매", f"{int(state['recent_sales_30m']):,}개")
    k4.metric(
        "다음 30분 예측",
        f"{int(prediction.get('predicted_sales_30m') or 0):,}개",
    )

    # -------------------------------------------------------------
    # Before / After
    # -------------------------------------------------------------
    st.plotly_chart(
        before_after(before_remaining, current_remaining),
        width="stretch",
        config={"displayModeBar": False},
        key=f"before-after-{booth_id}",
    )

    if baseline and current_remaining < before_remaining:
        reduced = before_remaining - current_remaining
        st.caption(
            f"예측 잔여 {before_remaining}개 → {current_remaining}개 "
            f"({reduced}개 · {reduced / max(before_remaining, 1):.0%} 감소). "
            "합성 데이터 기반 모델 예측 비교이며 실제 폐기 감소 실증 수치가 아닙니다."
        )
    else:
        st.caption(
            "운영자가 할인 Action을 승인하면 개입 전 예측과 현재 예측을 비교합니다."
        )

    if baseline:
        st.info(
            f"AI 적용 전 · {baseline['timestamp'][-5:]} 기준 "
            f"예상 잔여 **{before_remaining}개** · {before_risk}"
        )

    tone = {
        "HIGH": st.error,
        "MEDIUM": st.warning,
        "LOW": st.success,
    }.get(current_risk, st.info)

    tone(
        f"현재 예측 · 예상 잔여 **{current_remaining}개** · {current_risk}"
    )

    # -------------------------------------------------------------
    # Approved promotion → student response → re-prediction
    # -------------------------------------------------------------
    if promotions and not simulated:
        promo = promotions[0]

        st.success(
            f"{promo['discount_rate']}% 할인이 학생 화면에 노출 중입니다. "
            f"({promo['price']:,}원 → {promo['sale_price']:,}원)"
        )

        if st.button(
            "학생 반응 발생 → 재예측",
            type="primary",
            width="stretch",
            key=f"student-response-{booth_id}",
        ):
            # Explicitly bind the simulated response to the live POS booth.
            db.set_setting("student_response_booth", booth_id)

            result = db.simulate_student_response()
            run_workflow(booth_id)

            st.session_state["last_response"] = result
            st.rerun(scope="fragment")

    elif simulated:
        result = st.session_state.get("last_response")

        if result and result.get("booth_id") == booth_id:
            st.caption(
                f"{result['from'][-5:]} → {result['to'][-5:]} 사이 "
                f"{result['sold']}개 판매가 반영되었습니다."
            )

        st.success(
            "판매·재고 스냅샷 반영 후 동일 ML/Agent 파이프라인으로 재예측되었습니다."
        )

    else:
        st.warning(
            "현재 POS 부스에서 먼저 할인 Action을 승인하면 학생 반응 단계가 활성화됩니다."
        )

        st.page_link(
            "pages/operator.py",
            label="현재 부스 Action 승인하러 가기",
            icon="🧑‍🍳",
            width="stretch",
        )



live_simulation()

st.caption(
    "LIVE 모드는 2초마다 DB의 최신 상태만 다시 읽습니다. "
    "ML 재계산 자체는 POS 판매·재고 입력 시 즉시 실행되므로 불필요한 반복 학습/예측 호출을 만들지 않습니다."
)

mobile_bottom_nav(
    MOBILE_NAV,
    "simulation",
)
