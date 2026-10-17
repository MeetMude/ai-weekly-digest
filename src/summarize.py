"""
summarize.py

Turns full article text into a readable summary + key points using Google
Gemini, and builds a topic overview for the top of the PDF.
Falls back gracefully (no crash) if there is no API key or the call fails.
"""

import os
import re
import time

from src.extract import add_full_text

_model = None
_model_checked = False


def _get_model():
    """Create the Gemini model on first use (so .env is already loaded)."""
    global _model, _model_checked
    if _model_checked:
        return _model
    _model_checked = True

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("WARNING: GEMINI_API_KEY not found. Using plain-text fallback "
              "(summaries will be much weaker).")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        _model = genai.GenerativeModel(name)
        print(f"Gemini ready: {name}")
    except Exception as e:
        print(f"WARNING: could not start Gemini: {e}")
    return _model


def _strip_html(raw_html: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw_html or "")
    return re.sub(r"\s+", " ", clean).strip()


def _ask(prompt: str) -> str:
    """Call Gemini with one retry. Returns '' on failure."""
    model = _get_model()
    if not model:
        return ""
    for attempt in (1, 2):
        try:
            return model.generate_content(prompt).text.strip()
        except Exception as e:
            print(f"  Gemini call failed (attempt {attempt}): {e}")
            time.sleep(5)
    return ""


def _split_summary_and_bullets(text: str):
    """Split model output into (paragraph, [bullets])."""
    paragraph_lines, bullets = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().rstrip(":") in ("summary", "key points", "key takeaways", "overview"):
            continue
        if line.startswith(("-", "*", "•")):
            bullets.append(line.lstrip("-*• ").strip())
        else:
            paragraph_lines.append(line)
    return " ".join(paragraph_lines).strip(), bullets


def _fallback_summary(text: str, limit: int = 700) -> str:
    """No AI: take the first few sentences of the best text we have."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: last + 1] if last > 200 else cut.rstrip() + "..."


def summarize_article(article: dict) -> dict:
    title = article["title"]
    snippet = _strip_html(article.get("summary_raw", ""))
    full_text = article.get("full_text", "")
    source_text = full_text or snippet

    prompt = (
        "You are writing one entry of a news digest for a reader who wants to "
        "genuinely learn about this topic.\n"
        "Use ONLY the information in the article text below. Do not add facts "
        "that are not in it.\n\n"
        "Write:\n"
        "1. One paragraph of 4-6 sentences in plain English: what happened, who "
        "is involved, and why it matters.\n"
        "2. Then exactly 3 short key points, each on its own line starting with '- '.\n\n"
        f"Title: {title}\n"
        f"Article text:\n{source_text}\n"
    )
    answer = _ask(prompt)
    if answer:
        summary, points = _split_summary_and_bullets(answer)
        if summary:
            article["summary"], article["key_points"] = summary, points[:3]
            return article

    article["summary"] = _fallback_summary(source_text)
    article["key_points"] = []
    return article


def summarize_articles(articles: list[dict]) -> list[dict]:
    """Download full text, then summarize each article. Adds 'summary' and 'key_points'."""
    articles = add_full_text(articles)
    for article in articles:
        summarize_article(article)
    return articles


def build_overview(topic: str, articles: list[dict]):
    """Return (overview_paragraph, [takeaways]) for the top of the PDF."""
    if not articles:
        return "", []
    digest_text = "\n".join(f"- {a['title']}: {a.get('summary', '')}" for a in articles[:12])
    prompt = (
        f"Below are this week's news items about '{topic}'.\n"
        "Write a briefing for someone who knows little about the subject:\n"
        "1. One paragraph of 5-7 sentences explaining what has been happening this "
        "week overall and the main storylines.\n"
        "2. Then 4-5 key takeaways, each on its own line starting with '- '.\n"
        "Use ONLY the items below.\n\n" + digest_text
    )
    answer = _ask(prompt)
    if answer:
        return _split_summary_and_bullets(answer)
    return "", []
