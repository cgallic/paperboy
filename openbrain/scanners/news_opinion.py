"""News-opinion scanner — RSS feeds, grouped by vertical, -> 'hot take?' prompts.

Reads config/news_sources.yaml (path overridable via NEWS_SOURCES env var).
For each vertical, fetches each feed, picks up to MAX_PER_VERTICAL items, asks
local Ollama to draft a short opinion prompt, then writes a pattern-scan/question
event with stream='news'. Dedups across runs via stream_common's actor slug.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from openbrain.stream_common import (
    write_prompt_event, recent_actors_by_stream, slug_for_stream
)

MAX_PER_VERTICAL = int(os.environ.get("NEWS_MAX_PER_VERTICAL", "2"))
FETCH_TIMEOUT = int(os.environ.get("NEWS_FETCH_TIMEOUT", "12"))
USER_AGENT = "openbrain/0.1 (+https://github.com/cgallic/openbrain)"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("NEWS_MODEL", os.environ.get("OPENBRAIN_FAST_MODEL", "llama3.2:3b"))


def _sources_path() -> Path:
    p = os.environ.get("NEWS_SOURCES")
    if p:
        return Path(p)
    # Try (in order): cwd/config, package-local config, ~/.openbrain/config
    candidates = [
        Path.cwd() / "config" / "news_sources.yaml",
        Path(__file__).resolve().parent.parent.parent / "config" / "news_sources.yaml",
        Path.home() / ".openbrain" / "config" / "news_sources.yaml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


def _load_sources() -> dict[str, list[str]]:
    try:
        import yaml
    except ImportError:
        print("[news_opinion] PyYAML not installed; run: pip install pyyaml", file=sys.stderr)
        return {}
    path = _sources_path()
    if not path.is_file():
        print(f"[news_opinion] no sources file at {path}", file=sys.stderr)
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _fetch_feed(url: str) -> list[dict]:
    """Return a list of {title, link, summary} dicts from an RSS/Atom feed."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = resp.read()
    except Exception:
        return []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    items: list[dict] = []
    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "summary": desc[:400]})
    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("a:title", namespaces=ns) or "").strip()
        link_el = entry.find("a:link", namespaces=ns)
        link = (link_el.get("href") if link_el is not None else "") or ""
        summary = (entry.findtext("a:summary", namespaces=ns) or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "summary": summary[:400]})
    return items[:20]


PROMPT = """\
A new piece of {vertical} news landed. Draft ONE short opinion prompt
phrased as a question that invites a sharp take (good blog material).

Style: direct, specific, <= 140 chars. Reference the actual move, not generic
framing. Do NOT include the URL in the text.

NEWS:
title: {title}
summary: {summary}

Return STRICT JSON: {{"text": "...", "why": "...", "evidence": ["..."]}}"""


def _ollama_json(prompt: str) -> dict:
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.5, "num_ctx": 4096},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read())
    try:
        return json.loads(out.get("response", "{}"))
    except json.JSONDecodeError:
        return {}


def llm_draft_prompt(vertical: str, item: dict) -> dict:
    return _ollama_json(PROMPT.format(
        vertical=vertical,
        title=item.get("title", ""),
        summary=item.get("summary", ""),
    ))


def run(dry_run: bool = False) -> int:
    sources = _load_sources()
    seen = set(recent_actors_by_stream("news", days=14))
    written = 0
    for vertical, feeds in sources.items():
        per_vert = 0
        for url in feeds:
            if per_vert >= MAX_PER_VERTICAL:
                break
            items = _fetch_feed(url)
            for item in items:
                if per_vert >= MAX_PER_VERTICAL:
                    break
                candidate_text = f"Hot take on {item['title']}?"
                if slug_for_stream("news", candidate_text) in seen:
                    continue
                draft = llm_draft_prompt(vertical, item)
                text = (draft.get("text") or "").strip()
                if not text:
                    continue
                if slug_for_stream("news", text) in seen:
                    continue
                ev = draft.get("evidence", [item["link"]])
                if not isinstance(ev, list):
                    ev = [str(ev)]
                if dry_run:
                    print(f"[{vertical}] {text}\n  why: {draft.get('why','')}\n  link: {item['link']}")
                    seen.add(slug_for_stream("news", text))
                    per_vert += 1
                    written += 1
                    continue
                eid = write_prompt_event(
                    stream="news",
                    kind="question",
                    text=text,
                    why=draft.get("why", f"{vertical} news"),
                    evidence=ev + [item["link"]],
                    extra_tags={f"vertical:{vertical}"},
                )
                if eid:
                    seen.add(slug_for_stream("news", text))
                    written += 1
                    per_vert += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    n = run(dry_run=args.dry_run)
    print(f"news_opinion: {n} prompts emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
