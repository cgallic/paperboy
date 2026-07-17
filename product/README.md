# Paperboy Filtered Firehose — validation surface

This self-contained product surface is deployed at
`https://newpaperboy.com/`.

The primary flow is real, bounded product behavior:

- choose a Hacker News, arXiv AI, or GitHub Blog preset, or paste public RSS/Atom feed URLs;
- describe what should make an item relevant and optionally name noise to ignore;
- call the same-origin `/api/firehose/subscribe` endpoint once;
- validate and safely fetch up to six public feeds;
- persist the email, source list, relevance filter, consent, time zone, and pending verification state;
- scan, filter, rank, deduplicate, and source-link the recent items;
- render the first cut when returned; and
- require an explicit confirmation POST from the emailed link;
- hand verified users to Stripe-hosted checkout; and
- expose tokenized in-page status and unsubscribe controls.

The subscription API first returns `{ok: true, status: "pending_verification"}`.
The page says **Check your email** and never claims delivery is active. The
emailed `?confirm=` link renders an explicit confirmation button; it does not
confirm on page load. After confirmation, the management screen requires hosted
checkout and only claims delivery is active when server billing status is
`trialing` or `active`.

## Product boundary

The automatic subscription supports public RSS and Atom feeds. It does not
connect to an inbox or auto-subscribe a user to email-only newsletters. The
live commercial offer is a card-required seven-day trial, then $5/month until
canceled. Card details remain on Stripe-hosted checkout. The existing
setup/account/checkout routes remain clearly labeled fixture previews and are
not linked from the primary live flow.

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
6. Request the subscription and inspect the first ranked, source-linked results.
7. Open the emailed link and explicitly confirm the address.
8. Start the card-required seven-day trial through hosted checkout.
9. Use the returned management controls to refresh status or unsubscribe.

## Acceptance checklist

- [ ] Hero positions Paperboy as a personal relevance filter, not a newsletter summarizer.
- [ ] The many-inputs-to-few-signals transformation is visible above the fold.
- [ ] Every primary CTA says **Start my daily brief**; the header CTA is visually secondary.
- [ ] Public-feed presets and a direct URL intake are available.
- [ ] Input rejects missing email, feeds, or relevance focus before network calls.
- [ ] `/api/firehose/subscribe` is same-origin, bounded, and rejects private/non-public destinations.
- [ ] Per-source failures do not discard valid feed results.
- [ ] Preview items include title, source, score, relevance explanation, and original URL.
- [ ] Pending requests render **Check your email** and never claim active delivery.
- [ ] Successful requests persist email, source URLs, focus, ignore terms, time zone, consent, and attribution.
- [ ] Confirmation requires an explicit POST and never exposes its token to analytics or lead capture.
- [ ] Daily delivery is called active only when billing status is `trialing` or `active`.
- [ ] Checkout accepts only a Stripe-hosted HTTPS URL and has a truthful unavailable state.
- [ ] Tokenized status and unsubscribe actions work in-page without exposing tokens in copy.
- [ ] Copy never claims Gmail access or automatic email-only newsletter subscription.
- [ ] Optional first-party analytics sends only consented, anonymous lifecycle events.
- [ ] Privacy and terms pages are linked from the footer.
- [ ] Desktop and mobile flows complete without horizontal overflow.
- [ ] Keyboard focus, labels, errors, reduced motion, target size, contrast, and typography pass the implemented Design OS floor.
