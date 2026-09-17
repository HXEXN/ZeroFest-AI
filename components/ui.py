"""Shared visual language and demo controls."""

from __future__ import annotations

from html import escape

import streamlit as st

from agents.graph import analyze_all
from services.database import reset_demo


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

MOBILE_CSS = """
<style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
    [data-testid="stMainBlockContainer"] {
        max-width:430px !important; padding:0 15px 92px !important;
        border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0;
        min-height:100vh; background:#faf8ff;
    }
    .stApp { background:#eef1f8 !important; }
    .zf-mobile-top { margin:0 -15px 14px; padding:12px 15px; background:rgba(250,248,255,.96);
        border-bottom:1px solid #dfe4f2; position:sticky; top:0; z-index:30; backdrop-filter:blur(14px); }
    .zf-mobile-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .zf-brand { display:flex; align-items:center; gap:9px; min-width:0; }
    .zf-logo { width:38px; height:38px; border-radius:11px; background:#005226; color:white; display:grid;
        place-items:center; font-weight:900; box-shadow:0 4px 12px rgba(0,76,34,.16); }
    .zf-brand-title { font-size:17px; line-height:1.1; font-weight:850; color:#131b2e; letter-spacing:-.03em; }
    .zf-brand-sub { font-size:10px; color:#64748b; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .zf-status { display:inline-flex; align-items:center; gap:5px; padding:5px 8px; border-radius:999px;
        background:#d1fae5; color:#006c49; border:1px solid #8ee5bd; font-size:10px; font-weight:850; white-space:nowrap; }
    .zf-dot { width:7px; height:7px; background:#10b981; border-radius:50%; box-shadow:0 0 0 3px #bbf7d0; }
    .zf-mobile-card { background:#fff; border:1px solid #e2e8f0; border-radius:15px; padding:14px;
        box-shadow:0 2px 7px rgba(15,23,42,.05); margin:10px 0; }
    .zf-mobile-card.danger { background:#fff5f5; border-color:#fecaca; }
    .zf-mobile-card.mint { background:linear-gradient(135deg,#ecfdf5,#fff); border-color:#bbf7d0; }
    .zf-eyebrow { font-size:10px; font-weight:850; letter-spacing:.05em; color:#166534; text-transform:uppercase; }
    .zf-mobile-h1 { font-size:25px; line-height:1.24; font-weight:900; letter-spacing:-.045em; margin:8px 0; color:#131b2e; }
    .zf-mobile-h2 { font-size:18px; font-weight:850; letter-spacing:-.03em; margin:0; color:#131b2e; }
    .zf-caption { font-size:11px; line-height:1.45; color:#64748b; }
    .zf-kpi-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0; }
    .zf-kpi { background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:12px; min-height:94px;
        box-shadow:0 2px 6px rgba(15,23,42,.04); }
    .zf-kpi.danger { background:#fff1f2; border-color:#fecdd3; }
    .zf-kpi-label { font-size:11px; color:#475569; font-weight:700; }
    .zf-kpi-value { margin-top:7px; font-family:"JetBrains Mono",ui-monospace,monospace; font-size:23px;
        color:#131b2e; font-weight:850; letter-spacing:-.06em; }
    .zf-kpi-note { margin-top:6px; font-size:10px; color:#64748b; font-weight:700; }
    .zf-danger-text { color:#c81e1e !important; }
    .zf-mint-text { color:#047857 !important; }
    .zf-signal { display:flex; gap:9px; align-items:flex-start; background:#fff; border-radius:10px; padding:9px;
        margin-top:7px; border:1px solid #edf0f7; font-size:11px; font-weight:700; }
    .zf-signal b { width:24px; height:24px; display:grid; place-items:center; flex:0 0 24px; border-radius:6px;
        background:#fee2e2; color:#b91c1c; }
    .zf-action-row { background:#f0fdf4; border:1px solid #bbf7d0; padding:9px; border-radius:10px;
        font-size:11px; font-weight:800; margin-top:7px; }
    .zf-progress { height:12px; border-radius:999px; overflow:hidden; background:#e9edfb; }
    .zf-progress > i { display:block; height:100%; border-radius:999px; }
    .zf-booth-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
    .zf-bottom-nav { position:fixed; bottom:0; left:50%; transform:translateX(-50%); z-index:100;
        width:min(430px,100vw); display:grid; grid-template-columns:repeat(4,1fr); padding:7px 8px max(8px,env(safe-area-inset-bottom));
        background:rgba(255,255,255,.96); border-top:1px solid #dfe4f2; box-shadow:0 -5px 18px rgba(15,23,42,.07);
        backdrop-filter:blur(15px); }
    .zf-bottom-nav a { color:#64748b; text-decoration:none; text-align:center; font-size:9px; font-weight:750;
        min-height:46px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; border-radius:10px; }
    .zf-bottom-nav a span { font-size:19px; line-height:1; }
    .zf-bottom-nav a.active { color:#166534; background:#ecfdf5; font-weight:900; }
    .zf-section-title { display:flex; align-items:center; justify-content:space-between; margin:18px 2px 8px; }
    .zf-section-title strong { font-size:18px; color:#131b2e; letter-spacing:-.035em; }
    .zf-weather { background:#fff1f2; border:1px solid #fecdd3; color:#9f1239; border-radius:14px; padding:12px; margin:8px 0; }
    .zf-pill { display:inline-flex; align-items:center; padding:3px 7px; border-radius:999px; font-size:9px; font-weight:850; }
    .zf-pill.high { background:#ef4444; color:white; } .zf-pill.medium { background:#ffedd5; color:#9a3412; }
    .zf-pill.low { background:#d1fae5; color:#047857; }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button { min-height:52px !important; font-size:14px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px !important; border-color:#dfe4f2 !important; background:#fff; }
    [data-testid="stMetric"] { padding:11px !important; min-height:96px; }
    [data-testid="stMetricLabel"] { font-size:11px !important; }
    [data-testid="stMetricValue"] { font-size:23px !important; }
    .stTabs [data-baseweb="tab-list"] { gap:4px; background:#eef2ff; border-radius:12px; padding:4px; }
    .stTabs [data-baseweb="tab"] { border-radius:9px; font-size:11px; min-height:40px; }
    @media (max-width:480px) { [data-testid="stMainBlockContainer"] { border:0; } }
</style>
"""


