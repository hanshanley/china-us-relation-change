#!/usr/bin/env python3
"""Browser checks for collective coverage, exact plot values and responsive layout."""

import argparse
import json
import re
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
            assert page.locator("#coverage").evaluate("node=>node.tagName==='DETAILS'&&!node.open")
            assert not page.locator("#coverage-limits").count()
            assert page.locator("#geography option").count() == 3
            assert page.locator("#chart").bounding_box()["y"] < 680
            assert page.locator("#chart").evaluate("node=>node.scrollWidth<=node.clientWidth")
            for geo in ("CHN", "HKG", "MAC"):
                page.select_option("#geography", geo)
                for direction in ("to_us", "from_us"):
                    page.select_option("#direction", direction)
                    origin, destination = (geo, "USA") if direction == "to_us" else ("USA", geo)
                    for measure in data["measures"]:
                        annual = sorted((r for r in data["observations"] if r["origin"] == origin and r["destination"] == destination
                                         and r["measure"] == measure and r["frequency"] == "annual" and r["value"] is not None),
                                        key=lambda r: r["year"])
                        option = page.locator(f'#measure option[value="{measure}"]')
                        assert option.evaluate("(o)=>o.disabled") == (not annual), (geo, direction, measure)
                        if not annual:
                            continue
                        page.select_option("#measure", measure)
                        actual = page.locator("#chart .screen-point").evaluate_all(
                            "nodes=>nodes.map(n=>[Number(n.dataset.year),Number(n.dataset.value)])")
                        assert actual == [[r["year"], r["value"]] for r in annual], (geo, direction, measure)
                        if len(annual) == 1 or (len(annual) == 2 and annual[0]["source_id"] == "ustr"
                                               and len({r["comparability"] for r in annual}) == 2):
                            snapshots = page.locator("#chart .screen-snapshot")
                            expect(snapshots).to_have_count(len(annual))
                            bounds = re.fullmatch(r"M([\d.]+) [\d.]+H([\d.]+)",
                                                  page.locator("#chart .screen-chart path").first.get_attribute("d"))
                            assert bounds
                            for i, row in enumerate(annual):
                                snapshot = snapshots.nth(i)
                                point = page.locator("#chart .screen-point").nth(i)
                                centre = float(snapshot.get_attribute("x")) + float(snapshot.get_attribute("width")) / 2
                                assert abs(float(point.get_attribute("cx")) - centre) < .01
                                fraction = (row["year"] - annual[0]["year"] + .5) / (annual[-1]["year"] - annual[0]["year"] + 1)
                                expected = float(bounds[1]) + (float(bounds[2]) - float(bounds[1])) * fraction
                                assert abs(centre - expected) < .01
                                assert (float(snapshot.get_attribute("height")) > 0) == (row["value"] > 0)
                            assert page.locator("#chart .screen-year").all_text_contents() == [str(r["year"]) for r in annual]
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
            expect(page.locator("#chart-mode")).to_have_value("levels")
            expect(page.locator("#selection-note")).to_contain_text("Showing reported levels")
            assert page.locator("#chart .screen-point").count() == 26
            page.select_option("#measure", "enrolled_students")
            page.locator("#related-series button").click()
            expect(page.locator("#measure")).to_have_value("international_students")
            if data.get("student_estimates"):
                page.select_option("#direction", "from_us")
                expect(page.locator("#student-estimates")).to_be_visible()
                assert page.locator("#student-estimates tbody tr").count() == 5
                expect(page.locator("#student-estimates")).to_contain_text("<2,000 per year")
                page.select_option("#geography", "HKG")
                expect(page.locator("#student-estimates")).to_be_hidden()
                page.select_option("#geography", "CHN")
                page.select_option("#direction", "to_us")
            page.select_option("#chart-mode", "levels")
            page.select_option("#measure", "goods")
            if screenshots:
                page.screenshot(path=str(screenshots / f"collective-exchanges-{width}.png"))
            page.goto(url.rsplit("/", 1)[0] + "/travel.html")
            expect(page.locator("h1")).to_have_text("Travel & tourism")
            expect(page.locator("#measure")).to_have_value("visitors")
            expect(page.locator(".travel-definition")).to_contain_text("not just tourism")
            expect(page.locator("#latest-period")).to_contain_text("2025")
            expect(page.locator("#partial-panel")).to_contain_text("2026")
            assert page.locator("#chart .screen-point").count() == 26
            page.select_option("#direction", "from_us")
            expect(page.locator("#measure")).to_have_value("air_visitors")
            expect(page.locator("#selection-note")).to_contain_text("ends in 2018")
            assert page.locator("#chart .screen-point").count() == 13
            expect(page.locator("#series-population")).to_contain_text("2012–2025")
            expect(page.locator("#partial-panel")).to_contain_text("2026")
            assert float(page.locator("#chart .screen-point[data-year='2020']").get_attribute("data-value")) == 89000
            assert page.locator("#chart .screen-point[data-year='2021']").count() == 0
            expect(page.locator("#chart .screen-unit")).to_have_text("Trips (millions)")
            expect(page.locator("#series-continuity")).to_contain_text("2021 estimate is unavailable")
            chart_bounds = page.locator("#chart svg").bounding_box()
            assert chart_bounds["height"] >= chart_bounds["width"] * .5
            assert page.locator("#chart .screen-y-tick").evaluate_all(
                f"nodes=>nodes.every(n=>Number(n.getAttribute('font-size'))>={14 if width == 390 else 17})")
            expect(page.locator("#baseline-label")).to_contain_text("2019 (pre-pandemic)")
            page.select_option("#chart-mode", "index")
            assert float(page.locator("#chart .screen-point[data-year='2019']").get_attribute("data-value")) == 100
            page.select_option("#chart-mode", "levels")
            page.locator("#related-series button").click()
            expect(page.locator("#measure")).to_have_value("visitors")
            expect(page.locator("#latest-period")).to_contain_text("2018")
            assert page.locator("#chart .screen-point").count() == 19
            expect(page.locator("#related-series")).to_contain_text("ends in 2018")
            page.locator("#related-series button").click()
            expect(page.locator("#measure")).to_have_value("air_visitors")
            assert page.locator("#chart .screen-point").count() == 13
            if screenshots:
                page.locator(".exchange-panel").screenshot(path=str(screenshots / f"tourism-current-{width}.png"))
            for geo in ("CHN", "HKG"):
                page.select_option("#geography", geo)
                expect(page.locator("#latest-period")).to_contain_text("2025")
                expect(page.locator("#partial-panel")).to_contain_text("2026")
                expect(page.locator("#partial-panel")).to_contain_text(
                    "32,000 (+7.2%)" if geo == "CHN" else "53,000 (-17.4%)")
            page.select_option("#direction", "to_us")
            expect(page.locator("#measure")).to_have_value("visitors")
            expect(page.locator("#selection-note")).to_contain_text("no verified annual series for this route")
            assert page.locator("#chart .screen-point").count() == 26
            for name in ["immigration.html", "comparisons.html", "language-learning.html", "business-presence.html", "weibo.html"]:
                page.goto(url.rsplit("/", 1)[0] + "/" + name)
                page.evaluate("document.fonts.ready")
                expect(page.locator(".module-controls")).to_be_visible()
                if name == "comparisons.html":
                    page.select_option("#module-chart", "goods-to_us")
                    logarithmic = page.locator("#goods-to_us details").filter(has=page.locator(".native-chart"))
                    logarithmic.evaluate("node=>node.open=true")
                    expect(logarithmic.locator(".screen-unit")).to_have_text("Nominal US$ (log scale)")
                if name == "immigration.html":
                    page.select_option("#module-chart", "migrant-stock-from-us")
                    assert page.locator("#migrant-stock-from-us .screen-point").count() == 12
                    expect(page.locator("#migrant-stock-from-us")).to_contain_text("citizenship")
                    page.select_option("#module-chart", "green-card-grants")
                    assert page.locator("#green-card-grants .screen-point").count() == 75
                    page.select_option("#module-chart", "latest-admissions")
                    assert page.locator("#latest-admissions .screen-bar").evaluate_all(
                        "nodes=>nodes.map(n=>Number(n.dataset.value))") == [27020, 38650]
                if name == "language-learning.html":
                    expect(page.locator("#module-chart")).to_have_value("college-enrollments")
                    assert page.locator("#college-enrollments .screen-point").count() == 18
                    if width == 390:
                        years = page.locator("#college-enrollments .screen-year").all_text_contents()
                        assert years[0] == "2002" and years[-1] == "2021"
                        assert len(years) >= 4 and set(years) <= {"2002", "2006", "2009", "2013", "2016", "2021"}
                        assert page.locator("#college-enrollments .screen-year").evaluate_all("""nodes=>nodes.every((n,i)=>{
                          if(!i)return true;
                          const previous=nodes[i-1].getBBox(),current=n.getBBox();
                          return current.x-previous.x-previous.width>=7.9;
                        })""")
                    page.select_option("#module-chart", "school-language-enrollments")
                    assert page.locator("#school-language-enrollments .screen-bar").evaluate_all(
                        "nodes=>nodes.map(n=>Number(n.dataset.value))") == [227086, 67909]
                    page.select_option("#module-chart", "school-language-availability")
                    assert page.locator("#school-language-availability .screen-bar").evaluate_all(
                        "nodes=>nodes.map(n=>Number(n.dataset.value))") == [1144, 433, 43]
                    page.select_option("#module-chart", "ap-chinese-global")
                    assert page.locator("#ap-chinese-global .screen-point").count() == 38
                    years = page.locator("#ap-chinese-global .screen-year").all_text_contents()
                    assert years[0] == "2007" and years[-1] == "2025"
                    expect(page.locator("#ap-chinese-global .ap-scope-note")).to_contain_text("not U.S.-only")
                    assert page.locator('#module-chart option[value="ap-language-standard-group"]').count() == 0
                    assert page.locator("#ap-language-standard-group").count() == 0
                if name == "weibo.html":
                    weibo_summary = json.loads((site / "downloads/weibo-summary.json").read_text())
                    monthly = weibo_summary.get("monthly", [])
                    if monthly:
                        for chart, field in (("monthly-posts", "recovered_posts"), ("monthly-accounts", "observed_accounts")):
                            page.select_option("#module-chart", chart)
                            actual = page.locator(f"#{chart} .screen-point").evaluate_all(
                                "nodes=>nodes.map(n=>[n.dataset.month,Number(n.dataset.value),n.dataset.partialWindow==='true'])")
                            assert actual == [[row["month"], row[field], row["partial_window"]] for row in monthly]
                            assert page.locator(f"#{chart} .screen-partial-line").count()
                            expect(page.locator(f"#{chart} .chart-context")).to_contain_text("not total posting activity")
                            if monthly[-1]["month"] == "2026-10":
                                expect(page.locator(f"#{chart} .chart-context")).to_contain_text("2026")
                    rolling = [r for r in weibo_summary.get("rolling_30d", []) if not r["partial_window"]]
                    if rolling:
                        for chart, field in (("rolling30-accounts", "observed_accounts"),
                                             ("rolling30-outlets", "observed_outlets"),
                                             ("rolling30-posts", "recovered_posts"),
                                             ("rolling30-average", "posts_per_day")):
                            page.select_option("#module-chart", chart)
                            actual = page.locator(f"#{chart} .screen-point").evaluate_all(
                                "nodes=>nodes.map(n=>[n.dataset.date,Number(n.dataset.value)])")
                            assert actual == [[row["date"], row[field]] for row in rolling]
                            expect(page.locator(f"#{chart} .chart-context")).to_contain_text("not a census")
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
        touch = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = touch.new_page()
        page.goto(url.rsplit("/", 1)[0] + "/travel.html")
        page.select_option("#direction", "from_us")
        chart = page.locator("#chart")
        chart.scroll_into_view_if_needed()
        source = chart.locator('.screen-point[data-year="2020"]').bounding_box()
        plot = chart.locator(".screen-chart").bounding_box()
        page.touchscreen.tap(source["x"] + source["width"] / 2, plot["y"] + 55)
        old_id = chart.get_attribute("data-tooltip-id")
        tip = page.locator("#" + old_id)
        expect(tip).to_be_visible()
        expect(tip.locator(".plot-tooltip-value")).to_have_text("89,000")
        expect(tip.locator(".plot-tooltip-period")).to_have_text("2020")
        page.touchscreen.tap(8, 8)
        expect(tip).to_be_hidden()
        page.select_option("#geography", "HKG")
        expect(page.locator("#" + old_id)).to_have_count(0)
        expect(page.locator(".plot-tooltip")).to_have_count(1)
        page.goto(url.rsplit("/", 1)[0] + "/comparisons.html")
        page.select_option("#module-chart", "goods-to_us")
        details = page.locator("#goods-to_us details").filter(has=page.locator(".native-chart"))
        details.evaluate("node=>node.open=true")
        native = details.locator(".native-chart")
        expect(native).to_have_attribute("data-tooltip-id", re.compile("plot-tooltip-"))
        details.evaluate("node=>node.open=false")
        expect(native).not_to_have_attribute("data-tooltip-id", re.compile(".+"))
        details.evaluate("node=>node.open=true")
        expect(native).to_have_attribute("data-tooltip-id", re.compile("plot-tooltip-"))
        native.locator(".screen-chart").press("Home")
        expect(page.locator("#" + native.get_attribute("data-tooltip-id"))).to_be_visible()
        touch.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto(url)
        expect(page.locator("form.controls")).to_be_hidden()
        assert page.locator("#chart svg").count() == 1
        assert page.locator("#chart svg").bounding_box()["width"] >= 840
        assert page.locator("#chart").evaluate("node=>node.scrollWidth>node.clientWidth")
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
