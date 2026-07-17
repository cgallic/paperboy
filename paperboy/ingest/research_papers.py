"""Ingest new AI/ML papers from arXiv + Hugging Face Daily + Semantic Scholar.

Reads config/research-sources.json for feed knobs. Writes one event per
unique paper to events.db. Idempotent: dedupes by canonical ID (arXiv id >
DOI > HF id > URL hash) stored in the actor column.

Event shape:
    source = research-papers
    type   = paper
    actor  = canonical_id (e.g. "arxiv:2402.12345")
    ts     = paper's published_at
    payload = {title, authors, abstract, url, pdf_url, code_url, categories,
               source_feeds, published_at, venue, citation_count, canonical_id}
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from paperboy.db import connect
from paperboy.stream_common import update_payload, write_event

CONTENT_MAX_CHARS = 4000
SUMMARY_EXCERPT_CHARS = 500


def _config_path() -> Path:
    p = os.environ.get("RESEARCH_SOURCES")
    if p:
        return Path(p)
    for c in [
        Path.cwd() / "config" / "research-sources.json",
        Path(__file__).resolve().parent.parent.parent / "config" / "research-sources.json",
        Path.home() / ".paperboy" / "config" / "research-sources.json",
    ]:
        if c.is_file():
            return c
    return Path.cwd() / "config" / "research-sources.json"


# ---------------------------------------------------------------------------

def fetch(url: str, *, ua: str, timeout: int, accept: str | None = None) -> tuple[bytes, str | None]:
    headers = {"User-Agent": ua}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as e:
        return b"", f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return b"", f"URL error: {e.reason}"
    except Exception as e:
        return b"", f"Fetch error: {type(e).__name__}: {e}"


def load_existing_actors() -> set[str]:
    conn = connect()
    try:
        return {
            r[0] for r in conn.execute(
                "SELECT actor FROM events "
                "WHERE source='research-papers' AND type='paper' AND actor IS NOT NULL"
            )
        }
    finally:
        conn.close()


def load_existing_payloads(actors: set[str]) -> dict[str, dict]:
    if not actors:
        return {}
    conn = connect()
    try:
        placeholders = ",".join("?" for _ in actors)
        out: dict[str, dict] = {}
        rows = conn.execute(
            f"SELECT actor, payload_json FROM events "
            f"WHERE source='research-papers' AND type='paper' AND actor IN ({placeholders})",
            tuple(actors),
        )
        for actor, pj in rows:
            with contextlib.suppress(json.JSONDecodeError):
                out[actor] = json.loads(pj)
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,6})(v\d+)?")


def canonicalize_arxiv_id(raw: str) -> str | None:
    if not raw:
        return None
    m = ARXIV_ID_RE.search(raw)
    return m.group(1) if m else None


def canonical_id(*, arxiv_id: str | None, doi: str | None,
                 hf_id: str | None, url: str | None) -> str | None:
    if arxiv_id:
        clean = canonicalize_arxiv_id(arxiv_id)
        if clean:
            return f"arxiv:{clean}"
    if doi:
        return f"doi:{doi.strip().lower()}"
    if hf_id:
        return f"hf:{hf_id.strip()}"
    if url:
        return "url:" + hashlib.sha256(url.strip().encode()).hexdigest()[:16]
    return None


def to_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        cleaned = raw.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        dt = datetime.strptime(raw.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------------------

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(cfg: dict, ua: str, timeout: int, verbose: bool) -> list[dict]:
    cats = cfg.get("categories", ["cs.AI"])
    search_query = "+OR+".join(f"cat:{c}" for c in cats)
    max_results = int(cfg.get("max_per_run", 200))
    url = (
        f"{cfg['api_url']}?search_query={search_query}"
        f"&start=0&max_results={max_results}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    if verbose:
        print(f"[arxiv] fetching {url}", file=sys.stderr)
    body, err = fetch(url, ua=ua, timeout=timeout, accept="application/atom+xml")
    if err:
        print(f"[arxiv] fetch failed: {err}", file=sys.stderr)
        return []
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as e:
        print(f"[arxiv] XML parse error: {e}", file=sys.stderr)
        return []
    papers: list[dict] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        id_text = (entry.findtext(f"{ATOM_NS}id") or "").strip()
        arxiv_id = canonicalize_arxiv_id(id_text)
        if not arxiv_id:
            continue
        title = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM_NS}title") or "")).strip()
        abstract = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM_NS}summary") or "")).strip()
        published = to_iso(entry.findtext(f"{ATOM_NS}published"))
        authors = [
            (a.findtext(f"{ATOM_NS}name") or "").strip()
            for a in entry.findall(f"{ATOM_NS}author")
            if a.findtext(f"{ATOM_NS}name")
        ]
        categories = [
            c.get("term", "") for c in entry.findall(f"{ATOM_NS}category")
            if c.get("term")
        ]
        pdf_url = None
        abs_url = None
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_url = link.get("href")
            elif link.get("rel") == "alternate":
                abs_url = link.get("href")
        papers.append({
            "arxiv_id": arxiv_id, "doi": None, "hf_id": None,
            "title": title, "abstract": abstract, "authors": authors,
            "url": abs_url or f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf_url, "code_url": None, "categories": categories,
            "published_at": published, "venue": None, "citation_count": None,
            "source_feed": "arxiv",
        })
    if verbose:
        print(f"[arxiv] parsed {len(papers)} entries", file=sys.stderr)
    return papers


def fetch_hf_papers(cfg: dict, ua: str, timeout: int, verbose: bool) -> list[dict]:
    url = cfg["api_url"]
    if verbose:
        print(f"[hf] fetching {url}", file=sys.stderr)
    body, err = fetch(url, ua=ua, timeout=timeout, accept="application/json")
    if err:
        print(f"[hf] fetch failed: {err}", file=sys.stderr)
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"[hf] JSON parse error: {e}", file=sys.stderr)
        return []
    papers: list[dict] = []
    max_n = int(cfg.get("max_per_run", 50))
    for item in (data if isinstance(data, list) else [])[:max_n]:
        paper = item.get("paper") if isinstance(item, dict) else None
        if not paper:
            continue
        hf_id = (paper.get("id") or "").strip()
        arxiv_id = canonicalize_arxiv_id(hf_id) or canonicalize_arxiv_id(paper.get("arxivId", ""))
        title = (paper.get("title") or "").strip()
        abstract = (paper.get("summary") or "").strip()
        authors = [
            (a.get("name") or a.get("user", {}).get("fullname") or "").strip()
            for a in (paper.get("authors") or [])
        ]
        authors = [a for a in authors if a]
        published = to_iso(paper.get("publishedAt") or item.get("publishedAt"))
        abs_url = f"https://huggingface.co/papers/{hf_id}" if hf_id else None
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None
        papers.append({
            "arxiv_id": arxiv_id, "doi": None, "hf_id": hf_id,
            "title": title, "abstract": abstract, "authors": authors,
            "url": abs_url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
            "pdf_url": pdf_url, "code_url": None, "categories": [],
            "published_at": published, "venue": "HF Daily",
            "citation_count": int(paper.get("upvotes", 0) or 0) or None,
            "source_feed": "hf_papers",
        })
    if verbose:
        print(f"[hf] parsed {len(papers)} entries", file=sys.stderr)
    return papers


def fetch_semantic_scholar(cfg: dict, ua: str, timeout: int, verbose: bool) -> list[dict]:
    base = cfg["api_url"]
    fields = cfg.get("fields", "title,abstract,authors,year,externalIds,publicationDate,openAccessPdf,url")
    max_per_query = int(cfg.get("max_per_query", 20))
    max_total = int(cfg.get("max_per_run", 120))
    queries = cfg.get("topic_queries", [])
    sleep_s = float(cfg.get("inter_request_sleep_sec", 1.5))
    papers: list[dict] = []
    for q in queries:
        if len(papers) >= max_total:
            break
        params = {"query": q, "fields": fields, "limit": max_per_query,
                  "sort": "publicationDate:desc"}
        url = f"{base}?{urllib.parse.urlencode(params)}"
        if verbose:
            print(f"[s2] query={q!r}", file=sys.stderr)
        body, err = fetch(url, ua=ua, timeout=timeout, accept="application/json")
        time.sleep(sleep_s)
        if err:
            print(f"[s2] {q!r}: {err}", file=sys.stderr)
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            print(f"[s2] JSON parse error: {e}", file=sys.stderr)
            continue
        for paper in data.get("data", []):
            if len(papers) >= max_total:
                break
            ext = paper.get("externalIds") or {}
            arxiv_id = canonicalize_arxiv_id(ext.get("ArXiv") or "")
            doi = ext.get("DOI")
            authors = [(a.get("name") or "").strip() for a in (paper.get("authors") or [])]
            authors = [a for a in authors if a]
            pdf = (paper.get("openAccessPdf") or {}).get("url")
            url_field = paper.get("url") or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None)
            papers.append({
                "arxiv_id": arxiv_id, "doi": doi, "hf_id": None,
                "title": (paper.get("title") or "").strip(),
                "abstract": (paper.get("abstract") or "").strip(),
                "authors": authors, "url": url_field or "", "pdf_url": pdf,
                "code_url": None, "categories": [],
                "published_at": to_iso(paper.get("publicationDate")),
                "venue": (paper.get("venue") or "").strip() or None,
                "citation_count": paper.get("citationCount"),
                "source_feed": "semantic_scholar",
            })
    if verbose:
        print(f"[s2] parsed {len(papers)} entries", file=sys.stderr)
    return papers


# ---------------------------------------------------------------------------

def dedup_and_merge(raw_papers: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for p in raw_papers:
        cid = canonical_id(
            arxiv_id=p.get("arxiv_id"), doi=p.get("doi"),
            hf_id=p.get("hf_id"), url=p.get("url"),
        )
        if not cid:
            continue
        if cid in merged:
            existing = merged[cid]
            feeds = set(existing.get("source_feeds", []))
            feeds.add(p["source_feed"])
            existing["source_feeds"] = sorted(feeds)
            for k in ("pdf_url", "code_url", "citation_count", "venue", "doi", "hf_id"):
                if not existing.get(k) and p.get(k):
                    existing[k] = p[k]
            if not existing.get("categories") and p.get("categories"):
                existing["categories"] = p["categories"]
            continue
        merged[cid] = {
            "canonical_id": cid,
            "title": p["title"], "abstract": p["abstract"], "authors": p["authors"],
            "url": p["url"], "pdf_url": p.get("pdf_url"), "code_url": p.get("code_url"),
            "categories": p.get("categories", []),
            "source_feeds": [p["source_feed"]],
            "published_at": p.get("published_at"),
            "venue": p.get("venue"), "citation_count": p.get("citation_count"),
        }
    return merged


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="all",
                    choices=["all", "arxiv", "hf", "s2"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg_path = _config_path()
    if not cfg_path.exists():
        print(json.dumps({"status": "error", "error": f"missing {cfg_path}"}), file=sys.stderr)
        sys.exit(1)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ua = cfg.get("user_agent", "paperboy/0.1")
    timeout = int(cfg.get("fetch_timeout_sec", 30))
    inter_sleep = float(cfg.get("inter_request_sleep_sec", 1.5))

    selected = {"all": ["arxiv", "hf_papers", "semantic_scholar"],
                "arxiv": ["arxiv"], "hf": ["hf_papers"],
                "s2": ["semantic_scholar"]}[args.source]
    feeds_cfg = cfg.get("feeds", {})
    raw_papers: list[dict] = []
    per_feed_counts: dict[str, int] = {}

    for feed_name in selected:
        feed_cfg = feeds_cfg.get(feed_name, {})
        if not feed_cfg.get("enabled", True):
            if args.verbose:
                print(f"[{feed_name}] disabled in config", file=sys.stderr)
            continue
        if feed_name == "arxiv":
            got = fetch_arxiv(feed_cfg, ua, timeout, args.verbose)
        elif feed_name == "hf_papers":
            got = fetch_hf_papers(feed_cfg, ua, timeout, args.verbose)
        elif feed_name == "semantic_scholar":
            got = fetch_semantic_scholar(feed_cfg, ua, timeout, args.verbose)
        else:
            got = []
        raw_papers.extend(got)
        per_feed_counts[feed_name] = len(got)
        time.sleep(inter_sleep)

    merged = dedup_and_merge(raw_papers)
    if args.verbose:
        print(f"[merge] {len(raw_papers)} raw → {len(merged)} unique", file=sys.stderr)

    existing = load_existing_actors()
    existing_payloads = load_existing_payloads(existing & set(merged.keys()))

    stats: dict[str, Any] = {
        "raw_total": len(raw_papers), "unique_total": len(merged),
        "new_ingested": 0, "updated_feed_list": 0, "skipped_existing": 0,
        "errors": 0, "would_ingest": 0, "per_feed_counts": per_feed_counts,
    }
    ingested_this_run = 0
    for cid, paper in merged.items():
        if cid in existing:
            stats["skipped_existing"] += 1
            old = existing_payloads.get(cid)
            if not old:
                continue
            old_feeds = set(old.get("source_feeds", []))
            new_feeds = old_feeds | set(paper["source_feeds"])
            if new_feeds != old_feeds and not args.dry_run:
                old["source_feeds"] = sorted(new_feeds)
                update_payload(
                    source="research-papers", event_type="paper",
                    actor=cid, payload=old,
                )
                stats["updated_feed_list"] += 1
            continue
        if args.limit and ingested_this_run >= args.limit:
            break

        title = paper["title"] or "(no title)"
        abstract = paper["abstract"] or ""
        excerpt = abstract[:SUMMARY_EXCERPT_CHARS].strip()
        summary = f"{title}\n{excerpt}" if excerpt else title
        ts = paper.get("published_at") or datetime.now(timezone.utc).isoformat()
        payload = {
            "summary": summary, "title": title, "authors": paper.get("authors", []),
            "abstract": abstract[:CONTENT_MAX_CHARS],
            "url": paper.get("url") or "", "pdf_url": paper.get("pdf_url"),
            "code_url": paper.get("code_url"), "categories": paper.get("categories", []),
            "source_feeds": paper.get("source_feeds", []), "published_at": ts,
            "venue": paper.get("venue"), "citation_count": paper.get("citation_count"),
            "canonical_id": cid,
        }
        if args.dry_run:
            stats["would_ingest"] += 1
            if args.verbose:
                print(f"[would] {cid}  {title[:70]}", file=sys.stderr)
            continue
        eid = write_event(
            source="research-papers", event_type="paper",
            actor=cid, ts=ts, payload=payload,
        )
        if eid:
            stats["new_ingested"] += 1
            ingested_this_run += 1
            if args.verbose:
                feeds = ",".join(paper.get("source_feeds", []))
                print(f"[ok] {cid}  [{feeds}]  {title[:70]}", file=sys.stderr)
        else:
            stats["errors"] += 1

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
