# Architecture

The whole system fits in one diagram and one table. If you understand
**events.db**, you understand paperboy.

## Data flow

```
                       ┌──────────────────┐
   RSS feeds           │  news_opinion    │  pattern-scan/question, stream=news
   (news_sources.yaml) │                  │ ──┐
                       └──────────────────┘   │
                                              │
                       ┌──────────────────┐   │
   arXiv + HF + S2 ──► │ research-ingest  │   │   research-papers/paper
                       │                  │   │
                       └────────┬─────────┘   │
                                │             │       ┌───────────────────┐
                                ▼             │       │                   │
                       ┌──────────────────┐   │   ┌──►│   events.db       │
                       │ research-score   │   │   │   │   (SQLite)        │
                       │                  │ ──┼───┘   │                   │
                       │ (local Ollama,   │   │       └────────┬──────────┘
                       │  grounded by     │   │                │
                       │  interests.md)   │   │                │
                       └────────┬─────────┘   │                │
                                │ paper-score │                │
                                ▼             │                ▼
                       ┌──────────────────┐   │       ┌──────────────────┐
                       │ papers-to-prompt │   │       │ prompt-digest    │
                       │ (top-N → queue)  │ ──┘   ┌──►│                  │ ──► Discord
                       └──────────────────┘       │   └──────────────────┘
                                                  │
   topical-map.md ──► topical-questions ──────────┤
   daily-briefs/ ───► today-briefing ─────────────┘

                       ┌──────────────────┐
   research-papers ──► │ research-digest  │ ──► Discord (top-3 papers)
   (paper-score)       └──────────────────┘
```

## The one table you need to know

`events.db` has two tables. The interesting one is `events`:

```sql
CREATE TABLE events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,  -- ISO 8601 UTC of when the event occurred
    source          TEXT    NOT NULL,  -- coarse-grained: news_opinion | research-papers | pattern-scan | ...
    type            TEXT    NOT NULL,  -- fine-grained:  paper | paper-score | question | ...
    actor           TEXT,               -- idempotency key (sha1 slug, arxiv id, etc.)
    payload_json    TEXT    NOT NULL,  -- structured content
    attachment_uri  TEXT,               -- optional blob pointer (unused by paperboy core)
    ingested_at     TEXT    NOT NULL   -- when the row was written
);
```

Plus `event_tags(event_id, tag)` for cheap multi-tag lookups.

The schema is intentionally tiny. It's an append-only log; nothing ever
mutates. Idempotency comes from unique `(source, type, actor)` keys —
re-running a scanner with the same content produces the same `actor` slug
and the row is skipped.

## What each pipeline writes

| Source | Type | Actor | Payload (key fields) |
|---|---|---|---|
| `research-papers` | `paper` | `arxiv:2402.12345` (canonical id) | `title, authors, abstract, url, source_feeds[]` |
| `research-papers` | `paper-score` | same canonical id | `relevance, applies_to[], improvement_idea, novelty, should_prototype, why` |
| `pattern-scan` | `question` | `<stream>:<sha1_12>` | `text, why, evidence[], stream` |
| `pattern-scan` | `feedback` | (rating event — not written by paperboy core, room for future thumbs-up/down loop) | `target_actor, rating` |
| `pattern-scan` | `answer` | (when YOU answer a prompt — also future) | `target_actor, answer_text` |

The `pattern-scan/question` rows have an actor like `news:abc123def456` or
`papers:abc123def456`. The prefix is the **stream**. Streams have different
weights in the morning digest:

| Stream | Weight | What it means |
|---|---|---|
| `today` | 1.5× | From your daily brief — most urgent |
| `papers` | 1.3× | Top-scored research paper |
| `news` | 1.2× | Hot take on a news item |
| `answer` | 1.1× | From your topical map |
| `cal`, `proj` | 1.0× | (reserved for future scanners) |
| `research` | 0.9× | (legacy / other) |
| `pendant` | 0.4× | (reserved for the pendant pipeline — low signal-to-noise) |

The digest also weighs by **freshness**: a 2-hour-old prompt scores 1.0×, a
40-hour-old prompt scores ~0.17×. The final score is `stream_weight ×
freshness`, top-N sorted, then grouped by stream in display.

## The scorer's contract

`research-interests.md` IS the system prompt. It gets injected verbatim into
every scoring call. Format:

```markdown
## My systems (slugs the scorer uses in `applies_to`)
- **`<slug>`** — one-line description of what it does.

## Active themes
- bullet points of areas you care about

## Tech stack
- bullet points of concrete tech you run

## What to score LOW
## What to score HIGH
```

The scorer returns strict JSON:

```json
{
  "relevance": 0,
  "applies_to": ["my-rag"],
  "improvement_idea": "≤240 chars",
  "novelty": "low|medium|high",
  "should_prototype": false,
  "why": "≤240 chars"
}
```

If the LLM returns garbage JSON, the paper is skipped (logged as `parse_errors`
in the run stats).

## Why SQLite

- One file, easy to back up
- Append-only is a natural fit for events
- `json_extract(payload_json, '$.relevance')` is a real index option
- No daemon, no port, no auth
- 945k+ events still query in <100ms with the indexes shipped here

If you outgrow it, the events table maps trivially to Postgres. But you
probably won't — disk is cheap and SQLite handles tens of GB without breaking
a sweat.

## What's deliberately NOT here

- **No queue/broker.** Timers + a SQLite write lock are enough.
- **No web UI.** Discord is the UI. Hot take: it's a better UI.
- **No vector search.** The morning digest is small enough that scoring +
  weighting is all you need. (Vector search shows up in the planned
  `paperboy-wiki` repo.)
- **No auth.** Local-only. If you expose this to the internet, that's on you.
- **No tests.** This is the v0.1 cut from a personal codebase. Tests come
  with v0.2.
