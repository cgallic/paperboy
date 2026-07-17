from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paperboy.api.main import app
from paperboy.db import connect, init_schema
from paperboy.firehose_delivery import run_daily_deliveries
from paperboy.subscriptions import (
    ExistingSubscriptionError,
    SubscriptionValidationError,
    active_subscriptions,
    confirm_subscription,
    confirmation_token,
    create_subscription,
    get_subscription,
    get_subscription_by_email,
    set_billing_state,
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

    def activate(self, email: str = "reader@example.com") -> tuple[dict, str]:
        subscription, token = self.create(email)
        confirmed = confirm_subscription(confirmation_token(subscription))
        assert confirmed is not None
        entitled = set_billing_state(
            int(confirmed["id"]),
            "trialing",
            trial_ends_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat()
            .replace("+00:00", "Z"),
        )
        assert entitled is not None
        return entitled, token


class SubscriptionStorageTests(SubscriptionTestCase):
    def test_validation_reuses_preview_contract_and_accepts_attribution(self) -> None:
        email, sources, focus, ignore, attribution, timezone_name = validate_subscription_payload(
            {
                "email": " Reader@Example.com ",
                "sources": ["https://example.com/feed"],
                "focus": "AI agents",
                "ignore": ["gossip"],
                "source": "landing_page",
                "utm_campaign": "founding",
                "consent": True,
                "timezone": "America/New_York",
            }
        )
        self.assertEqual(email, "reader@example.com")
        self.assertEqual(sources, ["https://example.com/feed"])
        self.assertEqual(focus, "AI agents")
        self.assertEqual(ignore, ["gossip"])
        self.assertEqual(attribution, {"source": "landing_page", "utm_campaign": "founding"})
        self.assertEqual(timezone_name, "America/New_York")
        with self.assertRaises(SubscriptionValidationError):
            validate_subscription_payload(
                {
                    "email": "bad",
                    "sources": ["https://example.com/feed"],
                    "focus": "agents",
                    "consent": True,
                }
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
        self.assertFalse(get_subscription(token)["active"])
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

    def test_unverified_resubscribe_cannot_disable_verified_entitled_row(self) -> None:
        entitled, old_token = self.activate()
        with self.assertRaises(ExistingSubscriptionError):
            create_subscription(
                "reader@example.com",
                ["https://attacker.example/rss"],
                "replacement focus",
                [],
            )

        current = get_subscription(old_token)
        assert current is not None
        self.assertEqual(current["id"], entitled["id"])
        self.assertTrue(current["active"])
        self.assertEqual(current["verification_status"], "verified")
        self.assertEqual(current["sources"], ["https://example.com/feed"])
        self.assertEqual(len(active_subscriptions()), 1)


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
                    "consent": True,
                    "timezone": "UTC",
                },
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending_verification")
        self.assertEqual(data["preview"]["items"][0]["score"], 88)
        self.assertTrue(data["confirmation_queued"])
        preview.assert_called_once()

        subscription = get_subscription_by_email("reader@example.com")
        assert subscription is not None
        confirmed = self.client.post(
            f"/api/firehose/subscriptions/{confirmation_token(subscription)}/confirm"
        )
        self.assertEqual(confirmed.status_code, 200)
        confirmed_data = confirmed.json()
        self.assertEqual(confirmed_data["status"], "active")
        status = self.client.get(confirmed_data["status_url"])
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["email_masked"], "r***@example.com")
        self.assertEqual(status.json()["status"], "active")
        self.assertIsNone(status.json()["next_delivery_at"])
        self.assertNotIn("email", status.json())

        stopped = self.client.post(confirmed_data["unsubscribe_url"])
        self.assertEqual(stopped.json(), {"ok": True, "status": "unsubscribed"})
        self.assertEqual(self.client.get(confirmed_data["status_url"]).json()["status"], "unsubscribed")

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
                    "consent": True,
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
        self.activate()
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
        self.assertIn("/unsubscribe", sent[0][0][1])
        conn = connect()
        try:
            status, item_count = conn.execute(
                "SELECT status, item_count FROM firehose_deliveries"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual((status, item_count), ("sent", 1))

    def test_daily_delivery_does_not_resend_previously_delivered_item(self) -> None:
        self.activate()
        sent: list[str] = []

        def sender(_subject: str, body_text: str, *_args, **_kwargs) -> dict:
            sent.append(body_text)
            return {"ok": True, "detail": "sent", "message_id": None}

        first = run_daily_deliveries(
            delivery_day=date(2026, 7, 16),
            preview_builder=lambda *_: _preview(),
            sender=sender,
        )
        second = run_daily_deliveries(
            delivery_day=date(2026, 7, 17),
            preview_builder=lambda *_: _preview(),
            sender=sender,
        )

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 1)
        self.assertIn("Agent reliability in production", sent[0])
        self.assertNotIn("Agent reliability in production", sent[1])
        self.assertIn("No items cleared your filter today.", sent[1])
        conn = connect()
        try:
            item_counts = [
                int(row[0])
                for row in conn.execute(
                    "SELECT item_count FROM firehose_deliveries ORDER BY delivery_date"
                )
            ]
            delivered_items = int(
                conn.execute(
                    "SELECT COUNT(*) FROM events "
                    "WHERE source = 'paperboy-firehose' AND type = 'delivered-item'"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        self.assertEqual(item_counts, [1, 0])
        self.assertEqual(delivered_items, 1)

    def test_failed_send_is_recorded_and_not_duplicated_that_day(self) -> None:
        self.activate()

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
