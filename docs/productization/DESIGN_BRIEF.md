# Paperboy Daily Intelligence Brief — product design brief

Status: locked local implementation direction
Updated: 2026-07-16 after product and commercial pivots
Authority: cgallic/paperboy plus the operator's current product decision

## 1. Product decision

Keep the name **paperboy**. Present it lowercase in the wordmark and as
“Paperboy” in prose.

Tagline:

> **What matters, delivered.**

Product:

> **Paperboy Daily Intelligence Brief** turns intentionally forwarded
> newsletters, public news/research/data, and selected public GitHub
> repositories into one evidence-linked morning edition for technical
> founders and operators.

The brief is not a generic summary and Repo Impact is not the whole product.
Repo-specific impact is one section called **Repo Radar**. The complete
edition has four capped sections:

1. **Today in 60 Seconds** — the small set of outside changes most likely to
   affect an operating or product decision.
2. **Repo Radar** — external changes that may alter a selected repository's
   next move.
3. **Research Worth Reading** — transferable techniques with enough evidence
   to justify attention.
4. **Watchlist / Do Nothing** — explicit decisions to monitor or ignore so
   the brief also prevents wasted work.

Email remains the product. The MVP has no dashboard or autonomous-action
surface.

## 2. Commercial decision

Primary offer:

> **Paperboy Operator — $49/month**

Audience: revenue-bearing AI, SaaS, and devtool founders/operators for whom a
missed dependency, vendor, cost, policy, research, or market change can alter
a real product or operating decision.

The price is a hypothesis, not a validated or live offer. After a personalized
sample demonstrates value, test **$29 / $49 / $79** willingness to pay.

Optional validation:

- **$199 one-time concierge calibration** may be tested while learning how
  much setup customers need. It is a validation option, not promised
  fulfillment in the prototype.
- A **$149 small-Team** plan comes only after individual retention is proven.
- The free MIT self-hosted Paperboy project remains the acquisition path.
- Affiliate availability must never affect ranking. Keep affiliate links and
  mechanics out of the MVP UI.

The value claim is decision quality, not a fabricated time-saved number:

> Know what changed, which decision it touches, what deserves inspection, and
> what can wait.

## 3. MVP boundary

In scope for the product surface:

- Email magic-link identity
- Explicit forwarded-email/newsletter source lane using a private alias
- Shared public news, research, release, and tracked-data source lane
- Optional read-only GitHub App for 1–5 selected public repositories
- Interests, active work, watchlist/risks, exclusions, and schedule
- Personalized sample before payment
- One responsive morning email with capped, evidence-linked items
- Useful, not useful, acted, and wrong-repo feedback
- Checkout handoff and account/privacy/billing states
- Free self-hosted GitHub route

Not in the MVP:

- Gmail OAuth or ambient inbox access
- Private repositories
- Dashboard, blackboard, archive, or team feed
- Autonomous PRs, code changes, issue creation, purchases, or agent execution
- Affiliate-ranked recommendations
- Slack, Discord, or mobile delivery
- Team plan, SSO, RBAC, procurement, or analytics
- Live connector, auth, email, model, billing, or backend behavior in the
  local no-secrets implementation

The existing SQLite/systemd/Discord runtime remains the free self-hosted
edition. Do not expose or multi-tenant it.

## 4. Audience and job

Primary audience:

- Founder/operator actively making product, cost, vendor, model, dependency,
  and go-to-market decisions for an AI, SaaS, or developer-tool business
- Maintains public repositories or can describe active systems and risks
- Follows several newsletters, releases, data points, news sources, and papers
- Needs judgment across sources, not another place to browse them

Core job:

> When the technical and market firehose changes, tell me what changes a
> decision in the business or product I am operating, show the evidence, and
> make it safe to ignore the rest.

The interface must answer:

