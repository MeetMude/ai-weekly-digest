import os
import json
import re
import feedparser
from datetime import datetime, timedelta, timezone
from time import mktime

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


FEEDS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feeds.json")

DEFAULT_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
}


def load_feeds() -> dict:
    """Load feeds from feeds.json, falling back to defaults if not found."""
    if os.path.exists(FEEDS_FILE):
        try:
            with open(FEEDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_feeds(DEFAULT_FEEDS)
    return DEFAULT_FEEDS.copy()


def save_feeds(feeds: dict) -> None:
    """Save feeds dictionary to feeds.json."""
    with open(FEEDS_FILE, "w", encoding="utf-8") as f:
        json.dump(feeds, f, indent=2)


def add_feed(name: str, url: str) -> dict:
    """Add or update an RSS feed source and persist changes."""
    feeds = load_feeds()
    feeds[name] = url
    save_feeds(feeds)
    return feeds


def remove_feed(name: str) -> dict:
    """Remove an RSS feed source by name and persist changes."""
    feeds = load_feeds()
    if name in feeds:
        del feeds[name]
        save_feeds(feeds)
    return feeds


def _entry_published(entry) -> datetime:
    """Best-effort parse of an entry's published date, falling back to now."""
    for key in ("published_parsed", "updated_parsed"):
        value = getattr(entry, key, None)
        if value:
            return datetime.fromtimestamp(mktime(value), tz=timezone.utc)
    return datetime.now(timezone.utc)


def _fetch_from_rss_fallback(topic: str, days_back: int, kw_list: list[str], feeds: dict, max_per_feed: int) -> list[dict]:
    """Fallback fetcher querying configured RSS feeds if DDGS yields no results."""
    if feeds is None:
        feeds = load_feeds()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    articles = []
    topic_keywords = [t.strip().lower() for t in topic.split() if len(t.strip()) > 3]

    for source_name, feed_url in feeds.items():
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:max_per_feed]:
                published = _entry_published(entry)
                if published < cutoff:
                    continue

                title = entry.get("title", "Untitled")
                summary_raw = entry.get("summary", "")
                search_text = f"{title} {summary_raw}".lower()

                # Filter by topic keywords if topic is custom
                if topic_keywords and not any(tk in search_text for tk in topic_keywords):
                    continue

                # Filter by keyword list if provided
                if kw_list and not any(kw in search_text for kw in kw_list):
                    continue

                articles.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "source": source_name,
                    "published": published.strftime("%Y-%m-%d"),
                    "summary_raw": summary_raw,
                })
        except Exception:
            continue

    return articles


# ---------------------------------------------------------------------------
# Quality filter: skips pages that are not real news (betting tips, live-score
# listings, TV guides...). Edit this list to add or remove words.
# Phrases that appear in your topic are never filtered (e.g. topic "sports
# betting" keeps betting articles).
# ---------------------------------------------------------------------------
JUNK_TITLE_PHRASES = [
    "betting", "sportsbook", "casino", "promo code", "bonus code",
    "dream11", "fantasy", "live score", "live scores", "fixtures",
    "how to watch", "where to watch", "live stream", "live streaming",
    "streaming today", "on tv", "tv schedule", "tv channel",
]


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _filter_articles(articles: list[dict], topic: str) -> list[dict]:
    """Drop junk pages and duplicates. Never returns an empty list by accident."""
    topic_lc = (topic or "").lower()
    phrases = [p for p in JUNK_TITLE_PHRASES if p not in topic_lc]
    junk_re = re.compile(r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b") if phrases else None

    kept, seen_titles, seen_urls, dropped = [], set(), set(), []
    for a in articles:
        title = a.get("title", "")
        norm = _normalize_title(title)
        url_key = (a.get("link", "") or "").split("?")[0].rstrip("/")

        if junk_re and junk_re.search(title.lower()):
            dropped.append(title)
            continue
        if norm in seen_titles or (url_key and url_key in seen_urls):
            dropped.append(title)
            continue
        seen_titles.add(norm)
        if url_key:
            seen_urls.add(url_key)
        kept.append(a)

    if dropped:
        print(f"Filtered out {len(dropped)} low-value or duplicate result(s):")
        for t in dropped:
            print(f"   - {t[:70]}")
    if not kept and articles:
        print("Filter removed everything, so keeping the original results.")
        return articles
    return kept


def fetch_news_for_topic(
    topic: str = "AI and Machine Learning",
    days_back: int = 7,
    keywords: list[str] | str = None,
    feeds: dict = None,
    max_results: int = 15
) -> list[dict]:
    """
    Fetch real-time news articles on demand for any dynamic topic query using DuckDuckGo Search (DDGS),
    falling back to RSS feeds if search returns no results or fails.

    Args:
        topic: The user-defined news topic (e.g. "Space Exploration", "Quantum Computing").
        days_back: Lookback window in days.
        keywords: Optional extra keywords string or list to filter articles.
        feeds: Optional custom RSS feeds dict for fallback.
        max_results: Maximum articles to fetch.

    Returns:
        List of dicts: {title, link, source, published, summary_raw}
    """
    clean_topic = (topic or "").strip() or "AI and Machine Learning"

    kw_list = []
    if isinstance(keywords, str):
        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    elif isinstance(keywords, list):
        kw_list = [str(k).strip().lower() for k in keywords if str(k).strip()]

    articles = []

    # 1. Primary Ingestion: DuckDuckGo Real-Time News Search
    try:
        ddgs = DDGS()
        raw_news = list(ddgs.news(clean_topic, max_results=max_results + 5))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)


        for item in raw_news:
            title = item.get("title", "Untitled")
            body = item.get("body", "") or item.get("snippet", "")
            url = item.get("url", "")
            source = item.get("source", "Web Search")
            pub_str = item.get("date", "")

            pub_dt = None
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            if pub_dt and pub_dt < cutoff:
                continue

            published_fmt = pub_dt.strftime("%Y-%m-%d") if pub_dt else datetime.now().strftime("%Y-%m-%d")

            if kw_list:
                search_text = f"{title} {body}".lower()
                if not any(kw in search_text for kw in kw_list):
                    continue

            articles.append({
                "title": title,
                "link": url,
                "source": source,
                "published": published_fmt,
                "summary_raw": body,
            })
    except Exception as e:
        print(f"Notice: DuckDuckGo news fetch error ({e}). Using RSS fallback...")

    # 2. Fallback Ingestion: Configured RSS feeds
    if not articles:
        articles = _fetch_from_rss_fallback(clean_topic, days_back, kw_list, feeds, max_results)

    articles = _filter_articles(articles, clean_topic)

    # Sort most recent first, keep the requested amount
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:max_results]


def fetch_articles(
    days_back: int = 7,
    keywords: list[str] | str = None,
    feeds: dict = None,
    max_per_feed: int = 8,
    topic: str = "AI and Machine Learning"
) -> list[dict]:
    """Backward-compatible wrapper for fetch_news_for_topic."""
    return fetch_news_for_topic(
        topic=topic,
        days_back=days_back,
        keywords=keywords,
        feeds=feeds,
        max_results=max_per_feed * 3
    )


if __name__ == "__main__":
    test_topic = "Space Exploration"
    print(f"Testing news fetch for topic: '{test_topic}'")
    res = fetch_news_for_topic(test_topic, days_back=7)
    print(f"Retrieved {len(res)} articles.")
    for art in res[:3]:
        print(f"[{art['source']}] {art['title']} ({art['published']})")