#!/usr/bin/env python3
"""Verify the date policy in every public plot, export and individual-series choice."""

import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from playwright.sync_api import expect, sync_playwright


def assert_current(points, identity, snapshot=False):
    assert points, (identity, "empty graph")
    years = [int(p["year"]) for p in points]
    periods = {(p["year"], p.get("period", "")) for p in points}
    if snapshot or len(periods) == 1:
        assert all(2024 <= year <= 2026 for year in years), (identity, "old snapshot", years)
    else:
        assert max(years) >= 2023, (identity, "stale history", years)


def model_current(model, definitions, identity):
    if (model.get("kind") == "line" and len(model.get("groups", [])) == 1
            and not model.get("snapshots") and model.get("scale") != "log" and "-log." not in identity
            and "=" not in model.get("unit", "")):
        assert model.get("columns"), (identity, "single-series levels must use bars")
    groups = defaultdict(list)
    for group in model.get("groups", []):
        groups[group["id"]].extend(group["points"])
    for bar in model.get("bars", []):
        groups[bar["id"]].append(bar)
    assert groups, (identity, "unrecognized empty model")
    for sid, points in groups.items():
        snapshot = bool(model.get("snapshots")) or "snapshot" in definitions.get(sid, {}).get("cadence", "").lower()
        assert_current(points, identity + ":" + sid, snapshot)


def check(site, url=None):
    manifest = json.loads((site / "publication-manifest.json").read_text())
    assert manifest["chart_freshness"] == {"history_since": 2023, "snapshot_from": 2024, "snapshot_through": 2026}
    definitions = {}
    for name in ("language-learning", "business-current", "business-inward", "immigration", "opinions"):
        if name == "business-inward" and not (site / f"downloads/{name}.json").is_file():
            continue
        data = json.loads((site / f"downloads/{name}.json").read_text())
        definitions.update(data["series"])
    observations = json.loads((site / "downloads/observations.json").read_text())
    immigration = json.loads((site / "downloads/immigration.json").read_text())
    arrivals = sorted((r for r in immigration["observations"]
                       if r["series_id"] == "ohss_nationality:new_arrivals"), key=lambda r: r["year"])
    lookup = {(r["series_id"], r["period"]): r for r in observations}
    spec = importlib.util.spec_from_file_location("freshness_plot_decoder", ROOT / "scripts/build_exchange_publication.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    labels = {sid: d["label"] for sid, d in definitions.items()}
    html_plots = 0
    for path in site.glob("*.html"):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        for script in soup.select(".plot-data"):
            model_current(json.loads(script.string), definitions, path.name)
            html_plots += 1
        for script in soup.select(".confucius-plot-data"):
            data = json.loads(script.string)
            assert_current([dict(r, year=int(r["reference"][:4])) for r in data["rows"]],
                           path.name + ":" + data["id"], snapshot=data["layout"] != "timeline")
            html_plots += 1
        payload = soup.select_one("#exchange-data")
        if payload:
            payload = json.loads(payload.string)
            for sid in payload["visible_series"]:
                rows = [r for r in payload["observations"] if r["series_id"] == sid
                        and r["frequency"] == "annual" and r["value"] is not None]
                assert_current(rows, path.name + ":" + sid)
        for link in soup.select('a[href*="?indicator="]'):
            target, _, query = link["href"].partition("?indicator=")
            target = site / target
            if target.is_file():
                identifier = query.split("#")[0].split("&")[0]
                assert BeautifulSoup(target.read_text(), "html.parser").select_one("#" + identifier), link["href"]
    exports = [site / name for name in manifest["files"] if name.startswith("figures/") and name.endswith(".svg")]
    for path in exports:
        soup = BeautifulSoup(path.read_text(), "html.parser")
        if soup.svg.get("data-state-map"):
            assert 2024 <= int(soup.svg["data-period"].split("-")[-1]) <= 2026
        elif soup.svg.get("data-confucius-chart"):
            rows = [{"year": int(n["data-reference"][:4])} for n in soup.select(".confucius-mark")]
            assert_current(rows, str(path), snapshot=soup.svg.get("data-chart-layout") != "timeline")
        else:
            model = builder.plot_model(soup.svg, labels, lookup)
            assert model, (str(path), "export has no inspectable dates")
            model_current(model, definitions, str(path))
    choices = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 390):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            for name in ("index.html", "travel.html", "trade.html"):
                page.goto(url.rstrip("/") + "/" + name if url else (site.resolve() / name).as_uri())
                page.evaluate("document.fonts.ready")
                if page.locator(".individual-series").count():
                    page.locator(".individual-series").evaluate("n=>n.open=true")
                for geo in ("CHN", "HKG", "MAC"):
                    page.select_option("#geography", geo)
                    for direction in ("from_us", "to_us"):
                        page.select_option("#direction", direction)
                        values = page.locator("#measure option:enabled").evaluate_all("nodes=>nodes.map(n=>n.value)")
                        for value in values:
                            page.select_option("#measure", value)
                            marks = page.locator("#chart .screen-point")
                            years = marks.evaluate_all("nodes=>nodes.map(n=>+n.dataset.year)")
                            assert years and (2024 <= max(years) <= 2026 if len(set(years)) == 1 else max(years) >= 2023), (
                                width, name, geo, direction, value, years)
                            choices += 1
                if name == "travel.html":
                    page.select_option("#geography", "CHN")
                    page.select_option("#direction", "to_us")
                    page.select_option("#measure", "visitors")
                    assert page.locator("#reverse-direction,.reverse-direction").count() == 0
                    page.select_option("#direction", "from_us")
                    expect(page.locator("#direction")).to_have_value("from_us")
                    expect(page.locator("#measure")).to_have_value("air_visitors")
                    air = [row for row in observations
                           if row["series_id"] == "ntto_siat:USA:CHN:air_visitors"
                           and row["frequency"] == "annual" and row["value"] is not None]
                    assert page.locator("#chart .screen-column").count() == len(air)
                    assert float(page.locator('#chart .screen-column[data-year="2021"]').get_attribute("data-value")) == 5000
                    expect(page.locator("#chart .covid-label")).to_have_text("COVID travel restrictions, 2020-22")
                    page.select_option("#direction", "to_us")
                    expect(page.locator("#direction")).to_have_value("to_us")
                    expect(page.locator("#measure")).to_have_value("visitors")
                    assert page.locator("#chart .screen-column").count() == 26
                if name == "index.html":
                    page.select_option("#geography", "CHN")
                    page.select_option("#direction", "from_us")
                    page.locator("#measure").evaluate(
                        "n=>{n.value='enrolled_students';n.dispatchEvent(new Event('change',{bubbles:true}));}")
                    expect(page.locator("#measure")).to_have_value("study_abroad")
                    expect(page.locator("#latest-period")).to_contain_text("2023/24")
                assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
            page.close()
            page = browser.new_page(viewport={"width": width, "height": 1000})
            page.goto(url.rstrip("/") + "/immigration.html" if url else (site.resolve() / "immigration.html").as_uri())
            expect(page.locator("#module-chart")).to_have_value("annual-china-to-us")
            assert page.locator("#annual-china-to-us .screen-column").evaluate_all(
                "nodes=>nodes.map(n=>[+n.dataset.year,+n.dataset.value])") == [
                    [r["year"], r["value"]] for r in arrivals]
            expect(page.locator(".annual-reverse-note")).to_contain_text("not been verified")
            page.close()
        browser.close()
    print(json.dumps({"public_models": html_plots, "svg_exports": len(exports),
                      "live_route_choices": choices, "stale_plots": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    args = parser.parse_args()
    check(args.site, args.url)
