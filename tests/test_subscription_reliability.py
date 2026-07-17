from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from paperboy.confirmation_delivery import run_pending_confirmations
from paperboy.db import connect, init_schema
from paperboy.email.sender import send_raw
from paperboy.firehose_delivery import main as firehose_delivery_main
from paperboy.firehose_delivery import run_daily_deliveries
from paperboy.scheduler import INTERVAL_JOBS
from paperboy.subscriptions import (
    SubscriptionSuppressedError,
    SubscriptionValidationError,
    active_subscriptions,
    allow_subscription_attempt,
    bounce_address,
    claim_billing_webhook,
    confirm_subscription,
    confirmation_token,
    create_subscription,
    create_tracking_token,
    delivery_date_if_due,
    finish_billing_webhook,
    get_subscription,
    next_delivery_at,
    record_tracking_event,
    resolve_click_target,
    set_billing_state,
    suppress_email,
    suppress_from_bounce_address,
    unsuppress_email,
    validate_subscription_payload,
)


def _preview() -> dict:
    return {
        "ok": True,
        "items": [
            {
                "title": "Reliable agents",
                "url": "https://example.com/agents",
                "source": "Builder News",
                "score": 90,
                "why": "Matches reliability",
            }
        ],
        "sources": [{"url": "https://example.com/feed", "status": "ok"}],
        "scanned": 1,
    }


class ReliabilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = os.environ.get("PAPERBOY_ROOT")
        self.old_db = os.environ.get("PAPERBOY_DB")
        self.old_secret = os.environ.get("PAPERBOY_MANAGE_SECRET")
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = self.tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(self.tempdir.name) / "events.db")
        os.environ["PAPERBOY_MANAGE_SECRET"] = "test-secret-is-at-least-thirty-two-bytes-long"
        init_schema()

    def tearDown(self) -> None:
        for key, value in (
            ("PAPERBOY_ROOT", self.old_root),
            ("PAPERBOY_DB", self.old_db),
            ("PAPERBOY_MANAGE_SECRET", self.old_secret),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def create(
        self,
        email: str = "reader@example.com",
        timezone_name: str = "UTC",
        cadence: str = "daily",
        weekly_day: int = 0,
    ) -> tuple[dict, str]:
        return create_subscription(
            email,
            ["https://example.com/feed"],
            "agent reliability",
            ["gossip"],
            {"utm_source": "test"},
            timezone_name,
            cadence,
            weekly_day,
        )

    def confirm_and_entitle(self) -> tuple[dict, str]:
        subscription, manage_token = self.create()
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
        return entitled, manage_token


class SchemaMigrationTests(unittest.TestCase):
    def test_legacy_schema_is_migrated_additively_and_held_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "legacy.db"
            conn = sqlite3.connect(database)
            conn.executescript(
                """
                CREATE TABLE firehose_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE,
                    sources_json TEXT NOT NULL, focus TEXT NOT NULL, ignore_json TEXT NOT NULL,
                    attribution_json TEXT NOT NULL DEFAULT '{}', token_hash TEXT NOT NULL UNIQUE,
                    token_nonce TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, unsubscribed_at TEXT
                );
                CREATE TABLE firehose_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, subscription_id INTEGER NOT NULL,
                    delivery_date TEXT NOT NULL, attempted_at TEXT NOT NULL, completed_at TEXT,
                    status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', item_count INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(subscription_id, delivery_date)
                );
                INSERT INTO firehose_subscriptions
                    (email,sources_json,focus,ignore_json,token_hash,token_nonce,active,created_at,updated_at)
                VALUES ('legacy@example.com','[]','legacy','[]','hash','nonce',1,'2026-01-01Z','2026-01-01Z');
                INSERT INTO firehose_subscriptions
                    (email,sources_json,focus,ignore_json,token_hash,token_nonce,active,created_at,updated_at,unsubscribed_at)
                VALUES ('stopped@example.com','[]','legacy','[]','hash2','nonce2',0,'2026-01-01Z','2026-01-01Z','2026-01-02Z');
                """
            )
            conn.commit()
            conn.close()
            old_db = os.environ.get("PAPERBOY_DB")
            os.environ["PAPERBOY_DB"] = str(database)
            try:
                init_schema()
                migrated = connect()
                try:
                    columns = {row[1] for row in migrated.execute("PRAGMA table_info(firehose_subscriptions)")}
                    active = migrated.execute(
                        "SELECT active FROM firehose_subscriptions WHERE email='legacy@example.com'"
                    ).fetchone()[0]
                    stopped_status = migrated.execute(
                        "SELECT verification_status FROM firehose_subscriptions WHERE email='stopped@example.com'"
                    ).fetchone()[0]
                finally:
                    migrated.close()
            finally:
                if old_db is None:
                    os.environ.pop("PAPERBOY_DB", None)
                else:
                    os.environ["PAPERBOY_DB"] = old_db
            self.assertIn("verification_status", columns)
            self.assertIn("billing_status", columns)
            self.assertIn("timezone", columns)
            self.assertIn("cadence", columns)
            self.assertIn("weekly_day", columns)
            self.assertEqual(active, 0)
            self.assertEqual(stopped_status, "expired")


class VerificationTests(ReliabilityTestCase):
    def test_validation_requires_consent_and_accepts_iana_timezone(self) -> None:
        result = validate_subscription_payload(
            {
                "email": "Reader@Example.com",
                "sources": ["https://example.com/feed"],
                "focus": "agents",
                "consent": True,
                "timezone": "America/New_York",
            }
        )
        self.assertEqual(result[0], "reader@example.com")
        self.assertEqual(result[5], "America/New_York")
        self.assertEqual(result[6], "daily")
        self.assertEqual(result[7], 0)
        with self.assertRaises(SubscriptionValidationError):
            validate_subscription_payload(
                {
                    "email": "reader@example.com",
                    "sources": ["https://example.com/feed"],
                    "focus": "agents",
                }
            )
        with self.assertRaises(SubscriptionValidationError):
            validate_subscription_payload(
                {
                    "email": "reader@example.com",
                    "sources": ["https://example.com/feed"],
                    "focus": "agents",
                    "consent": True,
                    "timezone": "Mars/Olympus_Mons",
                }
            )
        with self.assertRaises(SubscriptionValidationError):
            validate_subscription_payload(
                {
                    "email": "reader@example.com",
                    "sources": ["https://example.com/feed"],
                    "focus": "agents",
                    "consent": True,
                    "cadence": "monthly",
                }
            )

    def test_confirmation_is_distinct_pending_and_billing_gated(self) -> None:
        subscription, manage_token = self.create()
        verify_token = confirmation_token(subscription)
        self.assertNotEqual(manage_token, verify_token)
        self.assertFalse(subscription["active"])
        self.assertEqual(subscription["verification_status"], "pending")
        self.assertEqual(active_subscriptions(), [])

        sent: list[tuple[tuple, dict]] = []

        def sender(*args, **kwargs) -> dict:
            sent.append((args, kwargs))
            return {"ok": True, "detail": "sent", "message_id": "confirmation"}

        summary = run_pending_confirmations(sender=sender)
        self.assertEqual(summary, {"claimed": 1, "sent": 1, "failed": 0})
        self.assertIn("/?confirm=", sent[0][0][1])
        confirmed = confirm_subscription(verify_token)
        self.assertIsNotNone(confirmed)
        assert confirmed is not None
        self.assertTrue(confirmed["active"])
        self.assertTrue(confirmed["_newly_verified"])
        repeated = confirm_subscription(verify_token)
        assert repeated is not None
        self.assertFalse(repeated["_newly_verified"])
        self.assertEqual(confirmed["billing_status"], "unpaid")
        self.assertEqual(active_subscriptions(), [])
        set_billing_state(
            int(confirmed["id"]),
            "trialing",
            trial_ends_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat()
            .replace("+00:00", "Z"),
        )
        self.assertEqual(len(active_subscriptions()), 1)

    def test_expired_or_missing_trial_end_never_grants_delivery(self) -> None:
        subscription, _token = self.create()
        confirmed = confirm_subscription(confirmation_token(subscription))
        assert confirmed is not None
        set_billing_state(int(confirmed["id"]), "trialing")
        self.assertEqual(active_subscriptions(), [])
        set_billing_state(
            int(confirmed["id"]),
            "trialing",
            trial_ends_at="2020-01-01T00:00:00Z",
        )
        self.assertEqual(active_subscriptions(), [])

    def test_expired_confirmation_cannot_activate(self) -> None:
        subscription, _token = self.create()
        expiry = datetime.fromisoformat(str(subscription["verification_expires_at"]).replace("Z", "+00:00"))
        result = confirm_subscription(confirmation_token(subscription), now=expiry + timedelta(seconds=1))
        self.assertIsNone(result)

    def test_confirmation_failure_retries_stop_after_three_attempts(self) -> None:
        self.create()
        start = datetime.now(timezone.utc) + timedelta(seconds=1)

        def failed(*_args, **_kwargs) -> dict:
            return {"ok": False, "detail": "smtp unavailable", "message_id": None}

        first = run_pending_confirmations(sender=failed, now=start)
        second = run_pending_confirmations(sender=failed, now=start + timedelta(minutes=16))
        third = run_pending_confirmations(sender=failed, now=start + timedelta(minutes=47))
        fourth = run_pending_confirmations(sender=failed, now=start + timedelta(hours=3))
        self.assertEqual([first["failed"], second["failed"], third["failed"]], [1, 1, 1])
        self.assertEqual(fourth["claimed"], 0)


class ConsentAndAbuseTests(ReliabilityTestCase):
    def test_subscription_attempt_limits_store_only_hmac_hashes(self) -> None:
        start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
        results = [allow_subscription_attempt("203.0.113.7", "reader@example.com", now=start) for _ in range(4)]
        self.assertEqual(results, [True, True, True, False])
        self.assertTrue(
            allow_subscription_attempt("203.0.113.7", "other@example.com", now=start + timedelta(hours=1, seconds=1))
        )
        conn = connect()
        try:
            rows = conn.execute("SELECT ip_hash, email_hash FROM firehose_subscription_attempts").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows)
        self.assertNotIn("203.0.113.7", str(rows))
        self.assertNotIn("reader@example.com", str(rows))

    def test_suppression_blocks_delivery_and_resubscribe(self) -> None:
        subscription, token = self.confirm_and_entitle()
        self.assertEqual(len(active_subscriptions()), 1)
        suppress_email(str(subscription["email"]), "hard_bounce", "550 rejected")
        self.assertEqual(active_subscriptions(), [])
        with self.assertRaises(SubscriptionSuppressedError):
            self.create()
        self.assertTrue(unsuppress_email("reader@example.com"))
        self.assertTrue(get_subscription(token)["active"])
        self.assertEqual(len(active_subscriptions()), 1)
        with self.assertRaises(SubscriptionSuppressedError):
            self.create()


