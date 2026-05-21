# Personalizing paperboy

The code does the same thing for everyone. The signal-to-noise ratio comes
from your configs. Spend an hour here and the morning digest stops being
"interesting" and starts being "actionable."

## The four files that matter

| File | What it does | How much to invest |
|---|---|---|
| `research-interests.md` | Grounds the paper scorer in YOUR stack | **HIGH** — this is the most important one |
| `news_sources.yaml` | RSS feeds, grouped by vertical | MEDIUM — picks signal sources |
| `topical-map.md` | Your "questions I want to answer publicly" | LOW (optional) — only matters if you publish |
| `daily-brief.md` | Daily carry-overs and "dead repo" callouts | LOW (optional) — most users skip |

## Writing a good `research-interests.md`

The scorer's whole job is to ask: "could this technique be borrowed by one
of this person's existing systems?" — and that question only makes sense if
you've told it what your systems are.

### Bad

```markdown
- **`my-stuff`** — I do AI things.
```

This produces verdicts like `{"applies_to": [], "relevance": 4}` on
basically every paper. The model has nothing to anchor on.

### Good

```markdown
- **`my-rag`** — Semantic search over my Obsidian vault (~50k notes).
  Uses nomic-embed-text + Qdrant + a hybrid sparse-dense retriever.
  Currently struggles with: query rewriting for multi-hop questions,
  embedding drift on technical jargon, and dedup of near-identical chunks.
```

This produces verdicts like `{"applies_to": ["my-rag"], "relevance": 8,
"improvement_idea": "Paper proposes hybrid sparse-dense with learned-sparse
component — would replace BM25 in your existing pipeline."}`. The model has
something to reason against.

### The four sections that count

1. **My systems** — list each system with a slug + 2-3 sentences. Mention
   what it does, the tech stack, and ONE current pain point. Pain points
   are gold — they let the scorer flag papers that address that exact pain.
2. **Active themes** — broad areas you care about. The scorer treats these
   as topic priors.
3. **Tech stack** — name the specific models/libraries you use. If a paper
   benchmarks against the model you actually run, that's a strong signal.
4. **What to score LOW** — explicit exclusions. Vision-only? Robotics?
   Hardware-specific? List them so the scorer stops surfacing them.

### Calibration

Run the ingest + score manually for a few days. If the morning digest is
boring, look at the `improvement_idea` field on a few 7+/10 papers — does it
sound like something you'd actually do? If not, edit `research-interests.md`
to be more specific about what you would do, and re-run with `--retry-scored`:

```bash
sudo systemctl start paperboy-research-score.service
# or, to re-score everything from scratch:
sudo -u paperboy /opt/paperboy/.venv/bin/python -m paperboy.score.research_papers --retry-scored
```

## Tuning `news_sources.yaml`

Three rules:

1. **Pick narrow verticals**, not broad ones. "ai-research" is bad; "llm-tooling"
   is better; "llm-tooling-and-ollama-ecosystem" is best.
2. **3-5 feeds per vertical.** More burns LLM tokens on noise. Fewer leaves
   you with thin coverage.
3. **Avoid generic firehoses.** Hacker News RSS, Google News, top-X newsletters
   — these flood the deduper with items that don't deserve a hot take.

Good feeds have signal density. If every post would plausibly trigger a take
from you, keep it. If 9/10 posts make you think "meh," cut it.

Test: edit the file, then run `paperboy-news` once manually and watch what
prompts come out:

```bash
sudo -u paperboy /opt/paperboy/.venv/bin/python -m paperboy.scanners.news_opinion --dry-run
```

## Tuning `topical-map.md` (optional)

Only matters if you publish content. The scanner reads `## Pillar — <name>`
headings and the bulleted questions under them, then picks 2/day rotating
across pillars.

Format strictly:

```markdown
## Pillar — Local LLMs
- How do you choose between Q3_K_M and Q4_K_M quantization for a 24GB GPU?
- When does a 7B local model beat a frontier API for your use case?

## Pillar — Personal AI infrastructure
- How do you ingest 10 years of personal email into a queryable index?
```

Questions you've recently been surfaced won't re-appear within 21 days
(`TOPICAL_RECENT_DAYS`). To force a re-emit, edit the question text — that
changes its dedup slug.

### What makes a good topical-map question

- **Concrete, not abstract.** "How do I build a RAG?" is too broad.
  "What's the smallest chunk size that still gives good answers for code
  documentation?" is answerable.
- **Has a question mark.** The scanner parses these as "answer-shape" prompts.
- **Has a clear audience.** Knowing who you're writing for sharpens the
  question.

## Daily briefs (optional)

Most users skip this. If you do want it:

Write a markdown file at `~/.paperboy/daily-briefs/<YYYY-MM-DD>.md` each
morning. Two sections matter (see `config/daily-brief.md.example`):

- `## Today's corpse` — one repo/project that's gone stale
- `## Yesterday you said out loud` — bulleted carry-over commitments

You can write this manually each morning, or wire up your own script that
generates it from git activity, calendar events, or voice memos. The scanner
doesn't care where the file comes from.

## Optional: enabling LLM reframing

The morning digest can optionally rewrite news/papers prompts into shorter,
more specific content hooks via your local LLM. Off by default. Enable with:

```
PROMPT_DIGEST_REFRAME=1
PROMPT_DIGEST_MODEL=llama3.2:3b
```

in `/etc/paperboy/paperboy.env`. Adds ~5 seconds to the digest run per news
item. Quality varies by model — qwen2.5:7b gives better hooks than 3B models,
at the cost of more time.

## Tuning the weights

The digest assigns each prompt a `stream_weight × freshness` score. Defaults
favor `today` and `papers`. If you want to change that, edit
`paperboy/digest/prompt_digest.py:WEIGHTS` directly — there's no env var for
this because re-weighting is the kind of change you do once and forget.

| Default | Stream | Effect of lowering |
|---|---|---|
| 1.5× | `today` | De-emphasizes daily carry-overs |
| 1.3× | `papers` | Less paper-heavy digest |
| 1.2× | `news` | Less news-heavy digest |
| 1.1× | `answer` | Fewer content-pillar questions |
| 0.4× | `pendant` | Already de-emphasized |

## Tuning the timing

All timers are UTC. To shift them to your timezone, edit the `.timer` files
in `/etc/systemd/system/`:

```ini
[Timer]
OnCalendar=*-*-* 11:15:00 UTC    # ← change this
```

Then `sudo systemctl daemon-reload && sudo systemctl restart
paperboy-*.timer`.

Keep the staggering — each scanner needs the previous one to have finished
before it runs.
