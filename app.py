"""WealthLens — Personal Portfolio Dashboard."""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.parser import parse_fidelity_csv, find_csv_in_directory
from src.market_data import get_info_for_tickers, get_info, get_dividends
from src.portfolio import portfolio_cumulative_returns, portfolio_risk_metrics, correlation_matrix
from src.charts import (
    sector_allocation_chart, asset_class_chart,
    performance_bar_chart, waterfall_chart,
    benchmark_chart, concentration_chart,
    correlation_heatmap, dividend_bar_chart,
    dividend_timeline_chart, market_cap_donut,
    market_cap_treemap,
)

st.set_page_config(
    page_title="WealthLens",
    page_icon="📊",
    layout="wide",
)

# --- Sidebar ---
with st.sidebar:
    st.title("WealthLens")

    uploaded_file = st.file_uploader("Upload Fidelity CSV", type=["csv"])

    if uploaded_file is not None:
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        tmp.write(uploaded_file.getvalue())
        tmp.close()
        csv_path = tmp.name
    else:
        found = find_csv_in_directory(Path(__file__).parent)
        if found:
            csv_path = str(found)
            st.caption(f"Loaded: {found.name}")
        else:
            csv_path = None

if csv_path is None:
    st.warning("No portfolio CSV found. Upload a Fidelity positions export using the sidebar.")
    st.stop()

try:
    df = parse_fidelity_csv(csv_path)
except Exception as e:
    st.error(f"Failed to parse CSV: {e}")
    st.stop()

if uploaded_file is not None:
    os.unlink(csv_path)

# Account filter + sidebar controls
accounts = df["account_name"].unique().tolist()
with st.sidebar:
    selected_accounts = st.multiselect(
        "Filter by Account",
        options=accounts,
        default=accounts,
    )
    st.divider()
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    if "last_updated" not in st.session_state:
        st.session_state["last_updated"] = datetime.now()
    st.caption(f"Last updated: {st.session_state['last_updated'].strftime('%b %d, %Y %I:%M %p')}")

df_filtered = df[df["account_name"].isin(selected_accounts)]
total_value = df_filtered["current_value"].sum()

# --- Tabs ---
tab_overview, tab_benchmark, tab_allocation, tab_performance, tab_risk, tab_corr, tab_divs, tab_cap = st.tabs([
    "Overview", "Portfolio vs. Benchmark", "Allocation", "Performance",
    "Concentration & Risk", "Correlation", "Dividends", "Market Cap",
])

# ==================== TAB 1: OVERVIEW ====================
with tab_overview:
    # KPI calculations
    total_gain = df_filtered["total_gain_loss_dollar"].sum()
    total_cost = df_filtered["cost_basis"].sum()
    total_gain_pct = (total_gain / total_cost * 100) if total_cost else 0.0
    todays_change = df_filtered["todays_gain_loss_dollar"].sum()
    todays_change_pct = (todays_change / (total_value - todays_change) * 100) if total_value else 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Value", f"${total_value:,.2f}")
    with col2:
        st.metric("Total Gain/Loss", f"${total_gain:,.2f}", delta=f"{total_gain_pct:+.2f}%")
    with col3:
        st.metric("Today's Change", f"${todays_change:,.2f}", delta=f"{todays_change_pct:+.2f}%")
    with col4:
        non_cash = df_filtered[~df_filtered["is_cash"]]
        st.metric("Positions", len(non_cash))

    st.divider()

    # Summary table
    non_cash = df_filtered[~df_filtered["is_cash"]].copy()
    non_cash["weight"] = non_cash["current_value"] / total_value * 100

    display = non_cash[[
        "symbol", "description", "account_name", "quantity",
        "avg_cost_basis", "last_price", "current_value",
        "total_gain_loss_dollar", "total_gain_loss_pct", "weight",
    ]].sort_values("current_value", ascending=False)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "description": st.column_config.TextColumn("Name"),
            "account_name": st.column_config.TextColumn("Account"),
            "quantity": st.column_config.NumberColumn("Shares", format="%.3f"),
            "avg_cost_basis": st.column_config.NumberColumn("Avg Cost", format="$%.2f"),
            "last_price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "current_value": st.column_config.NumberColumn("Value", format="$%.2f"),
            "total_gain_loss_dollar": st.column_config.NumberColumn("Gain/Loss $", format="$%.2f"),
            "total_gain_loss_pct": st.column_config.NumberColumn("Gain/Loss %", format="%.2f%%"),
            "weight": st.column_config.NumberColumn("Weight %", format="%.2f%%"),
        },
    )

    cash_positions = df_filtered[df_filtered["is_cash"]]
    if not cash_positions.empty:
        cash_total = cash_positions["current_value"].sum()
        st.caption(f"Cash (money market): ${cash_total:,.2f}")

