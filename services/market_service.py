"""
Market service: orchestrates provider + DB.
- DB-first reads for history
- Incremental-ish refresh policy
"""
import logging
from typing import Dict, Any, Optional

import pandas as pd

import config
from core import database
from providers import market_yahoo

log = logging.getLogger("finedge.services.market")


def update_history(symbol: str, period: Optional[str] = None, interval: str = "1d") -> pd.DataFrame:
    """
    Fetch history from provider and store to DB.
    """
    symbol = symbol.upper().strip()
    df = market_yahoo.get_history(symbol, period=period, interval=interval)
    if df.empty:
        return df
    database.save_prices(symbol, df)
    return df


def get_history_df(symbol: str, days: int = 365, fallback_period: Optional[str] = None) -> pd.DataFrame:
    """
    Read from DB; if missing, fetch from provider, store, return.
    """
    symbol = symbol.upper().strip()
    prices = database.get_prices(symbol, limit=days)
    if not prices:
        df = update_history(symbol, period=fallback_period or config.HISTORY_PERIOD)
        return df if not df.empty else pd.DataFrame()

    df = pd.DataFrame(prices)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adj_close": "Adj Close",
        }
    )
    return df


def get_latest_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Latest price from provider (simple). Optionally you could cache in DB.
    """
    symbol = symbol.upper().strip()
    return market_yahoo.get_latest_price(symbol)


def refresh_watchlist(mode: str = "refresh") -> Dict[str, Any]:
    """
    Refresh all tickers in watchlist.

    mode:
      - "refresh": fetch only recent data for speed (30d)
      - "full": fetch config.HISTORY_PERIOD (e.g., 1y)
    """
    watchlist = database.get_watchlist()
    results: Dict[str, Any] = {}

    # Use shorter period on scheduled refresh to reduce rate limits
    period = "30d" if mode == "refresh" else config.HISTORY_PERIOD

    for item in watchlist:
        symbol = item["ticker"].upper().strip()
        try:
            info = market_yahoo.get_ticker_info(symbol)
            df = update_history(symbol, period=period, interval="1d")
            results[symbol] = {"info": info, "history_count": len(df), "status": "ok", "period_used": period}
        except Exception as e:
            results[symbol] = {"status": "error", "error": str(e)}
            log.error(f"Error refreshing {symbol}: {e}")

    return results