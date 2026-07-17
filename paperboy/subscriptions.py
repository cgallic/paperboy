"""Durable, verified subscriptions and delivery-support primitives."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from paperboy.config import settings
from paperboy.db import connect, init_schema, root
from paperboy.firehose import PreviewValidationError, validate_preview_payload

_ATTRIBUTION_KEYS = {"source", "page", "ref", "gclid", "fbclid"}
_BILLING_STATUSES = {"unpaid", "trialing", "active", "past_due", "canceled"}
_VERIFICATION_TTL = timedelta(hours=48)
_WEBHOOK_PROCESSING_LEASE = timedelta(minutes=10)
_DELIVERY_HOUR = 8
_CADENCES = {"daily", "weekly"}
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class SubscriptionValidationError(ValueError):
    """The subscription request is invalid."""


class SubscriptionSuppressedError(SubscriptionValidationError):
    """The address has explicitly unsubscribed or was delivery-suppressed."""


class ExistingSubscriptionError(SubscriptionSuppressedError):
    """An existing verified subscription must be changed through its private link."""


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _now() -> str:
    return _iso(_utc_now())


def _valid_email(value: Any) -> str:
    if not isinstance(value, str):
        raise SubscriptionValidationError("email must be a valid email address")
    email = value.strip().casefold()
    if len(email) > 254 or email.count("@") != 1:
        raise SubscriptionValidationError("email must be a valid email address")
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise SubscriptionValidationError("email must be a valid email address")
    if any(character.isspace() for character in email):
        raise SubscriptionValidationError("email must be a valid email address")
    return email


def _valid_timezone(value: Any) -> str:
    if value is None or value == "":
        return "UTC"
    if not isinstance(value, str) or len(value) > 64:
        raise SubscriptionValidationError("timezone must be a valid IANA timezone")
    timezone_name = value.strip()
    try:
        ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise SubscriptionValidationError("timezone must be a valid IANA timezone") from exc
    return timezone_name


def _valid_cadence(value: Any) -> str:
    if value is None or value == "":
        return "daily"
    if not isinstance(value, str) or value.casefold() not in _CADENCES:
        raise SubscriptionValidationError("cadence must be daily or weekly")
    return value.casefold()


def _valid_weekly_day(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 6:
        raise SubscriptionValidationError("weekly_day must be an integer from 0 to 6")
    return int(value)


def _normalized_schedule(cadence_value: Any, weekly_day_value: Any) -> tuple[str, int]:
    cadence = _valid_cadence(cadence_value)
    weekly_day = _valid_weekly_day(weekly_day_value)
    return cadence, weekly_day if cadence == "weekly" else 0


def validate_subscription_payload(
    payload: Any,
) -> tuple[str, list[str], str, list[str], dict[str, Any], str, str, int]:
    if not isinstance(payload, dict):
        raise SubscriptionValidationError("request body must be a JSON object")
    allowed = {
        "email",
        "sources",
        "focus",
        "ignore",
        "timezone",
        "cadence",
        "weekly_day",
        "consent",
        "analytics_consent",
    } | _ATTRIBUTION_KEYS
    unknown = {key for key in payload if key not in allowed and not key.startswith("utm_")}
    if unknown:
        raise SubscriptionValidationError("request contains unsupported fields")
    if payload.get("consent") is not True:
        raise SubscriptionValidationError("consent must be accepted")
    if not isinstance(payload.get("analytics_consent", False), bool):
        raise SubscriptionValidationError("analytics consent must be true or false")
    email = _valid_email(payload.get("email"))
    try:
        sources, focus, ignore = validate_preview_payload(
            {key: payload[key] for key in ("sources", "focus", "ignore") if key in payload}
        )
    except PreviewValidationError as exc:
        raise SubscriptionValidationError(str(exc)) from exc
    attribution = {key: value for key, value in payload.items() if key in _ATTRIBUTION_KEYS or key.startswith("utm_")}
    if "analytics_consent" in payload:
        attribution["_analytics_consent"] = bool(payload["analytics_consent"])
    cadence, weekly_day = _normalized_schedule(
        payload.get("cadence"), payload.get("weekly_day")
    )
    return (
        email,
        sources,
        focus,
        ignore,
        attribution,
        _valid_timezone(payload.get("timezone")),
        cadence,
        weekly_day,
    )


def _secret_path() -> Path:
    return Path(root()) / "manage-secret"


def _management_secret() -> bytes:
    configured = os.environ.get("PAPERBOY_MANAGE_SECRET")
    if configured:
        return configured.encode("utf-8")
    path = _secret_path()
    try:
        secret = path.read_bytes()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        candidate = secrets.token_bytes(32)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret = path.read_bytes()
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(candidate)
            secret = candidate
    if len(secret) < 32:
        raise RuntimeError("Paperboy management secret must be at least 32 bytes")
    return secret


def _token_for_nonce(nonce: str) -> str:
    """Build a management token; kept compatible with already-issued tokens."""
    signature = hmac.new(_management_secret(), nonce.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def _verification_token_for_nonce(nonce: str) -> str:
    signature = hmac.new(_management_secret(), f"verify:{nonce}".encode("ascii"), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_token(*, verification: bool = False) -> tuple[str, str, str]:
    nonce = secrets.token_urlsafe(32)
    token = _verification_token_for_nonce(nonce) if verification else _token_for_nonce(nonce)
    return token, nonce, _token_hash(token)


def _validated_token_hash(token: str, *, verification: bool = False) -> str | None:
    if not isinstance(token, str) or "." not in token or len(token) > 256:
        return None
    nonce, supplied_signature = token.rsplit(".", 1)
    try:
        builder = _verification_token_for_nonce if verification else _token_for_nonce
        expected = builder(nonce).rsplit(".", 1)[1]
    except (UnicodeEncodeError, RuntimeError):
        return None
    if not hmac.compare_digest(supplied_signature, expected):
        return None
    return _token_hash(token)


_SUBSCRIPTION_SELECT = """
SELECT s.*,
       (
           SELECT sent.completed_at FROM firehose_deliveries AS sent
           WHERE sent.subscription_id = s.id AND sent.status = 'sent'
           ORDER BY sent.delivery_date DESC, sent.id DESC LIMIT 1
       ) AS last_sent_at,
       (
           SELECT latest.status FROM firehose_deliveries AS latest
           WHERE latest.subscription_id = s.id
           ORDER BY latest.delivery_date DESC, latest.id DESC LIMIT 1
       ) AS last_delivery_status,
       EXISTS(
           SELECT 1 FROM firehose_suppressions AS suppression WHERE suppression.email = s.email
       ) AS suppressed
