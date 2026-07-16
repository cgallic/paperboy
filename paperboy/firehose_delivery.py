"""Timezone-aware daily firehose delivery with bounded retries."""
from __future__ import annotations

import html
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import make_msgid
from typing import Any

from paperboy.config import settings
from paperboy.db import connect, init_schema
from paperboy.email.sender import send_raw
from paperboy.firehose import build_firehose_preview
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import (
    active_subscriptions,
    create_tracking_token,
    delivery_date_if_due,
    management_token,
    management_urls,
)

logger = get_logger("firehose_delivery")


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DeliveryClaim:
    delivery_id: int
    attempt_count: int
    message_id: str


def _claim_delivery(
    subscription_id: int, delivery_date: str, *, now: datetime | None = None
) -> DeliveryClaim | None:
    """Claim a new/retry attempt without ever reclaiming a successful send."""
    init_schema()
    now_dt = _utc_now(now)
    now_iso = _iso(now_dt)
    stale_before = _iso(now_dt - timedelta(minutes=30))
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM firehose_deliveries WHERE subscription_id = ? AND delivery_date = ?",
            (subscription_id, delivery_date),
        ).fetchone()
        if row is None:
            message_id = make_msgid(
                idstring=f"firehose-{subscription_id}-{delivery_date}",
                domain="paperboy.kaibuilds.com",
            )
            cursor = conn.execute(
                """
                INSERT INTO firehose_deliveries
                    (subscription_id, delivery_date, attempted_at, status,
                     attempt_count, message_id)
                VALUES (?, ?, ?, 'running', 1, ?)
                """,
                (subscription_id, delivery_date, now_iso, message_id),
            )
            delivery_id = int(cursor.lastrowid or 0)
            conn.commit()
            return DeliveryClaim(delivery_id, 1, message_id)

        status = str(row["status"])
        attempts = int(row["attempt_count"])
        if status == "sent" or attempts >= 3:
            conn.commit()
            return None
        if status == "running" and str(row["attempted_at"]) > stale_before:
            conn.commit()
            return None
        next_attempt = row["next_attempt_at"]
        if status == "failed" and next_attempt is not None and str(next_attempt) > now_iso:
            conn.commit()
            return None

        attempts += 1
        message_id = str(row["message_id"] or "") or make_msgid(
            idstring=f"firehose-{subscription_id}-{delivery_date}",
            domain="paperboy.kaibuilds.com",
        )
        conn.execute(
            """
            UPDATE firehose_deliveries
            SET attempted_at = ?, completed_at = NULL, status = 'running', detail = '',
                attempt_count = ?, next_attempt_at = NULL, message_id = ?
            WHERE id = ?
            """,
            (now_iso, attempts, message_id, row["id"]),
        )
        conn.commit()
        return DeliveryClaim(int(row["id"]), attempts, message_id)
    finally:
        conn.close()


