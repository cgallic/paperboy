from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paperboy.db import connect, init_schema
from paperboy.privacy import erase_subscriber, run_retention
from paperboy.subscriptions import create_subscription


class PrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = os.environ.get("PAPERBOY_ROOT")
        self.old_db = os.environ.get("PAPERBOY_DB")
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = self.tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(self.tempdir.name) / "events.db")
        init_schema()

    def tearDown(self) -> None:
        if self.old_root is None:
            os.environ.pop("PAPERBOY_ROOT", None)
        else:
            os.environ["PAPERBOY_ROOT"] = self.old_root
        if self.old_db is None:
            os.environ.pop("PAPERBOY_DB", None)
        else:
            os.environ["PAPERBOY_DB"] = self.old_db
        self.tempdir.cleanup()

    def test_retention_purges_expired_tracking_and_old_telemetry(self) -> None:
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)
        old = (now - timedelta(days=500)).isoformat().replace("+00:00", "Z")
        subscription, _ = create_subscription(
            "reader@example.com", ["https://example.com/feed"], "agent reliability", []
        )
        conn = connect()
        try:
            token = conn.execute(
                "INSERT INTO firehose_tracking_tokens "
                "(subscription_id,token_hash,kind,created_at,expires_at) VALUES (?,?,?,?,?)",
                (subscription["id"], "expired", "open", old, old),
            ).lastrowid
            conn.execute(
                "INSERT INTO firehose_tracking_events "
                "(token_id,subscription_id,event,occurred_at) VALUES (?,?,?,?)",
                (token, subscription["id"], "open", old),
            )
            conn.execute(
                "INSERT INTO events (ts,source,type,actor,payload_json,ingested_at) "
                "VALUES (?,'paperboy-api','analytics_event',NULL,'{}',?)",
                (old, old),
            )
            conn.commit()
        finally:
            conn.close()
        result = run_retention(now=now)
        self.assertEqual(result["tracking_tokens"], 1)
        self.assertEqual(result["tracking_events"], 1)
        self.assertEqual(result["telemetry_events"], 1)

    def test_erasure_removes_inactive_subscriber_and_referencing_event(self) -> None:
        subscription, _ = create_subscription(
            "reader@example.com", ["https://example.com/feed"], "agent reliability", []
        )
        conn = connect()
        try:
            now = "2026-07-17T00:00:00Z"
            conn.execute(
                "INSERT INTO events (ts,source,type,actor,payload_json,ingested_at) VALUES (?,?,?,?,?,?)",
                (
                    now,
                    "paperboy-api",
                    "lead",
                    "reader@example.com",
                    '{"email":"reader@example.com"}',
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = erase_subscriber("reader@example.com")
        self.assertEqual(result["subscriptions"], 1)
        self.assertEqual(result["events"], 1)


if __name__ == "__main__":
    unittest.main()