def configure_page(title: str, icon: str = "🌿", mobile: bool = False) -> None:
    st.set_page_config(page_title=f"{title} | ZeroFest AI", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    if mobile:
        st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def mobile_header(title: str, subtitle: str, badge: str = "AI 연동", icon: str = "ZF") -> None:
    st.markdown(
        f'<div class="zf-mobile-top"><div class="zf-mobile-row"><div class="zf-brand">'
        f'<div class="zf-logo">{escape(icon)}</div><div><div class="zf-brand-title">{escape(title)}</div>'
        f'<div class="zf-brand-sub">{escape(subtitle)}</div></div></div>'
        f'<div class="zf-status"><span class="zf-dot"></span>{escape(badge)}</div></div></div>',
        unsafe_allow_html=True,
    )


# Every mobile screen shows the same four destinations. A page that renders the
# mobile shell without this nav strands the visitor: phones have no sidebar.
MOBILE_NAV = [
    ("gateway", "게이트웨이", "▦", "/"),
    ("simulation", "AI 시뮬레이터", "⚡", "/simulation"),
    ("student", "부스·지도", "▰", "/student"),
    ("chat", "AI 코파일럿", "✨", "/chat"),
]


def mobile_bottom_nav(items: list[tuple[str, str, str, str]], active: str) -> None:
    links = "".join(
        f'<a href="{escape(href)}" target="_self" class="{"active" if key == active else ""}">'
        f'<span>{escape(icon)}</span>{escape(label)}</a>'
        for key, label, icon, href in items
    )
    st.markdown(f'<nav class="zf-bottom-nav">{links}</nav>', unsafe_allow_html=True)


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="zf-header-shell"><div><div class="zf-kicker">{kicker}</div>'
        f'<div class="zf-title">{title}</div><div class="zf-subtitle">{subtitle}</div></div>'
        '<div class="zf-live"><span class="zf-live-dot"></span> REALTIME · 19:00</div></div>',
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
        st.caption("19:00 · 1시간 뒤 비 예보 · 메인 공연 종료 예정")


def flow_strip() -> None:
    st.markdown(
        '<div class="zf-flow"><span>Data</span><b>→</b><span>Predict</span><b>→</b>'
        '<span>Decide</span><b>→</b><span>Human Approval</span><b>→</b>'
        '<span>Demand Change</span><b>→</b><span>Re-predict</span></div>',
        unsafe_allow_html=True,
    )
