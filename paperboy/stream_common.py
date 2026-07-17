"""Shared writer for prompt-stream scanners.

All scanners (news, papers, topical, today) write pattern-scan events to
events.db with:
    source='pattern-scan'
    type='question' | 'guess' | 'observation' | 'playbook' | 'contradiction'
    actor='<stream>:<sha1[:12]>'   ← idempotency key
    event_tags row: 'stream:<stream>'
    payload_json: {"text": ..., "why": ..., "evidence": [...]}

Idempotent: writing the same (stream, text) twice returns the existing event_id.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from paperboy.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_for_stream(stream: str, text: str) -> str:
    """Stable, stream-prefixed slug from canonicalized text."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())[:500]
    h = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{stream}:{h}"


def write_prompt_event(
    *,
    stream: str,
    kind: str,
    text: str,
    why: str = "",
    evidence: Iterable[str] = (),
    extra_tags: Iterable[str] = (),
) -> int:
    """Insert a pattern-scan event idempotent by (stream, text)."""
    actor = slug_for_stream(stream, text)
    payload = json.dumps({
        "text": text,
        "why": why,
        "evidence": list(evidence),
        "stream": stream,
    }, ensure_ascii=False)
    conn = connect()
    try:
        existing = conn.execute(
            "SELECT id FROM events WHERE source='pattern-scan' AND actor=?",
            (actor,),
        ).fetchone()
        if existing:
            return int(existing[0])
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO events (ts, source, type, actor, payload_json, ingested_at) "
            "VALUES (?, 'pattern-scan', ?, ?, ?, ?)",
            (now, kind, actor, payload, now),
        )
        eid = cur.lastrowid
        if eid is None:
            raise RuntimeError("event insert did not return an id")
        tags = {f"stream:{stream}", *extra_tags}
        conn.executemany(
            "INSERT OR IGNORE INTO event_tags (event_id, tag) VALUES (?, ?)",
            [(eid, t) for t in tags],
        )
        conn.commit()
        return int(eid)
    finally:
        conn.close()


def recent_actors_by_stream(stream: str, days: int = 14) -> list[str]:
    """Actor slugs for a stream within the lookback window. Used for dedup."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT actor FROM events "
            "WHERE source='pattern-scan' AND actor LIKE ? AND ts >= ?",
            (f"{stream}:%", cutoff),
        ).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        conn.close()


def write_event(
    *,
    source: str,
    event_type: str,
    actor: str | None,
    ts: str,
    payload: dict,
    tags: Iterable[str] = (),
) -> int | None:
    """Generic event writer used by ingest/score modules.

    Idempotent against (source, type, actor) — returns existing id if a row
    with that key already exists.
    """
    conn = connect()
    try:
        if actor:
            existing = conn.execute(
                "SELECT id FROM events WHERE source=? AND type=? AND actor=?",
                (source, event_type, actor),
            ).fetchone()
            if existing:
                return int(existing[0])
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO events (ts, source, type, actor, payload_json, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, source, event_type, actor, json.dumps(payload, ensure_ascii=False), now),
        )
        eid = cur.lastrowid
        if eid is None:
            raise RuntimeError("event insert did not return an id")
        if tags:
            conn.executemany(
                "INSERT OR IGNORE INTO event_tags (event_id, tag) VALUES (?, ?)",
                [(eid, t) for t in tags],
            )
        conn.commit()
        return int(eid)
    finally:
        conn.close()


def update_payload(*, source: str, event_type: str, actor: str, payload: dict) -> bool:
    conn = connect()
    try:
        conn.execute(
            "UPDATE events SET payload_json=? WHERE source=? AND type=? AND actor=?",
            (json.dumps(payload, ensure_ascii=False), source, event_type, actor),
        )
        conn.commit()
        return True
    finally:
        conn.close()
