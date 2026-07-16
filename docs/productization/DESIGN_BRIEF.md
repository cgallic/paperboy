# Paperboy productization design brief

Status: decision-grade MVP direction
Date: 2026-07-16
Authority: cgallic/paperboy at commit 526ae15, especially README.md,
docs/ARCHITECTURE.md, docs/personalizing.md, docs/action-queue.md, and
dashboard/action-queue.html

## 1. Locked product decision

Keep the name **paperboy**, lowercase in the wordmark and “Paperboy” in prose.

Tagline:

> **What matters, delivered.**

Paid wedge:

> **Repo Impact Brief** — a scheduled email for solo and AI builders that
> explains which external developments may affect 1–5 selected public GitHub
> repositories, why the fit is credible, and what to inspect next.

MVP boundary:

- Hosted scheduled brief and tenant configuration
- Email identity and one email delivery surface
- One to five explicitly selected public repositories
- Read-only GitHub access; no code, issue, or pull-request writes
- Existing Paperboy scoring, explanation, evidence, and digest-formatting ideas
- Free open-source/self-hosted Paperboy remains available
- No web dashboard, autonomous actions, affiliate mechanics, Gmail OAuth, or
  multi-tenant exposure of the current SQLite/systemd runtime
- Forwarded-email intake is architecture-compatible but not an MVP promise

Use **$12/month** only as a PMF pricing hypothesis. Do not publish annual
savings, a trial, “cancel anytime,” or refunds until policy and billing
behavior support those statements.

The smallest coherent screen set is:

1. Landing with pricing
2. Email sign-in
3. GitHub consent and public-repository picker
4. Focus, schedule, and first-brief preview onboarding
5. Hosted checkout handoff
6. Confirmation/account page with repository, schedule, privacy, and billing
   controls
7. The email brief itself

Dashboard, queue, and web digest-detail designs below are **post-MVP reference
only**. They map the existing dashboard so later work can extend the product
without smuggling a dashboard into this build.

## 2. Product truth

Verified in the repository:

- Paperboy scores news and research against a user's stated systems/interests.
- Its default morning digest limit is up to 12 items.
- Research scores include relevance, applicable systems, improvement idea,
  novelty, prototype flag, reason, source URL, and timestamp.
- Action items include title, source, score, reason, suggested action, status,
  and evidence.
- The existing action queue is review-first and sends nothing by itself.
- The open-source predecessor is self-hostable and currently uses local
  Ollama, SQLite, systemd, and Discord.

The hosted product may reuse the logic and information model. It must not imply
that its runtime is local, that Discord is supported in the MVP, or that
approval executes work.

## 3. Audience, job, and conversion thesis

Primary audience: solo technical founders and AI builders maintaining several
public repositories while trying to follow research, model, tooling, and
platform changes.

Core job:

> When I start the day, tell me which changes could affect the repositories I
> am actively building, show the evidence, and give me a concrete place to
> inspect next.

The interface must answer:

- “Is this more than a generic newsletter?”
- “Why does it need GitHub?”
- “Can it see every repository?”
- “Can it change my code?”
- “What gets emailed and when?”
- “Can I inspect or self-host the underlying project?”
- “What happens when I disconnect or cancel?”

Conversion hierarchy:

1. Lead with the cost of missing repo-relevant changes.
2. Show a real, clearly labeled example brief.
3. Explain selected-repository context and read-only permission before OAuth.
4. Prove trust with exact scopes, evidence links, and the public repository.
5. Present one hosted plan and the free self-hosted alternative.
6. Reach a personalized preview during onboarding.

One filled primary action per viewport. No testimonials, user/revenue counts,
fake activity, countdowns, unsupported volume claims, or scarcity.

## 4. Visual thesis: editorial dispatch desk

Paperboy should feel like a precise morning edition assembled inside a
technical newsroom: warm paper, dark ink, blue editorial marks, ruled columns,
and compact source metadata. It should not become a generic blue SaaS
dashboard or a nostalgic newspaper costume.

