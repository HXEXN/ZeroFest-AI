"""Role-aware, database-grounded operations chat."""

from __future__ import annotations

import streamlit as st

from agents.graph import ensure_predictions
from components.ui import (
    MOBILE_NAV,
    configure_page,
    mobile_bottom_nav,
    mobile_header,
    page_header,
    risk_badge,
    sidebar,
)
from services import database as db
from services.chat import ask_operations


configure_page("AI 운영 Copilot", "✨", mobile=True)

# -------------------------------------------------------------------
# AI Copilot 전용 레이아웃
# st.chat_input()의 fixed bottom container를 사용하지 않고
# 본문 내부 form composer를 사용해 ZeroFest 하단 네비와 충돌하지 않게 한다.
# -------------------------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"],
    .block-container {
        padding-bottom: 115px !important;
    }

    /* Copilot 대화 영역 */
    [data-testid="stChatMessage"] {
        background: transparent !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    [data-testid="stChatMessageContent"] {
        font-size: 14px !important;
        line-height: 1.55 !important;
    }

    /* 입력 폼 */
    div[data-testid="stForm"] {
        background: #ffffff !important;
        border: 1px solid #dbe3ee !important;
        border-radius: 16px !important;
        padding: 10px !important;
        margin-top: 14px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;
    }

    div[data-testid="stForm"] [data-testid="stTextInput"] {
        margin-bottom: 0 !important;
    }

    div[data-testid="stForm"] [data-testid="stTextInput"] > div > div {
        border-radius: 12px !important;
        border-color: #cbd5e1 !important;
        background: #f8fafc !important;
        min-height: 48px !important;
    }

    div[data-testid="stForm"] input {
        font-size: 14px !important;
        min-height: 46px !important;
    }

    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        min-height: 48px !important;
        height: 48px !important;
        border-radius: 12px !important;
        font-size: 13px !important;
        font-weight: 850 !important;
        white-space: nowrap !important;
        padding: 0 10px !important;
    }

    /* 하단 부가 액션 */
    .zf-chat-footer-note {
        font-size: 11px;
        line-height: 1.5;
        color: #64748b;
        margin: 8px 2px 2px;
    }

    @media (max-width: 440px) {
        div[data-testid="stForm"] {
            padding: 8px !important;
        }

        div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
            gap: 8px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

db.initialize_database()
ensure_predictions()

sidebar("AI 운영 Copilot")

mobile_header(
    "ZeroFest Copilot",
    "운영 DB에 근거한 즉답",
    "GROUNDED",
    "AI",
)

page_header(
    "ZERO FEST AI · GROUNDED COPILOT",
    "묻는 즉시, 현재 운영 데이터로 답합니다",
    "판매·재고·예측·날씨·공연·Action Queue만 근거로 설명합니다. "
    "채팅은 실행 권한이 없고 최종 Action은 운영자가 승인합니다.",
)


# -------------------------------------------------------------------
# 대화 범위
# -------------------------------------------------------------------

booths = db.get_booths()

scope_options = [None] + [item["booth_id"] for item in booths]

labels = {None: "축제 전체 · Control Tower"}
labels.update(
    {
        item["booth_id"]: (
            f"{item['zone']}구역 · "
            f"{item['booth_name']} · "
            f"{item['menu_name']}"
        )
        for item in booths
    }
)

scope = st.selectbox(
    "대화 범위",
    scope_options,
    format_func=labels.get,
)


# -------------------------------------------------------------------
# 현재 운영 상태
# -------------------------------------------------------------------

rows = db.dashboard_rows()

if scope:
    focus = next(
        row
        for row in rows
        if row["booth_id"] == scope
    )
else:
    priority = {
        "HIGH": 2,
        "MEDIUM": 1,
        "LOW": 0,
    }

    focus = max(
        rows,
        key=lambda row: (
            priority.get(
                row.get("risk_level"),
                -1,
            ),
            int(
                row.get("expected_remaining")
                or 0
            ),
        ),
    )


m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "현재 재고",
    f"{int(focus['current_stock']):,}개",
)

