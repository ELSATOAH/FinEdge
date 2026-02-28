"""
FinEdge - News Sentiment Analyzer
Lightweight sentiment analysis using TextBlob on RSS news feeds.
"""
import logging
from datetime import datetime

import feedparser
from textblob import TextBlob

import config
from core import database

log = logging.getLogger("finedge.sentiment")


def fetch_news(ticker):
    """Fetch news headlines for a ticker from RSS feeds."""
    headlines = []
    for url_template in config.NEWS_SOURCES:
        url = url_template.format(ticker=ticker)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:config.MAX_NEWS_ITEMS]:
                headlines.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:200],
                })
        except Exception as e:
            log.error(f"Failed to fetch news for {ticker} from {url}: {e}")

    return headlines


def analyze_headline(text):
    """Analyze sentiment of a single text. Returns score -1.0 to +1.0."""
    try:
        blob = TextBlob(text)
        return blob.sentiment.polarity
    except Exception:
        return 0.0


def analyze_ticker(ticker):
    """Full sentiment analysis for a ticker.
    Returns sentiment score and analyzed headlines.
    """
    if not config.SENTIMENT_ENABLED:
        return 0.0, []

    headlines = fetch_news(ticker)
    if not headlines:
        log.info(f"No news found for {ticker}")
        return 0.0, []

    analyzed = []
    scores = []

    for item in headlines:
        text = f"{item['title']}. {item['summary']}"
        score = analyze_headline(text)
        scores.append(score)
        analyzed.append({
            "title": item["title"],
            "link": item["link"],
            "published": item["published"],
            "sentiment": round(score, 3),
            "label": _score_label(score),
        })

    # Weighted average (more recent = higher weight)
    if scores:
        weights = list(range(1, len(scores) + 1))
        avg_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    else:
        avg_score = 0.0

    # Cache in database
    database.save_sentiment(ticker, avg_score, len(analyzed),
                           [{"title": a["title"], "sentiment": a["sentiment"],
                             "label": a["label"]} for a in analyzed])

    log.info(f"Sentiment for {ticker}: {avg_score:.3f} ({len(analyzed)} articles)")
    return avg_score, analyzed


def get_sentiment_score(ticker):
    """Get sentiment score from -100 to +100."""
    avg_score, analyzed = analyze_ticker(ticker)

    # Scale from [-1, 1] to [-100, 100]
    score = avg_score * 100
    score = max(-100, min(100, score))

    return round(score, 1), {
        "raw_score": round(avg_score, 4),
        "articles": len(analyzed),
        "headlines": analyzed[:10],  # Top 10 for display
    }


def _score_label(score):
    if score > 0.3:
        return "VERY POSITIVE"
    elif score > 0.1:
        return "POSITIVE"
    elif score > -0.1:
        return "NEUTRAL"
    elif score > -0.3:
        return "NEGATIVE"
    else:
        return "VERY NEGATIVE"
