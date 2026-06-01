"""
IS 445 - Defensive Assets Project
Data Extraction & Analysis Module

All analysis functions are designed to be GUI-friendly:
  - No input() calls inside analysis functions
  - Parameters passed explicitly
  - Functions return data structures (DataFrames, dicts) for the GUI to render
  - CLI main() handles all user prompts for terminal use
"""

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv, find_dotenv
from yfinance import download

load_dotenv(find_dotenv())

# ─────────────────────────────────────────────
# DB CONNECTION
# ─────────────────────────────────────────────

user     = os.getenv("user")
password = os.getenv("password")
server   = os.getenv("server")
database = os.getenv("database")

connection_string = f'mysql+pymysql://{user}:{password}@{server}/{database}'
engine = create_engine(connection_string)

DEFAULT_TICKERS = ["SPY", "QQQ", "TLT", "SGOV", "GLD", "USO", "XLE"]


# ─────────────────────────────────────────────
# SECTION 3 — DATA WORK
# ─────────────────────────────────────────────

def download_and_insert_tickers(tickers: list[str], start_date: str, end_date: str) -> dict:
    """
    Download daily price data from yfinance and insert into MySQL.
    Cleans: NaNs, duplicate ticker/date records, type coercion.

    Parameters
    ----------
    tickers    : list of ticker strings, e.g. ['SPY', 'TLT']
    start_date : 'YYYY-MM-DD'
    end_date   : 'YYYY-MM-DD'

    Returns
    -------
    dict with keys 'inserted', 'skipped', 'errors' (lists of ticker strings)
    """
    results = {"inserted": [], "skipped": [], "errors": []}

    print(f"Downloading data for {tickers} | {start_date} → {end_date}")
    try:
        data = download(tickers, start=start_date, end=end_date, auto_adjust=True)
    except Exception as e:
        print(f"✗ Download failed: {e}")
        results["errors"] = tickers
        return results

    # Insert ticker symbols
    for ticker in tickers:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO ticker_symbol (ticker_symbol) VALUES (:symbol)"),
                    {"symbol": ticker},
                )
        except Exception as e:
            if "duplicate" in str(e).lower():
                print(f"⚠  {ticker} already in ticker_symbol — skipping insert")
            else:
                print(f"✗ Error inserting {ticker}: {str(e)[:100]}")
                results["errors"].append(ticker)

    # Insert price rows
    for ticker in tickers:
        try:
            # Newer yfinance always returns MultiIndex columns (Price, Ticker)
            # even for a single-ticker download, so always access via [ticker].
            ticker_data = pd.DataFrame({
                "price_date": data.index,
                "open":       data["Open"][ticker].values,
                "close":      data["Close"][ticker].values,
                "high":       data["High"][ticker].values,
                "low":        data["Low"][ticker].values,
                "volume":     data["Volume"][ticker].values,
            })

            # ── Cleaning (Section 3.4) ──────────────────────────────
            ticker_data["price_date"] = pd.to_datetime(ticker_data["price_date"])
            ticker_data = ticker_data.dropna(subset=["open", "close", "high", "low"])
            ticker_data = ticker_data.drop_duplicates(subset=["price_date"])
            ticker_data["open"]   = ticker_data["open"].astype(float)
            ticker_data["close"]  = ticker_data["close"].astype(float)
            ticker_data["high"]   = ticker_data["high"].astype(float)
            ticker_data["low"]    = ticker_data["low"].astype(float)
            ticker_data["volume"] = ticker_data["volume"].astype("Int64")
            ticker_data.reset_index(drop=True, inplace=True)

            if ticker_data.empty:
                print(f"⚠  No valid rows for {ticker} after cleaning")
                results["skipped"].append(ticker)
                continue

            # Resolve ticker_id
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT ticker_id FROM ticker_symbol WHERE ticker_symbol = :s"),
                    {"s": ticker},
                ).fetchone()
                if row is None:
                    print(f"✗ {ticker} not found in ticker_symbol — skipping prices")
                    results["errors"].append(ticker)
                    continue
                ticker_id = row[0]

            ticker_data["ticker_id"] = ticker_id
            ticker_data = ticker_data[["ticker_id", "price_date", "open", "close", "high", "low", "volume"]]

            # Remove rows that already exist (duplicate guard)
            with engine.connect() as conn:
                existing = pd.read_sql_query(
                    text("SELECT price_date FROM stock_prices WHERE ticker_id = :tid"),
                    conn,
                    params={"tid": ticker_id},
                )
            existing_dates = set(pd.to_datetime(existing["price_date"]))
            ticker_data = ticker_data[~ticker_data["price_date"].isin(existing_dates)]

            if ticker_data.empty:
                print(f"⚠  All rows for {ticker} already exist — skipping")
                results["skipped"].append(ticker)
                continue

            ticker_data.to_sql("stock_prices", con=engine, if_exists="append", index=False)
            print(f"✓ Inserted {len(ticker_data)} rows for {ticker}")
            results["inserted"].append(ticker)

        except Exception as e:
            print(f"✗ Error processing {ticker}: {e}")
            import traceback; traceback.print_exc()
            results["errors"].append(ticker)

    return results


