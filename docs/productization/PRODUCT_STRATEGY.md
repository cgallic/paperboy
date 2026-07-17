# Paper Boy product strategy

**Decision date:** 2026-07-16
**Recommendation:** Sell a hosted **Paperboy Daily Intelligence Brief** to revenue-bearing technical founders and operators at a primary price of **$49/month** while keeping the current self-hosted GitHub project free as distribution and proof. The brief should rank and synthesize explicitly forwarded newsletters, public news/research/data, and selected GitHub repositories into one evidence-backed morning edition. Repo Radar is one section, not the whole product.

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

Commercially, preserving the core job does not mean preserving the OSS audience, easiest beta, or lowest price. Optimize for the product that can create durable revenue: choose an ICP with an expensive information problem, charge against the value of better decisions, and keep delivery costs bounded. Reject both failure modes—turning Paperboy into a narrow repo utility and pricing a decision-intelligence product like a commodity reader.

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

### Paperboy Daily Intelligence Brief for technical founders and operators

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

Revenue-bearing technical founders and hands-on product/engineering operators who:

- run an AI, SaaS, developer-tool, technical agency, or data product where a missed model, API, competitor, research, or repository change can waste days or change a revenue decision;
- already receive multiple high-signal newsletters and follow public feeds, papers, datasets, or repositories;
- maintain or depend on at least one public GitHub repository, without requiring repo ownership to define their whole information need;
- personally reconcile overlapping sources and can act on the morning brief;
- can purchase a sub-$100 monthly tool without procurement; and
- already pay for developer productivity, research, or market-intelligence subscriptions.

The first cohort should skew toward AI and developer-tool founders because the current research scorer and source set are strongest there and external change velocity is high. The commercial qualification is not job title alone: the buyer should be able to name a recent missed signal that cost at least several hours, delayed a product decision, or created avoidable spend. Start with public repositories. Private-repository access introduces a trust and security sale that the first small-software version does not need.

### Excluded from the first wedge

- General-news consumers seeking a broad newspaper replacement.
- Hobbyists whose information problem is interesting but not economically costly.
- Users who want a read-later archive rather than a ranked morning decision surface.
- Researchers or employees who need reimbursement/procurement for a $49 tool.
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
- A bounded allowlist of user-selected public RSS/Atom feeds, research sources, public data endpoints, and up to 10 public GitHub repositories.
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
- Team accounts in the initial Operator build, plus standup reports, analytics dashboards, SSO, or RBAC. The later Small Team offer is shared delivery/feedback only.
- A read-later archive, full-text personal search engine, vector database, general personal memory product, or open-brane hosting.
- Affiliate-ranked recommendations.
- A marketplace or “agent factory.”

## Pricing hypothesis

### Offer

- **Self-hosted:** free, MIT GitHub project; users bring Linux, Ollama, Discord, and their own operation.
- **Operator — primary offer:** **$49/month** for one recipient, explicit newsletter forwarding, up to 30 declared public/news/research/data sources, up to 10 public repos, one scheduled Daily Intelligence Brief, evidence, feedback learning, and no infrastructure setup.
- **Annual:** test **$490/year** only after month-two retention clears the threshold below. Do not use an annual discount to hide weak monthly retention.
- **Concierge setup — optional during validation:** **$199 one time** for source mapping, initial ranking calibration, and a live first-edition review. Keep the subscription usable without this service and remove the manual dependency as onboarding improves.
- **Small Team — later expansion:** **$149/month** for up to five recipients sharing one source set and edition. Add only after Operator retention; keep it to shared delivery and feedback, not SSO, dashboards, permissions, or enterprise procurement.

Do not launch a permanently free hosted tier during PMF testing. The free self-hosted project is already the open-source acquisition path. Offer a no-card sample brief or short trial instead.

### $49 pressure test

As of 2026-07-16, current primary pricing pages show:

