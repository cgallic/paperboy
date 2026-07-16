"""Daily delivery runner for active filtered-firehose subscriptions."""
from __future__ import annotations

import html
import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from paperboy.config import settings
from paperboy.db import connect, init_schema
from paperboy.email.sender import send_raw
from paperboy.firehose import build_firehose_preview
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import active_subscriptions, management_token, management_urls

logger = get_logger("firehose_delivery")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _claim_delivery(subscription_id: int, delivery_date: str) -> bool:
    init_schema()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO firehose_deliveries
                (subscription_id, delivery_date, attempted_at, status)
            VALUES (?, ?, ?, 'running')
            """,
            (subscription_id, delivery_date, _now()),
        )
        conn.commit()
        return int(cursor.rowcount) == 1
    finally:
        conn.close()


def _finish_delivery(
    subscription_id: int,
    delivery_date: str,
    status: str,
    detail: str,
    item_count: int,
) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            UPDATE firehose_deliveries
            SET completed_at = ?, status = ?, detail = ?, item_count = ?
            WHERE subscription_id = ? AND delivery_date = ?
            """,
            (_now(), status, detail[:1000], item_count, subscription_id, delivery_date),
        )
        conn.commit()
    finally:
        conn.close()


def _render_digest(
    subscription: dict[str, Any],
    preview: dict[str, Any],
    delivery_date: str,
) -> tuple[str, str, str]:
    items = preview["items"]
    token = management_token(subscription)
    manage_path, _status_path, _unsubscribe_path = management_urls(token)
    base = settings.public_url.rstrip("/")
    manage_url = f"{base}{manage_path}"
    unsubscribe_url = f"{manage_url}#unsubscribe"
    subject = f"Paperboy: {len(items)} signal{'s' if len(items) != 1 else ''} for {delivery_date}"

    lines = [
        subject,
        "",
        f"Your focus: {subscription['focus']}",
        "",
    ]
    if items:
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"{index}. {item['title']}",
                    f"   {item['source']} - {item['why']}",
                    f"   {item['url']}",
                    "",
                ]
            )
    else:
        lines.extend(["No items cleared your filter today.", ""])
    lines.extend([f"Manage: {manage_url}", f"Unsubscribe: {unsubscribe_url}"])

    cards = []
    for item in items:
        cards.append(
            "<li style=\"margin:0 0 20px\">"
            f"<a href=\"{html.escape(str(item['url']), quote=True)}\"><strong>{html.escape(str(item['title']))}</strong></a>"
            f"<br><span>{html.escape(str(item['source']))} &middot; {html.escape(str(item['why']))}</span>"
            "</li>"
        )
    item_markup = "".join(cards) if cards else "<p>No items cleared your filter today.</p>"
    body_html = (
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;max-width:680px;margin:32px auto;line-height:1.5\">"
        f"<h1 style=\"font-size:24px\">{html.escape(subject)}</h1>"
        f"<p><strong>Your focus:</strong> {html.escape(str(subscription['focus']))}</p>"
        f"<ol>{item_markup}</ol>"
        f"<p><a href=\"{html.escape(manage_url, quote=True)}\">Manage your firehose</a> &middot; "
        f"<a href=\"{html.escape(unsubscribe_url, quote=True)}\">Unsubscribe</a></p>"
        "</body></html>"
    )
    return subject, "\n".join(lines), body_html


def run_daily_deliveries(
    *,
    delivery_day: date | None = None,
    preview_builder: Callable[[list[str], str, list[str]], dict[str, Any]] | None = None,
    sender: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Deliver at most one digest per active subscription per UTC date."""
    day = (delivery_day or datetime.now(timezone.utc).date()).isoformat()
    build_preview = preview_builder or build_firehose_preview
    send = sender or send_raw
    summary = {"active": 0, "sent": 0, "failed": 0, "skipped": 0}

    for subscription in active_subscriptions():
        summary["active"] += 1
        subscription_id = int(subscription["id"])
        if not _claim_delivery(subscription_id, day):
            summary["skipped"] += 1
            continue
        item_count = 0
        try:
            preview = build_preview(
                list(subscription["sources"]),
                str(subscription["focus"]),
                list(subscription["ignore"]),
            )
            item_count = len(preview["items"])
            subject, text, body_html = _render_digest(subscription, preview, day)
            result = send(subject, text, body_html, to=str(subscription["email"]))
            status = "sent" if result.get("ok") else "failed"
            detail = str(result.get("detail", status))
        except Exception as exc:
            logger.exception(
                "firehose_delivery_failed",
                extra={"event": "firehose_delivery_failed", "subscription_id": subscription_id},
            )
            status = "failed"
            detail = f"{type(exc).__name__}: {exc}"
        _finish_delivery(subscription_id, day, status, detail, item_count)
        summary[status] += 1

    logger.info("firehose_delivery_complete", extra={"event": "firehose_delivery_complete", **summary})
    return summary


def main() -> None:
    configure_logging()
    print(json.dumps(run_daily_deliveries(), sort_keys=True))


if __name__ == "__main__":
    main()
