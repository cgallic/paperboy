# paperboy

> Old paperboys delivered one newspaper to one house. This one reads ten
> thousand things and delivers the twelve that matter to you.

A daily Discord digest of news + research papers, scored by your local LLM
against your own interests. The self-hosted edition needs no Paperboy cloud
account or hosted subscription.

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

## Daily Intelligence Brief product sample

The hosted product direction is the **Paperboy Daily Intelligence Brief**: one
ranked morning edition assembled from explicitly forwarded newsletters, public
news/research/data, and optional selected GitHub repositories. Repo Radar is a
section of that edition, not a separate product. Suggested actions remain inert
text for human review.

The public founding beta is at **[newpaperboy.com](https://newpaperboy.com/)**. The original
`paperboy.kaibuilds.com` host remains available for existing links and callbacks.
Its live automatic intake is currently narrower than that product direction:
it previews and saves user-selected public RSS/Atom feeds, verifies the delivery
email, and activates scheduled delivery only after hosted checkout confirms a
trial. The page reports checkout availability live; a preview or verified email
is not a paid subscription.

This repository includes a deterministic, local-only sample of the selection
and email-rendering boundary. It makes no network calls, sends no email, and
uses sanitized fixture inputs. Relevance thresholds, edition size, and
per-source diversity are explicit configuration so plan limits can change
without changing ranking logic.

```bash
python -m paperboy.daily_brief.cli \
  --input examples/daily-brief.sample.json \
  --out-dir .local/daily-brief
```

The command writes plain-text and HTML previews. Run it with
`examples/daily-brief.quiet.json` to see the one-line quiet edition used when
nothing clears the relevance bar; it never pads the brief with weak items.

---

## News → Agent Action Queue

A file-first bridge that promotes the highest-signal digest items (papers
scored ≥ 7 or flagged `should_prototype`, plus the top-weighted prompts) into a
**reviewable queue of agent tasks** — each with a concrete `suggested_action`.

It writes an append-only JSONL queue and a rendered Markdown view, and sends
**nothing** (no Discord, no webhook). The queue is a human review gate: an
agent acts only on items you've marked `approved`.

```bash
python -m paperboy.digest.action_queue          # write queue (JSONL + Markdown)
python -m paperboy.digest.action_queue --dry-run # preview only
```

If `events.db` is empty/absent, it falls back to a bundled public fixture so it
always produces output.

- Module: [`paperboy/digest/action_queue.py`](paperboy/digest/action_queue.py)
- Demo output: [`examples/action-queue.demo.jsonl`](examples/action-queue.demo.jsonl) · [`examples/action-queue.demo.md`](examples/action-queue.demo.md)
- Dashboard: [`dashboard/action-queue.html`](dashboard/action-queue.html) (open directly in a browser)
- Walkthrough: [docs/action-queue.md](docs/action-queue.md)

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

## Relationship to open-brane

paperboy is a **consumer** of an event-log architecture defined by
[**cgallic/open-brane**](https://github.com/cgallic/open-brane) —
"an event-log brain for people who keep losing context." open-brane owns
the events.db schema, the canonical write path (`record_event.py`), an MCP
server, and adapters for gdrive / Claude sessions / git history. It also
ships `embed_events.py` + `semantic_search.py` for vector queries.

paperboy adds the **news + research-paper domain** on top: RSS scanners,
arXiv + HF + Semantic Scholar ingest, local-LLM scoring against your
stack, and the morning Discord digest.

paperboy can run standalone — it ships a compatible schema in its own
`db.py` so you don't *need* open-brane to get the digest working. But if
you install open-brane alongside (or first), every other ingester
populates the same store and paperboy's digest gets richer for free.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). The full planned stack:

1. [**open-brane**](https://github.com/cgallic/open-brane) — events.db
   foundation + MCP + canonical adapters (already shipped)
2. **paperboy** (this repo) — news + papers + Discord digest
3. **More open-brane adapters** — gmail, chatgpt, audible, linkedin, etc.
   (PRs to open-brane or sibling repos)
4. **Markdown KG / wiki compiler** — typed wiki pages + NL query CLI
   (planned, name TBD)
5. **cgallic/pendant-android** + **cgallic/pendant-pipeline** — custom
   Omi-pendant app + agent-side audio pipeline (planned)
6. **cgallic/casa-a2a** — JSON-RPC 2.0 broker + skill-sidecar pattern for
   cross-host agent coordination (planned)

## License

MIT. See [LICENSE](LICENSE).
