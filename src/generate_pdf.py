"""
generate_pdf.py

Renders summarized articles into a readable PDF briefing:
topic overview -> key takeaways -> detailed story summaries.
"""

from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
)

from src.summarize import build_overview


def _build_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("DigestTitle", parent=s["Title"], fontSize=24, spaceAfter=10))
    s.add(ParagraphStyle("DigestSubtitle", parent=s["Normal"], fontSize=11,
                         textColor=colors.grey, spaceAfter=14))
    s.add(ParagraphStyle("SectionHeading", parent=s["Heading2"], fontSize=15,
                         spaceBefore=16, spaceAfter=8, textColor=colors.HexColor("#1a1a2e")))
    s.add(ParagraphStyle("Body", parent=s["Normal"], fontSize=10.5, leading=15, spaceAfter=6))
    s.add(ParagraphStyle("Point", parent=s["Normal"], fontSize=10, leading=14,
                         leftIndent=16, bulletIndent=4, spaceAfter=3))
    s.add(ParagraphStyle("ArticleTitle", parent=s["Heading3"], fontSize=12.5,
                         spaceBefore=14, spaceAfter=2, textColor=colors.HexColor("#16213e")))
    s.add(ParagraphStyle("ArticleMeta", parent=s["Normal"], fontSize=8.5,
                         textColor=colors.grey, spaceAfter=5))
    s.add(ParagraphStyle("ReadMore", parent=s["Normal"], fontSize=9,
                         textColor=colors.HexColor("#1a5fb4"), spaceAfter=8))
    return s


def _bullets(points, style):
    return [Paragraph(escape(p), style, bulletText="•") for p in points]


def generate_pdf(articles: list[dict], output_path: str = "AI_Weekly_Digest.pdf",
                 topic: str = "AI and Machine Learning", overview=None) -> str:
    """
    Build the PDF. `overview` is an optional (paragraph, [takeaways]) tuple;
    if not given, it is generated automatically from the articles.
    """
    clean_topic = (topic or "").strip() or "AI and Machine Learning"
    st = _build_styles()
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
    )

    story = [
        Paragraph(f"Weekly Digest: {escape(clean_topic)}", st["DigestTitle"]),
        Paragraph(f"Your briefing on {escape(clean_topic)} &mdash; "
                  f"{date.today().strftime('%B %d, %Y')}", st["DigestSubtitle"]),
        HRFlowable(width="100%", color=colors.HexColor("#dddddd")),
    ]

    if not articles:
        story += [Spacer(1, 20),
                  Paragraph(f"No articles found for '{escape(clean_topic)}' during this period.", st["Body"])]
        doc.build(story)
        return output_path

    if overview is None:
        overview = build_overview(clean_topic, articles)
    overview_text, takeaways = overview
    if overview_text:
        story.append(Paragraph("The Big Picture", st["SectionHeading"]))
        story.append(Paragraph(escape(overview_text), st["Body"]))
    if takeaways:
        story.append(Paragraph("Key Takeaways", st["SectionHeading"]))
        story += _bullets(takeaways, st["Point"])

    story.append(Paragraph("Top Stories", st["SectionHeading"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd")))

    for a in articles:
        block = [
            Paragraph(escape(a["title"]), st["ArticleTitle"]),
            Paragraph(f"{escape(str(a['source']))} &middot; {escape(str(a['published']))}", st["ArticleMeta"]),
            Paragraph(escape(a.get("summary", "")), st["Body"]),
        ]
        block += _bullets(a.get("key_points", []), st["Point"])
        if a.get("link"):
            block.append(Paragraph(
                f"<link href='{escape(a['link'], {chr(39): '&apos;'})}'>Read the full article &rarr;</link>",
                st["ReadMore"]))
        story.append(KeepTogether(block))

    doc.build(story)
    return output_path
