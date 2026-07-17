"""Schema + path resolution for paperboy's SQLite event log.

The schema below mirrors cgallic/open-brane — paperboy is a consumer of
that event-log architecture, not the schema owner. We ship this so the
digest works standalone; if you've installed open-brane separately and
want one shared events.db across all your tools, set
PAPERBOY_DB=/path/to/open-brane/events.db.

The whole system writes append-only events to one table. Scanners write
pattern-scan events; ingesters write paper events; scorers write
paper-score events. The digest readers join across them.

Two env vars control where the DB lives:
    PAPERBOY_ROOT   default: ~/.paperboy
    PAPERBOY_DB     default: $PAPERBOY_ROOT/events.db

For backwards compatibility with the source codebase, BRAIN_ROOT / BRAIN_DB
are honored if PAPERBOY_* are unset.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def root() -> Path:
    p = os.environ.get("PAPERBOY_ROOT") or os.environ.get("BRAIN_ROOT")
    if p:
        return Path(p)
    return Path.home() / ".paperboy"


def db_path() -> Path:
    p = os.environ.get("PAPERBOY_DB") or os.environ.get("BRAIN_DB")
    if p:
        return Path(p)
    return root() / "events.db"


def connect() -> sqlite3.Connection:
    """Open a connection. Creates the parent dir but NOT the schema —
    callers should run init_schema() once at install time."""
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    type            TEXT    NOT NULL,
    actor           TEXT,
    payload_json    TEXT    NOT NULL,
    attachment_uri  TEXT,
    ingested_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts          ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_source_type ON events(source, type);
CREATE INDEX IF NOT EXISTS idx_events_actor       ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_ingested    ON events(ingested_at);

CREATE TABLE IF NOT EXISTS event_tags (
    event_id INTEGER NOT NULL,
    tag      TEXT    NOT NULL,
    PRIMARY KEY (event_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);

CREATE TABLE IF NOT EXISTS firehose_subscriptions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    email            TEXT    NOT NULL UNIQUE,
    sources_json     TEXT    NOT NULL,
    focus            TEXT    NOT NULL,
    ignore_json      TEXT    NOT NULL,
    attribution_json TEXT    NOT NULL DEFAULT '{}',
    token_hash       TEXT    NOT NULL UNIQUE,
    token_nonce      TEXT    NOT NULL UNIQUE,
    active           INTEGER NOT NULL DEFAULT 0,
    timezone         TEXT    NOT NULL DEFAULT 'UTC',
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verification_token_hash TEXT,
    verification_token_nonce TEXT,
    verification_expires_at TEXT,
    verification_sent_at TEXT,
    verification_attempts INTEGER NOT NULL DEFAULT 0,
    verification_next_attempt_at TEXT,
    verification_last_error TEXT NOT NULL DEFAULT '',
    verified_at      TEXT,
    billing_status   TEXT    NOT NULL DEFAULT 'unpaid',
    billing_customer_id TEXT,
    billing_subscription_id TEXT,
    trial_ends_at    TEXT,
    paid_at          TEXT,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    unsubscribed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_firehose_subscriptions_active
    ON firehose_subscriptions(active);

CREATE TABLE IF NOT EXISTS firehose_deliveries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id   INTEGER NOT NULL,
    delivery_date     TEXT    NOT NULL,
    attempted_at      TEXT    NOT NULL,
    completed_at      TEXT,
    status            TEXT    NOT NULL,
    detail            TEXT    NOT NULL DEFAULT '',
    item_count        INTEGER NOT NULL DEFAULT 0,
    attempt_count     INTEGER NOT NULL DEFAULT 0,
    next_attempt_at   TEXT,
    message_id        TEXT,
    FOREIGN KEY (subscription_id) REFERENCES firehose_subscriptions(id),
    UNIQUE (subscription_id, delivery_date)
);
CREATE INDEX IF NOT EXISTS idx_firehose_deliveries_date
    ON firehose_deliveries(delivery_date);

CREATE TABLE IF NOT EXISTS firehose_suppressions (
    email             TEXT PRIMARY KEY,
    reason            TEXT NOT NULL,
    detail            TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS firehose_tracking_tokens (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id   INTEGER NOT NULL,
    delivery_id       INTEGER,
    token_hash        TEXT NOT NULL UNIQUE,
    kind              TEXT NOT NULL,
    target_url        TEXT,
    created_at        TEXT NOT NULL,
    expires_at        TEXT NOT NULL,
    used_at           TEXT,
    FOREIGN KEY (subscription_id) REFERENCES firehose_subscriptions(id),
    FOREIGN KEY (delivery_id) REFERENCES firehose_deliveries(id)
);

CREATE TABLE IF NOT EXISTS firehose_tracking_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id          INTEGER NOT NULL,
    subscription_id   INTEGER NOT NULL,
    delivery_id       INTEGER,
    event             TEXT NOT NULL,
    occurred_at       TEXT NOT NULL,
    metadata_json     TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (token_id) REFERENCES firehose_tracking_tokens(id),
    FOREIGN KEY (subscription_id) REFERENCES firehose_subscriptions(id),
    FOREIGN KEY (delivery_id) REFERENCES firehose_deliveries(id)
);

CREATE TABLE IF NOT EXISTS firehose_subscription_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_hash           TEXT NOT NULL,
    email_hash        TEXT NOT NULL,
    attempted_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS billing_webhook_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    received_at       TEXT NOT NULL,
    processed_at      TEXT,
    status            TEXT NOT NULL,
    detail            TEXT NOT NULL DEFAULT ''
);
"""


