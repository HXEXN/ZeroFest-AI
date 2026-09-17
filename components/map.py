"""Privacy-safe mock festival map for zone-level demand routing."""

from __future__ import annotations

import streamlit as st


def festival_map(chicken_discount: bool = False, admin: bool = False) -> None:
    chicken = "🔥 20% 할인" if chicken_discount else ("재고 ↑ · 위험 🔴" if admin else "닭꼬치")
    st.markdown(
        f"""
        <div style="position:relative;height:355px;border-radius:18px;background:linear-gradient(145deg,#eaedff,#f2f3ff);
                    border:1px solid #d8def8;overflow:hidden;padding:20px;">
          <div style="position:absolute;left:31%;top:24%;width:38%;height:72px;background:#102a22;color:white;
                      border-radius:16px;padding:14px;text-align:center;font-weight:800;">🎤 Main Stage<br>
                      <small style="color:#a7f3d0">메인 공연 · 혼잡</small></div>
          <div style="position:absolute;left:7%;top:58%;width:25%;background:white;border:2px solid #ef4444;
                      border-radius:16px;padding:14px;box-shadow:0 8px 18px #0001;"><b>A ZONE</b><br>🍗 {chicken}</div>
          <div style="position:absolute;left:39%;top:64%;width:25%;background:white;border:2px solid #10b981;
                      border-radius:16px;padding:14px;box-shadow:0 8px 18px #0001;"><b>B ZONE</b><br>🥤 수요 ↑ · 혼잡</div>
          <div style="position:absolute;right:6%;top:53%;width:24%;background:white;border:2px solid #f59e0b;
                      border-radius:16px;padding:14px;box-shadow:0 8px 18px #0001;"><b>C ZONE</b><br>🍲 보통</div>
          <div style="position:absolute;left:8%;top:18%;color:#547268;font-size:.78rem;">Mock Location · 구역 단위<br>정밀 위치 추적 없음</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