def reset_db() -> bool:
    """
    Clear all data from stock_prices and ticker_symbol tables.

    Returns
    -------
    True on success, False on failure
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM stock_prices"))
            conn.execute(text("DELETE FROM ticker_symbol"))
            conn.execute(text("ALTER TABLE ticker_symbol AUTO_INCREMENT = 1"))
        print("✓ Database reset successfully")
        return True
    except Exception as e:
        print(f"✗ Error resetting database: {e}")
        return False


def delete_ticker(ticker: str) -> bool:
    """
    Remove one ticker and all its price rows from the database.

    Returns True on success, False if ticker not found or on error.
    """
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT ticker_id FROM ticker_symbol WHERE ticker_symbol = :s"),
                {"s": ticker},
            ).fetchone()
            if row is None:
                print(f"⚠  {ticker} not found in database")
                return False
            ticker_id = row[0]
            conn.execute(text("DELETE FROM stock_prices  WHERE ticker_id = :tid"), {"tid": ticker_id})
            conn.execute(text("DELETE FROM ticker_symbol WHERE ticker_id = :tid"), {"tid": ticker_id})
        print(f"✓ Deleted {ticker} from database")
        return True
    except Exception as e:
        print(f"✗ Error deleting {ticker}: {e}")
        return False


def get_available_tickers() -> list[str]:
    """Return list of ticker symbols currently in the database."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT ticker_symbol FROM ticker_symbol ORDER BY ticker_symbol")
        ).fetchall()
    return [r[0] for r in rows]


# ─────────────────────────────────────────────
# SHARED HELPER — load returns from DB
# ─────────────────────────────────────────────

def load_returns_from_db(
    tickers: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
) -> pd.DataFrame:
    """
    Pull adjusted close prices from MySQL and return a DataFrame of
    daily percentage returns, one column per ticker.

    Parameters
    ----------
    tickers    : ticker symbols to include
    start_date : optional filter 'YYYY-MM-DD'
    end_date   : optional filter 'YYYY-MM-DD'

    Returns
    -------
    DataFrame indexed by price_date, columns = tickers, values = daily returns
    """
    ticker_list = ", ".join([f"'{t}'" for t in tickers])
    query = f"""
        SELECT sp.price_date, ts.ticker_symbol, sp.close
        FROM stock_prices sp
        JOIN ticker_symbol ts ON sp.ticker_id = ts.ticker_id
        WHERE ts.ticker_symbol IN ({ticker_list})
        ORDER BY sp.price_date
    """
    df = pd.read_sql_query(query, engine)
    df["price_date"] = pd.to_datetime(df["price_date"])

    if start_date:
        df = df[df["price_date"] >= start_date]
    if end_date:
        df = df[df["price_date"] <= end_date]

    prices = df.pivot_table(index="price_date", columns="ticker_symbol", values="close")
    returns = prices.pct_change().dropna(how="all")
    return returns


