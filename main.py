"""
main.py

Entry point for AI & Universal News Digest.

Pipeline: fetch real-time news / RSS -> summarize with Claude -> render as PDF.

Usage:
    export ANTHROPIC_API_KEY=your_key_here   # optional, enables LLM summaries
    python main.py
    python main.py --topic "Space Exploration" --days 3
    python main.py --topic "Quantum Computing" --keywords "hardware,qubits"
    python main.py --history
"""

import argparse
from src.fetch_news import fetch_news_for_topic, load_feeds, add_feed, remove_feed
from src.summarize import summarize_articles
from src.generate_pdf import generate_pdf
from src.db import log_digest, get_digest_history


def run(days_back: int, output_path: str, keywords: str = None, topic: str = "AI and Machine Learning"):
    kw_msg = f" matching '{keywords}'" if keywords else ""
    clean_topic = (topic or "").strip() or "AI and Machine Learning"
    print(f"Fetching news for topic '{clean_topic}' from the last {days_back} day(s){kw_msg}...")

    articles = fetch_news_for_topic(topic=clean_topic, days_back=days_back, keywords=keywords)
    print(f"Found {len(articles)} article(s).")

    if not articles:
        print(f"No articles found for topic '{clean_topic}'. Try adjusting --days or --keywords.")
        return

    print("Summarizing with Claude...")
    articles = summarize_articles(articles)

    print(f"Generating PDF at {output_path}...")
    try:
        path = generate_pdf(articles, output_path=output_path, topic=clean_topic)
    except PermissionError:
        import os
        from datetime import datetime
        base, ext = os.path.splitext(output_path)
        output_path = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        print(f"File locked. Saving to fallback path: {output_path}")
        path = generate_pdf(articles, output_path=output_path, topic=clean_topic)

    print(f"Done. Digest saved to: {path}")

    row_id = log_digest(
        pdf_path=path,
        article_count=len(articles),
        days_back=days_back,
        keywords=keywords,
        source_trigger="cli",
        topic=clean_topic
    )
    print(f"Recorded in digest history database (Record #{row_id}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a weekly news digest PDF for any dynamic topic.")
    parser.add_argument("--topic", type=str, default="AI and Machine Learning", help="News topic query (e.g. 'Space Exploration', 'Quantum Computing').")
    parser.add_argument("--days", type=int, default=7, help="How many days back to pull news from.")
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords filter.")
    parser.add_argument("--output", type=str, default="AI_Weekly_Digest.pdf", help="Output PDF path.")
    parser.add_argument("--history", action="store_true", help="Display past generated digests history log.")
    parser.add_argument("--add-feed", nargs=2, metavar=("NAME", "URL"), help="Add a new RSS fallback source.")
    parser.add_argument("--remove-feed", metavar="NAME", help="Remove an RSS fallback source.")
    parser.add_argument("--list-feeds", action="store_true", help="List all configured fallback RSS feeds.")

    args = parser.parse_args()

    if args.history:
        history = get_digest_history()
        print("\n=== AI Digest History ===")
        if not history:
            print("No digest records found in database.")
        else:
            print(f"{'ID':<4} {'Timestamp':<20} {'Source':<10} {'Topic':<25} {'Days':<6} {'Articles':<10} {'Keywords':<15} {'PDF Path'}")
            print("-" * 115)
            for item in history:
                kw = item["keywords"] or "-"
                tp = item["topic"] or "AI and Machine Learning"
                print(f"{item['id']:<4} {item['timestamp']:<20} {item['source_trigger']:<10} {tp:<25} {item['days_back']:<6} {item['article_count']:<10} {kw:<15} {item['filename']}")
        print()
    elif args.list_feeds:
        feeds = load_feeds()
        print("\nConfigured Fallback RSS Feeds:")
        for name, url in feeds.items():
            print(f"  - {name}: {url}")
        print()
    elif args.add_feed:
        name, url = args.add_feed
        feeds = add_feed(name, url)
        print(f"Successfully added feed '{name}'. Current total feeds: {len(feeds)}")
    elif args.remove_feed:
        name = args.remove_feed
        feeds = remove_feed(name)
        print(f"Successfully removed feed '{name}'. Current total feeds: {len(feeds)}")
    else:
        run(days_back=args.days, output_path=args.output, keywords=args.keywords, topic=args.topic)