The memorable motif is a **blue delivery route**: one thin line with stops for
repos, relevance, evidence, and email. It appears in “How it works,” becomes
the onboarding progress indicator, and resolves into a delivered check. It
never loops or decorates dense content.

Logo:

- Lowercase “paperboy” wordmark
- Folded page corner crossed by the blue route as the mark
- No child mascot, newsboy cap, blackboard, or affiliate/factory imagery

### Tokens and typography

| Token | Value | Use |
|---|---:|---|
| paper | #F3EEE3 | Page background |
| paper-raised | #FBF8F1 | Cards, fields, email body |
| ink | #15171A | Primary text and dark buttons |
| ink-soft | #555C63 | Secondary text |
| rule | #D4CCBD | Dividers and borders |
| signal | #2864DC | Primary action, links, route |
| signal-dark | #17489F | Hover/pressed primary |
| approve | #237A4B | Success |
| caution | #9B5B08 | Warning |
| reject | #B33A3A | Error/destructive |
| press | #11161C | Deferred dark review surface |
| press-panel | #192129 | Deferred dark card |

- Display: Newsreader Variable, 500–650, for marketing and brief headlines.
- UI/body: IBM Plex Sans, 400–600.
- Evidence/data: IBM Plex Mono, 400–600, for repos, sources, scores, and time.
- Hero: 72/72 desktop, 46/48 mobile.
- Page title: 44/48 desktop, 34/38 mobile.
- Body: 16/25 desktop, 16/24 mobile.
- Four-pixel spacing base; primary intervals 8, 12, 16, 24, 32, 48, 72, 96.
- Ten-pixel card corners, eight-pixel fields/buttons, one-pixel rules.
- Optional paper grain at no more than three percent opacity; never under
  forms or dense reading text.

## 5. Information architecture

Public:

- Home: outcome, example brief, how it works, privacy/control, pricing, FAQ
- Open-source project
- Sign in

MVP account:

- Setup status
- Repositories
- Focus
- Delivery schedule
- Privacy/connection
- Billing

MVP has no dashboard navigation. The account page is a compact configuration
and status surface, not a content destination. Email is the product.

Post-MVP only:

- Today
- Digest archive/detail
- Review queue
- Rich source controls

## 6. Exact MVP copy and screen specification

### 6.1 Landing and pricing

Header:

- “paperboy”
- “How it works”
- “Pricing”
- “GitHub”
- “Sign in”
- Primary: “Start a Repo Impact Brief”

Hero:

> REPO IMPACT BRIEF
> **Wake up to the changes that matter to your code.**
> Paperboy follows technical news and research, checks the fit against 1–5
> public repositories you select, and emails you a short brief with the reason
> and evidence.
> **Start a Repo Impact Brief — $12/month**
> View the open-source project

Support line:

> Read-only GitHub access. Selected public repositories only. One scheduled
> email.

Example module:

> EXAMPLE REPO IMPACT BRIEF
> **Rubric-grounded self-critique for smaller models**
> RESEARCH PAPER · 8/10 · applies to api-evals
> **Why it may matter**
> A fixed scoring rubric could improve agreement in this repository's current
> evaluation step.
> **Inspect next**
> Compare rubric-guided and freeform critique on one held-out set.
> View source evidence

The example must be labeled and derived from the repository's public fixture
shape. Never present it as a customer result.

How it works:

> **1. Choose 1–5 public repositories**
> Paperboy reads only the repositories you select.
>
> **2. Set the relevance lens**
> Describe what you are building, its stack, and its current friction.
>
> **3. Get the Repo Impact Brief**
> Paperboy explains the strongest matches and sends one scheduled email.

Permission block:

> **Read context, not control.**
> MVP access is read-only and limited to selected public repositories.
> Paperboy cannot push code, open pull requests, change issues, or see
> unselected private repositories.

Pricing:

> **Paperboy Personal**
> **$12 / month**
> Pricing hypothesis for hosted Paperboy.
>
> - One scheduled Repo Impact Brief
> - Context from 1–5 selected public repositories
> - Repo-specific relevance, reasons, and evidence
> - Email delivery
> - Hosted scheduling and updates
>
> **Start a Repo Impact Brief — $12/month**

