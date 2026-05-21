"""Daily prompt digest — posts top unanswered/unrated prompts to Discord.

Selection:
  - source='pattern-scan', type='question'
  - emitted in last LOOKBACK_HOURS (default 48)
  - not yet rated (no feedback event for the same actor)
  - not yet answered (no answer event for the same actor)

Weighted score (stream → multiplier × freshness):
    today       × 1.5
    papers      × 1.3
    news        × 1.2
    answer      × 1.1   (your own topical-map questions)
    cal / proj  × 1.0
    research    × 0.9
    pendant     × 0.4   (downweighted — typically noisier)

Posts the top LIMIT (default 12) via Discord. Tries bot API first, falls back
to webhook. Optional reframer reshapes news/papers items into audience-targeted
hooks via Ollama; enable with PROMPT_DIGEST_REFRAME=1.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from openbrain.db import connect
from openbrain.discord_post import deliver
import urllib.request


LIMIT = int(os.environ.get("PROMPT_DIGEST_LIMIT", "12"))
LOOKBACK_HOURS = int(os.environ.get("PROMPT_DIGEST_LOOKBACK_HOURS", "48"))
REFRAME = os.environ.get("PROMPT_DIGEST_REFRAME", "0") == "1"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
REFRAME_MODEL = os.environ.get("PROMPT_DIGEST_MODEL", "llama3.2:3b")
DASHBOARD_URL = os.environ.get("OPENBRAIN_DASHBOARD_URL", "")

WEIGHTS = {"today": 1.5, "papers": 1.3, "news": 1.2, "answer": 1.1,
           "pendant": 0.4, "cal": 1.0, "proj": 1.0, "research": 0.9}
LABELS = {"today": "🎯 today", "answer": "❓ answer", "papers": "📄 papers",
          "news": "📰 news", "pendant": "🎙️ pendant", "cal": "📊 calibration",
          "proj": "🛠️ projects", "research": "🔬 research"}


def _stream_from_actor(actor):
    if not actor or ":" not in actor:
        return "research"
    prefix = actor.split(":", 1)[0]
    return prefix if prefix in WEIGHTS else "research"


def _load_candidates() -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    conn = connect()
    try:
        questions = conn.execute(
            """
            SELECT id, ts, actor, payload_json
            FROM events
            WHERE source='pattern-scan' AND type='question' AND ts >= ?
            ORDER BY ts DESC
            LIMIT 100
            """,
            (cutoff,),
        ).fetchall()
        rated = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT json_extract(payload_json,'$.target_actor') "
                "FROM events WHERE source='pattern-scan' AND type='feedback'"
            ) if r[0]
        }
        answered = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT actor FROM events "
                "WHERE source='pattern-scan' AND type='answer'"
            ) if r[0]
        }
    finally:
        conn.close()
    out = []
    now = datetime.now(timezone.utc)
    for qid, ts, actor, pj in questions:
        if actor in rated or actor in answered:
            continue
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
        score = WEIGHTS.get(stream, 1.0) * freshness
        out.append({
            "id": qid, "stream": stream, "text": text,
            "why": p.get("why", ""), "score": score,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:LIMIT]


REFRAME_PROMPT = """You are turning a research/news item into a single short
content hook. Return STRICT JSON: {{"hook": "..."}} with hook <= 140 chars,
specific, no "In conclusion", no rhetorical "Is this the death of X" setups.
Lead with the concrete fact or claim.

ITEM:
  text: {text}
  context: {why}

JSON:"""


def _reframe(text: str, why: str) -> str | None:
    body = json.dumps({
        "model": REFRAME_MODEL,
        "prompt": REFRAME_PROMPT.format(text=text[:300], why=(why or "")[:300]),
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.5, "num_ctx": 4096},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            out = json.loads(resp.read())
    except Exception:
        return None
    try:
        parsed = json.loads(out.get("response", "{}"))
    except json.JSONDecodeError:
        return None
    hook = (parsed.get("hook") or "").strip()
    if not hook:
        return None
    if len(hook) > 160:
        hook = hook[:160].rsplit(" ", 1)[0] + "…"
    return hook


REFRAME_STREAMS = {"news", "papers"}


def _format(candidates: list[dict]) -> str:
    if not candidates:
        return "🌅 morning prompts — no fresh items today."
    lines = ["🌅 **morning prompts** — today's queue:"]
    by_stream: dict[str, list[dict]] = {}
    for c in candidates:
        by_stream.setdefault(c["stream"], []).append(c)
    order = ["today", "answer", "papers", "news", "pendant", "cal", "proj", "research"]
    for stream in order:
        if stream not in by_stream:
            continue
        lines.append(f"\n{LABELS.get(stream, stream)}")
        for c in by_stream[stream]:
            text = c["text"]
            if REFRAME and stream in REFRAME_STREAMS:
                reframed = _reframe(text, c.get("why", ""))
                if reframed:
                    text = reframed
            lines.append(f"• {text}")
    if DASHBOARD_URL:
        lines.append(f"\nopen: {DASHBOARD_URL}")
    return "\n".join(lines)


def main() -> int:
    candidates = _load_candidates()
    msg = _format(candidates)
    ok, channel = deliver(msg, username="openbrain-prompts")
    print(f"prompt_digest: delivered={ok} channel={channel} prompts={len(candidates)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
