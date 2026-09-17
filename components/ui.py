"""Shared visual language and demo controls."""

from __future__ import annotations

import streamlit as st

from agents.graph import analyze_all
from services.database import get_demo_time, reset_demo


CSS = """
<style>
    :root {
        --zf-primary:#166534; --zf-primary-dark:#004c22; --zf-mint:#10b981;
        --zf-orange:#f97316; --zf-canvas:#faf8ff; --zf-soft:#f2f3ff;
        --zf-panel:#ffffff; --zf-ink:#131b2e; --zf-muted:#64748b;
        --zf-line:#e2e8f0; --zf-lavender:#eaedff;
    }
    html, body, [class*="css"] { font-family:Inter, Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .stApp { background:linear-gradient(180deg, var(--zf-canvas) 0%, #f8fafc 62%, #ffffff 100%); color:var(--zf-ink); }
    .block-container { max-width:1220px; padding-top:1.5rem; padding-bottom:5rem; }
    [data-testid="stSidebarNav"] { display:none; }
    [data-testid="stSidebar"] { background:#ffffff; border-right:1px solid var(--zf-line); }
    [data-testid="stSidebar"] h2 { color:var(--zf-primary-dark); letter-spacing:-.04em; }
    [data-testid="stSidebar"] a { border-radius:10px; min-height:42px; }
    [data-testid="stSidebar"] a:hover { background:var(--zf-soft); }
    .zf-kicker { color:var(--zf-primary); font-weight:800; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; }
    .zf-title { color:var(--zf-ink); font-size:2rem; font-weight:800; letter-spacing:-.035em; line-height:1.18; margin:.28rem 0 .45rem; }
    .zf-hero { color:var(--zf-ink); font-size:clamp(2.35rem,5.2vw,3.5rem); font-weight:850; letter-spacing:-.05em; line-height:1.12; margin:.25rem 0 .8rem; word-break:keep-all; }
    .zf-subtitle { color:#475569; font-size:.96rem; max-width:790px; line-height:1.62; }
    .zf-header-shell { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; padding-bottom:.5rem; }
    .zf-live { flex:0 0 auto; display:flex; align-items:center; gap:.45rem; border:1px solid #bbf7d0; background:#f0fdf4; color:#166534; border-radius:999px; padding:.45rem .75rem; font-size:.72rem; font-weight:800; }
    .zf-live-dot { width:7px; height:7px; background:var(--zf-mint); border-radius:50%; box-shadow:0 0 0 4px #d1fae5; }
    .zf-banner { border:1px solid #c7d2fe; background:#eef2ff; color:#3730a3; border-radius:12px; padding:.68rem .9rem; margin:.65rem 0 1.15rem; font-size:.79rem; }
    .zf-card { border:1px solid var(--zf-line); background:var(--zf-panel); border-radius:16px; padding:1.1rem; box-shadow:0 1px 3px rgba(15,23,42,.04),0 1px 2px rgba(15,23,42,.03); height:100%; }
    .zf-card:hover { border-color:#cbd5e1; box-shadow:0 4px 8px rgba(15,23,42,.055); }
    .zf-card h3 { margin:0 0 .35rem; color:var(--zf-ink); font-size:1.03rem; }
    .zf-muted { color:var(--zf-muted); font-size:.79rem; line-height:1.5; }
    .zf-numeric { font-family:"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace; font-variant-numeric:tabular-nums; letter-spacing:-.04em; }
    .zf-risk-high,.zf-risk-medium,.zf-risk-low { display:inline-flex; align-items:center; gap:.32rem; padding:.25rem .6rem; border-radius:999px; font-size:.7rem; letter-spacing:.04em; font-weight:800; }
    .zf-risk-high { background:#fef2f2; color:#991b1b; }
    .zf-risk-high:before { content:""; width:6px; height:6px; border-radius:50%; background:#ef4444; animation:zf-pulse 1.6s infinite; }
    .zf-risk-medium { background:#fffbeb; color:#92400e; }
    .zf-risk-medium:before { content:""; width:6px; height:6px; border-radius:50%; background:#f59e0b; }
    .zf-risk-low { background:#ecfdf5; color:#065f46; }
    .zf-risk-low:before { content:""; width:6px; height:6px; border-radius:50%; background:#10b981; }
    .zf-flow { display:flex; align-items:center; gap:.38rem; flex-wrap:wrap; margin:.9rem 0; }
    .zf-flow span { padding:.4rem .65rem; border-radius:8px; background:var(--zf-soft); border:1px solid #dbe2ff; font-size:.72rem; font-weight:750; }
    .zf-flow b { color:var(--zf-mint); }
    .zf-provenance { display:inline-flex; gap:.45rem; align-items:center; border:1px solid #fed7aa; background:#fff7ed; color:#9a3412; border-radius:999px; padding:.35rem .62rem; font-size:.68rem; font-weight:750; }
    .zf-stage { border:1px solid var(--zf-line); background:#fff; border-radius:12px; padding:.75rem; min-height:92px; }
    .zf-stage-pass { color:#047857; font-weight:800; font-size:.68rem; }
    .zf-copilot { border:1px solid #bbf7d0; background:linear-gradient(135deg,#f0fdf4 0%,#ffffff 58%,#fff7ed 100%); border-radius:18px; padding:1rem 1.1rem; margin:.7rem 0 1rem; }
    .zf-copilot strong { color:#004c22; }
    div[data-testid="stMetric"] { background:#fff; border:1px solid var(--zf-line); padding:.92rem; border-radius:14px; box-shadow:0 1px 3px rgba(15,23,42,.035); }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-family:"JetBrains Mono", ui-monospace, monospace; font-variant-numeric:tabular-nums; letter-spacing:-.04em; color:var(--zf-ink); }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button { border-radius:12px; font-weight:750; min-height:48px; border-color:#cbd5e1; }
    button[kind="primary"] { background:var(--zf-primary) !important; border-color:var(--zf-primary) !important; }
    button:focus-visible, a:focus-visible, input:focus-visible { outline:3px solid rgba(22,101,52,.28) !important; outline-offset:2px; }
    [data-testid="stAlert"] { border-radius:12px; }
    [data-testid="stDataFrame"] { border:1px solid var(--zf-line); border-radius:14px; overflow:hidden; }
    @keyframes zf-pulse { 50% { box-shadow:0 0 0 5px rgba(239,68,68,.12); } }
    @media (prefers-reduced-motion: reduce) { .zf-risk-high:before { animation:none; } }
    @media (max-width: 760px) {
        .block-container { padding:1rem 1rem 5.5rem; }
        .zf-header-shell { display:block; }
        .zf-live { margin-top:.75rem; width:max-content; }
        .zf-title { font-size:1.7rem; }
        .zf-hero { font-size:2.25rem; }
        div[data-testid="stHorizontalBlock"] { gap:.65rem; }
        div[data-testid="stMetric"] { padding:.72rem; }
        .zf-card { padding:.9rem; }
    }
</style>
"""


