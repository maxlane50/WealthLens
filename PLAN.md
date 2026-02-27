# WealthLens — Architecture & Implementation Plan

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | Streamlit |
| Charts | Plotly (via `plotly.express` and `plotly.graph_objects`) |
| Market Data | yfinance |
| Data Processing | pandas, numpy |
| Styling | Streamlit dark theme + custom CSS |
| Python | 3.10+ |

## File Structure

```
WealthLens/
├── app.py                                  # Streamlit entry point, page layout, sidebar, tab routing
├── Portfolio_Positions_Feb-26-2026.csv     # Real Fidelity CSV export (gitignored)
├── src/
│   ├── __init__.py
│   ├── parser.py                           # CSV parsing & normalization for Fidelity exports
│   ├── market_data.py                      # yfinance wrappers with st.cache_data (1hr TTL)
│   ├── portfolio.py                        # Portfolio-level calculations (returns, beta, volatility)
│   └── charts.py                           # All Plotly chart builders (one function per viz)
├── requirements.txt
├── .streamlit/
│   └── config.toml                         # Dark theme config
├── .gitignore                              # Ignore CSV files (contain sensitive financial data)
├── PLAN.md
└── README.md
```

## Fidelity CSV Parsing (`src/parser.py`)

Fidelity's "Positions" CSV export has these exact columns (verified from real export):
- `Account Number` — e.g. "Z21851826", "239653506", "86131", "245362956"
- `Account Name` — e.g. "Individual - TOD", "ROTH IRA", "WOLVERINE", "Health Savings Account"
- `Symbol` — ticker symbol (note: money market funds have `**` suffix, e.g. "SPAXX**", "FDRXX**")
- `Description` — full holding name
- `Quantity` — shares held (empty for money market positions)
- `Last Price` — current price, formatted as "$689.30" (empty for money market)
- `Last Price Change` — today's price change, e.g. "-$3.85" or "+$2.53" (empty for money market)
- `Current Value` — market value, formatted as "$42065.22" (always present, even for money market)
- `Today's Gain/Loss Dollar` — e.g. "-$234.96" (empty for money market)
- `Today's Gain/Loss Percent` — e.g. "-0.56%" (empty for money market)
- `Total Gain/Loss Dollar` — e.g. "+$11544.64" (empty for money market)
- `Total Gain/Loss Percent` — e.g. "+37.82%" (empty for money market)
- `Percent Of Account` — e.g. "22.98%"
- `Cost Basis Total` — formatted as "$30520.58" (empty for money market)
- `Average Cost Basis` — per-share cost, formatted as "$500.12" (empty for money market)
- `Type` — "Cash" for most rows (refers to settlement type, NOT asset class); blank for some accounts

**Key data notes:**
- Fidelity already provides today's gain/loss and total gain/loss — no need to recompute these from yfinance for the Overview tab
- The CSV contains a legal disclaimer footer (lines starting with quotes after the data) that must be stripped
- There are 4 accounts in the real data: Individual brokerage (TOD), Roth IRA, employer plan, and HSA
- Tickers include Fidelity zero-fee funds (FZROX, FZILX) and mutual funds (VFIAX, FSPTX) — these may have limited or no yfinance data for sector/market cap; handle gracefully
- Money market rows (SPAXX**, FDRXX**) have no quantity, price, or gain/loss — treat as cash positions
- Trailing commas after each data row are normal Fidelity formatting

The parser will:
1. Read the CSV, stopping at the first blank row (to exclude the disclaimer footer)
2. Normalize column names to a standard schema: `account_number`, `account_name`, `symbol`, `description`, `quantity`, `last_price`, `last_price_change`, `current_value`, `todays_gain_loss_dollar`, `todays_gain_loss_pct`, `total_gain_loss_dollar`, `total_gain_loss_pct`, `pct_of_account`, `cost_basis`, `avg_cost_basis`, `type`
3. Strip dollar signs (`$`), plus signs (`+`), percent signs (`%`), commas, and whitespace from numeric fields; convert to float
4. Clean the `**` suffix from money market ticker symbols
5. Tag money market positions (`is_cash = True`) so they can be included in totals but excluded from yfinance lookups
6. Return a clean `pd.DataFrame` ready for analysis

