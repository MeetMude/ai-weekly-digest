"""
summarize.py

Turns raw article snippets into short, clean summaries using an LLM
(Claude, via the Anthropic API). Falls back gracefully if no API key
is configured, so the pipeline never hard-crashes.
"""

import os
import re
from anthropic import Anthropic

client = None
api_key = os.environ.get("ANTHROPIC_API_KEY")
if api_key:
    client = Anthropic(api_key=api_key)


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags that often show up in RSS summary fields."""
    clean = re.sub(r"<[^>]+>", " ", raw_html or "")
    return re.sub(r"\s+", " ", clean).strip()


def summarize_article(title: str, raw_summary: str) -> str:
    """
    Produce a 1-2 sentence, plain-English summary of a single article.

    Args:
        title: the article headline.
        raw_summary: the raw RSS description/snippet (may contain HTML).

    Returns:
        A short summary string.
    """
    text = _strip_html(raw_summary)

    if not client:
        # No API key configured — just return the cleaned snippet, trimmed.
        return text[:220] + ("..." if len(text) > 220 else "")

    prompt = (
        "Summarize this AI/ML news snippet in exactly 1-2 clear, plain-English "
        "sentences for a weekly digest. Be concrete about what happened, no fluff.\n\n"
        f"Title: {title}\n"
        f"Snippet: {text}\n\n"
        "Summary:"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def summarize_articles(articles: list[dict]) -> list[dict]:
    """Summarize a full list of articles in place, adding a 'summary' key."""
    for article in articles:
        article["summary"] = summarize_article(article["title"], article["summary_raw"])
    return articles
