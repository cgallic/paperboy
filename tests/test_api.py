from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from paperboy.api.main import app
from paperboy.config import settings
from paperboy.db import connect
from paperboy.subscriptions import (
    bounce_address,
    confirm_subscription,
    confirmation_token,
    create_subscription,
    get_subscription_by_id,
)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._old_root = os.environ.get("PAPERBOY_ROOT")
        cls._old_db = os.environ.get("PAPERBOY_DB")
        cls._tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = cls._tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(cls._tempdir.name) / "events.db")
        cls._client_context = TestClient(app)
        cls.client = cls._client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_context.__exit__(None, None, None)
        if cls._old_root is None:
            os.environ.pop("PAPERBOY_ROOT", None)
        else:
            os.environ["PAPERBOY_ROOT"] = cls._old_root
        if cls._old_db is None:
            os.environ.pop("PAPERBOY_DB", None)
        else:
            os.environ["PAPERBOY_DB"] = cls._old_db
        cls._tempdir.cleanup()

    def test_health_returns_json(self) -> None:
        response = self.client.get("/api/health")
        self.assertIn(response.status_code, (200, 503))
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("probes", data)

    def test_config_returns_safe_subset(self) -> None:
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("version", data)
        self.assertEqual(data["billing"]["monthly_price_cents"], 500)
        self.assertIn("fast_model", data)
        self.assertNotIn("smtp_pass", data)
        self.assertNotIn("discord_bot_token", data)

    def test_hit_pixel(self) -> None:
        response = self.client.get("/api/hit?slug=paperboy")
        self.assertIn(response.status_code, (200, 204))

    def test_consent_analytics_accepts_only_pii_free_allowlisted_fields(self) -> None:
        accepted = self.client.post(
            "/api/analytics/event",
            json={
                "event": "begin_checkout",
                "anonymous_id": "pb_1234567890abcdef",
                "properties": {"currency": "USD", "cadence": "weekly", "weekly_day": 4},
            },
        )
        self.assertEqual(accepted.status_code, 204)
        bad_cadence = self.client.post(
            "/api/analytics/event",
            json={
                "event": "subscription_requested",
                "anonymous_id": "pb_1234567890abcdef",
                "properties": {"cadence": "monthly", "weekly_day": 9},
            },
        )
        self.assertEqual(bad_cadence.status_code, 422)
        rejected = self.client.post(
            "/api/analytics/event",
            json={
                "event": "begin_checkout",
                "anonymous_id": "pb_1234567890abcdef",
                "properties": {"email": "reader@example.com"},
            },
        )
        self.assertEqual(rejected.status_code, 422)
        trial = self.client.post(
            "/api/analytics/event",
            json={
                "event": "trial_started",
                "anonymous_id": "pb_1234567890abcdef",
                "properties": {"billing_status": "trialing"},
            },
        )
        self.assertEqual(trial.status_code, 204)
        false_purchase = self.client.post(
            "/api/analytics/event",
            json={
                "event": "purchase",
                "anonymous_id": "pb_1234567890abcdef",
                "properties": {"currency": "USD", "value": 49},
            },
        )
        self.assertEqual(false_purchase.status_code, 422)

    def test_preview_is_rate_limited_and_stream_body_is_bounded(self) -> None:
        headers = {"x-forwarded-for": "203.0.113.77"}
        for _ in range(12):
            response = self.client.post(
                "/api/firehose/preview",
                json={"sources": [], "focus": "agent reliability"},
                headers=headers,
            )
            self.assertEqual(response.status_code, 422)
        limited = self.client.post(
            "/api/firehose/preview",
            json={"sources": [], "focus": "agent reliability"},
            headers=headers,
        )
        self.assertEqual(limited.status_code, 429)

        oversized = self.client.post(
            "/api/firehose/preview",
            content=b"x" * 70_000,
            headers={"x-forwarded-for": "203.0.113.78", "content-type": "application/json"},
        )
        self.assertEqual(oversized.status_code, 413)

    def test_security_headers_are_present(self) -> None:
        response = self.client.get("/api/config")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_signed_hard_bounce_report_suppresses_delivery(self) -> None:
        pending, _token = create_subscription(
            "bounce-api@example.com",
            ["https://example.com/feed"],
            "agent reliability",
            [],
        )
        confirmed = confirm_subscription(confirmation_token(pending))
        assert confirmed is not None
        address = bounce_address(confirmed)
        report = (
            f"To: {address}\r\n"
            "Content-Type: multipart/report; boundary=paperboy\r\n\r\n"
            "--paperboy\r\nContent-Type: text/plain\r\n\r\nDelivery failed.\r\n"
            "--paperboy\r\nContent-Type: message/delivery-status\r\n\r\n"
            "Action: failed\r\nStatus: 5.1.1\r\n\r\n--paperboy--\r\n"
        )
        response = self.client.post("/api/email/bounce", content=report, headers={"Content-Type": "message/rfc822"})
        self.assertEqual(response.status_code, 204)
        updated = get_subscription_by_id(confirmed["id"])
        assert updated is not None
        self.assertTrue(updated["suppressed"])

    def test_signed_resend_bounce_is_idempotent_and_suppresses_delivery(self) -> None:
        pending, _token = create_subscription(
            "resend-api@example.com",
            ["https://example.com/feed"],
            "agent reliability",
            [],
        )
        confirmed = confirm_subscription(confirmation_token(pending))
        assert confirmed is not None
        key = b"paperboy-resend-test-secret-32b"
        old_secret = settings.resend_webhook_secret
        settings.resend_webhook_secret = "whsec_" + base64.b64encode(key).decode()
        try:
            payload = json.dumps(
                {
                    "type": "email.bounced",
                    "data": {
                        "email_id": "resend-email-1",
                        "to": ["resend-api@example.com"],
                    },
                },
                separators=(",", ":"),
            ).encode()
            event_id = "resend-event-1"
            timestamp = str(int(time.time()))
            digest = base64.b64encode(
                hmac.new(
                    key,
                    f"{event_id}.{timestamp}.".encode() + payload,
                    hashlib.sha256,
                ).digest()
            ).decode()
            headers = {
                "content-type": "application/json",
                "svix-id": event_id,
                "svix-timestamp": timestamp,
                "svix-signature": f"v1,{digest}",
            }
            response = self.client.post("/api/email/resend-webhook", content=payload, headers=headers)
            self.assertEqual(response.status_code, 200)
            duplicate = self.client.post("/api/email/resend-webhook", content=payload, headers=headers)
            self.assertTrue(duplicate.json()["duplicate"])
        finally:
            settings.resend_webhook_secret = old_secret
        updated = get_subscription_by_id(confirmed["id"])
        assert updated is not None
        self.assertTrue(updated["suppressed"])

    def test_lead_rejects_invalid_email(self) -> None:
        response = self.client.post("/api/lead", json={"email": "not-an-email"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_lead_accepts_valid_email(self) -> None:
        response = self.client.post(
            "/api/lead",
            json={
                "email": "test@example.com",
                "source": "unit_test",
                "newsletter_sources": ["Test newsletter"],
                "github_repo_urls": ["https://github.com/cgallic/paperboy"],
                "work_focus": "API persistence test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        conn = connect()
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE id = ?",
                (response.json()["lead_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        payload = json.loads(row[0])
        self.assertEqual(payload["extra"]["newsletter_sources"], ["Test newsletter"])
        self.assertEqual(payload["extra"]["github_repo_urls"], ["https://github.com/cgallic/paperboy"])
        self.assertEqual(payload["extra"]["work_focus"], "API persistence test")

    def test_daily_brief_rejects_server_path_override(self) -> None:
        response = self.client.post("/api/daily-brief", json={"fixture": "/nonexistent.json"})
        self.assertEqual(response.status_code, 400)

    def test_daily_brief_with_default_fixture(self) -> None:
        response = self.client.post("/api/daily-brief", json={})
        # Should succeed if examples/daily-brief.sample.json exists
        if response.status_code == 200:
            data = response.json()
            self.assertTrue(data["ok"])
            self.assertIn("text", data)
            self.assertIn("html", data)
            self.assertIn("status", data)


if __name__ == "__main__":
    unittest.main()