Self-hosted:

> **Prefer to run it yourself?**
> The original Paperboy remains free and open source. Its local setup and
> current delivery flow are documented on GitHub.
> **Open the self-hosted project**

FAQ:

- **Does Paperboy need every repository?**
  No. Select one to five public repositories during setup and change them
  later.
- **Can Paperboy change my code?**
  No. The MVP uses read-only GitHub access and does not write code, issues, or
  pull requests.
- **Does Paperboy read my inbox?**
  No. Email is used for sign-in and delivery. The MVP does not request Gmail
  OAuth.
- **What arrives by email?**
  One scheduled brief with the strongest repo-relevant items, why each may
  matter, what to inspect next, and source links.
- **Is this the open-source project?**
  The hosted subscription builds on the project's scoring and digest ideas.
  The free self-hosted repository remains available.

### 6.2 Email sign-in

Email is identity only and must stay separate from GitHub ingestion consent.

> **Start your Repo Impact Brief**
> Enter your email and we will send a secure sign-in link.
> Email address
> **Email me a sign-in link**
>
> Signing in does not connect your inbox or GitHub account.

Success:

> **Check your email**
> We sent a sign-in link to {email}.
> Use a different email

Expired:

> **That sign-in link has expired.**
> Request a new link to continue.
> **Send a new link**

Only display a numeric expiry after auth configuration verifies it.

### 6.3 GitHub consent and repository picker

> SETUP 1 OF 3
> **Choose the public repositories Paperboy may read.**
>
> Paperboy uses repository metadata, selected file content, and recent changes
> to understand what you are building. Access is read-only. It cannot push
> code, open pull requests, or change issues.
>
> **Connect GitHub**
> See the exact GitHub permissions

Repository picker:

> **Choose 1–5 public repositories**
> Search public repositories
> Selected only
> {n} of 5 selected
> **Use {n} repositories**

Disable the sixth checkbox with:

> The MVP supports up to five repositories. Remove one to choose another.

Use a fine-grained GitHub App or equivalent selected-repository grant. The UI
must render the exact verified scope, not a hand-written approximation.

Error/revoked:

> **GitHub access needs attention.**
> Paperboy can no longer refresh the selected repositories. Reconnect to
> resume future briefs. No write operation was attempted.
> **Reconnect GitHub**

### 6.4 Focus, schedule, and preview

The blue route is a three-step progress indicator. Preserve entered data when
moving backward.

Step 2:

> SETUP 2 OF 3
> **What are these repositories trying to do?**
> Give Paperboy enough context to separate useful changes from merely
> interesting ones.

For each repo:

- Repository name, read-only
- What it does — “Describe the user, stack, and current job.”
- Current friction — “What is slow, unreliable, or unclear?”
- Active themes — addable tags
- Score low — optional exclusions

Helper:

> Specific systems and current friction produce sharper reasons.

CTA: “Save focus and continue”

Step 3:

> SETUP 3 OF 3
> **When should your Repo Impact Brief arrive?**

Fields:

- Delivery email
- Time
- Detected but editable time zone
- Days of week

Preview:

> **Your first brief will look like this**

Use labeled demo data until a real run completes.

CTA:

> **Continue to payment — $12/month**

Support:

> You will review payment details before the subscription is created.

No Gmail OAuth, source marketplace, RSS editor, or forwarded-email setup in
the MVP. Forwarded-email intake may be added later without granting inbox
access.

### 6.5 Checkout, confirmation, and account

Use hosted checkout. The pre-checkout page repeats:

> Paperboy Personal · $12/month
> 1–5 selected public repositories · one scheduled email

Do not hide the price behind account creation or add an account-creation wall
inside checkout.

Confirmation:

> **Your Repo Impact Brief is scheduled.**
> Paperboy will use {n} selected repositories and send to {email} on {days} at
> {time} {time zone}.
> **Review setup**

Only show this after payment and schedule creation both succeed. Otherwise:

> **Payment succeeded, but scheduling needs attention.**
> No brief has been promised yet. Review delivery settings to finish setup.
> **Finish setup**