- “Is this intelligence or just summaries?”
- “What exactly reaches Paperboy?”
- “Does forwarding grant inbox access?”
- “Does GitHub access include every repository or any write authority?”
- “Why did an item make the brief?”
- “Can it say do nothing?”
- “What will arrive, when, and how much does it cost?”
- “Can I inspect or self-host the underlying project?”
- “What happens when I disconnect, cancel, or delete?”

## 5. Brand and visual thesis

### Editorial dispatch desk

Paperboy feels like a precise morning edition assembled inside a technical
newsroom: warm paper, dark ink, signal-blue editorial marks, ruled columns,
and compact source metadata.

It must not look like:

- a generic blue SaaS dashboard;
- a nostalgic newspaper costume;
- an AI-gradient content app;
- a blackboard, affiliate factory, or autonomous agent console.

The memorable motif is a **blue delivery route** connecting sources,
interests, evidence, and email. It appears in How It Works and onboarding,
then resolves into a delivered check. It never loops or decorates dense
content.

Logo:

- Lowercase “paperboy” wordmark
- Folded page corner crossed by the blue route
- No child mascot, newsboy cap, blackboard, or factory imagery

### Tokens

| Token | Value | Use |
|---|---:|---|
| paper | #F3EEE3 | Main background |
| paper-raised | #FBF8F1 | Cards, forms, email body |
| ink | #15171A | Primary text and dark actions |
| ink-soft | #555C63 | Secondary text |
| rule | #D4CCBD | Dividers and borders |
| signal | #2864DC | Primary action, links, delivery route |
| signal-dark | #17489F | Hover/pressed action |
| approve | #237A4B | Success |
| caution | #9B5B08 | Attention |
| reject | #B33A3A | Error/destructive |
| press | #11161C | Dark editorial contrast |
| press-panel | #192129 | Dark inset surface |

Typography:

- Editorial display: Newsreader Variable, with Sitka/Palatino/Georgia fallback
- Interface: IBM Plex Sans, with Aptos/Segoe UI fallback
- Evidence/data: IBM Plex Mono, with Cascadia/Consolas fallback
- Hero: 72/72 desktop, 46/48 mobile
- Page title: 44/48 desktop, 34/38 mobile
- Body: 16/25
- Metadata: 10–12/16 in mono

Shape and spacing:

- Four-pixel base; use 8, 12, 16, 24, 32, 48, 72, 96
- Ten-pixel cards, eight-pixel controls, one-pixel rules
- App maximum width 1240 pixels; email maximum width 640 pixels
- Optional paper grain at no more than three percent opacity

## 6. Information architecture

Public:

- Landing
  - Economic/decision outcome
  - Labeled sample edition
  - Four-step route
  - Permission boundary
  - Operator pricing
  - Free self-hosted alternative
  - FAQ
- Sign in
- GitHub project

Onboarding:

1. Sources
   - Forwarded newsletters
   - Public news/research/data
   - Optional selected public GitHub repos
2. Interests
   - Active work
   - Editorial themes
   - Decision/risk watchlist
   - What to skip
3. Delivery
   - Verified email in production
   - Days, time, time zone
   - Personalized sample preview
4. Hosted checkout handoff

Account/status:

- Commercial and billing state
- Selected source lanes and repositories
- Interests
- Delivery
- Connection permissions
- Privacy, retention, export/deletion

The account screen is a compact setup/status surface. It is not a content
dashboard. The brief stays in email.

## 7. Conversion hierarchy and exact landing copy

Sequence:

1. Decision outcome
2. Labeled example
3. Source-to-email route
4. Permission clarity
5. Price and self-hosted choice
6. Objection-handling FAQ
7. Final CTA

One filled primary action per viewport. No fake ratings, testimonials, logos,
customer counts, revenue, “people viewing,” time saved, scarcity, or
countdowns.

Header:

- paperboy
- How it works
- Pricing
- GitHub
- Sign in
- **Build a Daily Brief**

Hero:

