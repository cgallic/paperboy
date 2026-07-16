"""Opt-in Playwright smoke test for the deployed Paperboy validation page."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit-test-lead", action="store_true")
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
        assert page.title() == "Paperboy — One Daily Brief From Your Sources"
        assert page.locator('link[rel="canonical"]').get_attribute("href") == "https://paperboy.kaibuilds.com/"
        assert page.locator(".trust-line").get_by_text("No Gmail access", exact=True).is_visible()
        assert page.get_by_role("button", name="Get my free sample brief").first.is_visible()
        page.wait_for_timeout(500)
        page.screenshot(path=str(ROOT / "paperboy-live-smoke.png"))

        if args.submit_test_lead:
            page.get_by_role("button", name="Get my free sample brief").first.click()
            page.get_by_label("Email address").fill("paperboy-deploy-smoke@example.invalid")
            page.get_by_label("Newsletter names or URLs").fill("QA deploy smoke newsletter")
            page.get_by_label("Public GitHub repo URLs").fill("https://github.com/cgallic/paperboy")
            page.get_by_label("What are you working on?").fill("QA deploy verification")
            page.locator("#pilot-submit").click()
            page.get_by_role("heading", name="Your sample request is saved.").wait_for()

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto("https://paperboy.kaibuilds.com/", wait_until="networkidle")
        mobile.get_by_role("button", name="Toggle navigation").click()
        assert mobile.get_by_role("button", name="Get my free sample", exact=True).is_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        browser.close()

    if console_errors:
        raise AssertionError("Browser console errors: " + " | ".join(console_errors))

    print("Paperboy live Playwright smoke passed")
    print("- public TLS page, canonical, product boundary, and CTA passed")
    print("- mobile navigation and overflow checks passed")
    print("- deploy smoke lead submitted" if args.submit_test_lead else "- no lead submitted")


if __name__ == "__main__":
    main()
