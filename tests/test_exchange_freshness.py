"""Public recency is based on reported measurement periods, not source-upload dates."""

import importlib.util
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from us_china_exchange.public_freshness import current_groups, eligible, public, public_charts


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("years,accepted", [([2020, 2025], False), ([2024, 2025], True)])
def test_native_snapshot_metadata_checks_each_observation_not_just_the_latest(years, accepted):
    spec = importlib.util.spec_from_file_location("freshness_checker", ROOT / "scripts/check_public_freshness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = {"kind": "line", "snapshots": True, "groups": [
        {"id": "reported_snapshots", "points": [{"year": year, "value": 10} for year in years]}]}
    definitions = {"reported_snapshots": {"cadence": "annual"}}
    if accepted:
        module.model_current(model, definitions, "snapshot example")
    else:
        with pytest.raises(AssertionError, match="old snapshot"):
            module.model_current(model, definitions, "snapshot example")


def test_covid_band_uses_annual_bins_without_changing_observation_values():
    from xml.etree import ElementTree
    from us_china_exchange.covid_context import COVID_CONTEXT, svg_band
    from us_china_exchange.model import observation
    from us_china_exchange.render import svg_chart

    rows = [observation("test", "USA", "CHN", "air_visitors", year, value, "Resident air trips")
            for year, value in ((2019, 100), (2020, 10), (2022, 20), (2025, 80))]
    doc = ElementTree.fromstring(svg_chart(rows))
    band = next(n for n in doc.iter() if n.get("class") == "covid-band")
    assert float(band.get("x")) == pytest.approx(115 + 835 / 7, abs=.01)
    assert float(band.get("width")) == pytest.approx(3 * 835 / 7, abs=.01)
    assert [(int(n.get("data-year")), float(n.get("data-value"))) for n in doc.iter()
            if n.get("class") == "annual-column"] == [(2019, 100), (2020, 10), (2022, 20), (2025, 80)]
    assert "not a universal travel ban" in COVID_CONTEXT["note"]
    assert all(s["url"].startswith("https://") for s in COVID_CONTEXT["sources"])
    assert svg_band(2024, 2026, 115, 950, 170, 420) == ""


@pytest.mark.parametrize("rows,snapshot,expected", [
    ([{"year": 2010, "value": 10}, {"year": 2018, "value": 20}], None, False),
    ([{"year": 2010, "value": 10}, {"year": 2023, "value": 20}], None, True),
    ([{"year": 2023, "value": 20}], None, False),
    ([{"year": 2024, "value": 20}], None, True),
    ([{"year": 2026, "value": 0}], None, True),
    ([{"year": 2027, "value": 20}], True, False),
    ([{"year": 2022, "value": 20}, {"year": 2026, "value": None}], None, False),
    ([{"year": 2018, "value": 20}, {"year": 2023, "value": 0}], None, True),
    ([{"year": 2026, "reference": "2017-10", "value": 20}], None, False),
    ([{"year": 2023, "period_end": "2024-06-30", "value": 20}], True, True),
    ([{"reference": "2024-07", "value": None, "bound": 5}], True, True),
    ([], None, False),
])
def test_actual_measurement_dates_missingness_and_thresholds(rows, snapshot, expected):
    assert eligible(rows, snapshot) is expected


@pytest.mark.parametrize("measure,visible", [
    ("enrolled_students", False), ("degree_students", False),
    ("international_students", True), ("study_abroad", True),
])
def test_student_choices_are_retired_only_from_public_charts(measure, visible):
    from us_china_exchange.model import observation
    from us_china_exchange.public_freshness import annual_series
    from us_china_exchange.render import regional_series, svg_chart, svg_comparison

    rows = [observation("test", "CHN", "USA", measure, year, value, "Student population")
            for year, value in ((2000, 10), (2019, 20), (2025, 30))]
    assert eligible(rows) is visible
    assert bool(annual_series(rows)) is visible
    assert "<svg" in svg_chart(rows)
    assert regional_series(rows, measure, "to_us")["CHN"] == rows
    with public_charts():
        assert ("<svg" in svg_chart(rows)) is visible
        assert ("<svg" in svg_comparison(rows, measure, "to_us")) is visible
        assert bool(regional_series(rows, measure, "to_us")["CHN"]) is visible
    assert "<svg" in svg_chart(rows)


