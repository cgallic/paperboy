# Paperboy product strategy

**Decision date:** 2026-07-16

**Active offer:** Card-required seven-day trial, then **$5/month** until canceled.

**Product:** Working hosted self-serve daily or weekly rollup at `https://newpaperboy.com/`.

**Acquisition option:** Keep the self-hosted/open-source project free.

## Product truth

Paperboy lets a user choose up to six public RSS or Atom feeds, describe what matters and what to ignore, select daily or weekly delivery, confirm their email, and receive an automatically ranked and deduplicated rollup. The live product includes feed validation, bounded scans, secure management links, scheduled email delivery, unsubscribe handling, Stripe Checkout/portal/webhook code, privacy, terms, and consent-based analytics.

Paperboy does not connect to Gmail or read an inbox. It is self-serve and does not include installation, research, or consulting labor.

## Initial customer

Start with technical founders and hands-on product or engineering leads who already monitor several public sources and can describe a concrete relevance filter. The strongest trigger is not general curiosity; it is repeatedly missing an API, pricing, dependency, research, or product change that affects active work.

Exclude general-news readers, teams requiring private-source access, and enterprise buyers needing SSO, procurement, team administration, or compliance guarantees.

## Positioning

**Build your firehose. Read only what matters.**

The user controls the source list and relevance instructions. Paperboy produces a short, source-linked edition instead of another chronological inbox. Lead with this visible mechanism, not unsupported productivity or revenue claims.

## Packaging

| Plan | Price | Purpose |
|---|---:|---|
| Paperboy OSS | Free | Acquisition, trust, and a buyer-managed self-hosted path |
| Paperboy hosted | Seven-day card-required trial, then `$5/month` | Primary commercial offer with automatic daily or weekly delivery and self-service management |

Do not create a one-time Starter Pack or a managed setup offer. Do not publish a separate Affiliate Factory page over the working application.

## Funnel

1. Visitor sees the filtered-firehose promise and product boundaries.
2. Visitor enters an email, sources, focus, ignore terms, and timezone.
3. Paperboy validates the public feeds and shows a ranked first cut.
4. Visitor explicitly confirms through the emailed double-opt-in link.
5. Verified user starts Stripe-hosted checkout and the seven-day trial.
6. A successful webhook activates the selected scheduled delivery.
7. Management, billing portal, unsubscribe, and suppression flows retain user control.

## Measurement

Track these as separate events and cohorts:

- qualified landing session;
- setup start and valid subscription request;
- email confirmation;
- checkout start and Stripe redirect;
- successful webhook and trial activation;
- first successful delivery;
- open/click only when consented;
- trial-to-paid conversion;
- renewal, payment failure, cancel, unsubscribe, bounce, and suppression.

Do not call setup attempts, email rows, or shared Stripe revenue Paperboy customers or revenue without product-level mapping.

## Launch gate

Production billing remains disabled until a recurring `$5/month` Stripe price is selected and these values are configured:

- `PAPERBOY_STRIPE_SECRET_KEY`
- `PAPERBOY_STRIPE_PRICE_ID`
- `PAPERBOY_STRIPE_WEBHOOK_SECRET`

After configuration, run an authorized checkout, webhook, portal, cancel, and delivery smoke before traffic. Deploy price and canonical-domain changes from current Paperboy main through the existing application release path.

## First growth loop

Use the free repository, existing technical content, and already-live fleet distribution to send qualified users into the live setup flow. Publish examples that start from a real public-source bundle and a specific relevance filter. Measure which source/focus combinations verify, start trials, and receive a first successful edition. Expand only from retained cohorts; do not compensate for an unverified billing funnel with more page volume.
