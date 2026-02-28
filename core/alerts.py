"""
FinEdge - Telegram Alert System
Sends trading signals and alerts via Telegram bot.
"""
import logging
import requests

import config

log = logging.getLogger("finedge.alerts")


def send_telegram(message):
    """Send a message via Telegram bot."""
    if not config.TELEGRAM_ENABLED:
        return False
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram alert sent")
            return True
        else:
            log.error(f"Telegram API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        log.error(f"Failed to send Telegram alert: {e}")
        return False


def format_signal_alert(signal_data):
    """Format a signal into a Telegram message."""
    ticker = signal_data["ticker"]
    signal = signal_data["signal"]
    edge = signal_data["edge_score"]
    ml = signal_data.get("ml_score", 0)
    ta = signal_data.get("ta_score", 0)
    sent = signal_data.get("sentiment_score", 0)

    # Emoji mapping
    emoji_map = {
        "STRONG BUY": "🟢🟢",
        "BUY": "🟢",
        "HOLD": "🟡",
        "SELL": "🔴",
        "STRONG SELL": "🔴🔴",
    }
    emoji = emoji_map.get(signal, "⚪")

    msg = (
        f"{emoji} <b>FinEdge Signal: {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Signal: <b>{signal}</b>\n"
        f"Edge Score: <b>{edge:+.1f}</b>\n"
        f"ML Score: {ml:+.1f}\n"
        f"TA Score: {ta:+.1f}\n"
        f"Sentiment: {sent:+.1f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg


def alert_signal(signal_data):
    """Send a signal alert if it meets the threshold."""
    if not config.TELEGRAM_ENABLED:
        return

    edge = abs(signal_data.get("edge_score", 0))
    if edge < config.CONFIDENCE_THRESHOLD * 100:
        return  # Not confident enough to alert

    msg = format_signal_alert(signal_data)
    send_telegram(msg)


def alert_all_signals(signals):
    """Send alerts for all significant signals."""
    for sig in signals:
        alert_signal(sig)
