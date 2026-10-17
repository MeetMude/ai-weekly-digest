"""
extract.py

Downloads a news article page and pulls out the readable body text
(no menus, ads, or footers).

How it works:
  1. Download the page with a normal browser-like request (many news sites
     block plain script requests).
  2. For msn.com links (which load their text with JavaScript), use MSN's
     own content endpoint instead.
  3. Extract the main text with the `trafilatura` library.

Every article prints one line saying whether it worked and, if not, why.
"""

import gzip
import html as html_lib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import trafilatura

MIN_USEFUL_CHARS = 400     # shorter than this = probably not the real article
MAX_CHARS = 6000           # enough for a good summary, keeps API cost low
TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# https://www.msn.com/en-us/news/other/some-title/ar-AA2e30AB?ocid=...
_MSN_RE = re.compile(r"msn\.com/([a-z]{2}-[a-z]{2})/.*?/ar-([A-Za-z0-9]+)")


def _download(url: str) -> str:
    """Download a URL and return its text. Raises on failure."""
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _from_msn(url: str):
    """Return (text, reason) using MSN's content endpoint, or ('', reason)."""
    m = _MSN_RE.search(url)
    if not m:
        return "", "msn link without article id"
    locale, article_id = m.group(1), m.group(2)
    api = f"https://assets.msn.com/content/view/v2/Detail/{locale}/{article_id}"
    try:
        data = json.loads(_download(api))
    except Exception as e:
        return "", f"msn endpoint failed ({type(e).__name__})"
    body = data.get("body") or ""
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S | re.I)
    text = "\n".join(p for p in (_strip_tags(p) for p in paragraphs) if p)
    if not text:
        text = _strip_tags(body)
    return text, "" if text else "msn endpoint had no body"


def _from_page(url: str):
    """Return (text, reason) by downloading the page and extracting it."""
    try:
        page = _download(url)
    except HTTPError as e:
        return "", f"HTTP {e.code}"
    except URLError as e:
        return "", f"network error ({e.reason})"
    except Exception as e:
        return "", f"{type(e).__name__}"
    text = trafilatura.extract(page, include_comments=False, include_tables=False) or ""
    return text.strip(), "" if text.strip() else "no article text found on page"


def get_article_text(url: str):
    """Return (article_text, reason). article_text is '' if it failed."""
    if not url:
        return "", "no link"
    try:
        if "msn.com" in urlparse(url).netloc:
            text, reason = _from_msn(url)
            if len(text) < MIN_USEFUL_CHARS:        # try the page itself as a backup
                text2, reason2 = _from_page(url)
                if len(text2) > len(text):
                    text, reason = text2, reason2
        else:
            text, reason = _from_page(url)
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"

    text = text.strip()
    if len(text) < MIN_USEFUL_CHARS:
        return "", reason or f"only {len(text)} characters found"
    return text[:MAX_CHARS], ""


def add_full_text(articles: list[dict], workers: int = 4) -> list[dict]:
    """Download full text for all articles in parallel. Adds 'full_text' key."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda a: get_article_text(a.get("link", "")), articles))

    got = 0
    for article, (text, reason) in zip(articles, results):
        article["full_text"] = text
        site = urlparse(article.get("link", "")).netloc or "no-link"
        if text:
            got += 1
            print(f"  [OK]   {len(text):>5} chars  {site}")
        else:
            print(f"  [FAIL] {site}  ->  {reason}")
    print(f"Extracted full text for {got}/{len(articles)} article(s).")
    return articles