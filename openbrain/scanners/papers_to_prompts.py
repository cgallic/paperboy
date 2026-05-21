"""Papers→prompts scanner — promote top-scored research papers into the morning queue.

Reads `research-papers/paper-score` events from the last LOOKBACK_HOURS, picks
the highest-relevance hits (>= MIN_RELEVANCE), and emits one
`pattern-scan/question` event per paper with stream='papers'. These flow into
the prompt_digest.

Each emitted prompt is a content-ideation stimulus, not a Socratic question:
    text = "<title> — applies to <system>. Take?"
    why  = improvement_idea (scorer's "how WE'd apply it" note)
    evidence = [url, score-event-id, paper-event-id]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from openbrain.db import connect
from openbrain.stream_common import write_prompt_event

MIN_RELEVANCE = int(os.environ.get("PAPERS_MIN_RELEVANCE", "7"))
MAX_PER_RUN = int(os.environ.get("PAPERS_MAX_PER_RUN", "5"))
LOOKBACK_HOURS = int(os.environ.get("PAPERS_LOOKBACK_HOURS", "24"))


def _load_top_scores() -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT id, actor, payload_json
            FROM events
            WHERE source='research-papers'
              AND type='paper-score'
              AND ingested_at >= ?
              AND CAST(json_extract(payload_json,'$.relevance') AS INTEGER) >= ?
            ORDER BY CAST(json_extract(payload_json,'$.relevance') AS INTEGER) DESC,
                     ingested_at DESC
            LIMIT 50
            """,
            (cutoff, MIN_RELEVANCE),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for score_id, canonical_id, pj in rows:
        try:
            p = json.loads(pj or "{}")
        except json.JSONDecodeError:
            continue
        out.append({
            "score_id": score_id,
            "canonical_id": canonical_id,
            "title": (p.get("title") or "").strip(),
            "url": (p.get("url") or "").strip(),
            "relevance": p.get("relevance"),
            "applies_to": p.get("applies_to") or [],
            "improvement_idea": (p.get("improvement_idea") or "").strip(),
            "novelty": p.get("novelty"),
            "should_prototype": bool(p.get("should_prototype")),
        })
    return out


def _paper_event_id(canonical_id: str) -> int | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM events WHERE source='research-papers' AND type='paper' AND actor=? LIMIT 1",
            (canonical_id,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _format_prompt(p: dict) -> tuple[str, str, list[str]]:
    title = p["title"] or "(untitled paper)"
    applies = p["applies_to"][0] if p["applies_to"] else ""
    suffix = f" — applies to {applies}. Take?" if applies else " — Take?"
    text = f"{title}{suffix}"
    if len(text) > 200:
        text = text[:197] + "…"
    why = p["improvement_idea"]
    if len(why) > 220:
        why = why[:217] + "…"
    evidence = []
    if p["url"]:
        evidence.append(p["url"])
    evidence.append(f"paper-score event:{p['score_id']}")
    paper_id = _paper_event_id(p["canonical_id"])
    if paper_id:
        evidence.append(f"paper event:{paper_id}")
    return text, why, evidence


def run(dry_run: bool = False) -> int:
    scores = _load_top_scores()
    if not scores:
        return 0
    scores.sort(key=lambda s: (s["should_prototype"], s["relevance"] or 0), reverse=True)
    emitted = 0
    for p in scores[:MAX_PER_RUN]:
        if not p["title"]:
            continue
        text, why, evidence = _format_prompt(p)
        if dry_run:
            print(json.dumps({"text": text, "why": why, "evidence": evidence}, indent=2))
            emitted += 1
            continue
        eid = write_prompt_event(
            stream="papers",
            kind="question",
            text=text,
            why=why,
            evidence=evidence,
        )
        if eid:
            emitted += 1
    return emitted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    n = run(dry_run=args.dry_run)
    print(f"papers_to_prompts: {n} prompts emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
