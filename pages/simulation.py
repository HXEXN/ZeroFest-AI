"""Judge-friendly end-to-end before/after simulation.

The active booth follows the booth selected on the Operator POS.
The latest-data button explicitly re-runs the prediction/agent pipeline against
the newest sales and inventory snapshots before rendering the screen.
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


configure_page(
    "Before / After",
    "🧪",
    mobile=True,
)

db.initialize_database()
ensure_predictions()
sidebar("AI Simulation")

mobile_header(
    "ZeroFest 시뮬레이터",
    "예측 → 승인 → 반응 → 재예측",
    "AI 연동",
    "시",
)

page_header(
    "END-TO-END · JUDGE DEMO",
    "예측에서 끝나지 않는 Closed Loop",
    "POS의 최신 판매·재고 상태를 받아 Action과 학생 반응 이후 다시 예측되는 전체 흐름을 확인합니다.",
)

flow_strip()


# -------------------------------------------------------------------
# POS에서 선택한 부스를 Simulation 대상으로 자동 동기화
# -------------------------------------------------------------------

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

active_booth_id = st.session_state.get(
    "active_booth_id",
    db.get_setting(
        "active_booth_id",
        "booth-chicken",
    ),
)

if active_booth_id not in booth_ids:
    active_booth_id = (
        "booth-chicken"
        if "booth-chicken" in booth_ids
        else booth_ids[0]
    )

BOOTH_ID = active_booth_id

st.session_state[
    "active_booth_id"
] = BOOTH_ID

db.set_setting(
    "active_booth_id",
    BOOTH_ID,
)


# -------------------------------------------------------------------
# 현재 연동 대상 + 명시적 최신화
# -------------------------------------------------------------------

with st.container(
    border=True
):
    st.caption(
        "현재 POS 연동 대상"
    )

    st.markdown(
        f"### {labels.get(BOOTH_ID, BOOTH_ID)}"
    )

    st.caption(
        "Operator POS에서 선택한 부스를 자동으로 따라갑니다."
    )

    if st.button(
        "↻ 최신 POS 데이터 반영",
        type="primary",
        width="stretch",
        key=f"refresh-simulation-{BOOTH_ID}",
    ):
        # 최신 sales/inventory snapshot을 다시 읽어
        # ML + Risk + Agent Action 후보를 새로 계산하고 저장
        result = run_workflow(
            BOOTH_ID
        )

        st.session_state[
            "simulation_refresh_notice"
        ] = (
            f"{labels.get(BOOTH_ID, BOOTH_ID)}의 최신 판매·재고를 기준으로 "
            f"예측을 다시 계산했습니다. "
            f"다음 30분 {result['prediction'].get('predicted_sales_30m', 0)}개 · "
            f"예상 잔여 {result['prediction'].get('expected_remaining', 0)}개"
        )

        st.rerun()

if "simulation_refresh_notice" in st.session_state:
    st.success(
        st.session_state.pop(
            "simulation_refresh_notice"
        )
    )


# -------------------------------------------------------------------
# 최신 DB 상태 재조회
# -------------------------------------------------------------------

state = db.get_booth_state(
    BOOTH_ID
)

prediction = (
    db.get_latest_prediction(
        BOOTH_ID
    )
    or {}
)

baseline = (
    db.get_intervention_baseline(
        BOOTH_ID
    )
)

promotions = [
    item
    for item in db.get_active_promotions()
    if item["booth_id"] == BOOTH_ID
]

simulated = state[
    "student_response_simulated"
]

current_remaining = int(
    prediction.get(
        "expected_remaining",
        0,
    )
)

current_risk = str(
    prediction.get(
        "risk_level",
        "-",
    )
)

before_remaining = (
    int(
        baseline[
            "expected_remaining"
        ]
    )
    if baseline
    else current_remaining
)

before_risk = (
    str(
        baseline[
            "risk_level"
        ]
    )
    if baseline
    else current_risk
)


# -------------------------------------------------------------------
# Closed-loop 진행 상태
# -------------------------------------------------------------------

status_cols = st.columns(
    5
)

steps = [
    (
        "1",
        "위험 감지",
        bool(
            prediction
        ),
    ),
    (
        "2",
        "AI Action",
        bool(
            prediction
        ),
    ),
    (
        "3",
        "운영자 승인",
        bool(
            promotions
        ),
    ),
    (
        "4",
        "학생 노출",
        bool(
            promotions
        ),
    ),
    (
        "5",
        "재예측",
        bool(
            simulated
        ),
    ),
]

for column, (
    number,
    label,
    done,
) in zip(
    status_cols,
    steps,
):
    column.markdown(
        f'<div class="zf-card" '
        f'style="text-align:center;'
        f'border-color:{"#10b981" if done else "#dce9e3"}">'
        f'<div style="font-size:1.4rem">'
        f'{"✓" if done else number}'
        f'</div><b>{label}</b></div>',
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# Before / After
# -------------------------------------------------------------------

left, right = st.columns(
    [1.2, 0.8],
    gap="large",
)

with left:
    st.plotly_chart(
        before_after(
            before_remaining,
            current_remaining,
        ),
        width="stretch",
        config={
            "displayModeBar": False
        },
    )

    if (
        baseline
        and current_remaining
        < before_remaining
    ):
        reduced = (
            before_remaining
            - current_remaining
        )

        st.caption(
            f"예측 잔여 {before_remaining}개 → "
            f"{current_remaining}개 "
            f"({reduced}개 · "
            f"{reduced / max(before_remaining, 1):.0%} 감소). "
            "합성 데이터로 학습한 모델의 예측 비교이며 "
            "실제 폐기 감소 실증 수치가 아닙니다."
        )

    else:
        st.caption(
            "할인을 승인하면 개입 전 예측과 비교할 수 있습니다. "
            "모든 값은 합성 데이터 기반 예측입니다."
        )

with right:
    st.markdown(
        f"#### {db.get_demo_time():%H:%M} · "
        f"{state['zone']}구역 "
        f"{state['menu_name']}"
    )

    st.markdown(
        f"- 누적 판매 **{state['total_sales']}개**\n"
        f"- 현재 재고 **{state['current_stock']}개**\n"
        f"- 최근 30분 판매 **{state['recent_sales_30m']}개** "
        f"(이전 {state['previous_sales_30m']}개)\n"
        f"- 다음 30분 예측 "
        f"**{prediction.get('predicted_sales_30m', '-')}개**"
    )

    if baseline:
        st.info(
            f"AI 적용 전 · "
            f"{baseline['timestamp'][-5:]} 기준 "
            f"예상 잔여 **{before_remaining}개** · "
            f"{before_risk}"
        )

    tone = {
        "HIGH": st.error,
        "MEDIUM": st.warning,
        "LOW": st.success,
    }.get(
        current_risk,
        st.info,
    )

    tone(
        f"현재 예측 · 예상 잔여 "
        f"**{current_remaining}개** · "
        f"{current_risk}"
    )


    # ---------------------------------------------------------------
    # 학생 반응
    # ---------------------------------------------------------------

    if (
        promotions
        and not simulated
    ):
        promo = promotions[0]

        st.success(
            f"{promo['discount_rate']}% 할인이 "
            f"학생 화면에 노출되었습니다. "
            f"({promo['price']:,}원 → "
            f"{promo['sale_price']:,}원)"
        )

        if st.button(
            "학생 반응 발생 → 재예측",
            type="primary",
            width="stretch",
        ):
            # simulate_student_response()가 어느 부스를 사용할지 명시
            db.set_setting(
                "student_response_booth",
                BOOTH_ID,
            )

            result = (
                db.simulate_student_response()
            )

            run_workflow(
                BOOTH_ID
            )

            st.session_state[
                "last_response"
            ] = result

            st.rerun()

    elif simulated:
        result = st.session_state.get(
            "last_response"
        )

        if result and result.get(
            "booth_id"
        ) == BOOTH_ID:
            st.caption(
                f"{result['from'][-5:]} → "
                f"{result['to'][-5:]} 사이 "
                f"할인 적용 상태로 "
                f"{result['sold']}개가 판매된 것으로 "
                "시뮬레이션했습니다."
            )

        st.caption(
            "판매·재고 스냅샷이 기록된 뒤 "
            "같은 파이프라인이 새 상태에서 다시 예측했습니다."
        )

    else:
        st.warning(
            "먼저 현재 POS 부스의 할인 Action을 운영자 화면에서 승인해 주세요."
        )

        st.page_link(
            "pages/operator.py",
            label="현재 부스 Action 승인하러 가기",
            icon="🧑‍🍳",
            width="stretch",
        )


st.divider()

st.markdown(
    "### 발표용 시연 흐름"
)

st.markdown(
    f"1. **Operator POS**에서 `{labels.get(BOOTH_ID, BOOTH_ID)}`의 판매를 입력합니다.\n"
    "2. **Simulation**으로 이동하면 같은 부스가 자동 선택되고 최신 판매·재고를 읽습니다.\n"
    "3. `↻ 최신 POS 데이터 반영`을 누르면 ML·Risk·Agent를 다시 실행합니다.\n"
    "4. **Operator**에서 할인 Action을 승인하면 학생 화면에 노출됩니다.\n"
    "5. `학생 반응 발생 → 재예측`으로 판매·재고 변화와 재예측을 확인합니다."
)

st.caption(
    "POS 입력값과 Simulation은 동일한 SQLite sales/inventory snapshot을 사용합니다. "
    "화면 갱신이 필요한 경우 '최신 POS 데이터 반영' 버튼으로 명시적으로 재예측합니다."
)

mobile_bottom_nav(
    MOBILE_NAV,
    "simulation",
)