FROM firehose_subscriptions AS s
"""


def _decode_subscription(row: sqlite3.Row) -> dict[str, Any]:
    try:
        cadence, weekly_day = _normalized_schedule(row["cadence"], row["weekly_day"])
    except SubscriptionValidationError:
        cadence, weekly_day = "daily", 0
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "sources": json.loads(str(row["sources_json"])),
        "focus": str(row["focus"]),
        "ignore": json.loads(str(row["ignore_json"])),
        "attribution": json.loads(str(row["attribution_json"])),
        "token_nonce": str(row["token_nonce"]),
        "active": bool(row["active"]),
        "timezone": str(row["timezone"]),
        "cadence": cadence,
        "weekly_day": weekly_day,
        "verification_status": str(row["verification_status"]),
        "verification_token_nonce": row["verification_token_nonce"],
        "verification_expires_at": row["verification_expires_at"],
        "verification_sent_at": row["verification_sent_at"],
        "verification_attempts": int(row["verification_attempts"]),
        "verification_last_error": str(row["verification_last_error"]),
        "verified_at": row["verified_at"],
        "billing_status": str(row["billing_status"]),
        "billing_customer_id": row["billing_customer_id"],
        "billing_subscription_id": row["billing_subscription_id"],
        "trial_ends_at": row["trial_ends_at"],
        "paid_at": row["paid_at"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "unsubscribed_at": row["unsubscribed_at"],
        "last_sent_at": row["last_sent_at"],
        "last_delivery_status": row["last_delivery_status"],
        "suppressed": bool(row["suppressed"]),
    }


def _get_subscription_where(clause: str, parameters: tuple[Any, ...]) -> dict[str, Any] | None:
    init_schema()
    conn = connect()
    try:
        row = conn.execute(_SUBSCRIPTION_SELECT + f" WHERE {clause}", parameters).fetchone()
    finally:
        conn.close()
    return _decode_subscription(row) if row is not None else None


def create_subscription(
    email: str,
    sources: list[str],
    focus: str,
    ignore: list[str],
    attribution: dict[str, Any] | None = None,
    timezone_name: str = "UTC",
    cadence: str = "daily",
    weekly_day: int = 0,
) -> tuple[dict[str, Any], str]:
    """Create/replace a pending subscription and queue a confirmation email."""
    init_schema()
    email = _valid_email(email)
    timezone_name = _valid_timezone(timezone_name)
    cadence, weekly_day = _normalized_schedule(cadence, weekly_day)
    if is_suppressed(email):
        raise SubscriptionSuppressedError("email address is suppressed")
    management_token_value, management_nonce, management_hash = _new_token()
    _verification_token, verification_nonce, verification_hash = _new_token(verification=True)
    now_dt = _utc_now()
    now = _iso(now_dt)
    expires_at = _iso(now_dt + _VERIFICATION_TTL)
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, created_at, active, verification_status, billing_status "
            "FROM firehose_subscriptions WHERE email = ?",
            (email,),
        ).fetchone()
        if row is not None and (
            bool(row["active"])
            or str(row["verification_status"]) == "verified"
            or str(row["billing_status"]) in {"trialing", "active"}
        ):
            raise ExistingSubscriptionError(
                "this email already has a verified subscription; use its private management link"
            )
        values = (
            json.dumps(sources),
            focus,
            json.dumps(ignore),
            json.dumps(attribution or {}, ensure_ascii=False),
            management_hash,
            management_nonce,
            timezone_name,
            cadence,
            weekly_day,
            verification_hash,
            verification_nonce,
            expires_at,
        )
        if row is None:
            cursor = conn.execute(
                """
                INSERT INTO firehose_subscriptions
                    (email, sources_json, focus, ignore_json, attribution_json,
                     token_hash, token_nonce, active, timezone, cadence, weekly_day,
                     verification_status,
                     verification_token_hash, verification_token_nonce,
                     verification_expires_at, verification_attempts,
                     verification_next_attempt_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'pending', ?, ?, ?, 0, ?, ?, ?)
                """,
                (email, *values, now, now, now),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("subscription insert did not return an id")
            subscription_id = int(cursor.lastrowid)
        else:
            subscription_id = int(row["id"])
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET sources_json = ?, focus = ?, ignore_json = ?, attribution_json = ?,
                    token_hash = ?, token_nonce = ?, active = 0, timezone = ?,
                    cadence = ?, weekly_day = ?,
                    verification_status = 'pending', verification_token_hash = ?,
                    verification_token_nonce = ?, verification_expires_at = ?,
                    verification_sent_at = NULL, verification_attempts = 0,
                    verification_next_attempt_at = ?, verification_last_error = '',
                    verified_at = NULL, updated_at = ?, unsubscribed_at = NULL
                WHERE id = ?
                """,
                (*values, now, now, subscription_id),
            )
        conn.commit()
    finally:
        conn.close()
    subscription = get_subscription_by_id(subscription_id)
    if subscription is None:
        raise sqlite3.DatabaseError("subscription could not be reloaded")
    return subscription, management_token_value


