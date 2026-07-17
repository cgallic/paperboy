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

import os
import subprocess
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from paperboy.logging_config import configure_logging, get_logger

logger = get_logger("scheduler")
scheduler = BlockingScheduler(timezone="UTC")


def _run(module: str, *extra: str) -> None:
    cmd = [sys.executable, "-m", module, *extra]
    t0 = datetime.now(timezone.utc)
    logger.info("job_start", extra={"event": "job_start", "job": module})
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        ok = result.returncode == 0
        level = "info" if ok else "error"
        getattr(logger, level)(
            "job_end",
            extra={
                "event": "job_end",
                "job": module,
                "ok": ok,
                "elapsed_sec": round(elapsed, 1),
                "stdout": result.stdout[-500:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
            },
        )
    except subprocess.TimeoutExpired:
        logger.error("job_timeout", extra={"event": "job_timeout", "job": module})
    except Exception as exc:
        logger.error("job_error", extra={"event": "job_error", "job": module, "error": str(exc)})


JOBS = [
    ("paperboy.ingest.research_papers", "10:00"),
    ("paperboy.score.research_papers", "10:45"),
    ("paperboy.scanners.news_opinion", "11:00"),
    ("paperboy.scanners.papers_to_prompts", "11:05"),
    ("paperboy.scanners.topical_questions", "11:08"),
    ("paperboy.scanners.today_briefing", "11:10"),
    ("paperboy.digest.prompt_digest", "11:15"),
    ("paperboy.digest.research_digest", "12:00"),
]

INTERVAL_JOBS = [
    ("paperboy.confirmation_delivery", 5),
    ("paperboy.firehose_delivery", 5),
]


def main() -> None:
    configure_logging()
    only_module = os.environ.get("PAPERBOY_SCHEDULER_ONLY", "").strip()
    jobs = [job for job in JOBS if not only_module or job[0] == only_module]
    interval_jobs = [job for job in INTERVAL_JOBS if not only_module or job[0] == only_module]
    # Backwards compatibility: the deployed compose profile historically set
    # scheduler-only to firehose_delivery. Confirmation is a required companion
    # safety job and must not be accidentally disabled by that old setting.
    if only_module == "paperboy.firehose_delivery":
        interval_jobs = list(INTERVAL_JOBS)
    if not jobs and not interval_jobs:
        raise RuntimeError(f"PAPERBOY_SCHEDULER_ONLY does not match a configured job: {only_module}")
    logger.info(
        "scheduler_startup",
        extra={"event": "scheduler_startup", "jobs": len(jobs) + len(interval_jobs)},
    )
    for module, time_str in jobs:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            _run,
            trigger=CronTrigger(hour=int(hour), minute=int(minute)),
            args=(module,),
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
    main()
