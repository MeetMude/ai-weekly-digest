"""
extract.py

Downloads a news article page and pulls out the readable body text
(no menus, ads, or footers) using the `trafilatura` library.
"""

from concurrent.futures import ThreadPoolExecutor

import trafilatura

MIN_USEFUL_CHARS = 400     # shorter than this = probably not the real article
MAX_CHARS = 6000           # enough for a good summary, keeps API cost low


def get_article_text(url: str) -> str:
    """Return the article body text, or '' if it can't be extracted."""
    if not url:
        return ""
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return ""
        text = trafilatura.extract(
            html, include_comments=False, include_tables=False
        ) or ""
        text = text.strip()
        if len(text) < MIN_USEFUL_CHARS:
            return ""
        return text[:MAX_CHARS]
    except Exception as e:
        print(f"  extract failed for {url[:60]}...: {e}")
        return ""


def add_full_text(articles: list[dict], workers: int = 4) -> list[dict]:
    """Download full text for all articles in parallel. Adds 'full_text' key."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        texts = list(pool.map(lambda a: get_article_text(a.get("link", "")), articles))
    for article, text in zip(articles, texts):
        article["full_text"] = text
    got = sum(1 for t in texts if t)
    print(f"Extracted full text for {got}/{len(articles)} article(s).")
    return articles
