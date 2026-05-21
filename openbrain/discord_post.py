"""Shared Discord webhook poster.

Discord webhooks return 403 against the default Python User-Agent when
behind Cloudflare; this module always sets a custom UA.

Two delivery paths:
- post() — webhook. Reads DISCORD_WEBHOOK from env.
- post_via_bot() — Discord bot API (richer formatting, no rate limits).
  Reads DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID from env.

Callers (digest scripts) try the bot path first if configured, fall back
to webhook.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

UA = "openbrain/0.1 (+https://github.com/cgallic/openbrain)"
DISCORD_API = "https://discord.com/api/v10"
DISCORD_MAX_LEN = 1900  # leave headroom under the 2000 hard limit


def post(content: str, *, username: str = "openbrain", dry_run: bool = False) -> bool:
    """Post a message via webhook. Returns True on 2xx."""
    webhook = os.environ.get("DISCORD_WEBHOOK") or os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("[discord_post] no DISCORD_WEBHOOK configured", file=sys.stderr)
        return False
    if not content.strip():
        return False
    body = content if len(content) <= DISCORD_MAX_LEN else content[:DISCORD_MAX_LEN - 5] + "\n..."
    payload = json.dumps({"content": body, "username": username}).encode("utf-8")
    if dry_run:
        print(body)
        return True
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ok = 200 <= r.status < 300
            if not ok:
                print(f"[discord_post] HTTP {r.status}", file=sys.stderr)
            return ok
    except urllib.error.HTTPError as e:
        print(f"[discord_post] HTTPError {e.code}: {e.read()[:200]!r}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[discord_post] {type(e).__name__}: {e}", file=sys.stderr)
        return False


def post_via_bot(content: str, *, channel_id: str | None = None,
                 dry_run: bool = False) -> tuple[bool, str]:
    """Post via the Discord bot API. Returns (ok, reason).

    reason is 'bot_env_missing' when DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID
    aren't set — callers can use that to trigger webhook fallback.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel = channel_id or os.environ.get("DISCORD_CHANNEL_ID", "")
    if not token or not channel:
        return False, "bot_env_missing"
    body_text = content if len(content) <= DISCORD_MAX_LEN else content[:DISCORD_MAX_LEN - 1] + "…"
    if dry_run:
        print(body_text)
        return True, "dry_run"
    body = json.dumps({"content": body_text}).encode("utf-8")
    req = urllib.request.Request(
        f"{DISCORD_API}/channels/{channel}/messages",
        data=body,
        method="POST",
    )
    req.add_header("Authorization", f"Bot {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return (r.status in (200, 201), f"http_{r.status}")
    except urllib.error.HTTPError as e:
        return False, f"http_{e.code}"
    except Exception as e:
        return False, f"err_{type(e).__name__}"


def deliver(content: str, *, username: str = "openbrain", dry_run: bool = False) -> tuple[bool, str]:
    """Try bot API first; fall back to webhook. Returns (ok, channel_used)."""
    ok, reason = post_via_bot(content, dry_run=dry_run)
    if ok:
        return True, "bot"
    if reason != "bot_env_missing":
        # Bot configured but failed — don't silently re-send via webhook.
        return False, f"bot:{reason}"
    ok = post(content, username=username, dry_run=dry_run)
    return ok, "webhook" if ok else "webhook:failed"


if __name__ == "__main__":
    msg = sys.stdin.read() if not sys.stdin.isatty() else "test ping from openbrain"
    ok, channel = deliver(msg, dry_run="--dry-run" in sys.argv)
    print(f"delivered={ok} channel={channel}")
    sys.exit(0 if ok else 1)
