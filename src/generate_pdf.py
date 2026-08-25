"""
generate_pdf.py

Renders a list of summarized articles into a clean, shareable PDF digest.
"""

from datetime import date
from collections import defaultdict

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DigestTitle", parent=styles["Title"], fontSize=24, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="DigestSubtitle", parent=styles["Normal"], fontSize=11,
        textColor=colors.grey, spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=styles["Heading2"], fontSize=14,
        spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#1a1a2e")
    ))
    styles.add(ParagraphStyle(
        name="ArticleTitle", parent=styles["Heading3"], fontSize=12,
        spaceBefore=10, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="ArticleMeta", parent=styles["Normal"], fontSize=8,
        textColor=colors.grey, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="ArticleSummary", parent=styles["Normal"], fontSize=10,
        leading=14, spaceAfter=6
    ))
    return styles


def generate_pdf(articles: list[dict], output_path: str = "AI_Weekly_Digest.pdf", topic: str = "AI and Machine Learning") -> str:
    """
    Build a PDF digest grouped by source, from a list of summarized articles.

    Args:
        articles: list of dicts with keys title, link, source, published, summary.
        output_path: where to write the PDF.
        topic: user-defined topic string for header metadata.

    Returns:
        The output_path, for convenience.
    """
    clean_topic = (topic or "").strip() or "AI and Machine Learning"
    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    story = []
    story.append(Paragraph(f"Weekly Digest: {clean_topic}", styles["DigestTitle"]))
    story.append(Paragraph(
        f"Curated summary of top {clean_topic} news &mdash; {date.today().strftime('%B %d, %Y')}",
        styles["DigestSubtitle"]
    ))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd")))

    if not articles:
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"No articles found for '{clean_topic}' during this period.", styles["ArticleSummary"]))
    else:
        grouped = defaultdict(list)
        for article in articles:
            grouped[article["source"]].append(article)

        for source, items in grouped.items():
            story.append(Paragraph(source, styles["SectionHeading"]))
            for article in items:
                story.append(Paragraph(article["title"], styles["ArticleTitle"]))
                story.append(Paragraph(
                    f"{article['published']} &middot; <link href='{article['link']}'>{article['link']}</link>",
                    styles["ArticleMeta"]
                ))
                story.append(Paragraph(article["summary"], styles["ArticleSummary"]))

    doc.build(story)
    return output_path