# ==================== TAB 2: PORTFOLIO VS. BENCHMARK ====================
with tab_benchmark:
    PERIODS = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "YTD": "ytd", "1Y": "1y"}
    st.caption("Uses current portfolio weights — not actual trade history. Best viewed at shorter time ranges.")
    cols = st.columns(len(PERIODS))
    selected_period = "1Y"
    for i, (label, _) in enumerate(PERIODS.items()):
        if cols[i].button(label, use_container_width=True, key=f"period_{label}"):
            selected_period = label

    period_code = PERIODS[selected_period]

    # Build ticker/weight lists from current portfolio
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()
    ticker_weights = non_cash_df.groupby("symbol")["current_value"].sum()
    tickers = ticker_weights.index.tolist()
    weights = ticker_weights.values.tolist()

    with st.spinner("Fetching historical prices..."):
        cumulative = portfolio_cumulative_returns(tickers, weights, period=period_code)

    if not cumulative.empty:
        st.plotly_chart(benchmark_chart(cumulative), use_container_width=True)

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        port_return = cumulative["Portfolio"].iloc[-1] - 100
        with col1:
            st.metric("Portfolio Return", f"{port_return:+.2f}%")
        if "SPY" in cumulative.columns:
            spy_return = cumulative["SPY"].iloc[-1] - 100
            with col2:
                st.metric("SPY Return", f"{spy_return:+.2f}%")
            with col3:
                diff = port_return - spy_return
                st.metric("vs. Benchmark", f"{diff:+.2f}%")
    else:
        st.warning("Not enough price data for the selected period.")

# ==================== TAB 3: ALLOCATION ====================
with tab_allocation:
    # Get unique non-cash tickers and fetch yfinance info
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()
    unique_tickers = non_cash_df["symbol"].unique().tolist()

    with st.spinner("Fetching market data..."):
        ticker_info = get_info_for_tickers(unique_tickers)

    # Aggregate value per unique ticker (same ticker may appear in multiple accounts)
    ticker_values = non_cash_df.groupby("symbol")["current_value"].sum()

    # --- Sector allocation ---
    sector_rows = []
    for ticker, value in ticker_values.items():
        info = ticker_info.get(ticker, {})
        sector = info.get("sector")
        quote_type = info.get("quote_type", "")

        if sector:
            sector_rows.append({"sector": sector, "value": value})
        elif quote_type == "ETF":
            sector_rows.append({"sector": "ETF", "value": value})
        elif quote_type == "MUTUALFUND":
            sector_rows.append({"sector": "Mutual Fund", "value": value})
        else:
            sector_rows.append({"sector": "Unknown", "value": value})

    # --- Asset class breakdown ---
    class_rows = []
    for ticker, value in ticker_values.items():
        info = ticker_info.get(ticker, {})
        quote_type = info.get("quote_type", "")

        if quote_type == "ETF":
            class_rows.append({"asset_class": "ETF", "value": value})
        elif quote_type == "MUTUALFUND":
            class_rows.append({"asset_class": "Mutual Fund", "value": value})
        elif quote_type == "EQUITY":
            class_rows.append({"asset_class": "Stock", "value": value})
        else:
            class_rows.append({"asset_class": "Other", "value": value})

    # Add cash positions
    cash_total = df_filtered[df_filtered["is_cash"]]["current_value"].sum()
    if cash_total > 0:
        sector_rows.append({"sector": "Cash", "value": cash_total})
        class_rows.append({"asset_class": "Cash", "value": cash_total})

    # Render charts side by side
    col_left, col_right = st.columns(2)
    with col_left:
        sector_df = pd.DataFrame(sector_rows)
        if not sector_df.empty:
            st.plotly_chart(sector_allocation_chart(sector_df), use_container_width=True)
    with col_right:
        class_df = pd.DataFrame(class_rows)
        if not class_df.empty:
            st.plotly_chart(asset_class_chart(class_df), use_container_width=True)

