from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paperboy.api.main import app
from paperboy.db import connect, init_schema
from paperboy.firehose_delivery import run_daily_deliveries
from paperboy.subscriptions import (
    SubscriptionValidationError,
    create_subscription,
    get_subscription,
    unsubscribe,
    validate_subscription_payload,
)


def _preview() -> dict:
    return {
        "ok": True,
        "items": [
            {
                "title": "Agent reliability in production",
                "url": "https://example.com/agents",
                "source": "Builder News",
                "score": 88,
                "why": "Matches focus: agents, reliability",
                "summary": "A practical guide.",
            }
        ],
        "sources": [{"url": "https://example.com/feed", "status": "ok"}],
        "scanned": 10,
    }


class SubscriptionTestCase(unittest.TestCase):
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

    def create(self, email: str = "reader@example.com") -> tuple[dict, str]:
        return create_subscription(
            email,
            ["https://example.com/feed"],
            "AI agent reliability",
            ["funding gossip"],
            {"utm_source": "smoke"},
        )


class SubscriptionStorageTests(SubscriptionTestCase):
    def test_validation_reuses_preview_contract_and_accepts_attribution(self) -> None:
        email, sources, focus, ignore, attribution = validate_subscription_payload(
            {
                "email": " Reader@Example.com ",
                "sources": ["https://example.com/feed"],
                "focus": "AI agents",
                "ignore": ["gossip"],
                "source": "landing_page",
                "utm_campaign": "founding",
            }
        )
        self.assertEqual(email, "reader@example.com")
        self.assertEqual(sources, ["https://example.com/feed"])
        self.assertEqual(focus, "AI agents")
        self.assertEqual(ignore, ["gossip"])
        self.assertEqual(attribution, {"source": "landing_page", "utm_campaign": "founding"})
        with self.assertRaises(SubscriptionValidationError):
            validate_subscription_payload(
                {"email": "bad", "sources": ["https://example.com/feed"], "focus": "agents"}
            )

    def test_token_is_hashed_and_unsubscribe_is_idempotent(self) -> None:
        _subscription, token = self.create()
        conn = connect()
        try:
            token_hash, token_nonce = conn.execute(
                "SELECT token_hash, token_nonce FROM firehose_subscriptions"
            ).fetchone()
        finally:
            conn.close()
        self.assertNotEqual(token_hash, token)
        self.assertNotIn(token, token_nonce)
        self.assertTrue(get_subscription(token)["active"])
        self.assertFalse(unsubscribe(token)["active"])
        self.assertFalse(unsubscribe(token)["active"])
        self.assertIsNone(get_subscription(token + "x"))

    def test_resubscribing_replaces_config_and_invalidates_old_token(self) -> None:
        _first, old_token = self.create()
        second, new_token = create_subscription(
            "reader@example.com",
            ["https://example.org/rss"],
            "developer tools",
            [],
        )
        self.assertIsNone(get_subscription(old_token))
        self.assertEqual(get_subscription(new_token)["focus"], "developer tools")
        self.assertEqual(second["sources"], ["https://example.org/rss"])
        conn = connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM firehose_subscriptions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)


class SubscriptionEndpointTests(SubscriptionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        super().tearDown()

    def test_subscribe_previews_then_returns_self_service_routes(self) -> None:
        with patch("paperboy.api.main.build_firehose_preview", return_value=_preview()) as preview:
            response = self.client.post(
                "/api/firehose/subscribe",
                json={
                    "email": "reader@example.com",
                    "sources": ["https://example.com/feed"],
                    "focus": "AI agent reliability",
                    "ignore": ["funding gossip"],
                    "utm_source": "unit",
                },
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "subscribed")
        self.assertEqual(data["preview"]["items"][0]["score"], 88)
        self.assertTrue(data["manage_url"].startswith("/?manage="))
        self.assertTrue(data["status_url"].startswith("/api/firehose/subscriptions/"))
        self.assertTrue(data["unsubscribe_url"].endswith("/unsubscribe"))
        preview.assert_called_once()

        status = self.client.get(data["status_url"])
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["email_masked"], "r***@example.com")
        self.assertEqual(status.json()["status"], "active")
        self.assertIsNotNone(status.json()["next_delivery_at"])
        self.assertNotIn("email", status.json())

        stopped = self.client.post(data["unsubscribe_url"])
        self.assertEqual(stopped.json(), {"ok": True, "status": "unsubscribed"})
        self.assertEqual(self.client.get(data["status_url"]).json()["status"], "unsubscribed")

    def test_unreachable_preview_is_not_persisted(self) -> None:
        failed_preview = {
            "ok": True,
            "items": [],
            "sources": [{"url": "https://bad.example/feed", "status": "error", "error": "dns_failed"}],
            "scanned": 0,
        }
        with patch("paperboy.api.main.build_firehose_preview", return_value=failed_preview):
            response = self.client.post(
                "/api/firehose/subscribe",
                json={
                    "email": "reader@example.com",
                    "sources": ["https://bad.example/feed"],
                    "focus": "AI agents",
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["status"], "preview_failed")
        conn = connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM firehose_subscriptions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)


class FirehoseDeliveryTests(SubscriptionTestCase):
    def test_daily_delivery_sends_once_and_records_outcome(self) -> None:
        self.create()
        sent: list[tuple] = []

        def sender(*args, **kwargs) -> dict:
            sent.append((args, kwargs))
            return {"ok": True, "detail": "sent", "message_id": None}

        first = run_daily_deliveries(
            delivery_day=date(2026, 7, 16),
            preview_builder=lambda _sources, _focus, _ignore: _preview(),
            sender=sender,
        )
        second = run_daily_deliveries(
            delivery_day=date(2026, 7, 16),
            preview_builder=lambda _sources, _focus, _ignore: _preview(),
            sender=sender,
        )
        self.assertEqual(first, {"active": 1, "sent": 1, "failed": 0, "skipped": 0})
        self.assertEqual(second, {"active": 1, "sent": 0, "failed": 0, "skipped": 1})
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1]["to"], "reader@example.com")
        self.assertIn("https://paperboy.kaibuilds.com/?manage=", sent[0][0][1])
        self.assertIn("#unsubscribe", sent[0][0][1])
        conn = connect()
        try:
            status, item_count = conn.execute(
                "SELECT status, item_count FROM firehose_deliveries"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual((status, item_count), ("sent", 1))

    def test_failed_send_is_recorded_and_not_duplicated_that_day(self) -> None:
        self.create()

        def failed_sender(*_args, **_kwargs) -> dict:
            return {"ok": False, "detail": "smtp unavailable", "message_id": None}

        first = run_daily_deliveries(
            delivery_day=date(2026, 7, 17),
            preview_builder=lambda _sources, _focus, _ignore: _preview(),
            sender=failed_sender,
        )
        second = run_daily_deliveries(
            delivery_day=date(2026, 7, 17),
            preview_builder=lambda _sources, _focus, _ignore: _preview(),
            sender=failed_sender,
        )
        self.assertEqual(first["failed"], 1)
        self.assertEqual(second["skipped"], 1)
        conn = connect()
        try:
            status, detail = conn.execute("SELECT status, detail FROM firehose_deliveries").fetchone()
        finally:
            conn.close()
        self.assertEqual(status, "failed")
        self.assertEqual(detail, "smtp unavailable")


if __name__ == "__main__":
    unittest.main()
