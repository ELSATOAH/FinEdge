"""
FinEdge - Technical Indicators Engine
Calculates RSI, MACD, Bollinger Bands, SMA/EMA crossovers, and more.
All computations use pandas/numpy — lightweight for Raspberry Pi.
"""
import numpy as np
import pandas as pd
import logging

log = logging.getLogger("finedge.indicators")


def compute_all(df):
    """Compute all technical indicators on a price DataFrame.
    Expects columns: Open, High, Low, Close, Volume
    Returns DataFrame with indicator columns added.
    """
    if df.empty or len(df) < 30:
        log.warning("Not enough data for indicators")
        return df

    df = df.copy()
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    # ── Moving Averages ─────────────────────────────
    df["SMA_10"] = close.rolling(10).mean()
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()
    df["EMA_12"] = close.ewm(span=12, adjust=False).mean()
    df["EMA_26"] = close.ewm(span=26, adjust=False).mean()
    df["EMA_9"] = close.ewm(span=9, adjust=False).mean()

    # ── MACD ────────────────────────────────────────
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ── RSI (14-period) ─────────────────────────────
    df["RSI"] = _compute_rsi(close, 14)

    # ── Bollinger Bands (20-period, 2 std) ──────────
    bb_sma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["BB_Upper"] = bb_sma + (bb_std * 2)
    df["BB_Middle"] = bb_sma
    df["BB_Lower"] = bb_sma - (bb_std * 2)
    df["BB_Width"] = ((df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]) * 100
    df["BB_Pct"] = (close - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])

    # ── ATR (14-period) ─────────────────────────────
    df["ATR"] = _compute_atr(high, low, close, 14)

    # ── Stochastic Oscillator (14, 3) ───────────────
    low_14 = low.rolling(14).min()
    high_14 = high.rolling(14).max()
    df["Stoch_K"] = ((close - low_14) / (high_14 - low_14)) * 100
    df["Stoch_D"] = df["Stoch_K"].rolling(3).mean()

    # ── Volume indicators ───────────────────────────
    df["Volume_SMA_20"] = volume.rolling(20).mean()
    df["Volume_Ratio"] = volume / df["Volume_SMA_20"]
    df["OBV"] = _compute_obv(close, volume)

    # ── Price Rate of Change (ROC) ──────────────────
    df["ROC_5"] = close.pct_change(5) * 100
    df["ROC_10"] = close.pct_change(10) * 100
    df["ROC_20"] = close.pct_change(20) * 100

    # ── Momentum ────────────────────────────────────
    df["Momentum_10"] = close - close.shift(10)

    # ── SMA Crossover Signals ───────────────────────
    df["SMA_Cross_10_20"] = np.where(df["SMA_10"] > df["SMA_20"], 1, -1)
    df["SMA_Cross_20_50"] = np.where(df["SMA_20"] > df["SMA_50"], 1, -1)

    # ── VWAP (intraday proxy) ───────────────────────
    tp = (high + low + close) / 3
    df["VWAP"] = (tp * volume).cumsum() / volume.cumsum()

    # ── Williams %R ─────────────────────────────────
    df["Williams_R"] = ((high_14 - close) / (high_14 - low_14)) * -100

    # ── CCI (20-period) ─────────────────────────────
    tp = (high + low + close) / 3
    tp_sma = tp.rolling(20).mean()
    tp_mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["CCI"] = (tp - tp_sma) / (0.015 * tp_mad)

    return df


def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _compute_obv(close, volume):
    obv = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    return obv


def get_ta_score(df):
    """Generate a Technical Analysis score from -100 to +100.
    Combines multiple indicator readings into a single score.
    """
    if df.empty or len(df) < 50:
        return 0.0, {}

    last = df.iloc[-1]
    signals = {}
    score_parts = []

    # RSI Signal
    rsi = last.get("RSI", 50)
    if rsi < 30:
        signals["RSI"] = {"value": round(rsi, 1), "signal": "OVERSOLD", "score": 30}
        score_parts.append(30)
    elif rsi < 40:
        signals["RSI"] = {"value": round(rsi, 1), "signal": "BULLISH", "score": 15}
        score_parts.append(15)
    elif rsi > 70:
        signals["RSI"] = {"value": round(rsi, 1), "signal": "OVERBOUGHT", "score": -30}
        score_parts.append(-30)
    elif rsi > 60:
        signals["RSI"] = {"value": round(rsi, 1), "signal": "BEARISH", "score": -15}
        score_parts.append(-15)
    else:
        signals["RSI"] = {"value": round(rsi, 1), "signal": "NEUTRAL", "score": 0}
        score_parts.append(0)

    # MACD Signal
    macd_hist = last.get("MACD_Hist", 0)
    if macd_hist > 0:
        s = min(25, macd_hist * 100)
        signals["MACD"] = {"value": round(macd_hist, 4), "signal": "BULLISH", "score": round(s)}
        score_parts.append(s)
    else:
        s = max(-25, macd_hist * 100)
        signals["MACD"] = {"value": round(macd_hist, 4), "signal": "BEARISH", "score": round(s)}
        score_parts.append(s)

    # Bollinger Band Position
    bb_pct = last.get("BB_Pct", 0.5)
    if bb_pct < 0.1:
        signals["Bollinger"] = {"value": round(bb_pct, 2), "signal": "OVERSOLD", "score": 20}
        score_parts.append(20)
    elif bb_pct > 0.9:
        signals["Bollinger"] = {"value": round(bb_pct, 2), "signal": "OVERBOUGHT", "score": -20}
        score_parts.append(-20)
    else:
        signals["Bollinger"] = {"value": round(bb_pct, 2), "signal": "NEUTRAL", "score": 0}
        score_parts.append(0)

    # SMA Crossovers
    sma_cross = last.get("SMA_Cross_10_20", 0)
    if sma_cross > 0:
        signals["SMA_Cross"] = {"signal": "GOLDEN CROSS", "score": 15}
        score_parts.append(15)
    else:
        signals["SMA_Cross"] = {"signal": "DEATH CROSS", "score": -15}
        score_parts.append(-15)

    # Volume
    vol_ratio = last.get("Volume_Ratio", 1.0)
    if vol_ratio > 2.0:
        signals["Volume"] = {"value": round(vol_ratio, 1), "signal": "HIGH VOLUME", "score": 10}
        score_parts.append(10)
    elif vol_ratio < 0.5:
        signals["Volume"] = {"value": round(vol_ratio, 1), "signal": "LOW VOLUME", "score": -5}
        score_parts.append(-5)
    else:
        signals["Volume"] = {"value": round(vol_ratio, 1), "signal": "NORMAL", "score": 0}
        score_parts.append(0)

    # Stochastic
    stoch_k = last.get("Stoch_K", 50)
    if stoch_k < 20:
        signals["Stochastic"] = {"value": round(stoch_k, 1), "signal": "OVERSOLD", "score": 15}
        score_parts.append(15)
    elif stoch_k > 80:
        signals["Stochastic"] = {"value": round(stoch_k, 1), "signal": "OVERBOUGHT", "score": -15}
        score_parts.append(-15)
    else:
        signals["Stochastic"] = {"value": round(stoch_k, 1), "signal": "NEUTRAL", "score": 0}
        score_parts.append(0)

    # Aggregate score, clamped to [-100, 100]
    raw = sum(score_parts)
    final_score = max(-100, min(100, raw))

    return final_score, signals
