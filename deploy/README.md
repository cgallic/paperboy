# Paperboy hosted deployment

Production authority:

- application: `prod-77:/opt/paperboy`
- static landing: `prod-77:/var/www/kaibuilds/sites/paperboy`
- API: `127.0.0.1:9122`
- customer intake and visit stats: existing KaiBuilds capture service on
  `127.0.0.1:9120`

Deploy the API with `docker compose up -d paperboy`. The optional scheduler is
behind the `scheduler` Compose profile and must not be started until a real
customer-source ingestion and delivery configuration exists.

Install `Caddyfile.paperboy` before the wildcard `*.kaibuilds.com` behavior is
used. It deliberately preserves `/api/lead`, `/api/hit`, `/api/stats`, and
`/api/sites` on the KaiBuilds capture service so leads remain durable and
visible in the private admin.
