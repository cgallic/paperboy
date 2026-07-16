# Paperboy Filtered Firehose — validation surface

This self-contained product surface is deployed at
`https://paperboy.kaibuilds.com/`.

The primary flow is real, bounded product behavior:

- choose a Hacker News, arXiv AI, or GitHub Blog preset, or paste public RSS/Atom feed URLs;
- describe what should make an item relevant and optionally name noise to ignore;
- call the same-origin `/api/firehose/preview` endpoint;
- validate and safely fetch up to six public feeds;
- scan, filter, rank, deduplicate, and source-link the recent items; and
- render the strongest matches immediately in the browser.

On a KaiBuilds host, JavaScript also records the successful preview request in
the existing `/api/lead` queue with campaign attribution. The preview does not
depend on that capture call and still renders if lead persistence fails.

## Product boundary

The live preview supports public RSS and Atom feeds. It does not connect to an
inbox, auto-subscribe a user to email-only newsletters, persist per-user feed
registries, create accounts, schedule delivery, charge a card, or send the
daily edition. The existing setup/account/checkout routes remain clearly
labeled local fixture previews and are not linked from the primary live flow.

## Serve locally

Run the API from the repository root so `/api/firehose/preview` is available:

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

1. Open the landing page and select **Build my filter**.
2. Enter an email used for founding-pilot follow-up.
3. Choose one quick-start feed or paste up to six public RSS/Atom feed URLs.
4. Describe what should make an item relevant.
5. Optionally provide comma-separated ignore terms.
6. Run the filter and inspect the ranked, source-linked results.
7. Change the filter and rerun it without creating an account or subscription.

## Acceptance checklist

- [ ] Hero positions Paperboy as a personal relevance filter, not a newsletter summarizer.
- [ ] The many-inputs-to-few-signals transformation is visible above the fold.
- [ ] Every primary CTA says **Build my filter**; the header CTA is visually secondary.
- [ ] Public-feed presets and a direct URL intake are available.
- [ ] Input rejects missing email, feeds, or relevance focus before network calls.
- [ ] `/api/firehose/preview` is same-origin, bounded, and rejects private/non-public destinations.
- [ ] Per-source failures do not discard valid feed results.
- [ ] Preview items include title, source, score, relevance explanation, and original URL.
- [ ] Successful live previews persist source URLs, focus, ignore terms, and attribution to KaiBuilds Admin.
- [ ] Copy never claims Gmail access, automatic newsletter subscription, account creation, scheduled delivery, or billing.
- [ ] Desktop and mobile flows complete without horizontal overflow.
- [ ] Keyboard focus, labels, errors, reduced motion, target size, contrast, and typography pass the implemented Design OS floor.
