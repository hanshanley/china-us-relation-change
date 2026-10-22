#!/usr/bin/env python3
"""Browser checks for collective coverage, exact plot values and responsive layout."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(site, url=None, screenshots=None):
    url = url or (site.resolve() / "index.html").as_uri()
    data = json.loads((site / "downloads/exchange.json").read_text())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            expect(page.locator("form.controls")).to_be_visible()
            assert page.locator("#geography option").count() == 3
            assert page.locator("#chart").bounding_box()["y"] < 680
            assert page.locator("#chart").evaluate("node=>node.scrollWidth<=node.clientWidth")
            for geo in ("CHN", "HKG", "MAC"):
                page.select_option("#geography", geo)
                for direction in ("to_us", "from_us"):
                    page.select_option("#direction", direction)
                    origin, destination = (geo, "USA") if direction == "to_us" else ("USA", geo)
                    for measure in data["measures"]:
                        page.select_option("#measure", measure)
                        annual = sorted((r for r in data["observations"] if r["origin"] == origin and r["destination"] == destination
                                         and r["measure"] == measure and r["frequency"] == "annual" and r["value"] is not None),
                                        key=lambda r: r["year"])
                        actual = page.locator("#chart .screen-point").evaluate_all(
                            "nodes=>nodes.map(n=>[Number(n.dataset.year),Number(n.dataset.value)])")
                        assert actual == [[r["year"], r["value"]] for r in annual], (geo, direction, measure)
                        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth"), (geo, direction, measure)
            page.select_option("#geography", "CHN")
            page.select_option("#direction", "to_us")
            page.select_option("#measure", "goods")
            expect(page.locator("#latest-period")).to_contain_text("2025")
            expect(page.locator("#partial-panel")).to_contain_text("2026")
            assert page.locator("#chart svg text").evaluate_all("""nodes=>nodes.every(n=>{
              const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;
              return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
            })""")
            page.select_option("#chart-mode", "index")
            assert float(page.locator("#chart .screen-point[data-year='2020']").get_attribute("data-value")) == 100
            page.select_option("#measure", "international_students")
            assert not page.locator("#chart svg").count()
            expect(page.locator("#chart")).to_contain_text("Definitions differ")
            page.select_option("#chart-mode", "levels")
            page.select_option("#measure", "goods")
            if screenshots:
                page.screenshot(path=str(screenshots / f"collective-exchanges-{width}.png"))
            for name in ["comparisons.html", "language-learning.html", "business-presence.html", "weibo.html"]:
                page.goto(url.rsplit("/", 1)[0] + "/" + name)
                page.evaluate("document.fonts.ready")
                expect(page.locator(".module-controls")).to_be_visible()
                if name == "language-learning.html":
                    assert page.locator("#ap-chinese-global .screen-point").count() == 38
                    years = page.locator("#ap-chinese-global .screen-year").all_text_contents()
                    assert years[0] == "2007" and years[-1] == "2025"
                    expect(page.locator("#ap-chinese-global .ap-group-note")).to_contain_text("including")
                    page.select_option("#module-chart", "ap-language-standard-group")
                    expect(page.locator("#ap-language-standard-group .ap-group-note")).to_contain_text("Do not add")
                for option in page.locator("#module-chart option").all():
                    page.select_option("#module-chart", option.get_attribute("value"))
                    assert page.locator("[data-module-chart]:visible").count() == 1
                    assert page.locator("[data-module-chart]:visible .screen-chart").count()
                    assert page.locator("[data-module-chart]:visible .screen-chart text").evaluate_all("""nodes=>nodes.every(n=>{
                      const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;
                      return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
                    })"""), (width, name, option.get_attribute("value"), "clipped chart labels")
                    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth"), name
                if screenshots:
                    page.screenshot(path=str(screenshots / f"collective-{name[:-5]}-{width}.png"))
            page.goto(url.rsplit("/", 1)[0] + "/language-learning.html?indicator=college-benchmarks")
            expect(page.locator("#module-chart")).to_have_value("college-benchmarks")
            assert page.locator('#college-benchmarks .screen-line[data-series-id="mla:korean"]').count() == 1
            assert not errors, errors
            page.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto(url)
        expect(page.locator("form.controls")).to_be_hidden()
        assert page.locator("#chart svg").count() == 1
        assert page.locator("#all-values table").count() > 20
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        browser.close()
    print("Collective coverage, exact values, 2025/2026 periods, filters and mobile/no-JS checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.site, args.url, args.screenshots)