def get_subscription(token: str) -> dict[str, Any] | None:
    token_hash = _validated_token_hash(token)
    if token_hash is None:
        return None
    return _get_subscription_where("s.token_hash = ?", (token_hash,))


def get_subscription_by_id(subscription_id: int) -> dict[str, Any] | None:
    return _get_subscription_where("s.id = ?", (subscription_id,))


def get_subscription_by_email(email: str) -> dict[str, Any] | None:
    try:
        normalized = _valid_email(email)
    except SubscriptionValidationError:
        return None
    return _get_subscription_where("s.email = ?", (normalized,))


def management_token(subscription: dict[str, Any]) -> str:
    return _token_for_nonce(str(subscription["token_nonce"]))


def confirmation_token(subscription: dict[str, Any]) -> str:
    nonce = subscription.get("verification_token_nonce")
    if not nonce:
        raise ValueError("subscription has no confirmation token")
    return _verification_token_for_nonce(str(nonce))


def confirmation_url(token: str) -> str:
    return f"{settings.public_url.rstrip('/')}/?confirm={token}"


def confirm_subscription(token: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    token_hash = _validated_token_hash(token, verification=True)
    if token_hash is None:
        return None
    now_dt = _utc_now(now)
    now_iso = _iso(now_dt)
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, verification_expires_at, verification_status FROM firehose_subscriptions "
            "WHERE verification_token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None or not row["verification_expires_at"]:
            return None
        if _parse_iso(str(row["verification_expires_at"])) < now_dt:
            conn.execute(
                "UPDATE firehose_subscriptions SET verification_status = 'expired', active = 0, "
                "updated_at = ? WHERE id = ?",
                (now_iso, row["id"]),
            )
            conn.commit()
            return None
        suppressed = conn.execute(
            "SELECT 1 FROM firehose_suppressions WHERE email = (SELECT email FROM firehose_subscriptions WHERE id = ?)",
            (row["id"],),
        ).fetchone()
        if suppressed is not None:
            return None
        newly_verified = str(row["verification_status"]) != "verified"
        conn.execute(
            """
            UPDATE firehose_subscriptions
            SET verification_status = 'verified', verified_at = COALESCE(verified_at, ?),
                active = 1, updated_at = ?
            WHERE id = ?
            """,
            (now_iso, now_iso, row["id"]),
        )
        conn.commit()
        subscription_id = int(row["id"])
    finally:
        conn.close()
    subscription = get_subscription_by_id(subscription_id)
    if subscription is not None:
        subscription["_newly_verified"] = newly_verified
    return subscription


def _seed_legacy_confirmation_tokens(conn: sqlite3.Connection, now_dt: datetime) -> None:
    rows = conn.execute(
        "SELECT id FROM firehose_subscriptions "
        "WHERE verification_status = 'pending' AND verification_token_nonce IS NULL"
    ).fetchall()
    for row in rows:
        _token, nonce, token_hash = _new_token(verification=True)
        now_iso = _iso(now_dt)
        conn.execute(
            """
            UPDATE firehose_subscriptions
            SET verification_token_hash = ?, verification_token_nonce = ?,
                verification_expires_at = ?, verification_next_attempt_at = ?,
                verification_attempts = 0, verification_last_error = '', updated_at = ?
            WHERE id = ?
            """,
            (token_hash, nonce, _iso(now_dt + _VERIFICATION_TTL), now_iso, now_iso, row["id"]),
        )


def claim_pending_confirmations(*, now: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Atomically claim pending confirmation sends for one worker lease."""
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    now_dt = _utc_now(now)
    now_iso = _iso(now_dt)
    lease_until = _iso(now_dt + timedelta(minutes=10))
    init_schema()
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _seed_legacy_confirmation_tokens(conn, now_dt)
        rows = conn.execute(
            """
            SELECT s.id FROM firehose_subscriptions AS s
            WHERE s.verification_status = 'pending'
              AND s.unsubscribed_at IS NULL
              AND s.verification_sent_at IS NULL
              AND s.verification_attempts < 3
              AND s.verification_expires_at > ?
              AND (s.verification_next_attempt_at IS NULL OR s.verification_next_attempt_at <= ?)
              AND NOT EXISTS (
                  SELECT 1 FROM firehose_suppressions suppression WHERE suppression.email = s.email
              )
            ORDER BY s.id
            LIMIT ?
            """,
            (now_iso, now_iso, limit),
        ).fetchall()
        ids = [int(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE firehose_subscriptions SET verification_attempts = verification_attempts + 1, "
                f"verification_next_attempt_at = ?, updated_at = ? WHERE id IN ({placeholders})",
                (lease_until, now_iso, *ids),
            )
        conn.commit()
    finally:
        conn.close()
    return [subscription for item in ids if (subscription := get_subscription_by_id(item))]


def finish_confirmation_attempt(subscription_id: int, ok: bool, detail: str, *, now: datetime | None = None) -> None:
    now_dt = _utc_now(now)
    now_iso = _iso(now_dt)
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT verification_attempts FROM firehose_subscriptions WHERE id = ?",
            (subscription_id,),
        ).fetchone()
        if row is None:
            return
        if ok:
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET verification_sent_at = ?, verification_next_attempt_at = NULL,
                    verification_last_error = '', updated_at = ? WHERE id = ?
                """,
                (now_iso, now_iso, subscription_id),
            )
        else:
            attempts = int(row["verification_attempts"])
            next_attempt = _iso(now_dt + timedelta(minutes=15 * (2 ** max(0, attempts - 1)))) if attempts < 3 else None
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET verification_next_attempt_at = ?, verification_last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_attempt, detail[:1000], now_iso, subscription_id),
            )
        conn.commit()
    finally:
        conn.close()