def load_prices_from_db(
    tickers: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
) -> pd.DataFrame:
    """Same as load_returns_from_db but returns raw close prices (not returns)."""
    ticker_list = ", ".join([f"'{t}'" for t in tickers])
    query = f"""
        SELECT sp.price_date, ts.ticker_symbol, sp.close
        FROM stock_prices sp
        JOIN ticker_symbol ts ON sp.ticker_id = ts.ticker_id
        WHERE ts.ticker_symbol IN ({ticker_list})
        ORDER BY sp.price_date
    """
    df = pd.read_sql_query(query, engine)
    df["price_date"] = pd.to_datetime(df["price_date"])

    if start_date:
        df = df[df["price_date"] >= start_date]
    if end_date:
        df = df[df["price_date"] <= end_date]

    prices = df.pivot_table(index="price_date", columns="ticker_symbol", values="close")
    return prices


# ─────────────────────────────────────────────
# SECTION 3.5 — DAILY RETURNS (utility)
# ─────────────────────────────────────────────

def calculate_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Given a prices DataFrame (dates × tickers), return daily pct returns.
    Kept as a standalone utility for GUI charting use.
    """
    return prices.pct_change().dropna(how="all")


# ─────────────────────────────────────────────
# SECTION 4 — BASIC PERFORMANCE TABLE
# ─────────────────────────────────────────────

def calculate_performance_table(
    tickers: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
    risk_free_rate: float = 0.05,
) -> pd.DataFrame:
    """
    Section 4: cumulative return, annualized volatility, max drawdown, Sharpe ratio.

    Parameters
    ----------
    tickers        : list of ticker symbols
    start_date     : optional date filter
    end_date       : optional date filter
    risk_free_rate : annual risk-free rate for Sharpe (default 5%)

    Returns
    -------
    DataFrame with one row per ticker and columns:
        Cumulative Return, Annualized Volatility, Max Drawdown, Sharpe Ratio
    """
    returns = load_returns_from_db(tickers, start_date, end_date)
    prices  = load_prices_from_db(tickers, start_date, end_date)

    records = []
    for ticker in tickers:
        if ticker not in returns.columns:
            print(f"⚠  {ticker} not found in DB — skipping")
            continue

        r = returns[ticker].dropna()
        p = prices[ticker].dropna()

        cumulative_return = (1 + r).prod() - 1
        ann_vol = r.std() * np.sqrt(252)

        roll_max = p.cummax()
        drawdown = (p - roll_max) / roll_max
        max_drawdown = drawdown.min()

        daily_rf = risk_free_rate / 252
        excess = r - daily_rf
        sharpe = (excess.mean() / r.std()) * np.sqrt(252) if r.std() > 0 else np.nan

        records.append({
            "Ticker":                ticker,
            "Cumulative Return":     round(cumulative_return, 4),
            "Annualized Volatility": round(ann_vol, 4),
            "Max Drawdown":          round(max_drawdown, 4),
            "Sharpe Ratio":          round(sharpe, 4),
        })

    result = pd.DataFrame(records).set_index("Ticker")
    return result


# ─────────────────────────────────────────────
# SECTION 5 — CORRELATION WITH SPY
# ─────────────────────────────────────────────

def calculate_spy_correlation(
    tickers: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
    benchmark: str = "SPY",
) -> pd.DataFrame:
    """
    Section 5: correlation of each ETF's daily returns with SPY (or chosen benchmark).
    Also returns the full returns correlation matrix for heatmap use.

    Parameters
    ----------
    tickers   : list of tickers (should include benchmark)
    benchmark : benchmark ticker, default 'SPY'

    Returns
    -------
    spy_corr  : Series — correlation of each ticker vs benchmark
    full_corr : full n×n correlation matrix (for heatmap)
    """
    all_tickers = list(set(tickers + [benchmark]))
    returns = load_returns_from_db(all_tickers, start_date, end_date)

    full_corr = returns.corr()

    if benchmark not in full_corr.columns:
        raise ValueError(f"Benchmark '{benchmark}' not found in data.")

    spy_corr = full_corr[benchmark].drop(labels=[benchmark]).sort_values()

    return spy_corr, full_corr


# ─────────────────────────────────────────────
# SECTION 6 — SPY STRESS-DAY TEST
# ─────────────────────────────────────────────

def run_stress_test(
    tickers: list[str],
    start_date:   str | None = None,
    end_date:     str | None = None,
    benchmark:    str   = "SPY",
    stress_pct:   float = 0.05,
) -> pd.DataFrame:
    """
    Section 6: identify worst N% of SPY days; measure each ETF's behavior on those days.

    Parameters
    ----------
    tickers     : list of ETF tickers (benchmark included automatically)
    benchmark   : benchmark ticker for stress definition, default 'SPY'
    stress_pct  : percentile threshold for stress days, default 0.05 (worst 5%)

    Returns
    -------
    DataFrame with one row per non-benchmark ticker and columns:
        Stress Days, Avg Return on SPY Stress Days, Hit Rate, Co-Crash Rate
    """
    all_tickers = list(set(tickers + [benchmark]))
    returns = load_returns_from_db(all_tickers, start_date, end_date)

    if benchmark not in returns.columns:
        raise ValueError(f"Benchmark '{benchmark}' not in loaded data.")

    threshold   = returns[benchmark].quantile(stress_pct)
    stress_mask = returns[benchmark] <= threshold
    stress_days = returns[stress_mask]

    n_stress = stress_mask.sum()
    print(f"\nSPY stress threshold (worst {stress_pct*100:.0f}%): {threshold:.4f}")
    print(f"Number of stress days: {n_stress}")

    records = []
    for ticker in tickers:
        if ticker == benchmark:
            continue
        if ticker not in returns.columns:
            print(f"⚠  {ticker} not in data — skipping")
            continue

        etf_on_stress = stress_days[ticker].dropna()
        n = len(etf_on_stress)

        avg_return    = etf_on_stress.mean()
        hit_rate      = (etf_on_stress > 0).sum() / n if n > 0 else np.nan
        co_crash_rate = (etf_on_stress < 0).sum() / n if n > 0 else np.nan

        records.append({
            "Ticker":                    ticker,
            "Stress Days":               n,
            "Avg Return on Stress Days": round(avg_return, 4),
            "Hit Rate":                  round(hit_rate, 4),
            "Co-Crash Rate":             round(co_crash_rate, 4),
        })

    result = pd.DataFrame(records).set_index("Ticker")
    return result


# ─────────────────────────────────────────────
# SECTION 7 — 80/20 PORTFOLIO BACKTEST
# ─────────────────────────────────────────────

def run_portfolio_backtest(
    tickers: list[str],
    start_date:    str | None = None,
    end_date:      str | None = None,
    benchmark:     str   = "SPY",
    benchmark_wgt: float = 0.80,
) -> pd.DataFrame:
    """
    Section 7: compare 100% benchmark vs. 80/20 blends with each alternative asset.

    Parameters
    ----------
    tickers        : alternative tickers to blend with benchmark
    benchmark      : core holding ticker, default 'SPY'
    benchmark_wgt  : weight of benchmark in blended portfolios, default 0.80

    Returns
    -------
    DataFrame with one row per portfolio and columns:
        Cumulative Return, Annualized Volatility, Max Drawdown
    """
    alt_wgt     = 1.0 - benchmark_wgt
    all_tickers = list(set(tickers + [benchmark]))
    returns     = load_returns_from_db(all_tickers, start_date, end_date)

    def _portfolio_stats(port_returns: pd.Series) -> dict:
        cumulative = (1 + port_returns).prod() - 1
        ann_vol    = port_returns.std() * np.sqrt(252)
        wealth     = (1 + port_returns).cumprod()
        roll_max   = wealth.cummax()
        drawdown   = (wealth - roll_max) / roll_max
        max_dd     = drawdown.min()
        return {
            "Cumulative Return":     round(cumulative, 4),
            "Annualized Volatility": round(ann_vol, 4),
            "Max Drawdown":          round(max_dd, 4),
        }

    records = []

    if benchmark in returns.columns:
        stats = _portfolio_stats(returns[benchmark].dropna())
        stats["Portfolio"] = f"100% {benchmark}"
        records.append(stats)

    for ticker in tickers:
        if ticker == benchmark or ticker not in returns.columns:
            continue

        aligned = returns[[benchmark, ticker]].dropna()
        port_r  = (
            aligned[benchmark] * benchmark_wgt +
            aligned[ticker]    * alt_wgt
        )
        stats = _portfolio_stats(port_r)
        stats["Portfolio"] = f"{int(benchmark_wgt*100)}% {benchmark} / {int(alt_wgt*100)}% {ticker}"
        records.append(stats)

    result = pd.DataFrame(records).set_index("Portfolio")
    return result


# ─────────────────────────────────────────────
# SECTION 8 — FINAL ASSET CLASSIFICATION
# ─────────────────────────────────────────────

def classify_assets(
    performance: pd.DataFrame,
    stress:      pd.DataFrame,
    portfolios:  pd.DataFrame,
    benchmark:   str = "SPY",
) -> pd.DataFrame:
    """
    Section 8: assign each asset a role label based on combined evidence
    from performance, stress-day, and portfolio backtest results.

    Classification logic
    --------------------
    - Risk Amplifier             : higher vol than benchmark AND low stress hit rate
    - Safe-Haven / Diversifier   : high hit rate on stress days (>= 60%) AND positive avg return
    - Conditional Hedge          : positive avg stress return but inconsistent hit rate
    - Stabilizer                 : reduces vol and drawdown vs. benchmark alone
    - Inflation / Cyclical       : helps sometimes but adds vol (energy/commodity)

    Returns
    -------
    DataFrame with one row per asset: Role, Rationale
    """
    benchmark_vol  = performance.loc[benchmark, "Annualized Volatility"] if benchmark in performance.index else None
    benchmark_port = f"100% {benchmark}"

    baseline_vol = portfolios.loc[benchmark_port, "Annualized Volatility"] if benchmark_port in portfolios.index else None
    baseline_dd  = portfolios.loc[benchmark_port, "Max Drawdown"]          if benchmark_port in portfolios.index else None

    records = []
    for ticker in stress.index:
        hit_rate   = stress.loc[ticker, "Hit Rate"]
        co_crash   = stress.loc[ticker, "Co-Crash Rate"]
        avg_stress = stress.loc[ticker, "Avg Return on Stress Days"]

        etf_vol = performance.loc[ticker, "Annualized Volatility"] if ticker in performance.index else None

        port_label = next((l for l in portfolios.index if ticker in l), None)
        port_vol   = portfolios.loc[port_label, "Annualized Volatility"] if port_label else None
        port_dd    = portfolios.loc[port_label, "Max Drawdown"]          if port_label else None

        if etf_vol and benchmark_vol and etf_vol > benchmark_vol * 1.1 and hit_rate < 0.40:
            role      = "Risk Amplifier"
            rationale = f"Higher vol than {benchmark}; only positive on {hit_rate:.0%} of stress days."

        elif hit_rate >= 0.60 and avg_stress > 0:
            role      = "Safe-Haven / Diversifier"
            rationale = f"Positive on {hit_rate:.0%} of {benchmark} stress days; avg stress return {avg_stress:.2%}."

        elif avg_stress > 0 and hit_rate >= 0.45:
            role      = "Conditional Hedge"
            rationale = f"Helpful in some stress periods (hit rate {hit_rate:.0%}) but inconsistent."

        elif port_vol and baseline_vol and port_dd and baseline_dd \
                and port_vol < baseline_vol and abs(port_dd) < abs(baseline_dd):
            role      = "Stabilizer"
            rationale = f"80/20 blend reduces vol ({port_vol:.2%} vs {baseline_vol:.2%}) and drawdown."

        else:
            role      = "Inflation / Cyclical Exposure"
            rationale = f"Co-crash rate {co_crash:.0%}; adds volatility; sector/commodity driven."

        records.append({"Ticker": ticker, "Role": role, "Rationale": rationale})

    return pd.DataFrame(records).set_index("Ticker")


# ─────────────────────────────────────────────
# SECTION 5 (extended) — FULL CORRELATION
# ─────────────────────────────────────────────

def calculate_correlations(
    tickers: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    General correlation + covariance analysis (price and returns).

    Returns
    -------
    price_corr, returns_corr, price_cov, returns_cov
    """
    prices  = load_prices_from_db(tickers, start_date, end_date)
    returns = prices.pct_change().dropna(how="all")

    return prices.corr(), returns.corr(), prices.cov(), returns.cov()


