"""
db.py

SQLite database helper module for logging and querying AI Weekly Digest history.
"""

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "digests.db")


def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the SQLite database and create/migrate digests and scheduled_jobs tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                days_back INTEGER NOT NULL,
                keywords TEXT,
                article_count INTEGER NOT NULL,
                pdf_path TEXT NOT NULL,
                source_trigger TEXT DEFAULT 'cli',
                topic TEXT DEFAULT 'AI and Machine Learning'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                job_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                topic TEXT NOT NULL,
                frequency TEXT NOT NULL,
                interval_gap INTEGER,
                day_of_week TEXT,
                run_time TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Schema migration: add topic column if existing DB lacks it
        try:
            cursor.execute("ALTER TABLE digests ADD COLUMN topic TEXT DEFAULT 'AI and Machine Learning'")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def log_digest(
    pdf_path: str,
    article_count: int,
    days_back: int = 7,
    keywords: str = None,
    source_trigger: str = "cli",
    topic: str = "AI and Machine Learning"
) -> int:
    """
    Record a newly generated digest into the database.

    Args:
        pdf_path: file path to the generated PDF.
        article_count: number of articles in the digest.
        days_back: lookback window in days.
        keywords: keywords filter string used (or None).
        source_trigger: trigger source ('cli', 'web', 'scheduled').
        topic: news topic string.

    Returns:
        The inserted row ID.
    """
    init_db()
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
    clean_topic = topic.strip() if (topic and isinstance(topic, str)) else "AI and Machine Learning"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO digests (timestamp, days_back, keywords, article_count, pdf_path, source_trigger, topic)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp_str, days_back, clean_keywords, article_count, pdf_path, source_trigger, clean_topic))
        conn.commit()
        return cursor.lastrowid


def get_digest_history(limit: int = 50) -> list[dict]:
    """
    Retrieve past generated digests, newest first.

    Returns:
        List of dicts representing digest records.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, days_back, keywords, article_count, pdf_path, source_trigger, topic
            FROM digests
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

    history = []
    for row in rows:
        pdf_path = row["pdf_path"]
        history.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "days_back": row["days_back"],
            "keywords": row["keywords"] or "",
            "article_count": row["article_count"],
            "pdf_path": pdf_path,
            "filename": os.path.basename(pdf_path),
            "source_trigger": row["source_trigger"],
            "topic": row["topic"] if ("topic" in row.keys() and row["topic"]) else "AI and Machine Learning",
        })
    return history


def add_scheduled_job(
    job_id: str,
    email: str,
    topic: str,
    frequency: str,
    interval_gap: int = None,
    day_of_week: str = None,
    run_time: str = "09:00"
) -> str:
    """Save a scheduled job record into scheduled_jobs table."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scheduled_jobs (job_id, email, topic, frequency, interval_gap, day_of_week, run_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, email, topic, frequency, interval_gap, day_of_week, run_time))
        conn.commit()
        return job_id


def get_scheduled_jobs() -> list[dict]:
    """Retrieve all active scheduled jobs."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT job_id, email, topic, frequency, interval_gap, day_of_week, run_time, created_at
            FROM scheduled_jobs
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

    jobs = []
    for row in rows:
        jobs.append({
            "job_id": row["job_id"],
            "email": row["email"],
            "topic": row["topic"],
            "frequency": row["frequency"],
            "interval_gap": row["interval_gap"],
            "day_of_week": row["day_of_week"],
            "run_time": row["run_time"],
            "created_at": row["created_at"],
        })
    return jobs


def get_scheduled_job(job_id: str) -> dict | None:
    """Retrieve a single scheduled job by job_id."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT job_id, email, topic, frequency, interval_gap, day_of_week, run_time, created_at
            FROM scheduled_jobs
            WHERE job_id = ?
        """, (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "job_id": row["job_id"],
            "email": row["email"],
            "topic": row["topic"],
            "frequency": row["frequency"],
            "interval_gap": row["interval_gap"],
            "day_of_week": row["day_of_week"],
            "run_time": row["run_time"],
            "created_at": row["created_at"],
        }


def delete_scheduled_job(job_id: str) -> bool:
    """Delete a scheduled job record by job_id."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scheduled_jobs WHERE job_id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0


