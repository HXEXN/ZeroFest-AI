"""Judge-friendly end-to-end before/after simulation.

Every number on this page is read back from the model and the database. There is
no scripted before/after pair: if the model changes, this page changes with it.
"""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions, run_workflow
from components.charts import before_after
from components.ui import configure_page, flow_strip, page_header, sidebar
from services import database as db


BOOTH_ID = "booth-chicken"

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

state = db.get_booth_state(BOOTH_ID)
prediction = db.get_latest_prediction(BOOTH_ID) or {}
baseline = db.get_intervention_baseline(BOOTH_ID)
promotions = [item for item in db.get_active_promotions() if item["booth_id"] == BOOTH_ID]
simulated = state["student_response_simulated"]
response_trace = db.get_student_response_trace()

current_remaining = int(prediction.get("expected_remaining", 0))
current_risk = str(prediction.get("risk_level", "-"))
counterfactual = response_trace.get("counterfactual", {}) if response_trace else {}
before_remaining = int(
    counterfactual.get(
        "expected_remaining",
        baseline["expected_remaining"] if baseline else current_remaining,
    )
)
before_risk = str(
    counterfactual.get("risk_level", baseline["risk_level"] if baseline else current_risk)
)
before_stock = int(baseline["current_stock"]) if baseline else int(state["current_stock"])
before_sales = int(baseline.get("recent_sales_30m", state["recent_sales_30m"])) if baseline else int(state["recent_sales_30m"])

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
        f'<div class="zf-card" style="text-align:center;border-color:{"#10b981" if done else "#dce9e3"}">'
        f'<div style="font-size:1.4rem">{"✓" if done else number}</div><b>{label}</b></div>',
        unsafe_allow_html=True,
    )

metric_sales, metric_stock, metric_remaining = st.columns(3)
after_sales = (
    max(0, int(state["total_sales"]) - int(baseline.get("total_sales", state["total_sales"])))
    if baseline else int(state["recent_sales_30m"])
)
stock_delta = int(state["current_stock"]) - before_stock if baseline else None
remaining_delta = current_remaining - before_remaining if baseline else None
metric_sales.metric(
    "AI 추천 후 누적 판매",
    f"{after_sales}개",
    "18:30 → 20:00" if baseline and simulated else "승인 이후 집계",
)
metric_stock.metric(
    f"{db.get_demo_time():%H:%M} 실제 재고",
    f"{state['current_stock']}개",
    f"{stock_delta:+d}개 vs 18:30" if stock_delta is not None else None,
    delta_color="inverse",
)
metric_remaining.metric(
    "AI 적용 · 종료 예상 잔여",
    f"{current_remaining}개",
    f"{remaining_delta:+d}개 vs 미적용" if remaining_delta is not None else None,
    delta_color="inverse",
)
if baseline:
    if counterfactual:
        st.caption(
            f"20:00 동일 시점 비교 · AI 추천 미적용 경로 재고 "
            f"{counterfactual['current_stock']}개 / 22:00 예상 잔여 "
            f"{before_remaining}개 ({before_risk})"
        )
    else:
        st.caption(
            f"AI 추천 미적용 기준 · 18:30 최근 30분 판매 {before_sales}개 / "
            f"재고 {before_stock}개 / 22:00 예상 잔여 {before_remaining}개 ({before_risk})"
        )

left, right = st.columns([1.2, 0.8], gap="large")
with left:
    st.plotly_chart(
        before_after(before_remaining, current_remaining),
        width="stretch",
        config={"displayModeBar": False},
    )
    if baseline and current_remaining < before_remaining:
        reduced = before_remaining - current_remaining
        st.caption(
            f"AI 추천 미적용 시 {before_remaining}개 → 추천 적용 후 {current_remaining}개 "
            f"({reduced}개 · {reduced / max(before_remaining, 1):.0%} 감소). "
            "같은 18:30 시작·20:00 평가 조건의 모델 시나리오 비교이며 실제 폐기 감소 실증 수치가 아닙니다."
        )
    else:
        st.caption("할인을 승인하면 개입 전 예측과 비교할 수 있습니다. 모든 값은 합성 데이터 기반 예측입니다.")