# ==================== TAB 4: PERFORMANCE ====================
with tab_performance:
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()

    # Aggregate by ticker across accounts
    perf = non_cash_df.groupby("symbol").agg(
        current_value=("current_value", "sum"),
        cost_basis=("cost_basis", "sum"),
        gain_loss_dollar=("total_gain_loss_dollar", "sum"),
    ).reset_index()
    perf["total_return_pct"] = (perf["gain_loss_dollar"] / perf["cost_basis"] * 100).fillna(0)

    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(performance_bar_chart(perf[["symbol", "total_return_pct"]]), use_container_width=True)
    with col_right:
        st.plotly_chart(waterfall_chart(perf[["symbol", "gain_loss_dollar"]]), use_container_width=True)

# ==================== TAB 5: CONCENTRATION & RISK ====================
with tab_risk:
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()

    # Aggregate by ticker across accounts for concentration
    conc = non_cash_df.groupby("symbol")["current_value"].sum().reset_index()
    conc["weight"] = conc["current_value"] / total_value * 100
    top10 = conc.nlargest(10, "weight")
    top10_pct = top10["weight"].sum()

    # Layout: chart on left, risk metrics on right
    col_chart, col_metrics = st.columns([3, 2])

    with col_chart:
        st.plotly_chart(concentration_chart(conc[["symbol", "weight"]]), use_container_width=True)

    with col_metrics:
        st.subheader("Risk Metrics")

        # Fetch risk metrics
        ticker_weights = non_cash_df.groupby("symbol")["current_value"].sum()
        tickers = ticker_weights.index.tolist()
        weights = ticker_weights.values.tolist()

        with st.spinner("Computing risk metrics..."):
            risk = portfolio_risk_metrics(tickers, weights)

        if risk:
            # Beta
            beta = risk.get("beta")
            if beta is not None:
                beta_color = "#4CAF50" if 0.8 <= beta <= 1.2 else "#FFA726" if beta < 1.5 else "#EF5350"
                st.markdown(
                    f"<div style='padding:12px; border-radius:8px; border-left:4px solid {beta_color}; "
                    f"background:rgba(255,255,255,0.03); margin-bottom:12px;'>"
                    f"<span style='color:#999; font-size:0.85em;'>Portfolio Beta</span><br>"
                    f"<span style='font-size:1.8em; font-weight:600; color:{beta_color};'>{beta}</span>"
                    f"<br><span style='color:#666; font-size:0.75em;'>vs. S&P 500 (1.0 = market)</span></div>",
                    unsafe_allow_html=True,
                )

            # Volatility
            vol = risk.get("annualized_volatility")
            if vol is not None:
                vol_color = "#4CAF50" if vol < 15 else "#FFA726" if vol < 25 else "#EF5350"
                st.markdown(
                    f"<div style='padding:12px; border-radius:8px; border-left:4px solid {vol_color}; "
                    f"background:rgba(255,255,255,0.03); margin-bottom:12px;'>"
                    f"<span style='color:#999; font-size:0.85em;'>Annualized Volatility</span><br>"
                    f"<span style='font-size:1.8em; font-weight:600; color:{vol_color};'>{vol}%</span>"
                    f"<br><span style='color:#666; font-size:0.75em;'>S&P 500 typically 15-20%</span></div>",
                    unsafe_allow_html=True,
                )

            # Sharpe
            sharpe = risk.get("sharpe_ratio")
            if sharpe is not None:
                sharpe_color = "#4CAF50" if sharpe > 1 else "#FFA726" if sharpe > 0.5 else "#EF5350"
                rfr = risk.get("risk_free_rate", 4.0)
                st.markdown(
                    f"<div style='padding:12px; border-radius:8px; border-left:4px solid {sharpe_color}; "
                    f"background:rgba(255,255,255,0.03); margin-bottom:12px;'>"
                    f"<span style='color:#999; font-size:0.85em;'>Sharpe Ratio</span><br>"
                    f"<span style='font-size:1.8em; font-weight:600; color:{sharpe_color};'>{sharpe}</span>"
                    f"<br><span style='color:#666; font-size:0.75em;'>Risk-free rate: {rfr}% | >1.0 is good</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.warning("Not enough data to compute risk metrics.")

    # Concentration summary
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Top 10 Concentration", f"{top10_pct:.1f}%")
    with col2:
        largest = conc.nlargest(1, "weight").iloc[0]
        st.metric("Largest Position", f"{largest['symbol']} ({largest['weight']:.1f}%)")
    with col3:
        unique_count = len(conc)
        st.metric("Unique Holdings", unique_count)

# ==================== TAB 6: CORRELATION ====================
with tab_corr:
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()
    unique_tickers = sorted(non_cash_df["symbol"].unique().tolist())

    with st.spinner("Computing correlations..."):
        corr = correlation_matrix(unique_tickers)

    if not corr.empty:
        # Quick insight: find the most and least correlated pairs
        pairs = []
        tickers_list = corr.columns.tolist()
        for i in range(len(tickers_list)):
            for j in range(i + 1, len(tickers_list)):
                pairs.append({
                    "pair": f"{tickers_list[i]} / {tickers_list[j]}",
                    "correlation": corr.iloc[i, j],
                })
        pairs_df = pd.DataFrame(pairs).sort_values("correlation")

        # Insight cards
        if len(pairs_df) >= 2:
            lowest = pairs_df.iloc[0]
            highest = pairs_df.iloc[-1]

            col1, col2 = st.columns(2)
            with col1:
                val = lowest["correlation"]
                color = "#EF5350" if val < 0 else "#FFA726"
                st.markdown(
                    f"<div style='padding:14px; border-radius:8px; border-left:4px solid {color}; "
                    f"background:rgba(255,255,255,0.03);'>"
                    f"<span style='color:#999; font-size:0.85em;'>Least Correlated Pair</span><br>"
                    f"<span style='font-size:1.4em; font-weight:600; color:#FAFAFA;'>{lowest['pair']}</span>"
                    f"<br><span style='font-size:1.2em; color:{color};'>{val:.2f}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col2:
                val = highest["correlation"]
                color = "#4CAF50"
                st.markdown(
                    f"<div style='padding:14px; border-radius:8px; border-left:4px solid {color}; "
                    f"background:rgba(255,255,255,0.03);'>"
                    f"<span style='color:#999; font-size:0.85em;'>Most Correlated Pair</span><br>"
                    f"<span style='font-size:1.4em; font-weight:600; color:#FAFAFA;'>{highest['pair']}</span>"
                    f"<br><span style='font-size:1.2em; color:{color};'>{val:.2f}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.plotly_chart(correlation_heatmap(corr), use_container_width=True)

        # Diversification insight
        avg_corr = pairs_df["correlation"].mean()
        if avg_corr < 0.4:
            msg = "Your portfolio has good diversification — low average correlation between holdings."
            icon = "&#9989;"
        elif avg_corr < 0.7:
            msg = "Moderate correlation — your holdings move somewhat together. Consider adding uncorrelated assets."
            icon = "&#9888;&#65039;"
        else:
            msg = "High average correlation — your holdings are tightly coupled. Diversification is limited."
            icon = "&#128308;"

        st.markdown(
            f"<div style='padding:14px; border-radius:8px; background:rgba(255,255,255,0.03); "
            f"margin-top:8px; text-align:center;'>"
            f"<span style='font-size:1.1em;'>{icon} Avg. Correlation: <b>{avg_corr:.2f}</b> — {msg}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Not enough price data to compute correlations.")

# ==================== TAB 7: DIVIDENDS ====================
with tab_divs:
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()

    # Aggregate by ticker
    holdings = non_cash_df.groupby("symbol").agg(
        current_value=("current_value", "sum"),
        quantity=("quantity", "sum"),
    ).reset_index()

    # Fetch dividend info for each ticker
    with st.spinner("Fetching dividend data..."):
        div_rows = []
        timeline_data = []

        for _, row in holdings.iterrows():
            ticker = row["symbol"]
            value = row["current_value"]
            shares = row["quantity"]
            info = get_info(ticker)
            dy = info.get("dividend_yield") or 0.0

            # dividendYield from yfinance is already in % form (1.05 = 1.05%)
            annual_income = value * (dy / 100)
            div_rows.append({
                "symbol": ticker,
                "current_value": value,
                "shares": shares,
                "dividend_yield": dy,
                "annual_income": annual_income,
                "quarterly_income": annual_income / 4,
            })

            # Estimated historical: get actual dividend payments from yfinance
            if dy > 0:
                divs = get_dividends(ticker)
                if len(divs) > 0:
                    # Filter to last year
                    one_year_ago = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(years=1)
                    recent = divs[divs.index >= one_year_ago]
                    for date, amount in recent.items():
                        timeline_data.append({
                            "date": date,
                            "symbol": ticker,
                            "income": float(amount) * shares,
                        })

    div_df = pd.DataFrame(div_rows)
    payers = div_df[div_df["annual_income"] > 0].copy()
    total_annual = div_df["annual_income"].sum()
    portfolio_yield = (total_annual / total_value * 100) if total_value > 0 else 0

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"<div style='padding:14px; border-radius:8px; border-left:4px solid #4CAF50; "
            f"background:rgba(255,255,255,0.03);'>"
            f"<span style='color:#999; font-size:0.85em;'>Projected Annual Income</span><br>"
            f"<span style='font-size:1.8em; font-weight:600; color:#4CAF50;'>${total_annual:,.2f}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        monthly = total_annual / 12
        st.markdown(
            f"<div style='padding:14px; border-radius:8px; border-left:4px solid #42A5F5; "
            f"background:rgba(255,255,255,0.03);'>"
            f"<span style='color:#999; font-size:0.85em;'>Monthly (avg)</span><br>"
            f"<span style='font-size:1.8em; font-weight:600; color:#42A5F5;'>${monthly:,.2f}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"<div style='padding:14px; border-radius:8px; border-left:4px solid #FFA726; "
            f"background:rgba(255,255,255,0.03);'>"
            f"<span style='color:#999; font-size:0.85em;'>Portfolio Yield</span><br>"
            f"<span style='font-size:1.8em; font-weight:600; color:#FFA726;'>{portfolio_yield:.2f}%</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col4:
        num_payers = len(payers)
        num_total = len(div_df)
        st.markdown(
            f"<div style='padding:14px; border-radius:8px; border-left:4px solid #AB47BC; "
            f"background:rgba(255,255,255,0.03);'>"
            f"<span style='color:#999; font-size:0.85em;'>Dividend Payers</span><br>"
            f"<span style='font-size:1.8em; font-weight:600; color:#AB47BC;'>{num_payers}/{num_total}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    # Charts
    col_left, col_right = st.columns([3, 2])

    with col_left:
        if not payers.empty:
            st.plotly_chart(
                dividend_bar_chart(payers[["symbol", "annual_income", "dividend_yield"]].rename(
                    columns={"dividend_yield": "yield_pct"}
                )),
                use_container_width=True,
            )
        else:
            st.info("No dividend-paying holdings in your portfolio.")

    with col_right:
        # Projected quarterly breakdown table
        st.markdown("**Projected Income by Position**")
        if not payers.empty:
            table = payers[["symbol", "dividend_yield", "annual_income", "quarterly_income"]].sort_values(
                "annual_income", ascending=False
            )
            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "symbol": st.column_config.TextColumn("Symbol"),
                    "dividend_yield": st.column_config.NumberColumn("Yield %", format="%.2f%%"),
                    "annual_income": st.column_config.NumberColumn("Annual $", format="$%.2f"),
                    "quarterly_income": st.column_config.NumberColumn("Quarterly $", format="$%.2f"),
                },
            )

    # Estimated monthly timeline
    if timeline_data:
        tl_df = pd.DataFrame(timeline_data)
        tl_df["month"] = tl_df["date"].dt.to_period("M").dt.to_timestamp()
        monthly_income = tl_df.groupby("month")["income"].sum().reset_index()

        st.plotly_chart(dividend_timeline_chart(monthly_income), use_container_width=True)
        st.caption("Estimated based on current shares held x historical dividend payments. Actual income may differ.")

# ==================== TAB 8: MARKET CAP ====================
with tab_cap:
    non_cash_df = df_filtered[~df_filtered["is_cash"]].copy()
    unique_tickers = non_cash_df["symbol"].unique().tolist()

    with st.spinner("Fetching market cap data..."):
        ticker_info = get_info_for_tickers(unique_tickers)

    # Aggregate by ticker and classify
    ticker_values = non_cash_df.groupby("symbol")["current_value"].sum()

    def classify_cap(info):
        """Classify by category (ETFs/funds) or market cap (stocks)."""
        category = (info.get("category") or "").lower()
        quote_type = info.get("quote_type", "")

        # ETFs and mutual funds: use the fund category
        if quote_type in ("ETF", "MUTUALFUND") and category:
            if "small" in category:
                return "Small Cap"
            if "mid" in category:
                return "Mid Cap"
            if "large" in category:
                return "Large Cap"
            # Sector/thematic ETFs are typically large cap
            if category in ("technology", "health", "digital assets"):
                return "Large Cap"

        # Individual stocks: use market cap
        mc = info.get("market_cap")
        if mc is not None:
            if mc > 10e9:
                return "Large Cap"
            if mc > 2e9:
                return "Mid Cap"
            return "Small Cap"

        # Mutual funds without category: assume broad market (large cap)
        if quote_type == "MUTUALFUND":
            return "Large Cap"

        return "Unknown"

    cap_rows = []
    for ticker, value in ticker_values.items():
        info = ticker_info.get(ticker, {})
        bucket = classify_cap(info)
        cap_rows.append({
            "symbol": ticker,
            "cap_bucket": bucket,
            "value": value,
            "market_cap": info.get("market_cap"),
        })

    cap_df = pd.DataFrame(cap_rows)

    # KPI summary
    cap_summary = cap_df.groupby("cap_bucket")["value"].sum()
    cap_total = cap_summary.sum()

    cap_colors = {
        "Large Cap": "#42A5F5",
        "Mid Cap": "#FFA726",
        "Small Cap": "#EF5350",
        "Unknown": "#78909C",
    }
    cap_order = ["Large Cap", "Mid Cap", "Small Cap", "Unknown"]
    kpi_cols = st.columns(len([b for b in cap_order if b in cap_summary.index]))
    col_idx = 0
    for bucket in cap_order:
        if bucket in cap_summary.index:
            val = cap_summary[bucket]
            pct = val / cap_total * 100
            color = cap_colors[bucket]
            with kpi_cols[col_idx]:
                st.markdown(
                    f"<div style='padding:14px; border-radius:8px; border-left:4px solid {color}; "
                    f"background:rgba(255,255,255,0.03);'>"
                    f"<span style='color:#999; font-size:0.85em;'>{bucket}</span><br>"
                    f"<span style='font-size:1.6em; font-weight:600; color:{color};'>{pct:.1f}%</span>"
                    f"<br><span style='color:#666; font-size:0.75em;'>${val:,.0f}</span></div>",
                    unsafe_allow_html=True,
                )
            col_idx += 1

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    # Charts side by side
    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(market_cap_donut(cap_df[["cap_bucket", "value"]]), use_container_width=True)
    with col_right:
        # Treemap needs parent rows for each bucket
        treemap_df = cap_df[["symbol", "cap_bucket", "value"]].copy()
        st.plotly_chart(market_cap_treemap(treemap_df), use_container_width=True)
