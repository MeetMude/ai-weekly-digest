# AI Weekly Digest

A clean, customizable pipeline that pulls the past week's AI/ML news from curated RSS feeds, filters by keywords, summarizes each article with Claude (Anthropic API), logs every generation to a local SQLite database, and compiles everything into a PDF digest. Includes full web UI feed management, digest history archive, and automated email dispatch capabilities.

> Inspired by [KalyanM45/Synapse-Daily](https://github.com/KalyanM45/Synapse-Daily), built as an expandable personal portfolio project.

---

## Pipeline Overview

```
[RSS Feeds / feeds.json]
       │
       ▼
 [src/fetch_news.py]  ──▶  Date & Keyword Filtering  ──▶  Raw Articles
                                                             │
                                                             ▼
                                                    [src/summarize.py]  ──▶  1-2 sentence summaries (Claude)
                                                             │
                                                             ▼
                                                   [src/generate_pdf.py] ──▶  PDF Document
                                                             │
                                              ┌──────────────┴──────────────┐
                                              ▼                             ▼
                                      [src/db.py (SQLite)]         [src/mailer.py (SMTP)]
                                 (Logged to digests.db)        (Emailed to subscriber)
```

- **`src/fetch_news.py`** — fetches RSS articles based on `feeds.json`, filtered by publication cutoff and keyword matching.
- **`src/summarize.py`** — condenses articles into 1–2 sentence summaries via Anthropic API (with graceful plain-text fallback).
- **`src/generate_pdf.py`** — renders formatted PDFs grouped by source using ReportLab.
- **`src/db.py`** — persistent SQLite logging database (`digests.db`) tracking timestamps, keywords, article counts, trigger source, and file paths.
- **`src/mailer.py`** — email sender module dispatching PDF attachments via SMTP.
- **`main.py`** — CLI entry point with feed management, keyword filtering, and history viewing flags.
- **`scheduled_digest.py`** — headless script designed for automated task scheduling (Task Scheduler / Cron).
- **`app.py`** + **`templates/`** — Flask web interface serving generator form, live feed manager, and digest history archive (`/history`).

---

## Setup & Environment

1. **Clone & Install Dependencies**:
   ```bash
   git clone https://github.com/<your-username>/ai-weekly-digest.git
   cd ai-weekly-digest
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables (`.env`)**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your API keys and email credentials:
   ```env
   # Claude Summaries
   ANTHROPIC_API_KEY=your_anthropic_api_key_here

   # Email Credentials (for scheduled_digest.py)
   EMAIL_ADDRESS=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password_here
   EMAIL_TO=recipient@example.com

   # Optional SMTP Settings
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

---

## Usage

### CLI Commands (`main.py`)

```bash
# Generate digest (default 7 days)
python main.py

# Filter by keywords & lookback days
python main.py --days 7 --keywords "agents,open-source,llm" --output custom_digest.pdf

# View past generated digests history log (SQLite)
python main.py --history

# Manage RSS Feeds
python main.py --list-feeds
python main.py --add-feed "Ars Technica" "https://feeds.arstechnica.com/arstechnica/index"
python main.py --remove-feed "Ars Technica"
```

### Web App (`app.py`)

```bash
python app.py
# Open http://127.0.0.1:5000 in your browser
```
- **Generator (`/`)**: Select lookback window, filter by keywords, manage active RSS feed pills, and generate/download PDFs.
- **History Archive (`/history`)**: Browse past digests logged in the SQLite database and re-download previous report PDFs.

---

## Automated Scheduling & Email Delivery

The script `scheduled_digest.py` runs the entire pipeline headlessly, logs the output to `digests.db`, and emails the PDF as an attachment.

### Dry Run (Test without sending email):
```bash
python scheduled_digest.py --days 7 --keywords "agents,AI" --no-email
```

### Manual Trigger (Generate & Email):
```bash
python scheduled_digest.py --days 7
```

### 1. Windows Task Scheduler

To run `scheduled_digest.py` automatically every Monday at 9:00 AM:

#### Option A: Command Line (`schtasks`)
Open PowerShell as Administrator and run:
```powershell
schtasks /Create /TN "AIWeeklyDigest" /TR "python C:\path\to\ai-weekly-digest\scheduled_digest.py" /SC WEEKLY /D MON /ST 09:00
```

#### Option B: Task Scheduler GUI
1. Press `Win + R`, type `taskschd.msc`, and press **Enter**.
2. Click **Create Basic Task...** in the right sidebar.
3. Name: `AI Weekly Digest`.
4. Trigger: **Weekly** -> Select **Monday**, Start time: `9:00 AM`.
5. Action: **Start a program**.
   - Program/script: `python` (or full path e.g. `C:\Python313\python.exe`)
   - Add arguments: `scheduled_digest.py`
   - Start in: `C:\path\to\ai-weekly-digest`

---

### 2. Linux / macOS Cron Job

To run the job every Monday at 9:00 AM via `cron`:

1. Open crontab editor:
   ```bash
   crontab -e
   ```
2. Add the following line (replace `/path/to/ai-weekly-digest` with your absolute path):
   ```cron
   0 9 * * 1 cd /path/to/ai-weekly-digest && /usr/bin/python3 scheduled_digest.py >> cron.log 2>&1
   ```

---

## License

MIT
