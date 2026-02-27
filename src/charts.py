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


def performance_bar_chart(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart of total return % per holding, sorted best to worst.
    Expects DataFrame with columns: symbol, total_return_pct
    """
    df = df.sort_values("total_return_pct", ascending=True)
    colors = ["#4CAF50" if v >= 0 else "#EF5350" for v in df["total_return_pct"]]

    fig = go.Figure(go.Bar(
        x=df["total_return_pct"],
        y=df["symbol"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in df["total_return_pct"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Return: %{x:+.2f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Total Return by Position",
        template=TEMPLATE,
        xaxis_title="Total Return %",
        yaxis_title="",
        height=max(400, len(df) * 35),
        margin=dict(t=60, b=40, l=80, r=60),
    )
    return fig


def waterfall_chart(df: pd.DataFrame) -> go.Figure:
    """
    Waterfall chart showing gain/loss contribution per position.
    Expects DataFrame with columns: symbol, gain_loss_dollar, sorted by absolute value.
    """
    df = df.sort_values("gain_loss_dollar", ascending=False)
    colors = ["#4CAF50" if v >= 0 else "#EF5350" for v in df["gain_loss_dollar"]]

    fig = go.Figure(go.Waterfall(
        x=df["symbol"],
        y=df["gain_loss_dollar"],
        measure=["relative"] * len(df),
        connector=dict(line=dict(color="rgba(255,255,255,0.2)")),
        increasing=dict(marker=dict(color="#4CAF50")),
        decreasing=dict(marker=dict(color="#EF5350")),
        totals=dict(marker=dict(color="#42A5F5")),
        text=[f"${v:+,.0f}" for v in df["gain_loss_dollar"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Gain/Loss: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Gain/Loss Contribution by Position",
        template=TEMPLATE,
        yaxis_title="Gain/Loss ($)",
        height=450,
        margin=dict(t=60, b=40, l=80, r=40),
        showlegend=False,
    )
    return fig


def benchmark_chart(cumulative: pd.DataFrame) -> go.Figure:
    """
    Line chart of portfolio vs. SPY cumulative returns as percentages.
    Expects DataFrame with columns: Portfolio, SPY (both normalized to 100).
    """
    # Convert from base-100 to percentage (100 -> 0%, 115 -> 15%)
    # Use Python round via applymap to avoid float64 precision artifacts
    pct = (cumulative - 100).apply(lambda col: col.apply(lambda v: round(v, 2)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pct.index, y=pct["Portfolio"].tolist(),
        name="Portfolio", line=dict(color="#4CAF50", width=2),
        hovertemplate="%{x|%b %d, %Y}<br>Portfolio: %{y:+.2f}%<extra></extra>",
    ))
    if "SPY" in pct.columns:
        fig.add_trace(go.Scatter(
            x=pct.index, y=pct["SPY"].tolist(),
            name="SPY", line=dict(color="#42A5F5", width=2, dash="dot"),
            hovertemplate="%{x|%b %d, %Y}<br>SPY: %{y:+.2f}%<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig.update_layout(
        title="Portfolio vs. S&P 500 (SPY)",
        template=TEMPLATE,
        xaxis_title="",
        yaxis_title="Cumulative Return (%)",
        yaxis_ticksuffix="%",
        height=500,
        margin=dict(t=60, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
