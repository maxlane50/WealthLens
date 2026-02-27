"""Parse Fidelity portfolio positions CSV exports."""

from __future__ import annotations

import pandas as pd
import re
from pathlib import Path
from typing import Optional


# Fidelity CSV column name -> internal name mapping
COLUMN_MAP = {
    "Account Number": "account_number",
    "Account Name": "account_name",
    "Symbol": "symbol",
    "Description": "description",
    "Quantity": "quantity",
    "Last Price": "last_price",
    "Last Price Change": "last_price_change",
    "Current Value": "current_value",
    "Today's Gain/Loss Dollar": "todays_gain_loss_dollar",
    "Today's Gain/Loss Percent": "todays_gain_loss_pct",
    "Total Gain/Loss Dollar": "total_gain_loss_dollar",
    "Total Gain/Loss Percent": "total_gain_loss_pct",
    "Percent Of Account": "pct_of_account",
    "Cost Basis Total": "cost_basis",
    "Average Cost Basis": "avg_cost_basis",
    "Type": "type",
}

# Columns that should be parsed as floats
NUMERIC_COLUMNS = [
    "quantity",
    "last_price",
    "last_price_change",
    "current_value",
    "todays_gain_loss_dollar",
    "todays_gain_loss_pct",
    "total_gain_loss_dollar",
    "total_gain_loss_pct",
    "pct_of_account",
    "cost_basis",
    "avg_cost_basis",
]


def _clean_numeric(value):
    """Strip $, +, %, commas from a value and convert to float."""
    if pd.isna(value) or value == "":
        return None
    s = str(value).strip()
    s = re.sub(r"[$+,%]", "", s)
    s = s.strip()
    if s == "" or s == "--":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_fidelity_csv(filepath: str | Path) -> pd.DataFrame:
    """
    Parse a Fidelity positions CSV export into a clean DataFrame.

    Handles:
    - Column renaming to internal schema
    - Stripping $, +, %, commas from numeric fields
    - Money market detection (SPAXX**, FDRXX**)
    - Disclaimer footer removal
    - Empty/blank rows
    """
    filepath = Path(filepath)

    # Read all lines, stop at first blank line to exclude disclaimer footer
    lines = filepath.read_text().splitlines()
    data_lines = []
    for line in lines:
        if line.strip() == "":
            break
        data_lines.append(line)

    if len(data_lines) < 2:
        raise ValueError(f"No data found in {filepath}")

    # Parse from the filtered lines
    from io import StringIO
    # Strip trailing commas from each line (Fidelity adds them) and remove BOM
    cleaned_lines = [line.rstrip(",").lstrip("\ufeff") for line in data_lines]
    csv_text = "\n".join(cleaned_lines)
    df = pd.read_csv(StringIO(csv_text))

    # Rename columns to internal schema
    df = df.rename(columns=COLUMN_MAP)

    # Drop any columns not in our mapping (e.g. trailing empty columns from commas)
    known_cols = list(COLUMN_MAP.values())
    df = df[[c for c in df.columns if c in known_cols]]

    # Clean money market symbols: strip ** suffix
    df["symbol"] = df["symbol"].astype(str).str.replace(r"\*+$", "", regex=True)

    # Detect money market / cash positions
    df["description"] = df["description"].astype(str)
    df["is_cash"] = df["description"].str.contains("MONEY MARKET", case=False, na=False)

    # Clean numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(_clean_numeric)

    # Drop rows where symbol is empty/nan (shouldn't happen but just in case)
    df = df.dropna(subset=["symbol"])
    df = df[df["symbol"].str.strip() != ""]

    # Fill missing current_value for safety
    df["current_value"] = df["current_value"].fillna(0.0)

    df = df.reset_index(drop=True)
    return df


def find_csv_in_directory(directory: str | Path) -> Optional[Path]:
    """Find the first Fidelity portfolio CSV in a directory."""
    directory = Path(directory)
    candidates = sorted(directory.glob("Portfolio_Positions_*.csv"), reverse=True)
    if candidates:
        return candidates[0]
    # Fallback: any CSV file
    csvs = sorted(directory.glob("*.csv"), reverse=True)
    for csv in csvs:
        try:
            first_line = csv.read_text().splitlines()[0]
            if "Account Number" in first_line and "Symbol" in first_line:
                return csv
        except Exception:
            continue
    return None