| Alternative | Current offer and price | What it proves | Paper Boy gap/opportunity |
|---|---|---|---|
| GitHub notifications | GitHub natively sends activity for watched repos to its inbox, mobile, or email; users can filter issue, PR, release, security, and discussion activity. [Official docs](https://docs.github.com/en/subscriptions-and-notifications/concepts/about-notifications), [subscription controls](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-subscriptions-for-activity-on-github/managing-your-subscriptions) | Repo email is already native and carries no separate product purchase. | Repo Radar must synthesize repo activity with outside news/research rather than forward notifications. |
| Digest | Starter is **$6/month** and includes AI newsletter summaries, RSS, news sources, and GitHub Trending sources. [Official pricing](https://usedigest.com/pricing/) | Multi-source daily email aggregation is inexpensive. | A $49 edition must demonstrably improve decisions through ranking, claim synthesis, and evidence—not just collect widgets. |
| Inoreader | Pro is **$7.50/month billed annually or $9.99 monthly**, with monitoring feeds, filters/rules, AI summaries, and scheduled email digests. [Official pricing](https://www.inoreader.com/pricing/feature/subscriptions) | Power users can build sophisticated filters far below $49. | Paperboy must remove rule-building work and supply cross-source judgment plus a strict relevance bar for a buyer with an expensive miss problem. |
| Digest AI | Pro is **$15/month** for unlimited newsletter sources, advanced summaries, categories, and custom delivery time. [Official pricing](https://www.newsletterdigest.tech/pricing) | Inbox-summary buyers already see a $15 reference price. | Paperboy earns a premium only when it joins forwarded claims to public evidence and makes the result decision-ready. |
| Git Digest | **$25/month billed annually** for unlimited teammates/repos, code-change summaries, and daily/weekly email or Slack. [Official product and pricing](https://gitdigest.ai/) | Customers pay for selected-repo summaries that replace coordination work. | Paper Boy should not compete on standups; it should cover external change → internal impact. |
| AlphaSignal | Free covers top AI stories/models/repos; Pro is **$350/year ($29.17/month)** for a work-personalized, ad-free newsletter covering models, repos, and papers. [Official pricing](https://alphasignal.ai/pricing) | The closest public-news/research promise establishes a roughly $29 individual reference price. | Paperboy's $49 price requires a stronger outcome: user-chosen private-to-them forwarded sources, visible evidence, cross-source synthesis, feedback learning, and one next move. |
| Feedly Market Intelligence | Standard is **$1,600/month billed annually**, including 100 AI feeds, newsletter templates, collaboration, and up to 10 seats. [Official pricing](https://feedly.com/market-intelligence/pricing) | Enterprise intelligence is a different budget and buyer. | Avoid enterprise features; win on individual setup speed and specificity. |

**Conclusion:** Lead with **$49/month**, not $12. A $12 price positions Paperboy beside commodity readers and attracts buyers with low-cost curiosity rather than an expensive decision problem. $49 is still self-serve small-software pricing, sits above the $25-$29 specialist references, and remains far below enterprise intelligence. That premium is earned only if the product combines the buyer's chosen sources, produces cross-source conclusions with evidence, and reliably changes a decision. Feedly's enterprise price shows budget headroom, but it is not direct proof that individuals will pay $49.

### Price test

Test actual checkout behavior after a personalized sample edition, not survey answers. Randomly quote **$29, $49, or $79/month** to 60 commercially qualified, activated prospects, 20 per cell.

- Keep $49 as primary if at least 25% purchase and its conversion rate is no more than 25% lower than the $29 cell.
- Move to $79 if it produces the highest gross profit per activated prospect and its first-month activation/retention is not worse than $49 by more than 10 percentage points.
- Fall to $29 only if $29 converts at least 30% while $49 converts below 15% after the same sample quality.
- If every cell converts below 15%, fix the outcome and ICP; do not conclude that the answer is a cheaper summary product.

### Revenue model and margin gates

Subscription is the base business. Setup revenue funds early learning; Team expansion raises account value after the single-user loop retains.

| Illustrative mix | Operator MRR | Team MRR | Total MRR |
|---|---:|---:|---:|
| 50 Operator + 10 Team accounts | $2,450 | $1,490 | **$3,940** |
| 200 Operator + 30 Team accounts | $9,800 | $4,470 | **$14,270** |

These are arithmetic scenarios, not forecasts. Commercial gates:

- Target Operator variable cost at or below **$5/account/month**; hard cap **$8**, leaving at least 84% gross margin at $49.
- Target Team variable cost at or below **$20/account/month**; hard cap **$25**, leaving at least 83% gross margin at $149.
- After concierge onboarding is removed, median support must stay below **15 minutes per Operator account per month**.
- Use OSS/audience-led acquisition first. Target organic/blended CAC at or below one month of Operator gross profit (about **$41**) and any paid CAC below **$120**, a sub-three-month gross-profit payback.
- If source fetch, inference, or support breaches the hard cap for two months, reduce source frequency/context, batch synthesis, or raise price before adding customers.

## Distribution

The free repo is a credibility and acquisition asset, not the hosted product's pricing anchor.

1. **OSS conversion:** add a hosted sample CTA to the GitHub README and install docs: choose public sources/repos, receive one sample edition, then pay to schedule it. Do not cripple the self-hosted edition.
2. **Founder-led proof:** publish recurring before/after examples through Connor's existing X, LinkedIn, and email audience: “43 inputs became four material signals and one decision,” with every claim and source visible.
3. **Repo-owner outreach:** invite maintainers and technical founders whose public repos expose a clear stack. Generate a bounded sample from public context, then ask them to forward two newsletters to complete it.
4. **Public demonstration:** publish one weekly all-public Paperboy edition. It should demonstrate synthesis and evidence without leaking customer source lists or forwarded content.
5. **Referral loop:** after a customer records a useful action, offer one free month for a referred paid Operator. Cap credits so referrals improve CAC without creating a free hosted tier.

Do not buy broad consumer-news traffic. Distribution should reach people who control a technical product and can recognize the cost of a missed signal.

## Retention engine

Retention should come from better judgment over time, not a growing unread archive.

- Learn explicit source trust, topic weights, “already knew,” wrong-context, useful, and acted feedback.
- Preserve a small decision ledger linking an item, its evidence, the recommended move, and whether the user acted.
- Show a monthly value receipt: useful items, actions taken, sources pruned, and high-signal topics—not vanity counts of articles processed.
- Detect dead or repetitive sources and recommend removal; a smaller improving source set is a feature.
- Keep quiet-day behavior trustworthy. Padding the edition increases send volume but destroys the habit.

The retention floor is at least one useful item in three of four weeks and one recorded action per month. If users open but do not rate, click evidence, or act, the product is an email habit without proven economic value.

### Affiliate revenue

Subscription should remain the base business. Affiliate monetization before trust is dangerous because it makes rankings suspect. Keep affiliate links out of the beta. After paid month-two retention clears 70%, test clearly disclosed vendor referral links only on items that already ranked without commercial inputs; referral availability, rate, or payout must never affect inclusion or order. Treat affiliate income as a later **5-15% revenue supplement**, not the reason the brief exists. Continue only if affiliate items have no worse usefulness/dismissal rate than non-affiliate items.

## PMF risks

1. **Commodity risk:** summarization and email delivery are already cheap or free; Paperboy must prove better decisions, not prettier summaries.
2. **Precision risk:** one irrelevant daily email can train the user to ignore all later emails.
3. **Source-quality risk:** forwarded newsletters and public sources can repeat the same unsupported claim, creating false confidence unless provenance and corroboration remain visible.
4. **Actionability risk:** the current deterministic action queue can produce plausible but generic tasks; “one action” may not be worth doing.
5. **Trust risk:** forwarded email retention and repository access create security questions. Broad mailbox or private-repo scope would amplify them.
6. **Cadence risk:** a required daily edition may tempt the system to pad quiet days instead of reporting that nothing material changed.
7. **Cost risk:** cross-source synthesis can expand inference and fetch costs faster than subscription revenue unless source frequency and context are bounded.
8. **OSS cannibalization risk:** capable users may self-host, leaving the hosted product with higher-support customers.
9. **Cold-start risk:** a user's chosen newsletters and feeds may have little overlap, leaving no convincing cross-source synthesis in the first edition.
10. **Affiliate conflict risk:** monetized recommendations can destroy the trust the subscription depends on.

## Falsifiable PMF tests

Run these in order. Do not use broad sign-up counts as PMF evidence.

| Test | Method | Continue | Iterate | Kill or change wedge |
|---|---|---|---|---|
| Problem pull | Recruit 20 commercially qualified technical founders/operators. Ask each to forward two newsletters and choose at least one public feed/research/data source and one repo before showing a result. | At least 10 complete source setup; at least 6 ask to keep receiving the edition. | 6-9 complete setup. | Fewer than 6 complete setup. |
| Concierge activation | Manually configure the first 10 users and deliver a sample within 48 hours. | At least 7/10 mark one ranked or synthesized insight useful; at least 5/10 identify something they would otherwise have missed. | 5-6 useful. | Fewer than 5 useful. |
| Signal precision | Capture item-level useful/not-useful/already-knew/wrong-context feedback. | At least 70% useful across the first 100 rated items; fewer than 20% already-knew plus wrong-context. | 50-69% useful. | Below 50% useful after one tuning cycle. |
| Synthesis delta | Blind-test the Paperboy edition against source-by-source AI summaries for the same material. | At least 60% of users prefer Paperboy and can name a useful connection/evidence advantage. | 40-59% prefer it. | Below 40%; synthesis is not adding value. |
| Quiet-day trust | Seed days with no threshold-clearing material and days with only weak material. | At least 80% of weak items are excluded; quiet-day editions are not rated less trustworthy than normal editions. | 60-79% excluded. | Below 60%; ranking is manufacturing news. |
| Willingness to pay | Run the $29/$49/$79 checkout test after one personalized sample. | $49 converts at least 25% and stays within 25% of the $29 conversion rate, or $79 yields higher gross profit without materially worse activation. | $29 converts at least 30% while $49 lands at 15-24%. | Every cell below 15%; fix outcome/ICP before price. |
| Retention | Follow the first paid cohort for two billing cycles. | At least 70% retain into month two; at least 60% get a useful item in 3 of 4 weeks; at least 40% record one action/month. | 50-69% retain. | Below 50% month-two retention. |
| Unit economics | Measure actual fetch, inference, email, support, and refunds. | Operator variable cost at or below $5/account/month and support below 15 minutes/month. | Cost $5-$8. | Above $8 for two months after bounded-model optimization. |
| Affiliate trust, later only | After paid retention, show disclosed affiliate-eligible items to a small randomized cohort without changing rank. | Usefulness and dismissal remain within 5 percentage points of control. | 6-10 point degradation. | More than 10 point degradation; remove affiliate layer. |

## Product decisions

1. **Wedge:** Paperboy Daily Intelligence Brief for revenue-bearing technical founders and operators.
2. **Delivery:** one hosted morning email; explicit forwarding is also a bounded input.
3. **Sources:** forwarded newsletters, allowlisted public news/research/data, and up to 10 selected public GitHub repositories; no mailbox or private-repo access.
4. **Value unit:** a ranked, evidence-backed cross-source insight or decision—not a stack of summaries. Repo Radar is one section.
5. **Price:** lead at $49/month and validate against $29/$79 with real checkout behavior; do not default to $12 because it is easier to sell.
6. **Open-source boundary:** preserve the current self-hosted SQLite/systemd/Discord project; do not expose or multi-tenant it.
7. **Safety:** recommendations only. No autonomous code or external action.
8. **Monetization:** subscription first; no affiliate links during PMF beta.
9. **Build order:** sell paid concierge pilots and generate all-source editions manually → validate price/activation → build bounded forwarding intake and source registry → ranking/dedup/synthesis → edition renderer → scheduled email + feedback/value receipts → remove manual setup. Add the $149 small-Team delivery only after Operator retention. Do not build dashboards/private-repo/enterprise features before activation, synthesis-delta, payment, and margin thresholds clear.

## One-sentence positioning

**Paperboy turns the newsletters, news, research, data, and repositories you trust into one ranked morning edition—showing what is new, what connects, the evidence behind it, and what deserves your next move.**
