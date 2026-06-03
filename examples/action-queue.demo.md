# Agent Action Queue — 2026-06-03

_7 item(s) · 7 pending · source: **fixture-fallback**_

> Read-only review surface. Flip `status` to `approved`/`dismissed` in
> the JSONL before any agent acts. Nothing here is sent anywhere.

## ⏳ Speculative Retrieval: Cutting RAG Latency with Draft-then-Verify Lookups

- **id:** `act_demo0001paper01`
- **source:** `research-paper`
- **score:** `9`
- **status:** `pending`
- **why:** Sample/demo data. Two-stage retrieval cuts tail latency without hurting recall — directly applicable to any RAG layer that's latency-bound.
- **suggested action:** Open a prototype spike against the RAG layer: scope a 1-day experiment to test the paper's core idea, then report keep/kill.
- **evidence:** https://example.com/papers/speculative-retrieval, paper-score event:1001

## ⏳ Rubric-Grounded Self-Critique Beats Constitutional Prompts on Small Models

- **id:** `act_demo0002paper02`
- **source:** `research-paper`
- **score:** `8`
- **status:** `pending`
- **why:** Sample/demo data. A fixed scoring rubric in the critique step outperforms freeform self-critique for 3B-7B models — cheap quality win for a local scorer.
- **suggested action:** Evaluate for the scoring pipeline: swap freeform critique for a fixed rubric and A/B the score agreement on a held-out set.
- **evidence:** https://example.com/papers/rubric-self-critique, paper-score event:1002

## ⏳ Event-Log Memory: Append-Only Stores Outperform Vector DBs for Agent Recall

- **id:** `act_demo0003paper03`
- **source:** `research-paper`
- **score:** `7`
- **status:** `pending`
- **why:** Sample/demo data. Append-only event logs with cheap tags beat embedding stores on precision for time-anchored agent recall — validates the events.db approach.
- **suggested action:** Read in full and assess fit for the event-log brain; draft a one-paragraph take.
- **evidence:** https://example.com/papers/event-log-memory, paper-score event:1003

## ⏳ A hypothetical small-business SaaS, PingDesk, shipped real-time call summaries. What changes for tools that lag on transcripts?

- **id:** `act_demo0004news01`
- **source:** `digest-prompt:news`
- **score:** `8.0`
- **status:** `pending`
- **why:** Sample/demo data. Competitor moved transcript turnaround from minutes to seconds; reframes the speed bar for the whole category.
- **suggested action:** Draft a short take responding to: A hypothetical small-business SaaS, PingDesk, shipped real-time call summaries.
- **evidence:** https://example.com/news/pingdesk-realtime-summaries

## ⏳ Open-source local STT model hit parity with paid APIs on noisy phone audio — does the build-vs-buy math flip?

- **id:** `act_demo0005news02`
- **source:** `digest-prompt:news`
- **score:** `7.2`
- **status:** `pending`
- **why:** Sample/demo data. Quality gap that justified paid transcription APIs just narrowed; worth a reassessment post.
- **suggested action:** Draft a short take responding to: Open-source local STT model hit parity with paid APIs on noisy phone audio.
- **evidence:** https://example.com/news/local-stt-parity

## ⏳ Speculative Retrieval — applies to the RAG layer. Take?

- **id:** `act_demo0006papers01`
- **source:** `digest-prompt:papers`
- **score:** `8.7`
- **status:** `pending`
- **why:** Sample/demo data. Promoted from the top-scored paper; content-ideation stimulus.
- **suggested action:** Skim the paper and note one applicable idea: Speculative Retrieval — applies to the RAG layer. Take?
- **evidence:** https://example.com/papers/speculative-retrieval, paper-score event:1001

## ⏳ How do you decide between an append-only event log and a vector store for agent memory?

- **id:** `act_demo0007answer01`
- **source:** `digest-prompt:answer`
- **score:** `6.5`
- **status:** `pending`
- **why:** Sample/demo data. From the topical map — a question the audience keeps asking.
- **suggested action:** Write a crisp answer for the topical map: How do you decide between an append-only event log and a vector store for agent memory?
- **evidence:** topical-map:agent-memory