def unsubscribe(token: str) -> dict[str, Any] | None:
    subscription = get_subscription(token)
    if subscription is None:
        return None
    now = _now()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO firehose_suppressions(email, reason, detail, created_at, updated_at)
            VALUES (?, 'unsubscribe', '', ?, ?)
            ON CONFLICT(email) DO UPDATE SET reason = 'unsubscribe', detail = '', updated_at = excluded.updated_at
            """,
            (subscription["email"], now, now),
        )
        conn.execute(
            """
            UPDATE firehose_subscriptions
            SET active = 0, updated_at = ?, unsubscribed_at = ? WHERE id = ?
            """,
            (now, now, subscription["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return get_subscription_by_id(int(subscription["id"]))


def suppress_email(email: str, reason: str, detail: str = "") -> None:
    normalized = _valid_email(email)
    if not reason.strip() or len(reason) > 100:
        raise ValueError("suppression reason is required")
    now = _now()
    init_schema()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO firehose_suppressions(email, reason, detail, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET reason = excluded.reason,
                detail = excluded.detail, updated_at = excluded.updated_at
            """,
            (normalized, reason.strip(), detail[:1000], now, now),
        )
        conn.execute(
            "UPDATE firehose_subscriptions SET active = 0, updated_at = ? WHERE email = ?",
            (now, normalized),
        )
        conn.commit()
    finally:
        conn.close()