with right:
    st.markdown(f"#### {db.get_demo_time():%H:%M} · {state['zone']}구역 {state['menu_name']}")
    st.markdown(
        f"- 현재 재고 **{state['current_stock']}개**\n"
        f"- 최근 30분 판매 **{state['recent_sales_30m']}개** (이전 {state['previous_sales_30m']}개)\n"
        f"- 다음 30분 예측 **{prediction.get('predicted_sales_30m', '-')}개**"
    )
    if baseline:
        comparison_time = "20:00 동일 시점" if counterfactual else f"{baseline['timestamp'][-5:]} 기준"
        st.info(
            f"AI 추천 미적용 · {comparison_time} · "
            f"예상 잔여 **{before_remaining}개** · {before_risk}"
        )
    tone = {"HIGH": st.error, "MEDIUM": st.warning, "LOW": st.success}.get(current_risk, st.info)
    tone(f"현재 예측 · 예상 잔여 **{current_remaining}개** · {current_risk}")

    if promotions and not simulated:
        promo = promotions[0]
        st.success(f"{promo['discount_rate']}% 할인이 학생 화면에 노출되었습니다. ({promo['price']:,}원 → {promo['sale_price']:,}원)")
        if st.button("20:00까지 판매 반영 · 30분마다 재예측", type="primary", width="stretch"):
            result = db.simulate_student_response(until_time="20:00")
            run_workflow(BOOTH_ID)
            st.session_state["last_response"] = result
            st.rerun()
    elif simulated:
        result = response_trace or st.session_state.get("last_response")
        if result:
            st.caption(
                f"{result['from'][-5:]} → {result['to'][-5:]} 할인 적용 상태로 "
                f"원클릭 입력 {result.get('pre_recorded_sales', 0)}개를 포함해 "
                f"총 {result.get('window_sales', result['sold'])}개 판매를 반영했습니다."
            )
        st.caption("30분마다 판매·재고 스냅샷을 기록하고, 바뀐 상태를 같은 모델의 다음 입력으로 되돌렸습니다.")
    else:
        st.warning("먼저 운영자 화면에서 20% 할인을 승인해 주세요.")
        st.page_link("pages/operator.py", label="할인 승인하러 가기", icon="🧑‍🍳")

if response_trace and response_trace.get("windows"):
    st.divider()
    st.markdown("### Closed Loop · 30분 단위 재예측 로그")
    st.caption("각 구간의 실제 판매와 마감 재고가 다음 구간 예측의 입력이 됩니다.")
    loop_rows = []
    for index, window in enumerate(response_trace["windows"], start=1):
        loop_rows.append(
            {
                "루프": index,
                "구간": f"{window['from'][-5:]} → {window['to'][-5:]}",
                "AI 예측 판매": f"{window['predicted_sales']}개",
                "실제 반영 판매": f"{window['actual_sales']}개",
                "재고 변화": f"{window['opening_stock']} → {window['closing_stock']}개",
                "다음 입력": f"판매 {window['actual_sales']} · 재고 {window['closing_stock']}",
            }
        )
    st.dataframe(loop_rows, hide_index=True, width="stretch")
    st.markdown(
        "**Predict → Sell → Update → Re-predict**가 세 번 반복됩니다. "
        "즉, 20:00 결과는 고정된 After 숫자가 아니라 직전 결과를 다시 읽어 계산한 값입니다."
    )

st.divider()
st.markdown("### 발표용 2분 시나리오")
st.markdown(
    "1. **17:30 Admin** · 축제 시작 후 재고가 줄어든 것을 확인합니다.\n"
    f"2. **18:00 Admin** · {state['menu_name']} 잔여 위험 알림을 보고 운영 부스에 할인을 제안합니다.\n"
    "3. **18:30 Operator / Student** · 운영자가 `20% 마감 할인`을 승인하고 학생 화면과 원클릭 판매 입력을 보여줍니다.\n"
    "4. **20:00 Before / After** · 30분 단위 폐쇄 루프 로그와 AI 추천 미적용·적용 시 종료 예상 잔여를 비교합니다."
)
st.caption(
    "한 번의 할인으로 위험이 사라지지는 않습니다. 모델이 학습한 할인 탄력성 기준으로 "
    "예상 잔여가 얼마나 줄어드는지를 보여주고, 루프는 새 상태에서 다시 반복됩니다."
)
