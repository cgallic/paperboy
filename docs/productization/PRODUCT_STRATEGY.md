# Paper Boy product strategy

**Decision date:** 2026-07-16
**Recommendation:** Test a hosted **Repo Impact Brief** for individual AI builders at **$12/month** while keeping the current self-hosted GitHub project free. Do not position Paper Boy as a generic AI newsletter, a blackboard, or an autonomous agent factory.

## Source-of-truth note

Current-product claims below are grounded in commit [`526ae15`](https://github.com/cgallic/paperboy/tree/526ae15ed76b501a53e3c0439b7215d234d8ec7c) of the exact public repo, `cgallic/paperboy`.

Live read-only checks were also run on 2026-07-16:

- **Brain host/source:** `agent:/home/connor/brain/events.db`. Relevant exact events include `1286611` (`claude-laptop/message`, the 10,000-to-12 positioning and open-brane relationship), `1187894` (`claude-laptop/message`, Paper Boy as a Discord daily digest and desired action-queue demo), and `1188408` (`claude-laptop/message`, the explicit file-first, no-external-send action-queue contract).
- **Gmail source:** live Gmail API via DWD for `connor@kaicalls.com` and `me@connorgallic.com`. Exact searches for `"Paper Boy"`, `paperboy`, `"cgallic/paperboy"`, `from:github paperboy`, and `subject:paperboy` found no current Paper Boy product thread. The three `paperboy` hits in `me@connorgallic.com` were unrelated 2018-2019 newsletter mentions (thread IDs `16aa268aed0e00e2`, `16a9701a0f54d7e0`, `1633b15f8a98ea8d`). No product requirement is inferred from those emails.

The 2026-07-16 operator direction is therefore treated as the forward product brief: **email is the first hosted delivery surface, and selected GitHub repositories are the first personalization context.** Neither is represented as a capability that already exists.

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

### Repo Impact Brief for AI builders

**Promise:** Paper Boy watches the technical firehose through the lens of the public GitHub repositories you select. It emails only the changes worth acting on, explains why each matters to a named repo, and recommends one next action.

The email should have no more than five items:

1. What changed.
2. Which selected repo it affects.
3. Why it matters now.
4. The source evidence.
5. One recommended action, or an explicit “watch, do nothing.”

If nothing clears the relevance bar, Paper Boy sends nothing. Silence is part of the product.

This wedge connects the strongest existing asset—system-specific research scoring—to a context source developers already maintain. It is narrower than “personalized news,” more actionable than a repository-activity summary, and substantially smaller than enterprise market intelligence.

## ICP and job to be done

### Primary ICP

Solo developers, technical founders, and AI-tool builders who:

- actively maintain roughly 2-10 public GitHub repositories;
- follow AI models, libraries, papers, and developer tooling;
- repeatedly discover important changes late or spend too much time scanning;
- can make an implementation decision without team procurement; and
- already pay for at least one developer productivity subscription.

Start with public repositories. Private-repository access introduces a trust and security sale that a $12 beta does not need.

### Excluded from the first wedge

- General news consumers.
- Nontechnical newsletter readers.
- Engineering managers seeking standup replacement or velocity analytics.
- Enterprise competitive-intelligence teams.
- Teams that require private-code indexing, SSO, audit logs, or procurement.

### JTBD

> When new tools, releases, papers, and technical news pile up, tell me only what changes a decision in the code I am already shipping, so I can act before the information goes stale without reading the entire firehose.

### Sharp pain

The pain is not “too much content.” Cheap readers already summarize content. The pain is the missing join between an external change and the developer's actual repositories. Existing tools usually answer either **what happened on the internet** or **what changed inside my repos**. The wedge must answer **what happened outside my repos that should change what I do inside them**.

## Recurring value loop

```text
select public repos
        ↓
derive a small repo/stack profile
        ↓
scan papers, releases, and technical news
        ↓
score against the selected repos
        ↓
email only threshold-clearing impacts + one action
        ↓
useful / not useful / acted / wrong-repo feedback
        ↓
tune interests, sources, and thresholds for the next brief
```

The existing `research-interests.md` contract is the seed for this loop, but user feedback is not yet implemented. Current digest code only excludes items after separate feedback/answer events exist; it does not provide the hosted feedback capture needed here ([`prompt_digest.py:55-86`](https://github.com/cgallic/paperboy/blob/526ae15ed76b501a53e3c0439b7215d234d8ec7c/paperboy/digest/prompt_digest.py#L55-L86)).

## Activation moment

Activation is not “connected a repo” or “opened the first email.” It is:

> Within 48 hours of selecting repos, the user marks at least one item useful and agrees that its recommended action applies to a specific repo.

The onboarding preview should produce one sample brief before payment. If Paper Boy cannot find a credible repo-specific impact from recent public signals, it has not activated the user.

## Hosted MVP

### In scope

- Email address plus 1-5 public GitHub repo URLs.
- A generated stack profile from bounded public repo material such as the README, dependency manifests, languages, releases, and topics.
- The existing research/news/paper intake where it is reliable, plus selected-repo context for scoring.
- One scheduled email surface, with evidence links and a hard item cap.
- Four feedback actions: useful, not useful, acted, wrong repo.
- Per-user source, repo, threshold, delivery-time, and feedback configuration.
- Basic run, delivery, click, feedback, and cost telemetry.
- A clear deletion path for account/config data.

### Architecture boundary

Keep the current SQLite/systemd project self-hosted and single-user. Do not expose its database or mutate it into the hosted multi-tenant service. The hosted product should reuse scoring contracts and content shapes behind a separate scheduled service and tenant configuration layer. This preserves the free project and avoids turning a local, unauthenticated event log into a public SaaS backend.

### Explicit non-goals

- Private repository access or broad GitHub OAuth scopes.
- Gmail mailbox ingestion. Email is delivery in the first wedge, not an inbox data source.
- Discord, Slack, mobile app, or dashboard delivery for hosted v1.
- Autonomous PR creation, code changes, purchases, or external actions.
- Team accounts, shared feeds, standup reports, analytics, SSO, or RBAC.
- A vector database, general personal memory product, or open-brane hosting.
- Affiliate-ranked recommendations.
- A marketplace or “agent factory.”

## Pricing hypothesis

### Offer

- **Self-hosted:** free, MIT GitHub project; users bring Linux, Ollama, Discord, and their own operation.
- **Hosted Personal beta:** **$12/month**, monthly cancellation, 1-5 public repos, scheduled repo-impact email, feedback learning, and no infrastructure setup.
- **Annual plan:** do not introduce until monthly willingness-to-pay and 30-day retention clear the thresholds below. Then test $99/year against $12 monthly.

Do not launch a permanently free hosted tier during PMF testing. The free self-hosted project is already the open-source acquisition path. Offer a no-card sample brief or short trial instead.

### $12 pressure test

As of 2026-07-16, current primary pricing pages show:

| Alternative | Current offer and price | What it proves | Paper Boy gap/opportunity |
|---|---|---|---|
| GitHub notifications | GitHub natively sends activity for watched repos to its inbox, mobile, or email; users can filter issue, PR, release, security, and discussion activity. [Official docs](https://docs.github.com/en/subscriptions-and-notifications/concepts/about-notifications), [subscription controls](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-subscriptions-for-activity-on-github/managing-your-subscriptions) | Repo email is already native and carries no separate product purchase. | Paper Boy cannot charge merely for forwarding repository activity. It must connect external signals to repo decisions. |
| Digest | Starter is **$6/month** and includes AI newsletter summaries, RSS, news sources, and GitHub Trending sources. [Official pricing](https://usedigest.com/pricing/) | Multi-source daily email aggregation is inexpensive. | A $12 brief must be twice as decision-useful, not just better formatted. |
| Inoreader | Pro is **$7.50/month billed annually or $9.99 monthly**, with monitoring feeds, filters/rules, AI summaries, and scheduled email digests. [Official pricing](https://www.inoreader.com/pricing/feature/subscriptions) | Power users can build sophisticated filters below $12. | Paper Boy must remove configuration work and supply repo-fit judgment. |
| Digest AI | Pro is **$15/month** for unlimited newsletter sources, advanced summaries, categories, and custom delivery time. [Official pricing](https://www.newsletterdigest.tech/pricing) | Inbox-summary buyers already see a $15 reference price. | Paper Boy at $12 is plausible, but only if selected repos materially improve ranking. |
| Git Digest | **$25/month billed annually** for unlimited teammates/repos, code-change summaries, and daily/weekly email or Slack. [Official product and pricing](https://gitdigest.ai/) | Customers pay for selected-repo summaries that replace coordination work. | Paper Boy should not compete on standups; it should cover external change → internal impact. |
| AlphaSignal | Free covers top AI stories/models/repos; Pro is **$350/year ($29.17/month)** for a work-personalized, ad-free newsletter covering models, repos, and papers. [Official pricing](https://alphasignal.ai/pricing) | The closest broad promise already exists and charges above $12. | Paper Boy needs verifiable repo-specific “why/action,” not another AI-engineer digest. |
| Feedly Market Intelligence | Standard is **$1,600/month billed annually**, including 100 AI feeds, newsletter templates, collaboration, and up to 10 seats. [Official pricing](https://feedly.com/market-intelligence/pricing) | Enterprise intelligence is a different budget and buyer. | Avoid enterprise features; win on individual setup speed and specificity. |

**Conclusion:** $12 is a reasonable hypothesis between commodity aggregation and specialized AI-engineer intelligence. It is not validated. If the product is only “pick repos, get an email summary,” GitHub plus a $6-$10 reader wins. The paid delta must be repo-specific impact and trusted next-action judgment.

### Affiliate revenue

Subscription should be the PMF test. Affiliate monetization before trust is dangerous because it makes rankings suspect. Keep affiliate links out of the beta. After paid retention is proven, test clearly disclosed referral links only on items that already cleared the relevance score; referral availability must never affect ranking. Continue only if affiliate items have no worse usefulness/dismissal rate than non-affiliate items.

## PMF risks

1. **Commodity risk:** summarization and email delivery are already cheap or free.
2. **Precision risk:** one irrelevant daily email can train the user to ignore all later emails.
3. **Context risk:** public README/manifests may not reveal the user's actual roadmap or constraints.
4. **Actionability risk:** the current deterministic action queue can produce plausible but generic tasks; “one action” may not be worth doing.
5. **Trust risk:** repository access, even public-only, creates security questions. Private repo scope would amplify them.
6. **Cadence risk:** daily may be too frequent for repo-level impact. A three-times-weekly or event-triggered brief may retain better.
7. **Cost risk:** hosted inference, fetch, and email costs could make a $12 plan unattractive if scoring is not aggressively bounded.
8. **OSS cannibalization risk:** capable users may self-host, leaving the hosted product with higher-support customers.
9. **Cold-start risk:** a user may select a quiet or poorly documented repo and receive no convincing first impact.
10. **Affiliate conflict risk:** monetized recommendations can destroy the trust the subscription depends on.

## Falsifiable PMF tests

Run these in order. Do not use broad sign-up counts as PMF evidence.

| Test | Method | Continue | Iterate | Kill or change wedge |
|---|---|---|---|---|
| Problem pull | Recruit 20 qualified AI builders from repo-owner communities. Ask for 1-5 public repos before showing a generated result. | At least 10 provide repos; at least 6 ask to keep receiving the brief. | 6-9 provide repos. | Fewer than 6 provide repos. |
| Concierge activation | Manually configure the first 10 users and deliver a sample within 48 hours. | At least 7/10 mark one repo-specific item useful; at least 5/10 agree with the action. | 5-6 useful. | Fewer than 5 useful. |
| Signal precision | For each brief, capture item-level useful/not-useful feedback. | At least 70% useful across the first 100 rated items; fewer than 15% wrong-repo. | 50-69% useful. | Below 50% useful after one tuning cycle. |
| Cadence | Randomize daily versus Monday/Wednesday/Friday for 20 users over four weeks. Measure useful/acted feedback, not opens. | Keep the cadence with at least 20% higher actions per delivered email; daily survives only if it wins. | Difference under 20%: default to lower frequency. | Both cadences produce action in fewer than 20% of emails. |
| Willingness to pay | After two useful weeks, require $12 to continue. | At least 8 of 20 qualified activated users pay. | 4-7 pay; test promise/onboarding once. | Fewer than 4 pay. |
| Retention | Follow the first paid cohort for two billing cycles. | At least 70% retain into month two and at least 50% take a useful/acted action in 3 of 4 weeks. | 50-69% retain. | Below 50% month-two retention. |
| Unit economics | Measure actual fetch, inference, email, and support burden. | Variable cost at or below $2/user/month and median support below 10 minutes/user/month. | Cost $2-$4. | Above $4 after bounded-model optimization. |
| Affiliate trust, later only | After paid retention, show disclosed affiliate-eligible items to a small randomized cohort without changing rank. | Usefulness and dismissal remain within 5 percentage points of control. | 6-10 point degradation. | More than 10 point degradation; remove affiliate layer. |

## Product decisions

1. **Wedge:** Repo Impact Brief for individual AI builders.
2. **Delivery:** email only for the hosted PMF test.
3. **Context:** 1-5 selected public GitHub repos; no private access in MVP.
4. **Value unit:** one repo-specific decision or action, not an article summary.
5. **Price:** test $12/month; keep it labeled as a hypothesis until paid retention.
6. **Open-source boundary:** preserve the current self-hosted SQLite/systemd/Discord project; do not expose or multi-tenant it.
7. **Safety:** recommendations only. No autonomous code or external action.
8. **Monetization:** subscription first; no affiliate links during PMF beta.
9. **Build order:** concierge proof → sample generator → scheduled email + feedback → billing. Do not build team/dashboard/private-repo features before the activation and payment thresholds clear.

## One-sentence positioning

**Paper Boy reads the releases, papers, and technical news you do not have time to track, checks them against the GitHub repos you are actually shipping, and emails only what changes your next move.**