def bounce_address(subscription: dict[str, Any]) -> str:
    """Return a signed, non-PII envelope sender for bounce correlation."""
    subscription_id = int(subscription["id"])
    signature = hmac.new(_management_secret(), f"bounce:{subscription_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"paperboy-bounce+{subscription_id}.{signature}@{settings.bounce_domain}"


def suppress_from_bounce_address(address: str, detail: str = "hard bounce reported") -> bool:
    """Verify a bounce envelope recipient and suppress only its signed subscription."""
    match = re.fullmatch(
        rf"paperboy-bounce\+(\d+)\.([a-f0-9]{{32}})@{re.escape(settings.bounce_domain)}",
        address.strip().casefold(),
    )
    if match is None:
        return False
    subscription_id = int(match.group(1))
    expected = hmac.new(_management_secret(), f"bounce:{subscription_id}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(match.group(2), expected):
        return False
    subscription = get_subscription_by_id(subscription_id)
    if subscription is None:
        return False
    suppress_email(str(subscription["email"]), "hard_bounce", detail)
    return True


def unsuppress_email(email: str) -> bool:
    normalized = _valid_email(email)
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT reason FROM firehose_suppressions WHERE email = ?", (normalized,)
        ).fetchone()
        cursor = conn.execute("DELETE FROM firehose_suppressions WHERE email = ?", (normalized,))
        if row is not None and str(row["reason"]) == "hard_bounce":
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET active = CASE
                        WHEN verification_status = 'verified'
                         AND billing_status IN ('trialing', 'active')
                         AND unsubscribed_at IS NULL THEN 1
                        ELSE active
                    END,
                    updated_at = ?
                WHERE email = ?
                """,
                (_now(), normalized),
            )
        conn.commit()
        return int(cursor.rowcount) == 1
    finally:
        conn.close()


def is_suppressed(email: str) -> bool:
    normalized = _valid_email(email)
    init_schema()
    conn = connect()
    try:
        return conn.execute("SELECT 1 FROM firehose_suppressions WHERE email = ?", (normalized,)).fetchone() is not None
    finally:
        conn.close()


def active_subscriptions() -> list[dict[str, Any]]:
    """Return verified, entitled, non-suppressed subscriptions only."""
    init_schema()
    conn = connect()
    try:
        rows = conn.execute(
            _SUBSCRIPTION_SELECT
            + """
            WHERE s.active = 1 AND s.verification_status = 'verified'
              AND s.verified_at IS NOT NULL
              AND s.billing_status IN ('trialing', 'active')
              AND NOT EXISTS (
                  SELECT 1 FROM firehose_suppressions suppression WHERE suppression.email = s.email
              )
            ORDER BY s.id
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        subscription
        for row in rows
        if billing_entitled(subscription := _decode_subscription(row))
    ]


