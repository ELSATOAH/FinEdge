"""
FinEdge - AI-Powered Stock/Crypto Edge Predictor
Main Flask Application
Runs on Raspberry Pi 4B (2GB RAM)
"""
import sys
import os
import logging
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

import config
from core import database, fetcher, indicators, predictor, signals, sentiment, alerts

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(config.DATA_DIR, "finedge.log"), maxBytes=5*1024*1024),
    ]
)
log = logging.getLogger("finedge")

# ── Flask App ───────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False

# ── Scheduler ───────────────────────────────────────────
scheduler = BackgroundScheduler(daemon=True)


def scheduled_update():
    """Periodic data fetch and signal generation."""
    log.info("Running scheduled update...")
    try:
        fetcher.fetch_all_watchlist()
        results = signals.generate_all_signals()
        alerts.alert_all_signals(results)
        log.info(f"Scheduled update complete: {len(results)} signals generated")
    except Exception as e:
        log.error(f"Scheduled update failed: {e}")


def scheduled_retrain():
    """Periodic model retraining."""
    log.info("Running scheduled retrain...")
    try:
        predictor.retrain_all()
        log.info("Retrain complete")
    except Exception as e:
        log.error(f"Retrain failed: {e}")


# ══════════════════════════════════════════════════════════
# ROUTES - Dashboard
# ══════════════════════════════════════════════════════════

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ══════════════════════════════════════════════════════════
# API - Watchlist
# ══════════════════════════════════════════════════════════

@app.route("/api/watchlist", methods=["GET"])
def api_get_watchlist():
    return jsonify(database.get_watchlist())


@app.route("/api/watchlist", methods=["POST"])
def api_add_watchlist():
    data = request.json
    ticker = data.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    # Fetch info and add
    info = fetcher.fetch_ticker_info(ticker)
    asset_type = "crypto" if "-USD" in ticker else "stock"
    database.add_to_watchlist(ticker, info.get("name", ticker), asset_type)

    # Fetch historical data in background
    fetcher.fetch_history(ticker)

    return jsonify({"status": "added", "ticker": ticker, "info": info})


@app.route("/api/watchlist/<ticker>", methods=["DELETE"])
def api_remove_watchlist(ticker):
    database.remove_from_watchlist(ticker.upper())
    return jsonify({"status": "removed", "ticker": ticker.upper()})


# ══════════════════════════════════════════════════════════
# API - Market Data
# ══════════════════════════════════════════════════════════

@app.route("/api/price/<ticker>")
def api_get_price(ticker):
    price = fetcher.get_latest_price(ticker.upper())
    if price:
        return jsonify(price)
    return jsonify({"error": "No data"}), 404


@app.route("/api/history/<ticker>")
def api_get_history(ticker):
    days = request.args.get("days", 90, type=int)
    prices = database.get_prices(ticker.upper(), limit=days)
    return jsonify(prices)


@app.route("/api/indicators/<ticker>")
def api_get_indicators(ticker):
    df = fetcher.get_history_df(ticker.upper())
    if df.empty:
        return jsonify({"error": "No data"}), 404
    df = indicators.compute_all(df)
    last = df.iloc[-1]
    result = {}
    for col in df.columns:
        val = last[col]
        if hasattr(val, "item"):
            result[col] = round(val.item(), 4)
        elif isinstance(val, (int, float)):
            result[col] = round(val, 4)
    return jsonify(result)


# ══════════════════════════════════════════════════════════
# API - Predictions & Signals
# ══════════════════════════════════════════════════════════

@app.route("/api/predict/<ticker>")
def api_predict(ticker):
    result = predictor.predict(ticker.upper())
    return jsonify(result)


@app.route("/api/signal/<ticker>")
def api_signal(ticker):
    result = signals.generate_signal(ticker.upper())
    if result:
        return jsonify(result)
    return jsonify({"error": "Could not generate signal"}), 500


@app.route("/api/signals")
def api_all_signals():
    result = signals.generate_all_signals()
    return jsonify(result)


@app.route("/api/signals/latest")
def api_latest_signals():
    return jsonify(database.get_latest_signals())


@app.route("/api/signal-history/<ticker>")
def api_signal_history(ticker):
    limit = request.args.get("limit", 50, type=int)
    history = database.get_signal_history(ticker.upper(), limit)
    return jsonify(history)


# ══════════════════════════════════════════════════════════
# API - Sentiment
# ══════════════════════════════════════════════════════════

@app.route("/api/sentiment/<ticker>")
def api_sentiment(ticker):
    score, details = sentiment.get_sentiment_score(ticker.upper())
    return jsonify({"score": score, "details": details})


# ══════════════════════════════════════════════════════════
# API - Model Info
# ══════════════════════════════════════════════════════════

@app.route("/api/model/<ticker>")
def api_model_info(ticker):
    metrics = database.get_model_metrics(ticker.upper())
    accuracy = database.get_prediction_accuracy(ticker.upper())
    return jsonify({"metrics": metrics, "prediction_accuracy": accuracy})


@app.route("/api/retrain", methods=["POST"])
def api_retrain():
    ticker = request.json.get("ticker") if request.json else None
    if ticker:
        result = predictor.train_model(ticker.upper())
        return jsonify({"ticker": ticker.upper(), "metrics": result})
    else:
        results = predictor.retrain_all()
        return jsonify(results)


# ══════════════════════════════════════════════════════════
# API - Dashboard Data
# ══════════════════════════════════════════════════════════

@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(signals.get_dashboard_data())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Manually trigger a full refresh."""
    log.info("Manual refresh triggered")
    fetcher.fetch_all_watchlist()
    result = signals.generate_all_signals()
    return jsonify({"status": "ok", "signals": len(result)})


@app.route("/api/status")
def api_status():
    watchlist = database.get_watchlist()
    return jsonify({
        "status": "running",
        "version": "1.0.0",
        "watchlist_count": len(watchlist),
        "uptime": datetime.now().isoformat(),
        "scheduler_running": scheduler.running,
        "fetch_interval_min": config.FETCH_INTERVAL_MIN,
        "retrain_hours": config.RETRAIN_HOURS,
    })


# ══════════════════════════════════════════════════════════
# Startup
# ══════════════════════════════════════════════════════════

def initialize():
    """Initialize database and default watchlist."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    database.init_db()

    # Add default watchlist if empty
    watchlist = database.get_watchlist()
    if not watchlist:
        log.info("Initializing default watchlist...")
        for ticker in config.DEFAULT_WATCHLIST:
            asset_type = "crypto" if "-USD" in ticker else "stock"
            database.add_to_watchlist(ticker, ticker, asset_type)
        log.info(f"Added {len(config.DEFAULT_WATCHLIST)} default tickers")


if __name__ == "__main__":
    log.info("="*50)
    log.info("  FinEdge - AI Stock/Crypto Edge Predictor")
    log.info("  Running on Raspberry Pi")
    log.info("="*50)

    initialize()

    # Start scheduler
    scheduler.add_job(scheduled_update, "interval",
                      minutes=config.FETCH_INTERVAL_MIN, id="update")
    scheduler.add_job(scheduled_retrain, "interval",
                      hours=config.RETRAIN_HOURS, id="retrain")
    scheduler.start()
    log.info(f"Scheduler started: updates every {config.FETCH_INTERVAL_MIN}min, "
             f"retrain every {config.RETRAIN_HOURS}h")

    # Run initial data fetch
    log.info("Running initial data fetch (this may take a minute)...")

    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