The compact account page shows:

- Subscription status
- Next verified scheduled run
- Selected repositories
- Focus summary
- Delivery email/time/time zone/days
- GitHub connection status and exact permissions
- Billing actions
- Privacy, retention, deletion, disconnect, and account controls

Disconnect confirmation:

> **Disconnect GitHub?**
> New repository ingestion will stop and scheduled briefs will pause. Billing
> and deletion are separate controls.
> Keep connected · Disconnect GitHub

Billing states:

| State | Message | Primary action |
|---|---|---|
| Checkout incomplete | “Finish payment to activate scheduled delivery.” | Finish payment |
| Active | “Your subscription is active.” | Manage billing |
| Processing | “Payment is processing. We will update this page when it settles.” | Refresh |
| Past due | “Payment needs attention. Delivery is paused until billing recovers.” | Update payment |
| Cancel scheduled | “Your subscription ends on {verified date}.” | Keep Paperboy |
| Canceled | “Hosted delivery is off. Data follows the retention policy below.” | Restart |
| Unavailable | “Billing details are unavailable. No new charge was started here.” | Try again |

Cancellation must use the provider's verified effective date. Canceling,
disconnecting GitHub, deleting derived context, and deleting the account are
four distinct actions.

### 6.6 Email brief: the MVP product surface

Subject:

> Paperboy · {n} changes worth checking for your repos

Preheader:

> Repo Impact Brief for {repo list or “your selected repositories”}

Header:

> PAPERBOY · REPO IMPACT BRIEF
> **{localized long date}**
> {n} items across {m} selected repositories

Each item:

> {SOURCE TYPE} · {score}/10 · {repository}
> **{headline}**
> **Why it may matter**
> {grounded reason}
> **Inspect next**
> {concrete, non-autonomous next check}
> View source evidence

Footer:

> You received this because Paperboy is scheduled for {days} at {time zone}.
> Change repositories · Change delivery · Pause Paperboy · Manage billing

Use “may” for inferred impact. Every item includes a source link. Do not put
Approve, Run, Create issue, Open PR, or affiliate links in the MVP email.

## 7. Text wireframes

Landing:

~~~text
┌ paperboy ─── How it works ─ Pricing ─ GitHub ─ Sign in ─ [Start] ┐
│ REPO IMPACT BRIEF                                                │
│ Wake up to the changes that matter to your code.                 │
│ [Start — $12/month]  View the open-source project                │
│ Read-only · 1–5 public repos · one scheduled email               │
├──────────────── example Repo Impact Brief ───────────────────────┤
│ score · source · repo · headline                                 │
│ Why it may matter                                                │
│ Inspect next                                        [Evidence]   │
├ repos ●──────── relevance ●──────── evidence ●──────── email ✓ ──┤
│ exact permission explanation                    GitHub proof     │
├ Paperboy Personal · $12/month                         [Start]     │
│ Free self-hosted alternative · Open on GitHub                     │
└ FAQ ──────────────────────────────────────────────────────────────┘
~~~

Onboarding:

~~~text
┌ paperboy                                          Save and exit  ┐
│ Repositories ●──────── Focus ○──────── Delivery ○                │
│ SETUP 1 OF 3                                                     │
│ Choose the public repositories Paperboy may read.                │
│ [exact read-only explanation]                [Connect GitHub]    │
│ Search public repositories                     Selected only     │
│ □ org/api-evals       □ org/agent-core       □ org/toolkit       │
│ 3 of 5 selected                         [Use 3 repositories]     │
└───────────────────────────────────────────────────────────────────┘
~~~

Email:

~~~text
┌ PAPERBOY · REPO IMPACT BRIEF · JULY 16                           ┐
│ 4 items across 3 selected repositories                           │
├ RESEARCH · 8/10 · api-evals ─────────────────────────────────────┤
│ Headline                                                         │
│ Why it may matter                                                │
│ Inspect next                                      [View evidence]│
├ NEWS · 7/10 · agent-core ────────────────────────────────────────┤
│ Headline                                                         │
│ Why it may matter                                                │
│ Inspect next                                      [View evidence]│
├ Change repositories · Change delivery · Pause · Billing          │
└───────────────────────────────────────────────────────────────────┘
~~~

