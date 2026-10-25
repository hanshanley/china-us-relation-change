#!/usr/bin/env python3
"""Check every opinion plot against complete survey data on desktop, phone and no-JS."""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import expect, sync_playwright
from us_china_exchange.opinion_analysis import CHARTS
from us_china_exchange.opinion_sources import validate_opinion_data


def expected_rows(data, config):
    result = []
    for sid in config["series"]:
        rows = sorted((r for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
        if config.get("first_survey_per_year"):
            rows = [min((row for row in rows if row["year"] == year),
                        key=lambda row: data["surveys"][row["survey_id"]]["field_start"])
                    for year in sorted({row["year"] for row in rows})]
        if config.get("latest"):
            rows = [r for r in rows if r["year"] == max(p["year"] for p in rows)]
        result.extend(r for r in rows if r["value"] is not None)
    return result


def check_page(page, data, exhaustive=True):
    expect(page.locator("#module-chart")).to_be_visible()
    choices = set(page.locator("#module-chart option").evaluate_all("nodes=>nodes.map(n=>n.value)"))
    expected = set(CHARTS) - {"us-china-earlier-favorability", "china-us-earlier-favorability"}
    assert choices == expected
    for chart_id, config in CHARTS.items():
        if chart_id not in choices:
            assert not page.locator("#" + chart_id).count()
            continue
        page.select_option("#module-chart", chart_id)
        panel = page.locator("#" + chart_id)
        expect(panel).to_be_visible()
        assert page.locator("[data-module-chart]:visible").count() == 1
        chart = panel.locator(".native-chart")
        assert not chart.locator(".covid-band,.covid-label").count(), chart_id
        expect(chart.locator(".screen-chart")).to_have_attribute("data-axis-max", "100")
        rows = expected_rows(data, config)
        expect(chart.locator(".plot-unit,.screen-unit")).to_have_text(config["unit"])
        selector = ".screen-bar" if config["mode"] == "bars" else ".screen-point"
        marks = chart.locator(selector)
        values = marks.evaluate_all("nodes=>nodes.map(n=>+n.dataset.value)")
        assert values == [r["value"] for r in rows], chart_id
        if config["mode"] == "bars":
            assert chart.locator(".screen-bar-track").count() == len(rows)
            for i, row in enumerate(rows):
                ratio = marks.nth(i).evaluate("n=>+n.getAttribute('width')/(n.ownerSVGElement.viewBox.baseVal.width-10)")
                assert math.isclose(ratio, row["value"] / 100, abs_tol=1e-9), chart_id
        else:
            assert chart.locator(".screen-y-tick").all_text_contents() == ["0", "25", "50", "75", "100"]
            if chart_id == "us-china-favorability":
                assert min(row["year"] for row in rows) == 2000
                assert max(row["year"] for row in rows) == 2026
                assert len(rows) == 54
                assert "Gallup" in panel.inner_text()
        assert chart.locator(".screen-chart").evaluate("""svg=>{
          const v=svg.viewBox.baseVal;
          return [...svg.querySelectorAll('text')].every(n=>{
            const b=n.getBBox();return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
          });
        }"""), (chart_id, "clipped labels")
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        if exhaustive:
            marks.last.hover()
            tip = page.locator("#" + chart.get_attribute("data-tooltip-id"))
            expect(tip).to_be_visible()
            expected = f'{rows[-1]["value"]:,.2f}'.rstrip("0").rstrip(".")
            if "percent" in config["unit"].lower():
                expected += "%"
            assert expected in tip.locator(".plot-tooltip-value").all_text_contents(), chart_id
            svg = chart.locator(".screen-chart")
            svg.focus()
            svg.press("Home")
            expect(tip).to_be_visible()
            svg.press("End")
            expect(tip).to_contain_text(rows[-1]["period"])
            svg.press("Escape")
            expect(tip).to_be_hidden()
    page.select_option("#module-chart", "us-china-favorability")


def check(site, url=None, screenshots=None):
    data = json.loads((site / "downloads/opinions.json").read_text())
    validate_opinion_data(data)
    rows = list(csv.DictReader((site / "downloads/opinion-observations.csv").open()))
    assert len(rows) == len(data["observations"])
    assert {(r["series_id"], r["survey_id"]) for r in rows} == {
        (r["series_id"], r["survey_id"]) for r in data["observations"]}
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    url = url or (site.resolve() / "opinions.html").as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390, 320):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            check_page(page, data)
            if screenshots:
                for chart_id in CHARTS:
                    if not page.locator("#" + chart_id).count():
                        continue
                    page.select_option("#module-chart", chart_id)
                    page.locator("#" + chart_id).screenshot(path=str(screenshots / f"{chart_id}-{width}.png"))
            assert not errors, errors
            page.close()
        touch = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = touch.new_page()
        page.goto(url)
        page.select_option("#module-chart", "us-china-age")
        panel = page.locator("#us-china-age .native-chart")
        panel.locator(".screen-bar").first.tap()
        tip = page.locator("#" + panel.get_attribute("data-tooltip-id"))
        expect(tip).to_be_visible()
        expect(tip).to_contain_text("38%")
        page.select_option("#module-chart", "china-us-age")
        panel = page.locator("#china-us-age .native-chart")
        panel.locator(".screen-bar").nth(1).tap()
        tip = page.locator("#" + panel.get_attribute("data-tooltip-id"))
        expect(tip).to_contain_text("29")
        assert "%" not in tip.locator(".plot-tooltip-value").inner_text()
        touch.close()
        fallback = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = fallback.new_page()
        page.goto(url)
        expect(page.locator(".module-controls")).to_be_hidden()
        for chart_id in CHARTS:
            if not page.locator("#" + chart_id).count():
                continue
            panel = page.locator("#" + chart_id)
            expect(panel).to_be_visible()
            assert panel.locator(".comparison-chart > svg").count() == 1
            assert not panel.locator(".covid-band,.covid-label").count()
            panel.locator("details").first.evaluate("n=>n.open=true")
            assert panel.locator("tbody tr").count() == len(expected_rows(data, CHARTS[chart_id]))
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        fallback.close()
        browser.close()
    print("All opinion values, age bands, bounded scales, hover, keyboard, touch and no-JS checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.site, args.url, args.screenshots)
