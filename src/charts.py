"""Plotly chart builders for WealthLens."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

TEMPLATE = "plotly_dark"
COLORS = px.colors.qualitative.Set2


def donut_chart(labels: list, values: list, title: str) -> go.Figure:
    """Generic donut chart."""
    total = sum(values)
    # Only show text on slices >= 3% to avoid clutter
    text_positions = ["inside" if v / total >= 0.03 else "none" for v in values]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        textinfo="label+percent",
        textposition=text_positions,
        insidetextorientation="horizontal",
        marker=dict(colors=COLORS),
        hovertemplate="<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>",
    )])
    fig.update_layout(
        title=title,
        template=TEMPLATE,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        margin=dict(t=60, b=100, l=20, r=20),
        height=500,
    )
    return fig


def sector_allocation_chart(sector_data: pd.DataFrame) -> go.Figure:
    """
    Donut chart for sector allocation.
    Expects DataFrame with columns: sector, value
    """
    grouped = sector_data.groupby("sector")["value"].sum().sort_values(ascending=False)
    return donut_chart(grouped.index.tolist(), grouped.values.tolist(), "Sector Allocation")


def asset_class_chart(class_data: pd.DataFrame) -> go.Figure:
    """
    Donut chart for asset class breakdown.
    Expects DataFrame with columns: asset_class, value
    """
    grouped = class_data.groupby("asset_class")["value"].sum().sort_values(ascending=False)
    return donut_chart(grouped.index.tolist(), grouped.values.tolist(), "Asset Class Breakdown")
