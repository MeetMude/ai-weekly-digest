"""
mailer.py

Utility for sending AI Weekly Digest PDF attachments via email using smtplib.
Reads credentials from environment variables:
  - EMAIL_ADDRESS
  - EMAIL_PASSWORD
  - EMAIL_TO (optional, defaults to EMAIL_ADDRESS)
  - SMTP_SERVER (optional, defaults to smtp.gmail.com)
  - SMTP_PORT (optional, defaults to 587)
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


def send_email_digest(pdf_path: str, article_count: int, recipient: str = None) -> bool:
    """
    Send the generated PDF digest as an email attachment.

    Args:
        pdf_path: Path to the generated PDF file.
        article_count: Number of articles summarized.
        recipient: Optional recipient email address (overrides EMAIL_TO env var).

    Returns:
        True if email was sent successfully.
    """
    sender_email = os.environ.get("EMAIL_ADDRESS")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    target_email = recipient or os.environ.get("EMAIL_TO") or sender_email

    if not sender_email or not sender_password:
        raise ValueError(
            "Missing email credentials. Please set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables."
        )

    if not target_email:
        raise ValueError("Missing recipient email address. Set EMAIL_TO environment variable.")

    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    filename = os.path.basename(pdf_path)
    today_str = datetime.now().strftime("%B %d, %Y")

    # Build MIME message
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = target_email
    msg["Subject"] = f"AI Weekly Digest — {today_str}"

    body_text = (
        f"Hello,\n\n"
        f"Your AI Weekly Digest for {today_str} is ready!\n"
        f"This edition contains {article_count} curated and summarized article(s).\n\n"
        f"Please find the attached PDF report.\n\n"
        f"Best regards,\n"
        f"AI Weekly Digest Automation"
    )
    msg.attach(MIMEText(body_text, "plain"))

    # Attach PDF
    with open(pdf_path, "rb") as f:
        pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf_attachment)

    # Send email
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

    print(f"Successfully emailed digest to {target_email}")
    return True