def billing_entitled(
    subscription: dict[str, Any], *, now: datetime | None = None
) -> bool:
    """Return whether Stripe state currently permits delivery."""
    status = str(subscription.get("billing_status") or "unpaid")
    if status == "active":
        return True
    if status != "trialing" or not subscription.get("trial_ends_at"):
        return False
    try:
        trial_end = _parse_iso(str(subscription["trial_ends_at"]))
    except (TypeError, ValueError):
        return False
    return trial_end > _utc_now(now)


def next_delivery_at(subscription: dict[str, Any], *, now: datetime | None = None) -> datetime:
    now_utc = _utc_now(now)
    zone = ZoneInfo(str(subscription.get("timezone") or "UTC"))
    local_now = now_utc.astimezone(zone)
    cadence = str(subscription.get("cadence") or "daily")
    if cadence == "weekly":
        weekly_day = int(subscription.get("weekly_day", 0))
        days_ahead = (weekly_day - local_now.weekday()) % 7
        candidate = datetime.combine(local_now.date() + timedelta(days=days_ahead), time(_DELIVERY_HOUR), zone)
        if candidate <= local_now:
            candidate += timedelta(days=7)
    else:
        candidate = datetime.combine(local_now.date(), time(_DELIVERY_HOUR), zone)
        if candidate <= local_now:
            candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def delivery_date_if_due(subscription: dict[str, Any], *, now: datetime | None = None) -> date | None:
    now_utc = _utc_now(now)
    zone = ZoneInfo(str(subscription.get("timezone") or "UTC"))
    local_now = now_utc.astimezone(zone)
    if local_now.time().replace(tzinfo=None) < time(_DELIVERY_HOUR):
        return None
    if str(subscription.get("cadence") or "daily") == "weekly":
        weekly_day = int(subscription.get("weekly_day", 0))
        if local_now.weekday() != weekly_day:
            return None
    return local_now.date()


def delivery_schedule_label(subscription: dict[str, Any]) -> str:
    """Return a concise, user-facing schedule in the subscription timezone."""
    timezone_name = str(subscription.get("timezone") or "UTC")
    if str(subscription.get("cadence") or "daily") == "weekly":
        weekly_day = int(subscription.get("weekly_day", 0))
        return f"Weekly · {_WEEKDAYS[weekly_day]} at 8:00 AM · {timezone_name}"
    return f"Daily · 8:00 AM · {timezone_name}"