_ADDITIVE_COLUMNS = {
    "firehose_subscriptions": {
        "timezone": "TEXT NOT NULL DEFAULT 'UTC'",
        "verification_status": "TEXT NOT NULL DEFAULT 'pending'",
        "verification_token_hash": "TEXT",
        "verification_token_nonce": "TEXT",
        "verification_expires_at": "TEXT",
        "verification_sent_at": "TEXT",
        "verification_attempts": "INTEGER NOT NULL DEFAULT 0",
        "verification_next_attempt_at": "TEXT",
        "verification_last_error": "TEXT NOT NULL DEFAULT ''",
        "verified_at": "TEXT",
        "billing_status": "TEXT NOT NULL DEFAULT 'unpaid'",
        "billing_customer_id": "TEXT",
        "billing_subscription_id": "TEXT",
        "trial_ends_at": "TEXT",
        "paid_at": "TEXT",
    },
    "firehose_deliveries": {
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "next_attempt_at": "TEXT",
        "message_id": "TEXT",
    },
}


_POST_MIGRATION_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_firehose_subscriptions_verification
    ON firehose_subscriptions(verification_status, verification_next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_firehose_subscriptions_delivery_gate
    ON firehose_subscriptions(active, billing_status);
CREATE INDEX IF NOT EXISTS idx_firehose_deliveries_retry
    ON firehose_deliveries(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_firehose_tracking_tokens_hash
    ON firehose_tracking_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_firehose_tracking_events_subscription
    ON firehose_tracking_events(subscription_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_firehose_subscription_attempts_ip
    ON firehose_subscription_attempts(ip_hash, attempted_at);
CREATE INDEX IF NOT EXISTS idx_firehose_subscription_attempts_email
    ON firehose_subscription_attempts(email_hash, attempted_at);
"""


def _migrate_additive_columns(conn: sqlite3.Connection) -> None:
    """Add new nullable/defaulted columns without rebuilding live SQLite tables."""
    for table, columns in _ADDITIVE_COLUMNS.items():
        existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, declaration in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _migrate_additive_columns(conn)
        conn.executescript(_POST_MIGRATION_SCHEMA)
        # A pre-verification subscription must never continue sending merely
        # because its legacy row had active=1.
        conn.execute(
            "UPDATE firehose_subscriptions SET active = 0 "
            "WHERE verification_status != 'verified' OR verified_at IS NULL"
        )
        conn.execute(
            "UPDATE firehose_subscriptions SET verification_status = 'expired', active = 0 "
            "WHERE unsubscribed_at IS NOT NULL AND verification_status = 'pending'"
        )
        conn.commit()
    finally:
        conn.close()
