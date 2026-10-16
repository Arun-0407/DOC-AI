"""
Email service — sends password reset emails via SMTP.
Supports Gmail (TLS on port 587) and any other SMTP provider.
Falls back to logging when SMTP is not configured (dev mode).

IMPORTANT: SMTP calls run in a thread-pool executor so they never block
the FastAPI async event loop.
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial

from app.config import settings

logger = logging.getLogger(__name__)


def _build_reset_email(to_email: str, full_name: str, reset_link: str) -> MIMEMultipart:
    """Build a professional HTML + plain-text reset email."""
    msg = MIMEMultipart("alternative")
    from_address = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg["Subject"] = "Reset your DocGen AI password"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_address}>"
    msg["To"] = to_email

    plain = (
        f"Hi {full_name},\n\n"
        f"We received a request to reset your DocGen AI password.\n\n"
        f"Click the link below to choose a new password "
        f"(valid for {settings.PASSWORD_RESET_EXPIRY_MINUTES} minutes):\n\n"
        f"{reset_link}\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n\n"
        f"– The DocGen AI Team"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Reset Password</title></head>
<body style="margin:0;padding:0;background:#0A1628;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0A1628;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#162240;border-radius:16px;border:1px solid rgba(255,255,255,0.08);">
        <tr>
          <td style="padding:32px 40px;background:linear-gradient(135deg,#0F4C81,#1B6CB0);text-align:center;">
            <div style="font-weight:700;font-size:14px;color:#fff;background:rgba(255,255,255,0.15);
                        display:inline-block;padding:10px 16px;border-radius:10px;margin-bottom:10px;">SAP</div>
            <h1 style="margin:0;font-size:22px;font-weight:700;color:#fff;">DocGen AI</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:40px;">
            <h2 style="margin:0 0 8px;font-size:20px;color:#e2e8f0;">Reset your password</h2>
            <p style="margin:0 0 24px;font-size:14px;color:#94a3b8;line-height:1.6;">
              Hi <strong style="color:#e2e8f0;">{full_name}</strong>, we received a request to reset
              the password for your DocGen AI account.
            </p>
            <div style="text-align:center;margin:32px 0;">
              <a href="{reset_link}"
                 style="display:inline-block;padding:14px 36px;background:#1B6CB0;color:#fff;
                        font-weight:600;font-size:15px;border-radius:10px;text-decoration:none;">
                Reset Password
              </a>
            </div>
            <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;">Or copy and paste this link:</p>
            <p style="margin:0 0 24px;font-size:11px;color:#1B6CB0;word-break:break-all;">{reset_link}</p>
            <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:16px;
                        border:1px solid rgba(255,255,255,0.06);">
              <p style="margin:0;font-size:13px;color:#64748b;line-height:1.6;">
                This link expires in <strong style="color:#94a3b8;">{settings.PASSWORD_RESET_EXPIRY_MINUTES} minutes</strong>.<br>
                If you didn't request this, you can safely ignore this email.
              </p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center;">
            <p style="margin:0;font-size:12px;color:#475569;">© 2024 DocGen AI · AI-Powered SAP Documentation</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


async def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    """
    Send a password reset email.
    Returns True on success, False on failure.
    Logs the reset link to console when SMTP is not configured (dev fallback).
    """
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("[EMAIL DEV MODE] Password reset link for %s:\n  %s", to_email, reset_link)
        return True

    try:
        msg = _build_reset_email(to_email, full_name, reset_link)
        msg_str = msg.as_string()
        from_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USER

        def _send_sync() -> None:
            """Blocking SMTP call — runs in a thread-pool executor."""
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(from_addr, to_email, msg_str)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync)
        logger.info("Password reset email sent to %s", to_email)
        return True
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending reset email to %s: %s", to_email, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error sending reset email to %s: %s", to_email, exc)
        return False
