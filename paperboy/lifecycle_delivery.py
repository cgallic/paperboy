"""Durable Paperboy lifecycle forwarding to the KaiBuilds attribution ledger."""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from paperboy.config import settings
from paperboy.db import connect, init_schema
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import get_subscription_by_id

logger = get_logger("lifecycle_delivery")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def enqueue_lifecycle_event(
    event_key: str,
    subscription_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Queue a de-duplicated attribution event without storing another email copy."""
    if not event_key or subscription_id <= 0 or not event_type:
        raise ValueError("event key, subscription id, and event type are required")
    init_schema()
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO product_lifecycle_outbox "
            "(event_key, subscription_id, event_type, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event_key[:200],
                subscription_id,
                event_type[:80],
                json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")),
                _iso(_utc_now()),
            ),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _claim_pending(limit: int, now: datetime) -> list[sqlite3.Row]:
    conn = connect()
    try:
        stale = _iso(now - timedelta(minutes=15))
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE product_lifecycle_outbox SET status='failed', claimed_at=NULL, "
            "next_attempt_at=? WHERE status='processing' AND claimed_at < ?",
            (_iso(now), stale),
        )
        rows = conn.execute(
            "SELECT * FROM product_lifecycle_outbox "
            "WHERE status IN ('pending','failed') "
            "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "ORDER BY created_at, id LIMIT ?",
            (_iso(now), limit),
        ).fetchall()
        if rows:
            placeholders = ",".join("?" for _ in rows)
            conn.execute(
                f"UPDATE product_lifecycle_outbox SET status='processing', claimed_at=? "
                f"WHERE id IN ({placeholders})",
                (_iso(now), *(int(row["id"]) for row in rows)),
            )
        conn.commit()
        return rows
    finally:
        conn.close()


def _finish(row_id: int, *, delivered: bool, detail: str = "") -> None:
    now = _utc_now()
    conn = connect()
    try:
        if delivered:
            conn.execute(
                "UPDATE product_lifecycle_outbox SET status='delivered', delivered_at=?, "
                "claimed_at=NULL, last_error='' WHERE id=?",
                (_iso(now), row_id),
            )
        else:
            attempts = int(
                conn.execute(
                    "SELECT attempt_count FROM product_lifecycle_outbox WHERE id=?", (row_id,)
                ).fetchone()[0]
            ) + 1
            delay_minutes = min(24 * 60, 5 * (2 ** min(attempts - 1, 8)))
            conn.execute(
                "UPDATE product_lifecycle_outbox SET status='failed', attempt_count=?, "
                "next_attempt_at=?, claimed_at=NULL, last_error=? WHERE id=?",
                (
                    attempts,
                    _iso(now + timedelta(minutes=delay_minutes)),
                    detail[:240],
                    row_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _post(payload: dict[str, Any]) -> bool:
    if not settings.kaibuilds_capture_url:
        return False
    request = urllib.request.Request(
        settings.kaibuilds_capture_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return 200 <= int(response.status) < 300


def deliver_pending(
    *,
    limit: int = 50,
    sender: Callable[[dict[str, Any]], bool] = _post,
    now: datetime | None = None,
) -> dict[str, int]:
    """Deliver due lifecycle events and retain failures for exponential retry."""
    now = now or _utc_now()
    summary = {"claimed": 0, "delivered": 0, "failed": 0, "skipped": 0}
    if not settings.kaibuilds_capture_url and sender is _post:
        summary["skipped"] = 1
        return summary
    for row in _claim_pending(limit, now):
        summary["claimed"] += 1
        subscription = get_subscription_by_id(int(row["subscription_id"]))
        if subscription is None:
            _finish(int(row["id"]), delivered=False, detail="subscription_missing")
            summary["failed"] += 1
            continue
        extra = json.loads(str(row["payload_json"]))
        attribution = subscription.get("attribution", {})
        payload = {
            "slug": "paperboy",
            "email": subscription["email"],
            "source": f"paperboy_{row['event_type']}",
            "page": settings.public_url,
            "offer": f"{settings.stripe_trial_days}-day trial",
            "price": (
                f"{settings.stripe_monthly_price_cents / 100:g} "
                f"{settings.stripe_currency.upper()}/month"
            ),
            "lifecycle_event": row["event_type"],
            "paperboy_subscription_id": int(row["subscription_id"]),
            "cadence": subscription["cadence"],
            "weekly_day": subscription["weekly_day"],
            **{
                key: value
                for key, value in attribution.items()
                if key.startswith("utm_") or key in {"ref", "gclid", "fbclid"}
            },
            **extra,
        }
        try:
            delivered = bool(sender(payload))
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            delivered = False
            detail = type(exc).__name__
        else:
            detail = "capture_rejected" if not delivered else ""
        _finish(int(row["id"]), delivered=delivered, detail=detail)
        summary["delivered" if delivered else "failed"] += 1
    return summary


def main() -> None:
    configure_logging()
    started = time.monotonic()
    summary = deliver_pending()
    logger.info(
        "lifecycle_delivery_end",
        extra={
            "event": "lifecycle_delivery_end",
            **summary,
            "elapsed_sec": round(time.monotonic() - started, 3),
        },
    )
    print(json.dumps(summary, sort_keys=True))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
