"""
mailer.py

Utility for sending AI Weekly Digest PDF attachments via email.

Two delivery methods:
  1. Brevo HTTPS API (used when BREVO_API_KEY is set) - works on Render free tier.
  2. SMTP via smtplib (fallback) - works locally, but blocked on Render free tier.

Environment variables:
  - EMAIL_ADDRESS   (sender; must be a verified sender in Brevo)
  - BREVO_API_KEY   (enables the Brevo HTTPS path)
  - EMAIL_PASSWORD  (only needed for the SMTP fallback)
  - EMAIL_TO        (optional, defaults to EMAIL_ADDRESS)
  - SMTP_SERVER     (optional, defaults to smtp.gmail.com)
  - SMTP_PORT       (optional, defaults to 587)
"""

import base64
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


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
    brevo_key = os.environ.get("BREVO_API_KEY")
    target_email = recipient or os.environ.get("EMAIL_TO") or sender_email

    if not sender_email:
        raise ValueError("Missing EMAIL_ADDRESS environment variable.")
    if not target_email:
        raise ValueError("Missing recipient email address. Set EMAIL_TO environment variable.")
    if not brevo_key and not sender_password:
        raise ValueError(
            "Set BREVO_API_KEY (recommended on Render) or EMAIL_PASSWORD (SMTP fallback)."
        )
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    filename = os.path.basename(pdf_path)
    today_str = datetime.now().strftime("%B %d, %Y")
    subject = f"AI Weekly Digest — {today_str}"
    body_text = (
        f"Hello,\n\n"
        f"Your AI Weekly Digest for {today_str} is ready!\n"
        f"This edition contains {article_count} curated and summarized article(s).\n\n"
        f"Please find the attached PDF report.\n\n"
        f"Best regards,\n"
        f"AI Weekly Digest Automation"
    )

    # ---- Path 1: Brevo HTTPS API (works on Render free tier) ----
    if brevo_key:
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode()

        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender": {"name": "AI Weekly Digest", "email": sender_email},
                "to": [{"email": target_email}],
                "subject": subject,
                "textContent": body_text,
                "attachment": [{"name": filename, "content": pdf_b64}],
            },
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Brevo API error {resp.status_code}: {resp.text}")
        print(f"Successfully emailed digest to {target_email} via Brevo")
        return True

    # ---- Path 2: SMTP fallback (local use; blocked on Render free tier) ----
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = target_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    with open(pdf_path, "rb") as f:
        pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf_attachment)

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

    print(f"Successfully emailed digest to {target_email} via SMTP")
    return True
