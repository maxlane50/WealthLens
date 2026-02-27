"""yfinance wrappers with Streamlit caching."""

from __future__ import annotations

import streamlit as st
import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional

CACHE_TTL = 900  # 15 minutes

# Fidelity symbol -> yfinance symbol mapping
TICKER_MAP = {
    "BRKB": "BRK-B",
}


def _yf_ticker(ticker: str) -> str:
    """Convert Fidelity ticker to yfinance ticker."""
    return TICKER_MAP.get(ticker, ticker)


@st.cache_data(ttl=CACHE_TTL)
def get_info(ticker: str) -> Dict:
    """
    Fetch ticker fundamentals: sector, market cap, beta, dividend yield, quoteType.
    Returns empty dict on failure.
    """
    try:
        t = yf.Ticker(_yf_ticker(ticker))
        info = t.info or {}
        return {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "quote_type": info.get("quoteType"),
            "short_name": info.get("shortName"),
            "category": info.get("category"),
        }
    except Exception:
        return {}


@st.cache_data(ttl=CACHE_TTL)
def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch historical OHLCV prices. Returns empty DataFrame on failure."""
    try:
        t = yf.Ticker(_yf_ticker(ticker))
        hist = t.history(period=period)
        return hist if hist is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def get_dividends(ticker: str) -> pd.Series:
    """Fetch historical dividend payments. Returns empty Series on failure."""
    try:
        t = yf.Ticker(_yf_ticker(ticker))
        divs = t.dividends
        return divs if divs is not None else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=CACHE_TTL)
def get_bulk_history(tickers: tuple, period: str = "1y") -> pd.DataFrame:
    """
    Fetch closing prices for multiple tickers. Returns DataFrame with
    tickers as columns and dates as index. Uses tuple for tickers
    so Streamlit can hash the argument.
    """
    try:
        yf_tickers = [_yf_ticker(t) for t in tickers]
        data = yf.download(yf_tickers, period=period, progress=False)
        if data.empty:
            return pd.DataFrame()
        # yf.download returns multi-level columns; extract Close prices
        if isinstance(data.columns, pd.MultiIndex):
            closes = data["Close"]
        else:
            closes = data[["Close"]]
            closes.columns = [tickers[0]]
        return closes
    except Exception:
        return pd.DataFrame()


def get_info_for_tickers(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch info for multiple tickers, skipping failures."""
    results = {}
    for ticker in tickers:
        info = get_info(ticker)
        results[ticker] = info
    return results
