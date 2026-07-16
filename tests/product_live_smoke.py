"""Opt-in Playwright smoke test for the deployed Paperboy validation page."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--submit-test-subscription",
        "--submit-test-lead",
        dest="submit_test_subscription",
        action="store_true",
    )
    args = parser.parse_args()

    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        response = page.goto(
            "https://paperboy.kaibuilds.com/?utm_source=deploy_smoke&utm_campaign=paperboy_kaibuilds_launch",
            wait_until="networkidle",
        )
        assert response is not None and response.ok
        assert page.title() == "Paperboy — Your Own Filtered Firehose"
        assert page.locator('link[rel="canonical"]').get_attribute("href") == "https://paperboy.kaibuilds.com/"
        assert page.locator(".trust-line").get_by_text("No Gmail access", exact=True).is_visible()
        assert page.get_by_role("button", name="Start my daily brief").first.is_visible()
        page.wait_for_timeout(500)
        page.screenshot(path=str(ROOT / "paperboy-live-smoke.png"))

        if args.submit_test_subscription:
            page.get_by_role("button", name="Start my daily brief").first.click()
            page.get_by_label("Email address").fill("paperboy-deploy-smoke@example.invalid")
            page.get_by_label("Public RSS or Atom feed URLs").fill("https://news.ycombinator.com/rss")
            page.get_by_label("What should make an item relevant?").fill("AI infrastructure and API pricing")
            page.get_by_label("What should Paperboy ignore?").fill("funding gossip")
            page.locator("#subscription-submit").click()
            page.get_by_role("heading", name="Your daily brief is active.").wait_for(timeout=45_000)
            page.get_by_role("button", name="Unsubscribe", exact=True).click()
            page.locator("#confirm-dialog").get_by_role("button", name="Unsubscribe").click()
            page.get_by_role("heading", name="This daily brief is unsubscribed.").wait_for(timeout=10_000)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto("https://paperboy.kaibuilds.com/", wait_until="networkidle")
        mobile.get_by_role("button", name="Toggle navigation").click()
        assert mobile.locator("#mobile-nav").get_by_role("button", name="Start my daily brief", exact=True).is_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        browser.close()

    if console_errors:
        raise AssertionError("Browser console errors: " + " | ".join(console_errors))

    print("Paperboy live Playwright smoke passed")
    print("- public TLS page, canonical, product boundary, and CTA passed")
    print("- mobile navigation and overflow checks passed")
    print(
        "- deploy smoke subscription activated and unsubscribed"
        if args.submit_test_subscription
        else "- no subscription created"
    )


if __name__ == "__main__":
    main()
