# paperboy

> Old paperboys delivered one newspaper to one house. This one reads ten
> thousand things and delivers the twelve that matter to you.

A daily Discord digest of news + research papers, scored by your local LLM
against your own interests. No cloud, no SaaS, no account.

Drop your favorite RSS feeds in `news_sources.yaml`. Describe your stack in
`research-interests.md`. Wake up to a Discord post like this:

```
🌅 morning prompts — today's queue:

📄 papers
• Diff-Transformer — applies to my-agent. Take?
• Self-Critique-via-Rubric vs. constitutional AI — applies to my-rag. Take?

📰 news
• Anthropic shipped tool-streaming. What changes for orchestrator+worker stacks?
• OpenAI's new pricing tier kills the gap for self-hosted Whisper. Hot take?

❓ answer
• How do you choose between Q3_K_M and Q4_K_M quantization for a 24GB GPU?

🎯 today
• Revive or kill: weekend-experiment (dead 17d) — pick one before EOD.
```

The bot also posts a separate **Research Digest** message with the top 3
papers scored ≥ 7/10 against your stack, each with a one-line "how WE'd apply
it" note from your local LLM.

---

## What this gives you

Seven cron jobs that work together:

1. **`research-ingest`** — pulls new papers daily from arXiv + HF Daily Papers
   + Semantic Scholar.
2. **`research-score`** — local LLM rates each paper 0-10 for whether it could
   improve one of YOUR systems (grounded by `research-interests.md`).
3. **`news-opinion`** — fetches RSS feeds grouped by vertical, drafts a sharp
   hot-take prompt per item via local LLM.
4. **`papers-to-prompts`** — promotes top-scored papers into the morning queue.
5. **`topical-questions`** — picks AEO-shaped questions from YOUR pillar map.
6. **`today-briefing`** — parses a daily-brief markdown file (optional) for
   carry-overs and "dead repo" callouts.
7. **`prompt-digest`** — assembles + posts the morning digest to Discord.
8. **`research-digest`** — posts the top-3 newly-scored papers separately.

All of them write to one SQLite events.db. Everything is dedup'd by content
hash, so re-runs are idempotent.

## What you need

- A Linux box with `systemd` (any small VPS or homelab machine works)
- [Ollama](https://ollama.com/) running locally with one fast model (e.g.
  `llama3.2:3b`) and one stronger model (e.g. `qwen2.5:7b`)
- A Discord webhook (or a bot token + channel ID)
- Python 3.10+

That's it. No Postgres, no Redis, no Docker, no cloud accounts.

## Install

```bash
git clone https://github.com/cgallic/paperboy.git
cd paperboy
sudo ./scripts/bootstrap.sh
```

Then:

1. Edit `/etc/paperboy/paperboy.env` — set `DISCORD_WEBHOOK`.
2. Edit `/etc/paperboy/news_sources.yaml` — your RSS feeds, by topic.
3. Edit `/etc/paperboy/research-interests.md` — describe YOUR systems.
   This is the most important file — without it, the scorer can't tell what
   matters to you.
4. (Optional) Edit `/etc/paperboy/topical-map.md` — your content pillars.

Test:

```bash
sudo systemctl start paperboy-news-opinion.service
journalctl -u paperboy-news-opinion.service -n 50
```

See [docs/INSTALL.md](docs/INSTALL.md) for the full walkthrough.

## Architecture (one diagram)

```
            morning UTC                       

10:00 │ research-ingest  ──► events.db (paper events)
10:45 │ research-score   ──► events.db (paper-score events, via local Ollama)
11:00 │ news-opinion     ──► events.db (pattern-scan/question, stream=news)
11:05 │ papers-to-prompts ──► events.db (stream=papers)
11:08 │ topical-questions ──► events.db (stream=answer)
11:10 │ today-briefing   ──► events.db (stream=today)
11:15 │ prompt-digest    ──► Discord  (the morning post)
12:00 │ research-digest  ──► Discord  (separate top-3 paper post)
```

One SQLite table. Twelve env vars. Zero queues, zero brokers.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full data model and
event schema.

## Customizing

Most of the value comes from tuning the config files, not the code. See
[docs/personalizing.md](docs/personalizing.md) for:

- Adding/removing news verticals
- Writing a good `research-interests.md` (the scorer's grounding)
- Building your own topical map
- Optional: enabling LLM reframing of prompts into audience-targeted hooks

## Roadmap

`paperboy` is the foundation. Five sibling repos are coming that build on the
same events.db schema:

- **paperboy-ingesters** — connectors for your gmail, chatgpt history, audible,
  linkedin, etc. — all dumping to the same events table.
- **paperboy-wiki** — turn your events into a markdown knowledge graph with
  semantic search.
- **pendant-android** — a custom Android app for the Omi-style audio pendant
  that streams raw BLE to your agent box.
- **pendant-pipeline** — agent-side audio pipeline (decoder → STT → diarizer →
  wake-word → realtime directive) writing to paperboy's event store.
- **casa-a2a** — JSON-RPC 2.0 broker + skill-sidecar pattern for cross-host
  agent coordination.

See [docs/ROADMAP.md](docs/ROADMAP.md) for what's coming and timing.

## License

MIT. See [LICENSE](LICENSE).
