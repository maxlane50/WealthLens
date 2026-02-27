"""WealthLens — Personal Portfolio Dashboard."""

import streamlit as st
from pathlib import Path
from src.parser import parse_fidelity_csv, find_csv_in_directory

st.set_page_config(
    page_title="WealthLens",
    page_icon="📊",
    layout="wide",
)

# --- Sidebar ---
with st.sidebar:
    st.title("WealthLens")

    # File upload or auto-detect
    uploaded_file = st.file_uploader("Upload Fidelity CSV", type=["csv"])

    if uploaded_file is not None:
        # Save uploaded file temporarily and parse
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        tmp.write(uploaded_file.getvalue())
        tmp.close()
        csv_path = tmp.name
    else:
        # Auto-detect CSV in project directory
        found = find_csv_in_directory(Path(__file__).parent)
        if found:
            csv_path = str(found)
            st.caption(f"Loaded: {found.name}")
        else:
            csv_path = None

    st.divider()
    st.caption("Step 1: CSV Parser")

# --- Main Content ---
if csv_path is None:
    st.warning("No portfolio CSV found. Upload a Fidelity positions export using the sidebar.")
    st.stop()

try:
    df = parse_fidelity_csv(csv_path)
except Exception as e:
    st.error(f"Failed to parse CSV: {e}")
    st.stop()

# Clean up temp file if we created one
if uploaded_file is not None:
    import os
    os.unlink(csv_path)

# Account filter
accounts = df["account_name"].unique().tolist()
with st.sidebar:
    selected_accounts = st.multiselect(
        "Filter by Account",
        options=accounts,
        default=accounts,
    )

df_filtered = df[df["account_name"].isin(selected_accounts)]

# Display parsed data
st.header("Parsed Portfolio Data")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Positions", len(df_filtered))
with col2:
    st.metric("Accounts", len(df_filtered["account_name"].unique()))
with col3:
    total_value = df_filtered["current_value"].sum()
    st.metric("Total Value", f"${total_value:,.2f}")

st.divider()

# Display columns we care about in a clean table
display_cols = [
    "account_name",
    "symbol",
    "description",
    "quantity",
    "last_price",
    "current_value",
    "cost_basis",
    "total_gain_loss_dollar",
    "total_gain_loss_pct",
    "is_cash",
]
display_cols = [c for c in display_cols if c in df_filtered.columns]

st.dataframe(
    df_filtered[display_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "account_name": st.column_config.TextColumn("Account"),
        "symbol": st.column_config.TextColumn("Symbol"),
        "description": st.column_config.TextColumn("Description"),
        "quantity": st.column_config.NumberColumn("Shares", format="%.3f"),
        "last_price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "current_value": st.column_config.NumberColumn("Value", format="$%.2f"),
        "cost_basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
        "total_gain_loss_dollar": st.column_config.NumberColumn("Gain/Loss $", format="$%.2f"),
        "total_gain_loss_pct": st.column_config.NumberColumn("Gain/Loss %", format="%.2f%%"),
        "is_cash": st.column_config.CheckboxColumn("Cash?"),
    },
)
