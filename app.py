"""
app.py

Flask front-end and backend server for AI & Universal News Digest.

Features:
- On-demand topic search and PDF digest generation.
- Interactive RSS fallback feed manager.
- In-app Automated Digest Scheduler powered by Flask-APScheduler & SQLite.
- Digest History Archive with direct PDF download links.

Usage:
    export ANTHROPIC_API_KEY=your_key_here   # optional, enables LLM summaries
    python app.py
    # then open http://127.0.0.1:5000
"""
from dotenv import load_dotenv
load_dotenv()
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, send_from_directory, jsonify, request
from flask_apscheduler import APScheduler
from apscheduler.triggers.cron import CronTrigger

from src.fetch_news import fetch_news_for_topic, load_feeds, add_feed, remove_feed
from src.summarize import summarize_articles
from src.generate_pdf import generate_pdf
from src.db import (
    log_digest,
    get_digest_history,
    add_scheduled_job,
    get_scheduled_jobs,
    get_scheduled_job,
    delete_scheduled_job,
)
from src.mailer import send_email_digest

app = Flask(__name__)
app.config['SCHEDULER_TIMEZONE'] = 'Asia/Kolkata'
app.config["SCHEDULER_API_ENABLED"] = True

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

GENERATED_DIR = os.path.join(app.root_path, "static", "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)


def execute_automated_scheduled_digest(job_id: str):
    """Execution function triggered by APScheduler background job."""
    with app.app_context():
        job = get_scheduled_job(job_id)
        if not job:
            print(f"[APScheduler] Scheduled job {job_id} not found in database.")
            return

        topic = job["topic"]
        email = job["email"]
        days_back = 7

        print(f"[APScheduler] Running scheduled digest for job {job_id} (topic='{topic}', email='{email}')...")

        try:
            articles = fetch_news_for_topic(topic=topic, days_back=days_back)
            if not articles:
                print(f"[APScheduler] No articles found for topic '{topic}'. Skipping generation.")
                return

            articles = summarize_articles(articles)

            safe_topic = "".join([c if c.isalnum() else "_" for c in topic])[:20]
            filename = f"Weekly_Digest_Scheduled_{safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = os.path.join(GENERATED_DIR, filename)

            generate_pdf(articles, output_path=output_path, topic=topic)

            log_digest(
                pdf_path=output_path,
                article_count=len(articles),
                days_back=days_back,
                keywords="",
                source_trigger="scheduled_web",
                topic=topic,
            )

            try:
                send_email_digest(pdf_path=output_path, article_count=len(articles), recipient=email)
                print(f"[APScheduler] Successfully emailed digest for job {job_id} to {email}")
            except Exception as e:
                print(f"[APScheduler] Email delivery failed for job {job_id}: {e}")

        except Exception as err:
            print(f"[APScheduler] Error executing scheduled job {job_id}: {err}")


def register_job_with_apscheduler(job_data: dict):
    """Build APScheduler CronTrigger and add/update job in memory scheduler."""
    job_id = job_data["job_id"]
    run_time = job_data.get("run_time", "09:00")
    try:
        hour, minute = map(int, run_time.split(":"))
    except Exception:
        hour, minute = 9, 0

    freq = job_data.get("frequency", "daily")
    interval_gap = job_data.get("interval_gap")
    day_of_week = job_data.get("day_of_week", "mon")

    if freq == "daily":
        trigger = CronTrigger(hour=hour, minute=minute)
    elif freq == "alternate_days":
        trigger = CronTrigger(day="*/2", hour=hour, minute=minute)
    elif freq == "interval_days" and interval_gap:
        trigger = CronTrigger(day=f"*/{interval_gap}", hour=hour, minute=minute)
    elif freq == "weekly" and day_of_week:
        trigger = CronTrigger(day_of_week=str(day_of_week).lower()[:3], hour=hour, minute=minute)
    else:
        trigger = CronTrigger(hour=hour, minute=minute)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        id=job_id,
        func=execute_automated_scheduled_digest,
        args=[job_id],
        trigger=trigger,
        replace_existing=True,
    )


def restore_all_scheduled_jobs():
    """Load all saved scheduled jobs from SQLite into APScheduler on startup."""
    jobs = get_scheduled_jobs()
    for job in jobs:
        try:
            register_job_with_apscheduler(job)
        except Exception as err:
            print(f"Failed to restore scheduled job {job['job_id']}: {err}")


with app.app_context():
    restore_all_scheduled_jobs()


@app.route("/")
def index():
    """Landing page with on-demand search and automated scheduler UI."""
    return render_template("index.html")


@app.route("/history")
def history_page():
    """Page listing all past generated digests with download links."""
    return render_template("history.html")


@app.route("/api/history", methods=["GET"])
def api_history():
    """Return past generated digest records as JSON."""
    return jsonify({"success": True, "history": get_digest_history()})


