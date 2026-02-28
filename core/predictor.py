"""
FinEdge - ML Prediction Engine
Scikit-learn models for price prediction.
Uses GradientBoosting or RandomForest to predict next-day price direction.
"""
import os
import pickle
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler

import config
from core import database, indicators

log = logging.getLogger("finedge.predictor")

# Feature columns used for prediction
FEATURE_COLS = [
    "RSI", "MACD", "MACD_Hist", "BB_Pct", "BB_Width",
    "ATR", "Stoch_K", "Stoch_D", "Volume_Ratio",
    "ROC_5", "ROC_10", "ROC_20", "Momentum_10",
    "SMA_Cross_10_20", "SMA_Cross_20_50", "CCI", "Williams_R",
]


def _get_model_path(ticker):
    return os.path.join(config.MODELS_DIR, f"{ticker.upper()}_model.pkl")


def _get_scaler_path(ticker):
    return os.path.join(config.MODELS_DIR, f"{ticker.upper()}_scaler.pkl")


def prepare_features(df):
    """Prepare feature matrix from a DataFrame with indicators computed."""
    if df.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    # Compute indicators if not present
    if "RSI" not in df.columns:
        df = indicators.compute_all(df)

    # Target: next-day direction (1 = up, 0 = down)
    df = df.copy()
    df["Future_Return"] = df["Close"].shift(-1) / df["Close"] - 1
    df["Target"] = (df["Future_Return"] > 0).astype(int)

    # Select features and drop NaN
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    feature_df = df[available_features].copy()
    target = df["Target"].copy()

    # Drop rows with NaN
    mask = feature_df.notna().all(axis=1) & target.notna()
    feature_df = feature_df[mask]
    target = target[mask]

    return feature_df, target


def train_model(ticker, df=None):
    """Train an ML model for a ticker. Returns metrics dict."""
    log.info(f"Training model for {ticker}...")

    if df is None:
        from core import fetcher
        df = fetcher.get_history_df(ticker)

    if df.empty or len(df) < config.MIN_TRAINING_SAMPLES:
        log.warning(f"Not enough data to train {ticker} ({len(df)} samples)")
        return None

    # Compute all indicators
    df = indicators.compute_all(df)

    # Prepare features
    X, y = prepare_features(df)

    if len(X) < config.MIN_TRAINING_SAMPLES:
        log.warning(f"Not enough valid samples for {ticker}: {len(X)}")
        return None

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Select model type
    if config.MODEL_TYPE == "random_forest":
        model = RandomForestClassifier(
            n_estimators=100, max_depth=8, min_samples_split=10,
            min_samples_leaf=5, random_state=42, n_jobs=2
        )
    else:
        model = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            min_samples_split=10, min_samples_leaf=5, random_state=42
        )

    # Cross-validation
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring="accuracy")
    log.info(f"{ticker} CV Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Train on full data
    model.fit(X_scaled, y)

    # Evaluate on training set (for tracking)
    y_pred = model.predict(X_scaled)
    metrics = {
        "accuracy": round(accuracy_score(y, y_pred), 4),
        "precision": round(precision_score(y, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y, y_pred, zero_division=0), 4),
        "cv_accuracy": round(cv_scores.mean(), 4),
        "cv_std": round(cv_scores.std(), 4),
        "samples": len(X),
        "features": list(X.columns),
    }

    # Save model and scaler
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    with open(_get_model_path(ticker), "wb") as f:
        pickle.dump(model, f)
    with open(_get_scaler_path(ticker), "wb") as f:
        pickle.dump(scaler, f)

    # Save metrics to DB
    database.save_model_metrics(
        ticker, metrics["accuracy"], metrics["precision"],
        metrics["recall"], metrics["f1"], metrics["samples"]
    )

    log.info(f"Model saved for {ticker}: {metrics}")
    return metrics


def predict(ticker, df=None):
    """Make a prediction for a ticker. Returns prediction dict."""
    model_path = _get_model_path(ticker)
    scaler_path = _get_scaler_path(ticker)

    # Load or train model
    if not os.path.exists(model_path):
        log.info(f"No model found for {ticker}, training...")
        result = train_model(ticker, df)
        if result is None:
            return {"direction": "NEUTRAL", "confidence": 0.0, "change_pct": 0.0}

    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
    except Exception as e:
        log.error(f"Failed to load model for {ticker}: {e}")
        return {"direction": "NEUTRAL", "confidence": 0.0, "change_pct": 0.0}

    # Get latest data
    if df is None:
        from core import fetcher
        df = fetcher.get_history_df(ticker)

    if df.empty:
        return {"direction": "NEUTRAL", "confidence": 0.0, "change_pct": 0.0}

    # Compute indicators
    df = indicators.compute_all(df)

    # Get latest row features
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    last_row = df[available_features].iloc[-1:]

    if last_row.isna().any(axis=1).iloc[0]:
        log.warning(f"NaN in features for {ticker}")
        return {"direction": "NEUTRAL", "confidence": 0.0, "change_pct": 0.0}

    # Scale and predict
    X_scaled = scaler.transform(last_row)
    prediction = model.predict(X_scaled)[0]
    probabilities = model.predict_proba(X_scaled)[0]

    confidence = float(max(probabilities))
    direction = "UP" if prediction == 1 else "DOWN"

    # Estimate change percentage based on recent volatility
    recent_returns = df["Close"].pct_change().tail(20).abs().mean()
    estimated_change = float(recent_returns * 100)
    if direction == "DOWN":
        estimated_change = -estimated_change

    result = {
        "direction": direction,
        "confidence": round(confidence, 4),
        "change_pct": round(estimated_change, 2),
        "prob_up": round(float(probabilities[1]) if len(probabilities) > 1 else 0, 4),
        "prob_down": round(float(probabilities[0]) if len(probabilities) > 0 else 0, 4),
    }

    # Save prediction
    database.save_prediction(ticker, direction, confidence, estimated_change)

    return result


def get_ml_score(ticker, df=None):
    """Get ML-based score from -100 to +100."""
    pred = predict(ticker, df)

    if pred["direction"] == "NEUTRAL":
        return 0.0, pred

    # Score based on direction and confidence
    base = pred["confidence"] * 100
    if pred["direction"] == "DOWN":
        base = -base

    # Scale to -100 to +100
    score = max(-100, min(100, base))

    return round(score, 1), pred


def retrain_all():
    """Retrain models for all watchlist tickers."""
    watchlist = database.get_watchlist()
    results = {}
    for item in watchlist:
        ticker = item["ticker"]
        try:
            metrics = train_model(ticker)
            results[ticker] = metrics or {"status": "insufficient_data"}
        except Exception as e:
            results[ticker] = {"status": "error", "error": str(e)}
            log.error(f"Failed to retrain {ticker}: {e}")
    return results
