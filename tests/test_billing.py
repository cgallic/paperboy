from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paperboy.billing import BillingUnavailableError, apply_event, create_checkout
from paperboy.config import settings
from paperboy.db import init_schema
from paperboy.subscriptions import (
    confirm_subscription,
    confirmation_token,
    create_subscription,
    get_subscription_by_id,
)


class BillingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = os.environ.get("PAPERBOY_ROOT")
        self.old_db = os.environ.get("PAPERBOY_DB")
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = self.tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(self.tempdir.name) / "events.db")
        init_schema()
        pending, _token = create_subscription(
            "reader@example.com",
            ["https://example.com/feed"],
            "agent reliability",
            [],
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

    def billing_settings(self):
        return patch.multiple(
            settings,
            stripe_secret_key="sk_test_example",
            stripe_webhook_secret="whsec_example",
            stripe_price_id="price_example",
            stripe_trial_days=7,
        )

    def test_checkout_is_card_required_and_uses_configured_price(self) -> None:
        with self.billing_settings(), patch(
            "paperboy.billing.stripe.checkout.Session.create",
            return_value=SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123"),
        ) as create:
            url = create_checkout(self.subscription)
        self.assertTrue(url.startswith("https://checkout.stripe.com/"))
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["payment_method_collection"], "always")
        self.assertEqual(kwargs["line_items"], [{"price": "price_example", "quantity": 1}])
        self.assertEqual(kwargs["subscription_data"]["trial_period_days"], 7)
        self.assertTrue(kwargs["idempotency_key"].startswith("paperboy-checkout-"))
        self.assertNotIn("reader@example.com", kwargs["success_url"])

    def test_checkout_rejects_non_stripe_redirect(self) -> None:
        with self.billing_settings(), patch(
            "paperboy.billing.stripe.checkout.Session.create",
            return_value=SimpleNamespace(url="https://attacker.example/checkout"),
        ), self.assertRaises(BillingUnavailableError):
            create_checkout(self.subscription)

    def test_checkout_webhook_grants_trial_entitlement(self) -> None:
        outcome, subscription_id = apply_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "client_reference_id": str(self.subscription["id"]),
                        "customer": "cus_123",
                        "subscription": "sub_123",
                    }
                },
            }
        )
        self.assertEqual((outcome, subscription_id), ("processed", self.subscription["id"]))
        updated = get_subscription_by_id(self.subscription["id"])
        assert updated is not None
        self.assertEqual(updated["billing_status"], "trialing")
        self.assertEqual(updated["billing_customer_id"], "cus_123")
        self.assertEqual(updated["billing_subscription_id"], "sub_123")


if __name__ == "__main__":
    unittest.main()
