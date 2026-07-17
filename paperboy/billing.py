"""Stripe-hosted billing for Paperboy subscriptions.

Checkout owns card collection. Paperboy only stores Stripe identifiers and the
entitlement state needed by the delivery scheduler.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import stripe

from paperboy.config import settings
from paperboy.db import connect
from paperboy.subscriptions import get_subscription_by_id, set_billing_state


class BillingUnavailableError(RuntimeError):
    """Billing is not configured or Stripe did not return a safe URL."""


class BillingStateError(ValueError):
    """The subscription cannot enter the requested billing flow."""


def _stripe_ready() -> None:
    if not settings.billing_enabled:
        raise BillingUnavailableError("checkout is temporarily unavailable")
    stripe.api_key = settings.stripe_secret_key


def _safe_stripe_url(value: Any, *, portal: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise BillingUnavailableError("Stripe did not return a checkout URL")
    parsed = urlsplit(value)
    allowed = {"billing.stripe.com"} if portal else {"checkout.stripe.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username:
        raise BillingUnavailableError("Stripe did not return a safe checkout URL")
    return value


def create_checkout(subscription: dict[str, Any]) -> str:
    """Create a card-required seven-day subscription trial."""
    _stripe_ready()
    if subscription.get("verification_status") != "verified" or not subscription.get("active"):
        raise BillingStateError("verify the email address before checkout")
    billing_status = str(subscription.get("billing_status") or "unpaid")
    if billing_status in {"trialing", "active", "past_due"}:
        raise BillingStateError("manage the existing billing account instead")
    price_id = settings.stripe_price_id
    if not price_id:
        raise BillingUnavailableError("checkout is temporarily unavailable")

    metadata = {"paperboy_subscription_id": str(subscription["id"])}
    customer_args: dict[str, Any]
    if subscription.get("billing_customer_id"):
        customer_args = {"customer": subscription["billing_customer_id"]}
    else:
        customer_args = {"customer_email": subscription["email"]}
    session = stripe.checkout.Session.create(
        **customer_args,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        payment_method_collection="always",
        client_reference_id=str(subscription["id"]),
        metadata=metadata,
        subscription_data={
            "trial_period_days": settings.stripe_trial_days,
            "metadata": metadata,
        },
        allow_promotion_codes=True,
        success_url=f"{settings.public_url.rstrip('/')}?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.public_url.rstrip('/')}?billing=cancelled",
        idempotency_key=(
            "paperboy-checkout-"
            + hashlib.sha256(
                f"{subscription['id']}:{subscription['updated_at']}".encode()
            ).hexdigest()
        ),
    )
    return _safe_stripe_url(getattr(session, "url", None))


def create_customer_portal(subscription: dict[str, Any]) -> str:
    _stripe_ready()
    customer_id = subscription.get("billing_customer_id")
    if not customer_id:
        raise BillingStateError("no billing account exists for this subscription")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=settings.public_url.rstrip("/"),
    )
    return _safe_stripe_url(getattr(session, "url", None), portal=True)


def construct_event(payload: bytes, signature: str) -> Any:
    _stripe_ready()
    if not signature:
        raise ValueError("missing Stripe signature")
    return stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _metadata_id(obj: Any) -> int | None:
    metadata = _value(obj, "metadata", {}) or {}
    raw = _value(metadata, "paperboy_subscription_id")
    if raw is None:
        raw = _value(obj, "client_reference_id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _subscription_for_external_id(external_id: str | None) -> dict[str, Any] | None:
    if not external_id:
        return None
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM firehose_subscriptions WHERE billing_subscription_id = ?",
            (external_id,),
        ).fetchone()
    finally:
        conn.close()
    return get_subscription_by_id(int(row[0])) if row is not None else None


def _timestamp(value: Any) -> str | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _mapped_status(value: Any) -> str:
    status = str(value or "")
    if status == "trialing":
        return "trialing"
    if status == "active":
        return "active"
    if status in {"canceled", "incomplete_expired"}:
        return "canceled"
    return "past_due"


def _event_identity(event: Any) -> tuple[str, int] | None:
    event_id = str(_value(event, "id", ""))
    try:
        created = int(_value(event, "created"))
    except (TypeError, ValueError):
        return None
    if not event_id or created < 0:
        return None
    return event_id, created


def _apply_ordered_state(
    subscription_id: int,
    status: str,
    event: Any,
    **values: Any,
) -> bool:
    identity = _event_identity(event)
    if identity is None:
        return False
    event_id, event_created = identity
    updated = set_billing_state(
        subscription_id,
        status,
        event_created=event_created,
        event_id=event_id,
        **values,
    )
    return bool(updated and updated.get("_billing_event_applied", False))


def apply_event(event: Any) -> tuple[str, int | None]:
    """Apply a verified Stripe event and return (outcome, subscription id)."""
    event_type = str(_value(event, "type", ""))
    data = _value(event, "data", {}) or {}
    obj = _value(data, "object", {}) or {}

    if event_type == "checkout.session.completed":
        subscription_id = _metadata_id(obj)
        if subscription_id is None or get_subscription_by_id(subscription_id) is None:
            return "ignored", None
        # Checkout does not carry the authoritative trial end. Entitlement is
        # granted by customer.subscription.created/updated instead.
        return "ignored", subscription_id

    if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        external_subscription = _value(obj, "id")
        subscription_id = _metadata_id(obj)
        subscription = (
            get_subscription_by_id(subscription_id) if subscription_id is not None else None
        ) or _subscription_for_external_id(external_subscription)
        if subscription is None:
            return "ignored", None
        mapped = "canceled" if event_type.endswith("deleted") else _mapped_status(_value(obj, "status"))
        trial_ends_at = _timestamp(_value(obj, "trial_end"))
        if mapped == "trialing" and trial_ends_at is None:
            return "ignored", int(subscription["id"])
        applied = _apply_ordered_state(
            int(subscription["id"]),
            mapped,
            event,
            customer_id=_value(obj, "customer"),
            billing_subscription_id=external_subscription,
            trial_ends_at=trial_ends_at,
        )
        return ("processed" if applied else "ignored"), int(subscription["id"])

    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        external_subscription = _value(obj, "subscription")
        if not external_subscription:
            parent = _value(obj, "parent", {}) or {}
            details = _value(parent, "subscription_details", {}) or {}
            external_subscription = _value(details, "subscription")
        subscription = _subscription_for_external_id(external_subscription)
        if subscription is None:
            return "ignored", None
        amount_paid = int(_value(obj, "amount_paid", 0) or 0)
        status = "past_due"
        if event_type == "invoice.paid":
            status = (
                "trialing"
                if subscription["billing_status"] == "trialing" and amount_paid <= 0
                else "active"
            )
        applied = _apply_ordered_state(
            int(subscription["id"]),
            status,
            event,
            trial_ends_at=(
                subscription["trial_ends_at"] if status == "trialing" else None
            ),
            paid_at=_timestamp(_value(_value(obj, "status_transitions", {}) or {}, "paid_at")),
        )
        return ("processed" if applied else "ignored"), int(subscription["id"])

    return "ignored", None
