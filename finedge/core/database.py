"""
FinEdge - Database Layer
SQLite-based storage for market data, predictions, and signals.
"""
import sqlite3
import json
import threading
from datetime import datetime
from contextlib import contextmanager

import config

_local = threading.local()


def get_connection():
    """Get thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
    return _local.conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Initialize all database tables."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                asset_type TEXT DEFAULT 'stock',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume INTEGER,
                adj_close REAL,
                UNIQUE(ticker, date)
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                prediction_date TEXT NOT NULL,
                predicted_direction TEXT,  -- UP / DOWN / NEUTRAL
                confidence REAL,
                predicted_change_pct REAL,
                actual_direction TEXT,
                actual_change_pct REAL,
                was_correct INTEGER,
                model_version TEXT
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                signal_type TEXT,  -- STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
                edge_score REAL,   -- -100 to +100
                ml_score REAL,
                ta_score REAL,
                sentiment_score REAL,
                details TEXT       -- JSON blob with breakdown
            );

            CREATE TABLE IF NOT EXISTS sentiment_cache (
                ticker TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score REAL,
                article_count INTEGER,
                headlines TEXT,  -- JSON
                PRIMARY KEY(ticker)
            );

            CREATE TABLE IF NOT EXISTS model_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accuracy REAL,
                precision_score REAL,
                recall REAL,
                f1 REAL,
                sample_count INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price_history(ticker, date);
            CREATE INDEX IF NOT EXISTS idx_pred_ticker ON predictions(ticker, created_at);
            CREATE INDEX IF NOT EXISTS idx_signal_ticker ON signals(ticker, created_at);
        """)


# ── Watchlist Operations ────────────────────────────────────

def get_watchlist():
    with get_db() as db:
        rows = db.execute("SELECT * FROM watchlist ORDER BY ticker").fetchall()
        return [dict(r) for r in rows]


def add_to_watchlist(ticker, name="", asset_type="stock"):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO watchlist (ticker, name, asset_type) VALUES (?, ?, ?)",
            (ticker.upper(), name, asset_type)
        )


def remove_from_watchlist(ticker):
    with get_db() as db:
        db.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))


# ── Price History ───────────────────────────────────────────

def save_prices(ticker, df):
    """Save a pandas DataFrame of OHLCV data."""
    with get_db() as db:
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            db.execute("""
                INSERT OR REPLACE INTO price_history
                (ticker, date, open, high, low, close, volume, adj_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker.upper(), date_str,
                float(row.get("Open", 0)), float(row.get("High", 0)),
                float(row.get("Low", 0)), float(row.get("Close", 0)),
                int(row.get("Volume", 0)),
                float(row.get("Adj Close", row.get("Close", 0)))
            ))


def get_prices(ticker, limit=365):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM price_history WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker.upper(), limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# ── Predictions ─────────────────────────────────────────────

def save_prediction(ticker, direction, confidence, change_pct, model_version="v1"):
    with get_db() as db:
        pred_date = datetime.now().strftime("%Y-%m-%d")
        db.execute("""
            INSERT INTO predictions
            (ticker, prediction_date, predicted_direction, confidence, predicted_change_pct, model_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker.upper(), pred_date, direction, confidence, change_pct, model_version))


def get_predictions(ticker, limit=30):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM predictions WHERE ticker = ? ORDER BY created_at DESC LIMIT ?",
            (ticker.upper(), limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_prediction_accuracy(ticker):
    with get_db() as db:
        row = db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM predictions
            WHERE ticker = ? AND was_correct IS NOT NULL
        """, (ticker.upper(),)).fetchone()
        if row and row["total"] > 0:
            return {"total": row["total"], "correct": row["correct"],
                    "accuracy": row["correct"] / row["total"]}
        return {"total": 0, "correct": 0, "accuracy": 0.0}


# ── Signals ─────────────────────────────────────────────────

def save_signal(ticker, signal_type, edge_score, ml_score, ta_score, sentiment_score, details=None):
    with get_db() as db:
        db.execute("""
            INSERT INTO signals
            (ticker, signal_type, edge_score, ml_score, ta_score, sentiment_score, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker.upper(), signal_type, edge_score, ml_score, ta_score,
              sentiment_score, json.dumps(details or {})))


def get_latest_signals():
    with get_db() as db:
        rows = db.execute("""
            SELECT s.* FROM signals s
            INNER JOIN (
                SELECT ticker, MAX(created_at) as max_created
                FROM signals GROUP BY ticker
            ) latest ON s.ticker = latest.ticker AND s.created_at = latest.max_created
            ORDER BY s.edge_score DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_signal_history(ticker, limit=50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM signals WHERE ticker = ? ORDER BY created_at DESC LIMIT ?",
            (ticker.upper(), limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Sentiment Cache ─────────────────────────────────────────

def save_sentiment(ticker, score, article_count, headlines):
    with get_db() as db:
        db.execute("""
            INSERT OR REPLACE INTO sentiment_cache
            (ticker, fetched_at, score, article_count, headlines)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
        """, (ticker.upper(), score, article_count, json.dumps(headlines)))


def get_sentiment(ticker):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM sentiment_cache WHERE ticker = ?",
            (ticker.upper(),)
        ).fetchone()
        if row:
            r = dict(row)
            r["headlines"] = json.loads(r["headlines"]) if r["headlines"] else []
            return r
        return None


# ── Model Metrics ───────────────────────────────────────────

def save_model_metrics(ticker, accuracy, precision, recall, f1, sample_count):
    with get_db() as db:
        db.execute("""
            INSERT INTO model_metrics
            (ticker, accuracy, precision_score, recall, f1, sample_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker.upper(), accuracy, precision, recall, f1, sample_count))


def get_model_metrics(ticker):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM model_metrics WHERE ticker = ? ORDER BY trained_at DESC LIMIT 1",
            (ticker.upper(),)
        ).fetchone()
        return dict(row) if row else None
