#!/usr/bin/env python3
"""Independently reconcile dated program counts, bound geometry and interactions."""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from playwright.sync_api import expect, sync_playwright
from us_china_exchange.confucius_sources import validate


SERIES_BY_CHART = {
    "confucius-institutes": {"institutes_reported"},
    "confucius-campus": {"institutes_campus"},
    "confucius-classrooms": {"classrooms_reported"},
    "confucius-successors": {"successors_documented"},
    "confucius-directory": {"institutes_listed", "classrooms_listed"},
}


def display(row):
    if row["qualifier"] == "unknown":
        return "Unknown"
    prefix = {"exact": "", "approximate": "About ", "less_than": "Fewer than ", "at_least": "At least "}[row["qualifier"]]
    return prefix + f'{row["value"] if row["value"] is not None else row["bound"]:,}'


def expected_rows(data, chart_id):
    return {r["id"]: r for r in data["observations"] if r["series_id"] in SERIES_BY_CHART[chart_id]}


def check_export(path, data):
    soup = BeautifulSoup(path.read_text(), "html.parser")
    svg = soup.svg
    chart_id = svg["data-confucius-chart"]
    expected = expected_rows(data, chart_id)
    marks = svg.select(".confucius-mark")
    assert len(marks) == len(expected) and {m["data-observation-id"] for m in marks} == expected.keys()
    maximum = float(svg["data-axis-max"])
    assert not svg.select(".data-line,.screen-line")
    for mark in marks:
        row = expected[mark["data-observation-id"]]
        assert mark["data-qualifier"] == row["qualifier"] and mark["data-reference"] == row["reference"]
        assert mark["data-value"] == ("" if row["value"] is None else str(row["value"]))
        assert mark["data-bound"] == ("" if row["bound"] is None else str(row["bound"]))
        assert mark.select_one(".confucius-reported").text == display(row)
        if row["qualifier"] in {"less_than", "at_least"}:
            assert not mark.select(".confucius-bar")
            circle = mark.select_one(".confucius-boundary")
            assert circle and mark.select_one(".confucius-bound")
            assert math.isclose(float(circle["cx"]), 58 + row["bound"] / maximum * 870, abs_tol=.01)
        elif row["value"] is not None:
            bar = mark.select_one(".confucius-bar")
            assert math.isclose(float(bar["width"]), row["value"] / maximum * 870, abs_tol=.01)
    png = path.with_suffix(".png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == (3000, 1800)


def check_page(page, data, exhaustive=True):
    for category in ("institutes", "classrooms", "successors"):
        if page.locator("#module-chart").count():
            page.select_option("#module-chart", "confucius-" + category)
        panel = page.locator("#confucius-" + category)
        expect(panel).to_be_visible()
        if category == "institutes":
            panel.locator(".confucius-campus").evaluate("node=>node.open=true")
        for chart in panel.locator(".confucius-chart").all():
            chart_id = chart.get_attribute("data-confucius-chart")
            expected = expected_rows(data, chart_id)
            expect(chart).to_have_class(re.compile("js-ready"))
            marks = chart.locator(".confucius-hit")
            assert marks.count() == len(expected)
            for mark in marks.all():
                row = expected[mark.get_attribute("data-observation-id")]
                assert mark.get_attribute("data-value") == ("" if row["value"] is None else str(row["value"]))
                assert mark.get_attribute("data-bound") == ("" if row["bound"] is None else str(row["bound"]))
                assert mark.get_attribute("data-reference") == row["reference"]
                expect(mark.locator(".confucius-reported")).to_have_text(display(row))
                if row["bound"] is not None:
                    assert not mark.locator(".confucius-bar").count()
                    assert mark.locator(".confucius-boundary").count() == 1
                if row["value"] is not None:
                    assert mark.locator(".confucius-bar").evaluate("""(bar,value)=>{
                      const v=bar.ownerSVGElement.viewBox.baseVal;
                      const maximum=Number(bar.closest('.confucius-chart').querySelector('svg').dataset.axisMax);
                      return Math.abs(Number(bar.getAttribute('width'))-value/maximum*(v.width-22))<.01;
                    }""", row["value"]), (chart_id, row["id"], "incorrect bar width")
                if exhaustive or row["bound"] is not None:
                    mark.focus()
                    tip = page.locator(f'.confucius-tooltip[data-observation-id="{row["id"]}"]')
                    expect(tip).to_be_visible()
                    expect(tip).to_contain_text(display(row))
                    expect(tip).to_contain_text(data["sources"][row["source_id"]]["name"])
                    expect(tip).to_contain_text(data["series"][row["series_id"]]["scope"])
                    mark.press("Escape")
                    expect(tip).to_be_hidden()
            # Every visible label must fit the responsive SVG; bounds have no exact-count bar.
            assert chart.locator("svg").evaluate("""svg=>{
              const v=svg.viewBox.baseVal;
              return [...svg.querySelectorAll('text')].every(n=>{
                const b=n.getBBox();return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
              });
            }"""), (chart_id, "clipped label")
            assert chart.locator(".confucius-hit").evaluate_all("""nodes=>nodes.every(n=>{
              const labels=n.querySelectorAll('text'), a=labels[0].getBBox(), b=labels[1].getBBox();
              return a.x+a.width+5<=b.x;
            })"""), (chart_id, "overlapping date/value labels")
            assert chart.locator("svg").bounding_box()["height"] <= 530
            marks.first.focus()
            marks.first.press("End")
            expect(marks.last).to_be_focused()
            marks.last.press("Home")
            expect(marks.first).to_be_focused()
            marks.first.press("Escape")
        if category == "institutes":
            panel.locator(".confucius-campus").evaluate("node=>node.open=false")
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
    directory = page.locator("details.confucius-directory")
    directory.evaluate("node=>node.open=true")
    chart = directory.locator(".confucius-chart")
    expect(chart).to_have_class(re.compile("js-ready"))
    assert chart.locator(".confucius-hit").count() == 2
    assert directory.locator("[data-directory-id]").count() == len([
        r for r in data["records"] if r["source_id"] == "cief_directory"])
    directory.evaluate("node=>node.open=false")
    if page.locator("#module-chart").count():
        page.select_option("#module-chart", "confucius-institutes")


def check(site, url=None, screenshots=None):
    data = validate(json.loads((site / "downloads/confucius-programs.json").read_text()))
    values = list(csv.DictReader((site / "downloads/confucius-observations.csv").open()))
    records = list(csv.DictReader((site / "downloads/confucius-records.csv").open()))
    assert len(values) == len(data["observations"]) and len(records) == len(data["records"])
    assert {r["id"] for r in values} == {r["id"] for r in data["observations"]}
    assert {r["id"] for r in records} == {r["id"] for r in data["records"]}
    for row in values:
        original = next(r for r in data["observations"] if r["id"] == row["id"])
        for key in ("value", "bound"):
            assert row[key] == ("" if original[key] is None else str(original[key]))
        assert row["qualifier"] == original["qualifier"] and row["reference"] == original["reference"]
    for theme in ("substack", "themarginoferror"):
        for chart_id in SERIES_BY_CHART:
            check_export(site / f"figures/language_learning/{theme}/{chart_id}.svg", data)
    url = url or (site.resolve() / "confucius.html").as_uri()
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390, 320):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            expect(page.locator("#confucius-successors .confucius-summary")).to_contain_text("At least 28")
            assert page.locator("[data-confucius-row]").count() == len(values)
            check_page(page, data)
            for category in ("institutes", "classrooms", "successors"):
                page.select_option("#module-chart", "confucius-" + category)
                if screenshots:
                    page.screenshot(path=str(screenshots / f"confucius-{category}-{width}.png"), full_page=True)
            assert not errors, errors
            page.close()
        context = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto(url)
        page.select_option("#module-chart", "confucius-successors")
        mark = page.locator('[data-observation-id="nas_successors_2023"].confucius-hit')
        mark.tap()
        tip = page.locator('.confucius-tooltip[data-observation-id="nas_successors_2023"]')
        expect(tip).to_be_visible()
        expect(tip).to_contain_text("At least 28")
        page.touchscreen.tap(5, 5)
        expect(tip).to_be_hidden()
        context.close()
        fallback = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = fallback.new_page()
        page.goto(url)
        expect(page.locator(".module-controls")).to_be_hidden()
        assert page.locator(".series-panel:visible").count() == 3
        assert page.locator(".confucius-plot-data").count() == 5
        assert page.locator("[data-confucius-row]").count() == len(values)
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        fallback.close()
        page = browser.new_page()
        for theme in ("substack", "themarginoferror"):
            for chart_id in SERIES_BY_CHART:
                page.goto((site.resolve() / f"figures/language_learning/{theme}/{chart_id}.svg").as_uri())
                assert page.locator("svg").evaluate("""svg=>{
                  const v=svg.viewBox.baseVal, nodes=[...svg.querySelectorAll('text')];
                  if(!nodes.every(n=>{const b=n.getBBox();return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;}))return false;
                  const boxes=nodes.map(n=>n.getBBox());
                  return boxes.every((a,i)=>boxes.slice(i+1).every(b=>
                    Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)<=2||
                    Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)<=2));
                }"""), (chart_id, theme, "clipped/overlapping export labels")
        page.close()
        browser.close()
    print(f"Confucius publication: {len(values)} observations, {len(records)} records; exact bounds, all exports, desktop/phone, keyboard, touch and no-JS checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.site, args.url, args.screenshots)