Account:

~~~text
┌ paperboy                                      account@example.com┐
│ Paperboy Personal · Active                    [Manage billing]    │
│ Next run: verified date/time                                      │
├ Repositories (3/5)                               [Change]         │
├ Focus                                               [Edit]       │
├ Delivery · email · days · time zone                 [Edit]       │
├ GitHub · connected · read-only                 [Disconnect]      │
├ Privacy · retention · delete controls               [Open]       │
└───────────────────────────────────────────────────────────────────┘
~~~

## 8. Existing dashboard component map

The current static dashboard is valuable as an information hierarchy, not an
MVP route. Reuse its primitives in the email template, landing example, and
future dashboard.

| Existing element | Productized component | MVP destination/change |
|---|---|---|
| header/subtitle | BriefHeader | Email date, selected-repo count |
| meta | BriefSummary | Real item/repo counts, no fake activity |
| toolbar | StatusFilter | Deferred dashboard only |
| note | GuardrailNotice | Permission and “no autonomous action” copy |
| grid | SignalList | Single-column email/preview, never dense tiles |
| card | ImpactItem | Source, repo, score, reason, next inspection, evidence |
| card-top | ImpactItemHeader | Preserve title/score separation |
| title | ImpactTitle | Newsreader in email, Plex Sans in dense lists |
| score | RelevanceScore | Accessible “8 out of 10” label |
| source code line | SourceMeta | Source type, public repo, timestamp |
| why | WhyItMayMatter | Keep visible and use calibrated “may” |
| action callout | InspectNext | Non-autonomous inspection step |
| actions | DecisionBar | Deferred; excluded from MVP email |
| approve/dismiss | ReviewControls | Deferred; no autonomous action |
| status-pill | StatusBadge | Account/setup/billing states |
| empty | EmptyState | First run, no impact, source failure |
| footer | BriefFooter | Delivery/settings/billing links |
| inline QUEUE | ExampleBriefFixture | Landing/demo only, visibly labeled |
| esc function | SafeText renderer | Preserve escaping; no trusted source HTML |
| render/filter | Tenant data adapter | Deferred web view, tenant scoped |

New MVP components:

- MarketingHeader, DeliveryRoute, ExampleBrief, PricingCard
- MagicLinkForm, ConsentScopeCard, PublicRepositoryPicker
- SetupStepper, RepoFocusEditor, SchedulePicker, BriefPreview
- CheckoutSummary, SetupConfirmation, AccountStatusCard
- ConnectionCard, BillingStatusCard, PrivacyControls
- EmailBrief, ImpactItem, EvidenceLink
- Skeleton, InlineError, ErrorSummary, ConfirmScopeDialog

## 9. Interaction, responsive, and accessibility rules

- One filled primary action per viewport.
- Buttons press down one pixel and scale to 0.98 for 100 milliseconds.
- Delivery route draws once; it never loops.
- Repository count updates immediately and is announced in an aria-live polite
  region.
- Source/repository removal names its scope and effect before confirmation.
- Use layout-matched warm skeletons; spinner only inside a labeled button.
- Do not animate score, price, or counts like live demand.
- Respect prefers-reduced-motion.
- Design from 320 pixels; breakpoints 640, 768, 1024, 1280.
- Mobile padding 16 pixels; desktop 32 pixels.
- Every target at least 44 by 44 pixels with 8 pixels between targets.
- Repository picker is full-screen on mobile with sticky selected-count footer.
- Email width no more than 640 pixels and readable with images disabled.
- Meet WCAG 2.2 AA; color always paired with icon/text.
- Focus: three-pixel signal ring with two-pixel paper offset.
- Scores expose “8 out of 10”; headings and landmarks are semantic.
- Validate on blur and submit, preserve paste, link field errors to a summary.
- Escape closes modal/drawer only if focus returns to its trigger.
- Critical email meaning must not depend on CSS background images or webfonts.

## 10. Empty, loading, error, and revocation states

