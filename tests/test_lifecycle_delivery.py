from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from paperboy.db import connect, init_schema
from paperboy.lifecycle_delivery import deliver_pending, enqueue_lifecycle_event
from paperboy.subscriptions import confirm_subscription, confirmation_token, create_subscription


class LifecycleDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = os.environ.get("PAPERBOY_ROOT")
        self.old_db = os.environ.get("PAPERBOY_DB")
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = self.tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(self.tempdir.name) / "events.db")
        init_schema()
        pending, _ = create_subscription(
            "reader@example.com",
            ["https://example.com/feed"],
            "agent reliability",
            [],
            {"utm_source": "kaibuilds", "utm_campaign": "paperboy"},
        )
        self.subscription = confirm_subscription(confirmation_token(pending))
        assert self.subscription is not None

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

    def test_outbox_is_durable_deduplicated_and_preserves_attribution(self) -> None:
        self.assertTrue(
            enqueue_lifecycle_event("verified:1", int(self.subscription["id"]), "email_verified")
        )
        self.assertFalse(
            enqueue_lifecycle_event("verified:1", int(self.subscription["id"]), "email_verified")
        )
        payloads: list[dict] = []

        def sender(payload: dict) -> bool:
            payloads.append(payload)
            return True

        summary = deliver_pending(sender=sender)
        self.assertEqual(summary, {"claimed": 1, "delivered": 1, "failed": 0, "skipped": 0})
        self.assertEqual(payloads[0]["utm_source"], "kaibuilds")
        self.assertEqual(payloads[0]["lifecycle_event"], "email_verified")
        self.assertEqual(payloads[0]["cadence"], "daily")
        self.assertEqual(payloads[0]["weekly_day"], 0)
        conn = connect()
        try:
            status = conn.execute("SELECT status FROM product_lifecycle_outbox").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(status, "delivered")

    def test_failed_delivery_remains_retryable_without_logging_email(self) -> None:
        enqueue_lifecycle_event("trial:1", int(self.subscription["id"]), "trial_started")
        summary = deliver_pending(sender=lambda _payload: False)
        self.assertEqual(summary["failed"], 1)
        conn = connect()
        try:
            row = conn.execute(
                "SELECT status, attempt_count, last_error FROM product_lifecycle_outbox"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(tuple(row), ("failed", 1, "capture_rejected"))


if __name__ == "__main__":
    unittest.main()