class TimezoneAndDeliveryTests(ReliabilityTestCase):
    def test_iana_timezone_targets_0800_local(self) -> None:
        subscription, _token = self.create(timezone_name="America/New_York")
        before = datetime(2026, 7, 16, 11, 59, tzinfo=timezone.utc)
        after = datetime(2026, 7, 16, 12, 1, tzinfo=timezone.utc)
        self.assertIsNone(delivery_date_if_due(subscription, now=before))
        self.assertEqual(next_delivery_at(subscription, now=before).hour, 12)
        self.assertEqual(delivery_date_if_due(subscription, now=after), date(2026, 7, 16))
        self.assertEqual(next_delivery_at(subscription, now=after).date(), date(2026, 7, 17))

    def test_weekly_cadence_targets_selected_weekday_at_0800(self) -> None:
        subscription, _token = self.create(cadence="weekly", weekly_day=0)
        sunday = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
        monday_before = datetime(2026, 7, 20, 7, 59, tzinfo=timezone.utc)
        monday_after = datetime(2026, 7, 20, 8, 1, tzinfo=timezone.utc)
        tuesday = datetime(2026, 7, 21, 8, 1, tzinfo=timezone.utc)

        self.assertEqual(next_delivery_at(subscription, now=sunday), datetime(2026, 7, 20, 8, tzinfo=timezone.utc))
        self.assertIsNone(delivery_date_if_due(subscription, now=monday_before))
        self.assertEqual(delivery_date_if_due(subscription, now=monday_after), date(2026, 7, 20))
        self.assertEqual(
            next_delivery_at(subscription, now=monday_after), datetime(2026, 7, 27, 8, tzinfo=timezone.utc)
        )
        self.assertIsNone(delivery_date_if_due(subscription, now=tuesday))

    def test_weekly_cadence_preserves_0800_local_across_dst(self) -> None:
        subscription, _token = self.create(
            timezone_name="America/New_York", cadence="weekly", weekly_day=6
        )
        before_fall_back = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        after_sunday_delivery = datetime(2026, 11, 1, 13, 1, tzinfo=timezone.utc)

        self.assertEqual(
            next_delivery_at(subscription, now=before_fall_back),
            datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            delivery_date_if_due(subscription, now=after_sunday_delivery),
            date(2026, 11, 1),
        )
        self.assertEqual(
            next_delivery_at(subscription, now=after_sunday_delivery),
            datetime(2026, 11, 8, 13, 0, tzinfo=timezone.utc),
        )

    def test_corrupt_stored_schedule_falls_back_to_daily(self) -> None:
        subscription, token = self.create()
        conn = connect()
        try:
            conn.execute(
                "UPDATE firehose_subscriptions SET cadence='monthly', weekly_day=99 WHERE id=?",
                (subscription["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        decoded = get_subscription(token)
        assert decoded is not None
        self.assertEqual(decoded["cadence"], "daily")
        self.assertEqual(decoded["weekly_day"], 0)

    def test_weekly_scheduler_skips_other_days_and_sends_selected_day(self) -> None:
        pending, _token = self.create(cadence="weekly", weekly_day=0)
        confirmed = confirm_subscription(confirmation_token(pending))
        assert confirmed is not None
        entitled = set_billing_state(
            int(confirmed["id"]),
            "trialing",
            trial_ends_at="2026-07-27T08:00:00Z",
        )
        assert entitled is not None
        sent: list[tuple[tuple, dict]] = []

        def sender(*args, **kwargs) -> dict:
            sent.append((args, kwargs))
            return {"ok": True, "detail": "sent", "message_id": None}

        sunday = run_daily_deliveries(
            now=datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
            preview_builder=lambda *_: _preview(),
            sender=sender,
        )
        monday = run_daily_deliveries(
            now=datetime(2026, 7, 20, 8, 1, tzinfo=timezone.utc),
            preview_builder=lambda *_: _preview(),
            sender=sender,
        )

        self.assertEqual(sunday["skipped"], 1)
        self.assertEqual(monday["sent"], 1)
        self.assertEqual(len(sent), 1)
        self.assertIn("Paperboy weekly rollup", sent[0][0][0])

    def test_delivery_retries_three_times_then_never_duplicates_success(self) -> None:
        self.confirm_and_entitle()
        start = datetime(2026, 7, 16, 8, 1, tzinfo=timezone.utc)

        def failed(*_args, **_kwargs) -> dict:
            return {"ok": False, "detail": "smtp unavailable", "message_id": None}

        first = run_daily_deliveries(now=start, preview_builder=lambda *_: _preview(), sender=failed)
        too_soon = run_daily_deliveries(
            now=start + timedelta(minutes=10), preview_builder=lambda *_: _preview(), sender=failed
        )
        second = run_daily_deliveries(
            now=start + timedelta(minutes=16), preview_builder=lambda *_: _preview(), sender=failed
        )
        third = run_daily_deliveries(
            now=start + timedelta(minutes=47), preview_builder=lambda *_: _preview(), sender=failed
        )
        exhausted = run_daily_deliveries(
            now=start + timedelta(hours=4), preview_builder=lambda *_: _preview(), sender=failed
        )
        self.assertEqual(first["failed"], 1)
        self.assertEqual(too_soon["skipped"], 1)
        self.assertEqual(second["failed"], 1)
        self.assertEqual(third["failed"], 1)
        self.assertEqual(exhausted["skipped"], 1)
        conn = connect()
        try:
            attempts = conn.execute(
                "SELECT attempt_count FROM firehose_deliveries WHERE delivery_date='2026-07-16'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(attempts, 3)

        sent_calls: list[dict] = []

        def sent(*_args, **kwargs) -> dict:
            sent_calls.append(kwargs)
            return {"ok": True, "detail": "sent", "message_id": kwargs["message_id"]}

        next_day = start + timedelta(days=1)
        sent_once = run_daily_deliveries(now=next_day, preview_builder=lambda *_: _preview(), sender=sent)
        duplicate = run_daily_deliveries(
            now=next_day + timedelta(hours=1), preview_builder=lambda *_: _preview(), sender=sent
        )
        self.assertEqual(sent_once["sent"], 1)
        self.assertEqual(duplicate["skipped"], 1)
        self.assertEqual(len(sent_calls), 1)
        self.assertTrue(sent_calls[0]["unsubscribe_url"].startswith("https://"))

    def test_email_tracking_requires_optional_analytics_consent(self) -> None:
        self.confirm_and_entitle()
        sent_messages: list[tuple] = []

        def sent(*args, **_kwargs) -> dict:
            sent_messages.append(args)
            return {"ok": True, "detail": "sent", "message_id": None}

        run_daily_deliveries(
            now=datetime(2026, 7, 16, 8, 1, tzinfo=timezone.utc),
            preview_builder=lambda *_: _preview(),
            sender=sent,
        )
        self.assertIn("https://example.com/agents", sent_messages[0][1])
        self.assertNotIn("/api/t/", sent_messages[0][1])
        self.assertNotIn("/api/t/", sent_messages[0][2])
        conn = connect()
        try:
            token_count = conn.execute("SELECT COUNT(*) FROM firehose_tracking_tokens").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(token_count, 0)


class TrackingAndEmailTests(ReliabilityTestCase):
    def test_signed_bounce_address_suppresses_only_its_subscription(self) -> None:
        subscription, _token = self.confirm_and_entitle()
        address = bounce_address(subscription)
        self.assertNotIn("reader@example.com", address)
        self.assertFalse(suppress_from_bounce_address(address.replace("a", "b", 1)))
        self.assertEqual(len(active_subscriptions()), 1)
        self.assertTrue(suppress_from_bounce_address(address))
        self.assertEqual(active_subscriptions(), [])

    def test_tracking_tokens_are_hashed_and_click_target_is_server_side(self) -> None:
        subscription, _token = self.create()
        click = create_tracking_token(int(subscription["id"]), "click", target_url="https://example.com/story")
        opened = create_tracking_token(int(subscription["id"]), "open")
        self.assertEqual(resolve_click_target(click), "https://example.com/story")
        self.assertIsNone(resolve_click_target(opened))
        self.assertTrue(record_tracking_event(click, "click", metadata={"ua": "test"}))
        self.assertTrue(record_tracking_event(opened, "open"))
        self.assertFalse(record_tracking_event(click + "x", "click"))
        self.assertIsNone(resolve_click_target("not-ascii-\u2603"))
        self.assertFalse(record_tracking_event("not-ascii-\u2603", "open"))
        conn = connect()
        try:
            stored_hash, events = conn.execute(
                "SELECT token_hash, (SELECT COUNT(*) FROM firehose_tracking_events) "
                "FROM firehose_tracking_tokens WHERE kind='click'"
            ).fetchone()
        finally:
            conn.close()
        self.assertNotEqual(stored_hash, click)
        self.assertEqual(events, 2)
        with self.assertRaises(ValueError):
            create_tracking_token(int(subscription["id"]), "click", target_url="javascript:alert(1)")

    def test_send_raw_emits_one_click_unsubscribe_and_stable_message_id(self) -> None:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with patch("paperboy.email.sender._create_smtp_connection", return_value=connection):
            result = send_raw(
                "Subject",
                "Text",
                "<p>HTML</p>",
                to="reader@example.com",
                unsubscribe_url="https://newpaperboy.com/api/unsubscribe/token",
                message_id="<stable@newpaperboy.com>",
            )
        message = connection.sendmail.call_args.args[2]
        self.assertIn("List-Unsubscribe: <https://newpaperboy.com/api/unsubscribe/token>", message)
        self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", message)
        self.assertIn("Message-ID: <stable@newpaperboy.com>", message)
        self.assertEqual(result["message_id"], "<stable@newpaperboy.com>")


class BillingPrimitiveTests(ReliabilityTestCase):
    def test_billing_state_and_failed_webhook_reclaim(self) -> None:
        subscription, manage_token = self.create()
        updated = set_billing_state(
            int(subscription["id"]),
            "active",
            customer_id="cus_test",
            billing_subscription_id="sub_test",
            paid_at="2026-07-16T12:00:00Z",
        )
        self.assertEqual(updated["billing_status"], "active")
        self.assertEqual(get_subscription(manage_token)["billing_customer_id"], "cus_test")
        self.assertTrue(claim_billing_webhook("evt_1", "checkout.completed"))
        self.assertFalse(claim_billing_webhook("evt_1", "checkout.completed"))
        finish_billing_webhook("evt_1", "failed", "temporary database error")
        self.assertTrue(claim_billing_webhook("evt_1", "checkout.completed"))
        finish_billing_webhook("evt_1", "processed")
        self.assertFalse(claim_billing_webhook("evt_1", "checkout.completed"))

    def test_stuck_processing_webhook_is_reclaimed_after_lease(self) -> None:
        start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
        self.assertTrue(
            claim_billing_webhook("evt_stuck", "customer.subscription.updated", now=start)
        )
        self.assertFalse(
            claim_billing_webhook(
                "evt_stuck",
                "customer.subscription.updated",
                now=start + timedelta(minutes=9),
            )
        )
        self.assertTrue(
            claim_billing_webhook(
                "evt_stuck",
                "customer.subscription.updated",
                now=start + timedelta(minutes=11),
            )
        )

    def test_delivery_cli_exits_nonzero_when_any_delivery_failed(self) -> None:
        with patch(
            "paperboy.firehose_delivery.run_daily_deliveries",
            return_value={"active": 1, "sent": 0, "failed": 1, "skipped": 0},
        ), self.assertRaises(SystemExit) as caught:
            firehose_delivery_main()
        self.assertEqual(caught.exception.code, 1)

    def test_scheduler_runs_confirmation_and_due_delivery_frequently(self) -> None:
        self.assertIn(("paperboy.confirmation_delivery", 5), INTERVAL_JOBS)
        self.assertIn(("paperboy.firehose_delivery", 5), INTERVAL_JOBS)


if __name__ == "__main__":
    unittest.main()
