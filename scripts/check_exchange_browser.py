#!/usr/bin/env python3
"""Offline browser acceptance checks; run after build_site.py."""
import json
from pathlib import Path
import sys

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from us_china_exchange.model import change
from us_china_exchange.render import comparison, number


def check():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    matrix = json.loads((ROOT / "data/site/coverage.json").read_text())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "site/index.html").as_uri())
        for cell in matrix:
            origin, destination, measure = (cell[k] for k in ["origin", "destination", "measure"])
            geo = destination if origin == "USA" else origin
            page.select_option("#geography", geo)
            page.select_option("#direction", "from_us" if origin == "USA" else "to_us")
            page.select_option("#measure", measure)
            available = [r for r in rows if (r["origin"], r["destination"], r["measure"], r["frequency"])
                         == (origin, destination, measure, "annual") and r["value"] is not None]
            if not available:
                assert page.locator("#annual-headlines .gap").is_visible()
                assert not page.locator("#partial-panel").is_visible()
                continue
            current = max(available, key=lambda r: r["year"])
            actual = page.locator("#latest-value").inner_text()
            expected = number(current["value"], current["unit"])
            assert actual == expected, (origin, destination, measure, actual, expected)
            baseline = next((r for r in available if r["year"] == 2020), None)
            assert page.locator("#baseline-change").inner_text() == comparison(change(current, baseline), current["unit"])
            assert page.locator("#chart svg").count() == 1
            partials = [r for r in rows if (r["origin"], r["destination"], r["measure"], r["frequency"])
                        == (origin, destination, measure, "ytd") and r["value"] is not None]
            partial = max(partials, key=lambda r: r["period"]) if partials else None
            panel = page.locator("#partial-panel")
            if partial and partial["year"] > current["year"]:
                assert panel.is_visible()
                text = panel.inner_text()
                assert number(partial["value"], partial["unit"]) in text
                assert partial["status"] in text
                for year in [2020, partial["year"] - 1]:
                    reference = next((r for r in partials
                                      if r["period"] == f"{year}-{partial['period'][5:]}"), None)
                    assert comparison(change(partial, reference), partial["unit"]) in text
            else:
                assert not panel.is_visible()
        page.select_option("#geography", "CHN")
        page.select_option("#direction", "to_us")
        page.select_option("#measure", "visitors")
        page.select_option("#chart-mode", "index")
        assert "2020 = 100" in page.locator("#chart").inner_text()
        page.select_option("#measure", "goods")
        if page.locator("#partial-panel").is_visible():
            assert "seasonally adjusted" in page.locator("#partial-panel").inner_text()
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.locator("#geography").focus()
        page.keyboard.press("h")
        page.keyboard.press("Tab")
        expect(page.locator("#series-title")).to_contain_text("Hong Kong")
        expect(page.locator("#direction")).to_be_focused()
        page.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto((ROOT / "site/index.html").as_uri())
        assert page.locator("noscript").is_visible()
        assert page.locator("#all-values details").count() > 30
        page.locator("#all-values summary").first.click()
        assert page.locator("#all-values table").first.is_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not errors, errors
        browser.close()
    print("Browser acceptance passed: all 64 combinations, exact changes, YTD, keyboard, mobile, no JavaScript.")


if __name__ == "__main__":
    check()