## Market Data Layer (`src/market_data.py`)

All yfinance calls wrapped with `@st.cache_data(ttl=3600)`:

| Function | Purpose |
|----------|---------|
| `get_history(ticker, period)` | Historical OHLCV prices |
| `get_info(ticker)` | Fundamentals: sector, market cap, beta, dividend yield |
| `get_dividends(ticker)` | Historical dividend payments |
| `get_bulk_history(tickers, period)` | Batch fetch for correlation/benchmark calcs |

Graceful fallbacks: if a ticker lookup fails (delisted, money market, etc.), log a warning and exclude it from enriched views rather than crashing.

## Portfolio Calculations (`src/portfolio.py`)

| Calculation | Method |
|-------------|--------|
| Total value | Sum of `current_value` across all positions (from CSV) |
| Total gain/loss | Sum of `total_gain_loss_dollar` across all positions (from CSV — already provided by Fidelity) |
| Today's change | Sum of `todays_gain_loss_dollar` across all positions (from CSV — already provided by Fidelity) |
| Portfolio daily returns | Weighted sum of individual daily returns (via yfinance history) |
| Portfolio vs. SPY | Normalize both to day-1 = 100, plot over selected range |
| Portfolio beta | `cov(portfolio_returns, spy_returns) / var(spy_returns)` over 1Y |
| Annualized volatility | `std(daily_returns) × sqrt(252)` |
| Correlation matrix | Pairwise correlation of daily returns over 1Y |
| Projected dividends | `dividend_yield × current_value` per position |

**Note on yfinance coverage:** Fidelity zero-fee funds (FZROX, FZILX) and some mutual funds (VFIAX, FSPTX) may not return sector or market cap data from yfinance. For these, we will:
- Attempt lookup; if it fails, mark sector as "Unknown" and exclude from sector/cap charts
- Still include them in portfolio totals and the overview table (since the CSV provides all needed values)
- For benchmark/returns calculations, use available price history where possible

## Dashboard Tabs (in `app.py`, each calling functions from `src/charts.py`)

### Tab 1: Overview
- KPI cards row: Total Value, Total Gain/Loss ($), Total Gain/Loss (%), Today's Change — all derived directly from CSV columns (no yfinance needed)
- Summary table of all positions with columns: Symbol, Name, Account, Shares, Avg Cost, Current Price, Market Value, Gain/Loss ($), Gain/Loss (%), Weight (%)
- Sortable, color-coded (green/red for gain/loss)
- Money market positions (SPAXX, FDRXX) shown as cash with their current value but no gain/loss

### Tab 2: Portfolio vs. Benchmark
- Line chart: portfolio cumulative return vs. SPY cumulative return
- Date range selector buttons: 1M, 3M, 6M, YTD, 1Y, All
- Uses portfolio weights at start of period to compute weighted returns

### Tab 3: Allocation
- Two donut charts side by side:
  - **Sector allocation** — pulled from `yfinance.info['sector']` per ticker, weighted by current value. ETFs (SPY, VOO, QQQM, etc.) will be labeled by their primary category (e.g. "Broad Market", "Sector ETF") since they don't have a single sector. Fidelity funds with no yfinance sector data grouped as "Unknown".
  - **Asset class breakdown** — Stocks vs. ETFs vs. Mutual Funds vs. Cash, inferred from yfinance `quoteType` field (EQUITY, ETF, MUTUALFUND) and money market detection from the CSV

### Tab 4: Position Performance
- Horizontal bar chart: each holding's total return %, sorted best → worst, color-coded green/red
- Waterfall chart: cost basis → current value showing which positions contributed most to gains/losses

### Tab 5: Concentration & Risk
- Horizontal bar chart: top 10 holdings by portfolio weight %
- KPI cards: Portfolio Beta, Annualized Volatility, Sharpe Ratio (using risk-free rate from ^TNX)
- Brief risk summary

