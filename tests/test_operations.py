from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paperboy.health import check_backup_recency, check_scheduler
from paperboy.logging_config import _JSONFormatter
from paperboy.scheduler import (
    INTERVAL_JOBS,
    JOB_ARGS,
    JOBS,
    _initialize_heartbeat,
    _record_job_result,
    _safe_summary,
    check_heartbeat,
)


class LoggingTests(unittest.TestCase):
    def test_json_formatter_keeps_safe_counts_and_drops_sensitive_extras(self) -> None:
        record = logging.LogRecord("paperboy.test", logging.INFO, __file__, 1, "job_end", (), None)
        record.event = "job_end"
        record.job = "paperboy.firehose_delivery"
        record.failed = 2
        record.elapsed_sec = 1.5
        record.email = "reader@example.com"
        record.stdout = "sensitive child output"
        payload = json.loads(_JSONFormatter().format(record))
        self.assertEqual(payload["failed"], 2)
        self.assertEqual(payload["elapsed_sec"], 1.5)
        self.assertNotIn("email", payload)
        self.assertNotIn("stdout", payload)

    def test_safe_summary_uses_only_non_negative_count_fields(self) -> None:
        summary = _safe_summary('noise\n{"sent": 2, "failed": 0, "email": "private", "pending": -1}\n')
        self.assertEqual(summary, {"sent": 2, "failed": 0})


class SchedulerHeartbeatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "heartbeat.json"
        self.environment = patch.dict(
            os.environ,
            {
                "PAPERBOY_SCHEDULER_HEARTBEAT": str(self.path),
                "PAPERBOY_SCHEDULER_HEARTBEAT_MAX_AGE_SECONDS": "900",
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def test_heartbeat_requires_every_job_to_succeed_recently(self) -> None:
        now = datetime.now(timezone.utc)
        jobs = ["paperboy.confirmation_delivery", "paperboy.firehose_delivery"]
        _initialize_heartbeat(jobs, now=now)
        _record_job_result(jobs[0], True, {"sent": 1}, now=now)
        self.assertFalse(check_heartbeat(path=self.path, now=now)[0])
        _record_job_result(jobs[1], True, {"sent": 1}, now=now)
        self.assertTrue(check_heartbeat(path=self.path, now=now)[0])
        self.assertTrue(check_scheduler()[0])
        self.assertFalse(check_heartbeat(path=self.path, now=now + timedelta(minutes=16))[0])

    def test_failed_job_makes_heartbeat_unhealthy(self) -> None:
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)
        _initialize_heartbeat(["paperboy.firehose_delivery"], now=now)
        _record_job_result("paperboy.firehose_delivery", False, {"failed": 1}, now=now)
        self.assertFalse(check_heartbeat(path=self.path, now=now)[0])

    def test_lifecycle_attribution_retry_is_a_five_minute_job(self) -> None:
        self.assertIn(("paperboy.lifecycle_delivery", 5), INTERVAL_JOBS)

    def test_privacy_purge_runs_daily(self) -> None:
        self.assertIn(("paperboy.privacy", "03:30"), JOBS)
        self.assertEqual(JOB_ARGS["paperboy.privacy"], ("purge",))


class BackupHealthTests(unittest.TestCase):
    def test_backup_recency_rejects_missing_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"PAPERBOY_BACKUP_DIR": directory}, clear=False
        ):
            self.assertFalse(check_backup_recency()[0])


if __name__ == "__main__":
    unittest.main()