@app.route("/api/feeds", methods=["GET"])
def get_feeds():
    """Return configured RSS fallback feeds."""
    return jsonify({"success": True, "feeds": load_feeds()})


@app.route("/api/feeds", methods=["POST"])
def create_feed():
    """Add a new RSS fallback feed."""
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()

    if not name or not url:
        return jsonify({"success": False, "error": "Both feed name and URL are required."}), 400

    feeds = add_feed(name, url)
    return jsonify({"success": True, "feeds": feeds})


@app.route("/api/feeds/delete", methods=["POST"])
@app.route("/api/feeds/<path:name>", methods=["DELETE"])
def delete_feed(name=None):
    """Remove an RSS fallback feed by name."""
    if not name:
        data = request.get_json(silent=True) or request.form
        name = data.get("name")

    if not name:
        return jsonify({"success": False, "error": "Feed name is required."}), 400

    feeds = remove_feed(name)
    return jsonify({"success": True, "feeds": feeds})


@app.route("/api/schedules", methods=["GET"])
def get_schedules():
    """Return all active scheduled jobs from SQLite."""
    return jsonify({"success": True, "schedules": get_scheduled_jobs()})


@app.route("/schedule", methods=["POST"])
@app.route("/api/schedules", methods=["POST"])
def create_schedule():
    """
    Create a new scheduled digest job, store in SQLite, and register into APScheduler.
    """
    data = request.get_json(silent=True) or request.form

    email = (data.get("recipient_email") or data.get("email") or "").strip()
    topic = (data.get("schedule_topic") or data.get("topic") or "AI and Machine Learning").strip()
    frequency = (data.get("frequency") or "daily").strip()
    run_time = (data.get("run_time") or "09:00").strip()

    interval_gap = data.get("interval_gap")
    if interval_gap and str(interval_gap).isdigit():
        interval_gap = int(interval_gap)
    else:
        interval_gap = None

    day_of_week = (data.get("day_of_week") or "").strip() or None

    if not email:
        return jsonify({"success": False, "error": "Recipient Email is required."}), 400

    job_id = f"job_{uuid.uuid4().hex[:8]}"

    add_scheduled_job(
        job_id=job_id,
        email=email,
        topic=topic,
        frequency=frequency,
        interval_gap=interval_gap,
        day_of_week=day_of_week,
        run_time=run_time,
    )

    job_data = {
        "job_id": job_id,
        "email": email,
        "topic": topic,
        "frequency": frequency,
        "interval_gap": interval_gap,
        "day_of_week": day_of_week,
        "run_time": run_time,
    }

    try:
        register_job_with_apscheduler(job_data)
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to register background job: {e}"}), 500

    return jsonify({"success": True, "job_id": job_id, "schedules": get_scheduled_jobs()})


@app.route("/schedule/delete/<path:job_id>", methods=["POST", "DELETE"])
@app.route("/api/schedules/<path:job_id>", methods=["DELETE"])
def remove_schedule(job_id):
    """Remove a scheduled job from APScheduler and SQLite database."""
    if not job_id:
        return jsonify({"success": False, "error": "job_id is required."}), 400

    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception:
        pass

    deleted = delete_scheduled_job(job_id)
    return jsonify({"success": True, "deleted": deleted, "schedules": get_scheduled_jobs()})


@app.route("/generate", methods=["POST"])
def generate():
    """
    Run the pipeline on demand for a given topic and return a JSON payload with a
    download link to the freshly generated PDF.
    """
    topic = request.form.get("topic", "AI and Machine Learning").strip() or "AI and Machine Learning"
    days_back = int(request.form.get("days", 7))
    keywords = request.form.get("keywords", "").strip()

    articles = fetch_news_for_topic(topic=topic, days_back=days_back, keywords=keywords)
    articles = summarize_articles(articles)

    safe_topic = "".join([c if c.isalnum() else "_" for c in topic])[:20]
    filename = f"Weekly_Digest_{safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = os.path.join(GENERATED_DIR, filename)
    generate_pdf(articles, output_path=output_path, topic=topic)

    log_digest(
        pdf_path=output_path,
        article_count=len(articles),
        days_back=days_back,
        keywords=keywords,
        source_trigger="web",
        topic=topic,
    )

    return jsonify({
        "success": True,
        "article_count": len(articles),
        "topic": topic,
        "download_url": f"/download/{filename}",
    })


@app.route("/download/<path:filename>")
def download(filename):
    """Serve a previously generated PDF for download."""
    if os.path.exists(os.path.join(GENERATED_DIR, filename)):
        return send_from_directory(GENERATED_DIR, filename, as_attachment=True)
    elif os.path.exists(os.path.join(app.root_path, filename)):
        return send_from_directory(app.root_path, filename, as_attachment=True)
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)