> DAILY INTELLIGENCE BRIEF
> **Know what changes your next move.**
> Paperboy turns the newsletters you forward, public news and research,
> tracked data, and selected GitHub repos into one evidence-linked morning
> edition: what changes a decision, what deserves inspection, and what can
> wait.
> **Build a Daily Brief**
> View the open-source project

Boundary line:

> No Gmail OAuth · Read-only GitHub · Decision-ready morning email

Example label:

> EXAMPLE EDITION · FICTIONAL FIXTURE DATA

How it works:

> **1. Choose source lanes**
> Forward newsletters, use the public catalog, and optionally select public
> repos.
>
> **2. Set your interests**
> Name the themes, systems, decisions, and risks that deserve attention.
>
> **3. Rank and cap the edition**
> News, research, data, and repo signals compete for limited space.
>
> **4. Get the morning email**
> Four short sections arrive with evidence—and silence when nothing clears the
> bar.

Permission copy:

> **Explicit inputs, not ambient access.**
> Forward only the newsletters you choose. Public intelligence comes from a
> shared catalog. The optional GitHub App is read-only and limited to selected
> public repositories.

Pricing:

> **Paperboy Operator**
> **$49 / month**
> Primary price hypothesis—not a live offer.
>
> - One scheduled morning intelligence edition
> - Forwarded newsletters without inbox access
> - Public news, research, release, and data signals
> - Optional context from 1–5 public repositories
> - Economic-decision lens for cost, dependency, vendor, and market changes
> - Capped sections, source evidence, and feedback
>
> **Build a personalized sample**

Validation note:

> Test $29 / $49 / $79 only after a personalized sample demonstrates value.
> A $199 one-time concierge calibration is a validation option, not available
> from this preview. A $149 small-Team plan comes only after retention.

Self-hosted:

> **Prefer to run it yourself?**
> The original Paperboy remains free and open source. Bring Linux, Ollama,
> Discord, and your own operations.
> **Open the GitHub project**

## 8. Source selection and consent

### Forwarded newsletters

Copy:

> **Forwarded newsletters**
> Send only chosen messages to your private Paperboy forwarding alias. This
> does not connect or read your inbox.

The local implementation shows:

> local-preview@in.paperboy.example
> Demo address; receives nothing.

The production product must verify the inbound provider signature, accept only
the workspace alias, strip active content and quoted history, ignore launch
attachments, and disclose retention. None of that is claimed live in the
prototype.

### Public intelligence

Copy:

> **Public news, research, and data**
> Shared catalog for releases, papers, technical news, and tracked metrics.

Custom arbitrary URLs are not part of the first product surface.

### GitHub

Copy:

> **Selected public GitHub repos**
> Optional Repo Radar context. Select 1–5 public repositories.

Planned permission ledger:

| Permission | Level | Reason |
|---|---|---|
| Metadata | Read | Repository identity and mapping |
| Contents | Read | Bounded commit/dependency context |
| Pull requests | Read | Opened, merged, and review activity |
| Issues | Read | Opened, closed, and comment activity |
| All writes | None | Product cannot modify customer accounts |

No Actions, workflows, administration, members, organization write, content
write, issue write, or pull-request write permissions.

The production UI must render provider-verified scopes. The local surface uses
clearly fictional demo-labs repositories and makes no GitHub request.

## 9. Sign-in, interests, delivery, and checkout copy

Sign-in:

> **Start your Daily Brief.**
> Enter an email and we will send a secure sign-in link.
> **Email me a sign-in link**
> Signing in does not connect your inbox or GitHub account.

Local success:

> **Check your email—simulated.**
> No message was sent. Continue with the local magic link to test the flow.

Interests:

> **What deserves your attention right now?**
> Give Paperboy an editorial lens for the newsletters, public signals, data,
> and optional repos you selected.

Fields:

- Interests and active work
- Decisions or risks on the watchlist
- Editorial themes
- What Paperboy should skip

Delivery:

