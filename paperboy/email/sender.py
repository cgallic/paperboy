"""Email delivery for the Paperboy Daily Intelligence Brief.

Supports SMTP (plain, STARTTLS, or SSL) and is SendGrid-ready
via SMTP relay.  Renders plain-text + HTML from a BriefEdition
and sends via the configured SMTP server.
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from paperboy.config import settings
from paperboy.daily_brief.brief import render_html, render_text, subject_for
from paperboy.daily_brief.models import BriefEdition
from paperboy.logging_config import get_logger

logger = get_logger("email")


def _create_smtp_connection() -> smtplib.SMTP | smtplib.SMTP_SSL:
    host = settings.smtp_host
    port = settings.smtp_port
    if not host:
        raise RuntimeError("SMTP_HOST is not configured")
    context = ssl.create_default_context()
    if port == 465:
        return smtplib.SMTP_SSL(host, port, context=context, timeout=30)
    conn = smtplib.SMTP(host, port, timeout=30)
    conn.starttls(context=context)
    return conn


def send_edition(
    edition: BriefEdition,
    to: str | None = None,
    from_addr: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Send a BriefEdition as a multipart email.

    Returns {"ok": bool, "detail": str, "message_id": str|None}.
    """
    to_addr = to or settings.email_to
    from_address = from_addr or settings.email_from
    if not to_addr:
        return {"ok": False, "detail": "no recipient configured", "message_id": None}

    subject = subject_for(edition)
    text = render_text(edition)
    html = render_html(edition)
    if subject is None or text is None or html is None:
        return {"ok": False, "detail": "render_failed", "message_id": None}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to_addr
    msg["X-Paperboy-Edition"] = edition.config.policy_version
    msg["X-Paperboy-Hash"] = edition.candidate_hash
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if dry_run:
        logger.info("email_dry_run", extra={"event": "email_dry_run", "to": to_addr, "subject": subject})
        return {"ok": True, "detail": "dry_run", "message_id": None}

    try:
        with _create_smtp_connection() as conn:
            if settings.smtp_user and settings.smtp_pass:
                conn.login(settings.smtp_user, settings.smtp_pass)
            conn.sendmail(from_address, [to_addr], msg.as_string())
        logger.info("email_sent", extra={"event": "email_sent", "to": to_addr, "subject": subject})
        return {"ok": True, "detail": "sent", "message_id": None}
    except smtplib.SMTPException as exc:
        logger.error("email_failed", extra={"event": "email_failed", "error": str(exc)})
        return {"ok": False, "detail": f"smtp_error: {exc}", "message_id": None}
    except Exception as exc:
        logger.error("email_failed", extra={"event": "email_failed", "error": str(exc)})
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}", "message_id": None}


def send_raw(
    subject: str,
    body_text: str,
    body_html: str | None = None,
    to: str | None = None,
    from_addr: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Send a raw multipart email."""
    to_addr = to or settings.email_to
    from_address = from_addr or settings.email_from
    if not to_addr:
        return {"ok": False, "detail": "no recipient configured", "message_id": None}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to_addr
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    if dry_run:
        logger.info("email_dry_run", extra={"event": "email_dry_run", "to": to_addr, "subject": subject})
        return {"ok": True, "detail": "dry_run", "message_id": None}

    try:
        with _create_smtp_connection() as conn:
            if settings.smtp_user and settings.smtp_pass:
                conn.login(settings.smtp_user, settings.smtp_pass)
            conn.sendmail(from_address, [to_addr], msg.as_string())
        logger.info("email_sent", extra={"event": "email_sent", "to": to_addr, "subject": subject})
        return {"ok": True, "detail": "sent", "message_id": None}
    except Exception as exc:
        logger.error("email_failed", extra={"event": "email_failed", "error": str(exc)})
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}", "message_id": None}