m2.metric(
    "다음 30분",
    f"{int(focus.get('predicted_sales_30m') or 0):,}개",
)

m3.metric(
    "종료 예상 잔여",
    f"{int(focus.get('expected_remaining') or 0):,}개",
)

with m4:
    st.caption("폐기 위험도")

    st.markdown(
        risk_badge(
            str(
                focus.get("risk_level")
                or "LOW"
            )
        ),
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# 빠른 질문
# -------------------------------------------------------------------

st.markdown("#### 빠른 질문")

prompts = [
    "지금 운영 상황을 3줄로 브리핑해줘",
    "가장 위험한 부스와 이유를 알려줘",
    "재고는 언제 다 소진될 것으로 보여?",
    "지금 추천 Action은 무엇이야?",
]

prompt_cols = st.columns(2)

queued_prompt = None

for index, label in enumerate(prompts):
    if prompt_cols[index % 2].button(
        label,
        key=f"quick-{index}",
        width="stretch",
    ):
        queued_prompt = label


# -------------------------------------------------------------------
# 채팅 히스토리
# -------------------------------------------------------------------

scope_key = scope or "all"
history_key = f"operations_chat:{scope_key}"

if history_key not in st.session_state:
    st.session_state[history_key] = [
        {
            "role": "assistant",
            "content": (
                "현재 운영 DB와 AI 예측이 연결되었습니다. "
                "위험 우선순위, 할인 근거, 품절 시각, 날씨 영향, "
                "추천 Action을 물어보세요."
            ),
            "source": "ZeroFest AI",
            "evidence": [],
        }
    ]


for message in st.session_state[history_key]:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )

        if message.get("evidence"):

            with st.expander(
                "사용한 실시간 근거",
                expanded=False,
            ):

                for item in message["evidence"]:
                    st.markdown(
                        f"- {item}"
                    )

        if message.get("source"):
            st.caption(
                message["source"]
            )


# -------------------------------------------------------------------
# Copilot 입력창
#
# st.chat_input()을 사용하지 않는다.
# Streamlit의 fixed bottom layer와 ZeroFest fixed bottom nav가 겹치는
# 문제를 원천적으로 피하기 위해 본문 내부 form을 사용한다.
# -------------------------------------------------------------------

with st.form(
    "copilot_input_form",
    clear_on_submit=True,
    border=False,
):

    input_col, send_col = st.columns(
        [4.6, 1.15],
        vertical_alignment="bottom",
    )

    with input_col:
        typed_prompt = st.text_input(
            "AI Copilot 질문",
            placeholder="예: 닭꼬치를 왜 할인해야 해?",
            label_visibility="collapsed",
        )

    with send_col:
        submitted = st.form_submit_button(
            "전송",
            type="primary",
            width="stretch",
        )


question = queued_prompt or (
    typed_prompt.strip()
    if submitted and typed_prompt
    else None
)

if question:

    st.session_state[
        history_key
    ].append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.spinner(
        "현재 DB와 예측 근거를 확인하는 중..."
    ):

        answer, source, evidence = (
            ask_operations(
                question,
                booth_id=scope,
            )
        )

    st.session_state[
        history_key
    ].append(
        {
            "role": "assistant",
            "content": answer,
            "source": source,
            "evidence": evidence,
        }
    )

    st.rerun()


# -------------------------------------------------------------------
# 하단 액션
# -------------------------------------------------------------------

bottom_left, bottom_right = st.columns(2)

if bottom_left.button(
    "대화 초기화",
    width="stretch",
):

    if history_key in st.session_state:
        del st.session_state[
            history_key
        ]

    st.rerun()


with bottom_right:

    st.page_link(
        "pages/operator.py",
        label="추천 Action 승인 화면 →",
        icon="🧑‍🍳",
        width="stretch",
    )


st.info(
    "안전장치 · 채팅은 설명만 제공합니다. "
    "할인·조리 중단·재고 이동은 운영자 화면에서 "
    "승인해야 실행됩니다."
)


mobile_bottom_nav(
    MOBILE_NAV,
    "chat",
)