def configure_page(title: str, icon: str = "🌿") -> None:
    st.set_page_config(page_title=f"{title} | ZeroFest AI", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(kicker: str, title: str, subtitle: str) -> None:
    now_label = get_demo_time().strftime("%H:%M")
    st.markdown(
        f'<div class="zf-header-shell"><div><div class="zf-kicker">{kicker}</div>'
        f'<div class="zf-title">{title}</div><div class="zf-subtitle">{subtitle}</div></div>'
        f'<div class="zf-live"><span class="zf-live-dot"></span> REALTIME · {now_label}</div></div>',
        unsafe_allow_html=True,
    )
    demo_banner()


def demo_banner() -> None:
    st.markdown(
        '<div class="zf-banner">🧪 <b>Demo Simulation</b> · 모든 축제·판매·날씨·효과 수치는 '
        'Sample / Synthetic Data이며 실제 실증 결과가 아닙니다.</div>',
        unsafe_allow_html=True,
    )


def risk_badge(level: str) -> str:
    normalized = (level or "LOW").lower()
    return f'<span class="zf-risk-{normalized}">{level}</span>'


def sidebar(role: str) -> None:
    with st.sidebar:
        st.markdown("## ZeroFest AI")
        st.caption(f"현재 화면 · {role}")
        st.page_link("app.py", label="시작 화면", icon="🏠")
        st.page_link("pages/admin.py", label="학생회 Control Tower", icon="📊")
        st.page_link("pages/chat.py", label="AI 운영 Copilot", icon="✨")
        st.page_link("pages/operator.py", label="부스 운영자", icon="🧑‍🍳")
        st.page_link("pages/student.py", label="학생", icon="🎓")
        st.page_link("pages/simulation.py", label="Before / After", icon="🧪")
        st.page_link("pages/ai_ops.py", label="AI · ML · Data Ops", icon="🧠")
        st.divider()
        if st.button("↻ Demo 전체 초기화", width="stretch"):
            with st.spinner("샘플 상태를 복원하는 중..."):
                reset_demo()
                analyze_all()
            st.session_state.clear()
            st.rerun()
        st.caption(f"{get_demo_time():%H:%M} · 행사 종료 22:00 · 30분 단위 Demo")


def flow_strip() -> None:
    st.markdown(
        '<div class="zf-flow"><span>Data</span><b>→</b><span>Predict</span><b>→</b>'
        '<span>Decide</span><b>→</b><span>Human Approval</span><b>→</b>'
        '<span>Demand Change</span><b>→</b><span>Re-predict</span></div>',
        unsafe_allow_html=True,
    )
