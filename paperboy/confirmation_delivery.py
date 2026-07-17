"""Send queued double-opt-in confirmation messages with bounded retries."""
from __future__ import annotations

import html
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from paperboy.email.sender import send_raw
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import (
    bounce_address,
    claim_pending_confirmations,
    confirmation_token,
    confirmation_url,
    finish_confirmation_attempt,
)

logger = get_logger("confirmation_delivery")


def _render_confirmation(subscription: dict[str, Any]) -> tuple[str, str, str]:
    url = confirmation_url(confirmation_token(subscription))
    subject = "Confirm your Paperboy firehose"
    text = "\n".join(
        [
            "Confirm your Paperboy firehose",
            "",
            f"Focus: {subscription['focus']}",
            "",
            f"Confirm: {url}",
            "",
            "This link expires in 48 hours. Ignore this email if you did not request it.",
        ]
    )
    body_html = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:640px;margin:32px auto;line-height:1.5">'
        "<h1>Confirm your Paperboy firehose</h1>"
        f"<p><strong>Focus:</strong> {html.escape(str(subscription['focus']))}</p>"
        f'<p><a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:12px 18px;'
        'background:#0b57d0;color:#fff;text-decoration:none;border-radius:6px">Confirm my email</a></p>'
        "<p>This link expires in 48 hours. Ignore this email if you did not request it.</p>"
        "</body></html>"
    )
    return subject, text, body_html


def run_pending_confirmations(
    *,
    sender: Callable[..., dict[str, Any]] | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Send one claimed batch; failed sends are retried at most three times."""
    send = sender or send_raw
    subscriptions = claim_pending_confirmations(now=now, limit=limit)
    summary = {"claimed": len(subscriptions), "sent": 0, "failed": 0}
    for subscription in subscriptions:
        try:
            subject, text, body_html = _render_confirmation(subscription)
            result = send(
                subject,
                text,
                body_html,
                to=str(subscription["email"]),
                envelope_from=bounce_address(subscription),
            )
            ok = bool(result.get("ok"))
            detail = str(result.get("detail", "sent" if ok else "failed"))
        except Exception as exc:
            logger.exception(
                "confirmation_delivery_failed",
                extra={"event": "confirmation_delivery_failed", "subscription_id": subscription["id"]},
            )
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
        finish_confirmation_attempt(int(subscription["id"]), ok, detail, now=now)
        summary["sent" if ok else "failed"] += 1
    logger.info(
        "confirmation_delivery_complete",
        extra={"event": "confirmation_delivery_complete", **summary},
    )
    return summary


def main() -> None:
    configure_logging()
    print(json.dumps(run_pending_confirmations(), sort_keys=True))


if __name__ == "__main__":
    main()
