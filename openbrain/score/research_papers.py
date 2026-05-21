"""Local-LLM scorer for research-papers/paper events.

For each unscored paper, asks local Ollama whether the technique could improve
one of your systems. Records the verdict as a new event with type='paper-score',
deduped by canonical_id in the actor column.

Grounded by config/research-interests.md (injected into the system prompt).
That file describes YOUR systems and themes — without it, scoring is a coin flip.

Verdict shape (payload_json):
    canonical_id, title, url,
    relevance:       0-10 int
    applies_to:      [your_system_slug, ...]
    improvement_idea: "≤240 chars"
    novelty:         "low" | "medium" | "high"
    should_prototype: bool
    why:             "≤240 chars"
    model:           ollama model tag
    judged_at:       ISO 8601 UTC
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from openbrain.db import connect
from openbrain.stream_common import write_event

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OPENBRAIN_RESEARCH_MODEL",
                       os.environ.get("BRAIN_RESEARCH_MODEL", "qwen2.5:7b"))
TIMEOUT = int(os.environ.get("OPENBRAIN_SCORE_TIMEOUT", "240"))

VALID_NOVELTY = {"low", "medium", "high"}


def _interests_path() -> Path:
    p = os.environ.get("RESEARCH_INTERESTS")
    if p:
        return Path(p)
    for c in [
        Path.cwd() / "config" / "research-interests.md",
        Path(__file__).resolve().parent.parent.parent / "config" / "research-interests.md",
        Path.home() / ".openbrain" / "config" / "research-interests.md",
    ]:
        if c.is_file():
            return c
    return Path.cwd() / "config" / "research-interests.md"


def load_interests() -> str:
    p = _interests_path()
    if not p.exists():
        return "(no interests file present — score conservatively)"
    return p.read_text(encoding="utf-8")


SYSTEM_PROMPT_HEADER = """You evaluate AI/ML research papers for whether their TECHNIQUES could
improve one of the user's existing systems. You are NOT judging the paper's
academic merit — you are judging whether a specific idea from the paper could be
borrowed and shipped as a small change to system X.

Below is the current state of the user's stack. Use the system slugs verbatim
in your `applies_to` field. If no system applies, return [] (an empty list).

────────────────────────────────────────────────────────────────────
"""

SYSTEM_PROMPT_FOOTER = """
────────────────────────────────────────────────────────────────────

Scoring guide:
- relevance 0-3: doesn't apply, no transferable technique
- relevance 4-6: interesting, weak/abstract application
- relevance 7-8: clear technique that could upgrade a specific system
- relevance 9-10: drop-in technique with strong fit AND likely high impact

Set should_prototype=true ONLY when relevance>=7 AND the paper gives enough
specificity that a 1-2 day prototype is feasible.

Be ruthless. Most papers score 3-5. Default novelty=low unless the paper
introduces a genuinely new mechanism.

Respond with ONLY valid JSON (no prose, no markdown fences). Schema:
{
  "relevance": 0,
  "applies_to": [],
  "improvement_idea": "",
  "novelty": "low",
  "should_prototype": false,
  "why": ""
}"""


PROMPT_TEMPLATE = """Paper title: {title}
Authors: {authors}
Venue: {venue}
Categories: {categories}
URL: {url}
Source feeds: {feeds}

Abstract:
{abstract}

