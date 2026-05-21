# Roadmap

openbrain is the first of six planned repos that share the same `events.db`
schema. Each one stands alone, but they compose: install just openbrain and
you get a working morning digest; layer the others on as you want more.

Below is the planned order. Status updates land here when each repo ships.

## ✅ openbrain (this repo) — v0.1 shipped

News + papers + Discord digest. The core pipeline. See [README.md](../README.md).

---

## 🟡 openbrain-ingesters — planned

Connectors that dump YOUR personal accounts into the same `events` table.
Each is one Python script + one systemd timer. All idempotent.

Planned coverage (drawn from a working personal codebase, ~100k LOC to extract):

| Connector | Source | Event type | Status |
|---|---|---|---|
| `gmail` | Gmail API (DWD) | `gmail/message` | Working in source, extraction pending |
| `chatgpt` | ChatGPT history export | `chatgpt/conversation` | Working in source |
| `audible` | Audible library scrape | `audible/book` | Working in source |
| `linkedin` | LinkedIn data export | `linkedin/post`, `linkedin/connection` | Working in source |
| `discord-history` | Discord channel backfill | `discord/message` | Working in source |
| `anthropic-claude` | Claude conversation history | `anthropic/conversation` | Working in source |
| `snapchat` | Snapchat data export | `snapchat/snap` | Working in source |

Once any of these are populated, openbrain's existing scanners stay the same
— they just have more data to work with. The wiki repo (below) then turns
that data into a knowledge graph.

**Why it's separate**: privacy. Some people will only want the public-facing
news + papers pipeline. Others want their whole life indexed. Splitting lets
you choose.

---

## 🟡 openbrain-wiki — planned

Turn your events.db into a queryable markdown knowledge graph:

- `embed_events.py` — embed every event into Qdrant (nomic-embed-text or
  qwen3-embedding)
- `compile_wiki.py` — nightly job that turns event clusters into typed markdown
  pages (people, projects, decisions, topics)
- `query_brain.py` — natural-language CLI: "what did I work on last week?"
- `semantic_search.py` — direct Qdrant query CLI

Depends on **openbrain** (events.db schema) but not on **openbrain-ingesters**
— you can run it on just the news + papers data.

**Why it's separate**: requires Qdrant + larger model. Adds non-trivial deps
that the core pipeline doesn't need.

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
                              realtime-directive       openbrain events.db
                                   ▼                   (source=pendant)
                              handoff doc → /schedule
```

Writes `pendant/conversation` events into openbrain's events.db. The
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
across them is the events.db schema — defined in `openbrain/db.py`. As long
as a new ingester writes rows with `source`, `type`, `actor`, `ts`,
`payload_json`, `ingested_at`, it composes.

Suggested install order if you want the full stack:

1. `openbrain` (this repo) — proves the digest works
2. `openbrain-ingesters` — start adding your personal data
3. `openbrain-wiki` — once you have a few thousand events, turn them into a
   queryable graph
4. `casa-a2a` — when you want cross-host agents
5. `pendant-android` + `pendant-pipeline` — if you have the hardware

## Want a specific repo sooner?

Open an issue. Order is flexible based on what people actually want.
