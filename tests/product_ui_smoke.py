"""Playwright smoke for Paperboy's verified, paid subscription funnel."""

import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = Path(tempfile.gettempdir()) / "paperboy-product-smoke.png"
LANDING_SCREENSHOT = Path(tempfile.gettempdir()) / "paperboy-landing-smoke.png"


def main() -> None:
    subscription_payloads: list[dict] = []
    confirmation_requests: list[str] = []
    status_requests: list[str] = []
    checkout_payloads: list[dict] = []
    analytics_payloads: list[dict] = []
    unsubscribe_requests: list[str] = []
    unexpected_leads: list[dict] = []
    subscribe_failure = {"enabled": False}
    checkout_failure = {"enabled": False}
    billing_config = {"enabled": True}
    status_payload = {
        "ok": True,
        "status": "active",
        "billing_status": "unpaid",
        "checkout_available": True,
        "email_masked": "p***@example.invalid",
        "sources": ["https://news.ycombinator.com/rss"],
        "focus": "API pricing and QA validation",
        "ignore": ["funding gossip"],
        "timezone": "America/New_York",
        "created_at": "2026-07-16T12:00:00Z",
        "last_sent_at": None,
        "next_delivery_at": None,
    }
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--host-resolver-rules=MAP paperboy.kaibuilds.com 127.0.0.1",
                "--no-proxy-server",
            ],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        def json_response(route, body: dict, status: int = 200) -> None:
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        def serve_product(route, request) -> None:
            path = urlparse(request.url).path
            if path == "/api/config":
                json_response(
                    route,
                    {
                        "version": "0.4.0",
                        "billing": {
                            "enabled": billing_config["enabled"],
                            "trial_days": 7,
                            "monthly_price_cents": 4900,
                            "currency": "USD",
                        },
                    },
                )
                return
            if path == "/api/firehose/subscribe":
                subscription_payloads.append(json.loads(request.post_data or "{}"))
                if subscribe_failure["enabled"]:
                    json_response(route, {"detail": "The filter could not be saved."}, 503)
                    return
                json_response(
                    route,
                    {
                        "ok": True,
                        "status": "pending_verification",
                        "confirmation_queued": True,
                        "manage_url": "/?manage=smoke-manage",
                        "status_url": "/api/firehose/subscriptions/smoke-manage",
                        "preview": {
                            "scanned": 18,
                            "sources": [{"url": "https://news.ycombinator.com/rss", "status": "ok"}],
                            "items": [
                                {
                                    "title": "A provider changed its API price",
                                    "url": "https://example.invalid/provider-price",
                                    "source": "Hacker News",
                                    "score": 8.5,
                                    "why": "Matched API pricing and QA validation.",
                                }
                            ],
                        },
                    },
                )
                return
            if path == "/api/firehose/subscriptions/verify-smoke/confirm":
                confirmation_requests.append(request.url)
                json_response(
                    route,
                    {
                        "ok": True,
                        "status": "active",
                        "billing_status": "unpaid",
                        "checkout_available": True,
                        "manage_url": "/?manage=smoke-manage",
                        "status_url": "/api/firehose/subscriptions/smoke-manage",
                        "unsubscribe_url": "/api/firehose/subscriptions/smoke-manage/unsubscribe",
                    },
                )
                return
            if path == "/api/firehose/subscriptions/smoke-manage":
                status_requests.append(request.url)
                json_response(route, status_payload)
                return
            if path == "/api/firehose/subscriptions/smoke-manage/unsubscribe":
                unsubscribe_requests.append(request.url)
                json_response(route, {"ok": True, "status": "unsubscribed"})
                return
            if path == "/api/billing/checkout":
                checkout_payloads.append(json.loads(request.post_data or "{}"))
                if checkout_failure["enabled"]:
                    json_response(route, {"ok": False, "error": "billing_unavailable"}, 503)
                else:
                    json_response(
                        route,
                        {"ok": True, "checkout_url": "https://checkout.stripe.com/c/pay/smoke"},
                    )
                return
            if path == "/api/analytics/event":
                analytics_payloads.append(json.loads(request.post_data or "{}"))
                json_response(route, {"ok": True})
                return
            if path == "/api/lead":
                unexpected_leads.append(json.loads(request.post_data or "{}"))
                json_response(route, {"ok": True})
                return
            if path == "/api/hit":
                route.fulfill(status=200, content_type="image/gif", body="")
                return

            relative = "index.html" if path == "/" else path.lstrip("/")
            if path != "/" and path.endswith("/"):
                relative += "index.html"
            asset = ROOT / "product" / relative
            content_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "text/javascript",
                ".txt": "text/plain",
                ".xml": "application/xml",
            }
            if asset.is_file():
                route.fulfill(
                    status=200,
                    content_type=content_types.get(asset.suffix, "application/octet-stream"),
                    path=str(asset),
                )
            else:
                route.fulfill(status=404, body="Not found")

        context.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        context.route(
            "https://checkout.stripe.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<title>Stripe Checkout</title><h1>Secure checkout</h1>",
            ),
        )

        page.goto(
            "http://paperboy.kaibuilds.com:8123/?utm_source=smoke&utm_campaign=paperboy_launch",
            wait_until="networkidle",
        )
        assert page.title() == "Paperboy — Your Own Filtered Firehose", repr(page.title())
        assert page.get_by_role("heading", name="Build your firehose. Read only what matters.").is_visible()
        assert page.get_by_role("link", name="Privacy").is_visible()
        assert page.get_by_role("link", name="Terms").is_visible()
        assert page.get_by_role("link", name="Open source").is_visible()
        assert page.get_by_text("Hosted checkout available", exact=True).is_visible()
        assert analytics_payloads == []
        page.screenshot(path=str(LANDING_SCREENSHOT))

        page.get_by_role("button", name="Allow product analytics").click()
        page.get_by_role("button", name="Start my daily brief").first.click()
        page.get_by_label("Email address").fill("paperboy-smoke@example.invalid")
        page.get_by_label("Public RSS or Atom feed URLs").fill("https://news.ycombinator.com/rss")
        page.get_by_label("What should make an item relevant?").fill("API pricing and QA validation")
        page.get_by_label("What should Paperboy ignore?").fill("funding gossip")
        timezone = page.get_by_label("Your time zone").input_value()
        assert timezone
        page.get_by_label("I agree to receive the Paperboy brief and service emails.").check()
        page.locator("#subscription-submit").click()
        page.get_by_role("heading", name="Check your email.").wait_for()
        assert page.get_by_text("Awaiting confirmation", exact=True).is_visible()
        assert page.get_by_text("Not started", exact=True).count() >= 1
        assert page.get_by_role("heading", name="A provider changed its API price").is_visible()
        assert page.locator("#start-checkout").is_hidden()

        assert len(subscription_payloads) == 1
        assert subscription_payloads[0]["timezone"] == timezone
        assert subscription_payloads[0]["consent"] is True
        assert subscription_payloads[0]["utm_source"] == "smoke"
        assert unexpected_leads == []

        page.goto("http://paperboy.kaibuilds.com:8123/?confirm=verify-smoke", wait_until="networkidle")
        page.get_by_role("heading", name="Verify your email to continue.").wait_for()
        assert confirmation_requests == []
        page.get_by_role("button", name="Confirm my email").click()
        page.get_by_role("heading", name="Email verified. Finish checkout to start delivery.").wait_for()
        assert len(confirmation_requests) == 1
        assert "confirm=" not in page.url
        assert page.get_by_text("Checkout required", exact=True).count() >= 1
        assert unexpected_leads == []

        page.get_by_role("button", name="Continue to founding checkout").click()
        page.wait_for_url("https://checkout.stripe.com/**")
        assert checkout_payloads == [{"token": "smoke-manage"}]

        status_payload.update(
            {
                "billing_status": "trialing",
                "next_delivery_at": "2026-07-17T07:30:00-04:00",
            }
        )
        page.goto("http://paperboy.kaibuilds.com:8123/?billing=success", wait_until="networkidle")
        page.get_by_role("heading", name="Your daily brief is active.").wait_for()
        assert status_requests
        assert page.get_by_text("7-day trial", exact=True).is_visible()
        page.wait_for_timeout(200)
        event_names = [payload["event"] for payload in analytics_payloads]
        for expected in (
            "page_view",
            "signup_started",
            "subscription_requested",
            "email_verified",
            "begin_checkout",
            "trial_started",
        ):
            assert expected in event_names
        assert "purchase" not in event_names
        serialized_analytics = json.dumps(analytics_payloads)
        assert "paperboy-smoke@example.invalid" not in serialized_analytics
        assert "smoke-manage" not in serialized_analytics
        assert "verify-smoke" not in serialized_analytics

        page.get_by_role("button", name="Unsubscribe", exact=True).click()
        page.locator("#confirm-dialog").get_by_role("button", name="Unsubscribe").click()
        page.get_by_role("heading", name="This daily brief is unsubscribed.").wait_for()
        assert len(unsubscribe_requests) == 1
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        checkout_failure["enabled"] = True
        status_payload.update({"billing_status": "unpaid"})
        unavailable = context.new_page()
        unavailable.goto("http://paperboy.kaibuilds.com:8123/?manage=smoke-manage", wait_until="networkidle")
        unavailable.get_by_role("heading", name="Email verified. Finish checkout to start delivery.").wait_for()
        unavailable.get_by_role("button", name="Continue to founding checkout").click()
        unavailable.get_by_text("Checkout is temporarily unavailable.", exact=False).wait_for()
        assert unavailable.get_by_text("delivery has not started", exact=False).is_visible()

        subscribe_failure["enabled"] = True
        failure = context.new_page()
        failure.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        failure.get_by_role("button", name="Start my daily brief").first.click()
        failure.get_by_label("Email address").fill("paperboy-failure@example.invalid")
        failure.get_by_label("Public RSS or Atom feed URLs").fill("https://news.ycombinator.com/rss")
        failure.get_by_label("What should make an item relevant?").fill("API pricing")
        failure.get_by_label("I agree to receive the Paperboy brief and service emails.").check()
        failure.locator("#subscription-submit").click()
        failure.get_by_text("The filter could not be saved.").wait_for()
        assert failure.locator("#magic-success").is_hidden()

        mobile = context.new_page()
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        mobile.get_by_role("button", name="Toggle navigation").click()
        assert mobile.locator("#mobile-nav").get_by_role("button", name="Start my daily brief", exact=True).is_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        legal = context.new_page()
        legal.goto("http://paperboy.kaibuilds.com:8123/privacy/", wait_until="networkidle")
        assert legal.title() == "Privacy — Paperboy"
        assert legal.get_by_role("heading", name="What Paperboy collects").is_visible()
        legal.goto("http://paperboy.kaibuilds.com:8123/terms/", wait_until="networkidle")
        assert legal.title() == "Terms — Paperboy"
        assert legal.get_by_role("heading", name="Trial and billing").is_visible()

        billing_config["enabled"] = False
        unavailable_launch = context.new_page()
        unavailable_launch.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        assert unavailable_launch.get_by_text("Preview and email verification are live", exact=True).is_visible()
        assert unavailable_launch.get_by_text("No card will be requested or charged.", exact=False).is_visible()
        assert unavailable_launch.get_by_text("Checkout temporarily unavailable", exact=True).is_visible()

        context.close()
        browser.close()

    if console_errors:
        raise AssertionError("Browser console errors: " + " | ".join(console_errors))

    print("Paperboy Playwright smoke passed")
    print("- pending requests never claim active delivery")
    print("- explicit email confirmation and Stripe-hosted checkout passed")
    print("- server-confirmed trial return emitted trial_started, never purchase")
    print("- runtime checkout availability copy passed")
    print("- checkout failure, subscription failure, mobile, privacy, and terms passed")
    print("- consented analytics contained no email or lifecycle token")


if __name__ == "__main__":
    main()
