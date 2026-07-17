# Paperboy hosted deployment

Production authority:

- application: `prod-77:/opt/paperboy`
- static landing: `prod-77:/var/www/kaibuilds/sites/paperboy`
- API: `127.0.0.1:9122`
- customer intake and visit stats: existing KaiBuilds capture service on
  `127.0.0.1:9120`

Copy `deploy/paperboy.env.example` to `.env` and keep it mode `0600`. Before
starting Compose, create the host backup directory for the image's non-root
UID. Compose deliberately refuses to create this bind mount implicitly:

```bash
install -d -o 1000 -g 1000 -m 0700 /var/backups/paperboy
chmod 0600 /opt/paperboy/.env
docker compose --profile scheduler up -d --build paperboy paperboy-scheduler
docker compose ps
```

The scheduler profile runs confirmation, daily-delivery, and lifecycle-ledger
retry jobs every five minutes. Its Docker health check requires every interval
job to complete successfully within the configured heartbeat window. A running
PID alone is not considered healthy.

Install `Caddyfile.paperboy` before the wildcard `*.kaibuilds.com` behavior is
used. It deliberately preserves `/api/lead`, `/api/hit`, `/api/stats`, and
`/api/sites` on the KaiBuilds capture service so leads remain durable and
visible in the private admin.

## Backups and restore drills

The backup command uses SQLite's online backup API, includes the management
signing key, writes SHA-256 checksums, runs `PRAGMA integrity_check`, and only
then publishes the timestamped bundle. Retention applies only to valid direct
children of the configured backup directory. Expired bundles move to the
recoverable `.expired/` quarantine; this automation never irreversibly deletes
production backup material.

Install and exercise the daily timer after the containers are healthy:

```bash
install -m 0644 systemd/paperboy-backup.service /etc/systemd/system/paperboy-backup.service
install -m 0644 systemd/paperboy-backup.timer /etc/systemd/system/paperboy-backup.timer
systemctl daemon-reload
systemctl enable --now paperboy-backup.timer
systemctl start paperboy-backup.service
systemctl status paperboy-backup.service --no-pager
systemctl list-timers paperboy-backup.timer --no-pager
```

Verify a specific bundle and restore it into a brand-new drill directory. The
restore command refuses existing paths and refuses the live Paperboy state
directory:

```bash
docker compose exec -T paperboy python -m paperboy.backup verify \
  /app/backups/paperboy-YYYYMMDDTHHMMSS.ffffffZ
docker compose exec -T paperboy python -m paperboy.backup restore \
  /app/backups/paperboy-YYYYMMDDTHHMMSS.ffffffZ \
  --target-dir /app/backups/restore-drill-YYYYMMDD
```

The configured directory is still on the production host. Host loss therefore
remains a recovery risk until an encrypted offsite destination is approved and
the verified bundles are replicated there. This repository intentionally does
not guess or embed offsite credentials.

## Operational checks

```bash
curl -fsS https://newpaperboy.com/api/health
docker compose ps
docker compose logs --since 30m paperboy-scheduler
```

Logs are JSON-rotated at 10 MiB with three files per container. Scheduler logs
retain only bounded counts, return codes, timing, and error types; raw child
output, recipient addresses, subjects, and tokens are not copied into the
structured record.
