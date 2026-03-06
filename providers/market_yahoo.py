"""
Yahoo (yfinance) market-data provider.
External I/O only: fetches data from Yahoo, returns dicts/DFs.
No DB writes here.
"""
import logging
import time
from typing import Optional, Dict, Any

import pandas as pd
import yfinance as yf

import config

log = logging.getLogger("finedge.providers.market_yahoo")


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _retry(fn, *args, retries: int = 3, base_sleep: float = 0.6, **kwargs):
    last_err = None
    for i in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            sleep = base_sleep * (2 ** i)
            log.warning(f"Retry {i+1}/{retries} failed: {e} (sleep {sleep:.1f}s)")
            time.sleep(sleep)
    raise last_err


def get_ticker_info(symbol: str) -> Dict[str, Any]:
    """
    Fetch basic quote/info (best-effort). Yahoo info can be flaky.
    """
    symbol = symbol.upper().strip()
    try:
        t = yf.Ticker(symbol)
        info = _retry(lambda: (t.info or {}))
        return {
            "ticker": symbol,
            "name": info.get("shortName", info.get("longName", symbol)),
            "price": info.get("regularMarketPrice", info.get("currentPrice", 0)) or 0,
            "prev_close": info.get("previousClose", 0) or 0,
            "market_cap": info.get("marketCap", 0) or 0,
            "volume": info.get("regularMarketVolume", info.get("volume", 0)) or 0,
            "day_high": info.get("dayHigh", 0) or 0,
            "day_low": info.get("dayLow", 0) or 0,
            "52w_high": info.get("fiftyTwoWeekHigh", 0) or 0,
            "52w_low": info.get("fiftyTwoWeekLow", 0) or 0,
            "pe_ratio": info.get("trailingPE", 0) or 0,
            "sector": info.get("sector", "N/A"),
            "asset_type": "crypto" if "-USD" in symbol else "stock",
        }
    except Exception as e:
        log.error(f"Failed to fetch info for {symbol}: {e}")
        return {"ticker": symbol, "name": symbol, "price": 0, "error": str(e)}


def get_history(symbol: str, period: Optional[str] = None, interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV history from Yahoo.
    """
    symbol = symbol.upper().strip()
    period = period or config.HISTORY_PERIOD
    try:
        t = yf.Ticker(symbol)
        df = _retry(lambda: t.history(period=period, interval=interval, auto_adjust=False))
        df = _flatten_columns(df)
        if df.empty:
            log.warning(f"No history data for {symbol} (period={period}, interval={interval})")
            return pd.DataFrame()
        return df
    except Exception as e:
        log.error(f"Failed to fetch history for {symbol}: {e}")
        return pd.DataFrame()


def get_latest_price(symbol: str, period: str = "5d") -> Optional[Dict[str, Any]]:
    """
    Fetch latest candle and compute day change vs previous candle.
    """
    symbol = symbol.upper().strip()
    try:
        t = yf.Ticker(symbol)
        df = _retry(lambda: t.history(period=period, auto_adjust=False))
        df = _flatten_columns(df)
        if df.empty:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        last_close = float(last["Close"])
        prev_close = float(prev["Close"])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

        return {
            "ticker": symbol,
            "price": round(last_close, config.DECIMAL_PLACES),
            "open": round(float(last["Open"]), config.DECIMAL_PLACES),
            "high": round(float(last["High"]), config.DECIMAL_PLACES),
            "low": round(float(last["Low"]), config.DECIMAL_PLACES),
            "volume": int(last["Volume"]) if "Volume" in df.columns else 0,
            "change": round(change, config.DECIMAL_PLACES),
            "change_pct": round(change_pct, 2),
            "date": df.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:
        log.error(f"Failed to get latest price for {symbol}: {e}")
        return None