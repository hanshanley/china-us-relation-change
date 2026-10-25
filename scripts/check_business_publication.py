#!/usr/bin/env python3
"""Check country affiliate counts, investment histories and complete downloads."""

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
    inward_path = site / "downloads/business-inward.json"
    inward = json.loads(inward_path.read_text()) if inward_path.is_file() else None
    count_series = {
        "us-affiliates-china": "bea_affiliates:china",
        "germany-affiliates-china": "bundesbank_germany:china",
        "germany-affiliates-china-eurostat": "eurostat_germany:china",
        "norway-affiliates-china": "ssb_norway:china",
        "sweden-affiliates-china": "tillvaxtanalys_sweden:china",
        "finland-affiliates-china": "statfin_finland:china",
        "france-affiliates-china": "eurostat_france:china",
        "netherlands-affiliates-china": "eurostat_netherlands:china",
        "finland-affiliates-china-eurostat": "eurostat_finland:china",
        "sweden-affiliates-china-eurostat": "eurostat_sweden:china",
    }
    counts = {
        chart: sorted((r for r in archive["observations"] if r["series_id"] == sid and r["value"] is not None),
                      key=lambda r: r["year"])
        for chart, sid in count_series.items()}
    counts = {chart: rows for chart, rows in counts.items()
              if len(rows) > 1 and max(r["year"] for r in rows) >= 2023}
    chart_count = (6 if inward is not None else 4) + len(counts)
    new_counts = {chart: rows for chart, rows in counts.items()
                  if chart in {"sweden-affiliates-china", "finland-affiliates-china", "france-affiliates-china",
                               "netherlands-affiliates-china", "finland-affiliates-china-eurostat",
                               "sweden-affiliates-china-eurostat"}}
    visible_count = (6 if inward is not None else 4) + len(new_counts)
    if inward is not None:
        with (site / "downloads/business-inward-observations.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == len(inward["observations"]) == 50
        assert {(r["series_id"], int(r["year"]), int(r["value"])) for r in rows} == {
            (r["series_id"], r["year"], r["value"]) for r in inward["observations"]}
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
            expect(page.locator(".business-card:visible")).to_have_count(visible_count)
            expect(page.locator(".native-chart")).to_have_count(chart_count)
            expect(page.locator(".screen-chart")).to_have_count(visible_count)
            assert not page.locator("#module-chart,#business-controls,#annual-values,.covid-band,.covid-context").count()
            assert not page.locator("#uk-affiliates-china,#eu-affiliates-china,#us-parent-companies-china").count()
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            if counts.keys() - new_counts.keys():
                references = page.locator("#business-count-references")
                assert references.get_attribute("open") is None
                references.locator(":scope > summary").click()
                expect(page.locator(".business-card:visible")).to_have_count(chart_count)
                expect(page.locator(".screen-chart")).to_have_count(chart_count)
            for chart, expected in counts.items():
                assert page.locator(f"#{chart} .screen-point").evaluate_all(
                    "nodes => nodes.map(n => [+n.dataset.year,+n.dataset.value])") == [
                        [r["year"], r["value"]] for r in expected]
                expect(page.locator(f"#{chart} .screen-column")).to_have_count(len(expected))
                svg = page.locator(f"#{chart} .screen-chart")
                svg.focus()
                svg.press("End")
                tooltip_id = page.locator(f"#{chart} .native-chart").get_attribute("data-tooltip-id")
                expect(page.locator("#" + tooltip_id)).to_contain_text(str(expected[-1]["year"]))
                expect(page.locator("#" + tooltip_id)).to_contain_text(f'{expected[-1]["value"]:,}')
                svg.press("Escape")
            if counts.keys() - new_counts.keys():
                summary = page.locator("#business-count-references > summary")
                for _ in range(2):
                    summary.click()
                    expect(page.locator(".business-card:visible")).to_have_count(visible_count)
                    for chart, rows in new_counts.items():
                        expect(page.locator(f"#{chart} .screen-column:visible")).to_have_count(len(rows))
                    summary.focus()
                    summary.press("Enter")
                    expect(page.locator(".business-card:visible")).to_have_count(chart_count)
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
            if inward is not None:
                for chart, geo in [("china-ubo-us-affiliates", "CHN"), ("hong-kong-ubo-us-affiliates", "HKG")]:
                    expected = [r for r in inward["observations"] if r["series_id"] == "bea_mousa:" + geo
                                and r["comparability"] == "including_banks:USD20000000"]
                    assert page.locator(f"#{chart} .screen-point").evaluate_all(
                        "nodes => nodes.map(n => [+n.dataset.year,+n.dataset.value])") == [
                            [r["year"], r["value"]] for r in expected]
                    assert [r["year"] for r in expected] == list(range(2012, 2025))
                    svg = page.locator(f"#{chart} .screen-chart")
                    svg.focus()
                    svg.press("End")
                    tooltip_id = page.locator(f"#{chart} .native-chart").get_attribute("data-tooltip-id")
                    expect(page.locator("#" + tooltip_id)).to_contain_text("Fiscal year ending 2024")
                    expect(page.locator("#" + tooltip_id)).to_contain_text(str(expected[-1]["value"]))
                    svg.press("Escape")
                page.locator("#business-inward-data > summary").click()
                expect(page.locator("#business-inward-data table tbody tr")).to_have_count(25)
                expect(page.locator("#business-inward-data")).to_contain_text("not joined")
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
        for chart in ("sweden-affiliates-china", "finland-affiliates-china", "france-affiliates-china",
                      "netherlands-affiliates-china", "finland-affiliates-china-eurostat",
                      "sweden-affiliates-china-eurostat"):
            if chart in counts:
                page.locator(f"#{chart} .screen-column").last.tap()
                tooltip_id = page.locator(f"#{chart} .native-chart").get_attribute("data-tooltip-id")
                expect(page.locator("#" + tooltip_id)).to_contain_text(f'{counts[chart][-1]["value"]:,}')
        touch.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page = context.new_page()
        page.goto(url)
        expect(page.locator(".business-card:visible")).to_have_count(visible_count)
        if counts.keys() - new_counts.keys():
            page.locator("#business-count-references > summary").click()
            expect(page.locator(".business-card:visible")).to_have_count(chart_count)
        expect(page.locator("#us-investment-mainland .annual-column")).to_have_count(26)
        for chart, rows in counts.items():
            expect(page.locator(f"#{chart} .annual-column")).to_have_count(len(rows))
        assert not page.locator(".covid-band").count()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert page.locator("a[data-original-chart]").count() == chart_count * 4
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
