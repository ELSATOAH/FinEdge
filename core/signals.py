"""
FinEdge - Signal Generator
Combines ML predictions, technical analysis, and sentiment into an Edge Score.
"""
import logging
from datetime import datetime

import config
from core import database, indicators, predictor
from services.market_service import get_history_df, get_latest_price
from services.sentiment_service import get_sentiment_score

log = logging.getLogger("finedge.signals")

SIGNAL_LABELS = {
    (60, 100): "STRONG BUY",
    (25, 60): "BUY",
    (-25, 25): "HOLD",
    (-60, -25): "SELL",
    (-100, -60): "STRONG SELL",
}


def classify_signal(score: float) -> str:
    """Classify an edge score into a signal label."""
    for (lo, hi), label in SIGNAL_LABELS.items():
        if lo <= score <= hi:
            return label
    return "HOLD"


def generate_signal(ticker: str):
    """
    Generate a complete trading signal for a ticker.
    Combines ML + Technical + Sentiment into a single Edge Score.
    """
    ticker = ticker.upper().strip()
    log.info(f"Generating signal for {ticker}...")

    details = {"ticker": ticker, "timestamp": datetime.now().isoformat()}

    # DB-first history; only fetches externally if DB is empty (service handles it)
    df = get_history_df(ticker, days=365)
    if df.empty:
        log.warning(f"No data available for {ticker}")
        return None

    # Compute indicators
    df_with_indicators = indicators.compute_all(df)

    # ── ML Score ──────────────────────────────────────────
    try:
        ml_score, ml_details = predictor.get_ml_score(ticker, df_with_indicators)
        details["ml"] = ml_details
    except Exception as e:
        log.error(f"ML prediction failed for {ticker}: {e}")
        ml_score = 0.0
        details["ml"] = {"error": str(e)}

    # ── Technical Analysis Score ──────────────────────────
    try:
        ta_score, ta_details = indicators.get_ta_score(df_with_indicators)
        details["technical"] = ta_details
    except Exception as e:
        log.error(f"TA failed for {ticker}: {e}")
        ta_score = 0.0
        details["technical"] = {"error": str(e)}

    # ── Sentiment Score ───────────────────────────────────
    try:
        sent_score, sent_details = get_sentiment_score(ticker)
        details["sentiment"] = sent_details
    except Exception as e:
        log.error(f"Sentiment failed for {ticker}: {e}")
        sent_score = 0.0
        details["sentiment"] = {"error": str(e)}

    # ── Composite Edge Score ──────────────────────────────
    edge_score = (
        ml_score * config.WEIGHT_ML
        + ta_score * config.WEIGHT_TECHNICAL
        + sent_score * config.WEIGHT_SENTIMENT
    )
    edge_score = round(max(-100, min(100, edge_score)), 1)
    signal_type = classify_signal(edge_score)

    details["edge_score"] = edge_score
    details["signal"] = signal_type
    details["weights"] = {
        "ml": config.WEIGHT_ML,
        "technical": config.WEIGHT_TECHNICAL,
        "sentiment": config.WEIGHT_SENTIMENT,
    }

    # Save to database
    database.save_signal(
        ticker, signal_type, edge_score,
        ml_score, ta_score, sent_score, details
    )

    log.info(f"Signal for {ticker}: {signal_type} (Edge: {edge_score})")

    return {
        "ticker": ticker,
        "signal": signal_type,
        "edge_score": edge_score,
        "ml_score": round(ml_score, 1),
        "ta_score": round(ta_score, 1),
        "sentiment_score": round(sent_score, 1),
        "details": details,
    }


def generate_all_signals():
    """Generate signals for all watchlist tickers."""
    watchlist = database.get_watchlist()
    results = []

    for item in watchlist:
        t = (item.get("ticker") or "").upper().strip()
        if not t:
            continue
        try:
            sig = generate_signal(t)
            if sig:
                results.append(sig)
        except Exception as e:
            log.error(f"Signal generation failed for {t}: {e}")
            results.append({
                "ticker": t,
                "signal": "ERROR",
                "edge_score": 0,
                "error": str(e)
            })

    return sorted(results, key=lambda x: x.get("edge_score", 0), reverse=True)


def get_dashboard_data():
    """Get all data needed for the dashboard."""
    watchlist = database.get_watchlist()
    latest_signals = database.get_latest_signals()
    signal_map = {s["ticker"]: s for s in latest_signals}

    dashboard_items = []
    for item in watchlist:
        ticker = (item.get("ticker") or "").upper().strip()
        if not ticker:
            continue

        # latest price (provider call)
        price_data = get_latest_price(ticker)

        # latest saved signal from DB
        sig = signal_map.get(ticker, {})

        metrics = database.get_model_metrics(ticker)
        pred_accuracy = database.get_prediction_accuracy(ticker)

        dashboard_items.append({
            "ticker": ticker,
            "name": item.get("name", ticker),
            "asset_type": item.get("asset_type", "stock"),
            "price": price_data,
            "signal": sig.get("signal_type", "N/A"),
            "edge_score": sig.get("edge_score", 0),
            "ml_score": sig.get("ml_score", 0),
            "ta_score": sig.get("ta_score", 0),
            "sentiment_score": sig.get("sentiment_score", 0),
            "model_accuracy": metrics.get("accuracy", 0) if metrics else 0,
            "prediction_accuracy": pred_accuracy,
            "last_signal_time": sig.get("created_at", "Never"),
        })

    return sorted(dashboard_items, key=lambda x: x.get("edge_score", 0), reverse=True)