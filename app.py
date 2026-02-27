"""WealthLens — Personal Portfolio Dashboard."""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.parser import parse_fidelity_csv, find_csv_in_directory
from src.market_data import get_info_for_tickers
from src.charts import sector_allocation_chart, asset_class_chart

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
tab_overview, tab_allocation = st.tabs(["Overview", "Allocation"])

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

# ==================== TAB 2: ALLOCATION ====================
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
