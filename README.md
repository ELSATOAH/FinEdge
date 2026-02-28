# FinEdge — AI-Powered Stock/Crypto Edge Predictor

> Uses machine learning, technical analysis, and news sentiment to generate trading signals with a composite **Edge Score**.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **ML Predictions** — GradientBoosting/RandomForest models trained per-ticker
- **17 Technical Indicators** — RSI, MACD, Bollinger Bands, Stochastic, CCI, ATR, OBV, and more
- **News Sentiment** — Real-time RSS feed analysis with TextBlob NLP
- **Edge Score** — Composite signal from -100 to +100 combining ML + TA + Sentiment
- **Cyberpunk Dashboard** — Dark-mode web UI with live ticker tape, charts, and signal cards
- **Auto-Analysis** — Scheduled data fetching and model retraining
- **Telegram Alerts** — Get notified when strong signals are detected
- **REST API** — Full API for integration with other tools

## Quick Start

```bash
cd finedge
chmod +x setup.sh
./setup.sh
source venv/bin/activate
python3 app.py
```

Open `http://localhost:5000` in your browser.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Web Dashboard                   │
│  (Flask + Canvas Charts + Real-time Updates)     │
├─────────────────────────────────────────────────┤
│                 Signal Generator                 │
│  Edge Score = ML(45%) + TA(35%) + Sent(20%)     │
├──────────┬──────────────┬───────────────────────┤
│  ML      │  Technical   │  Sentiment            │
│  Engine  │  Analysis    │  Analyzer             │
│ sklearn  │  17 indicators│  TextBlob + RSS      │
├──────────┴──────────────┴───────────────────────┤
│              Data Layer (SQLite + yfinance)       │
└─────────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/dashboard` | GET | Full dashboard data |
| `/api/watchlist` | GET/POST | List or add tickers |
| `/api/watchlist/<ticker>` | DELETE | Remove ticker |
| `/api/signal/<ticker>` | GET | Generate signal for ticker |
| `/api/signals` | GET | Generate all signals |
| `/api/price/<ticker>` | GET | Latest price data |
| `/api/history/<ticker>` | GET | Price history |
| `/api/indicators/<ticker>` | GET | Technical indicators |
| `/api/sentiment/<ticker>` | GET | Sentiment analysis |
| `/api/model/<ticker>` | GET | Model metrics |
| `/api/retrain` | POST | Retrain ML models |
| `/api/refresh` | POST | Full data refresh |

## Configuration

Edit `config.py` to customize:
- Default watchlist tickers
- Update intervals
- ML model type (GradientBoosting / RandomForest)
- Edge score weights
- Telegram bot credentials

## Run as Service (24/7)

```bash
sudo cp finedge.service /etc/systemd/system/
sudo systemctl enable finedge
sudo systemctl start finedge
sudo systemctl status finedge
```

## Telegram Alerts

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Set environment variables:

```bash
export FINEDGE_TG_TOKEN="your-bot-token"
export FINEDGE_TG_CHAT="your-chat-id"
```

4. Set `TELEGRAM_ENABLED = True` in `config.py`

---

*Not financial advice. For educational purposes only.*
