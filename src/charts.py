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
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Return: %{x:+.2f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Total Return by Position",
        template=TEMPLATE,
        xaxis_title="Total Return %",
        yaxis_title="",
        height=max(400, len(df) * 35),
        margin=dict(t=60, b=40, l=80, r=100),
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


def concentration_chart(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart of top 10 holdings by portfolio weight.
    Expects DataFrame with columns: symbol, weight
    """
    df = df.nlargest(10, "weight").sort_values("weight", ascending=True)

    # Gradient from muted to bright based on weight
    max_w = df["weight"].max()
    colors = [
        f"rgba(76, 175, 80, {0.4 + 0.6 * (w / max_w)})" for w in df["weight"]
    ]

    fig = go.Figure(go.Bar(
        x=df["weight"],
        y=df["symbol"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df["weight"]],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(color="#FAFAFA"),
        hovertemplate="<b>%{y}</b><br>Weight: %{x:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Top 10 Holdings by Weight",
        template=TEMPLATE,
        xaxis_title="Portfolio Weight %",
        xaxis_ticksuffix="%",
        yaxis_title="",
        height=420,
        margin=dict(t=60, b=40, l=80, r=100),
    )
    return fig


def correlation_heatmap(corr: pd.DataFrame) -> go.Figure:
    """
    Heatmap of pairwise return correlations.
    Red (negative) → dark bg (zero) → green (positive).
    """
    tickers = corr.columns.tolist()
    z = corr.values

    # Custom colorscale: red → orange → yellow → light green → green
    colorscale = [
        [0.0, "#EF5350"],
        [0.25, "#FF7043"],
        [0.4, "#FFA726"],
        [0.5, "#FFCA28"],
        [0.65, "#C6D94E"],
        [0.8, "#66BB6A"],
        [1.0, "#2E7D32"],
    ]

    # Build annotation text — show values, but blank the diagonal
    annotations = []
    for i, row_ticker in enumerate(tickers):
        for j, col_ticker in enumerate(tickers):
            val = z[i][j]
            if i == j:
                text = ""
                font_color = "rgba(0,0,0,0)"
            else:
                text = f"{val:.2f}"
                # Dark text on bright mid-range cells, light text on dark extremes
                norm = (val + 1) / 2  # 0 to 1
                if 0.35 < norm < 0.65:
                    font_color = "rgba(30, 30, 30, 0.9)"
                else:
                    font_color = "rgba(250, 250, 250, 0.9)"

            annotations.append(dict(
                x=col_ticker, y=row_ticker,
                text=text,
                font=dict(size=11, color=font_color),
                showarrow=False,
            ))

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=tickers,
        y=tickers,
        colorscale=colorscale,
        zmin=-1, zmax=1,
        hovertemplate="<b>%{x} × %{y}</b><br>Correlation: %{z:.2f}<extra></extra>",
        colorbar=dict(
            title=dict(text="Corr", side="right"),
            tickvals=[-1, -0.5, 0, 0.5, 1],
            ticktext=["-1.0", "-0.5", "0.0", "0.5", "1.0"],
        ),
    ))

    n = len(tickers)
    fig.update_layout(
        title="Return Correlations (1Y Daily)",
        template=TEMPLATE,
        annotations=annotations,
        xaxis=dict(side="bottom", tickangle=-45),
        yaxis=dict(autorange="reversed"),
        height=max(500, n * 45 + 120),
        width=max(500, n * 45 + 120),
        margin=dict(t=60, b=80, l=80, r=40),
    )

    return fig


def dividend_bar_chart(df: pd.DataFrame) -> go.Figure:
    """
    Bar chart of projected annual dividend income by position.
    Expects DataFrame with columns: symbol, annual_income, yield_pct
    """
    df = df.sort_values("annual_income", ascending=True)

    # Gradient: dimmer for small, brighter for large
    max_inc = df["annual_income"].max() if df["annual_income"].max() > 0 else 1
    colors = [
        f"rgba(76, 175, 80, {0.3 + 0.7 * (v / max_inc)})" for v in df["annual_income"]
    ]

    fig = go.Figure(go.Bar(
        x=df["annual_income"],
        y=df["symbol"],
        orientation="h",
        marker_color=colors,
        text=[f"${v:,.2f}" for v in df["annual_income"]],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(color="#FAFAFA"),
        customdata=df["yield_pct"].values,
        hovertemplate="<b>%{y}</b><br>Annual Income: $%{x:,.2f}<br>Yield: %{customdata:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Projected Annual Dividend Income",
        template=TEMPLATE,
        xaxis_title="Annual Income ($)",
        yaxis_title="",
        height=max(400, len(df) * 35),
        margin=dict(t=60, b=40, l=80, r=100),
    )
    return fig


def dividend_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """
    Monthly bar chart of estimated historical dividend income over the past year.
    Expects DataFrame with columns: month (datetime), income
    """
    fig = go.Figure(go.Bar(
        x=df["month"],
        y=df["income"],
        marker=dict(
            color=df["income"],
            colorscale=[[0, "rgba(76,175,80,0.3)"], [1, "#4CAF50"]],
        ),
        text=[f"${v:,.2f}" for v in df["income"]],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(color="#FAFAFA", size=10),
        hovertemplate="%{x|%b %Y}<br>Est. Income: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Estimated Monthly Dividend Income (Past Year)",
        template=TEMPLATE,
        xaxis_title="",
        yaxis_title="Income ($)",
        height=400,
        margin=dict(t=80, b=40, l=60, r=20),
        xaxis=dict(dtick="M1", tickformat="%b\n%Y"),
    )
    return fig


CAP_COLORS = {
    "Large Cap": "#42A5F5",
    "Mid Cap": "#FFA726",
    "Small Cap": "#EF5350",
    "Unknown": "#78909C",
}


def market_cap_donut(df: pd.DataFrame) -> go.Figure:
    """
    Donut chart of portfolio weight by market cap bucket.
    Expects DataFrame with columns: cap_bucket, value
    """
    grouped = df.groupby("cap_bucket")["value"].sum()
    # Order: Large, Mid, Small, Unknown
    order = ["Large Cap", "Mid Cap", "Small Cap", "Unknown"]
    grouped = grouped.reindex([b for b in order if b in grouped.index])
    colors = [CAP_COLORS.get(b, "#78909C") for b in grouped.index]

    fig = go.Figure(data=[go.Pie(
        labels=grouped.index.tolist(),
        values=grouped.values.tolist(),
        hole=0.45,
        textinfo="label+percent",
        textposition="inside",
        insidetextorientation="horizontal",
        marker=dict(colors=colors),
        hovertemplate="<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>",
    )])
    fig.update_layout(
        title="Market Cap Allocation",
        template=TEMPLATE,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        margin=dict(t=60, b=80, l=20, r=20),
        height=450,
    )
    return fig


def market_cap_treemap(df: pd.DataFrame) -> go.Figure:
    """
    Treemap of holdings grouped by market cap bucket.
    Expects DataFrame with columns: symbol, cap_bucket, value
    """
    fig = px.treemap(
        df,
        path=["cap_bucket", "symbol"],
        values="value",
        color="cap_bucket",
        color_discrete_map=CAP_COLORS,
        template=TEMPLATE,
    )
    fig.update_traces(
        textinfo="label+percent root",
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}",
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<br>%{percentRoot:.1%} of portfolio<extra></extra>",
    )
    fig.update_layout(
        title="Holdings by Market Cap",
        height=500,
        margin=dict(t=60, b=20, l=20, r=20),
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