def _finish_delivery(
    claim: DeliveryClaim,
    status: str,
    detail: str,
    item_count: int,
    *,
    now: datetime | None = None,
) -> None:
    now_dt = _utc_now(now)
    next_attempt = None
    if status == "failed" and claim.attempt_count < 3:
        next_attempt = _iso(now_dt + timedelta(minutes=15 * (2 ** (claim.attempt_count - 1))))
    conn = connect()
    try:
        conn.execute(
            """
            UPDATE firehose_deliveries
            SET completed_at = ?, status = ?, detail = ?, item_count = ?, next_attempt_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (_iso(now_dt), status, detail[:1000], item_count, next_attempt, claim.delivery_id),
        )
        conn.commit()
    finally:
        conn.close()


def _render_digest(
    subscription: dict[str, Any],
    preview: dict[str, Any],
    delivery_date: str,
    delivery_id: int,
) -> tuple[str, str, str, str]:
    items = preview["items"]
    token = management_token(subscription)
    manage_path, _status_path, unsubscribe_path = management_urls(token)
    base = settings.public_url.rstrip("/")
    manage_url = f"{base}{manage_path}"
    unsubscribe_url = f"{base}{unsubscribe_path}"
    subject = f"Paperboy: {len(items)} signal{'s' if len(items) != 1 else ''} for {delivery_date}"

    analytics_consent = bool(subscription.get("attribution", {}).get("_analytics_consent"))
    tracked_items: list[tuple[dict[str, Any], str]] = []
    for item in items:
        item_url = str(item["url"])
        if analytics_consent:
            click_token = create_tracking_token(
                int(subscription["id"]),
                "click",
                delivery_id=delivery_id,
                target_url=item_url,
            )
            item_url = f"{base}/api/t/c/{click_token}"
        tracked_items.append((item, item_url))
    open_markup = ""
    if analytics_consent:
        open_token = create_tracking_token(
            int(subscription["id"]), "open", delivery_id=delivery_id
        )
        open_url = f"{base}/api/t/o/{open_token}.gif"
        open_markup = (
            f'<img src="{html.escape(open_url, quote=True)}" width="1" height="1" '
            'alt="" style="display:none">'
        )

    lines = [subject, "", f"Your focus: {subscription['focus']}", ""]
    if tracked_items:
        for index, (item, click_url) in enumerate(tracked_items, start=1):
            lines.extend(
                [
                    f"{index}. {item['title']}",
                    f"   {item['source']} - {item['why']}",
                    f"   {click_url}",
                    "",
                ]
            )
    else:
        lines.extend(["No items cleared your filter today.", ""])
    lines.extend([f"Manage: {manage_url}", f"Unsubscribe: {unsubscribe_url}"])

    cards = []
    for item, click_url in tracked_items:
        cards.append(
            '<li style="margin:0 0 20px">'
            f'<a href="{html.escape(click_url, quote=True)}"><strong>{html.escape(str(item["title"]))}</strong></a>'
            f"<br><span>{html.escape(str(item['source']))} &middot; {html.escape(str(item['why']))}</span>"
            "</li>"
        )
    item_markup = "".join(cards) if cards else "<p>No items cleared your filter today.</p>"
    body_html = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:680px;margin:32px auto;line-height:1.5">'
        f'<h1 style="font-size:24px">{html.escape(subject)}</h1>'
        f"<p><strong>Your focus:</strong> {html.escape(str(subscription['focus']))}</p>"
        f"<ol>{item_markup}</ol>"
        f'<p><a href="{html.escape(manage_url, quote=True)}">Manage your firehose</a> &middot; '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p>'
        f"{open_markup}"
        "</body></html>"
    )
    return subject, "\n".join(lines), body_html, unsubscribe_url


def run_daily_deliveries(
    *,
    delivery_day: date | None = None,
    now: datetime | None = None,
    preview_builder: Callable[[list[str], str, list[str]], dict[str, Any]] | None = None,
    sender: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Deliver due 08:00-local editions with at most three failed attempts."""
    now_dt = _utc_now(now)
    build_preview = preview_builder or build_firehose_preview
    send = sender or send_raw
    summary = {"active": 0, "sent": 0, "failed": 0, "skipped": 0}

    for subscription in active_subscriptions():
        summary["active"] += 1
        due_date = delivery_day or delivery_date_if_due(subscription, now=now_dt)
        if due_date is None:
            summary["skipped"] += 1
            continue
        day = due_date.isoformat()
        claim = _claim_delivery(int(subscription["id"]), day, now=now_dt)
        if claim is None:
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
            subject, text, body_html, unsubscribe_url = _render_digest(
                subscription, preview, day, claim.delivery_id
            )
            result = send(
                subject,
                text,
                body_html,
                to=str(subscription["email"]),
                unsubscribe_url=unsubscribe_url,
                message_id=claim.message_id,
            )
            status = "sent" if result.get("ok") else "failed"
            detail = str(result.get("detail", status))
        except Exception as exc:
            logger.exception(
                "firehose_delivery_failed",
                extra={"event": "firehose_delivery_failed", "subscription_id": subscription["id"]},
            )
            status = "failed"
            detail = f"{type(exc).__name__}: {exc}"
        _finish_delivery(claim, status, detail, item_count, now=now_dt)
        summary[status] += 1

    logger.info(
        "firehose_delivery_complete", extra={"event": "firehose_delivery_complete", **summary}
    )
    return summary


def main() -> None:
    configure_logging()
    print(json.dumps(run_daily_deliveries(), sort_keys=True))


if __name__ == "__main__":
    main()
