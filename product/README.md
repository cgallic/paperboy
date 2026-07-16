# Paperboy Daily Intelligence Brief — validation surface

This is a self-contained, no-secrets validation surface for the hosted Paperboy
product direction. It is deployed at `https://paperboy.kaibuilds.com/`.

It demonstrates:

- a cold-traffic Daily Brief landing with a free personalized sample;
- explicit source selection for forwarded newsletters, public
  news/research/data, and optional read-only public GitHub repositories;
- a live same-origin concierge intake on KaiBuilds that records the email,
  newsletter names or URLs, optional public GitHub repos, and work focus;
- local-only fixture repository, interests, schedule, checkout,
  account, privacy, and billing state previews;
- a responsive email edition with Today in 60 Seconds, Repo Radar, Research
  Worth Reading, and Watchlist / Do Nothing;
- capped fixture items, evidence links, and local feedback controls; and
- the free self-hosted GitHub project as the acquisition path.

No auth, connector, scheduled email, model, or billing provider is configured.
On a KaiBuilds host, JavaScript records a visit with `/api/hit` and submits the
founding-pilot form to `/api/lead`; campaign parameters are preserved. The
product-tour state remains local under `paperboy.product-demo.v2`.

## Serve locally

From the repository root:

```powershell
python -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173/product/
```

Serving from the repository root keeps future local fixture links available.
No environment variables, package installation, or secret files are needed.

## Static checks

```powershell
node --check product/app.js
node product/check.mjs
git diff --check
```

## Golden path

1. Open the landing page and select **Get my free sample brief**.
2. Enter a valid email, at least one newsletter name or URL, optional public
   GitHub repo URLs, and the work focus that should rank the sample.
3. On KaiBuilds, confirm the complete intake persists in Admin under `paperboy`.
4. Open the fictional product tour.
5. Keep or change the forwarding/public source lanes.
6. Load fictional GitHub fixtures, search, and select up to five.
7. Add interests, active themes, and a watchlist decision.
8. Choose delivery days, time, and time zone.
9. Open the responsive email preview.
10. Continue to the disabled checkout handoff.
11. Preview successful setup and inspect account/privacy/billing states.
12. Clear all local demo data.

## Acceptance checklist

- [ ] Landing is clearly a Daily Intelligence Brief, not a generic summary or
  Repo Impact-only product.
- [ ] The hero names the manual behavior to replace and explains the product
  in one sentence.
- [ ] Every primary CTA says **Get my free sample brief**.
- [ ] Pricing makes the first personalized sample free and presents the
  $49/month founding pilot only after the sample.
- [ ] Source lanes explicitly distinguish forwarding, public catalog, and
  selected public GitHub repositories.
- [ ] Forwarding copy states that Gmail OAuth is not used.
- [ ] GitHub copy states selected repositories, exact planned read scopes, and
  zero write permission.
- [ ] Fixture repo picker enforces the 1–5 cap and supports search/selected-only.
- [ ] Interests and delivery steps validate required fields.
- [ ] Email preview contains four capped sections and evidence links.
- [ ] Feedback changes only local state.
- [ ] Checkout cannot create a charge.
- [ ] KaiBuilds lead capture uses only same-origin `/api/lead` and carries the
  explicit `paperboy` slug, campaign attribution, newsletter sources, optional
  public repo URLs, and work focus.
- [ ] Account state previews cannot call auth, billing, email, or GitHub.
- [ ] Desktop and mobile golden paths complete without horizontal overflow.
- [ ] Keyboard focus, labels, field errors, reduced motion, and touch targets
  meet the prototype accessibility baseline.
