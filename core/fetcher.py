"""
FinEdge - Market Data Fetcher
Pulls real-time and historical market data via yfinance.
"""
import logging
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

import config
from core import database

log = logging.getLogger("finedge.fetcher")


def fetch_ticker_info(ticker):
    """Fetch basic info about a ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName", info.get("longName", ticker)),
            "price": info.get("regularMarketPrice", info.get("currentPrice", 0)),
            "prev_close": info.get("previousClose", 0),
            "market_cap": info.get("marketCap", 0),
            "volume": info.get("regularMarketVolume", info.get("volume", 0)),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "sector": info.get("sector", "N/A"),
            "asset_type": "crypto" if "-USD" in ticker.upper() else "stock",
        }
    except Exception as e:
        log.error(f"Failed to fetch info for {ticker}: {e}")
        return {"ticker": ticker.upper(), "name": ticker, "price": 0, "error": str(e)}


def fetch_history(ticker, period=None):
    """Fetch historical OHLCV data and store in database."""
    period = period or config.HISTORY_PERIOD
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, auto_adjust=False)
        if df.empty:
            log.warning(f"No history data for {ticker}")
            return pd.DataFrame()

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Save to database
        database.save_prices(ticker, df)
        log.info(f"Fetched {len(df)} records for {ticker}")
        return df
    except Exception as e:
        log.error(f"Failed to fetch history for {ticker}: {e}")
        return pd.DataFrame()


def fetch_all_watchlist():
    """Fetch data for all tickers in the watchlist."""
    watchlist = database.get_watchlist()
    results = {}
    for item in watchlist:
        ticker = item["ticker"]
        try:
            info = fetch_ticker_info(ticker)
            history = fetch_history(ticker)
            results[ticker] = {
                "info": info,
                "history_count": len(history),
                "status": "ok"
            }
        except Exception as e:
            results[ticker] = {"status": "error", "error": str(e)}
            log.error(f"Error fetching {ticker}: {e}")
    return results


def get_latest_price(ticker):
    """Get the most recent price data for a ticker."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="5d", auto_adjust=False)
        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        change = float(last["Close"]) - float(prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100 if float(prev["Close"]) != 0 else 0

        return {
            "ticker": ticker.upper(),
            "price": round(float(last["Close"]), config.DECIMAL_PLACES),
            "open": round(float(last["Open"]), config.DECIMAL_PLACES),
            "high": round(float(last["High"]), config.DECIMAL_PLACES),
            "low": round(float(last["Low"]), config.DECIMAL_PLACES),
            "volume": int(last["Volume"]),
            "change": round(change, config.DECIMAL_PLACES),
            "change_pct": round(change_pct, 2),
            "date": df.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:
        log.error(f"Failed to get latest price for {ticker}: {e}")
        return None


def get_history_df(ticker, days=365):
    """Get price history as pandas DataFrame (from DB)."""
    prices = database.get_prices(ticker, limit=days)
    if not prices:
        # Try fetching from API
        df = fetch_history(ticker)
        if not df.empty:
            return df
        return pd.DataFrame()

    df = pd.DataFrame(prices)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume", "adj_close": "Adj Close"
    })
    return df
