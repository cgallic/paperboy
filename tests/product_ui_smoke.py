"""Manual Playwright smoke test for the static Paperboy product surface."""

import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = ROOT / "paperboy-product-smoke.png"
LANDING_SCREENSHOT = ROOT / "paperboy-landing-smoke.png"


def main() -> None:
    subscription_payloads: list[dict] = []
    status_requests: list[str] = []
    unsubscribe_requests: list[str] = []
    subscribe_failure = {"enabled": False}
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--host-resolver-rules=MAP paperboy.kaibuilds.com 127.0.0.1",
                "--no-proxy-server",
            ],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        def capture_subscription(route, request) -> None:
            subscription_payloads.append(json.loads(request.post_data or "{}"))
            if subscribe_failure["enabled"]:
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"Daily delivery could not be activated."}',
                )
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "status": "subscribed",
                        "manage_url": "/?manage=smoke-token",
                        "status_url": "/api/firehose/subscriptions/smoke-token",
                        "unsubscribe_url": "/api/firehose/subscriptions/smoke-token/unsubscribe",
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
                    }
                ),
            )

        def capture_status(route, request) -> None:
            status_requests.append(request.url)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "status": "active",
                        "email_masked": "p***@example.invalid",
                        "sources": ["https://news.ycombinator.com/rss"],
                        "focus": "API pricing and QA validation",
                        "ignore": ["funding gossip"],
                        "created_at": "2026-07-16T12:00:00Z",
                        "last_sent_at": None,
                        "next_delivery_at": "2026-07-17T07:30:00Z",
                    }
                ),
            )

        def capture_unsubscribe(route, request) -> None:
            unsubscribe_requests.append(request.url)
            route.fulfill(
                status=200,
                content_type="application/json",
                body='{"ok":true,"status":"unsubscribed"}',
            )

        def serve_product(route, request) -> None:
            path = urlparse(request.url).path
            if path == "/api/firehose/subscribe":
                capture_subscription(route, request)
                return
            if path == "/api/firehose/subscriptions/smoke-token/unsubscribe":
                capture_unsubscribe(route, request)
                return
            if path == "/api/firehose/subscriptions/smoke-token":
                capture_status(route, request)
                return
            if path == "/api/hit":
                route.fulfill(status=200, content_type="image/gif", body="")
                return
            relative = "index.html" if path == "/" else path.lstrip("/")
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

        page.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        page.goto(
            "http://paperboy.kaibuilds.com:8123/?utm_source=smoke&utm_campaign=paperboy_launch",
            wait_until="networkidle",
        )

        assert page.evaluate("location.hostname") == "paperboy.kaibuilds.com"
        assert page.title() == "Paperboy — Your Own Filtered Firehose"
        assert page.locator('link[rel="canonical"]').get_attribute("href") == "https://paperboy.kaibuilds.com/"
        hero_heading = page.get_by_role("heading", name="Build your firehose. Read only what matters.")
        assert hero_heading.is_visible(), page.locator(".hero-copy").evaluate(
            "node => ({display: getComputedStyle(node).display, opacity: getComputedStyle(node).opacity, html: node.innerHTML})"
        )
        assert page.locator(".trust-line").get_by_text("No Gmail access", exact=True).is_visible()
        assert page.get_by_role("button", name="Start my daily brief").first.is_visible()
        page.screenshot(path=str(LANDING_SCREENSHOT))

        page.get_by_role("button", name="Start my daily brief").first.click()
        page.get_by_label("Email address").fill("paperboy-smoke@example.invalid")
        page.locator("#subscription-submit").click()
        assert page.locator("#intake-error").inner_text() == "Add at least one public RSS or Atom feed URL."
        assert len(subscription_payloads) == 0
        page.get_by_label("Public RSS or Atom feed URLs").fill("https://news.ycombinator.com/rss")
        page.get_by_label("What should make an item relevant?").fill("API pricing and QA validation")
        page.get_by_label("What should Paperboy ignore?").fill("funding gossip")
        page.locator("#subscription-submit").click()
        page.wait_for_timeout(500)
        if not page.locator("#magic-success").is_visible():
            raise AssertionError(
                "Pilot form did not complete: "
                + json.dumps(
                    {
                        "error": page.locator("#email-error").inner_text(),
                        "payloads": subscription_payloads,
                        "console_errors": console_errors,
                    }
                )
            )
        page.get_by_role("heading", name="Your daily brief is active.").wait_for()
        page.get_by_role("heading", name="A provider changed its API price").wait_for()

        assert len(subscription_payloads) == 1
        payload = subscription_payloads[0]
        assert payload == {
            "email": "paperboy-smoke@example.invalid",
            "sources": ["https://news.ycombinator.com/rss"],
            "focus": "API pricing and QA validation",
            "ignore": ["funding gossip"],
            "source": "paperboy_automatic_subscription",
            "page": "http://paperboy.kaibuilds.com:8123/?utm_source=smoke&utm_campaign=paperboy_launch#signin",
            "utm_source": "smoke",
            "utm_campaign": "paperboy_launch",
        }
        assert page.get_by_text("No card collected", exact=True).is_visible()

        page.get_by_role("button", name="Refresh subscription status").click()
        page.get_by_text("Delivering to p***@example.invalid").wait_for()
        assert len(status_requests) == 1

        page.get_by_role("button", name="Unsubscribe", exact=True).click()
        page.locator("#confirm-dialog").get_by_role("button", name="Unsubscribe").click()
        page.get_by_role("heading", name="This daily brief is unsubscribed.").wait_for()
        assert len(unsubscribe_requests) == 1

        page.screenshot(path=str(SCREENSHOT), full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        mobile.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        mobile.get_by_role("button", name="Toggle navigation").click()
        assert mobile.locator("#mobile-nav").get_by_role("button", name="Start my daily brief", exact=True).is_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        manager = browser.new_page(viewport={"width": 900, "height": 800})
        manager.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        manager.goto("http://paperboy.kaibuilds.com:8123/?manage=smoke-token", wait_until="networkidle")
        manager.get_by_role("heading", name="Your daily brief is active.").wait_for()
        assert manager.get_by_text("1 public source connected").is_visible()

        subscribe_failure["enabled"] = True
        failure = browser.new_page(viewport={"width": 900, "height": 800})
        failure.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        failure.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        failure.get_by_role("button", name="Start my daily brief").first.click()
        failure.get_by_label("Email address").fill("paperboy-failure@example.invalid")
        failure.get_by_label("Public RSS or Atom feed URLs").fill("https://news.ycombinator.com/rss")
        failure.get_by_label("What should make an item relevant?").fill("API pricing")
        failure.locator("#subscription-submit").click()
        failure.get_by_text("Daily delivery could not be activated.").wait_for()
        assert failure.locator("#magic-success").is_hidden()

        browser.close()

    if console_errors:
        raise AssertionError("Browser console errors: " + " | ".join(console_errors))

    print("Paperboy Playwright smoke passed")
    print(f"- captured and validated {len(subscription_payloads)} automatic subscription payloads")
    print(f"- validated {len(status_requests)} management status requests and {len(unsubscribe_requests)} unsubscribe request")
    print("- failed subscriptions never render an active-delivery claim")
    print("- mobile navigation and overflow checks passed")
    print(f"- screenshot: {SCREENSHOT}")
    print(f"- landing screenshot: {LANDING_SCREENSHOT}")


if __name__ == "__main__":
    main()
