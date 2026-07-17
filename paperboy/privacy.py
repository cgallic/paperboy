"""Paperboy retention enforcement and verified subscriber-erasure tooling."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from paperboy.db import connect, init_schema


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def run_retention(*, now: datetime | None = None) -> dict[str, int]:
    """Purge expired tracking data and age out privacy-sensitive product telemetry."""
    now = now or datetime.now(timezone.utc)
    init_schema()
    conn = connect()
    counts: dict[str, int] = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "DELETE FROM firehose_tracking_events WHERE token_id IN "
            "(SELECT id FROM firehose_tracking_tokens WHERE expires_at <= ?)",
            (_iso(now),),
        )
        counts["tracking_events"] = int(cursor.rowcount)
        cursor = conn.execute(
            "DELETE FROM firehose_tracking_tokens WHERE expires_at <= ?", (_iso(now),)
        )
        counts["tracking_tokens"] = int(cursor.rowcount)

        telemetry_rules = (
            ("visit", 30),
            ("analytics_event", 400),
        )
        counts["telemetry_events"] = 0
        for event_type, retention_days in telemetry_rules:
            cutoff = _iso(now - timedelta(days=retention_days))
            ids = [
                int(row[0])
                for row in conn.execute(
                    "SELECT id FROM events WHERE source='paperboy-api' AND type=? AND ingested_at < ?",
                    (event_type, cutoff),
                )
            ]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"DELETE FROM event_tags WHERE event_id IN ({placeholders})", ids)
                cursor = conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids)
                counts["telemetry_events"] += int(cursor.rowcount)

        long_cutoff = _iso(now - timedelta(days=400))
        cursor = conn.execute(
            "DELETE FROM email_provider_events WHERE received_at < ? AND status IN ('processed','ignored')",
            (long_cutoff,),
        )
        counts["provider_events"] = int(cursor.rowcount)
        cursor = conn.execute(
            "DELETE FROM product_lifecycle_outbox WHERE created_at < ? AND status='delivered'",
            (long_cutoff,),
        )
        counts["lifecycle_events"] = int(cursor.rowcount)
        conn.commit()
        return counts
    finally:
        conn.close()


def _payload_references_subscriber(raw: str, email: str, subscription_id: int) -> bool:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False

    def contains(value: Any, key: str = "") -> bool:
        if isinstance(value, dict):
            return any(contains(child, str(child_key)) for child_key, child in value.items())
        if isinstance(value, list):
            return any(contains(child, key) for child in value)
        if key == "email" and isinstance(value, str):
            return value.casefold() == email.casefold()
        if key in {"subscription_id", "paperboy_subscription_id"}:
            return str(value) == str(subscription_id)
        return False

    return contains(payload)


def erase_subscriber(email: str) -> dict[str, int]:
    """Erase one inactive subscriber and locally held dependent PII."""
    normalized = email.strip().casefold()
    if "@" not in normalized:
        raise ValueError("a valid subscriber email is required")
    init_schema()
    conn = connect()
    counts: dict[str, int] = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        subscription = conn.execute(
            "SELECT id,billing_status FROM firehose_subscriptions WHERE email=?", (normalized,)
        ).fetchone()
        if subscription is None:
            conn.rollback()
            return {"subscriptions": 0}
        if str(subscription["billing_status"]) in {"trialing", "active", "past_due"}:
            raise ValueError("cancel the Stripe subscription before erasing local subscriber data")
        subscription_id = int(subscription["id"])

        event_ids: list[int] = []
        actor_prefix = f"subscription:{subscription_id}"
        for row in conn.execute("SELECT id,actor,payload_json FROM events"):
            actor = str(row["actor"] or "")
            if actor.startswith(actor_prefix) or _payload_references_subscriber(
                str(row["payload_json"]), normalized, subscription_id
            ):
                event_ids.append(int(row["id"]))
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            conn.execute(f"DELETE FROM event_tags WHERE event_id IN ({placeholders})", event_ids)
            counts["events"] = int(
                conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", event_ids).rowcount
            )
        else:
            counts["events"] = 0

        for name, statement, parameters in (
            (
                "tracking_events",
                "DELETE FROM firehose_tracking_events WHERE subscription_id=?",
                (subscription_id,),
            ),
            (
                "tracking_tokens",
                "DELETE FROM firehose_tracking_tokens WHERE subscription_id=?",
                (subscription_id,),
            ),
            (
                "provider_events",
                "DELETE FROM email_provider_events WHERE subscription_id=?",
                (subscription_id,),
            ),
            (
                "lifecycle_events",
                "DELETE FROM product_lifecycle_outbox WHERE subscription_id=?",
                (subscription_id,),
            ),
            (
                "deliveries",
                "DELETE FROM firehose_deliveries WHERE subscription_id=?",
                (subscription_id,),
            ),
            (
                "suppressions",
                "DELETE FROM firehose_suppressions WHERE email=?",
                (normalized,),
            ),
        ):
            counts[name] = int(conn.execute(statement, parameters).rowcount)
        counts["subscriptions"] = int(
            conn.execute("DELETE FROM firehose_subscriptions WHERE id=?", (subscription_id,)).rowcount
        )
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("purge", help="apply automatic retention windows")
    erase = subparsers.add_parser("erase", help="erase one canceled/unpaid subscriber")
    email_group = erase.add_mutually_exclusive_group(required=True)
    email_group.add_argument("--email")
    email_group.add_argument("--email-stdin", action="store_true")
    erase.add_argument("--confirm", action="store_true", required=True)
    args = parser.parse_args()
    command = args.command or "purge"
    if command == "purge":
        result = run_retention()
    else:
        email = sys.stdin.readline().strip() if args.email_stdin else str(args.email)
        result = erase_subscriber(email)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
