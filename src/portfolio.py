"""Portfolio-level calculations."""

from __future__ import annotations

import pandas as pd
import numpy as np
from src.market_data import get_bulk_history, get_history


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


def portfolio_risk_metrics(
    tickers: list[str],
    weights: list[float],
) -> dict:
    """
    Compute portfolio beta, annualized volatility, and Sharpe ratio.
    Uses 1Y of daily returns.
    """
    all_tickers = list(set(tickers + ["SPY"]))
    closes = get_bulk_history(tuple(sorted(all_tickers)), period="1y")

    if closes.empty:
        return {}

    # Build weight map
    weight_map = {}
    for t, w in zip(tickers, weights):
        if t in closes.columns:
            weight_map[t] = weight_map.get(t, 0.0) + w

    if not weight_map:
        return {}

    total_w = sum(weight_map.values())
    for t in weight_map:
        weight_map[t] /= total_w

    portfolio_tickers = list(weight_map.keys())
    base_weights = np.array([weight_map[t] for t in portfolio_tickers])

    # Daily returns, drop rows where any portfolio ticker is missing
    daily_returns = closes.pct_change().iloc[1:]
    # Only use dates where all portfolio tickers + SPY have data
    needed = portfolio_tickers + (["SPY"] if "SPY" in daily_returns.columns else [])
    daily_returns = daily_returns.dropna(subset=needed)

    if len(daily_returns) < 30:
        return {}

    # Weighted portfolio daily returns
    portfolio_daily = (daily_returns[portfolio_tickers] * base_weights).sum(axis=1)
    spy_daily = daily_returns["SPY"] if "SPY" in daily_returns.columns else None

    # Annualized volatility
    ann_volatility = round(portfolio_daily.std() * np.sqrt(252) * 100, 2)

    # Beta vs S&P 500
    beta = None
    if spy_daily is not None:
        cov = portfolio_daily.cov(spy_daily)
        var = spy_daily.var()
        if var > 0:
            beta = round(cov / var, 2)

    # Sharpe ratio (using 10Y Treasury yield as risk-free rate)
    risk_free_annual = 0.04  # ~4% fallback
    try:
        tnx = get_history("^TNX", period="5d")
        if not tnx.empty:
            risk_free_annual = tnx["Close"].iloc[-1] / 100
    except Exception:
        pass

    ann_return = portfolio_daily.mean() * 252
    sharpe = None
    if ann_volatility > 0:
        sharpe = round((ann_return - risk_free_annual) / (ann_volatility / 100), 2)

    return {
        "beta": beta,
        "annualized_volatility": ann_volatility,
        "sharpe_ratio": sharpe,
        "risk_free_rate": round(risk_free_annual * 100, 2),
    }


def correlation_matrix(tickers: list[str]) -> pd.DataFrame:
    """
    Compute pairwise return correlations for the given tickers over 1Y.
    Returns a square DataFrame of correlation values, rounded to 2 decimals.
    Tickers with insufficient data are excluded.
    """
    closes = get_bulk_history(tuple(sorted(tickers)), period="1y")

    if closes.empty:
        return pd.DataFrame()

    # Only keep tickers that have at least 60 days of data
    valid_tickers = [t for t in tickers if t in closes.columns and closes[t].notna().sum() >= 60]
    if len(valid_tickers) < 2:
        return pd.DataFrame()

    daily_returns = closes[valid_tickers].pct_change().iloc[1:]
    corr = daily_returns.corr().round(2)

    return corr
