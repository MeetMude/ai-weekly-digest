import base64
import requests

def send_email_digest(pdf_path: str, article_count: int, recipient: str = None) -> bool:
    sender_email = os.environ.get("EMAIL_ADDRESS")
    target_email = recipient or os.environ.get("EMAIL_TO") or sender_email
    if not target_email:
        raise ValueError("Missing recipient email address.")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    filename = os.path.basename(pdf_path)
    today_str = datetime.now().strftime("%B %d, %Y")
    subject = f"AI Weekly Digest — {today_str}"
    body_text = (
        f"Hello,\n\nYour AI Weekly Digest for {today_str} is ready!\n"
        f"This edition contains {article_count} curated and summarized article(s).\n\n"
        f"Please find the attached PDF report.\n\nBest regards,\nAI Weekly Digest Automation"
    )

    brevo_key = os.environ.get("BREVO_API_KEY")
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
        resp.raise_for_status()
        print(f"Successfully emailed digest to {target_email} via Brevo")
        return True

    # ---- existing SMTP path (works locally, blocked on Render free) ----
    # keep your original code here, but add timeout=20 to SMTP/SMTP_SSL
