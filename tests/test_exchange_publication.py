"""Reviewed source-table checkpoints, not generated expected values."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from us_china_exchange.model import validate


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/observations.json").read_text())


def reviewed_snapshot():
    # Freeze the independently reviewed vintage, not future legitimate revisions.
    return json.loads((ROOT / "tests/fixtures/exchange_reviewed_2026-10-21.json").read_text())


@pytest.mark.parametrize("origin,destination,measure,baseline,latest", [
    ("CHN", "USA", "goods", 432582, 309039),
    ("USA", "CHN", "goods", 125145, 107002),
    ("CHN", "USA", "services", 16275, 22768),
    ("USA", "CHN", "services", 40931, 57196),
    ("HKG", "USA", "goods", 8249, 5436),
    ("USA", "HKG", "goods", 24170, 34384),
    ("HKG", "USA", "services", 9759, 15541),
    ("USA", "HKG", "services", 12568, 16857),
    ("TWN", "USA", "goods", 60442, 201456),
    ("USA", "TWN", "goods", 30522, 55080),
    ("TWN", "USA", "services", 6422, 12599),
    ("USA", "TWN", "services", 9322, 14864),
])
def test_reviewed_bea_million_dollar_checkpoints(origin, destination, measure, baseline, latest):
    index = {(r["origin"], r["destination"], r["measure"], r["year"]): r["value"]
             for r in reviewed_snapshot() if r["source_id"] == "bea" and r["frequency"] == "annual"}
    assert index[(origin, destination, measure, 2020)] == baseline * 1_000_000
    assert index[(origin, destination, measure, 2025)] == latest * 1_000_000


@pytest.mark.parametrize("source,origin,destination,measure,year,value", [
    ("ntto", "CHN", "USA", "visitors", 2020, 378080),
    ("ntto", "CHN", "USA", "visitors", 2025, 1562458),
    ("ntto", "HKG", "USA", "visitors", 2025, 86692),
    ("ntto", "MAC", "USA", "visitors", 2025, 3409),
    ("ntto", "TWN", "USA", "visitors", 2025, 427470),
    ("taiwan_tourism", "USA", "TWN", "visitors", 2020, 82872),
    ("taiwan_tourism", "USA", "TWN", "visitors", 2025, 715481),
    ("iie", "CHN", "USA", "international_students", 2020, 372532),
    ("iie", "CHN", "USA", "international_students", 2025, 265919),
    ("iie", "HKG", "USA", "international_students", 2025, 5492),
    ("iie", "MAC", "USA", "international_students", 2025, 397),
    ("iie", "TWN", "USA", "international_students", 2025, 23263),
    ("iie", "USA", "CHN", "study_abroad", 2024, 1749),
    ("macau_tourism", "USA", "MAC", "visitors", 2020, 13489),
    ("macau_tourism", "USA", "MAC", "visitors", 2025, 162460),
])
def test_reviewed_people_checkpoints(source, origin, destination, measure, year, value):
    row = next(r for r in reviewed_snapshot() if
               (r["source_id"], r["origin"], r["destination"], r["measure"], r["year"], r["frequency"])
               == (source, origin, destination, measure, year, "annual"))
    assert row["value"] == value


def test_publication_has_no_duplicate_keys_and_complete_provenance():
    rows = published()
    assert validate(rows)
    assert all(len(r["raw_sha256"]) == 64 and r["source_url"].startswith("https://") for r in rows)
    assert not any(r["period_start"] is not None for r in rows if r["period_basis"] == "academic")


def test_publication_retains_year_2000_trade_and_inbound_visitor_history():
    rows = [r for r in published() if r["frequency"] == "annual" and r["value"] is not None]
    series = {r["series_id"] for r in rows if r["source_id"] in {"bea", "comtrade", "ntto"}}
    assert len(series) == 18
    for sid in series:
        assert any(r["series_id"] == sid and r["year"] == 2000 for r in rows), sid


def test_collective_export_preserves_complete_inputs_and_native_plot_boundaries(tmp_path):
    spec = importlib.util.spec_from_file_location("exchange_publication", ROOT / "scripts/build_exchange_publication.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.build_publication(ROOT, tmp_path, "checked-revision")
    expected = published()
    actual = json.loads((tmp_path / "downloads/exchange.json").read_text())
    assert actual["observations"] == expected
    assert manifest["observations"] == len(expected)
    with (tmp_path / "downloads/observations.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == len(expected)
    for path, checksum in manifest["files"].items():
        assert hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() == checksum
    for input_name, output_name in [("language_learning", "language-learning"), ("business_presence", "business-presence"),
                                    ("weibo_summary", "weibo-summary"), ("immigration", "immigration")]:
        assert json.loads((tmp_path / f"downloads/{output_name}.json").read_text()) == json.loads(
            (ROOT / f"data/site/{input_name}.json").read_text())
    for name in module.PAGES:
        page = BeautifulSoup((tmp_path / name).read_text(), "html.parser")
        assert len(page.select("h1")) == 1 and len(page.select(".analysis-tabs a")) == 8
        assert not page.select("iframe")
        github = page.select(".analysis-tabs a")[-1]
        assert github.text == "GitHub" and github["href"] == module.REPOSITORY
        assert not page.select("#downloads, #coverage, #sources, #all-values, .intro-notes")
        assert not page.select('.publication-footer a[href^="publication-manifest"]')
        assert "Automatic refresh:" not in page.get_text()
        assert "Sources and recorded checks" not in page.get_text()
        assert page.select_one(".publication-footer a")["href"] == module.REPOSITORY
        for a in page.select('a[href^="figures/"]'):
            assert a.has_attr("data-original-chart") and (tmp_path / urlsplit(a["href"]).path).is_file()
    page = BeautifulSoup((tmp_path / "index.html").read_text(), "html.parser")
    assert not page.select('#geography option[value="TWN"]')
    assert page.select_one('#measure option[selected]')["value"] == "goods"
    assert "2025" in page.select_one("#annual-headlines").text
    assert page.select_one("form.controls").has_attr("hidden")
    assert not page.select("#coverage-limits")
    assert "Coverage, including the gaps" not in page.get_text()
    assert "still being sourced" not in page.get_text()
    assert json.loads((tmp_path / "downloads/coverage.json").read_text()) == json.loads(
        (ROOT / "data/site/coverage.json").read_text())
    travel = BeautifulSoup((tmp_path / "travel.html").read_text(), "html.parser")
    assert travel.select_one('#measure option[selected]')["value"] == "visitors"
    assert travel.select_one(".travel-definition")
    assert travel.select_one("#series-population")
    for identifier in ["selection-note", "related-series", "series-continuity"]:
        assert travel.select_one("#" + identifier).find_parent("details") is None
    payload = json.loads(travel.select_one("#exchange-data").string)
    assert payload["prefer_current_travel"]
    assert payload["public_display"]
    assert {r["year"] for r in payload["observations"] if
            r["series_id"] == "ntto_siat:USA:CHN:air_visitors" and r["frequency"] == "annual"} == {
                *range(2012, 2021), *range(2022, 2026)}
    assert {o["value"] for o in travel.select("#measure option")} <= {"visitors", "leisure_visitors", "air_visitors"}
    immigration = BeautifulSoup((tmp_path / "immigration.html").read_text(), "html.parser")
    assert immigration.select_one("#green-card-grants .plot-data")
    assert immigration.select_one("#latest-admissions .plot-data")
    approvals = json.loads(immigration.select_one("#macau-residence-approvals .plot-data").string)
    assert [p["period"] for p in approvals["groups"][0]["points"]] == [str(y) for y in range(2010, 2026)]
    assert all("FY" not in p["label"] for p in approvals["groups"][0]["points"])
    business = BeautifulSoup((tmp_path / "business-presence.html").read_text(), "html.parser")
    model = json.loads(business.select_one("#us-affiliates-china .plot-data").string)
    assert len(model["groups"][0]["points"]) == 24
    assert [p["year"] for p in model["groups"][0]["points"] if not p["connect"]] == [2000, 2004, 2009, 2014, 2019]
    language = BeautifulSoup((tmp_path / "language-learning.html").read_text(), "html.parser")
    assert language.select_one("#module-chart option[selected]")["value"] == "college-enrollments"
    college = json.loads(language.select_one("#college-enrollments .plot-data").string)
    assert [g["id"] for g in college["groups"]] == ["mla:chinese", "mla:japanese", "mla:korean"]
    for chart in ["chinese-bachelors", "chinese-graduate-awards", "language-doctorates"]:
        model = json.loads(language.select_one(f"#{chart} .plot-data").string)
        assert [group["label"] for group in model["groups"]] == ["Chinese", "Japanese", "Korean"]
        assert model["unit"] == "Awards"
        assert [max(p["year"] for p in group["points"]) for group in model["groups"]] == [2025, 2025, 2025]
    school = json.loads(language.select_one("#school-language-enrollments .plot-data").string)
    assert [b["value"] for b in school["bars"]] == [227086, 67909]
    assert [b["period"] for b in school["bars"]] == ["2015", "2015"]
    availability = json.loads(language.select_one("#school-language-availability .plot-data").string)
    assert [b["value"] for b in availability["bars"]] == [3, 1]
    assert availability["unit"] == "Percent"
    assert availability["unavailable_bars"] == [
        {"id": "spp_availability:korean", "label": "Korean", "reason": "Not reportable"}]
    ap_scope = language.select_one("#ap-chinese-global .ap-scope-note")
    assert "no AP Korean exam is offered" in ap_scope.text
    assert "not zero participation" in ap_scope.text
    assert ap_scope.find_parent("details") is None
    assert ap_scope.find_next(class_="comparison-chart") is not None
    assert language.select_one("main > section").select_one(".native-chart")
    inventories = json.loads(language.select_one("#school-program-inventories .plot-data").string)
    assert all(str(year) in row["label"] for year, row in zip([2011, 2021, 2025], inventories["bars"]))
    comparisons = BeautifulSoup((tmp_path / "comparisons.html").read_text(), "html.parser")
    model = json.loads(comparisons.select_one("#goods-to_us .plot-data").string)
    assert len(model["groups"]) == 3
    assert model["unit"] == "Nominal USD"
    assert next(g for g in model["groups"] if g["label"] == "Macau")["dash"] == "7 4"
    weibo = BeautifulSoup((tmp_path / "weibo.html").read_text(), "html.parser")
    source_weibo = json.loads((ROOT / "data/site/weibo_summary.json").read_text())
    monthly = source_weibo["monthly"]
    assert weibo.select_one("#weibo-explorer")
    assert not weibo.select("#module-chart, .plot-data, #monthly-posts, #publication-years, #rolling30-posts")
    assert len(weibo.select(".weibo-dot")) == len(source_weibo["accounts"])
    assert len(weibo.select(".weibo-brand")) == len({a["outlet_id"] for a in source_weibo["accounts"]})
    assert len(weibo.select(".weibo-channel-detail")) == len(source_weibo["accounts"])
    assert weibo.select_one('script[src^="assets/weibo-explorer.js"]')
    assert weibo.select_one('link[href^="assets/weibo-explorer.css"]')
    assert (tmp_path / "assets/weibo-explorer.js").is_file()
    assert (tmp_path / "assets/weibo-explorer.css").is_file()
    with (tmp_path / "downloads/weibo-months.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(monthly)
    assert sum(int(row["recovered_posts"]) for row in rows) == sum(row["recovered_posts"] for row in monthly)
    with (tmp_path / "downloads/weibo-rolling30.csv").open(newline="") as stream:
        rolling = list(csv.DictReader(stream))
    assert len(rolling) == len(source_weibo["rolling_30d"])
    assert not list(tmp_path.rglob("*.pdf")) and not list(tmp_path.rglob("*.db"))


@pytest.mark.parametrize("coordinate,issue", [("x", "misplaced_calendar_year"), ("y", "misplaced_y_coordinate")])
def test_plot_auditor_rejects_correct_metadata_at_wrong_coordinates(coordinate, issue):
    spec = importlib.util.spec_from_file_location("plot_audit", ROOT / "scripts/audit_exchange_plots.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = module.Audit.__new__(module.Audit)
    audit.issues = []
    point = {"year": "2020", "value": 50, "x": 50, "y": 50}
    point[coordinate] = 25
    geometry = {"clipped": [], "overlaps": [], "unit": "Students",
                "ticks": [{"label": "0", "y": 100}, {"label": "100", "y": 0}],
                "points": [point], "snapshots": [], "bars": [], "paths": [], "allPaths": [],
                "years": [{"value": 2010, "x": 0}, {"value": 2030, "x": 100}]}
    model = {"kind": "line", "groups": [{"id": "example", "points": [{"year": 2020, "value": 50}]}]}
    audit.geometry("example", geometry, model)
    assert [row["kind"] for row in audit.issues] == [issue]


def test_plot_auditor_rejects_year_labels_that_nearly_touch():
    spec = importlib.util.spec_from_file_location("plot_audit", ROOT / "scripts/audit_exchange_plots.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = module.Audit.__new__(module.Audit)
    audit.issues = []
    geometry = {"clipped": [], "overlaps": [], "points": [], "bars": [], "ticks": [], "texts": [
        {"kind": "screen-year", "text": "2020", "x": 100, "w": 32},
        {"kind": "screen-year", "text": "2024", "x": 134, "w": 32}]}
    audit.geometry("example", geometry, None)
    assert [row["kind"] for row in audit.issues] == ["crowded_year_labels"]
