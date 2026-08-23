"""
main.py

Entry point for AI Weekly Digest.

Pipeline: fetch RSS articles -> summarize with Claude -> render as PDF.

Usage:
    export ANTHROPIC_API_KEY=your_key_here   # optional, enables LLM summaries
    python main.py
    python main.py --days 3 --keywords "agents,open-source"
    python main.py --add-feed "Ars Technica" "https://feeds.arstechnica.com/arstechnica/index"
    python main.py --remove-feed "TechCrunch AI"
    python main.py --list-feeds
"""

import argparse
from src.fetch_news import fetch_articles, load_feeds, add_feed, remove_feed
from src.summarize import summarize_articles
from src.generate_pdf import generate_pdf


def run(days_back: int, output_path: str, keywords: str = None):
    kw_msg = f" matching '{keywords}'" if keywords else ""
    print(f"Fetching articles from the last {days_back} day(s){kw_msg}...")
    articles = fetch_articles(days_back=days_back, keywords=keywords)
    print(f"Found {len(articles)} article(s).")

    if not articles:
        print("No articles found to summarize. Try adjusting --days or --keywords.")
        return

    print("Summarizing...")
    articles = summarize_articles(articles)

    print(f"Generating PDF at {output_path}...")
    path = generate_pdf(articles, output_path=output_path)

    print(f"Done. Digest saved to: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a weekly AI/ML news digest PDF.")
    parser.add_argument("--days", type=int, default=7, help="How many days back to pull news from.")
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords to filter articles.")
    parser.add_argument("--output", type=str, default="AI_Weekly_Digest.pdf", help="Output PDF path.")
    parser.add_argument("--add-feed", nargs=2, metavar=("NAME", "URL"), help="Add a new RSS feed source.")
    parser.add_argument("--remove-feed", metavar="NAME", help="Remove an existing RSS feed source by name.")
    parser.add_argument("--list-feeds", action="store_true", help="List all currently configured RSS feeds.")

    args = parser.parse_args()

    if args.list_feeds:
        feeds = load_feeds()
        print("\nConfigured RSS Feeds:")
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
        run(days_back=args.days, output_path=args.output, keywords=args.keywords)

