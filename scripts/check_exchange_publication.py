#!/usr/bin/env python3
"""Browser checks for collective coverage, exact plot values and responsive layout."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import expect, sync_playwright

from us_china_exchange.model import primary_observations


def check_weibo_explorer(page, summary):
    from check_weibo_publication import check_page

    check_page(page, summary)


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
            payload = json.loads(page.locator("#exchange-data").text_content())
            visible = set(payload.get("visible_series", {r["series_id"] for r in data["observations"]}))
            expect(page.locator("form.controls")).to_be_visible()
            assert page.locator("#reverse-direction,.reverse-direction").count() == 0
            assert not page.locator("#coverage, #coverage-limits, #downloads, #sources, #all-values").count()
            expect(page.locator(".analysis-tabs a").last).to_have_text("GitHub")
            expect(page.locator(".analysis-tabs a").last).to_have_attribute(
                "href", "https://github.com/hanshanley/china-us-relation-change")
            assert page.locator("#geography option").count() == 3
            assert page.locator("#chart").bounding_box()["y"] < 680
            assert page.locator("#chart").evaluate("node=>node.scrollWidth<=node.clientWidth")
            for geo in ("CHN", "HKG", "MAC"):
                for direction in ("to_us", "from_us"):
                    origin, destination = (geo, "USA") if direction == "to_us" else ("USA", geo)
                    for measure in data["measures"]:
                        target = ("trade.html" if measure in {"goods", "services"} else
                                  "travel.html" if "visitors" in measure else "index.html")
                        if not page.url.split("?")[0].endswith("/" + target):
                            page.goto(url.rsplit("/", 1)[0] + "/" + target)
                        if target == "trade.html":
                            page.locator(".individual-series").evaluate("node=>node.open=true")
                        page.select_option("#geography", geo)
                        page.select_option("#direction", direction)
                        annual = sorted((r for r in primary_observations(data["observations"]) if r["series_id"] in visible
                                         and r["origin"] == origin and r["destination"] == destination
                                         and r["measure"] == measure and r["frequency"] == "annual" and r["value"] is not None),
                                        key=lambda r: r["year"])
                        option = page.locator(f'#measure option[value="{measure}"]')
                        if not option.count():
                            assert not annual, (geo, direction, measure)
                            continue
                        assert option.evaluate("(o)=>o.disabled") == (not annual), (geo, direction, measure)
                        if not annual:
                            continue
                        page.select_option("#measure", measure)
                        actual = page.locator("#chart .screen-point").evaluate_all(
                            "nodes=>nodes.map(n=>[Number(n.dataset.year),Number(n.dataset.value)])")
                        assert actual == [[r["year"], r["value"]] for r in annual], (geo, direction, measure)
                        if len(annual) > 2:
                            columns = page.locator("#chart .screen-column")
                            assert columns.evaluate_all(
                                "nodes=>nodes.map(n=>[Number(n.dataset.year),Number(n.dataset.value)])") == actual
                            assert page.locator("#chart .screen-line").count() == 0
                            assert all(float(columns.nth(i).get_attribute("height")) >= 0 for i in range(len(annual)))
                            if screenshots and geo == "CHN" and direction == "to_us" and measure == "goods":
                                page.locator(".exchange-panel").screenshot(path=str(screenshots / f"annual-trade-columns-{width}.png"))
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
            page.goto(url.rsplit("/", 1)[0] + "/trade.html")
            page.locator(".individual-series").evaluate("node=>node.open=true")
            page.select_option("#geography", "CHN")
            page.select_option("#direction", "to_us")
            page.select_option("#measure", "goods")
            page.select_option("#chart-mode", "index")
            assert page.locator("#chart .screen-column").count() == 0
            assert page.locator("#chart .screen-line").count() == 1
            page.select_option("#chart-mode", "levels")
            expect(page.locator("#latest-period")).to_contain_text("2025")
            expect(page.locator("#partial-panel")).to_contain_text("2026")
            assert page.locator("#chart svg text").evaluate_all("""nodes=>nodes.every(n=>{
              const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;
              return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
            })""")
            page.select_option("#chart-mode", "index")
            assert float(page.locator("#chart .screen-point[data-year='2020']").get_attribute("data-value")) == 100
            page.goto(url)
            page.select_option("#measure", "international_students")
            expect(page.locator("#chart-mode")).to_have_value("levels")
            assert page.locator("#chart .screen-point").count() == 26
            page.select_option("#measure", "enrolled_students")
            page.locator("#related-series button").click()
            expect(page.locator("#measure")).to_have_value("international_students")
            if data.get("student_estimates"):
                page.select_option("#direction", "from_us")
                expect(page.locator("#student-estimates")).to_be_visible()
                assert page.locator("#student-estimates tbody tr").count() == 3
                expect(page.locator("#student-estimates")).to_contain_text("<2,000 per year")
                page.select_option("#geography", "HKG")
                expect(page.locator("#student-estimates")).to_be_hidden()
                page.select_option("#geography", "CHN")
                page.select_option("#direction", "to_us")
            page.select_option("#chart-mode", "levels")
            page.select_option("#measure", "international_students")
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
            expect(page.locator("#selection-note")).to_contain_text("U.S.-resident air-travel")
            air = sorted((row for row in data["observations"] if
                          row["series_id"] == "ntto_siat:USA:CHN:air_visitors"
                          and row["frequency"] == "annual" and row["value"] is not None),
                         key=lambda row: row["year"])
            assert page.locator("#chart .screen-point").evaluate_all(
                "nodes=>nodes.map(n=>[+n.dataset.year,+n.dataset.value])") == [
                    [row["year"], row["value"]] for row in air]
            assert air[0]["year"] == 2000
            expect(page.locator("#series-population")).to_contain_text(
                f'{air[0]["year"]}\u2013{air[-1]["year"]}')
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
            assert page.locator("#related-series button").count() == 0
            assert page.locator('#measure option[value="visitors"]').evaluate("o=>o.disabled&&o.hidden")
            page.locator("#measure").evaluate("n=>{n.value='visitors';n.dispatchEvent(new Event('change',{bubbles:true}));}")
            expect(page.locator("#measure")).to_have_value("air_visitors")
            assert page.locator("#chart .screen-point").count() == len(air)
            if screenshots:
                page.locator(".exchange-panel").screenshot(path=str(screenshots / f"tourism-current-{width}.png"))
            for geo in ("CHN", "HKG"):
                page.select_option("#geography", geo)
                expect(page.locator("#latest-period")).to_contain_text("2025")
                expect(page.locator("#partial-panel")).to_contain_text("2026")
                expect(page.locator("#partial-panel")).to_contain_text(
                    "32,000 (+7.2%)" if geo == "CHN" else "53,000 (-17.4%)")
            page.select_option("#measure", "visitors")
            expect(page.locator("#partial-panel")).to_contain_text("Jan–Aug 2026")
            expect(page.locator("#partial-panel")).to_contain_text("737,530")
            if screenshots:
                page.locator(".exchange-panel").screenshot(path=str(screenshots / f"hong-kong-current-{width}.png"))
            page.select_option("#measure", "air_visitors")
            page.select_option("#direction", "to_us")
            expect(page.locator("#measure")).to_have_value("visitors")
            expect(page.locator("#selection-note")).to_contain_text("no verified annual series for this route")
            assert page.locator("#chart .screen-point").count() == 26
            for name in ["immigration.html", "trade.html", "language-learning.html", "confucius.html", "business-presence.html", "weibo.html", "opinions.html"]:
                if not (site / name).is_file():
                    continue
                page.goto(url.rsplit("/", 1)[0] + "/" + name)
                page.evaluate("document.fonts.ready")
                if name == "opinions.html":
                    from check_opinion_publication import check_page

                    check_page(page, json.loads((site / "downloads/opinions.json").read_text()), exhaustive=False)
                    continue
                if name == "confucius.html":
                    from check_confucius_publication import check_page

                    check_page(page, json.loads((site / "downloads/confucius-programs.json").read_text()), exhaustive=False)
                    continue
                if name == "weibo.html":
                    check_weibo_explorer(page, json.loads((site / "downloads/weibo-summary.json").read_text()))
                    if screenshots:
                        page.screenshot(path=str(screenshots / f"collective-weibo-{width}.png"))
                    continue
                if name != "business-presence.html":
                    expect(page.locator(".module-controls")).to_be_visible()
                if name == "trade.html":
                    page.select_option("#module-chart", "goods-to_us")
                    logarithmic = page.locator("#goods-to_us details").filter(has=page.locator(".native-chart"))
                    logarithmic.evaluate("node=>node.open=true")
                    assert logarithmic.locator(".screen-unit").all_text_contents() == ["Nominal US$ (log scale)"] * 2
                    for indicator in ["goods-to_us", "goods-from_us", "services-to_us", "services-from_us"]:
                        page.select_option("#module-chart", indicator)
                        panels = page.locator(f"#{indicator} > .comparison-panels > .comparison-pane")
                        assert panels.count() == 2
                        assert panels.nth(0).get_attribute("data-geographies") == "CHN"
                        assert panels.nth(1).get_attribute("data-geographies") == "HKG MAC"
                        bounds = [panels.nth(i).bounding_box() for i in range(2)]
                        if width == 390:
                            assert bounds[1]["y"] >= bounds[0]["y"] + bounds[0]["height"]
                        else:
                            assert bounds[0]["x"] + bounds[0]["width"] <= bounds[1]["x"]
                            assert abs(bounds[0]["y"] - bounds[1]["y"]) < 1
                            plots = [panels.nth(i).locator(".screen-chart").bounding_box() for i in range(2)]
                            assert abs(plots[0]["y"] - plots[1]["y"]) < 1
                        endpoints = [p.locator(".screen-year").all_text_contents() for p in
                                     [panels.nth(0), panels.nth(1)]]
                        assert endpoints[0][0] == endpoints[1][0]
                        assert endpoints[0][-1] == endpoints[1][-1] == "2025"
                        if screenshots:
                            page.locator(f"#{indicator} > .comparison-panels").screenshot(
                                path=str(screenshots / f"split-{indicator}-{width}.png"))
                if name == "immigration.html":
                    immigration = json.loads((site / "downloads/immigration.json").read_text())
                    present = [r for r in immigration["observations"] if r["value"] is not None]
                    arrivals = [r for r in present if r["series_id"] == "ohss_nationality:new_arrivals"]
                    birthplace = [r for r in present if r["series_id"].startswith("ohss_birth:")]
                    stock_from_us = [r for r in present if r["series_id"].startswith("un_stock:USA:")]
                    approvals = [r for r in present if r["series_id"] == "dsec_abode:USA:MAC"]
                    expect(page.locator("#module-chart")).to_have_value("annual-china-to-us")
                    assert page.locator("#annual-china-to-us .screen-point").count() == len(arrivals)
                    assert page.locator("#annual-china-to-us .screen-column").count() == len(arrivals)
                    page.select_option("#module-chart", "migrant-stock-from-us")
                    assert page.locator("#migrant-stock-from-us .screen-point").count() == len(stock_from_us)
                    expect(page.locator("#migrant-stock-from-us")).to_contain_text("citizenship")
                    page.select_option("#module-chart", "green-card-grants")
                    assert page.locator("#green-card-grants .screen-point").count() == len(birthplace)
                    page.select_option("#module-chart", "latest-admissions")
                    assert page.locator("#latest-admissions .screen-bar").evaluate_all(
                        "nodes=>nodes.map(n=>Number(n.dataset.value))") == [27020, 38650]
                    page.select_option("#module-chart", "macau-residence-approvals")
                    assert page.locator("#macau-residence-approvals .screen-point").count() == len(approvals)
                    expect(page.locator("#macau-residence-approvals .screen-unit")).to_have_text("People approved")
                    if screenshots:
                        page.locator("#macau-residence-approvals").screenshot(path=str(screenshots / f"macau-approvals-{width}.png"))
                if name == "language-learning.html":
                    expect(page.locator("#module-chart")).to_have_value("chinese-bachelors")
                    assert page.locator("#chinese-bachelors .screen-point").count() == 75
                    assert not page.locator("#college-enrollments,#school-language-enrollments").count()
                    page.select_option("#module-chart", "school-language-availability")
                    assert page.locator("#school-language-availability .screen-bar").evaluate_all(
                        "nodes=>nodes.map(n=>Number(n.dataset.value))") == [3, 1]
                    assert "Korean" not in page.locator("#school-language-availability .screen-chart").text_content()
                    if screenshots:
                        page.locator("#school-language-availability").screenshot(path=str(screenshots / f"school-availability-{width}.png"))
                    page.select_option("#module-chart", "ap-chinese-global")
                    assert page.locator("#ap-chinese-global .screen-point").count() == 38
                    years = page.locator("#ap-chinese-global .screen-year").all_text_contents()
                    assert years[0] == "2007" and years[-1] == "2025"
                    expect(page.locator("#ap-chinese-global .ap-scope-note")).to_contain_text("not U.S.-only")
                    assert page.locator('#module-chart option[value="ap-language-standard-group"]').count() == 0
                    assert page.locator("#ap-language-standard-group").count() == 0
                if name == "business-presence.html":
                    assert page.locator(".business-card:visible").count() == 6
                    assert page.locator("#us-investment-mainland .screen-column").count() == 26
                    assert page.locator("#us-investment-hong-kong .screen-column").count() == 26
                    assert page.locator("#german-company-risk .screen-bar").count() == 3
                    assert page.locator("#china-ubo-us-affiliates .screen-column").count() == 13
                    assert page.locator("#hong-kong-ubo-us-affiliates .screen-column").count() == 13
                    assert not page.locator("#module-chart,.covid-band").count()
                    if screenshots:
                        page.locator("#investment-positions").screenshot(path=str(screenshots / f"business-investment-{width}.png"))
                for option in page.locator("#module-chart option").all():
                    page.select_option("#module-chart", option.get_attribute("value"))
                    assert page.locator("[data-module-chart]:visible").count() == 1
                    if option.get_attribute("value") == "state-china-map":
                        from check_state_immigration_map import check_page

                        check_page(page, json.loads((site / "downloads/state-immigration.json").read_text()))
                        continue
                    assert page.locator("[data-module-chart]:visible .screen-chart").count()
                    assert page.locator("[data-module-chart]:visible .screen-chart text").evaluate_all("""nodes=>nodes.every(n=>{
                      const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;
                      return b.x>=-1&&b.y>=-1&&b.x+b.width<=v.width+1&&b.y+b.height<=v.height+1;
                    })"""), (width, name, option.get_attribute("value"), "clipped chart labels")
                    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth"), name
                if screenshots:
                    page.screenshot(path=str(screenshots / f"collective-{name[:-5]}-{width}.png"))
            page.goto(url.rsplit("/", 1)[0] + "/language-learning.html?indicator=college-benchmarks")
            expect(page.locator("#module-chart")).to_have_value("chinese-bachelors")
            assert page.locator("#college-benchmarks").count() == 0
            assert page.locator('#chinese-bachelors .screen-line[data-series-id="ipeds_korean:bachelors"]').count() == 1
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
        page.goto(url.rsplit("/", 1)[0] + "/comparisons.html?indicator=goods-to_us")
        page.wait_for_url("**/trade.html?indicator=goods-to_us#regional-comparisons")
        page.select_option("#module-chart", "goods-to_us")
        details = page.locator("#goods-to_us details").filter(has=page.locator(".native-chart"))
        details.evaluate("node=>node.open=true")
        native = details.locator(".native-chart").first
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
        assert page.locator("#selected-table #series-table tbody tr").count() == len([
            row for row in data["observations"] if row["origin"] == "CHN" and row["destination"] == "USA"
            and row["measure"] == "international_students" and row["frequency"] == "annual"])
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
