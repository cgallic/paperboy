# Roadmap

paperboy is one consumer of a larger event-log architecture. The foundation
already exists as a separate repo (**[open-brane](https://github.com/cgallic/open-brane)** —
"an event-log brain for people who keep losing context"). paperboy adds the
news + research-paper domain on top.

The full picture looks like this:

```
        ┌─────────────────────────────────────────────┐
        │  cgallic/open-brane                         │
        │  • events.db schema (THE source of truth)   │
        │  • record_event.py (the one write path)     │
        │  • MCP server for agents                    │
        │  • Canonical adapters: gdrive, claude, git  │
        │  • embed_events.py + semantic_search.py     │
        └────────────────────┬────────────────────────┘
                             │ schema = (ts, source, type,
                             │           actor, payload_json,
                             │           attachment_uri,
                             │           ingested_at)
                             │
            ┌────────────────┼─────────────────┬───────────────┐
            │                │                 │               │
            ▼                ▼                 ▼               ▼
      cgallic/paperboy   future ingester   pendant-pipeline   casa-a2a
      (this repo)        repos (more       (planned)          (planned)
                          adapters)
```

Below is the planned order. Status updates land here when each repo ships.

---

## ✅ cgallic/paperboy (this repo) — v0.1 shipped

News + papers + Discord digest. The core pipeline. See [README.md](../README.md).
A consumer of open-brane's events.db schema — writes `pattern-scan`,
`research-papers/paper`, and `research-papers/paper-score` event types.

## ✅ cgallic/open-brane — already shipped

The event-log foundation. Not part of this roadmap because it predates
paperboy; included here as context. If you want to install the full stack,
[start with open-brane](https://github.com/cgallic/open-brane), then add
paperboy.

## 🟡 More open-brane adapters — open-brane PR / future repos

The personal-data connectors not yet in open-brane (drawn from a working
personal codebase, ~100k LOC):

| Adapter | Source | Status |
|---|---|---|
| `gmail` | Gmail API (DWD) | not yet shipped |
| `chatgpt` | ChatGPT history export | not yet shipped |
| `audible` | Audible library scrape | not yet shipped |
| `linkedin` | LinkedIn data export | not yet shipped |
| `discord-history` | Discord channel backfill | not yet shipped |
| `anthropic-claude` | Claude conversation history | not yet shipped |
| `snapchat` | Snapchat data export | not yet shipped |

These will land either as PRs to open-brane or as separate "open-brane
adapter" repos — TBD per source based on what makes sense.

## 🟡 markdown KG / wiki compiler — planned, name TBD

Turns events.db into a typed markdown knowledge graph (people, projects,
decisions, topics) with a natural-language query CLI. Open-brane already
ships `embed_events.py` + `semantic_search.py` (the vector layer), so this
repo is just the markdown compiler + NL query CLI.

Not yet shipped. Name TBD at extraction time.

## 🟡 cgallic/pendant-android — planned

A custom Android app (Kotlin) for the [Omi](https://omi.me/) audio pendant.
Streams raw BLE audio to your agent box for real-time processing.

The stock Omi app routes through Omi's cloud. This app routes to YOUR box.
Already working in a private fork — extraction is mechanical.

**Why it's separate**: hardware-specific. Most people don't have a pendant.

---

## 🟡 cgallic/pendant-pipeline — planned

The agent-side audio pipeline that consumes the pendant's BLE stream:

```
BLE bytes ─► decoder ─► STT (Deepgram or local Whisper) ─► diarizer
                                                             │
                                            ┌────────────────┤
                                            ▼                ▼
                                   wakeword ("kai action")  conversation summarizer
                                   ▼                         ▼
                              realtime-directive       open-brane events.db
                                   ▼                   (source=pendant)
                              handoff doc → /schedule
```

Writes `pendant/conversation` events into open-brane's events.db. The
paperboy `prompt-digest` scanner already has a `pendant` stream weight
ready — once this ships, the morning digest surfaces "open threads from
yesterday's pendant conversations" automatically.

**Why it's separate**: many services, GPU dependency, hardware coupling.

---

## 🟡 cgallic/casa-a2a — planned

A JSON-RPC 2.0 broker + skill-sidecar pattern for cross-host agent
coordination. Lets you wire scout/kai/hale/anyone as A2A peers with
data-driven skills.json files.

This is the most novel + smallest piece — probably the easiest to ship
standalone. Currently 5 files + 3k LOC.

**Why it's separate**: people who want JUST the broker pattern, not the
whole brain.

---

## 🟡 pendant-android — planned

A custom Android app (Kotlin) for the [Omi](https://omi.me/) audio pendant.
Streams raw BLE audio to your agent box for real-time processing.

The stock Omi app routes through Omi's cloud. This app routes to YOUR box.
Already working in a private fork — extraction is mechanical.

**Why it's separate**: hardware-specific. Most people don't have a pendant.
Lives in its own repo so people can find it.

---

## 🟡 pendant-pipeline — planned

The agent-side audio pipeline that consumes the pendant's BLE stream:

```
BLE bytes ─► decoder ─► STT (Deepgram or local Whisper) ─► diarizer
                                                             │
                                            ┌────────────────┤
                                            ▼                ▼
                                   wakeword ("kai action")  conversation summarizer
                                   ▼                         ▼
                              realtime-directive       paperboy events.db
                                   ▼                   (source=pendant)
                              handoff doc → /schedule
```

Writes `pendant/conversation` events into paperboy's events.db. The
`prompt-digest` scanner already has a `pendant` stream weight ready — once
this ships, the morning digest surfaces "open threads from yesterday's
pendant conversations" automatically.

**Why it's separate**: many services, GPU dependency, hardware coupling.

---

## 🟡 casa-a2a — planned

A JSON-RPC 2.0 broker + skill-sidecar pattern for cross-host agent
coordination. Lets you wire scout/kai/hale/anyone as A2A peers with
data-driven skills.json files.

This is the most novel + smallest piece — probably the easiest to ship
standalone. Currently 5 files + 3k LOC.

**Why it's separate**: people who want JUST the broker pattern, not the
whole brain. Could also work for non-personal multi-agent setups.

---

## Ordering rationale

Each repo is independent. You can install in any order. The "shared" thing
across them is the events.db schema — defined and owned by
[**open-brane**](https://github.com/cgallic/open-brane).

paperboy ships its own `db.py` with a compatible schema so you can run
paperboy standalone (without open-brane installed) and just get the news
+ papers digest. If you later install open-brane and point
`PAPERBOY_DB` at open-brane's events.db, every other ingester populates
the same store and paperboy's digest gets richer automatically.

Suggested install order if you want the full stack:

1. **[open-brane](https://github.com/cgallic/open-brane)** — the foundation
2. **paperboy** (this repo) — adds news + papers + Discord digest
3. **markdown KG / wiki compiler** — once you have a few thousand events
4. **casa-a2a** — when you want cross-host agents
5. **pendant-android** + **pendant-pipeline** — if you have the hardware

## Want a specific repo sooner?

Open an issue. Order is flexible based on what people actually want.
