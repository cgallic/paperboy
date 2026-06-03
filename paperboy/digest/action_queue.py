"""News → Agent Action Queue — turn the highest-signal digest items into a
reviewable queue of agent tasks.

This is the file-first bridge between paperboy's scoring layer and an agent
that wants to *act* on what it read. It reads the same events the digests read
(scored research papers + top-weighted pattern-scan questions), promotes the
strongest signals, and emits structured action items:

    {id, title, source, score, why, suggested_action, status, created}

Two outputs, both append-only, both on disk — NOTHING is sent anywhere:
    1. a JSONL queue (one action item per line), and
    2. a rendered Markdown view of the same queue.

There is NO Discord/webhook/email/HTTP in this module by design. The queue is
a review surface: a human (or a downstream agent with its own guardrails)
polls the JSONL, flips `status` to `approved`/`dismissed`, and only THEN acts.

Selection (matches the digests' bar):
    - research-papers/paper-score events with relevance >= MIN_RELEVANCE
      OR should_prototype = true, and
    - the top-weighted pattern-scan/question prompts (news/papers/answer/...).

If events.db is empty or absent, this falls back to a bundled public/fictional
fixture (examples/action-queue.demo.jsonl) so it ALWAYS produces output — handy
for demos, CI, and first-run before any real events exist.

Idempotency: each action item's `id` is a stable sha1 of (source-kind + the
underlying event's idempotency key). Re-running appends only items whose id is
not already present in the target JSONL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paperboy.db import connect, db_path

# Promotion thresholds. A paper-score qualifies if relevance >= this OR the
# scorer flagged should_prototype. The pattern-scan side pulls the top-N
# weighted prompts (same weighting the morning digest uses).
MIN_RELEVANCE = int(os.environ.get("ACTION_QUEUE_MIN_RELEVANCE", "7"))
LOOKBACK_HOURS = int(os.environ.get("ACTION_QUEUE_LOOKBACK_HOURS", "48"))
MAX_PROMPTS = int(os.environ.get("ACTION_QUEUE_MAX_PROMPTS", "8"))

# Stream weights mirror prompt_digest.py so "highest-signal" means the same
# thing across the system.
STREAM_WEIGHTS = {"today": 1.5, "papers": 1.3, "news": 1.2, "answer": 1.1,
                  "cal": 1.0, "proj": 1.0, "research": 0.9, "pendant": 0.4}

# Where the queue files live. Defaults sit next to the repo's examples/ so the
# demo is self-contained; override for a real deployment.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = _REPO_ROOT / "examples" / "action-queue.demo.jsonl"
DEFAULT_QUEUE_JSONL = Path(
    os.environ.get("ACTION_QUEUE_JSONL", _REPO_ROOT / "examples" / "action-queue.demo.jsonl")
)
DEFAULT_QUEUE_MD = Path(
    os.environ.get("ACTION_QUEUE_MD", _REPO_ROOT / "examples" / "action-queue.demo.md")
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action_id(kind: str, key: str) -> str:
    """Stable id for an action item — sha1 of source-kind + underlying key."""
    h = hashlib.sha1(f"{kind}:{key}".encode("utf-8")).hexdigest()[:16]
    return f"act_{h}"


def _stream_from_actor(actor: str | None) -> str:
    if not actor or ":" not in actor:
        return "research"
    prefix = actor.split(":", 1)[0]
    return prefix if prefix in STREAM_WEIGHTS else "research"


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# Suggested-action synthesis (deterministic, no LLM)                          #
# --------------------------------------------------------------------------- #

def _suggest_for_paper(score: dict) -> str:
    """Turn a paper score into a concrete, reviewable next step."""
    applies = score.get("applies_to") or []
    target = applies[0] if applies else "the relevant system"
    if score.get("should_prototype"):
        return (
            f"Open a prototype spike against {target}: scope a 1-day experiment "
            f"to test the paper's core idea, then report keep/kill."
        )
    idea = (score.get("improvement_idea") or "").strip()
    if idea:
        return f"Evaluate for {target}: {_truncate(idea, 180)}"
    return f"Read in full and assess fit for {target}; draft a one-paragraph take."


def _suggest_for_prompt(stream: str, text: str) -> str:
    """Turn a digest prompt into a concrete content/research action."""
    if stream == "news":
        return f"Draft a short take responding to: {_truncate(text, 160)}"
    if stream == "papers":
        return f"Skim the paper and note one applicable idea: {_truncate(text, 160)}"
    if stream == "answer":
        return f"Write a crisp answer for the topical map: {_truncate(text, 160)}"
    if stream == "today":
        return f"Resolve today's carry-over: {_truncate(text, 160)}"
    return f"Triage and decide a next step: {_truncate(text, 160)}"


# --------------------------------------------------------------------------- #
# Readers                                                                      #
# --------------------------------------------------------------------------- #

def _load_paper_actions(conn: sqlite3.Connection, cutoff: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, actor, payload_json
        FROM events
        WHERE source='research-papers' AND type='paper-score'
          AND ingested_at >= ?
        ORDER BY id DESC
        """,
        (cutoff,),
    ).fetchall()
    out: list[dict] = []
    for score_id, canonical_id, pj in rows:
        try:
            score = json.loads(pj or "{}")
        except json.JSONDecodeError:
            continue
        relevance = int(score.get("relevance", 0) or 0)
        should_proto = bool(score.get("should_prototype", False))
        if not (relevance >= MIN_RELEVANCE or should_proto):
            continue
        title = (score.get("title") or "").strip()
        if not title:
            # Fall back to the paper event's title if the score didn't carry one.
            prow = conn.execute(
                "SELECT payload_json FROM events "
                "WHERE source='research-papers' AND type='paper' AND actor=? LIMIT 1",
                (canonical_id,),
            ).fetchone()
            if prow:
                try:
                    title = (json.loads(prow[0]).get("title") or "").strip()
                except json.JSONDecodeError:
                    title = ""
        if not title:
            continue
        out.append({
            "id": _action_id("paper", canonical_id or str(score_id)),
            "title": _truncate(title, 200),
            "source": "research-paper",
            "score": relevance,
            "why": _truncate(score.get("why") or score.get("improvement_idea") or "", 240),
            "suggested_action": _suggest_for_paper(score),
            "status": "pending",
            "created": _now_iso(),
            "evidence": [e for e in [score.get("url"), f"paper-score event:{score_id}"] if e],
        })
    return out


