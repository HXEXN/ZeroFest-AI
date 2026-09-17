"""Plotly charts kept intentionally simple for presentation readability."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


RISK_COLORS = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}


def remaining_by_booth(rows: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(rows)
    figure = px.bar(
        frame,
        x="booth_name",
        y="expected_remaining",
        color="risk_level",
        color_discrete_map=RISK_COLORS,
        labels={"booth_name": "부스", "expected_remaining": "예상 잔여(개)", "risk_level": "위험"},
        text="expected_remaining",
    )
    figure.update_traces(textposition="outside")
    figure.update_layout(
        height=320, margin=dict(l=10, r=10, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend_orientation="h", legend_y=1.14,
    )
    return figure


def before_after(before: int, after: int) -> go.Figure:
    figure = go.Figure(
        go.Bar(
            x=["AI Action 전", "AI Action 후"],
            y=[before, after],
            text=[f"{before}개", f"{after}개"],
            textposition="outside",
            marker_color=["#ef4444", "#10b981"],
            width=[0.52, 0.52],
        )
    )
    figure.update_layout(
        height=340, yaxis_title="종료 시 예상 잔여(개)", yaxis_range=[0, max(before, after) * 1.3],
        margin=dict(l=10, r=10, t=25, b=10), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    return figure

