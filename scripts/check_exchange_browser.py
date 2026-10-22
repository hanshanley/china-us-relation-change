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
from us_china_exchange.theme import CHART_THEMES, PNG_HEIGHT, PNG_WIDTH


def check():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    matrix = json.loads((ROOT / "data/site/coverage.json").read_text())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "site/index.html").as_uri())
        page.evaluate("document.fonts.ready")
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
            assert "2000" in page.locator("#chart").inner_text()
            assert page.locator("#chart svg text").evaluate_all("""nodes => nodes.every(node => {
              const box = node.getBBox();
              const bounds = node.ownerSVGElement.viewBox.baseVal;
              return box.x >= 0 && box.y >= 0 && box.x + box.width <= bounds.width && box.y + box.height <= bounds.height;
            })"""), (origin, destination, measure, "clipped figure text")
            for theme, spec in CHART_THEMES.items():
                page.select_option("#chart-theme", theme)
                assert page.locator("#chart .chart-background").get_attribute("fill") == spec["background"]
                links = page.locator(f'#figure-link a[href*="/{theme}/"]')
                assert links.count() == 2
                png_path = page.locator(f'#figure-link a[href*="/{theme}/"][href$=".png"]').get_attribute("href")
                assert (ROOT / "site" / png_path).is_file()
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
        for geo in ["CHN", "HKG", "MAC", "TWN"]:
            page.select_option("#geography", geo)
            page.select_option("#direction", "to_us")
            page.select_option("#measure", "international_students")
            page.locator("#selected-table").evaluate("node => node.open = true")
            expect(page.locator("#series-table thead")).to_contain_text("Population definition")
            expect(page.locator("#series-table tbody tr").filter(has_text="2020/21")).to_contain_text(
                "expanded pandemic population")
            expect(page.locator("#series-table tbody tr").filter(has_text="2023/24")).to_contain_text(
                "standard temporary-visa population")
            page.select_option("#chart-mode", "index")
            expect(page.locator("#chart .gap")).to_contain_text("Definitions differ")
            assert page.locator("#chart svg").count() == 0
            page.select_option("#chart-mode", "levels")
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
        assert page.locator("#chart").evaluate("node => node.scrollWidth > node.clientWidth")
        assert page.locator("#chart svg text:not(.figure-source)").evaluate_all("""nodes =>
          nodes.every(node => parseFloat(getComputedStyle(node).fontSize) *
          node.ownerSVGElement.getBoundingClientRect().width /
          node.ownerSVGElement.viewBox.baseVal.width >= 16)""")
        page.locator("#chart").focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.getElementById('chart').scrollLeft > 0")
        page.locator("#geography").focus()
        page.keyboard.press("h" if sys.platform == "darwin" else "ArrowDown")
        page.keyboard.press("Tab")
        expect(page.locator("#geography")).to_have_value("HKG")
        expect(page.locator("#series-title")).to_contain_text("Hong Kong")
        expect(page.locator("#direction")).to_be_focused()
        page.close()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto((ROOT / "site/index.html").as_uri())
        assert page.locator("noscript").is_visible()
        page.locator("#selected-table summary").click()
        expect(page.locator("#series-table tbody tr").filter(has_text="2020/21")).to_contain_text(
            "expanded pandemic population")
        assert page.locator("#all-values details").count() > 30
        page.locator("#all-values summary").first.click()
        assert page.locator("#all-values table").first.is_visible()
        for theme in CHART_THEMES:
            assert page.locator(f'#figure-link a[href*="/{theme}/"]').count() == 2
        png_link = page.locator('#figure-link a[href$=".png"]').first.get_attribute("href")
        page.goto((ROOT / "site" / png_link).as_uri())
        image = page.locator("img")
        assert image.evaluate("img => [img.naturalWidth, img.naturalHeight]") == [PNG_WIDTH, PNG_HEIGHT]
        page.go_back()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.goto((ROOT / "site/index.html").as_uri())
        page.evaluate("document.fonts.ready")
        publication_svgs = list((ROOT / "site/figures").glob("*/comparisons/*/*.svg"))
        publication_svgs += list((ROOT / "site/figures/weibo").glob("*/*.svg"))
        publication_svgs += list((ROOT / "site/figures/language_learning").glob("*/*.svg"))
        publication_svgs += list((ROOT / "site/figures/business_presence").glob("*/*.svg"))
        for path in sorted(publication_svgs):
            page.locator("#chart").evaluate("(node, svg) => node.innerHTML = svg", path.read_text())
            assert page.locator("#chart svg text").evaluate_all("""nodes => nodes.every(node => {
              const box = node.getBBox(), bounds = node.ownerSVGElement.viewBox.baseVal;
              return box.x >= 0 && box.y >= 0 && box.x + box.width <= bounds.width && box.y + box.height <= bounds.height;
            })"""), (str(path), "clipped publication text")
            if path.parent.parent.name in {"language_learning", "business_presence"}:
                assert page.locator("#chart .legend-label,#chart .year-tick").evaluate_all("""nodes =>
                  nodes.every((node, i) => nodes.slice(i + 1).every(other => {
                    const a = node.getBBox(), b = other.getBBox();
                    return a.x + a.width + 8 <= b.x || b.x + b.width + 8 <= a.x ||
                           a.y + a.height <= b.y || b.y + b.height <= a.y;
                  }))"""), (str(path), "overlapping indicator legend or year labels")
        page.goto((ROOT / "site/comparisons.html").as_uri())
        assert page.locator(".series-panel").count() == 16
        images = page.locator('img[src$="-levels.png"]')
        assert images.count() == 11
        for image in images.all():
            image.scroll_into_view_if_needed()
            expect(image).to_have_js_property("naturalWidth", PNG_WIDTH)
            expect(image).to_have_js_property("naturalHeight", PNG_HEIGHT)
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        if (ROOT / "site/language-learning.html").exists():
            page.goto((ROOT / "site/language-learning.html").as_uri())
            expect(page.locator("header")).to_contain_text("global, not U.S.-only")
            images = page.locator("img")
            assert images.count() >= 7
            for image in images.all():
                image.scroll_into_view_if_needed()
                expect(image).to_have_js_property("naturalWidth", PNG_WIDTH)
                expect(image).to_have_js_property("naturalHeight", PNG_HEIGHT)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        if (ROOT / "site/business-presence.html").exists():
            page.goto((ROOT / "site/business-presence.html").as_uri())
            expect(page.locator("header")).to_contain_text("different counting units")
            images = page.locator("img")
            assert images.count() == 5
            for image in images.all():
                image.scroll_into_view_if_needed()
                expect(image).to_have_js_property("naturalWidth", PNG_WIDTH)
                expect(image).to_have_js_property("naturalHeight", PNG_HEIGHT)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        if (ROOT / "site/weibo.html").exists():
            page.goto((ROOT / "site/weibo.html").as_uri())
            images = page.locator("img")
            summary = json.loads((ROOT / "data/site/weibo_summary.json").read_text())
            assert images.count() == (4 if summary["yearly"] else 3)
            for image in images.all():
                image.scroll_into_view_if_needed()
                expect(image).to_have_js_property("naturalWidth", PNG_WIDTH)
                expect(image).to_have_js_property("naturalHeight", PNG_HEIGHT)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not errors, errors
        browser.close()
    print("Browser acceptance passed: all 64 combinations, exact changes, YTD, keyboard, mobile, no JavaScript.")


if __name__ == "__main__":
    check()
