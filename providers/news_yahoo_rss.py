"""
Yahoo RSS news provider.
External I/O only: fetches RSS feeds, returns list of articles.
No scoring and no DB writes here.
"""
import logging
from typing import List, Dict, Any, Set

import feedparser

import config

log = logging.getLogger("finedge.providers.news_yahoo_rss")


def get_news(symbol: str) -> List[Dict[str, Any]]:
    symbol = symbol.upper().strip()
    headlines: List[Dict[str, Any]] = []
    seen_links: Set[str] = set()

    for url_template in config.NEWS_SOURCES:
        url = url_template.format(ticker=symbol)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[: config.MAX_NEWS_ITEMS]:
                link = entry.get("link", "") or ""
                title = entry.get("title", "") or ""
                if link and link in seen_links:
                    continue
                if link:
                    seen_links.add(link)
                headlines.append(
                    {
                        "title": title,
                        "link": link,
                        "published": entry.get("published", "") or "",
                        "summary": (entry.get("summary", "") or "")[:200],
                        "source_url": url,
                    }
                )
        except Exception as e:
            log.error(f"Failed to fetch news for {symbol} from {url}: {e}")

    return headlines