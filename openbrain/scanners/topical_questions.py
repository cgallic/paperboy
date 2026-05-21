"""topical_questions.py — pick answer-questions from your topical map.

Reads config/topical-map.md (or $TOPICAL_MAP), parses pillars + bulleted
questions, picks PICKS_PER_RUN questions per run rotating across pillars,
and emits as pattern-scan/question events with stream='answer'.

These are content prompts you can answer directly — "How does X work?"-shape
questions targeting your audiences. The format is opinionated:

    ## Pillar — <name>
    - <question 1>
    - <question 2>

Dedup happens naturally via stream_common's actor slug.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbrain.db import connect
from openbrain.stream_common import write_prompt_event


def _map_path() -> Path:
    p = os.environ.get("TOPICAL_MAP")
    if p:
        return Path(p)
    for c in [
        Path.cwd() / "config" / "topical-map.md",
        Path(__file__).resolve().parent.parent.parent / "config" / "topical-map.md",
        Path.home() / ".openbrain" / "config" / "topical-map.md",
    ]:
        if c.is_file():
            return c
    return Path.cwd() / "config" / "topical-map.md"


PICKS_PER_RUN = int(os.environ.get("TOPICAL_PICKS_PER_RUN", "2"))
RECENT_DAYS = int(os.environ.get("TOPICAL_RECENT_DAYS", "21"))


def _parse_map(path: Path) -> dict[str, list[str]]:
    """Return {pillar: [question, ...]} from the markdown file."""
    if not path.is_file():
        return {}
    pillars: dict[str, list[str]] = {}
    current = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = re.match(r"^##\s+Pillar\s*[—\-]\s*(.+)$", line)
        if m:
            current = (m.group(1) or "").strip()
            pillars[current] = []
            continue
        if line.startswith("- ") and current:
            q = line[2:].strip()
            if q:
                pillars[current].append(q)
    return pillars


def _recently_emitted_questions() -> set[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).isoformat()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT json_extract(payload_json,'$.text') FROM events "
            "WHERE source='pattern-scan' AND actor LIKE 'answer:%' AND ts >= ?",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows if r[0]}


def _pick(pillars: dict[str, list[str]], n: int, recent: set[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pool = [(p, q) for p, qs in pillars.items() for q in qs if q not in recent]
    if not pool:
        pool = [(p, q) for p, qs in pillars.items() for q in qs]
    random.shuffle(pool)
    per_pillar = max(1, (n + len(pillars) - 1) // max(1, len(pillars)))
    counts: dict[str, int] = {}
    for pillar, q in pool:
        if counts.get(pillar, 0) >= per_pillar:
            continue
        out.append((pillar, q))
        counts[pillar] = counts.get(pillar, 0) + 1
        if len(out) >= n:
            break
    return out


def run(dry_run: bool = False) -> int:
    pillars = _parse_map(_map_path())
    if not pillars:
        print(f"topical_questions: no pillars found in {_map_path()}", file=sys.stderr)
        return 0
    recent = _recently_emitted_questions()
    picks = _pick(pillars, PICKS_PER_RUN, recent)
    emitted = 0
    for pillar, q in picks:
        if dry_run:
            print(json.dumps({"pillar": pillar, "text": q}, indent=2))
            emitted += 1
            continue
        eid = write_prompt_event(
            stream="answer",
            kind="question",
            text=q,
            why=f"AEO-shaped explainer for the '{pillar}' pillar.",
            evidence=[f"topical-map:{pillar}"],
        )
        if eid:
            emitted += 1
    return emitted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    n = run(dry_run=args.dry_run)
    print(f"topical_questions: {n} prompts emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
