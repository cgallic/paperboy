"""today_briefing.py — emit today's actionable prompts from a daily-brief file.

Reads $DAILY_BRIEFS_DIR/<YYYY-MM-DD>.md (default ~/.openbrain/daily-briefs/)
and turns its concrete sections into pattern-scan/question events with
stream='today'. These lead the morning digest as "what to actually do today."

Two sections are parsed (see config/daily-brief.md.example for the format):

    ## Today's corpse
    **`<repo-or-project>`** — dead **N days** since last commit. ...

    ## Yesterday you said out loud
    - <commitment 1>
    - <commitment 2>

Skips silently if no file exists for today.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from openbrain.stream_common import write_prompt_event

MAX_PER_RUN = int(os.environ.get("TODAY_MAX_PER_RUN", "6"))


def _briefs_dir() -> Path:
    p = os.environ.get("DAILY_BRIEFS_DIR")
    if p:
        return Path(p)
    return Path.home() / ".openbrain" / "daily-briefs"


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_brief(md_path: Path) -> list[dict]:
    if not md_path.is_file():
        return []
    text = md_path.read_text(encoding="utf-8")
    out: list[dict] = []

    # Today's corpse — first bold-repo + dead-N-days line
    corpse = re.search(
        r"##\s+Today'?s corpse\s*\n+(.+?)(?=\n##\s|\Z)",
        text,
        flags=re.DOTALL,
    )
    if corpse:
        body = corpse.group(1)
        repo_m = re.search(r"\*\*`?([\w/-]+)`?\*\*", body)
        dead_m = re.search(r"dead\s+\*\*(\d+)\s+days?\*\*", body, re.IGNORECASE)
        if repo_m:
            repo = repo_m.group(1)
            days = dead_m.group(1) if dead_m else "?"
            out.append({
                "text": f"Revive or kill: {repo} (dead {days}d) — pick one before EOD.",
                "why": "Today's corpse from morning brief. Options: land one commit, "
                       "echo to a 'killed.md' graveyard, or rot another 30 days.",
                "evidence": [f"daily-brief:{md_path.name}"],
            })

    # Yesterday you said out loud
    said = re.search(
        r"##\s+Yesterday[^\n]*you said[^\n]*\n+(.+?)(?=\n##\s|\Z)",
        text,
        flags=re.DOTALL,
    )
    if said:
        body = said.group(1).strip()
        if "_Nothing._" not in body:
            for b in re.findall(r"^[-*]\s+(.+)$", body, re.MULTILINE)[:3]:
                clean = b.strip().strip("`").strip()
                if 10 <= len(clean) <= 200:
                    out.append({
                        "text": f"Carry-over: {clean}",
                        "why": "You said this out loud yesterday. Did it happen?",
                        "evidence": [f"daily-brief:{md_path.name}"],
                    })

    return out


def run(dry_run: bool = False) -> int:
    md = _briefs_dir() / f"{_today_iso()}.md"
    prompts = _parse_brief(md)[:MAX_PER_RUN]
    if not prompts:
        return 0
    emitted = 0
    for p in prompts:
        if dry_run:
            print(json.dumps(p, indent=2))
            emitted += 1
            continue
        eid = write_prompt_event(
            stream="today",
            kind="question",
            text=p["text"],
            why=p.get("why", ""),
            evidence=p.get("evidence", []),
        )
        if eid:
            emitted += 1
    return emitted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    n = run(dry_run=args.dry_run)
    print(f"today_briefing: {n} prompts emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