# ─────────────────────────────────────────────
# CLI — MENU & MAIN LOOP
# ─────────────────────────────────────────────

def _cli_get_tickers(prompt: str, default: list[str] | None = None) -> list[str]:
    default_str = ",".join(default) if default else ""
    raw = input(f"{prompt} [default: {default_str}]: ").strip()
    if not raw and default:
        return default
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _cli_get_dates() -> tuple[str, str]:
    start = input("Start date (YYYY-MM-DD): ").strip()
    end   = input("End date   (YYYY-MM-DD): ").strip()
    return start, end


def display_menu() -> str:
    print("\n" + "=" * 55)
    print("  IS 445 — DEFENSIVE ASSETS PIPELINE")
    print("=" * 55)
    print("  0.  Quit")
    print("  1.  Insert / Download Tickers")
    print("  2.  Reset Database")
    print("  3.  General Correlation & Covariance")
    print("  4.  Basic Performance Table")
    print("  5.  SPY Correlation Table")
    print("  6.  SPY Stress-Day Test")
    print("  7.  80/20 Portfolio Backtest")
    print("  8.  Full Analysis (4 → 5 → 6 → 7 → Classify)")
    print("=" * 55)
    return input("Choice: ").strip()


def main():
    print(f"\nConnected: {user}@{server}/{database}")

    while True:
        choice = display_menu()

        if choice == "0":
            print("Goodbye!")
            engine.dispose()
            break

        elif choice == "1":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            download_and_insert_tickers(tickers, start, end)

        elif choice == "2":
            confirm = input("⚠  Type 'yes' to confirm full reset: ").strip().lower()
            if confirm == "yes":
                reset_db()
            else:
                print("Reset cancelled.")

        elif choice == "3":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            pc, rc, pv, rv = calculate_correlations(tickers, start, end)
            print("\n── Returns Correlation ──\n", rc.to_string())
            print("\n── Price Covariance ──\n", pv.to_string())

        elif choice == "4":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            perf = calculate_performance_table(tickers, start, end)
            print("\n── Basic Performance Table ──\n", perf.to_string())

        elif choice == "5":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            spy_corr, full_corr = calculate_spy_correlation(tickers, start, end)
            print("\n── Correlation vs SPY ──\n", spy_corr.to_string())

        elif choice == "6":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            stress = run_stress_test(tickers, start, end)
            print("\n── SPY Stress-Day Test ──\n", stress.to_string())

        elif choice == "7":
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()
            portfolios = run_portfolio_backtest(tickers, start, end)
            print("\n── 80/20 Portfolio Backtest ──\n", portfolios.to_string())

        elif choice == "8":
            print("\n── Full Analysis Pipeline ──")
            tickers    = _cli_get_tickers("Tickers", DEFAULT_TICKERS)
            start, end = _cli_get_dates()

            perf = calculate_performance_table(tickers, start, end)
            print("\n[4] Performance Table:\n", perf.to_string())

            spy_corr, full_corr = calculate_spy_correlation(tickers, start, end)
            print("\n[5] SPY Correlation:\n", spy_corr.to_string())

            stress = run_stress_test(tickers, start, end)
            print("\n[6] Stress-Day Test:\n", stress.to_string())

            portfolios = run_portfolio_backtest(tickers, start, end)
            print("\n[7] Portfolio Backtest:\n", portfolios.to_string())

            classification = classify_assets(perf, stress, portfolios)
            print("\n[8] Asset Classification:\n", classification.to_string())

        else:
            print("✗ Invalid choice.")


if __name__ == "__main__":
    main()