### Tab 6: Correlation Heatmap
- Heatmap of pairwise return correlations (1Y daily returns)
- Color scale: red (negative) → white (zero) → green (positive)
- Annotations with correlation values

### Tab 7: Dividends
- Bar chart: projected annual dividend income by position
- Table: historical dividends received (shares held × dividend per share for each ex-date in the holding period)
- KPI: total projected annual income, portfolio yield %

### Tab 8: Market Cap Breakdown
- Donut chart: Large Cap (>$10B) / Mid Cap ($2B–$10B) / Small Cap (<$2B) by portfolio weight
- Treemap: each holding sized by portfolio weight, grouped by cap bucket — so you can see exactly which stocks drive your small/mid cap exposure

## Sidebar

- **File uploader**: upload a Fidelity positions CSV (defaults to looking for any `*.csv` in project root matching Fidelity format)
- **Refresh Data** button: clears `st.cache_data` and reruns
- **Last Updated** timestamp: stored in `st.session_state`
- **Account filter**: multi-select to filter by account name (e.g. "Individual - TOD", "ROTH IRA", "WOLVERINE", "Health Savings Account")

## Styling (`.streamlit/config.toml` + inline CSS)

```toml
[theme]
base = "dark"
primaryColor = "#4CAF50"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1A1D23"
textColor = "#FAFAFA"
```

Plotly charts will use `plotly_dark` template with consistent color palette.

## Portfolio CSV

A real Fidelity export (`Portfolio_Positions_Feb-26-2026.csv`) is already present in the project root. The CSV will be gitignored since it contains sensitive financial data. The app will auto-detect any Fidelity-format CSV in the project root, or the user can upload one via the sidebar.

## Implementation Phases

### Phase 1: Foundation
- `requirements.txt`, `.streamlit/config.toml`, `.gitignore`, project structure
- `src/parser.py` — Fidelity CSV parser (tested against real export)
- `src/market_data.py` — yfinance wrappers with caching
- `app.py` — basic Streamlit skeleton with sidebar and file loading

### Phase 2: Core Dashboard
- Tab 1: Overview (KPIs + summary table)
- Tab 3: Allocation (sector + asset class donuts)
- Tab 4: Position Performance (bar chart + waterfall)

### Phase 3: Analytics
- `src/portfolio.py` — returns, beta, volatility calculations
- Tab 2: Portfolio vs. Benchmark
- Tab 5: Concentration & Risk
- Tab 6: Correlation Heatmap

### Phase 4: Income & Cap Analysis
- Tab 7: Dividends
- Tab 8: Market Cap Breakdown (donut + treemap)

### Phase 5: Polish
- Error handling edge cases
- Loading spinners for data fetches
- Final styling pass
- README with setup instructions

## Dependencies (`requirements.txt`)

```
streamlit>=1.30.0
yfinance>=0.2.30
plotly>=5.18.0
pandas>=2.0.0
numpy>=1.24.0
```

## Follow-Up Items

### Trade History Import for Accurate Benchmark
- Fidelity only allows exporting 365 days of trade history at a time
- Investigate: allow uploading multiple trade history CSVs (one per year) to get 3-4 years of coverage
- Parse buy/sell dates, quantities, and tickers from trade history exports
- Use actual purchase dates to build a time-accurate portfolio weight history (instead of assuming current weights held forever)
- This would make the Portfolio vs. Benchmark chart reflect real returns, not just a hypothetical backtest
- Current workaround: benchmark tab capped at 1Y with a disclaimer that it uses current weights

### UI/UX & Visual Polish
- Explore advanced color schemes and gradients for charts (beyond default Plotly palettes)
- Investigate custom CSS styling for KPI cards, tables, and layout
- Look into animated transitions, sparklines, or mini-charts in the overview table
- Consider a more polished color system — e.g. consistent green/red tones across all tabs, subtle accent colors
- Explore Streamlit theming options and custom components for a more "app-like" feel
