#!/usr/bin/env bash
# bootstrap.sh — one-shot installer for paperboy on a Linux host with systemd.
#
# What this does:
#   1. Creates a venv at /opt/paperboy/.venv and installs paperboy into it.
#   2. Creates /etc/paperboy/paperboy.env from the example (if missing).
#   3. Copies systemd units to /etc/systemd/system/ and patches ExecStart to
#      use the venv's python.
#   4. Initializes the SQLite events.db at $PAPERBOY_ROOT/events.db.
#   5. Enables all 7 timers.
#
# Re-runnable: skips steps that are already done.
#
# After this runs:
#   - Edit /etc/paperboy/paperboy.env and set DISCORD_WEBHOOK (or bot token).
#   - Edit /etc/paperboy/news_sources.yaml, research-interests.md, etc.
#   - `systemctl list-timers | grep paperboy` to confirm.
set -euo pipefail

ROOT="${PAPERBOY_ROOT:-/var/lib/paperboy}"
INSTALL="/opt/paperboy"
ETC="/etc/paperboy"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$EUID" -ne 0 ]]; then
    echo "error: must run as root (uses systemctl + writes to /etc + /opt)" >&2
    exit 1
fi

echo "==> installing into $INSTALL"
mkdir -p "$INSTALL" "$ROOT" "$ETC"

if [[ ! -d "$INSTALL/.venv" ]]; then
    python3 -m venv "$INSTALL/.venv"
fi
"$INSTALL/.venv/bin/pip" install --upgrade pip >/dev/null
"$INSTALL/.venv/bin/pip" install "$REPO_ROOT" >/dev/null

echo "==> seeding config in $ETC"
for f in paperboy.env news_sources.yaml research-sources.json \
         research-interests.md topical-map.md; do
    src="$REPO_ROOT/config/${f}.example"
    [[ "$f" == *.env ]] && src="$REPO_ROOT/config/env.example"
    [[ "$f" == *.yaml ]] && src="$REPO_ROOT/config/news_sources.yaml.example"
    [[ "$f" == *.json ]] && src="$REPO_ROOT/config/research-sources.json.example"
    [[ "$f" == "research-interests.md" ]] && src="$REPO_ROOT/config/research-interests.md.example"
    [[ "$f" == "topical-map.md" ]] && src="$REPO_ROOT/config/topical-map.md.example"
    if [[ -f "$src" && ! -f "$ETC/$f" ]]; then
        cp "$src" "$ETC/$f"
        echo "    seeded $ETC/$f"
    fi
done

echo "==> initializing SQLite events.db"
PAPERBOY_ROOT="$ROOT" "$INSTALL/.venv/bin/python" -c "from paperboy.db import init_schema; init_schema()"

echo "==> installing systemd units"
VENV_PY="$INSTALL/.venv/bin/python"
for unit in "$REPO_ROOT"/systemd/*.service "$REPO_ROOT"/systemd/*.timer; do
    name=$(basename "$unit")
    # Rewrite ExecStart to use the venv python and point EnvironmentFile at /etc/paperboy
    sed -e "s|/usr/bin/env python3|$VENV_PY|g" \
        "$unit" > "/etc/systemd/system/$name"
done

systemctl daemon-reload

echo "==> enabling timers"
for timer in paperboy-news-opinion paperboy-research-ingest \
             paperboy-research-score paperboy-papers-to-prompts \
             paperboy-topical-questions paperboy-today-briefing \
             paperboy-prompt-digest paperboy-research-digest; do
    systemctl enable --now "${timer}.timer" >/dev/null
    echo "    enabled ${timer}.timer"
done

cat <<EOF

==> done.

Next steps:
  1. Edit $ETC/paperboy.env  — set DISCORD_WEBHOOK (or DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID)
  2. Edit $ETC/news_sources.yaml — your RSS feeds, by vertical
  3. Edit $ETC/research-interests.md — describe YOUR systems (the scorer reads this)
  4. (Optional) edit $ETC/topical-map.md — your content pillars
  5. (Optional) drop daily briefs into \$DAILY_BRIEFS_DIR (default ~/.paperboy/daily-briefs/)

Confirm: systemctl list-timers | grep paperboy
Test:    sudo -u paperboy $VENV_PY -m paperboy.scanners.news_opinion --dry-run
EOF
