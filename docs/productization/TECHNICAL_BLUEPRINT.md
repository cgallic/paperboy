# Paper Boy subscription technical blueprint

Status: implementation-ready architecture, no application code changed  
Authority: [`cgallic/paperboy`](https://github.com/cgallic/paperboy) at `526ae15`  
Verified: 2026-07-16

## Executive decision

Productize one narrow loop:

> Forward useful email and connect selected GitHub repositories. Paper Boy
> turns the highest-signal changes into one scheduled email and a reviewable
> blackboard. Nothing acts on the user's accounts.

The smallest paid boundary is a hosted, single-owner workspace with:

1. passwordless sign-in;
2. a private inbound email address (forwarding, not Gmail OAuth);
3. an optional read-only GitHub App installed on selected repositories;
4. a timezone, delivery time, and short interest profile;
5. one daily email plus a blackboard of the same ranked items;
6. approve, dismiss, and useful/not-useful feedback; and
7. subscription and retention limits enforced on the server.

RSS and research-paper discovery remain useful, but as a shared public catalog
that enriches the private email/GitHub digest. The action queue remains a human
review surface. Affiliate/referral mechanics, a general personal knowledge
graph, agent execution, Gmail-wide access, team collaboration, and repository
write operations are outside the first subscription boundary.

This is a hosted product alongside the existing self-hosted edition. Do not
break the local SQLite/systemd workflow to make the SaaS work.

## What exists today

### Repository and public project state

The GitHub repository is public, MIT licensed, and contains five commits. It
has one unprotected `main` branch, no public issues, releases, GitHub Actions
workflows, or GitHub deployments. The latest product change is the file-first
action queue demo from 2026-06-02 plus a one-line dedup guard. There is no
evidence in this repository of a running hosted Paper Boy service.

The project began as `openbrain`, was renamed to Paper Boy because it delivers
a curated morning paper, and was then corrected to identify
[`cgallic/open-brane`](https://github.com/cgallic/open-brane) as the owner of
the event-log schema. Open-brane is a related dependency/pattern source, not
the Paper Boy product boundary.

### Current capability map

| Capability | Current implementation | Runtime/state |
|---|---|---|
| Public news ingest | `paperboy/scanners/news_opinion.py` | Fetches RSS/Atom, asks Ollama for a short question, writes `pattern-scan/question` |
| Research ingest | `paperboy/ingest/research_papers.py` | Pulls arXiv, Hugging Face Daily Papers, and Semantic Scholar; canonicalizes and merges papers |
| Personal relevance scoring | `paperboy/score/research_papers.py` | Injects `research-interests.md` into a local Ollama prompt and stores strict-ish JSON verdicts |
| Paper promotion | `paperboy/scanners/papers_to_prompts.py` | Promotes recent 7+ papers to the prompt stream |
| Topical prompts | `paperboy/scanners/topical_questions.py` | Rotates questions from a Markdown topical map |
| Daily carry-overs | `paperboy/scanners/today_briefing.py` | Parses one local daily-brief Markdown file |
| Morning digest | `paperboy/digest/prompt_digest.py` | Weights streams by freshness and posts up to 12 items to Discord |
| Research digest | `paperboy/digest/research_digest.py` | Posts recent high-scoring papers to Discord |
| Blackboard seed | `paperboy/digest/action_queue.py` | Appends stable action items to JSONL and renders Markdown; never executes them |
| Delivery | `paperboy/discord_post.py` | Discord bot first, webhook fallback |
| State | `paperboy/db.py`, `paperboy/stream_common.py` | One local SQLite file with `events` and `event_tags` |
| Scheduling | `systemd/*` | Eight independent one-shot timer/service pairs on one Linux host |
| Install | `scripts/bootstrap.sh` | Root-only venv/config/systemd installer |

Current runtime topology:

```text
RSS/arXiv/HF/S2/config files
            |
       8 systemd timers
            |
       Python CLI modules ----> local Ollama
            |
        events.db (SQLite)
            |
       digest selectors
          /       \
     Discord    JSONL/Markdown blackboard demo
```

There is no email ingestion or email delivery. There is no GitHub API
connector in Paper Boy. `open-brane/scripts/ingest_git.py` is a local-path
`git log` adapter, not a hosted GitHub connector. Paper Boy's roadmap lists a
Gmail adapter as **not shipped**.

### Current data contract

Paper Boy mirrors the open-brane event shape:

```text
events(id, ts, source, type, actor, payload_json, attachment_uri, ingested_at)
event_tags(event_id, tag)
```

`actor` is used as an application-level dedup key. Prompt actors are
`<stream>:<sha1[:12]>`; papers use an arXiv/DOI/HF/URL canonical ID. The
database does not enforce uniqueness on `(source, type, actor)`, so concurrent
writers can still create duplicates.

### Baseline checks run for this blueprint

- `python -m compileall -q paperboy`: pass.
- `python -m paperboy.digest.action_queue --dry-run`: pass, fixture fallback,
  seven candidates, zero writes.
- There is no automated test suite to run.

### Gaps and contradictions to fix before relying on the self-hosted path

These are not reasons to redesign the whole product, but they are evidence
that the current installer/runtime should not become the SaaS control plane:

1. The docs say “seven” cron jobs in places, but eight timers are installed.
2. The bootstrap script seeds config under `/etc/paperboy`, while the Python
   defaults do not search that directory. The environment file contains the
   necessary overrides only as comments.
3. The bootstrap test command uses `sudo -u paperboy`, but the script does not
   create that user and the service units do not set `User=paperboy`.
4. Idempotency is check-then-insert in Python without a unique constraint.
5. `update_payload()` and research feed merging mutate existing event rows even
   though the architecture is described as append-only.
6. `--retry-scored` recomputes a verdict, but `write_event()` returns the
   existing score event rather than persisting a new score version.
7. Independent timers and `After=` ordering do not create a durable job DAG;
   a slow upstream run can race a downstream timer.
8. The action queue defaults its fixture and output to the same demo JSONL.
   Its dashboard buttons are a preview, not persisted workflow state.
9. Network and LLM calls, selection, persistence, and delivery are coupled in
   CLI entry points, making isolated retries difficult.

## Reuse versus build

### Reuse after extracting pure functions

- Paper canonicalization and source merging from
  `ingest/research_papers.py`.
- RSS/Atom parsing and public-source configuration.
- Research verdict normalization and the interests-grounded scoring contract.
- Prompt stream weights, freshness ranking, and digest formatting semantics.
- Paper/prompt-to-action synthesis from `digest/action_queue.py`.
- Discord as an optional secondary delivery adapter.
- The event vocabulary and stable external-key discipline.
- Fixture data for onboarding previews and contract tests.

Preserve these semantics behind interfaces. They should not know whether the
backing store is SQLite or Postgres, or whether the model is Ollama or a hosted
provider.

### Reuse only as a compatibility adapter

- Keep `paperboy.db` for the self-hosted edition.
- Allow export/import between hosted workspace events and the open-brane event
  shape.
- Reuse open-brane's `git` event vocabulary, but not its local-path adapter for
  a GitHub SaaS integration.
- Reuse open-brane's secret/payload policy ideas. Do not make open-brane a
  runtime dependency for the subscription product.

### Build for the hosted product

- tenant-aware Postgres schema and row-level authorization;
- authentication, workspaces, and onboarding state;
- Stripe customer/subscription/entitlement synchronization;
- signed inbound-email and GitHub webhook ingress;
- GitHub App token handling and backfill;
- durable jobs, attempts, cursors, digest runs, deliveries, and feedback;
- email renderer/delivery adapter;
- persisted blackboard state;
- privacy controls, audit log, deletion/export, CI, and deployment runbooks.

### Do not reuse

- systemd timers as the hosted scheduler;
- one SQLite file shared across customers;
- local Markdown files as tenant configuration;
- a customer's local checkout as the GitHub data source;
- manual JSONL edits as workflow state;
- Discord credentials as the primary onboarding path;
- direct caller access to provider tokens or the database service role.

## Recommended hosted architecture

Use a deliberately small two-runtime system:

1. **Web/control plane:** Next.js on Vercel for auth screens, onboarding,
   blackboard, settings, Stripe/GitHub callbacks, and fast webhook ingress.
2. **Data/auth:** Supabase Auth + Postgres. Every tenant-owned table has
   `workspace_id`, RLS, and indexes beginning with `workspace_id`.
3. **Worker:** one containerized Python worker deployment using the existing
   `paperboy` package. It claims durable Postgres jobs, runs ingest/scoring/
   render/delivery stages, and can scale horizontally later.
4. **Queue/scheduler:** Postgres first. A one-minute scheduler loop guarded by
   a Postgres advisory lock creates due jobs. Workers claim with
   `FOR UPDATE SKIP LOCKED`. Do not add Redis/Celery for the pilot.
5. **Billing:** Stripe Checkout + Billing Portal + signed webhooks. Stripe is
   payment truth; the app persists a local entitlement projection.
6. **Email:** provider-agnostic signed inbound webhook and transactional
   outbound API. Keep the adapter boundary narrow enough to change providers.
7. **GitHub:** one public GitHub App with read-only installation permissions.
8. **LLM:** a provider interface. Hosted inference is the default in SaaS;
   Ollama remains the self-hosted adapter. Deterministic filtering happens
   before model calls.

```text
 Browser
   |
   v
 Next.js control plane ---------------> Supabase Auth
   |      |       |
   |      |       +-------------------> Stripe Checkout/Portal
   |      |
   |      +-- signed webhook ingress <-- GitHub App / inbound email / Stripe
   |                    |
   +--------------------v
                    Postgres
         receipts / jobs / tenant data / runs
                         |
                   Python workers
            ingest -> score -> render -> deliver
               |         |                   |
          GitHub API   LLM adapter      outbound email
                         |
             persisted digest + blackboard
```

Why two runtimes: the user-facing control plane benefits from the existing
web/auth/billing ecosystem, while Paper Boy's long-running Python and LLM jobs
do not fit a serverless request lifecycle. The boundary is Postgres rows, not
an internal HTTP maze.

If the team already has a preferred hosted Postgres/auth or container vendor,
swap vendors without changing the contracts below. The important decisions
are tenant-keyed Postgres, a durable worker, and signed asynchronous ingress.

## Product and tenancy boundary

Use a `workspace` even for the single-user pilot. It prevents a painful schema
rewrite when a second owner or assistant is added. Launch supports one owner
membership; the role model is present but invitations are not.

Separate data into two planes:

- **Global public catalog:** RSS stories and public research papers. Fetch once,
  dedupe once, and score cheaply before applying workspace-specific relevance.
- **Private workspace events:** forwarded email and selected-repository GitHub
  activity. Never share candidates, embeddings, prompts, or outputs between
  workspaces.

Do not sell “an AI brain.” Sell the scheduled paper and blackboard. A digest
item may propose an action, but Paper Boy cannot send email on the user's
behalf, modify a repository, open an issue, or invoke an agent in the first
subscription release.

## Authentication, billing, and entitlements

### Authentication and authorization

- Default sign-in: email magic link.
- Optional GitHub sign-in may be added for convenience, but login identity and
  GitHub App installation are separate records and separate consent steps.
- Browser sessions carry user identity only. Workspace access is resolved
  through `workspace_members` on every request.
- Use Postgres RLS on every exposed tenant table. Authorization data belongs
  in server-controlled membership rows/app metadata, not mutable user metadata.
- Worker/service credentials bypass RLS only in server processes; never expose
  the Supabase service role to the browser.
- Require recent authentication for connector removal, data export/deletion,
  billing-email change, and ownership transfer.

Supabase's current guidance supports RLS keyed by authenticated user identity;
views exposed to clients must use `security_invoker` or remain in an unexposed
schema: [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security).

### Billing source of truth

- Checkout creates or reuses one Stripe customer per workspace.
- Store Stripe IDs, never card data.
- Verify and dedupe every Stripe webhook by provider event ID.
- Project `customer.subscription.*`, invoice/payment failures, and
  `entitlements.active_entitlement_summary.updated` into local subscription
  and entitlement rows.
- Gate capabilities on the local entitlement projection, not on a price ID in
  browser state. Stripe recommends persisting active entitlements for fast
  resolution: [Stripe Entitlements](https://docs.stripe.com/billing/entitlements).
- Permit a short, explicit payment-failure grace period. During grace, existing
  digests may deliver but new connectors/manual runs cannot be added. After
  grace, pause schedules without deleting data.
- Cancellation keeps access through `current_period_end`; deletion follows the
  user's retention/deletion choice, not cancellation itself.

Suggested entitlement keys (pricing determines values, not the code):

```text
digest.daily
digest.manual_runs_per_day
connector.email_inbound
connector.github
connector.github_repo_limit
retention.private_days
delivery.email_recipient_limit
blackboard.feedback
```

Check entitlements at connector installation, backfill enqueue, manual-run
creation, scheduler enqueue, and delivery. UI hiding alone is not enforcement.

## Onboarding state machine

```text
account_created
  -> email_verified
  -> workspace_created
  -> interests_saved
  -> inbound_alias_ready
  -> sample_digest_ready
  -> github_connected (optional)
  -> schedule_confirmed
  -> active
```

The first-value path must not wait for private data or external writes. Render
a clearly labeled sample from bundled/public fixtures as soon as interests are
saved. Then give the user a unique forwarding address and optional GitHub App
install. Activation requires a verified delivery address, timezone, local
delivery time, and at least one source (forwarding enabled, selected GitHub
repo, or public catalog opted in).

Persist each step and its timestamp. Onboarding is resumable; callbacks never
infer the next screen from query strings alone. A connector becomes `active`
only after a signed test event or successful read-only backfill.

## Email connector and delivery permissions

### Launch: forwarding address, not Gmail OAuth

Provision an address such as `<random-alias>@in.paperboy.example`. The inbound
provider validates the recipient and POSTs a signed payload. Paper Boy:

1. verifies the provider signature against the raw request;
2. stores a deduped receipt;
3. accepts only an active alias belonging to a workspace;
4. strips scripts, tracking pixels, remote images, and quoted reply history;
5. extracts sender, subject, sent time, text, and canonical links;
6. ignores attachments at launch; and
7. discards raw MIME after normalization (or within a short bounded retry
   window).

This needs no mailbox OAuth and cannot read unrelated mail. Paper Boy's
outbound credential is its own transactional-email key; it does not request
permission to send as the user.

### Later: direct Gmail sync

If PMF shows forwarding is the adoption blocker, add explicit Gmail sync as a
separate connector. Request only `gmail.readonly`, query an opt-in label, and
state plainly that the scope technically permits reading the mailbox even if
the product filters to that label. Google classifies `gmail.readonly` as a
restricted scope requiring restricted-scope verification:
[Gmail scope documentation](https://developers.google.com/workspace/gmail/api/auth/scopes).

Do not use Connor's domain-wide delegation setup as the multi-tenant product
transport. Do not request `gmail.modify`, `gmail.send`, or full `mail.google.com`
scope for the digest use case.

### Outbound digest

- Send only to a verified workspace delivery address.
- Include unsubscribe/manage-schedule links with short-lived signed tokens.
- Use a stable `Message-ID`/provider idempotency key per delivery row.
- Store rendered subject/text/HTML hashes and provider response ID, not
  invisible resend attempts.
- A retry reuses the stored rendered digest; it never re-scores or changes the
  edition being retried.

## GitHub connector permissions

Use a GitHub App, not user PATs and not local clones. Installation must default
to **selected repositories**.

Initial read-only repository permissions:

| Permission | Level | Why |
|---|---|---|
| Metadata | read (implicit/required) | Repository identity and installation mapping |
| Contents | read | Commit/backfill metadata and push/commit context |
| Pull requests | read | PR opened/merged/review activity |
| Issues | read | Issue opened/closed/comment activity if enabled |

Subscribe only to `installation`, `installation_repositories`, `push`,
`pull_request`, `issues`, `issue_comment`, and `release` initially. Actions/
workflow-run access is a later opt-in permission. Request no repository,
issue, PR, checks, actions, workflow, administration, members, or organization
write permission.

GitHub Apps start with no permissions and should request the minimum necessary:
[GitHub App permission guidance](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app).

Ingress requirements:

- Verify `X-Hub-Signature-256` with a constant-time comparison before JSON
  parsing.
- Use `X-GitHub-Delivery` as the webhook receipt dedup key.
- Return 2xx after durable receipt/enqueue, within GitHub's ten-second target;
  process asynchronously.
- Webhooks can arrive out of order. Use event timestamps and source IDs, not
  receipt order.
- Map installation ID and repository ID to an active workspace scope before
  storing normalized content.
- On installation removal, revoke locally immediately, cancel queued backfills,
  and stop new digest inclusion. Retained normalized events follow the user's
  retention setting.

See [GitHub webhook validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
and [webhook best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks).

The initial backfill is seven days of commits/PRs/issues for selected repos,
bounded by plan and a hard item cap. Store installation IDs; mint short-lived
installation tokens just in time. Do not store installation access tokens.

## Required Postgres model

Use UUID primary keys, `timestamptz`, JSONB only for source-specific payloads,
and explicit foreign keys. All private rows carry `workspace_id` even when it
is derivable; this makes RLS and deletion auditable.

### Identity and commercial state

```text
profiles(user_id, display_name, created_at)
workspaces(id, name, status, onboarding_state, created_at, deleted_at)
workspace_members(workspace_id, user_id, role, created_at)
subscriptions(workspace_id, stripe_customer_id, stripe_subscription_id,
              status, current_period_end, cancel_at_period_end, grace_until,
              updated_at)
entitlements(workspace_id, key, value_json, source_event_id, active_from,
             active_until, updated_at)
billing_webhook_receipts(provider_event_id UNIQUE, type, received_at,
                         processed_at, error_code)
```

### Connector and source state

```text
connections(id, workspace_id, kind, status, external_account_id,
            credential_ref, last_success_at, last_error_code, created_at,
            revoked_at)
connection_scopes(connection_id, external_scope_id, external_name,
                  enabled, metadata_json, UNIQUE(connection_id, external_scope_id))
inbound_addresses(id, workspace_id, local_token_hash UNIQUE, status,
                  created_at, revoked_at)
webhook_receipts(id, provider, provider_delivery_id, workspace_id,
                 connection_id, payload_ref_or_json, payload_hash,
                 received_at, processed_at, status, error_code,
                 UNIQUE(provider, provider_delivery_id))
ingest_cursors(connection_id, scope_key, cursor_json, updated_at,
               UNIQUE(connection_id, scope_key))
```

`credential_ref` points to an encrypted secret store/KMS envelope. Never place
refresh tokens, GitHub App private keys, webhook secrets, or provider API keys
in JSONB or client-readable tables.

### Content and preference state

```text
catalog_items(id, source, type, external_key, occurred_at, payload_json,
              content_hash, created_at, UNIQUE(source, type, external_key))
workspace_events(id, workspace_id, connection_id, source, type, external_key,
                 occurred_at, normalized_json, content_hash, sensitivity,
                 retention_until, created_at,
                 UNIQUE(workspace_id, source, type, external_key))
interest_profiles(id, workspace_id, version, text, structured_json,
                  active, created_at)
digest_preferences(workspace_id UNIQUE, timezone, local_time, weekdays,
                   public_catalog_enabled, quiet_day_behavior, schedule_version,
                   updated_at)
```

Keep the legacy Paper Boy `actor` as `external_key` during migration/export.
Do not copy the open-brane table unchanged: it lacks tenant isolation and
database-enforced idempotency.

### Work, digest, and feedback state

```text
jobs(id, workspace_id, kind, state, idempotency_key UNIQUE, payload_json,
     priority, available_at, attempt_count, max_attempts, lease_owner,
     lease_expires_at, last_error_code, created_at, updated_at)
job_attempts(id, job_id, attempt_no, started_at, finished_at, outcome,
             error_code, error_detail_redacted, metrics_json)
digest_runs(id, workspace_id, kind, local_date, period_start, period_end,
            schedule_version, interest_profile_version, state, candidate_hash,
            rendered_subject, rendered_text, rendered_html, created_at,
            completed_at,
            UNIQUE(workspace_id, kind, local_date, schedule_version))
digest_items(id, digest_run_id, source_kind, source_item_id, rank, score,
             reason, suggested_action, snapshot_json,
             UNIQUE(digest_run_id, source_kind, source_item_id))
deliveries(id, workspace_id, digest_run_id, channel, recipient_hash, state,
           provider_message_id, attempt_count, last_error_code, sent_at,
           UNIQUE(digest_run_id, channel, recipient_hash))
feedback(id, workspace_id, digest_item_id, user_id, signal, note, created_at,
         UNIQUE(digest_item_id, user_id, signal))
action_item_state(workspace_id, digest_item_id, state, decided_by, decided_at,
                  UNIQUE(workspace_id, digest_item_id))
audit_log(id, workspace_id, actor_type, actor_id, action, target_type,
          target_id, metadata_redacted, created_at)
```

Never put provider secrets or full raw email bodies in `jobs.payload_json`.
Jobs reference persisted rows by ID.

## API surface

User-facing endpoints (authenticated, workspace-authorized):

```text
POST   /api/workspaces
GET    /api/workspaces/:id/onboarding
PATCH  /api/workspaces/:id/interests
PATCH  /api/workspaces/:id/digest-preferences
GET    /api/workspaces/:id/connections
POST   /api/workspaces/:id/connections/github/install
DELETE /api/workspaces/:id/connections/:connection_id
POST   /api/workspaces/:id/digests/preview
GET    /api/workspaces/:id/digests
GET    /api/workspaces/:id/digests/:run_id
PATCH  /api/workspaces/:id/action-items/:digest_item_id
POST   /api/workspaces/:id/digest-items/:digest_item_id/feedback
POST   /api/workspaces/:id/billing/checkout
POST   /api/workspaces/:id/billing/portal
POST   /api/workspaces/:id/data-export
POST   /api/workspaces/:id/data-deletion
```

Server-only ingress/callbacks:

```text
GET/POST /api/callbacks/github/setup
POST     /api/webhooks/github
POST     /api/webhooks/inbound-email
POST     /api/webhooks/stripe
```

Webhook routes verify raw-body signatures, store a receipt, enqueue by stable
idempotency key, and return. They never call an LLM or provider API inline.

## Durable jobs and digest state

### Job lifecycle

```text
queued -> running -> succeeded
   |        |
   |        +-> retry_wait -> queued
   |        +-> dead
   +-> cancelled
```

Claim a job in one transaction. Set a lease owner/expiry. A crashed worker's
expired lease can be reclaimed. Retry network/429/5xx/timeouts with exponential
backoff, jitter, and provider `Retry-After`; do not retry validation, auth,
permission, or malformed-source errors without an external state change.

Default maximum: five attempts. A `dead` job keeps redacted diagnostics and
raises an operator alert. Replaying a dead job creates a new attempt on the
same job/idempotency key; it does not duplicate the source event.

Initial job kinds:

```text
parse_inbound_email
normalize_github_webhook
github_backfill_page
refresh_public_catalog
score_workspace_candidates
build_digest
deliver_digest_email
delete_workspace_data
export_workspace_data
```

Use separate concurrency pools inside the same worker deployment: ingress is
fast/high concurrency; LLM scoring is low concurrency and budgeted; delivery
is rate-limited by provider. Split deployments only after measurements show a
contention problem.

### Idempotency keys

| Operation | Key |
|---|---|
| Inbound email receipt | provider message/event ID; fallback hash of workspace + RFC Message-ID + body hash |
| GitHub webhook | `X-GitHub-Delivery` |
| GitHub normalized event | workspace + repo ID + event type + immutable source ID/version |
| Public catalog item | source + canonical URL/paper ID |
| Stripe webhook | Stripe event ID |
| Scheduled digest | workspace + local date + schedule version |
| Digest item | digest run + source kind + source row ID |
| Email delivery | digest run + channel + recipient hash |
| Manual preview | workspace + client request idempotency key |

Database unique constraints are the final authority. Application checks are
an optimization, not the guarantee.

### Digest lifecycle

```text
scheduled -> collecting -> scoring -> rendering -> ready -> delivering
                                                       |          |
                                                       |          +-> delivered
                                                       |          +-> partial
                                                       |          +-> failed
                                                       +-> skipped (quiet day/no candidates)
```

Each transition is compare-and-set from an allowed prior state and writes an
audit/attempt record. Candidate IDs and an input hash freeze the edition.
Delivery retries use the stored render. A schedule edit increments
`schedule_version`; it must not create two editions for the same intended
local date.

Candidate policy for the pilot:

1. collect private email/GitHub events in the run window and a bounded set of
   public catalog items;
2. deterministic dedup and source caps;
3. cheap rule/embedding prefilter;
4. workspace-grounded model scoring only on the bounded candidate set;
5. deterministic diversity/rank pass;
6. store reasons and source references;
7. render email and blackboard from the same `digest_items` rows.

This prevents “email says one thing, dashboard says another” and makes model
cost predictable.

## Privacy and security gates

1. **Least privilege:** forwarding alias first; selected-repo read-only GitHub
   App; no user-account write scopes.
2. **Tenant isolation:** RLS plus explicit workspace predicates in server
   repositories. Add automated cross-tenant negative tests for every table and
   endpoint.
3. **Secret handling:** provider secrets in managed secret storage; per-record
   connector credentials envelope-encrypted; short-lived GitHub installation
   tokens minted on demand; logs and job errors redacted.
4. **Webhook authenticity:** validate signatures on raw bytes before parsing;
   cap body size; persist delivery IDs; reject unknown installations/aliases.
5. **Untrusted content:** email, RSS, abstracts, issues, PRs, and comments are
   data, never instructions. Strip active HTML, cap fields, delimit content in
   model prompts, require structured outputs, and never let scoring invoke
   tools.
6. **SSRF:** launch does not accept arbitrary feed URLs. If custom feeds are
   added, resolve and block loopback/private/link-local addresses, restrict
   redirects, cap response size/time, and fetch from an isolated worker.
7. **Private-repo minimization:** ingest event metadata/body needed for the
   digest, not source files, diffs, secrets, Actions logs, or repository clones.
8. **Email minimization:** attachments off, remote content off, quoted-history
   stripping, normalized text retention bounded, raw MIME deleted promptly.
9. **Model disclosure:** tell users what fields reach the inference provider;
   use a no-training/no-retention contract where available; never mix tenant
   prompts or cache private outputs globally.
10. **Retention/deletion:** plan-backed default retention, per-workspace purge,
    disconnect behavior, export, and deletion job with an auditable tombstone.
    Backups age out on a documented schedule.
11. **Audit:** connector install/revoke, permission changes, billing state,
    exports/deletions, and admin access are immutable audit events.
12. **No action authority:** suggested actions are inert text. The blackboard
    can approve/dismiss for learning, but approval does not execute anything.

## Deployment and rollback

### Environments

- local: fixture providers, local Postgres/Supabase, fake clock;
- preview: web UI with fake providers and no external delivery;
- staging: separate Supabase project, Stripe test mode, GitHub test App,
  inbound/outbound provider test domain;
- production: isolated projects/secrets/domains and protected migrations.

Do not let preview deployments receive production webhooks or hold production
service-role credentials.

### Delivery order

1. apply backward-compatible migrations;
2. deploy web/ingress capable of writing the new shape;
3. deploy worker capable of reading old and new shapes;
4. enable the feature for an internal workspace;
5. enable scheduled jobs;
6. widen a workspace allowlist only after receipts, runs, and delivery proof.

All schema changes follow expand/migrate/contract. Destructive contract
migrations occur in a later release after old code and rows are gone.

### Rollback

- Web and worker deploy from immutable image/build hashes.
- Roll back code to the last known-good hash; do not reverse a destructive DB
  migration under incident pressure.
- Feature flags can independently pause inbound normalization, GitHub backfill,
  scoring, schedule creation, and email delivery.
- Stop new claims by pausing workers; leases expire safely.
- Reprocess from persisted webhook receipts/cursors and retry stored deliveries
  after recovery.
- Use managed Postgres point-in-time recovery and test restoration. A DB restore
  is a disaster-recovery action, not the normal replay mechanism.

Required operator views: queue depth/age, dead jobs, webhook signature failures,
connector error rate, LLM latency/cost, per-stage digest duration, scheduled vs
delivered count, duplicate suppression, and delivery bounce/complaint rate.

## Test and release gates

### Unit and contract tests

- canonical IDs, RSS/Atom parsing, GitHub/email normalization;
- score normalization, ranking, diversity, rendering, action synthesis;
- timezone/DST schedule calculation;
- legal/illegal job and digest state transitions;
- entitlement resolution and grace-period behavior;
- provider adapters against captured, sanitized fixtures;
- prompt-injection strings remain inert data.

### Database and concurrency tests

- migrations from empty and previous schema;
- RLS allow/deny matrix for owner, other tenant, anonymous, service role;
- duplicate webhook delivery under sequential and concurrent workers;
- worker crash after external success but before local commit;
- lease expiry/reclaim and max-attempt dead state;
- same workspace/local date scheduler race;
- deletion cascades and retention sweeper.

### Integration tests

- GitHub's published signature test vector and duplicate delivery ID;
- GitHub installation selected-repo mapping, revoke, and permission loss;
- signed inbound email, unknown alias, oversized body, HTML sanitization;
- Stripe test clock/webhooks for trial, active, past-due, grace, cancel, and
  entitlement change;
- outbound email provider idempotency, bounce, complaint, and retry;
- LLM timeout/invalid JSON/rate limit with deterministic fallback.

### End-to-end pilot gate

One test workspace must complete magic-link signup, sample digest, inbound
forward, selected-repo GitHub install, scheduled edition, email delivery,
blackboard rendering, feedback, billing activation/cancellation, connector
revoke, export, and deletion with pasted evidence. No “done” claim from UI
screens alone.

CI should run formatting/lint, type checks, unit/contract tests, migration/RLS
tests, and container build on every PR. Production deployment requires all
gates plus a successful staging smoke.

## Phased implementation slices

Each slice should be a reviewable PR with its own tests. Do not combine the
first live connector, billing, and worker rewrite into one release.

### Slice 0 — baseline truth and self-hosted safety

- Add CI and tests around current pure behavior.
- Document/fix timer count, config discovery, service user, and bootstrap smoke.
- Add database uniqueness or single-writer-safe semantics without breaking
  open-brane compatibility.
- Make score retry semantics versioned and explicit.

Exit: self-hosted install and dry-run are reproducible in CI/container tests.

### Slice 1 — pure domain package and provider contracts

- Extract source models, canonicalization, ranking, rendering, action synthesis,
  storage repository interfaces, clock, and LLM/delivery interfaces.
- Keep SQLite and Ollama adapters green.
- Add fake GitHub, inbound email, LLM, clock, and email-delivery providers.

Exit: a fixture edition renders deterministically without network or secrets.

### Slice 2 — hosted schema, auth, and sample onboarding

- Add Postgres migrations/RLS, worker job primitives, workspace/membership,
  interest/schedule forms, and persisted onboarding.
- Render a sample email/blackboard from fixture/public catalog data.
- No real billing or private connector yet.

Exit: two fixture users cannot read each other's rows; sample path is usable.

### Slice 3 — inbound forwarding and email delivery pilot

- Add signed inbound receipt/normalizer, unique aliases, retention, scheduled
  digest state machine, delivery records, and verified outbound recipient.
- Run in allowlisted internal workspaces with delivery feature-flagged.

Exit: forwarded message -> exactly one edition -> exactly one email and matching
blackboard, with duplicate/retry tests.

### Slice 4 — read-only GitHub App

- Add App install/setup, selected-repo scopes, signed webhooks, seven-day bounded
  backfill, cursoring, normalization, revoke/permission-loss behavior.

Exit: commits/PRs/issues from selected repos appear once; unselected repos and
other tenants never do.

### Slice 5 — subscriptions and entitlements

- Add Stripe Checkout/Portal/webhooks, local entitlement projection, server-side
  gates, grace/cancel flows, and billing audit events.

Exit: test-clock matrix proves provision, limit, grace, pause, resume, cancel.

### Slice 6 — private beta hardening

- Add export/deletion, monitoring/alerts, PITR restore drill, abuse/rate limits,
  bounce/complaint handling, cost caps, runbooks, and privacy/terms copy.
- Admit a small allowlist; measure activation, edition usefulness, connector
  failures, and marginal cost before adding plans/features.

Exit: operating review approves widening the allowlist.

### Explicitly later

- Gmail direct OAuth/restricted-scope verification;
- multiple members/roles/invitations;
- Slack/Discord delivery parity;
- repository Actions/workflow data;
- custom arbitrary feeds;
- semantic knowledge graph;
- affiliate/referral program;
- any agent or account write action.

## Safe work that can start now without secrets or external writes

1. Baseline tests and CI using current fixtures.
2. Pure domain/provider interface extraction while preserving CLI behavior.
3. Postgres migrations and RLS policies against local containers.
4. Job/digest state machines, fake clock, idempotency and crash tests.
5. Sanitized webhook contract fixtures and signature verification unit tests.
6. Static/on-local onboarding and blackboard UI against fixture APIs.
7. Sample digest renderer and email snapshots that write only local artifacts.
8. Docker image, health/readiness endpoints, migration checks, and deployment
   manifests with placeholder secret names.
9. Data inventory, retention matrix, threat model, and runbook drafts.

Do not register a GitHub App, create Stripe products, configure live webhooks,
send email, create production Supabase resources, or change DNS in this phase.
Those are external writes requiring explicit credentials and environment
authority.

## Suggested files for the implementation pass

```text
.github/workflows/ci.yml
Dockerfile
pyproject.toml

paperboy/domain/models.py
paperboy/domain/canonicalize.py
paperboy/domain/ranking.py
paperboy/domain/digest.py
paperboy/domain/actions.py
paperboy/providers/base.py
paperboy/providers/ollama.py
paperboy/providers/hosted_llm.py
paperboy/providers/email_delivery.py
paperboy/connectors/inbound_email.py
paperboy/connectors/github_app.py
paperboy/storage/base.py
paperboy/storage/sqlite.py
paperboy/storage/postgres.py
paperboy/jobs/models.py
paperboy/jobs/worker.py
paperboy/jobs/scheduler.py

apps/web/app/(auth)/*
apps/web/app/onboarding/*
apps/web/app/blackboard/*
apps/web/app/settings/*
apps/web/app/api/webhooks/github/route.ts
apps/web/app/api/webhooks/inbound-email/route.ts
apps/web/app/api/webhooks/stripe/route.ts
apps/web/lib/auth.ts
apps/web/lib/entitlements.ts
apps/web/lib/workspaces.ts

supabase/migrations/*_paperboy_core.sql
supabase/migrations/*_paperboy_rls.sql

tests/unit/*
tests/contracts/fixtures/*
tests/integration/test_idempotency.py
tests/integration/test_rls.py
tests/integration/test_digest_lifecycle.py
tests/e2e/*

docs/runbooks/deploy.md
docs/runbooks/rollback.md
docs/runbooks/dead-jobs.md
docs/runbooks/data-deletion.md
docs/security/threat-model.md
docs/security/data-inventory.md
```

File names can adapt to the chosen web scaffold, but the Python domain/provider
boundaries and database contracts should remain.

## Top technical risks

1. **Wrong product expansion:** turning a sharp digest into open-brane, a
   generic agent OS, or an affiliate factory delays the only loop that can be
   validated. Enforce the boundary in roadmap and permissions.
2. **Private-data trust:** email and private-repo activity are materially more
   sensitive than public RSS/papers. Least privilege, isolation, deletion, and
   clear inference disclosure are launch gates.
3. **Gmail verification trap:** direct Gmail access introduces a restricted
   scope and broad technical access. Forwarding avoids that until demand is
   proven.
4. **At-least-once duplication:** all three webhook providers and workers retry.
   Without database uniqueness and frozen digest/delivery rows, customers get
   duplicate items or email.
5. **LLM cost/latency fan-out:** scoring every source item for every workspace
   will erase small-subscription margins. Share public ingest, cap private
   candidates, prefilter deterministically, and meter model calls.
6. **Timer-to-job migration:** porting systemd scripts verbatim preserves
   hidden ordering and retry flaws. Extract stage contracts before parallel
   workers.
7. **Permission creep:** GitHub contents read can expose private code if the
   implementation starts fetching diffs/files. Enforce normalized event
   allowlists and tests, not only UI promises.
8. **Split-stack operational drag:** Next.js + Python + Postgres is justified,
   but additional brokers/services are not. Keep Postgres as the boundary until
   measured load requires more.

## Decisions to validate with PMF/design before live configuration

- Is “email” primarily inbound newsletters, outbound delivery, or both? This
  blueprint supports both and makes forwarding the lowest-permission input.
- Which GitHub events actually make a morning paper useful: commits only, or
  PR/issues/releases too?
- Is a no-source public sample sufficient to reach first value?
- Required private-data retention and whether users accept hosted inference.
- Trial/plan limits and quiet-day behavior.
- Whether blackboard approval is feedback only (recommended) or is expected to
  trigger work (explicitly excluded here).

None of these questions block the no-secret implementation work listed above.
