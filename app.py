
"""
app.py

Flask front-end and backend server for AI & Universal News Digest.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import threading
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
app.config["SCHEDULER_TIMEZONE"] = "Asia/Kolkata"
app.config["SCHEDULER_API_ENABLED"] = False

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

GENERATED_DIR = os.path.join(app.root_path, "static", "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

# In-memory status tracking for on-demand digest generation.
GENERATION_JOBS = {}
GENERATION_JOBS_LOCK = threading.Lock()


def execute_automated_scheduled_digest(job_id: str):
    """Execute a scheduled digest and email it to the recipient."""
    with app.app_context():
        job = get_scheduled_job(job_id)

        if not job:
            print(f"[APScheduler] Scheduled job {job_id} not found.")
            return

        topic = job["topic"]
        email = job["email"]
        days_back = 7

        print(
            f"[APScheduler] Running scheduled digest for job {job_id} "
            f"(topic='{topic}', email='{email}')..."
        )

        try:
            articles = fetch_news_for_topic(
                topic=topic,
                days_back=days_back,
            )

            if not articles:
                print(
                    f"[APScheduler] No articles found for topic '{topic}'."
                )
                return

            articles = summarize_articles(articles)

            safe_topic = "".join(
                c if c.isalnum() else "_" for c in topic
            )[:20]

            filename = (
                f"Weekly_Digest_Scheduled_{safe_topic}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

            output_path = os.path.join(GENERATED_DIR, filename)

            generate_pdf(
                articles,
                output_path=output_path,
                topic=topic,
            )

            log_digest(
                pdf_path=output_path,
                article_count=len(articles),
                days_back=days_back,
                keywords="",
                source_trigger="scheduled_web",
                topic=topic,
            )

            try:
                send_email_digest(
                    pdf_path=output_path,
                    article_count=len(articles),
                    recipient=email,
                )
                print(
                    f"[APScheduler] Successfully emailed digest "
                    f"for job {job_id} to {email}"
                )
            except Exception as e:
                print(
                    f"[APScheduler] Email delivery failed "
                    f"for job {job_id}: {e}"
                )

        except Exception as err:
            print(
                f"[APScheduler] Error executing scheduled job "
                f"{job_id}: {err}"
            )


def register_job_with_apscheduler(job_data: dict):
    """Register or update a scheduled job in APScheduler."""
    job_id = job_data["job_id"]
    run_time = job_data.get("run_time", "09:00")

    try:
        hour, minute = map(int, run_time.split(":"))
    except Exception:
        hour, minute = 9, 0

    freq = job_data.get("frequency", "daily")
    interval_gap = job_data.get("interval_gap")
    day_of_week = job_data.get("day_of_week", "mon")

    timezone = "Asia/Kolkata"

    if freq == "daily":
        trigger = CronTrigger(
            hour=hour, minute=minute, timezone=timezone
        )
    elif freq == "alternate_days":
        trigger = CronTrigger(
            day="*/2", hour=hour, minute=minute, timezone=timezone
        )
    elif freq == "interval_days" and interval_gap:
        trigger = CronTrigger(
            day=f"*/{interval_gap}",
            hour=hour,
            minute=minute,
            timezone=timezone,
        )
    elif freq == "weekly" and day_of_week:
        trigger = CronTrigger(
            day_of_week=str(day_of_week).lower()[:3],
            hour=hour,
            minute=minute,
            timezone=timezone,
        )
    else:
        trigger = CronTrigger(
            hour=hour, minute=minute, timezone=timezone
        )

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        id=job_id,
        func=execute_automated_scheduled_digest,
        args=[job_id],
        trigger=trigger,
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    print(
        f"[APScheduler] Registered {job_id}, next run: "
        f"{scheduler.get_job(job_id).next_run_time}"
    )


def restore_all_scheduled_jobs():
    """Restore saved scheduled jobs when the application starts."""
    jobs = get_scheduled_jobs()

    for job in jobs:
        try:
            register_job_with_apscheduler(job)
        except Exception as err:
            print(
                f"Failed to restore scheduled job "
                f"{job['job_id']}: {err}"
            )


with app.app_context():
    restore_all_scheduled_jobs()


@app.route("/")
def index():
    """Render the home page."""
    return render_template("index.html")


@app.route("/history")
def history_page():
    """Render the digest history page."""
    return render_template("history.html")


@app.route("/api/history", methods=["GET"])
def api_history():
    """Return past digest records."""
    return jsonify({
        "success": True,
        "history": get_digest_history(),
    })


@app.route("/api/feeds", methods=["GET"])
def get_feeds():
    """Return configured RSS fallback feeds."""
    return jsonify({
        "success": True,
        "feeds": load_feeds(),
    })


@app.route("/api/feeds", methods=["POST"])
def create_feed():
    """Add a new RSS fallback feed."""
    data = request.get_json(silent=True) or request.form

    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()

    if not name or not url:
        return jsonify({
            "success": False,
            "error": "Both feed name and URL are required.",
        }), 400

    feeds = add_feed(name, url)

    return jsonify({
        "success": True,
        "feeds": feeds,
    })


@app.route("/api/feeds/delete", methods=["POST"])
@app.route("/api/feeds/<path:name>", methods=["DELETE"])
def delete_feed(name=None):
    """Remove an RSS fallback feed."""
    if not name:
        data = request.get_json(silent=True) or request.form
        name = data.get("name")

    if not name:
        return jsonify({
            "success": False,
            "error": "Feed name is required.",
        }), 400

    feeds = remove_feed(name)

    return jsonify({
        "success": True,
        "feeds": feeds,
    })


@app.route("/api/schedules", methods=["GET"])
def get_schedules():
    """Return all active scheduled jobs."""
    return jsonify({
        "success": True,
        "schedules": get_scheduled_jobs(),
    })


@app.route("/schedule", methods=["POST"])
@app.route("/api/schedules", methods=["POST"])
def create_schedule():
    """Create, save, and register a scheduled digest job."""
    data = request.get_json(silent=True) or request.form

    email = (
        data.get("recipient_email")
        or data.get("email")
        or ""
    ).strip()

    topic = (
        data.get("schedule_topic")
        or data.get("topic")
        or "AI and Machine Learning"
    ).strip()

    frequency = (data.get("frequency") or "daily").strip()
    run_time = (data.get("run_time") or "09:00").strip()

    interval_gap = data.get("interval_gap")

    if interval_gap and str(interval_gap).isdigit():
        interval_gap = int(interval_gap)
    else:
        interval_gap = None

    day_of_week = (data.get("day_of_week") or "").strip() or None

    if not email:
        return jsonify({
            "success": False,
            "error": "Recipient Email is required.",
        }), 400

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
        return jsonify({
            "success": False,
            "error": f"Failed to register background job: {e}",
        }), 500

    return jsonify({
        "success": True,
        "job_id": job_id,
        "schedules": get_scheduled_jobs(),
    })


@app.route("/schedule/delete/<path:job_id>", methods=["POST", "DELETE"])
@app.route("/api/schedules/<path:job_id>", methods=["DELETE"])
def remove_schedule(job_id):
    """Remove a scheduled job."""
    if not job_id:
        return jsonify({
            "success": False,
            "error": "job_id is required.",
        }), 400

    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception:
        pass

    deleted = delete_scheduled_job(job_id)

    return jsonify({
        "success": True,
        "deleted": deleted,
        "schedules": get_scheduled_jobs(),
    })


def process_digest_job(job_id, topic, days_back, keywords):
    """Generate a digest in a background thread."""
    with GENERATION_JOBS_LOCK:
        GENERATION_JOBS[job_id]["status"] = "running"
        GENERATION_JOBS[job_id]["message"] = (
            "Fetching and summarizing news..."
        )

    try:
        with app.app_context():
            articles = fetch_news_for_topic(
                topic=topic,
                days_back=days_back,
                keywords=keywords,
            )

            articles = summarize_articles(articles)

            safe_topic = "".join(
                character if character.isalnum() else "_"
                for character in topic
            )[:20]

            filename = (
                f"Weekly_Digest_{safe_topic}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

            output_path = os.path.join(GENERATED_DIR, filename)

            generate_pdf(
                articles,
                output_path=output_path,
                topic=topic,
            )

            log_digest(
                pdf_path=output_path,
                article_count=len(articles),
                days_back=days_back,
                keywords=keywords,
                source_trigger="web",
                topic=topic,
            )

        with GENERATION_JOBS_LOCK:
            GENERATION_JOBS[job_id].update({
                "status": "completed",
                "message": "Digest generated successfully.",
                "article_count": len(articles),
                "topic": topic,
                "download_url": f"/download/{filename}",
            })

    except Exception as err:
        print(f"[Digest] Job {job_id} failed: {err}")

        with GENERATION_JOBS_LOCK:
            GENERATION_JOBS[job_id].update({
                "status": "failed",
                "message": str(err),
            })


@app.route("/generate", methods=["POST"])
def generate():
    """Start on-demand digest generation in the background."""
    topic = (
        request.form.get(
            "topic", "AI and Machine Learning"
        ).strip()
        or "AI and Machine Learning"
    )

    keywords = request.form.get("keywords", "").strip()

    try:
        days_back = int(request.form.get("days", 7))

        if not 1 <= days_back <= 30:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Days must be a number between 1 and 30.",
        }), 400

    job_id = uuid.uuid4().hex

    with GENERATION_JOBS_LOCK:
        GENERATION_JOBS[job_id] = {
            "status": "queued",
            "message": "Your digest has been queued.",
        }

    worker = threading.Thread(
        target=process_digest_job,
        args=(job_id, topic, days_back, keywords),
        daemon=True,
    )

    worker.start()

    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "queued",
    }), 202


@app.route("/api/generate-status/<job_id>", methods=["GET"])
def generate_status(job_id):
    """Return the current status of a digest job."""
    with GENERATION_JOBS_LOCK:
        job = GENERATION_JOBS.get(job_id)

        if job is not None:
            job = job.copy()

    if job is None:
        return jsonify({
            "success": False,
            "error": (
                "Digest job not found. "
                "Please start generation again."
            ),
        }), 404

    return jsonify({
        "success": True,
        **job,
    })


@app.route("/api/schedules/<job_id>/run", methods=["POST"])
def run_now(job_id):
    """Manually trigger a scheduled job immediately."""
    execute_automated_scheduled_digest(job_id)

    return jsonify({"success": True})


@app.route("/download/<path:filename>")
def download(filename):
    """Serve a generated PDF for download."""
    generated_path = os.path.join(GENERATED_DIR, filename)

    if os.path.exists(generated_path):
        return send_from_directory(
            GENERATED_DIR,
            filename,
            as_attachment=True,
        )

    if os.path.exists(os.path.join(app.root_path, filename)):
        return send_from_directory(
            app.root_path,
            filename,
            as_attachment=True,
        )

    return send_from_directory(
        GENERATED_DIR,
        filename,
        as_attachment=True,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )
