"""
Sentiment service: orchestrates news provider + scoring + DB caching.
"""
import logging
from typing import Tuple, List, Dict, Any

import config
from core import database
from core.sentiment_scoring import analyze_text, score_label
from providers.news_yahoo_rss import get_news

log = logging.getLogger("finedge.services.sentiment")


def analyze_ticker(symbol: str) -> Tuple[float, List[Dict[str, Any]]]:
    symbol = symbol.upper().strip()

    if not config.SENTIMENT_ENABLED:
        return 0.0, []

    headlines = get_news(symbol)
    if not headlines:
        log.info(f"No news found for {symbol}")
        return 0.0, []

    analyzed: List[Dict[str, Any]] = []
    scores: List[float] = []

    for item in headlines:
        text = f"{item.get('title','')}. {item.get('summary','')}"
        s = analyze_text(text)
        scores.append(s)
        analyzed.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "published": item.get("published", ""),
                "sentiment": round(s, 3),
                "label": score_label(s),
            }
        )

    # Weighted average (later entries get higher weight)
    if scores:
        weights = list(range(1, len(scores) + 1))
        avg_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    else:
        avg_score = 0.0

    database.save_sentiment(
        symbol,
        avg_score,
        len(analyzed),
        [{"title": a["title"], "sentiment": a["sentiment"], "label": a["label"]} for a in analyzed],
    )

    return avg_score, analyzed


def get_sentiment_score(symbol: str):
    avg_score, analyzed = analyze_ticker(symbol)

    score = max(-100, min(100, avg_score * 100))

    return round(score, 1), {
        "raw_score": round(avg_score, 4),
        "articles": len(analyzed),
        "headlines": analyzed[:10],
    }