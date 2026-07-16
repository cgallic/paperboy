# Paperboy Daily Intelligence Brief — local product surface

This is a self-contained, no-secrets static prototype for the hosted Paperboy
product direction.

It demonstrates:

- a Daily Intelligence Brief landing and $49/month Operator price hypothesis;
- explicit source selection for forwarded newsletters, public
  news/research/data, and optional read-only public GitHub repositories;
- local-only magic-link, fixture repository, interests, schedule, checkout,
  account, privacy, and billing state previews;
- a responsive email edition with Today in 60 Seconds, Repo Radar, Research
  Worth Reading, and Watchlist / Do Nothing;
- capped fixture items, evidence links, and local feedback controls; and
- the free self-hosted GitHub project as the acquisition path.

No auth, connector, email, model, billing, or backend provider is configured.
The JavaScript makes no network request. It persists only the demo state under
the browser localStorage key `paperboy.product-demo.v2`.

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

1. Open the landing page and select **Build a Daily Brief**.
2. Enter a valid email and open the simulated magic link.
3. Keep or change the forwarding/public source lanes.
4. Load fictional GitHub fixtures, search, and select up to five.
5. Add interests, active themes, and a watchlist decision.
6. Choose delivery days, time, and time zone.
7. Open the responsive email preview.
8. Continue to the disabled checkout handoff.
9. Preview successful setup and inspect account/privacy/billing states.
10. Clear all local demo data.

## Acceptance checklist

- [ ] Landing is clearly a Daily Intelligence Brief, not a generic summary or
  Repo Impact-only product.
- [ ] Pricing shows $49/month as a hypothesis; $29/$49/$79 and $199
  calibration are labeled validation options, not live offers.
- [ ] Self-hosted Paperboy remains visible as the free acquisition path.
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
- [ ] Account state previews cannot call auth, billing, email, or GitHub.
- [ ] Desktop and mobile golden paths complete without horizontal overflow.
- [ ] Keyboard focus, labels, field errors, reduced motion, and touch targets
  meet the prototype accessibility baseline.
