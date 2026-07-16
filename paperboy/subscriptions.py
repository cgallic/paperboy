"""Durable subscriptions and tokenized self-service management."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from paperboy.db import connect, init_schema, root
from paperboy.firehose import PreviewValidationError, validate_preview_payload

_ATTRIBUTION_KEYS = {"source", "page", "ref", "gclid", "fbclid"}


class SubscriptionValidationError(ValueError):
    """The subscription request is invalid."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def validate_subscription_payload(
    payload: Any,
) -> tuple[str, list[str], str, list[str], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise SubscriptionValidationError("request body must be a JSON object")
    allowed = {"email", "sources", "focus", "ignore"} | _ATTRIBUTION_KEYS
    unknown = {key for key in payload if key not in allowed and not key.startswith("utm_")}
    if unknown:
        raise SubscriptionValidationError("request contains unsupported fields")
    email = _valid_email(payload.get("email"))
    try:
        sources, focus, ignore = validate_preview_payload(
            {key: payload[key] for key in ("sources", "focus", "ignore") if key in payload}
        )
    except PreviewValidationError as exc:
        raise SubscriptionValidationError(str(exc)) from exc
    attribution = {
        key: value
        for key, value in payload.items()
        if key in _ATTRIBUTION_KEYS or key.startswith("utm_")
    }
    return email, sources, focus, ignore, attribution


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
    signature = hmac.new(_management_secret(), nonce.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_token() -> tuple[str, str, str]:
    nonce = secrets.token_urlsafe(32)
    token = _token_for_nonce(nonce)
    return token, nonce, _token_hash(token)


def _validated_token_hash(token: str) -> str | None:
    if not isinstance(token, str) or "." not in token or len(token) > 256:
        return None
    nonce, supplied_signature = token.rsplit(".", 1)
    try:
        expected = _token_for_nonce(nonce).rsplit(".", 1)[1]
    except (UnicodeEncodeError, RuntimeError):
        return None
    if not hmac.compare_digest(supplied_signature, expected):
        return None
    return _token_hash(token)


def create_subscription(
    email: str,
    sources: list[str],
    focus: str,
    ignore: list[str],
    attribution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Create or replace the single firehose owned by an email address."""
    init_schema()
    token, nonce, token_hash = _new_token()
    now = _now()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, created_at FROM firehose_subscriptions WHERE email = ?",
            (email,),
        ).fetchone()
        values = (
            json.dumps(sources),
            focus,
            json.dumps(ignore),
            json.dumps(attribution or {}, ensure_ascii=False),
            token_hash,
            nonce,
            now,
        )
        if row is None:
            cursor = conn.execute(
                """
                INSERT INTO firehose_subscriptions
                    (email, sources_json, focus, ignore_json, attribution_json,
                     token_hash, token_nonce, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (email, *values[:-1], now, now),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("subscription insert did not return an id")
            subscription_id = int(cursor.lastrowid)
            created_at = now
        else:
            subscription_id = int(row[0])
            created_at = str(row[1])
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET sources_json = ?, focus = ?, ignore_json = ?, attribution_json = ?,
                    token_hash = ?, token_nonce = ?, active = 1, updated_at = ?, unsubscribed_at = NULL
                WHERE id = ?
                """,
                (*values, subscription_id),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": subscription_id,
        "email": email,
        "sources": sources,
        "focus": focus,
        "ignore": ignore,
        "active": True,
        "created_at": created_at,
        "updated_at": now,
    }, token


def _decode_subscription(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "email": str(row[1]),
        "sources": json.loads(str(row[2])),
        "focus": str(row[3]),
        "ignore": json.loads(str(row[4])),
        "token_nonce": str(row[5]),
        "active": bool(row[6]),
        "created_at": str(row[7]),
        "updated_at": str(row[8]),
        "unsubscribed_at": row[9],
        "last_sent_at": row[10],
        "last_delivery_status": row[11],
    }


_SUBSCRIPTION_SELECT = """
SELECT s.id, s.email, s.sources_json, s.focus, s.ignore_json, s.token_nonce,
       s.active, s.created_at, s.updated_at, s.unsubscribed_at,
       (
           SELECT sent.completed_at FROM firehose_deliveries AS sent
           WHERE sent.subscription_id = s.id AND sent.status = 'sent'
           ORDER BY sent.delivery_date DESC, sent.id DESC LIMIT 1
       ),
       (
           SELECT latest.status FROM firehose_deliveries AS latest
           WHERE latest.subscription_id = s.id
           ORDER BY latest.delivery_date DESC, latest.id DESC LIMIT 1
       )
FROM firehose_subscriptions AS s
"""


def get_subscription(token: str) -> dict[str, Any] | None:
    token_hash = _validated_token_hash(token)
    if token_hash is None:
        return None
    init_schema()
    conn = connect()
    try:
        row = conn.execute(
            _SUBSCRIPTION_SELECT + " WHERE s.token_hash = ?",
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()
    return _decode_subscription(row) if row is not None else None


def unsubscribe(token: str) -> dict[str, Any] | None:
    subscription = get_subscription(token)
    if subscription is None:
        return None
    if subscription["active"]:
        now = _now()
        conn = connect()
        try:
            conn.execute(
                """
                UPDATE firehose_subscriptions
                SET active = 0, updated_at = ?, unsubscribed_at = ?
                WHERE id = ?
                """,
                (now, now, subscription["id"]),
            )
            conn.commit()
        finally:
            conn.close()
        subscription["active"] = False
        subscription["updated_at"] = now
        subscription["unsubscribed_at"] = now
    return subscription


def active_subscriptions() -> list[dict[str, Any]]:
    init_schema()
    conn = connect()
    try:
        rows = conn.execute(_SUBSCRIPTION_SELECT + " WHERE s.active = 1 ORDER BY s.id").fetchall()
    finally:
        conn.close()
    return [_decode_subscription(row) for row in rows]


def management_token(subscription: dict[str, Any]) -> str:
    return _token_for_nonce(str(subscription["token_nonce"]))


def management_urls(token: str) -> tuple[str, str, str]:
    return (
        f"/?manage={token}",
        f"/api/firehose/subscriptions/{token}",
        f"/api/firehose/subscriptions/{token}/unsubscribe",
    )
