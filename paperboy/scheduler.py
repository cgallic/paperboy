"""APScheduler-based scheduler for paperboy pipelines.

Runs inside a container (paperboy-scheduler service in docker-compose)
and executes the CLI modules on a cron-like schedule.  Replaces systemd
timers for containerized / cloud deployments.

Schedule (UTC):
  10:00  research-ingest
  10:45  research-score
  11:00  news-opinion
  11:05  papers-to-prompts
  11:08  topical-questions
  11:10  today-briefing
  11:15  prompt-digest
  12:00  research-digest
  every 5 minutes  confirmation queue + due 08:00-local firehose delivery
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from paperboy.db import root
from paperboy.logging_config import configure_logging, get_logger

logger = get_logger("scheduler")
scheduler = BlockingScheduler(timezone="UTC")
_heartbeat_lock = threading.Lock()
_heartbeat_state: dict[str, Any] = {}
_SUMMARY_FIELDS = {
    "active",
    "claimed",
    "sent",
    "failed",
    "skipped",
    "processed",
    "retried",
    "pending",
    "forwarded",
    "delivered",
    "suppressed",
}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("heartbeat timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _heartbeat_path() -> Path:
    configured = os.environ.get("PAPERBOY_SCHEDULER_HEARTBEAT")
    return Path(configured) if configured else root() / "scheduler-heartbeat.json"


def _write_heartbeat() -> None:
    path = _heartbeat_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(_heartbeat_state, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _initialize_heartbeat(required_jobs: list[str], *, now: datetime | None = None) -> None:
    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with _heartbeat_lock:
        _heartbeat_state.clear()
        _heartbeat_state.update(
            {
                "version": 1,
                "started_at": _iso(started),
                "updated_at": _iso(started),
                "required_jobs": sorted(required_jobs),
                "jobs": {},
            }
        )
        _write_heartbeat()


def _safe_summary(stdout: str) -> dict[str, int]:
    """Extract only non-negative operational counts from a CLI JSON summary."""
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        return {
            key: count
            for key, count in value.items()
            if key in _SUMMARY_FIELDS and isinstance(count, int) and not isinstance(count, bool) and count >= 0
        }
    return {}


def _record_job_result(
    module: str,
    ok: bool,
    diagnostics: dict[str, int | float | bool | str],
    *,
    now: datetime | None = None,
) -> None:
    completed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with _heartbeat_lock:
        if not _heartbeat_state:
            _heartbeat_state.update(
                {
                    "version": 1,
                    "started_at": _iso(completed),
                    "required_jobs": [],
                    "jobs": {},
                }
            )
        jobs = _heartbeat_state.setdefault("jobs", {})
        jobs[module] = {"completed_at": _iso(completed), "ok": ok, **diagnostics}
        _heartbeat_state["updated_at"] = _iso(completed)
        _write_heartbeat()


def check_heartbeat(
    *,
    path: Path | None = None,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Require every configured interval job to have succeeded recently."""
    heartbeat = path or _heartbeat_path()
    raw_max_age = (
        max_age_seconds
        if max_age_seconds is not None
        else os.environ.get("PAPERBOY_SCHEDULER_HEARTBEAT_MAX_AGE_SECONDS", "900")
    )
    try:
        maximum_age = int(raw_max_age)
    except (TypeError, ValueError):
        return False, "invalid heartbeat maximum age"
    if maximum_age < 60 or maximum_age > 86400:
        return False, "invalid heartbeat maximum age"
    try:
        state = json.loads(heartbeat.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "scheduler heartbeat is missing or unreadable"
    required_jobs = state.get("required_jobs")
    jobs = state.get("jobs")
    if not isinstance(required_jobs, list) or not required_jobs or not isinstance(jobs, dict):
        return False, "scheduler heartbeat has no required jobs"
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for module in required_jobs:
        result = jobs.get(module)
        if not isinstance(module, str) or not isinstance(result, dict):
            return False, "a required scheduler job has not completed"
        try:
            age = (checked_at - _parse_time(result.get("completed_at"))).total_seconds()
        except (TypeError, ValueError):
            return False, "a required scheduler job has an invalid timestamp"
        if age < -60 or age > maximum_age:
            return False, "a required scheduler job heartbeat is stale"
        if result.get("ok") is not True:
            return False, "a required scheduler job failed"
    return True, f"{len(required_jobs)} required jobs succeeded recently"


def _run(module: str, *extra: str) -> None:
    cmd = [sys.executable, "-m", module, *extra]
    t0 = datetime.now(timezone.utc)
    logger.info("job_start", extra={"event": "job_start", "job": module})
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        summary = _safe_summary(result.stdout)
        ok = result.returncode == 0 and summary.get("failed", 0) == 0
        diagnostics: dict[str, int | float | bool | str] = {
            **summary,
            "elapsed_sec": round(elapsed, 1),
            "returncode": result.returncode,
            "stderr_present": bool(result.stderr.strip()),
        }
        _record_job_result(module, ok, diagnostics)
        level = "info" if ok else "error"
        getattr(logger, level)(
            "job_end",
            extra={
                "event": "job_end",
                "job": module,
                "ok": ok,
                **diagnostics,
            },
        )
    except subprocess.TimeoutExpired:
        diagnostics = {"error_type": "TimeoutExpired", "returncode": -1}
        _record_job_result(module, False, diagnostics)
        logger.error("job_timeout", extra={"event": "job_timeout", "job": module, **diagnostics})
    except Exception as exc:
        diagnostics = {"error_type": type(exc).__name__, "returncode": -1}
        _record_job_result(module, False, diagnostics)
        logger.error("job_error", extra={"event": "job_error", "job": module, **diagnostics})


JOBS = [
    ("paperboy.privacy", "03:30"),
    ("paperboy.ingest.research_papers", "10:00"),
    ("paperboy.score.research_papers", "10:45"),
    ("paperboy.scanners.news_opinion", "11:00"),
    ("paperboy.scanners.papers_to_prompts", "11:05"),
    ("paperboy.scanners.topical_questions", "11:08"),
    ("paperboy.scanners.today_briefing", "11:10"),
    ("paperboy.digest.prompt_digest", "11:15"),
    ("paperboy.digest.research_digest", "12:00"),
]
JOB_ARGS = {"paperboy.privacy": ("purge",)}

INTERVAL_JOBS = [
    ("paperboy.confirmation_delivery", 5),
    ("paperboy.firehose_delivery", 5),
    ("paperboy.lifecycle_delivery", 5),
]


def main() -> None:
    configure_logging()
    only_module = os.environ.get("PAPERBOY_SCHEDULER_ONLY", "").strip()
    jobs = [job for job in JOBS if not only_module or job[0] == only_module]
    interval_jobs = [job for job in INTERVAL_JOBS if not only_module or job[0] == only_module]
    # Backwards compatibility: the deployed compose profile historically set
    # scheduler-only to firehose_delivery. Confirmation is a required companion
    # safety job, lifecycle forwarding is required attribution, and privacy
    # retention must not be accidentally disabled by that old setting.
    if only_module == "paperboy.firehose_delivery":
        interval_jobs = list(INTERVAL_JOBS)
        jobs = [job for job in JOBS if job[0] == "paperboy.privacy"]
    if not jobs and not interval_jobs:
        raise RuntimeError(f"PAPERBOY_SCHEDULER_ONLY does not match a configured job: {only_module}")
    _initialize_heartbeat([module for module, _minutes in interval_jobs])
    logger.info(
        "scheduler_startup",
        extra={"event": "scheduler_startup", "jobs": len(jobs) + len(interval_jobs)},
    )
    for module, time_str in jobs:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            _run,
            trigger=CronTrigger(hour=int(hour), minute=int(minute)),
            args=(module, *JOB_ARGS.get(module, ())),
            id=module,
            replace_existing=True,
        )
    for module, minutes in interval_jobs:
        scheduler.add_job(
            _run,
            trigger=IntervalTrigger(minutes=minutes),
            args=(module,),
            id=module,
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),
        )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler_shutdown", extra={"event": "scheduler_shutdown"})
        scheduler.shutdown()


if __name__ == "__main__":
    if sys.argv[1:] == ["--health-check"]:
        healthy, detail = check_heartbeat()
        print(json.dumps({"detail": detail, "status": "healthy" if healthy else "unhealthy"}, sort_keys=True))
        raise SystemExit(0 if healthy else 1)
    main()