| Context | Exact copy | Action |
|---|---|---|
| No repo selected | “Choose at least one public repository.” | Choose repositories |
| Sixth repo | “The MVP supports up to five repositories.” | Remove one |
| First run pending | “Your first Repo Impact Brief is being prepared.” | Review setup |
| Nothing meets bar | “Nothing cleared your relevance bar today. Your sources still ran.” | Edit focus |
| No prior delivery | “Your delivery history starts after the first scheduled brief.” | View schedule |
| GitHub failed | “GitHub did not finish connecting. No repository was selected.” | Try again |
| Repo refresh failed | “Paperboy could not refresh {repo}. Last successful context: {time}.” | Retry |
| Brief generation failed | “Today's brief could not be completed. No email was sent.” | Retry |
| Email failed | “The brief was created but email delivery failed.” | Retry delivery |
| Auth expired | “Your session expired before this change was saved.” | Sign in |
| Billing unavailable | “Billing details are unavailable. No new charge was started.” | Try again |

Privacy/revocation:

- Email sign-in does not grant inbox access; no Gmail OAuth.
- GitHub consent is separate from identity and limited to selected public repos.
- Removing a repo stops future ingestion for it.
- Revoking GitHub stops all new repo ingestion and pauses future briefs.
- The account must show connected identity, verified scope, selected repos,
  last sync, retention, processing/provider summary, and deletion controls.
- If retention/provider behavior is unknown in staging, show “Policy not
  configured,” not reassurance.
- Disconnect, delete derived context, cancel billing, and delete account remain
  separate.

## 11. Post-MVP reference states — do not build in MVP

If evidence shows users need a web reading/review surface, introduce:

- Today: run/delivery state, impact items, and source health
- Digest detail/archive: email-equivalent item groups and evidence drawers
- Review queue: pending, approved, dismissed; approval records a decision only
- Source controls: public repos, news, research, focus, and delivery

Post-MVP card copy:

> {SOURCE} · {score}/10 · {repo}
> **{headline}**
> **Why it may matter**
> {reason}
> **Inspect next**
> {step}
> View evidence · Approve · Dismiss

Guardrail:

> Approval records your decision. It does not change code or start work unless
> a separately configured worker explicitly supports that action.

This reference satisfies future dashboard/digest/source-control planning
without changing the PMF-validated email-first scope.

## 12. Acceptance checklist and build order

Landing:

- Paid wedge reads as Repo Impact Brief, not generic newsletter.
- $12 hypothesis is visible before sign-in.
- Demo is labeled; GitHub/open-source proof is reachable.
- No unsupported proof, urgency, affiliate, or autonomous-action claim.

Sign-in/consent:

- Email identity and GitHub data access are separate.
- Read-only/public/1–5 boundaries appear before authorization.
- Exact verified GitHub scope is visible and reversible.

Onboarding:

- Setup requires no YAML, environment variables, Gmail OAuth, or dashboard.
- Repositories, focus, schedule, delivery, and price are reviewable.
- Demo preview is distinguished from live output.

Email/account:

- Each item answers source, repo, score, why it may matter, inspect next, and
  evidence.
- Account shows verified schedule, repo selection, connection, privacy, and
  billing state.
- Canceling does not imply data deletion; disconnecting does not imply cancel.

Build order:

1. Tokens, typography, buttons, fields, notices, badges
2. EmailBrief and ImpactItem using the existing public fixture shape
3. Landing with the real example
4. Email magic-link sign-in
5. GitHub consent and 1–5 public-repository picker
6. Three-step onboarding shell and preview
7. Hosted checkout handoff
8. Confirmation/account/privacy/billing states

Golden path:

> Landing → price understood → email sign-in → read-only GitHub scope
> understood → 1–5 public repos selected → focus saved → schedule chosen →
> payment handoff → confirmation → first Repo Impact Brief email.

First usability test:

1. Can a solo builder explain the Repo Impact Brief before scrolling to price?
2. Can they accurately state what GitHub access permits?
3. Do they understand that email, not a dashboard or autonomous agent, is the
   MVP product?
