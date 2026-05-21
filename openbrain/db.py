"""Schema + path resolution for openbrain's SQLite event log.

The whole system writes append-only events to one table. Scanners write
prompt events; ingesters write paper events; scorers write paper-score events.
The digest readers join across them.

Two env vars control where the DB lives:
    OPENBRAIN_ROOT   default: ~/.openbrain
    OPENBRAIN_DB     default: $OPENBRAIN_ROOT/events.db

For backwards compatibility with the source codebase, BRAIN_ROOT / BRAIN_DB
are honored if OPENBRAIN_* are unset.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def root() -> Path:
    p = os.environ.get("OPENBRAIN_ROOT") or os.environ.get("BRAIN_ROOT")
    if p:
        return Path(p)
    return Path.home() / ".openbrain"


def db_path() -> Path:
    p = os.environ.get("OPENBRAIN_DB") or os.environ.get("BRAIN_DB")
    if p:
        return Path(p)
    return root() / "events.db"


def connect() -> sqlite3.Connection:
    """Open a connection. Creates the parent dir but NOT the schema —
    callers should run init_schema() once at install time."""
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(p)


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
"""


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
