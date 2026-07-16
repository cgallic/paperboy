# Paperboy Filtered Firehose — validation surface

This self-contained product surface is deployed at
`https://paperboy.kaibuilds.com/`.

The primary flow is real, bounded product behavior:

- choose a Hacker News, arXiv AI, or GitHub Blog preset, or paste public RSS/Atom feed URLs;
- describe what should make an item relevant and optionally name noise to ignore;
- call the same-origin `/api/firehose/subscribe` endpoint once;
- validate and safely fetch up to six public feeds;
- persist the email, source list, relevance filter, and automatic delivery state;
- scan, filter, rank, deduplicate, and source-link the recent items;
- render the first cut when returned; and
- expose tokenized in-page status and unsubscribe controls.

The page only shows **Your daily brief is active** after the subscription API
confirms `{ok: true, status: "subscribed"}`. A validation or persistence error
keeps the form visible and never claims delivery was activated. Campaign
attribution is sent with the subscription request, so there is no separate lead
or human-follow-up step.

## Product boundary

The automatic subscription supports public RSS and Atom feeds. It does not
connect to an inbox or auto-subscribe a user to email-only newsletters. No card
or payment is collected during launch. The existing setup/account/checkout
routes remain clearly labeled local fixture previews and are not linked from
the primary live flow.

## Serve locally

Run the API from the repository root so `/api/firehose/subscribe` is available:

```powershell
pip install -e ".[all]"
python -m uvicorn paperboy.api.main:app --reload --port 4173
```

Then open `http://127.0.0.1:4173/`.

## Static and browser checks

```powershell
node --check product/app.js
node product/check.mjs
python tests/product_ui_smoke.py
git diff --check
```

## Golden path

1. Open the landing page and select **Start my daily brief**.
2. Enter the email where the daily brief should be delivered.
3. Choose one quick-start feed or paste up to six public RSS/Atom feed URLs.
4. Describe what should make an item relevant.
5. Optionally provide comma-separated ignore terms.
6. Activate the filter and inspect the first ranked, source-linked results.
7. Use the returned management controls to refresh status or unsubscribe.

## Acceptance checklist

- [ ] Hero positions Paperboy as a personal relevance filter, not a newsletter summarizer.
- [ ] The many-inputs-to-few-signals transformation is visible above the fold.
- [ ] Every primary CTA says **Start my daily brief**; the header CTA is visually secondary.
- [ ] Public-feed presets and a direct URL intake are available.
- [ ] Input rejects missing email, feeds, or relevance focus before network calls.
- [ ] `/api/firehose/subscribe` is same-origin, bounded, and rejects private/non-public destinations.
- [ ] Per-source failures do not discard valid feed results.
- [ ] Preview items include title, source, score, relevance explanation, and original URL.
- [ ] Success is rendered only after the API confirms an active subscription.
- [ ] Successful subscriptions persist email, source URLs, focus, ignore terms, and attribution.
- [ ] Tokenized status and unsubscribe actions work in-page without exposing tokens in copy.
- [ ] Copy never claims Gmail access, automatic email-only newsletter subscription, or live billing.
- [ ] Desktop and mobile flows complete without horizontal overflow.
- [ ] Keyboard focus, labels, errors, reduced motion, target size, contrast, and typography pass the implemented Design OS floor.