Respond with ONLY valid JSON matching the schema."""


def load_unscored(retry_scored: bool, limit: int | None) -> list[dict]:
    conn = connect()
    try:
        scored: set[str] = set()
        if not retry_scored:
            scored = {
                r[0] for r in conn.execute(
                    "SELECT actor FROM events "
                    "WHERE source='research-papers' AND type='paper-score' AND actor IS NOT NULL"
                )
            }
        rows = []
        for r in conn.execute(
            "SELECT id, ts, actor, payload_json FROM events "
            "WHERE source='research-papers' AND type='paper' "
            "ORDER BY ts DESC, id DESC"
        ):
            if r[2] in scored:
                continue
            try:
                payload = json.loads(r[3])
            except json.JSONDecodeError:
                continue
            rows.append({"id": r[0], "ts": r[1], "actor": r[2], "payload": payload})
            if limit and len(rows) >= limit:
                break
        return rows
    finally:
        conn.close()


def call_ollama(system_prompt: str, user_prompt: str) -> dict:
    body = {
        "model": MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 600},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        resp = json.load(r)
    raw = resp.get("response", "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def normalize_verdict(v: dict, parent_actor: str, parent_payload: dict) -> dict:
    relevance = v.get("relevance", 0)
    try:
        relevance = int(relevance)
    except (TypeError, ValueError):
        relevance = 0
    relevance = max(0, min(10, relevance))
    applies_to = v.get("applies_to") or []
    if not isinstance(applies_to, list):
        applies_to = []
    applies_to = [str(s).strip().lower() for s in applies_to if isinstance(s, (str, int))][:6]
    novelty = str(v.get("novelty", "low")).strip().lower()
    if novelty not in VALID_NOVELTY:
        novelty = "low"
    return {
        "canonical_id": parent_actor,
        "title": (parent_payload.get("title") or "")[:300],
        "url": parent_payload.get("url", ""),
        "relevance": relevance,
        "applies_to": applies_to,
        "improvement_idea": str(v.get("improvement_idea", ""))[:240],
        "novelty": novelty,
        "should_prototype": bool(v.get("should_prototype", False)) and relevance >= 7,
        "why": str(v.get("why", ""))[:240],
        "model": MODEL,
        "judged_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--retry-scored", action="store_true")
    args = ap.parse_args()

    interests = load_interests()
    system_prompt = SYSTEM_PROMPT_HEADER + interests + SYSTEM_PROMPT_FOOTER
    candidates = load_unscored(args.retry_scored, args.limit)
    print(f"[score] {len(candidates)} unscored; model={MODEL}", file=sys.stderr)

    stats = {"judged": 0, "relevant_7plus": 0, "prototype_flags": 0,
             "parse_errors": 0, "llm_errors": 0, "record_errors": 0}

    for c in candidates:
        p = c["payload"]
        prompt = PROMPT_TEMPLATE.format(
            title=(p.get("title") or "")[:300],
            authors=", ".join((p.get("authors") or [])[:8]),
            venue=p.get("venue") or "",
            categories=", ".join((p.get("categories") or [])[:8]),
            url=p.get("url") or "",
            feeds=", ".join(p.get("source_feeds") or []),
            abstract=(p.get("abstract") or "")[:2500],
        )
        try:
            raw = call_ollama(system_prompt, prompt)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            stats["llm_errors"] += 1
            print(f"  [llm-error] {c['actor']}: {type(e).__name__}", file=sys.stderr)
            continue
        except json.JSONDecodeError:
            stats["parse_errors"] += 1
            continue
        except Exception as e:
            stats["llm_errors"] += 1
            print(f"  [unexpected] {c['actor']}: {type(e).__name__}", file=sys.stderr)
            continue

        verdict = normalize_verdict(raw, c["actor"], p)
        if not args.dry_run:
            eid = write_event(
                source="research-papers", event_type="paper-score",
                actor=c["actor"], ts=c["ts"], payload=verdict,
            )
            if not eid:
                stats["record_errors"] += 1
                continue

        stats["judged"] += 1
        if verdict["relevance"] >= 7:
            stats["relevant_7plus"] += 1
        if verdict["should_prototype"]:
            stats["prototype_flags"] += 1
        if args.verbose or verdict["relevance"] >= 7:
            tag = "★" if verdict["should_prototype"] else ("+" if verdict["relevance"] >= 7 else " ")
            applies = ",".join(verdict["applies_to"]) or "—"
            title = verdict["title"][:60]
            print(f"  {tag} [{verdict['relevance']:>2}/10] {applies:<25} {title}", file=sys.stderr)
            if verdict["relevance"] >= 7:
                print(f"      → {verdict['improvement_idea']}", file=sys.stderr)

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
