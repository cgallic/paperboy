"""Post top newly-scored research papers to Discord.

Selects papers scored in the last SINCE_HOURS where relevance >= MIN_RELEVANCE
or should_prototype=True. Posts one batched message via Discord bot API
(or webhook fallback). Quiet by default: nothing posted if no papers cross
the bar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone

from paperboy.db import connect
from paperboy.discord_post import deliver

DISCORD_LIMIT = 1900


def load_recent_scores(since_hours: int, min_relevance: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    conn = connect()
    try:
        rows = []
        for r in conn.execute(
            "SELECT id, ts, actor, payload_json, ingested_at FROM events "
            "WHERE source='research-papers' AND type='paper-score' "
            "AND ingested_at >= ? "
            "ORDER BY id DESC",
            (cutoff,),
        ):
            try:
                score = json.loads(r[3])
            except json.JSONDecodeError:
                continue
            relevance = int(score.get("relevance", 0) or 0)
            should_proto = bool(score.get("should_prototype", False))
            if not (relevance >= min_relevance or should_proto):
                continue
            paper_row = conn.execute(
                "SELECT id, payload_json FROM events "
                "WHERE source='research-papers' AND type='paper' AND actor=? "
                "ORDER BY id ASC LIMIT 1",
                (r[2],),
            ).fetchone()
            paper = json.loads(paper_row[1]) if paper_row else {}
            rows.append({
                "actor": r[2], "score_eid": r[0], "score": score,
                "paper": paper, "paper_eid": paper_row[0] if paper_row else None,
            })
        return rows
    finally:
        conn.close()


def pick_top(rows: list[dict], top_n: int) -> list[dict]:
    rows.sort(key=lambda x: (
        -int(x["score"].get("relevance", 0) or 0),
        not bool(x["score"].get("should_prototype", False)),
    ))
    if top_n and top_n > 0:
        return rows[:top_n]
    return rows


def render_line(entry: dict) -> str:
    paper = entry["paper"]
    score = entry["score"]
    title = (paper.get("title") or "(untitled)").strip()
    url = paper.get("url", "")
    relevance = int(score.get("relevance", 0) or 0)
    applies = score.get("applies_to") or []
    applies_str = ",".join(f"`{s}`" for s in applies[:3]) if applies else ""
    proto = " ★" if score.get("should_prototype") else ""
    one_sentence = (score.get("improvement_idea") or score.get("why") or "").strip()
    one_sentence = one_sentence.split(". ")[0].rstrip(".")
    if len(one_sentence) > 220:
        one_sentence = one_sentence[:217] + "..."
    suffix = f"  [{applies_str}]" if applies_str else ""
    return f"• [{title}](<{url}>) `{relevance}/10`{proto}{suffix} — {one_sentence}"


def batch_into_messages(lines: list[str], header: str) -> list[str]:
    messages: list[str] = []
    current = header
    for line in lines:
        candidate = current + "\n" + line
        if len(candidate) > DISCORD_LIMIT:
            messages.append(current)
            current = line
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--min-relevance", type=int, default=5)
    ap.add_argument("--since-hours", type=int, default=24)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rows = load_recent_scores(args.since_hours, args.min_relevance)
    picks = pick_top(rows, args.top)
    if not picks:
        print(json.dumps({"status": "no-posts", "candidates": len(rows)}))
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = (
        f"**🧠 Research Digest — {today}**  "
        f"({len(picks)} relevant paper(s), `relevance ≥ {args.min_relevance}`)"
    )
    lines = [render_line(e) for e in picks]
    messages = batch_into_messages(lines, header)

    stats = {"candidates": len(rows), "papers": len(picks),
             "messages_attempted": 0, "messages_posted": 0, "messages_failed": 0}
    for i, msg in enumerate(messages):
        ok, channel = deliver(msg, username="paperboy-research", dry_run=args.dry_run)
        stats["messages_attempted"] += 1
        if ok:
            stats["messages_posted"] += 1
        else:
            stats["messages_failed"] += 1
        if args.verbose:
            print(f"  [{'ok' if ok else 'fail'}] msg {i+1}/{len(messages)} ({len(msg)} chars) via {channel}",
                  file=sys.stderr)
        if i + 1 < len(messages) and not args.dry_run:
            time.sleep(1.0)

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