> **When should your Daily Brief arrive?**
> Choose the delivery email, days, local time, and time zone.

Sample:

> **Your first brief will look like this.**
> Local fixture data · not sent

Checkout handoff:

> **No charge can be created here.**
> This static surface has no Stripe account, backend, price ID, or payment
> form. “Preview successful setup” changes browser state only.

Summary:

> Paperboy Operator · $49/month price hypothesis
> Sources, interests, and schedule shown before payment
> Billing today: $0.00 — demo

## 10. Email as the product

Subject pattern:

> Paperboy · {n} decisions and changes worth your attention

Preheader:

> Your capped morning edition from explicitly selected sources

Header:

> PAPERBOY · DAILY INTELLIGENCE BRIEF
> **{localized long date}**
> {n} capped items across {selected source lanes}

Section caps for the first product test:

- Today in 60 Seconds: at most 2
- Repo Radar: at most 1
- Research Worth Reading: at most 1
- Watchlist / Do Nothing: at most 1
- Total maximum: 5 items

Each substantive item contains:

> {SOURCE TYPE} · {score}/10 · {decision/repo/watchlist target}
> **{headline}**
> **Why it matters**
> {grounded reason}
> **Inspect next / Decision**
> {bounded next check or explicit do-nothing judgment}
> View source evidence
> Useful · Not useful · Acted · Wrong repo

Use calibrated language for inference. “May affect” and “worth checking” are
preferred to unsupported certainty.

Email footer:

> You received this because Paperboy is scheduled for {days} at {time zone}.
> Change sources · Change interests · Change delivery · Privacy and billing

No Approve, Run, Create issue, Open PR, Buy, or affiliate link appears in the
first email.

## 11. Account, privacy, and billing states

The local account page previews state; it does not assert a live subscription
or connector.

Billing:

| State | Message | Action |
|---|---|---|
| Checkout incomplete | Finish payment to activate delivery. | Finish payment |
| Active | Subscription is active. | Manage billing |
| Processing | Payment is processing; update when provider settles. | Refresh |
| Past due | Payment needs attention; apply verified recovery policy. | Update |
| Cancel scheduled | Show only provider-verified period end. | Keep Paperboy |
| Canceled | Delivery is off; deletion is separate. | Restart |
| Unavailable | Billing unavailable; no new charge started. | Try again |

Privacy surface must distinguish:

- Email identity
- Forwarding alias
- Public catalog
- GitHub selected repositories and exact scopes
- Inference/provider processing disclosure
- Retention
- Export
- Disconnect source
- Delete derived source data
- Cancel billing
- Delete account

These are separate controls. Disconnecting does not cancel; canceling does not
delete; deletion does not infer an external provider revocation.

## 12. Interaction rules

- One primary filled action per viewport.
- Buttons press one pixel and scale to .98 for 100 milliseconds.
- The delivery route animates once and respects reduced motion.
- Source lanes are independent and explicit.
- Repository count updates immediately and announces changes with aria-live.
- Enforce the five-repository cap at selection time.
- Preserve setup state when navigating backward.
- Validate email, interests, watchlist, and at least one delivery day.
- A personalized sample appears before the checkout handoff.
- Feedback changes local state immediately and is reversible.
- Source removal names the effect before confirmation.
- Loading uses layout-matched warm skeletons if asynchronous behavior is added.
- Never animate price, score, or counts like live demand.

## 13. Responsive and accessibility requirements

- Design from 320 pixels upward.
- Breakpoints: 640, 768, 1024, 1280.
- Mobile padding: 16 pixels; desktop: 24–32.
- Every interactive target is at least 44 by 44 pixels.
- Maintain eight pixels between adjacent targets.
- Repository picker becomes single-column on mobile.
- Email remains readable at 320 pixels and with images disabled.
- Meet WCAG 2.2 AA contrast.
- Provide skip link, landmarks, real headings, labels, error summaries, and
  programmatic status.