def _load_prompt_actions(conn: sqlite3.Connection, cutoff: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, ts, actor, payload_json
        FROM events
        WHERE source='pattern-scan' AND type='question' AND ts >= ?
        ORDER BY ts DESC
        LIMIT 100
        """,
        (cutoff,),
    ).fetchall()
    now = datetime.now(timezone.utc)
    scored: list[tuple[float, dict]] = []
    for qid, ts, actor, pj in rows:
        try:
            p = json.loads(pj or "{}")
        except json.JSONDecodeError:
            continue
        text = (p.get("text") or "").strip()
        if not text:
            continue
        stream = _stream_from_actor(actor)
        try:
            event_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        age_hours = max(0.5, (now - event_ts).total_seconds() / 3600.0)
        freshness = max(0.1, 1.0 - (age_hours / 48.0))
        weight = STREAM_WEIGHTS.get(stream, 1.0) * freshness
        # 0-10 display score from the weighted value (purely for the queue UI).
        display = round(min(10.0, weight / 1.5 * 10.0), 1)
        scored.append((weight, {
            "id": _action_id("prompt", actor or str(qid)),
            "title": _truncate(text, 200),
            "source": f"digest-prompt:{stream}",
            "score": display,
            "why": _truncate(p.get("why") or "", 240),
            "suggested_action": _suggest_for_prompt(stream, text),
            "status": "pending",
            "created": _now_iso(),
            "evidence": list(p.get("evidence") or []),
        }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:MAX_PROMPTS]]


def _db_has_events() -> bool:
    if not db_path().exists():
        return False
    try:
        conn = connect()
    except sqlite3.Error:
        return False
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()
        if not row:
            return False
        n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return int(n) > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _load_fixture(fixture: Path) -> list[dict]:
    """Read the bundled demo JSONL as the empty-DB fallback."""
    if not fixture.exists():
        return []
    items: list[dict] = []
    for line in fixture.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def collect_actions(fixture: Path = DEFAULT_FIXTURE) -> tuple[list[dict], str]:
    """Gather action items from events.db, or the fixture if the DB is empty.

    Returns (items, mode) where mode is 'live' or 'fixture-fallback'.
    """
    if not _db_has_events():
        return _load_fixture(fixture), "fixture-fallback"
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    conn = connect()
    try:
        papers = _load_paper_actions(conn, cutoff)
        prompts = _load_prompt_actions(conn, cutoff)
    finally:
        conn.close()
    items = papers + prompts
    if not items:
        return _load_fixture(fixture), "fixture-fallback"
    return items, "live"


# --------------------------------------------------------------------------- #
# Writers (append-only)                                                        #
# --------------------------------------------------------------------------- #

def _existing_ids(jsonl_path: Path) -> set[str]:
    if not jsonl_path.exists():
        return set()
    ids: set[str] = set()
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ids.add(json.loads(line).get("id", ""))
        except json.JSONDecodeError:
            continue
    return ids


def append_jsonl(items: list[dict], jsonl_path: Path) -> int:
    """Append only new (by id) items. Returns count written."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _existing_ids(jsonl_path)
    written = 0
    with jsonl_path.open("a", encoding="utf-8") as fh:
        for item in items:
            if item.get("id") in seen:
                continue
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            seen.add(item.get("id"))
            written += 1
    return written


def _render_markdown(items: list[dict], mode: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pending = [i for i in items if i.get("status", "pending") == "pending"]
    lines = [
        f"# Agent Action Queue — {today}",
        "",
        f"_{len(items)} item(s) · {len(pending)} pending · source: **{mode}**_",
        "",
        "> Read-only review surface. Flip `status` to `approved`/`dismissed` in",
        "> the JSONL before any agent acts. Nothing here is sent anywhere.",
        "",
    ]
    for item in items:
        status = item.get("status", "pending")
        badge = {"pending": "⏳", "approved": "✅", "dismissed": "🗑️"}.get(status, "⏳")
        lines.append(f"## {badge} {item.get('title', '(untitled)')}")
        lines.append("")
        lines.append(f"- **id:** `{item.get('id', '')}`")
        lines.append(f"- **source:** `{item.get('source', '')}`")
        lines.append(f"- **score:** `{item.get('score', '')}`")
        lines.append(f"- **status:** `{status}`")
        if item.get("why"):
            lines.append(f"- **why:** {item['why']}")
        lines.append(f"- **suggested action:** {item.get('suggested_action', '')}")
        evidence = item.get("evidence") or []
        if evidence:
            lines.append(f"- **evidence:** {', '.join(str(e) for e in evidence)}")
        lines.append("")
    return "\n".join(lines)


def write_markdown(items: list[dict], md_path: Path, mode: str) -> None:
    """Render the full queue (overwrites — it's a view of the JSONL)."""
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_render_markdown(items, mode), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #

def run(jsonl_path: Path, md_path: Path, fixture: Path,
        dry_run: bool = False) -> dict:
    items, mode = collect_actions(fixture)
    if dry_run:
        return {"mode": mode, "candidates": len(items), "written": 0,
                "items": items}
    written = append_jsonl(items, jsonl_path)
    # The markdown is a view over the *full* JSONL (existing + new), so re-read.
    full = _load_fixture(jsonl_path)
    write_markdown(full or items, md_path, mode)
    return {"mode": mode, "candidates": len(items), "written": written,
            "jsonl": str(jsonl_path), "md": str(md_path)}


def main() -> int:
    ap = argparse.ArgumentParser(description="News → Agent Action Queue (file-first, read-only)")
    ap.add_argument("--jsonl", type=Path, default=DEFAULT_QUEUE_JSONL,
                    help="append-only JSONL queue path")
    ap.add_argument("--md", type=Path, default=DEFAULT_QUEUE_MD,
                    help="rendered Markdown queue path")
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE,
                    help="fallback demo fixture when events.db is empty/absent")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be emitted; write nothing")
    args = ap.parse_args()

    result = run(args.jsonl, args.md, args.fixture, dry_run=args.dry_run)
    if args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
