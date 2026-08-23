"""
app.py

Flask front-end for AI Weekly Digest.

Serves a single page with a "Generate Digest" button. Clicking it runs the
existing pipeline (fetch -> summarize -> PDF) and returns the PDF as a
download, so the whole project can be used from a browser instead of the CLI.

Usage:
    export ANTHROPIC_API_KEY=your_key_here   # optional, enables LLM summaries
    python app.py
    # then open http://127.0.0.1:5000
"""

import os
from datetime import datetime

from flask import Flask, render_template, send_from_directory, jsonify, request
import os
from datetime import datetime

from src.fetch_news import fetch_articles, load_feeds, add_feed, remove_feed
from src.summarize import summarize_articles
from src.generate_pdf import generate_pdf

app = Flask(__name__)

GENERATED_DIR = os.path.join(app.root_path, "static", "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)


@app.route("/")
def index():
    """Landing page with the Generate button."""
    return render_template("index.html")


@app.route("/api/feeds", methods=["GET"])
def get_feeds():
    """Return configured RSS feeds."""
    return jsonify({"success": True, "feeds": load_feeds()})


@app.route("/api/feeds", methods=["POST"])
def create_feed():
    """Add a new RSS feed."""
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
    """Remove an RSS feed by name."""
    if not name:
        data = request.get_json(silent=True) or request.form
        name = data.get("name")

    if not name:
        return jsonify({"success": False, "error": "Feed name is required."}), 400

    feeds = remove_feed(name)
    return jsonify({"success": True, "feeds": feeds})


@app.route("/generate", methods=["POST"])
def generate():
    """
    Run the pipeline end-to-end and return a JSON payload with a
    download link to the freshly generated PDF.
    """
    days_back = int(request.form.get("days", 7))
    keywords = request.form.get("keywords", "").strip()

    articles = fetch_articles(days_back=days_back, keywords=keywords)
    articles = summarize_articles(articles)

    filename = f"AI_Weekly_Digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = os.path.join(GENERATED_DIR, filename)
    generate_pdf(articles, output_path=output_path)

    return jsonify({
        "success": True,
        "article_count": len(articles),
        "download_url": f"/download/{filename}",
    })


@app.route("/download/<path:filename>")
def download(filename):
    """Serve a previously generated PDF for download."""
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)

