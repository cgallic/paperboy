"""Health-check probes for paperboy subsystems.

Used by the API /health endpoint and by Docker HEALTHCHECK.
Each probe returns (ok: bool, detail: str).
"""
from __future__ import annotations

import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

from paperboy.config import settings
from paperboy.db import db_path


def check_database() -> tuple[bool, str]:
    p = db_path()
    if not p.exists():
        return False, f"events.db not found at {p}"
    try:
        conn = sqlite3.connect(str(p), timeout=5)
        conn.execute("SELECT COUNT(*) FROM events").fetchone()
        conn.close()
        return True, "connected"
    except sqlite3.Error as exc:
        return False, str(exc)


def check_ollama() -> tuple[bool, str]:
    url = f"{settings.ollama_url.rstrip('/')}/api/tags"
    req = urllib.request.Request(url, method="GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            _ = resp.read()
        elapsed = (time.time() - t0) * 1000
        return True, f"reachable ({elapsed:.0f}ms)"
    except urllib.error.HTTPError as e:
        # 403/401 is still "up" — just auth-rejected
        if e.code in (401, 403):
            return True, f"up (auth required, {e.code})"
        return False, f"HTTP {e.code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def check_disk(path: Path | None = None, min_gb: float = 0.5) -> tuple[bool, str]:
    p = path or settings.root
    try:
        p.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(p))
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb >= min_gb
        return ok, f"{free_gb:.2f} GB free (need {min_gb})"
    except Exception as exc:
        return False, str(exc)


def check_discord() -> tuple[bool, str]:
    if settings.discord_webhook_url:
        return True, "webhook configured"
    if settings.discord_bot_token and settings.discord_channel_id:
        return True, "bot configured"
    return True, "not configured (optional)"


def run_all() -> dict[str, dict]:
    """Run every probe and return a structured report."""
    probes = {
        "database": check_database,
        "ollama": check_ollama,
        "disk": check_disk,
        "discord": check_discord,
    }
    out: dict[str, dict] = {}
    for name, fn in probes.items():
        ok, detail = fn()
        out[name] = {"status": "healthy" if ok else "unhealthy", "detail": detail}
    required = ("database", "disk")
    out["overall"] = {"status": "healthy" if all(out[name]["status"] == "healthy" for name in required) else "degraded"}
    return out
