# MARKETING.md — Product Marketing Bible

> Created from the Paperboy repository and live validation page on 2026-07-16. This is a pre-PMF messaging hypothesis until real traffic and buyer interviews produce evidence.

## Product

- **Name:** Paperboy
- **One-liner:** Paperboy turns a user-built firehose of public feeds into a short, source-linked brief ranked around what matters to them.
- **Category:** Personal relevance filter
- **URL:** https://paperboy.kaibuilds.com/

## ICP (Ideal Customer Profile)

### Primary ICP

- **Title/Role:** Technical founder or hands-on product/engineering operator
- **Company size:** 1–20 people
- **Industry:** AI, developer tools, and technical SaaS
- **Budget authority:** Usually direct for a $49/month tool; hypothesis, not buyer-validated
- **Trigger event:** Missing an API, pricing, dependency, or market change that affects active work
- **Current solution:** Newsletters, RSS, GitHub notifications, bookmarks, and manual LLM summaries
- **Pain severity:** Unknown; validate with free-sample requests and interviews

### Secondary ICP

- **Title/Role:** Product or engineering lead in a small technical team
- **Company size:** 5–50 people
- **Industry:** Software and AI
- **Budget authority:** May need manager approval
- **Trigger event:** Too many sources and no consistent morning review
- **Current solution:** Slack channels, email folders, GitHub notifications, and ad hoc summaries
- **Pain severity:** Unknown

### Anti-ICP

- General-news readers who do not need source-specific relevance
- Enterprise teams requiring private-repository access, SSO, procurement, or compliance review
- Buyers requiring private sources, enterprise controls, or team administration

## Personas

### Persona 1: Signal-Drowned Builder — based on Competent Cog

- **Who they are:** A capable technical founder who still reads and reconciles the important sources personally.
- **Core frustration:** The useful update is buried inside the feeds, news, research, and notifications they still scan themselves.
- **Language they use:** Hypothesis: “I missed that change,” “I already have too many feeds,” and “just tell me what matters.”
- **Objections:** Another summary email; can build this with rules and an LLM; does not want inbox or code access.
- **Decision trigger:** An automatic preview from their actual public feeds proves the filter can remove a real scanning task.
- **Channels they trust:** Technical newsletters, GitHub, founder communities, and peer recommendations.

### Persona 2: Change-Anxious Lead — based on Obsolescence Anxious

- **Who they are:** A technical lead who needs to track fast-moving model, API, and tooling changes without spending the day online.
- **Core frustration:** They cannot tell which releases deserve action and which are noise.
- **Language they use:** Hypothesis: “What changed?” “Does this affect us?” and “Do we need to do anything?”
- **Objections:** Relevance will be weak; citations may be missing; the brief may become unread email.
- **Decision trigger:** The sample correctly connects one change to a repo, dependency, or active decision.
- **Channels they trust:** GitHub releases, research papers, technical communities, and vendor documentation.

### User Segments

- **Launch subscriber:** Chooses presets or supplies public RSS/Atom feed URLs, a relevance focus, and an optional ignore list, then activates the daily edition.
- **Future paid buyer:** Keeps reading enough daily editions to justify the planned $49/month founding price.

## Value Prop

- **Core transformation:** From scanning a self-built information firehose to reading only the few items connected to current work.
- **Key actions:** Choose or paste public feeds; describe current interests; name what to ignore; activate the daily brief; inspect source-linked matches; self-manage or unsubscribe.
- **Activation moment:** The automatic first edition contains at least one relevant item and the private management screen confirms daily delivery is active.
- **Aha moment:** The reader opens an original source or changes a concrete next step because of the brief.

## Business Model

- **Monetization:** Free automatic daily delivery during launch; paid conversion is the next validation step
- **Pricing:** Planned founding price of $49/month; not yet collected
- **Stage:** Pre-PMF validation; automatic setup, persistence, scheduled delivery, and self-service unsubscribe are live, while billing is not

## Current Marketing

- **Channels active:** KaiBuilds landing page and GitHub
- **Email platform:** Paperboy's scheduled delivery worker through the configured server mail transport
- **Ad platforms:** None launched
- **Social:** Unknown
- **Content:** Open-source GitHub repository

## Brand Voice

- **Tone:** Editorial, technical, specific, and skeptical of hype
- **Banned patterns:** Internal strategy jargon, “operator” language, abstract intelligence claims, invented proof, and fake urgency
- **Examples:** “Build your firehose. Read only what matters.” “Every signal earns its place.”

## Competitive Landscape

- **Top alternatives:** RSS readers; read-it-later queues; email rules plus an LLM; manual daily scanning
- **Our differentiation:** The user chooses the firehose and explicitly defines relevance and noise. Paperboy ranks, deduplicates, and explains the short list instead of presenting another chronological inbox.

## Key Metrics

- **Traffic:** Only deployment and QA traffic so far
- **Conversion rate:** Unknown; existing lead is a classified test
- **Email list size:** Zero verified prospects
- **MRR/ARR:** $0 verified
