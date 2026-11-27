"""End-to-end demo flow for PASTNS. Run with: python scripts/e2e_playwright.py"""
import os
import re
import sys
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.environ.get("PASTNS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def run():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))

        # Officer login and application registration.
        page.goto(f"{BASE_URL}/officer/login/", wait_until="networkidle")
        page.get_by_label("Username").fill("officer")
        page.get_by_label("Password").fill("officer123")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="Applications")).to_be_visible()
        page.goto(f"{BASE_URL}/officer/applications/new/", wait_until="networkidle")
        national_id = "9900000000001"
        page.get_by_label("National ID").fill(national_id)
        page.get_by_label("First name").fill("E2E")
        page.get_by_label("Surname").fill("Applicant")
        page.get_by_label("Phone number").fill("+265991234001")
        page.get_by_label("Email (optional)").fill("e2e@example.mw")
        page.get_by_label("Preferred language").select_option("ny")
        page.get_by_label("Application type").select_option("new")
        page.get_by_role("button", name="Register and send SMS").click()
        expect(page.get_by_role("heading", name="Application registered")).to_be_visible()
        code_match = re.search(r"MW-MGC-\d{4}-\d{5}", page.locator("body").inner_text())
        assert code_match, "Registration confirmation did not show a tracking code"
        code = code_match.group(0)
        expect(page.get_by_text("Immigration:", exact=False)).to_be_visible()
        page.get_by_role("link", name="Open application").click()
        expect(page.get_by_role("heading", name="E2E Applicant")).to_be_visible()

        # Advance two stages and confirm the tracker changes.
        page.get_by_role("button", name="Advance to Under review").click()
        expect(page.get_by_text("Under review", exact=True).first).to_be_visible()
        page.get_by_role("button", name="Advance to Approved").click()
        expect(page.get_by_text("Approved", exact=True).first).to_be_visible()

        # Public portal dual-factor lookup.
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        page.get_by_label("National ID number").fill(national_id)
        page.get_by_label("Phone number or tracking code").fill(code)
        page.get_by_role("button", name="Check status").click()
        expect(page.get_by_text(code, exact=True)).to_be_visible()
        expect(page.get_by_text("Approved", exact=True).first).to_be_visible()
        expect(page.get_by_text("+265 99* *** 001", exact=True)).to_be_visible()

        # Phone-shaped simulator drives POST /api/ussd/ using the same session protocol.
        page.goto(f"{BASE_URL}/ussd-demo/", wait_until="networkidle")
        page.get_by_role("button", name="Start").click()
        expect(page.locator("[data-ussd-output]")).to_contain_text("Check status")
        page.locator("[data-ussd-input]").fill("1")
        page.get_by_role("button", name="Send").click()
        expect(page.locator("[data-ussd-output]")).to_contain_text("National ID")
        page.locator("[data-ussd-input]").fill(national_id)
        page.get_by_role("button", name="Send").click()
        expect(page.locator("[data-ussd-output]")).to_contain_text("tracking code")
        page.locator("[data-ussd-input]").fill(code)
        page.get_by_role("button", name="Send").click()
        expect(page.locator("[data-ussd-output]")).to_contain_text(code)
        expect(page.locator("[data-ussd-output]")).to_contain_text("Approved")

        # Bulk batch action: select the newly-approved row, mark as printed.
        page.goto(f"{BASE_URL}/officer/", wait_until="networkidle")
        page.locator('select[name="stage"]').select_option("approved")
        page.get_by_role("button", name="Apply filters").click()
        row = page.locator("tr").filter(has_text=code)
        expect(row).to_be_visible()
        row.locator('input[name="selected"]').check()
        page.get_by_role("button", name="Mark as Printed").click()
        expect(page.get_by_text(re.compile(r"1 updated.*1 SMS.*0 failed"))).to_be_visible()
        page.goto(f"{BASE_URL}/officer/applications/{code}/", wait_until="networkidle")
        expect(page.get_by_text("Printed", exact=True).first).to_be_visible()

        # A supervisor can open reporting pages.
        page.locator("form[action='/officer/logout/'] button").click()
        page.goto(f"{BASE_URL}/officer/login/", wait_until="networkidle")
        page.get_by_label("Username").fill("supervisor")
        page.get_by_label("Password").fill("super123")
        page.get_by_role("button", name="Sign in").click()
        page.goto(f"{BASE_URL}/officer/reports/", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Reports")).to_be_visible()
        expect(page.get_by_text("Monthly intake")).to_be_visible()

        # Public and staff surfaces must fit a 320 px viewport without page-level overflow.
        mobile = browser.new_page(viewport={"width": 320, "height": 780})
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(f"{BASE_URL}/", wait_until="networkidle")
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Public home overflows at 320 px"  # noqa: E501
        mobile.goto(f"{BASE_URL}/ussd-demo/", wait_until="networkidle")
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "USSD demo overflows at 320 px"  # noqa: E501

        assert not errors, "Browser JavaScript errors: " + " | ".join(errors)
        print(f"PASS: registered {code}, advanced to Approved, public lookup, USSD check, bulk-marked Printed, and opened reports.")  # noqa: E501
        browser.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
