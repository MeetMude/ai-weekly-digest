import os
import json
import feedparser
from datetime import datetime, timedelta, timezone
from time import mktime

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


def fetch_articles(days_back: int = 7, keywords: list[str] | str = None, feeds: dict = None, max_per_feed: int = 8) -> list[dict]:
    """
    Fetch recent articles from all configured RSS feeds.

    Args:
        days_back: only keep articles published within this many days.
        keywords: string or list of keyword strings to filter articles (matches title or summary).
        feeds: optional dict of {source_name: feed_url}. Defaults to stored feeds.json.
        max_per_feed: cap on articles pulled from each single feed.

    Returns:
        List of dicts: {title, link, source, published, summary_raw}
    """
    if feeds is None:
        feeds = load_feeds()

    kw_list = []
    if isinstance(keywords, str):
        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    elif isinstance(keywords, list):
        kw_list = [str(k).strip().lower() for k in keywords if str(k).strip()]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    articles = []

    for source_name, feed_url in feeds.items():
        parsed = feedparser.parse(feed_url)

        for entry in parsed.entries[:max_per_feed]:
            published = _entry_published(entry)
            if published < cutoff:
                continue

            title = entry.get("title", "Untitled")
            summary_raw = entry.get("summary", "")

            if kw_list:
                search_text = f"{title} {summary_raw}".lower()
                if not any(kw in search_text for kw in kw_list):
                    continue

            articles.append({
                "title": title,
                "link": entry.get("link", ""),
                "source": source_name,
                "published": published.strftime("%Y-%m-%d"),
                "summary_raw": summary_raw,
            })

    # Most recent first
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles


if __name__ == "__main__":
    for article in fetch_articles():
        print(f"[{article['source']}] {article['title']} ({article['published']})")

