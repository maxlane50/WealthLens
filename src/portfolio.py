"""Portfolio-level calculations."""

from __future__ import annotations

import pandas as pd
import numpy as np
from src.market_data import get_bulk_history


def portfolio_cumulative_returns(
    tickers: list[str],
    weights: list[float],
    period: str = "1y",
) -> pd.DataFrame:
    """
    Compute cumulative returns for a weighted portfolio vs. SPY benchmark.
    Returns DataFrame with columns: Portfolio, SPY (both normalized to 100).
    Re-weights around tickers that don't have data yet on a given day.
    """
    all_tickers = list(set(tickers + ["SPY"]))
    closes = get_bulk_history(tuple(sorted(all_tickers)), period=period)

    if closes.empty:
        return pd.DataFrame()

    # Build weight map (only for tickers with price data)
    weight_map = {}
    for t, w in zip(tickers, weights):
        if t in closes.columns:
            weight_map[t] = weight_map.get(t, 0.0) + w

    if not weight_map:
        return pd.DataFrame()

    total_w = sum(weight_map.values())
    for t in weight_map:
        weight_map[t] /= total_w

    portfolio_tickers = list(weight_map.keys())
    base_weights = np.array([weight_map[t] for t in portfolio_tickers])

    # Start from the earliest date where at least half the portfolio weight has data
    first_valid = closes[portfolio_tickers].apply(lambda col: col.first_valid_index())
    earliest = first_valid.min()
    closes = closes.loc[earliest:]

    # Daily returns
    daily_returns = closes.pct_change().iloc[1:]
    returns_matrix = daily_returns[portfolio_tickers]

    # Re-weight each day: normalize weights to only include tickers with data
    valid = returns_matrix.notna()
    adjusted_weights = valid.multiply(base_weights, axis=1)
    weight_sums = adjusted_weights.sum(axis=1)
    adjusted_weights = adjusted_weights.div(weight_sums, axis=0)

    portfolio_daily = (returns_matrix.fillna(0) * adjusted_weights).sum(axis=1)

    # Cumulative returns normalized to 100
    result = pd.DataFrame(index=daily_returns.index)
    result["Portfolio"] = (1 + portfolio_daily).cumprod() * 100
    if "SPY" in daily_returns.columns:
        spy_returns = daily_returns["SPY"].fillna(0)
        result["SPY"] = (1 + spy_returns).cumprod() * 100

    # Force clean rounding
    result = result.round(2).astype(float)

    return result