- Pair color with icon/text.
- Scores expose “8 out of 10.”
- Visible focus is a three-pixel signal ring with a paper offset.
- Core actions work by keyboard.
- Escape closes dialogs only if focus returns to the trigger.
- Respect prefers-reduced-motion.
- Critical email meaning cannot depend on webfonts, background images, hover,
  or JavaScript.

## 14. Empty, error, and revocation states

| Context | Copy |
|---|---|
| No source | Choose forwarding, public intelligence, or a fixture repository. |
| Sixth repo | This product supports up to five selected repositories. |
| No repo | Repo Radar will stay empty; other source lanes can still produce the brief. |
| First run | Your first Daily Brief is being prepared. |
| Quiet day | Nothing cleared the relevance bar. No filler was added. |
| GitHub failed | GitHub did not finish connecting; no repository was selected. |
| Repo refresh failed | Could not refresh {repo}; show last successful context. |
| Brief failed | Today's brief could not be completed; no email was sent. |
| Delivery failed | The edition exists, but email delivery failed. |
| Auth expired | The session expired before the change was saved. |
| Billing unavailable | Billing unavailable; no new charge was started. |

Revoking GitHub stops future repo ingestion and clears Repo Radar once retained
context expires. It does not affect forwarded/public lanes. Gmail OAuth is not
present to revoke.

## 15. Existing dashboard component map

The static action-queue dashboard is an information-pattern source, not an MVP
route.

| Existing element | Daily Brief component | Change |
|---|---|---|
| Header/meta | BriefHeader/BriefSummary | Date, cap, source lanes |
| Note | GuardrailNotice | Explain simulated/no-action boundary |
| Grid | SectionedSignalList | Four editorial sections, single reading column |
| Card | IntelligenceItem | Source, target, score, reason, decision, evidence |
| Score | RelevanceScore | Accessible numeric label |
| Source line | SourceLedger | Source kind, repo/decision target, fixture label |
| Why | WhyItMatters | First-class visible reasoning |
| Suggested action | InspectNext/Decision | Bounded check or do-nothing judgment |
| Approve/dismiss | FeedbackControls | Useful, not useful, acted, wrong repo |
| Status | StatusBadge | Setup, connector, delivery, billing |
| Empty | QuietEditionState | No filler when nothing clears bar |
| Footer | BriefPreferenceFooter | Source/interests/delivery/privacy links |
| Fixture array | ExampleEditionFixture | Clearly labeled, local only |
| Escaping | SafeText renderer | Never trust source HTML |

## 16. Local no-secrets acceptance

Required screen set:

1. Landing and Operator pricing
2. Simulated magic link
3. Source lanes and exact GitHub permission explanation
4. Fictional 1–5 public-repository picker
5. Interests/watchlist
6. Schedule and personalized sample
7. Disabled checkout handoff
8. Account/privacy/billing state previews
9. Responsive Daily Intelligence Brief

Local safety:

- No environment variables or secrets
- No backend
- No fetch, XMLHttpRequest, WebSocket, sendBeacon, form action, remote UI
  framework, or remote asset requirement
- State persisted only under a named localStorage key
- External evidence/GitHub links navigate only after click
- Checkout can create no customer, charge, invoice, or subscription
- Fixtures are labeled fictional or public demo data

Golden path:

> Landing → email simulation → choose source lanes → optionally select fixture
> repos → describe interests/watchlist → set schedule → inspect the four-part
> email → view disabled $49 checkout handoff → preview account/privacy/billing
> states → clear local data.

First usability questions:

1. Can a technical founder explain the difference between this brief and a
   generic newsletter?
2. Can they name the three source lanes and their permission boundaries?
3. Does Watchlist / Do Nothing feel like saved attention rather than missing
   content?
4. Does the personalized sample establish enough economic decision value to
   test $29 / $49 / $79?
5. Do they understand that email—not a dashboard or autonomous agent—is the
   MVP product?