def test_scope_preserves_archive_and_history_but_not_unrelated_old_snapshots():
    groups = [
        {"id": "current", "cadence": "annual", "points": [{"year": 2010, "value": 1}, {"year": 2023, "value": 2}]},
        {"id": "stale", "cadence": "annual", "points": [{"year": 2018, "value": 5}]},
        {"id": "snapshots", "cadence": "inventory snapshot", "points": [{"year": 2021, "value": 6}, {"year": 2025, "value": 7}]},
        {"id": "poll", "cadence": "survey_rounds", "points": [{"year": 2016, "value": 39}]},
        {"id": "poll", "cadence": "survey_rounds", "points": [{"year": 2026, "value": 37}]},
    ]
    assert current_groups(groups) is groups
    with public_charts():
        result = current_groups(groups)
        assert [g["id"] for g in result] == ["current", "snapshots", "poll", "poll"]
        assert [p["year"] for p in result[0]["points"]] == [2010, 2023]
        assert [p["year"] for p in result[1]["points"]] == [2025]
        assert result[-2]["points"][0]["year"] == 2016
    assert not public() and current_groups(groups) is groups
    with pytest.raises(RuntimeError), public_charts():
        raise RuntimeError("build failed")
    assert not public()


def test_publication_retires_all_stale_surfaces_but_keeps_complete_data(tmp_path):
    spec = importlib.util.spec_from_file_location("fresh_publication", ROOT / "scripts/build_exchange_publication.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stale = "figures/students/themarginoferror/moe-USA-CHN-enrolled_students.svg"
    old = tmp_path / stale
    old.parent.mkdir(parents=True)
    old.write_text("Previously published old graph")
    custom = tmp_path / "figures/custom.svg"
    custom.write_text("Unrelated user graphic")
    previous = {stale: "old-sha"}
    for series in ("iie-CHN-USA-enrolled_students", "uis-CHN-USA-degree_students"):
        for theme in ("substack", "themarginoferror"):
            for extension in ("svg", "png"):
                path = tmp_path / f"figures/students/{theme}/{series}.{extension}"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Previously published retired graph")
                previous[str(path.relative_to(tmp_path))] = "old-sha"
    (tmp_path / "publication-manifest.json").write_text(json.dumps({"files": previous}))
    manifest = module.build_publication(ROOT, tmp_path, "freshness-test")
    assert not old.exists() and custom.read_text() == "Unrelated user graphic"
    assert all(not (tmp_path / path).exists() for path in previous)
    assert stale not in manifest["files"]
    assert manifest["chart_freshness"] == {"history_since": 2023, "snapshot_from": 2024, "snapshot_through": 2026}
    raw = json.loads((tmp_path / "downloads/exchange.json").read_text())
    assert raw["observations"] == json.loads((ROOT / "data/site/observations.json").read_text())
    retired = {"degree_students", "enrolled_students"}
    retired_ids = {r["series_id"] for r in raw["observations"] if r["measure"] in retired}
    assert retired <= raw["measures"].keys()
    assert retired_ids and not retired_ids.intersection(raw["visible_series"])
    for path in manifest["files"]:
        if path.startswith("figures/students/"):
            assert not any(measure in path for measure in retired), path
    students = BeautifulSoup((tmp_path / "index.html").read_text(), "html.parser")
    assert {o["value"] for o in students.select("#measure option")} == {
        "international_students", "study_abroad"}
    assert students.select_one('#measure option[value="international_students"]').text == "Enrolled + OPT"
    assert {o["value"] for o in students.select("#module-chart option")} == {
        "international_students-to_us", "study_abroad-from_us"}
    for measure in retired:
        assert not students.select(f'[id^="{measure}-"]')
    for script in students.select(".plot-data"):
        model = json.loads(script.string)
        assert not retired_ids.intersection(group["id"] for group in model.get("groups", []))
    directory = BeautifulSoup((tmp_path / "comparisons.html").read_text(), "html.parser")
    routes = json.loads(directory.select_one("#regional-topic-routes").string)
    assert not any(route.startswith(tuple(measure + "-" for measure in retired)) for route in routes)
    assert any(r["series_id"] == "moe:USA:CHN:enrolled_students" and r["year"] == 2018
               for r in raw["observations"])
    for name in ("index", "travel", "trade"):
        page = BeautifulSoup((tmp_path / (name + ".html")).read_text(), "html.parser")
        payload = json.loads(page.select_one("#exchange-data").string)
        assert "moe:USA:CHN:enrolled_students" not in payload["visible_series"]
        assert "nbs_tourism:USA:CHN:visitors" not in payload["visible_series"]
        for pane in page.select(".comparison-pane"):
            assert pane.select_one(".comparison-chart"), "Do not leave empty stale comparison panes"
    removed = {
        "language-learning.html": {"college-enrollments", "college-share", "college-benchmarks",
                                   "matched-college-benchmarks", "school-language-enrollments", "ap-chinese-us-cohorts"},
        "business-presence.html": {"eu-affiliates-china", "uk-affiliates-china", "us-parent-companies-china"},
        "opinions.html": {"us-china-earlier-favorability", "china-us-earlier-favorability"},
        "confucius.html": {"confucius-classrooms"},
    }
    for name, identifiers in removed.items():
        page = BeautifulSoup((tmp_path / name).read_text(), "html.parser")
        for identifier in identifiers:
            assert not page.select("#" + identifier), (name, identifier)
            assert not page.select(f'[data-confucius-chart="{identifier}"]'), (name, identifier)
        assert not identifiers.intersection(o["value"] for o in page.select("#module-chart option"))
    confucius = BeautifulSoup((tmp_path / "confucius.html").read_text(), "html.parser")
    assert confucius.select_one("main > .series-panel")["id"] == "confucius-institutes"
    assert not confucius.select_one(".confucius-directory").has_attr("open")
    assert not confucius.select("#confucius-institutes .confucius-summary")
    assert "Operating status" not in confucius.get_text()
    assert "Reported histories: 2006–2023" in confucius.select_one('meta[name="description"]')["content"]
    assert not confucius.select(".covid-band,.covid-label")
    for identifier in ("confucius-institutes", "confucius-campus", "confucius-successors"):
        model = json.loads(confucius.select_one(f'[data-confucius-chart="{identifier}"] .confucius-plot-data').string)
        assert model["layout"] == "timeline"
        assert "covid_context" not in model
        assert len({r["observation_year"] for r in model["rows"]}) > 1
        assert max(r["observation_year"] for r in model["rows"]) == 2023
    languages = BeautifulSoup((tmp_path / "language-learning.html").read_text(), "html.parser")
    assert languages.select_one('#module-chart option[selected]')["value"] == "chinese-bachelors"
    inventory = json.loads(languages.select_one("#school-program-inventories .plot-data").string)
    assert [bar["year"] for bar in inventory["bars"]] == [2025]
    opinions = BeautifulSoup((tmp_path / "opinions.html").read_text(), "html.parser")
    warmth = json.loads(opinions.select_one("#us-china-warmth .plot-data").string)
    assert [bar["year"] for bar in warmth["bars"]] == [2016, 2018, 2021, 2026]
    for source, target in (("language_learning", "language-learning"), ("opinions", "opinions")):
        assert json.loads((tmp_path / f"downloads/{target}.json").read_text()) == json.loads(
            (ROOT / f"data/site/{source}.json").read_text())
    spec = importlib.util.spec_from_file_location("freshness_checker", ROOT / "scripts/check_public_freshness.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.check(tmp_path)
