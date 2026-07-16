"""Manual Playwright smoke test for the static Paperboy product surface."""

import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = ROOT / "paperboy-product-smoke.png"
LANDING_SCREENSHOT = ROOT / "paperboy-landing-smoke.png"


def main() -> None:
    lead_payloads: list[dict] = []
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

        def capture_lead(route, request) -> None:
            lead_payloads.append(json.loads(request.post_data or "{}"))
            route.fulfill(status=200, content_type="application/json", body='{"ok":true}')

        def serve_product(route, request) -> None:
            path = urlparse(request.url).path
            if path == "/api/lead":
                capture_lead(route, request)
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
        assert page.title() == "Paperboy — One Daily Brief From Your Sources"
        assert page.locator('link[rel="canonical"]').get_attribute("href") == "https://paperboy.kaibuilds.com/"
        hero_heading = page.get_by_role("heading", name="Stop reading 20 newsletters every morning.")
        assert hero_heading.is_visible(), page.locator(".hero-copy").evaluate(
            "node => ({display: getComputedStyle(node).display, opacity: getComputedStyle(node).opacity, html: node.innerHTML})"
        )
        assert page.locator(".trust-line").get_by_text("No Gmail access", exact=True).is_visible()
        assert page.get_by_role("button", name="Get my free sample brief").first.is_visible()
        page.screenshot(path=str(LANDING_SCREENSHOT))

        page.get_by_role("button", name="Get my free sample brief").first.click()
        page.get_by_label("Email address").fill("paperboy-smoke@example.invalid")
        page.locator("#pilot-submit").click()
        assert page.locator("#intake-error").inner_text() == "Add at least one newsletter name or URL."
        assert len(lead_payloads) == 0
        page.get_by_label("Newsletter names or URLs").fill("QA Newsletter\nhttps://example.invalid/qa-newsletter")
        page.get_by_label("Public GitHub repo URLs").fill("https://github.com/cgallic/paperboy")
        page.get_by_label("What are you working on?").fill("QA validation of the Paperboy concierge intake")
        page.locator("#pilot-submit").click()
        page.wait_for_timeout(500)
        if not page.locator("#magic-success").is_visible():
            raise AssertionError(
                "Pilot form did not complete: "
                + json.dumps(
                    {
                        "error": page.locator("#email-error").inner_text(),
                        "payloads": lead_payloads,
                        "console_errors": console_errors,
                    }
                )
            )
        page.get_by_role("heading", name="Your sample request is saved.").wait_for()

        assert len(lead_payloads) == 1
        payload = lead_payloads[0]
        assert payload["slug"] == "paperboy"
        assert payload["email"] == "paperboy-smoke@example.invalid"
        assert payload["offer"] == "Free personalized Paperboy sample"
        assert payload["price"] == "$49/month after sample"
        assert payload["source"] == "paperboy_sample_request"
        assert payload["newsletter_sources"] == ["QA Newsletter", "https://example.invalid/qa-newsletter"]
        assert payload["github_repo_urls"] == ["https://github.com/cgallic/paperboy"]
        assert payload["work_focus"] == "QA validation of the Paperboy concierge intake"
        assert payload["utm_source"] == "smoke"
        assert payload["utm_campaign"] == "paperboy_launch"

        page.get_by_role("button", name="Explore the product preview").click()
        page.get_by_role("heading", name="Choose what belongs in your morning edition.").wait_for()
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.route("http://paperboy.kaibuilds.com:8123/**", serve_product)
        mobile.goto("http://paperboy.kaibuilds.com:8123/", wait_until="networkidle")
        mobile.get_by_role("button", name="Toggle navigation").click()
        assert mobile.get_by_role("button", name="Get my free sample", exact=True).is_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        browser.close()

    if console_errors:
        raise AssertionError("Browser console errors: " + " | ".join(console_errors))

    print("Paperboy Playwright smoke passed")
    print(f"- captured and validated {len(lead_payloads)} free-sample payload")
    print("- product-tour handoff passed")
    print("- mobile navigation and overflow checks passed")
    print(f"- screenshot: {SCREENSHOT}")
    print(f"- landing screenshot: {LANDING_SCREENSHOT}")


if __name__ == "__main__":
    main()
