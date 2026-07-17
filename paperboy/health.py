"""Health-check probes for paperboy subsystems.

Used by the API /health endpoint and by Docker HEALTHCHECK.
Each probe returns (ok: bool, detail: str).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from paperboy.config import settings
from paperboy.db import db_path


def check_database() -> tuple[bool, str]:
    p = db_path()
    if not p.exists():
        return False, f"events.db not found at {p}"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(p), timeout=5)
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'events'"
        ).fetchone()
        if table is None:
            return False, "events table is missing"
        conn.execute("SELECT 1 FROM events LIMIT 1").fetchone()
        return True, "connected"
    except sqlite3.Error as exc:
        return False, str(exc)
    finally:
        if conn is not None:
            conn.close()


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


def check_scheduler() -> tuple[bool, str]:
    """Report scheduler recency when the shared heartbeat is configured."""
    if not os.environ.get("PAPERBOY_SCHEDULER_HEARTBEAT"):
        return True, "not configured (optional)"
    try:
        from paperboy.scheduler import check_heartbeat
    except ModuleNotFoundError:
        return False, "scheduler dependencies are unavailable"
    return check_heartbeat()


def check_backup_recency(max_age_hours: int = 48) -> tuple[bool, str]:
    """Check that a complete backup bundle has been created recently."""
    configured = os.environ.get("PAPERBOY_BACKUP_DIR")
    if not configured:
        return True, "not configured (optional)"
    backup_root = Path(configured)
    try:
        manifests = sorted(
            backup_root.glob("paperboy-*/manifest.json"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
    except OSError as exc:
        return False, f"backup directory is unavailable: {type(exc).__name__}"
    if not manifests:
        return False, "no completed backup bundle exists"
    try:
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00"))
        files = manifest["files"]
        complete = all(name in files and (manifests[0].parent / name).is_file() for name in ("events.db", "manage-secret"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return False, f"latest backup manifest is invalid: {type(exc).__name__}"
    if created_at.tzinfo is None or not complete:
        return False, "latest backup bundle is incomplete"
    age = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()
    if age < -300 or age > max_age_hours * 3600:
        return False, "latest backup is stale"
    return True, f"latest backup is {age / 3600:.1f} hours old"


def run_all() -> dict[str, dict]:
    """Run every probe and return a structured report."""
    probes: dict[str, Callable[[], tuple[bool, str]]] = {
        "database": check_database,
        "ollama": check_ollama,
        "disk": check_disk,
        "discord": check_discord,
        "scheduler": check_scheduler,
        "backup": check_backup_recency,
    }
    out: dict[str, dict] = {}
    for name, fn in probes.items():
        ok, detail = fn()
        out[name] = {"status": "healthy" if ok else "unhealthy", "detail": detail}
    required = ("database", "disk")
    out["overall"] = {"status": "healthy" if all(out[name]["status"] == "healthy" for name in required) else "degraded"}
    return out
