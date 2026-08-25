"""
scheduled_digest.py

Automated script for scheduled AI & Universal News Digest generation, database logging, and email delivery.

Usage:
    python scheduled_digest.py
    python scheduled_digest.py --topic "Space Exploration" --days 7
    python scheduled_digest.py --topic "Stock Market" --no-email    # Run pipeline & log to DB without sending email

Can be scheduled using Windows Task Scheduler or Linux Cron.
"""

import os
import argparse
from datetime import datetime

from src.fetch_news import fetch_news_for_topic
from src.summarize import summarize_articles
from src.generate_pdf import generate_pdf
from src.db import log_digest
from src.mailer import send_email_digest


def load_env_file():
    """Simple parser to load environment variables from .env if present."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))


def run_scheduled_digest(
    days_back: int = 7,
    keywords: str = None,
    send_email: bool = True,
    recipient: str = None,
    topic: str = "AI and Machine Learning"
):
    """Run full pipeline for a topic: fetch -> summarize -> generate PDF -> log to SQLite DB -> send email."""
    load_env_file()
    clean_topic = (topic or "").strip() or "AI and Machine Learning"

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scheduled digest generation for topic '{clean_topic}'...")

    articles = fetch_news_for_topic(topic=clean_topic, days_back=days_back, keywords=keywords)
    print(f"Fetched {len(articles)} article(s).")

    if not articles:
        print(f"No articles found for topic '{clean_topic}'. Aborting generation.")
        return

    print("Summarizing articles with Claude...")
    articles = summarize_articles(articles)

    output_dir = os.path.join(os.path.dirname(__file__), "static", "generated")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"AI_Weekly_Digest_Scheduled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = os.path.join(output_dir, filename)

    print(f"Generating PDF at: {output_path}")
    generate_pdf(articles, output_path=output_path, topic=clean_topic)

    print("Logging digest to SQLite database...")
    row_id = log_digest(
        pdf_path=output_path,
        article_count=len(articles),
        days_back=days_back,
        keywords=keywords,
        source_trigger="scheduled",
        topic=clean_topic
    )
    print(f"Digest recorded in database with ID #{row_id}.")

    if send_email:
        print("Dispatching email with attached PDF...")
        try:
            send_email_digest(pdf_path=output_path, article_count=len(articles), recipient=recipient)
        except Exception as e:
            print(f"ERROR: Email delivery failed: {e}")
    else:
        print("Email sending skipped (--no-email requested).")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduled digest process completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scheduled news digest generation and email delivery.")
    parser.add_argument("--topic", type=str, default="AI and Machine Learning", help="News topic query (e.g. 'Space Exploration').")
    parser.add_argument("--days", type=int, default=7, help="How many days back to pull news from.")
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords filter.")
    parser.add_argument("--to", type=str, default=None, help="Recipient email address override.")
    parser.add_argument("--no-email", action="store_true", help="Generate PDF and log to DB without sending email.")

    args = parser.parse_args()
    run_scheduled_digest(
        days_back=args.days,
        keywords=args.keywords,
        send_email=not args.no_email,
        recipient=args.to,
        topic=args.topic
    )

