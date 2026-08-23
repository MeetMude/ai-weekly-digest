# AI Weekly Digest

A small pipeline that pulls the past week's AI/ML news from a curated set of
RSS feeds, summarizes each article with Claude, and compiles everything into
a clean, shareable PDF digest — one report per source, sorted by recency.
Usable either as a CLI command or through a one-page Flask web app.

> Inspired by [KalyanM45/Synapse-Daily](https://github.com/KalyanM45/Synapse-Daily),
> built from scratch as a personal learning project.

## How it works

```
RSS feeds  ─▶  fetch_news.py   ─▶  raw articles
                                          │
                                          ▼
                                  summarize.py   ─▶  1-2 sentence summaries (Claude)
                                          │
                                          ▼
                                  generate_pdf.py ─▶  AI_Weekly_Digest.pdf
```

- **`src/fetch_news.py`** — pulls recent entries from a list of RSS feeds
  (TechCrunch AI, MIT Tech Review, VentureBeat AI, The Verge AI by default),
  filtered to the last N days.
- **`src/summarize.py`** — condenses each article into a tight 1-2 sentence
  summary using the Anthropic API. Falls back to a trimmed raw snippet if no
  API key is set, so the pipeline never breaks.
- **`src/generate_pdf.py`** — renders the summarized articles into a
  formatted PDF, grouped by source.
- **`main.py`** — ties the three steps together into a single CLI command.
- **`app.py`** + **`templates/index.html`** — a minimal Flask front-end: pick
  how many days back to look, click Generate, and download the PDF straight
  from the browser.

## Setup

```bash
git clone https://github.com/<your-username>/ai-weekly-digest.git
cd ai-weekly-digest
pip install -r requirements.txt
```

Set your Anthropic API key to enable LLM-quality summaries (optional):

```bash
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

### CLI

```bash
python main.py                          # last 7 days, default output path
python main.py --days 3                 # last 3 days only
python main.py --output digest.pdf      # custom output filename
```

### Web app

```bash
python app.py
# then open http://127.0.0.1:5000
```

Pick a lookback window, click **Generate Digest**, and download the PDF once
it's ready. Generated files are saved under `static/generated/`.

## Customizing sources

Edit the `RSS_FEEDS` dictionary in `src/fetch_news.py` to add, remove, or
swap out news sources.

## Possible extensions

- Add topic categorization (e.g. LLMs, robotics, policy) per article
- Push the digest to Slack/Telegram/email instead of just a local PDF
- Deduplicate stories covered by multiple sources
- Schedule it weekly with GitHub Actions or a cron job
- Add a history page in the Flask app listing previously generated digests

## License

MIT
