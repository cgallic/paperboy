"""FastAPI backend for the Paperboy hosted product.

Serves:
  - /api/health          — liveness + subsystem probes
  - /api/lead            — founding-pilot lead capture
  - /api/hit             — lightweight visit pixel
  - /api/daily-brief     — render the bundled sanitized sample
  - /api/firehose/*      — preview, subscribe, manage, and unsubscribe
  - /api/config          — validated runtime config (safe subset)

Static files from product/ are served at / so the landing page works.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import sqlite3
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from paperboy.billing import (
    BillingStateError,
    BillingUnavailableError,
    apply_event,
    construct_event,
    create_checkout,
    create_customer_portal,
)
from paperboy.config import settings
from paperboy.db import connect, init_schema
from paperboy.firehose import (
    MAX_REQUEST_BYTES,
    PreviewValidationError,
    build_firehose_preview,
    validate_preview_payload,
)
from paperboy.health import run_all
from paperboy.lifecycle_delivery import enqueue_lifecycle_event
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import (
    SubscriptionSuppressedError,
    SubscriptionValidationError,
    allow_subscription_attempt,
    billing_entitled,
    claim_billing_webhook,
    confirm_subscription,
    create_subscription,
    finish_billing_webhook,
    get_subscription,
    get_subscription_by_email,
    get_subscription_by_id,
    management_token,
    management_urls,
    next_delivery_at,
    record_tracking_event,
    resolve_click_target,
    suppress_email,
    suppress_from_bounce_address,
    unsubscribe,
    validate_subscription_payload,
)

logger = get_logger("api")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_schema()
    logger.info("api_startup")
    yield
    logger.info("api_shutdown")


app = FastAPI(
    title="Paperboy API",
    description="Backend for the Paperboy Daily Intelligence Brief",
    version="0.4.0",
    lifespan=lifespan,
)

# Single-process limits are sufficient while Paperboy runs one API worker.
_last_hit: dict[str, float] = {}
_rate_buckets: dict[tuple[str, str], list[float]] = {}
_rate_lock = asyncio.Lock()
_preview_semaphore = asyncio.Semaphore(4)


def _client_identity(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


async def _allow_rate(
    request: Request,
    scope: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    now = time.monotonic()
    key = (scope, _client_identity(request))
    cutoff = now - window_seconds
    async with _rate_lock:
        recent = [timestamp for timestamp in _rate_buckets.get(key, []) if timestamp >= cutoff]
        if len(recent) >= limit:
            _rate_buckets[key] = recent
            return False
        recent.append(now)
        _rate_buckets[key] = recent
        if len(_rate_buckets) > 4096:
            for stale_key in list(_rate_buckets)[:1024]:
                if not any(timestamp >= cutoff for timestamp in _rate_buckets[stale_key]):
                    _rate_buckets.pop(stale_key, None)
        return True


async def _read_bounded_body(request: Request, limit: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > limit:
                raise HTTPException(status_code=413, detail="request body is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid content-length") from None
    chunks: list[bytes] = []
    size = 0
    try:
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(status_code=413, detail="request body is too large")
            chunks.append(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="could not read request body") from exc
    return b"".join(chunks)


async def _read_json_body(request: Request, limit: int) -> object:
    raw = await _read_bounded_body(request, limit)
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc


def _verify_resend_signature(raw: bytes, request: Request) -> str:
    secret = settings.resend_webhook_secret or ""
    message_id = request.headers.get("svix-id", "")
    timestamp_text = request.headers.get("svix-timestamp", "")
    signatures = request.headers.get("svix-signature", "")
    if not secret.startswith("whsec_") or not message_id or not timestamp_text or not signatures:
        raise ValueError("missing Resend webhook signature")
    try:
        timestamp = int(timestamp_text)
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid Resend webhook signature metadata") from exc
    if abs(int(time.time()) - timestamp) > 300:
        raise ValueError("stale Resend webhook")
    signed = f"{message_id}.{timestamp_text}.".encode() + raw
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    supplied = [part[3:] for part in signatures.split() if part.startswith("v1,")]
    if not supplied or not any(hmac.compare_digest(expected, value) for value in supplied):
        raise ValueError("invalid Resend webhook signature")
    return message_id


def _claim_email_provider_event(event_id: str, event_type: str) -> bool:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    stale = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 600))
    conn = connect()
    try:
        row = conn.execute(
            "SELECT status,received_at FROM email_provider_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO email_provider_events "
                "(event_id,event_type,received_at,status) VALUES (?,?,?,'processing')",
                (event_id, event_type, now),
            )
            conn.commit()
            return True
        if row["status"] == "failed" or (
            row["status"] == "processing" and str(row["received_at"]) < stale
        ):
            conn.execute(
                "UPDATE email_provider_events SET status='processing', received_at=?, detail='' "
                "WHERE event_id=?",
                (now, event_id),
            )
            conn.commit()
            return True
        return False
    finally:
        conn.close()


def _finish_email_provider_event(
    event_id: str,
    status: str,
    *,
    subscription_id: int | None = None,
    provider_email_id: str | None = None,
    detail: str = "",
) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = connect()
    try:
        conn.execute(
            "UPDATE email_provider_events SET status=?, subscription_id=?, provider_email_id=?, "
            "processed_at=?, detail=? WHERE event_id=?",
            (status, subscription_id, provider_email_id, now, detail[:120], event_id),
        )
        conn.commit()
    finally:
        conn.close()


def _append_product_event(event_type: str, payload: dict) -> int:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT INTO events (ts, source, type, actor, payload_json, attachment_uri, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, "paperboy-api", event_type, payload.get("email"), json.dumps(payload, ensure_ascii=False), None, now),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise sqlite3.DatabaseError("event insert did not return an id")
        return int(cursor.lastrowid)
    finally:
        conn.close()


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    t0 = time.time()
    response = await call_next(request)
    elapsed = (time.time() - t0) * 1000
    logger.info(
        "request",
        extra={
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "elapsed_ms": round(elapsed, 2),
        },
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> JSONResponse:
    report = run_all()
    overall = report.pop("overall")
    code = 200 if overall["status"] == "healthy" else 503
    return JSONResponse(
        content={"status": overall["status"], "probes": {name: probe["status"] for name, probe in report.items()}},
        status_code=code,
    )


@app.post("/api/lead")
async def capture_lead(request: Request) -> JSONResponse:
    try:
        body = await _read_json_body(request, 32_000)
    except HTTPException as exc:
        if exc.status_code == 400:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        raise
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    email = str(body.get("email", "")).strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return JSONResponse({"ok": False, "error": "invalid_email"}, status_code=400)
    if body.get("source") == "paperboy_email_verified":
        subscription = await asyncio.to_thread(get_subscription_by_email, email)
        if subscription is None or subscription.get("verification_status") != "verified":
            return JSONResponse({"ok": False, "error": "email_not_verified"}, status_code=403)

    lead = {
        "slug": body.get("slug", "paperboy"),
        "email": email,
        "message": body.get("message", ""),
        "offer": body.get("offer", ""),
        "price": body.get("price", ""),
        "source": body.get("source", ""),
        "page": body.get("page", ""),
        "campaign": {k: v for k, v in body.items() if k.startswith(("utm_", "ref", "gclid", "fbclid"))},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip": request.client.host if request.client else None,
        "ua": request.headers.get("user-agent", ""),
        "extra": {
            key: value
            for key, value in body.items()
            if key
            not in {
                "slug",
                "email",
                "message",
                "offer",
                "price",
                "source",
                "page",
                "ref",
                "gclid",
                "fbclid",
            }
            and not key.startswith("utm_")
        },
    }
    try:
        lead_id = _append_product_event("lead", lead)
    except (OSError, sqlite3.Error):
        logger.exception("lead_persistence_failed", extra={"event": "lead_persistence_failed"})
        return JSONResponse({"ok": False, "error": "persistence_failed"}, status_code=503)
    logger.info("lead_captured", extra={"event": "lead_captured", "email": email, "source": lead["source"]})
    return JSONResponse({"ok": True, "lead_id": lead_id})


_ANALYTICS_EVENTS = {
    "page_view",
    "signup_started",
    "subscription_requested",
    "email_verified",
    "begin_checkout",
    "trial_started",
}
_ANALYTICS_PROPERTIES = {"source_count", "billing_status", "currency", "value"}
_ANONYMOUS_ID = re.compile(r"^[A-Za-z0-9_-]{16,80}$")


@app.post("/api/analytics/event")
async def capture_analytics_event(request: Request) -> Response:
    """Persist an explicitly consented, PII-free first-party product event."""
    if not await _allow_rate(request, "analytics", limit=120, window_seconds=60):
        raise HTTPException(status_code=429, detail="too many analytics events")
    body = await _read_json_body(request, 8192)
    if not isinstance(body, dict) or body.get("event") not in _ANALYTICS_EVENTS:
        raise HTTPException(status_code=422, detail="unsupported analytics event")
    anonymous_id = body.get("anonymous_id")
    if not isinstance(anonymous_id, str) or not _ANONYMOUS_ID.fullmatch(anonymous_id):
        raise HTTPException(status_code=422, detail="invalid anonymous id")
    raw_properties = body.get("properties", {})
    if not isinstance(raw_properties, dict) or any(key not in _ANALYTICS_PROPERTIES for key in raw_properties):
        raise HTTPException(status_code=422, detail="unsupported analytics properties")
    properties: dict[str, str | int | float | bool] = {}
    for key, value in raw_properties.items():
        if isinstance(value, str | int | float | bool) and len(str(value)) <= 120:
            properties[key] = value
    _append_product_event(
        "analytics_event",
        {"event": body["event"], "anonymous_id": anonymous_id, "properties": properties},
    )
    return Response(status_code=204)


@app.post("/api/email/bounce")
async def capture_hard_bounce(request: Request) -> Response:
    """Consume a Postfix DSN and suppress only a signed hard-bounce recipient."""
    raw = await _read_bounded_body(request, 512_000)
    message = BytesParser(policy=policy.default).parsebytes(raw)
    report_text = raw.decode("utf-8", errors="replace")
    is_delivery_report = (
        message.get_content_type() == "multipart/report"
        or "message/delivery-status" in report_text.casefold()
    )
    is_hard_failure = bool(
        re.search(r"(?im)^Action:\s*failed\s*$", report_text)
        and re.search(r"(?im)^Status:\s*5\.\d+\.\d+\s*$", report_text)
    )
    if not is_delivery_report or not is_hard_failure:
        return Response(status_code=204)
    pattern = re.compile(
        rf"paperboy-bounce\+\d+\.[a-f0-9]{{32}}@{re.escape(settings.bounce_domain)}",
        re.IGNORECASE,
    )
    for address in pattern.findall(report_text):
        if await asyncio.to_thread(suppress_from_bounce_address, address):
            logger.warning("hard_bounce_suppressed", extra={"event": "hard_bounce_suppressed"})
            break
    return Response(status_code=204)


@app.post("/api/email/resend-webhook")
async def capture_resend_event(request: Request) -> JSONResponse:
    """Verify and apply Resend delivery outcomes without retaining recipient PII twice."""
    raw = await _read_bounded_body(request, 256_000)
    try:
        event_id = _verify_resend_signature(raw, request)
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid Resend webhook") from exc
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise HTTPException(status_code=422, detail="invalid Resend event")
    event_type = str(event["type"])
    if not _claim_email_provider_event(event_id, event_type):
        return JSONResponse({"ok": True, "duplicate": True})
    try:
        raw_data = event.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        raw_recipients = data.get("to")
        recipients: list[Any] = raw_recipients if isinstance(raw_recipients, list) else []
        email = str(recipients[0]).strip().lower() if recipients else ""
        subscription = get_subscription_by_email(email) if email else None
        subscription_id = int(subscription["id"]) if subscription is not None else None
        provider_email_id = str(data.get("email_id") or "") or None
        if subscription is not None and event_type in {
            "email.bounced",
            "email.complained",
            "email.suppressed",
        }:
            suppress_email(email, f"resend_{event_type.rsplit('.', 1)[-1]}", event_id)
        if subscription_id is not None and event_type in {
            "email.sent",
            "email.delivered",
            "email.delivery_delayed",
            "email.failed",
            "email.bounced",
            "email.complained",
            "email.suppressed",
        }:
            _append_product_event(
                "email_provider_event",
                {
                    "subscription_id": subscription_id,
                    "provider": "resend",
                    "provider_event": event_type,
                    "provider_email_id": provider_email_id,
                },
            )
        _finish_email_provider_event(
            event_id,
            "processed" if subscription_id is not None else "ignored",
            subscription_id=subscription_id,
            provider_email_id=provider_email_id,
        )
    except Exception as exc:
        _finish_email_provider_event(event_id, "failed", detail=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Resend webhook processing failed") from exc
    return JSONResponse({"ok": True, "status": "processed"})


@app.get("/api/hit")
async def visit_pixel(request: Request, slug: str = "paperboy") -> PlainTextResponse:
    # Naive rate-limit: one hit per IP per 5 seconds
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    if now - _last_hit.get(ip, 0) < 5:
        return PlainTextResponse("", status_code=204)
    _last_hit[ip] = now
    try:
        _append_product_event("visit", {"slug": slug, "ip": ip, "ua": request.headers.get("user-agent", "")})
    except (OSError, sqlite3.Error):
        logger.exception("visit_persistence_failed", extra={"event": "visit_persistence_failed"})
        return PlainTextResponse("", status_code=503)
    logger.info("visit", extra={"event": "page_visit", "slug": slug, "ip": ip})
    return PlainTextResponse("", status_code=204)


@app.get("/api/config")
async def runtime_config() -> JSONResponse:
    """Return a safe subset of runtime configuration."""
    return JSONResponse(
        {
            "log_level": settings.log_level,
            "fast_model": settings.fast_model,
            "research_model": settings.research_model,
            "dashboard_url": settings.dashboard_url,
            "features": {
                "ollama": bool(settings.ollama_url),
                "smtp": bool(settings.smtp_host),
            },
            "version": "0.4.0",
            "billing": {
                "enabled": settings.billing_enabled,
                "trial_days": settings.stripe_trial_days,
                "monthly_price_cents": settings.stripe_monthly_price_cents,
                "currency": settings.stripe_currency.upper(),
            },
        }
    )


@app.post("/api/daily-brief")
async def render_brief(request: Request) -> JSONResponse:
    """Render the bundled sanitized Daily Intelligence Brief sample."""
    from paperboy.daily_brief.cli import run as render_run

    try:
        body = await _read_json_body(request, 1024)
    except HTTPException as exc:
        if exc.status_code == 400:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        raise
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    if body:
        return JSONResponse({"ok": False, "error": "fixture_overrides_not_supported"}, status_code=400)
    path = settings.app_root / "examples" / "daily-brief.sample.json"

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "brief"
        result = render_run(path, out)
        text = (out / "paperboy-daily-brief.txt").read_text(encoding="utf-8")
        html = (out / "paperboy-daily-brief.html").read_text(encoding="utf-8")
        return JSONResponse(
            {
                "ok": True,
                "status": result["status"],
                "items": result["items"],
                "text": text,
                "html": html,
            }
        )


@app.post("/api/firehose/preview")
async def preview_firehose(request: Request) -> JSONResponse:
    """Return an instant, source-linked RSS/Atom relevance preview."""
    if not await _allow_rate(request, "preview", limit=12, window_seconds=60):
        raise HTTPException(status_code=429, detail="too many previews; try again shortly")
    payload = await _read_json_body(request, MAX_REQUEST_BYTES)
    try:
        sources, focus, ignore = validate_preview_payload(payload)
    except PreviewValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async with _preview_semaphore:
        result = await asyncio.to_thread(build_firehose_preview, sources, focus, ignore)
    return JSONResponse(result)


@app.post("/api/firehose/subscribe")
async def subscribe_firehose(request: Request) -> JSONResponse:
    """Preview a firehose, then persist it for automatic daily delivery."""
    payload = await _read_json_body(request, MAX_REQUEST_BYTES)
    try:
        email, sources, focus, ignore, attribution, timezone_name = validate_subscription_payload(payload)
    except SubscriptionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    client_ip = _client_identity(request)
    if not await asyncio.to_thread(allow_subscription_attempt, client_ip, email):
        raise HTTPException(status_code=429, detail="too many subscription attempts; try again later")

    async with _preview_semaphore:
        preview = await asyncio.to_thread(build_firehose_preview, sources, focus, ignore)
    if not any(source.get("status") == "ok" for source in preview["sources"]):
        return JSONResponse(
            {
                "ok": False,
                "status": "preview_failed",
                "error": "no_sources_reachable",
                "preview": preview,
            },
            status_code=422,
        )
    try:
        _subscription, _management_token = await asyncio.to_thread(
            create_subscription,
            email,
            sources,
            focus,
            ignore,
            attribution,
            timezone_name,
        )
    except SubscriptionSuppressedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SubscriptionValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, sqlite3.Error):
        logger.exception("subscription_persistence_failed", extra={"event": "subscription_persistence_failed"})
        return JSONResponse({"ok": False, "status": "error", "error": "persistence_failed"}, status_code=503)
    logger.info("firehose_confirmation_queued", extra={"event": "firehose_confirmation_queued", "email": email})
    return JSONResponse(
        {
            "ok": True,
            "status": "pending_verification",
            "preview": preview,
            "confirmation_queued": True,
        }
    )


def _masked_email(email: str) -> str:
    local, domain = email.rsplit("@", 1)
    return f"{local[:1]}***@{domain}"


@app.get("/api/firehose/subscriptions/{token}")
async def firehose_subscription_status(token: str) -> JSONResponse:
    subscription = await asyncio.to_thread(get_subscription, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    entitled = billing_entitled(subscription)
    status = (
        "unsubscribed"
        if subscription["unsubscribed_at"] or subscription["suppressed"]
        else "active" if subscription["verification_status"] == "verified" else "pending_verification"
    )
    return JSONResponse(
        {
            "ok": True,
            "status": status,
            "email_masked": _masked_email(subscription["email"]),
            "sources": subscription["sources"],
            "focus": subscription["focus"],
            "ignore": subscription["ignore"],
            "timezone": subscription["timezone"],
            "billing_status": subscription["billing_status"],
            "created_at": subscription["created_at"],
            "last_sent_at": subscription["last_sent_at"],
            "next_delivery_at": (
                next_delivery_at(subscription).isoformat().replace("+00:00", "Z")
                if status == "active" and entitled
                else None
            ),
            "checkout_available": settings.billing_enabled and status == "active" and not entitled,
            "portal_available": settings.billing_enabled and bool(subscription["billing_customer_id"]),
            "paid_at": subscription["paid_at"],
        }
    )


@app.post("/api/firehose/subscriptions/{token}/confirm")
async def confirm_firehose_subscription(token: str) -> JSONResponse:
    subscription = await asyncio.to_thread(confirm_subscription, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="confirmation link is invalid or expired")
    token_value = management_token(subscription)
    manage_url, status_url, unsubscribe_url = management_urls(token_value)
    if subscription.get("_newly_verified"):
        _append_product_event(
            "email_verified",
            {
                "subscription_id": subscription["id"],
                "attribution": subscription["attribution"],
            },
        )
        await asyncio.to_thread(
            enqueue_lifecycle_event,
            f"email_verified:{subscription['id']}:{subscription['verified_at']}",
            int(subscription["id"]),
            "email_verified",
        )
    logger.info("firehose_email_verified", extra={"event": "firehose_email_verified", "email": subscription["email"]})
    return JSONResponse(
        {
            "ok": True,
            "status": "active",
            "billing_status": subscription["billing_status"],
            "manage_url": manage_url,
            "status_url": status_url,
            "unsubscribe_url": unsubscribe_url,
            "checkout_available": settings.billing_enabled,
            "portal_available": False,
            "timezone": subscription["timezone"],
            "sources": subscription["sources"],
            "focus": subscription["focus"],
            "ignore": subscription["ignore"],
        }
    )


@app.post("/api/firehose/subscriptions/{token}/unsubscribe")
async def unsubscribe_firehose(token: str) -> JSONResponse:
    subscription = await asyncio.to_thread(unsubscribe, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    logger.info("firehose_unsubscribed", extra={"event": "firehose_unsubscribed", "email": subscription["email"]})
    return JSONResponse({"ok": True, "status": "unsubscribed"})


@app.post("/api/billing/checkout")
async def start_checkout(request: Request) -> JSONResponse:
    body = await _read_json_body(request, 8192)
    token = body.get("token") if isinstance(body, dict) else None
    if not isinstance(token, str):
        raise HTTPException(status_code=422, detail="management token is required")
    subscription = await asyncio.to_thread(get_subscription, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    try:
        checkout_url = await asyncio.to_thread(create_checkout, subscription)
    except BillingStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BillingUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("stripe_checkout_failed", extra={"event": "stripe_checkout_failed"})
        raise HTTPException(status_code=502, detail="checkout is temporarily unavailable") from exc
    _append_product_event(
        "begin_checkout",
        {"subscription_id": subscription["id"], "attribution": subscription["attribution"]},
    )
    return JSONResponse({"ok": True, "checkout_url": checkout_url})


@app.post("/api/billing/portal")
async def start_customer_portal(request: Request) -> JSONResponse:
    body = await _read_json_body(request, 8192)
    token = body.get("token") if isinstance(body, dict) else None
    if not isinstance(token, str):
        raise HTTPException(status_code=422, detail="management token is required")
    subscription = await asyncio.to_thread(get_subscription, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    try:
        portal_url = await asyncio.to_thread(create_customer_portal, subscription)
    except BillingStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BillingUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("stripe_portal_failed", extra={"event": "stripe_portal_failed"})
        raise HTTPException(status_code=502, detail="billing management is temporarily unavailable") from exc
    return JSONResponse({"ok": True, "portal_url": portal_url})


@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    payload = await _read_bounded_body(request, 1_000_000)
    try:
        event = construct_event(payload, request.headers.get("stripe-signature", ""))
    except BillingUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid Stripe webhook signature") from exc
    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    if not claim_billing_webhook(event_id, event_type):
        return JSONResponse({"ok": True, "duplicate": True})
    try:
        outcome, subscription_id = apply_event(event)
        finish_billing_webhook(event_id, outcome)
    except Exception as exc:
        finish_billing_webhook(event_id, "failed", type(exc).__name__)
        logger.exception("stripe_webhook_failed", extra={"event": "stripe_webhook_failed", "stripe_event": event_type})
        raise HTTPException(status_code=500, detail="webhook processing failed") from exc
    if outcome == "processed" and subscription_id is not None:
        subscription = get_subscription_by_id(subscription_id)
        if subscription is not None:
            _append_product_event(
                "billing_state_changed",
                {
                    "subscription_id": subscription_id,
                    "billing_status": subscription["billing_status"],
                    "attribution": subscription["attribution"],
                },
            )
            event_object = (event.get("data") or {}).get("object") or {}
            if event_type == "invoice.paid":
                amount_paid = int(event_object.get("amount_paid") or 0)
                if amount_paid > 0:
                    _append_product_event(
                        "purchase",
                        {
                            "subscription_id": subscription_id,
                            "transaction_id": str(event_object.get("id") or event_id),
                            "amount_paid": amount_paid,
                            "currency": str(event_object.get("currency") or "").upper(),
                            "attribution": subscription["attribution"],
                        },
                    )
    return JSONResponse({"ok": True, "status": outcome})


_PIXEL = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b"
)


@app.get("/api/t/o/{token}.gif")
async def track_email_open(token: str) -> Response:
    await asyncio.to_thread(record_tracking_event, token, "open")
    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@app.get("/api/t/c/{token}")
async def track_email_click(token: str) -> RedirectResponse:
    target = await asyncio.to_thread(resolve_click_target, token)
    if target is None:
        raise HTTPException(status_code=404, detail="tracking link not found")
    await asyncio.to_thread(record_tracking_event, token, "click")
    return RedirectResponse(target, status_code=302, headers={"Referrer-Policy": "no-referrer"})


# ---------------------------------------------------------------------------
# Static files (landing page)
# ---------------------------------------------------------------------------

_product_dir = settings.app_root / "product"
if _product_dir.exists():
    app.mount("/", StaticFiles(directory=str(_product_dir), html=True), name="product")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_product_dir / "index.html")
