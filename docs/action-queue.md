# News → Agent Action Queue

paperboy reads ten thousand things and scores the twelve that matter. The
**action queue** takes the next step: it turns the highest-signal of those
twelve into a reviewable list of *agent tasks* — without firing any of them.

It is the bridge between "here's what's worth knowing" (the morning digest)
and "here's what an agent should do about it" (a task queue) — with a human
review gate in between.

> **File-first, read-only.** This module writes two files to disk and sends
> nothing — no Discord, no webhook, no email, no HTTP. The queue is a review
> surface. An agent acts only after a human flips an item to `approved`.

## How a daily digest item becomes an agent task

```
research-score / pattern-scan  ──►  action_queue.py  ──►  action-queue.demo.jsonl   (append-only)
        (events.db)                  (promote + shape)     action-queue.demo.md      (rendered view)
                                                           dashboard/action-queue.html (cards)
```

1. **Score** (existing paperboy step). The local LLM rates each paper 0-10 and
   the scanners emit weighted `pattern-scan/question` prompts. Both land in
   `events.db` exactly as the digests consume them.
2. **Promote.** `action_queue.py` selects the strongest signals (see below)
   and shapes each into a structured action item with a concrete
   `suggested_action`.
3. **Persist.** Each new item is appended to a JSONL queue and the full queue
   is re-rendered to Markdown. Re-runs are idempotent (dedup by `id`).
4. **Review.** A human (or the `dashboard/action-queue.html` card view) reads
   the queue and approves or dismisses items.
5. **Act (downstream, out of scope here).** A separate agent polls the JSONL,
   picks up `approved` items, does the work under its own guardrails, and can
   write the result back as a new event.

## What gets promoted

The bar matches the digests so "highest-signal" means the same thing system-wide:

| Source | Promotion rule |
|---|---|
| `research-papers/paper-score` | `relevance >= ACTION_QUEUE_MIN_RELEVANCE` (default 7) **OR** `should_prototype = true` |
| `pattern-scan/question` | top `ACTION_QUEUE_MAX_PROMPTS` (default 8) by `stream_weight × freshness` |

Stream weights are the same as `prompt_digest.py` (`today` 1.5×, `papers` 1.3×,
`news` 1.2×, `answer` 1.1×, …). The prompt `score` shown in the queue is that
weighted value mapped onto a 0-10 scale for display.

If `events.db` is empty or absent, the module falls back to the bundled
fixture (`examples/action-queue.demo.jsonl`) so it **always** produces output —
useful for demos, CI, and the very first run.

## The schema

One JSON object per line in the JSONL queue:

```json
{
  "id": "act_<sha1[:16]>",
  "title": "Speculative Retrieval: Cutting RAG Latency...",
  "source": "research-paper",
  "score": 9,
  "why": "Two-stage retrieval cuts tail latency without hurting recall...",
  "suggested_action": "Open a prototype spike against the RAG layer: ...",
  "status": "pending",
  "created": "2026-06-02T10:00:00+00:00",
  "evidence": ["https://example.com/papers/...", "paper-score event:1001"]
}
```

| Field | Meaning |
|---|---|
| `id` | Stable sha1 of `source-kind + underlying event key`. The dedup key. |
| `title` | Short human-readable label (paper title or digest prompt). |
| `source` | `research-paper` or `digest-prompt:<stream>` (e.g. `digest-prompt:news`). |
| `score` | 0-10. Paper relevance, or the weighted prompt score on a 0-10 scale. |
| `why` | One line on why it crossed the bar (scorer's `why`/`improvement_idea`). |
| `suggested_action` | A concrete, reviewable next step. Deterministic — no LLM call. |
| `status` | `pending` → `approved` → `dismissed`. Starts `pending`. |
| `created` | ISO-8601 UTC of when the item was generated. |
| `evidence` | Source URL + originating event ids, for traceability. |

## How an agent would poll the queue

The queue is just a JSONL file, so polling is a five-line read:

```python
import json
from pathlib import Path

QUEUE = Path("examples/action-queue.demo.jsonl")

def pending_approved():
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "approved":
            yield item

for task in pending_approved():
    print(task["id"], "→", task["suggested_action"])
    # ... do the work under YOUR OWN guardrails, then record the outcome ...
```

A reviewer marks items by editing the `status` field in the JSONL (the
dashboard's Approve/Dismiss buttons are a no-op preview of that edit). Because
the file is append-only by `id`, a common pattern is a sibling
`action-queue.state.jsonl` that records `{id, status, decided_at}` overrides,
leaving the original promotion log untouched. The action queue itself never
mutates rows — same append-only discipline as the rest of paperboy's events.db.

## Running it

```bash
# Generate / refresh the queue (writes JSONL + Markdown; sends nothing)
python -m paperboy.digest.action_queue

# Preview without writing
python -m paperboy.digest.action_queue --dry-run

# Custom paths
python -m paperboy.digest.action_queue \
  --jsonl /path/to/queue.jsonl \
  --md /path/to/queue.md
```

Environment knobs: `ACTION_QUEUE_MIN_RELEVANCE` (7), `ACTION_QUEUE_LOOKBACK_HOURS`
(48), `ACTION_QUEUE_MAX_PROMPTS` (8), `ACTION_QUEUE_JSONL`, `ACTION_QUEUE_MD`.

## See also

- `dashboard/action-queue.html` — static card view of the demo JSONL.
- `examples/action-queue.demo.md` — rendered Markdown queue.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — the events.db model this reads from.
