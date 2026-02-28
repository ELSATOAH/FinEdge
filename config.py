"""
FinEdge Configuration
AI-Powered Stock/Crypto Edge Predictor
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DB_PATH = os.path.join(DATA_DIR, "finedge.db")

# ── Server ──────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False

# ── Default Watchlist ───────────────────────────────────
# Add tickers you want to track (stocks & crypto)
DEFAULT_WATCHLIST = [
  "ADS.DE",
  "AIR.DE",
  "ALV.DE",
  "BAS.DE",
  "BAYN.DE",
  "BEI.DE",
  "BMW.DE",
  "BNR.DE",
  "CBK.DE",
  "CON.DE",
  "DTG.DE",
  "DBK.DE",
  "DB1.DE",
  "DHL.DE",
  "DTE.DE",
  "EOAN.DE",
  "FRE.DE",
  "FME.DE",
  "G1A.DE",
  "HNR1.DE",
  "HEI.DE",
  "HEN3.DE",
  "IFX.DE",
  "MBG.DE",
  "MRK.DE",
  "MTX.DE",
  "MUV2.DE",
  "PAH3.DE",
  "QIA.DE",
  "RHM.DE",
  "RWE.DE",
  "SAP.DE",
  "G24.DE",
  "SIE.DE",
  "ENR.DE",
  "SHL.DE",
  "SY1.DE",
  "VOW3.DE",
  "VNA.DE",
  "ZAL.DE",
]

# ── Data Settings ───────────────────────────────────────
HISTORY_PERIOD = "1y"       # How much historical data to fetch
FETCH_INTERVAL_MIN = 15     # Auto-refresh interval in minutes
PREDICTION_HORIZON = 1      # Predict N days ahead

# ── ML Model Settings ──────────────────────────────────
MODEL_TYPE = "gradient_boosting"  # gradient_boosting | random_forest
MIN_TRAINING_SAMPLES = 60        # Minimum data points to train
CONFIDENCE_THRESHOLD = 0.6       # Min confidence to generate signal
RETRAIN_HOURS = 6                # Retrain models every N hours

# ── Sentiment Settings ──────────────────────────────────
SENTIMENT_ENABLED = True
NEWS_SOURCES = [
  "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=DE&lang=de-DE",
]
MAX_NEWS_ITEMS = 20

# ── Alert Settings ──────────────────────────────────────
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = os.environ.get("FINEDGE_TG_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("FINEDGE_TG_CHAT", "")

# ── Edge Score Weights ──────────────────────────────────
WEIGHT_ML = 0.45          # ML prediction weight
WEIGHT_TECHNICAL = 0.35   # Technical analysis weight
WEIGHT_SENTIMENT = 0.20   # Sentiment weight

# ── Display ─────────────────────────────────────────────
CURRENCY_SYMBOL = "$"
DECIMAL_PLACES = 2
