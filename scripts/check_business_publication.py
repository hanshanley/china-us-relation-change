#!/usr/bin/env python3
"""Check full investment histories, separate survey bars and complete downloads."""

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def check(site, url=None):
    name = "business-presence.html" if (site / "business-presence.html").is_file() else "index.html"
    url = url or (site.resolve() / name).as_uri()
    archive = json.loads((site / "downloads/business-presence.json").read_text())
    data = json.loads((site / "downloads/business-current.json").read_text())
    with (site / "downloads/business-observations.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == len(archive["observations"])
    with (site / "downloads/business-current-observations.csv").open() as stream:
        rows = list(csv.DictReader(stream))
        assert len(rows) == len(data["observations"])
        assert {(r["series_id"], int(r["year"]), float(r["value"])) for r in rows} == {
            (r["series_id"], r["year"], r["value"]) for r in data["observations"]}
        assert all(r["source_assets"] and r["source_locator"] for r in rows)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390, 320):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            expect(page.locator(".business-card:visible")).to_have_count(4)
            expect(page.locator(".screen-chart")).to_have_count(4)
            assert not page.locator("#module-chart,#business-controls,#annual-values,.covid-band,.covid-context").count()
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            for chart, sid in [("us-investment-mainland", "bea_position:CHN"),
                               ("us-investment-hong-kong", "bea_position:HKG")]:
                expected = sorted((r for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
                points = page.locator(f"#{chart} .screen-point")
                assert points.evaluate_all("nodes => nodes.map(n => [+n.dataset.year,+n.dataset.value])") == [
                    [r["year"], r["value"]] for r in expected]
                assert [r["year"] for r in expected] == list(range(2000, 2026))
                expect(page.locator(f"#{chart} .screen-column")).to_have_count(len(expected))
                region = page.locator(f"#{chart} .native-chart")
                svg = region.locator(".screen-chart")
                svg.focus()
                svg.press("Home")
                svg.press("ArrowRight")
                tooltip = page.locator("#" + region.get_attribute("data-tooltip-id"))
                expect(tooltip).to_be_visible()
                expect(tooltip).to_contain_text("2001")
                svg.press("Escape")
            for chart, values in [("us-company-decisions", [78, 58, 39, 28]),
                                  ("german-company-risk", [33, 47, 14])]:
                assert page.locator(f"#{chart} .screen-bar").evaluate_all(
                    "nodes => nodes.map(n => +n.dataset.value)") == values
                assert page.locator(f"#{chart} svg").get_attribute("data-axis-max") == "100"
            page.locator("#business-data > summary").click()
            expect(page.locator("#business-data table tbody tr")).to_have_count(len(data["observations"]))
            for link in page.locator('a[href^="figures/"],a[href^="downloads/"]').all():
                assert (site / urlsplit(link.get_attribute("href")).path).is_file()
            assert not errors, errors
            page.close()
        touch = browser.new_context(has_touch=True, viewport={"width": 390, "height": 900})
        page = touch.new_page()
        page.goto(url)
        column = page.locator("#us-investment-mainland .screen-column").nth(0)
        column.tap()
        tooltip_id = page.locator("#us-investment-mainland .native-chart").get_attribute("data-tooltip-id")
        expect(page.locator("#" + tooltip_id)).to_contain_text("2000")
        touch.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page = context.new_page()
        page.goto(url)
        expect(page.locator(".business-card:visible")).to_have_count(4)
        expect(page.locator("#us-investment-mainland .annual-column")).to_have_count(26)
        assert not page.locator(".covid-band").count()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert page.locator("a[data-original-chart]").count() == 16
        for link in page.locator('a[href^="figures/"]').all():
            assert (site / urlsplit(link.get_attribute("href")).path).is_file()
        browser.close()
    print("Business histories, survey bars, complete downloads, phone, touch, keyboard and no-JS checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url", help="Optional served or live URL instead of a local file")
    args = parser.parse_args()
    check(args.site, args.url)
