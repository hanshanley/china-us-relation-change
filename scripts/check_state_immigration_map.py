#!/usr/bin/env python3
"""Audit every state identity, colour, value, export and map interaction."""

import argparse
import csv
import io
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import expect, sync_playwright
from us_china_exchange.state_immigration_sources import validate


def expected_color(value, metric):
    bounds = (0, 2, 4, 6, 8, 10) if metric == "share" else (0, 5000, 20000, 50000, 100000, 250000)
    palette = ("#F0E5E2", "#E1C7C1", "#CCA099", "#B4776E", "#98534A", "#7B2D26")
    return "#D6D3CC" if value is None else palette[sum(value >= b for b in bounds[1:])]


def check_export(path, data):
    svg = ElementTree.fromstring(path.read_text())
    metric = svg.attrib["data-state-map"]
    field = "share_percent" if metric == "share" else "china_born"
    expected = {s["fips"]: s for s in data["states"]}
    marks = [n for n in svg.iter() if n.attrib.get("class") == "state-shape"]
    assert len(marks) == 51 and {n.attrib["data-state-fips"] for n in marks} == expected.keys()
    assert svg.attrib["data-period"] == f'{data["start_year"]}-{data["end_year"]}'
    for mark in marks:
        row = expected[mark.attrib["data-state-fips"]]
        for attribute, key in (("data-china-born", "china_born"), ("data-foreign-born", "foreign_born"),
                               ("data-share-percent", "share_percent")):
            actual = mark.attrib[attribute]
            assert actual == "" if row[key] is None else math.isclose(float(actual), row[key], rel_tol=1e-12)
        assert mark.attrib["fill"] == expected_color(row[field], metric)
        assert mark.attrib["d"].startswith("M") and mark.attrib["d"].endswith("Z")
        assert row["name"] in "".join(mark.itertext())
    png = path.with_suffix(".png")
    content = png.read_bytes()
    assert content[:8] == b"\x89PNG\r\n\x1a\n"
    assert (int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")) == (3000, 1800)


def check_page(page, data, exhaustive=False):
    if page.locator("#module-chart").count():
        page.select_option("#module-chart", "state-china-map")
    panel = page.locator("#state-china-map")
    expect(panel).to_be_visible()
    expect(panel.locator(".state-map-controls")).to_be_visible()
    assert panel.locator(".state-shape").count() == 51
    assert panel.locator("#state-map-select option").count() == 52
    selected = data["states"] if exhaustive else [next(r for r in data["states"] if r["fips"] == "06")]
    for metric in ("count", "share"):
        panel.locator(f'[data-map-metric="{metric}"]').click()
        expect(panel.locator(f'[data-map-metric="{metric}"]')).to_have_attribute("aria-pressed", "true")
        actual = panel.locator(".state-shape").evaluate_all(
            "nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.stateFips,n.getAttribute('fill')]))")
        field = "share_percent" if metric == "share" else "china_born"
        assert actual == {s["fips"]: expected_color(s[field], metric) for s in data["states"]}
        for row in selected:
            panel.locator("#state-map-select").select_option(row["fips"])
            readout = panel.locator(".state-map-readout")
            expect(readout).to_have_attribute("data-state-fips", row["fips"])
            expect(readout).to_contain_text(row["name"])
            for field in ("china_born", "foreign_born"):
                expect(readout).to_contain_text(f'{row[field]:,}' if row[field] is not None else "Unavailable")
            expect(readout).to_contain_text(f'{row["share_percent"]:.2f}%' if row["share_percent"] is not None else "Unavailable")
            if row["china_born_moe"] is not None:
                expect(readout).to_contain_text(f'{row["china_born_moe"]:,}')
    wyoming = panel.locator('.state-shape[data-state-fips="56"]')
    wyoming.focus()
    expect(panel.locator(".state-map-readout")).to_contain_text("Wyoming")
    wyoming.press("Enter")
    expect(panel.locator("#state-map-select")).to_have_value("56")
    wyoming.press("Escape")
    expect(panel.locator("#state-map-select")).to_have_value("")
    expect(panel.locator(".state-map-readout")).to_contain_text("United States")
    panel.locator('.state-shape[data-state-fips="48"]').hover()
    expect(panel.locator(".state-map-readout")).to_contain_text("Texas")
    page.mouse.move(0, 0)
    expect(panel.locator(".state-map-readout")).to_contain_text("United States")
    dc = panel.locator(".state-callout")
    dc.focus()
    dc.press(" ")
    expect(panel.locator("#state-map-select")).to_have_value("11")
    expect(panel.locator(".state-map-readout")).to_contain_text("District of Columbia")
    panel.locator(".state-map-table").evaluate("node=>node.open=true")
    assert panel.locator("[data-state-row]").count() == 51
    panel.locator(".state-map-table").evaluate("node=>node.open=false")
    for region in ("02", "15"):
        shape = panel.locator(f'.state-shape[data-state-fips="{region}"]')
        assert shape.evaluate("n=>{const b=n.getBBox();return b.width>2&&b.height>2}")
    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert panel.locator("svg").evaluate("""n=>{
      const v=n.viewBox.baseVal;
      return [...n.querySelectorAll('.state-shape,.state-callout,text')].every(n=>{
        const b=n.getBBox();
        return b.x>=v.x-1&&b.y>=v.y-1&&b.x+b.width<=v.x+v.width+1&&b.y+b.height<=v.y+v.height+1;
      });
    }"""), "Clipped map shapes or labels"
    panel.locator('[data-map-metric="share"]').click()
    panel.locator("#state-map-select").select_option("")


def check(site, url=None, screenshots=None):
    data = json.loads((site / "downloads/state-immigration.json").read_text())
    geometry = json.loads((site / "downloads/us-states.geojson").read_text())
    validate(data, geometry)
    rows = list(csv.DictReader(io.StringIO((site / "downloads/state-immigration.csv").read_text())))
    assert {r["fips"] for r in rows} == {r["fips"] for r in data["states"]} and len(rows) == 51
    for row in rows:
        expected = next(s for s in data["states"] if s["fips"] == row["fips"])
        for field in ("china_born", "foreign_born", "share_percent"):
            assert row[field] == "" if expected[field] is None else math.isclose(
                float(row[field]), expected[field], rel_tol=1e-12)
    for theme in ("themarginoferror", "substack"):
        for metric in ("count", "share"):
            check_export(site / f"figures/immigration/{theme}/state-china-{metric}.svg", data)
    url = url or (site.resolve() / "immigration.html").as_uri()
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            check_page(page, data, exhaustive=True)
            if screenshots:
                page.locator("#state-china-map").screenshot(path=str(screenshots / f"state-map-share-{width}.png"))
                page.locator('[data-map-metric="count"]').click()
                page.select_option("#state-map-select", "06")
                page.locator("#state-china-map").screenshot(path=str(screenshots / f"state-map-count-{width}.png"))
            assert not errors, errors
            page.close()
        touch = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = touch.new_page()
        page.goto(url)
        if page.locator("#module-chart").count():
            page.select_option("#module-chart", "state-china-map")
        panel = page.locator("#state-china-map")
        expect(panel).to_be_visible()
        panel.locator('.state-shape[data-state-fips="06"]').tap()
        expect(panel.locator("#state-map-select")).to_have_value("06")
        expect(panel.locator(".state-map-readout")).to_contain_text("California")
        panel.locator("#state-map-select").select_option("15")
        expect(panel.locator(".state-map-readout")).to_contain_text("Hawaii")
        touch.close()
        fallback = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = fallback.new_page()
        page.goto(url)
        expect(page.locator(".state-map-controls")).to_be_hidden()
        expect(page.locator(".state-map-chart")).to_be_visible()
        assert page.locator(".state-shape").count() == 51
        page.locator(".state-map-table").evaluate("node=>node.open=true")
        assert page.locator("[data-state-row]").count() == 51
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        fallback.close()
        browser.close()
    print("All 51 state identities, both colour scales, exact values, exports, touch, keyboard and no-JS map checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.site, args.url, args.screenshots)
