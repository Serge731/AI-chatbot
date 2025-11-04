# app/utils/email.py
"""
Email utilities for sending password reset emails.
- In development, prints the reset link to the console.
- In production, uses SMTP (configurable via environment variables).
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Load config from environment
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")  # where reset-password.tsx lives


def send_password_reset_email(email: str, token: str):
    """
    Sends a password reset email with the reset link.
    Falls back to console logging if SMTP is not configured.
    """
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}&email={email}"

    # If SMTP config is missing → dev mode
    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD]):
        print("🔐 PASSWORD RESET (Development Mode)")
        print(f"📧 Email: {email}")
        print(f"🔗 Reset Link: {reset_link}")
        print(f"⏰ Token expires in: 1 hour")
        print("-" * 60)
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = email
        msg["Subject"] = "Password Reset Request - SergeAI"

        body = f"""
        Hello,

        You requested a password reset for your SergeAI account.

        Click here to reset your password:
        {reset_link}

        Or use this reset code: {token}

        ⚠️ This link will expire in 1 hour.

        If you didn’t request this, you can ignore this email.

        Best regards,
        SergeAI Team
        """

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Password reset email sent to: {email}")

    except Exception as e:
        print(f"❌ Failed to send password reset email: {str(e)}")