def set_billing_state(
    subscription_id: int,
    status: str,
    *,
    customer_id: str | None = None,
    billing_subscription_id: str | None = None,
    trial_ends_at: str | None = None,
    paid_at: str | None = None,
    event_created: int | None = None,
    event_id: str | None = None,
) -> dict[str, Any] | None:
    if status not in _BILLING_STATUSES:
        raise ValueError("unsupported billing status")
    if event_created is not None and event_created < 0:
        raise ValueError("event_created must be a non-negative Unix timestamp")
    if event_created is not None and (not event_id or len(event_id) > 255):
        raise ValueError("event_id is required for an ordered billing update")
    init_schema()
    conn = connect()
    applied = True
    try:
        if event_created is not None:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT billing_status FROM firehose_subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
            if current is None:
                conn.commit()
                return None
            actor = f"subscription:{subscription_id}"
            previous = conn.execute(
                "SELECT payload_json FROM events "
                "WHERE source = 'paperboy-billing' AND type = 'state-applied' AND actor = ? "
                "ORDER BY id DESC LIMIT 1",
                (actor,),
            ).fetchone()
            previous_created: int | None = None
            if previous is not None:
                try:
                    previous_created = int(json.loads(str(previous["payload_json"]))["event_created"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    previous_created = None
            applied = not (
                previous_created is not None
                and (
                    event_created < previous_created
                    or (
                        event_created == previous_created
                        and str(current["billing_status"]) == "canceled"
                        and status in {"trialing", "active"}
                    )
                )
            )
            if not applied:
                conn.commit()
                subscription = get_subscription_by_id(subscription_id)
                if subscription is not None:
                    subscription["_billing_event_applied"] = False
                return subscription
        now_iso = _now()
        conn.execute(
            """
            UPDATE firehose_subscriptions
            SET billing_status = ?, billing_customer_id = COALESCE(?, billing_customer_id),
                billing_subscription_id = COALESCE(?, billing_subscription_id),
                trial_ends_at = ?, paid_at = COALESCE(?, paid_at), updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                customer_id,
                billing_subscription_id,
                trial_ends_at,
                paid_at,
                now_iso,
                subscription_id,
            ),
        )
        if event_created is not None:
            conn.execute(
                """
                INSERT INTO events
                    (ts, source, type, actor, payload_json, attachment_uri, ingested_at)
                VALUES (?, 'paperboy-billing', 'state-applied', ?, ?, NULL, ?)
                """,
                (
                    now_iso,
                    f"subscription:{subscription_id}",
                    json.dumps(
                        {
                            "event_id": event_id,
                            "event_created": event_created,
                            "status": status,
                        },
                        sort_keys=True,
                    ),
                    now_iso,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    subscription = get_subscription_by_id(subscription_id)
    if subscription is not None and event_created is not None:
        subscription["_billing_event_applied"] = applied
    return subscription


def _rate_hash(kind: str, value: str) -> str:
    return hmac.new(_management_secret(), f"rate:{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def allow_subscription_attempt(ip: str, email: str, *, now: datetime | None = None) -> bool:
    """Persistently limit subscribe attempts to 5/IP/hour and 3/email/hour."""
    normalized_email = _valid_email(email)
    normalized_ip = (ip or "unknown").strip()[:128]
    now_dt = _utc_now(now)
    now_iso = _iso(now_dt)
    hour_ago = _iso(now_dt - timedelta(hours=1))
    cleanup_before = _iso(now_dt - timedelta(days=1))
    ip_hash = _rate_hash("ip", normalized_ip)
    email_hash = _rate_hash("email", normalized_email)
    init_schema()
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM firehose_subscription_attempts WHERE attempted_at < ?", (cleanup_before,))
        ip_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM firehose_subscription_attempts WHERE ip_hash = ? AND attempted_at > ?",
                (ip_hash, hour_ago),
            ).fetchone()[0]
        )
        email_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM firehose_subscription_attempts WHERE email_hash = ? AND attempted_at > ?",
                (email_hash, hour_ago),
            ).fetchone()[0]
        )
        allowed = ip_count < 5 and email_count < 3
        if allowed:
            conn.execute(
                "INSERT INTO firehose_subscription_attempts(ip_hash, email_hash, attempted_at) VALUES (?, ?, ?)",
                (ip_hash, email_hash, now_iso),
            )
        conn.commit()
        return allowed
    finally:
        conn.close()


def _safe_target_url(value: str) -> str:
    if len(value) > 2048 or "\r" in value or "\n" in value:
        raise ValueError("invalid tracking target")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("invalid tracking target")
    return value


def create_tracking_token(
    subscription_id: int,
    kind: str,
    *,
    delivery_id: int | None = None,
    target_url: str | None = None,
    now: datetime | None = None,
    expires_days: int = 90,
) -> str:
    if kind not in {"open", "click"}:
        raise ValueError("tracking kind must be open or click")
    if kind == "click":
        if target_url is None:
            raise ValueError("click tracking requires a target URL")
        target_url = _safe_target_url(target_url)
    elif target_url is not None:
        raise ValueError("open tracking cannot have a target URL")
    if expires_days < 1 or expires_days > 365:
        raise ValueError("expires_days must be between 1 and 365")
    now_dt = _utc_now(now)
    token = secrets.token_urlsafe(32)
    init_schema()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO firehose_tracking_tokens
                (subscription_id, delivery_id, token_hash, kind, target_url, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                delivery_id,
                _token_hash(token),
                kind,
                target_url,
                _iso(now_dt),
                _iso(now_dt + timedelta(days=expires_days)),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def resolve_click_target(token: str, *, now: datetime | None = None) -> str | None:
    if not isinstance(token, str) or len(token) > 256:
        return None
    try:
        token_hash = _token_hash(token)
    except UnicodeEncodeError:
        return None
    now_iso = _iso(_utc_now(now))
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT target_url FROM firehose_tracking_tokens "
            "WHERE token_hash = ? AND kind = 'click' AND expires_at > ?",
            (token_hash, now_iso),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row["target_url"]:
        return None
    try:
        return _safe_target_url(str(row["target_url"]))
    except ValueError:
        return None


def record_tracking_event(
    token: str,
    event: str,
    *,
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    if event not in {"open", "click"} or not isinstance(token, str) or len(token) > 256:
        return False
    try:
        token_hash = _token_hash(token)
    except UnicodeEncodeError:
        return False
    now_iso = _iso(_utc_now(now))
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    if len(metadata_json) > 2000:
        metadata_json = "{}"
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, subscription_id, delivery_id FROM firehose_tracking_tokens
            WHERE token_hash = ? AND kind = ? AND expires_at > ?
            """,
            (token_hash, event, now_iso),
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            """
            INSERT INTO firehose_tracking_events
                (token_id, subscription_id, delivery_id, event, occurred_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["subscription_id"],
                row["delivery_id"],
                event,
                now_iso,
                metadata_json,
            ),
        )
        conn.execute(
            "UPDATE firehose_tracking_tokens SET used_at = COALESCE(used_at, ?) WHERE id = ?",
            (now_iso, row["id"]),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def claim_billing_webhook(event_id: str, event_type: str, *, now: datetime | None = None) -> bool:
    if not event_id.strip() or len(event_id) > 255 or not event_type.strip() or len(event_type) > 255:
        raise ValueError("invalid billing webhook identity")
    init_schema()
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, received_at FROM billing_webhook_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        received_at = _iso(_utc_now(now))
        retryable = False
        if row is None:
            conn.execute(
                """
                INSERT INTO billing_webhook_events
                    (event_id, event_type, received_at, status)
                VALUES (?, ?, ?, 'processing')
                """,
                (event_id, event_type, received_at),
            )
            claimed = True
        else:
            stale_processing = False
            if str(row["status"]) == "processing":
                try:
                    stale_processing = _parse_iso(str(row["received_at"])) <= (
                        _utc_now(now) - _WEBHOOK_PROCESSING_LEASE
                    )
                except (TypeError, ValueError):
                    stale_processing = True
            retryable = str(row["status"]) == "failed" or stale_processing
        if row is not None and retryable:
            conn.execute(
                """
                UPDATE billing_webhook_events
                SET event_type = ?, received_at = ?, processed_at = NULL,
                    status = 'processing', detail = '' WHERE event_id = ?
                """,
                (event_type, received_at, event_id),
            )
            claimed = True
        elif row is not None:
            claimed = False
        conn.commit()
        return claimed
    finally:
        conn.close()


def finish_billing_webhook(event_id: str, status: str, detail: str = "", *, now: datetime | None = None) -> None:
    if status not in {"processed", "failed", "ignored"}:
        raise ValueError("invalid billing webhook status")
    init_schema()
    conn = connect()
    try:
        conn.execute(
            """
            UPDATE billing_webhook_events
            SET processed_at = ?, status = ?, detail = ? WHERE event_id = ?
            """,
            (_iso(_utc_now(now)), status, detail[:1000], event_id),
        )
        conn.commit()
    finally:
        conn.close()


def management_urls(token: str) -> tuple[str, str, str]:
    return (
        f"/?manage={token}",
        f"/api/firehose/subscriptions/{token}",
        f"/api/firehose/subscriptions/{token}/unsubscribe",
    )
