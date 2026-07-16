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
import json
import sqlite3
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from paperboy.config import settings
from paperboy.db import connect, init_schema
from paperboy.firehose import (
    MAX_REQUEST_BYTES,
    PreviewValidationError,
    build_firehose_preview,
    validate_preview_payload,
)
from paperboy.health import run_all
from paperboy.logging_config import configure_logging, get_logger
from paperboy.subscriptions import (
    SubscriptionValidationError,
    create_subscription,
    get_subscription,
    management_urls,
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
    version="0.3.0",
    lifespan=lifespan,
)

# Rate-limit helper (naive; replace with Redis in prod)
_last_hit: dict[str, float] = {}


def _append_product_event(event_type: str, payload: dict) -> int:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT INTO events (ts, source, type, actor, payload_json, attachment_uri, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, "paperboy-api", event_type, payload.get("email"), json.dumps(payload, ensure_ascii=False), None, now),
        )
        conn.commit()
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
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    email = str(body.get("email", "")).strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return JSONResponse({"ok": False, "error": "invalid_email"}, status_code=400)

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
            "version": "0.3.0",
        }
    )


@app.post("/api/daily-brief")
async def render_brief(request: Request) -> JSONResponse:
    """Render the bundled sanitized Daily Intelligence Brief sample."""
    from paperboy.daily_brief.cli import run as render_run

    try:
        body = await request.json()
    except Exception:
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
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="request body is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid content-length") from None
    try:
        raw_body = await request.body()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="could not read request body") from exc
    if len(raw_body) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="request body is too large")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc
    try:
        sources, focus, ignore = validate_preview_payload(payload)
    except PreviewValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = await asyncio.to_thread(build_firehose_preview, sources, focus, ignore)
    return JSONResponse(result)


@app.post("/api/firehose/subscribe")
async def subscribe_firehose(request: Request) -> JSONResponse:
    """Preview a firehose, then persist it for automatic daily delivery."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="request body is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid content-length") from None
    raw_body = await request.body()
    if len(raw_body) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="request body is too large")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc
    try:
        email, sources, focus, ignore, attribution = validate_subscription_payload(payload)
    except SubscriptionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        _subscription, token = await asyncio.to_thread(
            create_subscription,
            email,
            sources,
            focus,
            ignore,
            attribution,
        )
    except (OSError, sqlite3.Error):
        logger.exception("subscription_persistence_failed", extra={"event": "subscription_persistence_failed"})
        return JSONResponse({"ok": False, "status": "error", "error": "persistence_failed"}, status_code=503)
    manage_url, status_url, unsubscribe_url = management_urls(token)
    logger.info("firehose_subscribed", extra={"event": "firehose_subscribed", "email": email})
    return JSONResponse(
        {
            "ok": True,
            "status": "subscribed",
            "preview": preview,
            "manage_url": manage_url,
            "status_url": status_url,
            "unsubscribe_url": unsubscribe_url,
        }
    )


def _masked_email(email: str) -> str:
    local, domain = email.rsplit("@", 1)
    return f"{local[:1]}***@{domain}"


def _next_delivery_at() -> str:
    now = datetime.now(timezone.utc)
    next_delivery = now.replace(hour=12, minute=30, second=0, microsecond=0)
    if next_delivery <= now:
        next_delivery += timedelta(days=1)
    return next_delivery.isoformat().replace("+00:00", "Z")


@app.get("/api/firehose/subscriptions/{token}")
async def firehose_subscription_status(token: str) -> JSONResponse:
    subscription = await asyncio.to_thread(get_subscription, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    return JSONResponse(
        {
            "ok": True,
            "status": "active" if subscription["active"] else "unsubscribed",
            "email_masked": _masked_email(subscription["email"]),
            "sources": subscription["sources"],
            "focus": subscription["focus"],
            "ignore": subscription["ignore"],
            "created_at": subscription["created_at"],
            "last_sent_at": subscription["last_sent_at"],
            "next_delivery_at": _next_delivery_at() if subscription["active"] else None,
        }
    )


@app.post("/api/firehose/subscriptions/{token}/unsubscribe")
async def unsubscribe_firehose(token: str) -> JSONResponse:
    subscription = await asyncio.to_thread(unsubscribe, token)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    logger.info("firehose_unsubscribed", extra={"event": "firehose_unsubscribed", "email": subscription["email"]})
    return JSONResponse({"ok": True, "status": "unsubscribed"})


# ---------------------------------------------------------------------------
# Static files (landing page)
# ---------------------------------------------------------------------------

_product_dir = settings.app_root / "product"
if _product_dir.exists():
    app.mount("/", StaticFiles(directory=str(_product_dir), html=True), name="product")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_product_dir / "index.html")
