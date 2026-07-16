# Paper Boy product strategy

**Decision date:** 2026-07-16
**Recommendation:** Test a hosted **Paperboy Daily Brief** for independent technical builders at **$12/month** while keeping the current self-hosted GitHub project free. The brief should rank and synthesize explicitly forwarded newsletters, public news/research/data, and selected GitHub repositories into one evidence-backed morning edition. Repo Radar is one section, not the whole product.

## Source-of-truth note

Current-product claims below are grounded in commit [`526ae15`](https://github.com/cgallic/paperboy/tree/526ae15ed76b501a53e3c0439b7215d234d8ec7c) of the exact public repo, `cgallic/paperboy`.

Live read-only checks were also run on 2026-07-16:

- **Brain host/source:** `agent:/home/connor/brain/events.db`. Relevant exact events include `1286611` (`claude-laptop/message`, the 10,000-to-12 positioning and open-brane relationship), `1187894` (`claude-laptop/message`, Paper Boy as a Discord daily digest and desired action-queue demo), and `1188408` (`claude-laptop/message`, the explicit file-first, no-external-send action-queue contract).
- **Gmail source:** live Gmail API via DWD for `connor@kaicalls.com` and `me@connorgallic.com`. Exact searches for `"Paper Boy"`, `paperboy`, `"cgallic/paperboy"`, `from:github paperboy`, and `subject:paperboy` found no current Paper Boy product thread. The three `paperboy` hits in `me@connorgallic.com` were unrelated 2018-2019 newsletter mentions (thread IDs `16aa268aed0e00e2`, `16a9701a0f54d7e0`, `1633b15f8a98ea8d`). No product requirement is inferred from those emails.

The 2026-07-16 operator direction is therefore treated as the forward product brief: **a hosted morning email combining explicitly forwarded email/newsletters, public news/research/data, and selected GitHub repositories.** These are proposed hosted inputs/delivery, not capabilities represented as already existing. “Forwarded email” means messages intentionally sent to a Paperboy address, not broad mailbox access.

## Correction guardrail

Discovery correctly identified Paperboy's existing core job as a daily news-and-research digest. The first product synthesis then overrode that evidence with a narrow paid-wedge heuristic and made Repo Impact the product. That was the wrong abstraction.

Future product decisions must state three things in order:

1. **Existing core job:** rank a large news/research firehose into a small daily digest.
2. **Requested expansion:** add explicitly forwarded newsletters, public data, selected GitHub sources/context, and hosted email delivery.
3. **Paid delta:** cross-source relevance ranking, synthesis, evidence, feedback learning, and quiet-day discipline.

Reject any wedge that changes the core job merely because one input or section appears easier to sell. **Repo Radar is a section of the Daily Brief, not Paperboy's product identity.**

## Current product truth

| Area | What exists now | Evidence |
|---|---|---|
| Product shape | A self-hosted daily Discord digest scored by a local LLM. The repo explicitly says “No cloud, no SaaS, no account.” | [`README.md:6-7`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/README.md#L6-L7) |
| Inputs | RSS/Atom news plus research papers from arXiv, Hugging Face Daily Papers, and Semantic Scholar. There is no selected-repository or Gmail ingest in the current package. | [`README.md:65-75`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/README.md#L65-L75), [`research_papers.py:1-5`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/ingest/research_papers.py#L1-L5), [`research_papers.py:364-382`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/ingest/research_papers.py#L364-L382) |
| Personalization | `research-interests.md` is injected into the local Ollama scoring prompt. A 7-8 means a clear technique could upgrade a named system; 9-10 means strong fit and likely high impact. | [`research_papers.py:7-8`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/score/research_papers.py#L7-L8), [`research_papers.py:78-86`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/score/research_papers.py#L78-L86), [`research_papers.py:205-225`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/score/research_papers.py#L205-L225) |
| State | One local SQLite event log, with `PAPERBOY_DB` override and `events` plus `event_tags` tables. | [`db.py:14-15`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/db.py#L14-L15), [`db.py:50-69`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/db.py#L50-L69) |
| Delivery | The morning queue selects up to 12 unanswered/unrated prompts and sends them by Discord bot or webhook. Email delivery does not exist. | [`prompt_digest.py:1-18`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/prompt_digest.py#L1-L18), [`prompt_digest.py:181-184`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/prompt_digest.py#L181-L184), [`discord_post.py:6-12`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/discord_post.py#L6-L12) |
| Action queue | A deterministic module promotes strong items into pending JSONL and Markdown records. It sends nothing; a human must change status before a separate downstream agent acts. | [`action_queue.py:13-25`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/action_queue.py#L13-L25), [`action_queue.py:301-312`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/action_queue.py#L301-L312), [`action_queue.py:320-349`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/action_queue.py#L320-L349) |
| Operations | The supported install requires root, Linux/systemd, Python 3.10+, Ollama, and Discord. The architecture explicitly has no auth and no tests. | [`README.md:83-89`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/README.md#L83-L89), [`bootstrap.sh:20-37`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/scripts/bootstrap.sh#L20-L37), [`ARCHITECTURE.md:152-159`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/docs/ARCHITECTURE.md#L152-L159) |

“Reads 10,000 things and delivers 12” is strong positioning, not proven throughput telemetry. The repo tagline and Brain event `1286611` establish the intended promise; neither establishes a measured daily source count.

## Recommended wedge

### Paperboy Daily Brief for technical builders

**Promise:** Forward the newsletters you trust, choose the public sources and GitHub repositories you care about, and receive one ranked morning edition showing what changed, what connects across sources, why it matters, and what deserves action.

The edition is a brief, not a dump. It should take less than five minutes to scan and use stable sections:

1. **The three that matter** — the highest-ranked items across every source.
2. **Newsletter signals** — only novel claims from explicitly forwarded messages.
3. **News + data moves** — public developments or material metric changes.
4. **Research** — papers that clear the user's relevance threshold.
5. **Repo Radar** — external changes or watched-repo activity tied to a selected repo.
6. **One next move** — one recommended action, or an explicit “watch; do nothing.”

On a quiet day, Paperboy sends a one-line “nothing material changed” edition instead of padding the brief. Users may later opt to skip empty editions, but the beta should preserve the morning ritual while proving that the ranking bar is real.

This wedge preserves Paperboy's original news-and-research identity and uses selected repositories as one personalization signal. Its differentiation is not generic summarization. It is **cross-source relevance ranking, synthesis of corroborating or conflicting signals, evidence links, and quiet-day discipline**.

## ICP and job to be done

### Primary ICP

Independent technical founders, developers, researchers, and product operators who:

- already receive multiple high-signal newsletters and follow public feeds, papers, datasets, or repositories;
- maintain or depend on at least one public GitHub repository, without requiring repo ownership to define their whole information need;
- repeatedly discover important connections late or spend too much time reconciling overlapping sources;
- can make an implementation decision without team procurement; and
- already pay for at least one developer productivity subscription.

The first cohort should still skew toward AI and developer-tool builders because the current research scorer and source set are strongest there. Start with public repositories. Private-repository access introduces a trust and security sale that a $12 beta does not need.

### Excluded from the first wedge

- General-news consumers seeking a broad newspaper replacement.
- Users who want a read-later archive rather than a ranked morning decision surface.
- Engineering managers seeking standup replacement or velocity analytics.
- Enterprise competitive-intelligence teams.
- Teams that require private-code indexing, SSO, audit logs, or procurement.

### JTBD

> When trusted newsletters, public news, research, data, and repository changes pile up in separate places, give me one ranked morning view of what is materially new, how the signals connect, and what deserves my attention or action.

### Sharp pain

The pain is not merely “too much content.” Cheap readers already summarize feeds and newsletters. The sharper pain is that the same underlying change arrives fragmented across an email, a public article, a paper, a dataset, and a repository release. The user must deduplicate it, judge source quality, resolve disagreement, and decide whether it matters. Paperboy must answer **what is materially new, what the sources collectively imply, and what deserves action**. Repo Radar supplies extra context when code is affected; it is not required for every useful item.

## Recurring value loop

```text
forward chosen newsletters + select feeds/data/repos
        ↓
build an explicit interest, source, and repo-context profile
        ↓
ingest new items with source identity and evidence
        ↓
deduplicate, rank relevance, and synthesize cross-source claims
        ↓
assemble the ranked morning edition + one next move
        ↓
useful / not useful / already knew / acted / wrong-context feedback
        ↓
tune sources, interests, ranking, sections, and thresholds
```

The existing `research-interests.md` contract is the seed for this loop, but user feedback is not yet implemented. Current digest code only excludes items after separate feedback/answer events exist; it does not provide the hosted feedback capture needed here ([`prompt_digest.py:55-86`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/prompt_digest.py#L55-L86)).

## Activation moment

Activation is not “forwarded an email,” “selected a repo,” or “opened the first brief.” It is:

> Within 48 hours of adding at least three sources, the user marks one cross-source insight useful or acts on one item they would otherwise have missed.

The onboarding preview should produce one sample edition before payment. A credible activation can be a newsletter claim corroborated by public data, a research result connected to a watched tool, or a Repo Radar item. If the preview merely restates individual summaries without ranking or synthesis, Paperboy has not activated the user.

## Hosted MVP

### In scope

- Email address and a unique forwarding address for newsletters the user explicitly chooses.
- A small allowlist of user-selected public RSS/Atom feeds, research sources, public data endpoints, and 1-5 public GitHub repositories.
- A generated interest/context profile from onboarding answers, forwarded-source choices, and bounded public repo material such as README, dependency manifests, languages, releases, and topics.
- The existing research/news/paper intake where it is reliable, with source-level provenance preserved.
- One scheduled morning email surface with stable sections, evidence links, source attribution, and a hard item cap.
- Claim-level deduplication and lightweight cross-source synthesis that distinguishes corroboration, disagreement, and a single-source claim.
- Five feedback actions: useful, not useful, already knew, acted, wrong context.
- Per-user source, repo, threshold, delivery-time, and feedback configuration.
- Basic run, delivery, click, feedback, and cost telemetry.
- A clear deletion path for account/config data.

### Architecture boundary

Keep the current SQLite/systemd project self-hosted and single-user. Do not expose its database or mutate it into the hosted multi-tenant service. The hosted product should reuse scoring contracts and content shapes behind a separate scheduled service and tenant configuration layer. This preserves the free project and avoids turning a local, unauthenticated event log into a public SaaS backend.

### Source boundaries

- **Forwarded email:** accept only messages intentionally forwarded or subscribed to a per-user Paperboy address. Do not request Gmail OAuth, read an inbox, follow reply chains, or ingest attachments in MVP.
- **Public news/research/data:** use declared RSS/Atom feeds and documented public APIs/endpoints. Keep the source URL, publication time, retrieval time, and claim evidence. Do not add broad web crawling or paywall bypass.
- **GitHub:** accept selected public repository URLs and documented public metadata/content. Use repositories as both watched sources and relevance context. Do not request private-code scopes.
- **User control:** every source must be visible, removable, and attributable in the edition. Deleting a source stops future ingest; deleting the account removes tenant configuration and retained forwarded content.

### Explicit non-goals

- Private repository access or broad GitHub OAuth scopes.
- Gmail/Outlook mailbox access, broad inbox search, reply drafting, or sending as the user. Explicit forwarding is the only email intake.
- Discord, Slack, mobile app, or dashboard delivery for hosted v1.
- Autonomous PR creation, code changes, purchases, or external actions.
- Team accounts, shared feeds, standup reports, analytics, SSO, or RBAC.
- A read-later archive, full-text personal search engine, vector database, general personal memory product, or open-brane hosting.
- Affiliate-ranked recommendations.
- A marketplace or “agent factory.”

## Pricing hypothesis

### Offer

- **Self-hosted:** free, MIT GitHub project; users bring Linux, Ollama, Discord, and their own operation.
- **Hosted Personal beta:** **$12/month**, monthly cancellation, explicit newsletter forwarding, bounded public feeds/research/data, 1-5 public repos, one scheduled morning edition, feedback learning, and no infrastructure setup.
- **Annual plan:** do not introduce until monthly willingness-to-pay and 30-day retention clear the thresholds below. Then test $99/year against $12 monthly.

Do not launch a permanently free hosted tier during PMF testing. The free self-hosted project is already the open-source acquisition path. Offer a no-card sample brief or short trial instead.

### $12 pressure test

As of 2026-07-16, current primary pricing pages show:

| Alternative | Current offer and price | What it proves | Paper Boy gap/opportunity |
|---|---|---|---|
| GitHub notifications | GitHub natively sends activity for watched repos to its inbox, mobile, or email; users can filter issue, PR, release, security, and discussion activity. [Official docs](https://docs.github.com/en/subscriptions-and-notifications/concepts/about-notifications), [subscription controls](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-subscriptions-for-activity-on-github/managing-your-subscriptions) | Repo email is already native and carries no separate product purchase. | Repo Radar must synthesize repo activity with outside news/research rather than forward notifications. |
| Digest | Starter is **$6/month** and includes AI newsletter summaries, RSS, news sources, and GitHub Trending sources. [Official pricing](https://usedigest.com/pricing/) | Multi-source daily email aggregation is inexpensive. | A $12 edition must rank across source types, merge duplicate claims, and explain evidence—not just collect widgets. |
| Inoreader | Pro is **$7.50/month billed annually or $9.99 monthly**, with monitoring feeds, filters/rules, AI summaries, and scheduled email digests. [Official pricing](https://www.inoreader.com/pricing/feature/subscriptions) | Power users can build sophisticated filters below $12. | Paperboy must remove rule-building work and supply cross-source judgment plus a strict relevance bar. |
| Digest AI | Pro is **$15/month** for unlimited newsletter sources, advanced summaries, categories, and custom delivery time. [Official pricing](https://www.newsletterdigest.tech/pricing) | Inbox-summary buyers already see a $15 reference price. | Paperboy at $12 is plausible if it joins forwarded claims to public evidence and other source classes. |
| Git Digest | **$25/month billed annually** for unlimited teammates/repos, code-change summaries, and daily/weekly email or Slack. [Official product and pricing](https://gitdigest.ai/) | Customers pay for selected-repo summaries that replace coordination work. | Paper Boy should not compete on standups; it should cover external change → internal impact. |
| AlphaSignal | Free covers top AI stories/models/repos; Pro is **$350/year ($29.17/month)** for a work-personalized, ad-free newsletter covering models, repos, and papers. [Official pricing](https://alphasignal.ai/pricing) | The closest public-news/research promise already exists and charges above $12. | Paperboy differentiates through user-chosen forwarded sources, visible evidence, cross-source synthesis, and quiet-day restraint. |
| Feedly Market Intelligence | Standard is **$1,600/month billed annually**, including 100 AI feeds, newsletter templates, collaboration, and up to 10 seats. [Official pricing](https://feedly.com/market-intelligence/pricing) | Enterprise intelligence is a different budget and buyer. | Avoid enterprise features; win on individual setup speed and specificity. |

**Conclusion:** Keep **$12/month** as the beta hypothesis. The broader Daily Brief supports the price better than the repo-only concept because it can replace several scanning rituals without moving into enterprise territory. It remains unvalidated. If the product only stacks source-by-source summaries, a $6-$10 reader wins. The paid delta is trusted ranking across source types, synthesis of repeated or conflicting claims, evidence, one useful next move, and the discipline not to manufacture news on quiet days.

### Affiliate revenue

Subscription should be the PMF test. Affiliate monetization before trust is dangerous because it makes rankings suspect. Keep affiliate links out of the beta. After paid retention is proven, test clearly disclosed referral links only on items that already cleared the relevance score; referral availability must never affect ranking. Continue only if affiliate items have no worse usefulness/dismissal rate than non-affiliate items.

## PMF risks

1. **Commodity risk:** summarization and email delivery are already cheap or free; Paperboy must prove better decisions, not prettier summaries.
2. **Precision risk:** one irrelevant daily email can train the user to ignore all later emails.
3. **Source-quality risk:** forwarded newsletters and public sources can repeat the same unsupported claim, creating false confidence unless provenance and corroboration remain visible.
4. **Actionability risk:** the current deterministic action queue can produce plausible but generic tasks; “one action” may not be worth doing.
5. **Trust risk:** forwarded email retention and repository access create security questions. Broad mailbox or private-repo scope would amplify them.
6. **Cadence risk:** a required daily edition may tempt the system to pad quiet days instead of reporting that nothing material changed.
7. **Cost risk:** hosted inference, fetch, and email costs could make a $12 plan unattractive if scoring is not aggressively bounded.
8. **OSS cannibalization risk:** capable users may self-host, leaving the hosted product with higher-support customers.
9. **Cold-start risk:** a user's chosen newsletters and feeds may have little overlap, leaving no convincing cross-source synthesis in the first edition.
10. **Affiliate conflict risk:** monetized recommendations can destroy the trust the subscription depends on.

## Falsifiable PMF tests

Run these in order. Do not use broad sign-up counts as PMF evidence.

| Test | Method | Continue | Iterate | Kill or change wedge |
|---|---|---|---|---|
| Problem pull | Recruit 20 qualified technical builders. Ask each to forward two newsletters and choose at least one public feed/research/data source and one repo before showing a result. | At least 10 complete source setup; at least 6 ask to keep receiving the edition. | 6-9 complete setup. | Fewer than 6 complete setup. |
| Concierge activation | Manually configure the first 10 users and deliver a sample within 48 hours. | At least 7/10 mark one ranked or synthesized insight useful; at least 5/10 identify something they would otherwise have missed. | 5-6 useful. | Fewer than 5 useful. |
| Signal precision | Capture item-level useful/not-useful/already-knew/wrong-context feedback. | At least 70% useful across the first 100 rated items; fewer than 20% already-knew plus wrong-context. | 50-69% useful. | Below 50% useful after one tuning cycle. |
| Synthesis delta | Blind-test the Paperboy edition against source-by-source AI summaries for the same material. | At least 60% of users prefer Paperboy and can name a useful connection/evidence advantage. | 40-59% prefer it. | Below 40%; synthesis is not adding value. |
| Quiet-day trust | Seed days with no threshold-clearing material and days with only weak material. | At least 80% of weak items are excluded; quiet-day editions are not rated less trustworthy than normal editions. | 60-79% excluded. | Below 60%; ranking is manufacturing news. |
| Willingness to pay | After two useful weeks, require $12 to continue. | At least 8 of 20 qualified activated users pay. | 4-7 pay; test promise/onboarding once. | Fewer than 4 pay. |
| Retention | Follow the first paid cohort for two billing cycles. | At least 70% retain into month two and at least 50% take a useful/acted action in 3 of 4 weeks. | 50-69% retain. | Below 50% month-two retention. |
| Unit economics | Measure actual fetch, inference, email, and support burden. | Variable cost at or below $2/user/month and median support below 10 minutes/user/month. | Cost $2-$4. | Above $4 after bounded-model optimization. |
| Affiliate trust, later only | After paid retention, show disclosed affiliate-eligible items to a small randomized cohort without changing rank. | Usefulness and dismissal remain within 5 percentage points of control. | 6-10 point degradation. | More than 10 point degradation; remove affiliate layer. |

## Product decisions

1. **Wedge:** Paperboy Daily Brief for independent technical builders.
2. **Delivery:** one hosted morning email; explicit forwarding is also a bounded input.
3. **Sources:** forwarded newsletters, allowlisted public news/research/data, and 1-5 selected public GitHub repositories; no mailbox or private-repo access.
4. **Value unit:** a ranked, evidence-backed cross-source insight or decision—not a stack of summaries. Repo Radar is one section.
5. **Price:** test $12/month; keep it labeled as a hypothesis until paid retention.
6. **Open-source boundary:** preserve the current self-hosted SQLite/systemd/Discord project; do not expose or multi-tenant it.
7. **Safety:** recommendations only. No autonomous code or external action.
8. **Monetization:** subscription first; no affiliate links during PMF beta.
9. **Build order:** concierge edition across all source classes → bounded forwarding intake and source registry → ranking/dedup/synthesis → edition renderer → scheduled email + feedback → billing. Do not build team/dashboard/private-repo features before activation, synthesis-delta, and payment thresholds clear.

## One-sentence positioning

**Paperboy turns the newsletters, news, research, data, and repositories you trust into one ranked morning edition—showing what is new, what connects, the evidence behind it, and what deserves your next move.**
