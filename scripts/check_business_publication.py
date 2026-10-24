#!/usr/bin/env python3
"""Check the curated business page, filters and no-JavaScript fallback."""

import argparse
import csv
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(site, url=None):
    url = url or (site.resolve() / "index.html").as_uri()
    data = json.loads((site / "downloads/business-presence.json").read_text())
    with (site / "downloads/business-observations.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == len(data["observations"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            expect(page.locator("#business-controls")).to_be_visible()
            assert page.locator("section[data-business-origin]:visible").count() == 4
            assert page.locator("#annual-values tbody tr:visible").count() == 25
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            assert page.locator("#us-affiliates-china svg").evaluate(
                "node => node.viewBox.baseVal.width") == 1000
            page.select_option("#business-origin", "eu")
            assert page.locator("section[data-business-origin]:visible").count() == 1
            expect(page.locator("#eu-affiliates-china")).to_be_visible()
            assert page.locator("#annual-values thead th:visible").count() == 3
            expect(page.locator("#business-benchmark-background")).to_be_hidden()
            page.locator("#business-start").fill("2014")
            page.locator("#business-start").press("Tab")
            page.locator("#business-end").fill("2022")
            page.locator("#business-end").press("Tab")
            assert page.locator("#annual-values tbody tr:visible").count() == 9
            assert page.locator("#eu-affiliates-china .business-point").count() == 12
            expect(page.locator("#business-filter-status")).to_contain_text("table only")
            page.locator("#business-start").fill("2023")
            page.locator("#business-start").press("Tab")
            expect(page.locator("#business-filter-status")).to_contain_text("start no later than end")
            assert page.locator("#annual-values tbody tr:visible").count() == 9
            page.locator("#business-start").fill("")
            page.locator("#business-start").press("Tab")
            expect(page.locator("#business-filter-status")).to_contain_text("Choose whole table years")
            page.locator("#business-start").fill("2000")
            page.locator("#business-start").press("Tab")
            page.locator("#business-end").fill("2024")
            page.locator("#business-end").press("Tab")
            for origin, chart, count in [("us", "us", 24), ("uk", "uk", 10), ("norway", "norway", 17)]:
                page.select_option("#business-origin", origin)
                assert page.locator("section[data-business-origin]:visible").count() == 1
                assert page.locator("#annual-values thead th:visible").count() == 2
                assert page.locator(f"#{chart}-affiliates-china .business-point").count() == count
            page.select_option("#business-origin", "all")
            page.locator("#business-benchmark-background > summary").click()
            assert page.locator("#us-parent-companies-china .business-point").count() == 4
            assert page.locator("section[data-business-origin]:visible").count() == 5
            assert not errors, errors
            page.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page = context.new_page()
        page.goto(url)
        expect(page.locator("#business-controls")).to_be_hidden()
        assert page.locator("section[data-business-origin]:visible").count() == 4
        assert page.locator("#annual-values tbody tr:visible").count() == 25
        assert page.locator("#annual-values thead th:visible").count() == 6
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert page.locator("a[data-original-chart]").count() == 20
        for link in page.locator('a[href^="figures/"]').all():
            assert (site / link.get_attribute("href")).is_file()
        browser.close()
    print("Business publication filters, complete downloads, desktop/mobile and no-JS fallback passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url", help="Optional served or live URL instead of a local file")
    args = parser.parse_args()
    check(args.site, args.url)
