import copy
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from us_china_exchange.theme import png_dimensions
from bs4 import BeautifulSoup

from us_china_exchange.confucius_analysis import CHARTS, build_confucius, chart_rows, svg_counts
from us_china_exchange.confucius_sources import parse_directory, reference_date, reported, validate
from us_china_exchange.public_freshness import public_charts


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/confucius_programs.json").read_text())


def directory_row(key="123", name="Confucius Institute at Example", enable="0"):
    return {"siteKey": key, "name": name, "labelId": "C-Ame-United-States-of-America",
            "language": "EN", "enable": enable, "updateTime": "2026-01-01 00:00:00"}


@pytest.mark.parametrize("enable", ["0", "1"])
def test_operator_website_switch_is_never_interpreted_as_operating_status(enable):
    content = json.dumps({"code": 200, "data": [
        directory_row(enable=enable),
        directory_row("456", "Confucius Classroom at Example School", enable),
    ]})
    records = parse_directory(content)
    assert len(records) == 2
    assert {r["category"] for r in records} == {"institutes", "classrooms"}
    assert all(r["operating_status"] == "not_verified" for r in records)
    assert all(r["website_enable"] == enable for r in records)
    assert not any(r.get("active") for r in records)


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.append(copy.deepcopy(rows[0])),
    lambda rows: rows[0].update(labelId="C-Ame-Canada"),
    lambda rows: rows[0].update(name="Unclassified Chinese Partnership"),
    lambda rows: rows[0].update(language="CN"),
])
def test_unexpected_directory_identity_scope_or_labels_require_review(mutate):
    rows = [directory_row()]
    mutate(rows)
    with pytest.raises(ValueError):
        parse_directory(json.dumps({"code": 200, "data": rows}))


def test_primary_report_checkpoints_preserve_reference_periods_and_bounds():
    data = validate(published())
    rows = {r["id"]: r for r in data["observations"]}
    # Independently reviewed original report facts, not expectations recomputed by the collector.
    assert (rows["mfa_2014_institutes_reported"]["reference"], rows["mfa_2014_institutes_reported"]["value"]) == ("2014-09-29", 100)
    assert rows["nas_2017_classrooms_reported"]["value"] == 501
    assert data["sources"]["nas_2017"]["published_on"] == "2017-04"
    assert rows["senate_classrooms_2019"]["reference"] == "2019-02"
    assert rows["senate_classrooms_2019"]["value"] == 519
    assert data["sources"]["senate_2019"]["published_on"] == "2019-02-27"
    assert (rows["gao_campus_2018"]["reference"], rows["gao_campus_2018"]["value"]) == ("2018-12", 96)
    bound = rows["gao_campus_2023"]
    assert (bound["reference"], bound["value"], bound["bound"], bound["qualifier"]) == ("2023-07", None, 5, "less_than")
    assert reported(bound) == "Fewer than 5"
    assert data["sources"]["gao_2023"]["published_on"] == "2023-10-30"
    assert (rows["nas_successors_2023"]["value"], rows["nas_successors_2023"]["bound"]) == (None, 28)
    assert reported(rows["nas_successors_2023"]) == "At least 28"
    assert len([r for r in data["observations"] if r["series_id"] == "classrooms_reported"]) == 3


def test_classroom_inventory_and_institute_campus_counts_never_enter_national_history():
    data = published()
    history = chart_rows(data, "confucius-classrooms")
    assert [r["value"] for r in history] == [366, 501, 519]
    assert not any(r["measurement"] in {"documented_inventory", "directory_listings"} for r in history)
    institutes = chart_rows(data, "confucius-institutes")
    assert not any(r["measurement"] == "campus_stock" for r in institutes)
    assert not any(r["id"] in {"gao_campus_2018", "gao_campus_2023"} for r in institutes)
    successors = chart_rows(data, "confucius-successors")
    assert {r["series_id"] for r in successors} == {"successors_documented"}
    assert not any(r["series_id"] in {"partners_retained", "successors_proposed", "institutes_transferred"} for r in successors)


def test_source_flags_and_directory_downloads_retain_all_selected_records_without_asserting_activity():
    data = published()
    records = data["records"]
    directory = [r for r in records if r["source_id"] == "cief_directory"]
    old = [r for r in records if r["source_id"] == "nas_roster_2023"]
    closures = [r for r in records if r["source_id"] == "nas_closures_2023"]
    assert len(directory) == 17 and len(old) == 10 and len(closures) == 108
    assert sum(r["category"] == "institutes" for r in directory) == 10
    assert sum(r["category"] == "classrooms" for r in directory) == 7
    assert sum(r["operating_status"] == "paused_as_reported" for r in old) == 1
    assert sum(r["replacement_flag"] == "R" for r in closures) == 29
    assert sum(r["replacement_flag"] == "R?" for r in closures) == 12
    assert any(r["replacement_flag"] == "R" and r["partnership_flag"] == "M" for r in closures)
    assert all(r["operating_status"] == "not_verified" for r in directory + closures)
    assert not any("createBy" in r or "createName" in r for r in records)


@pytest.mark.parametrize("change,match", [
    (lambda d: d["observations"].append(copy.deepcopy(d["observations"][0])), "Duplicate"),
    (lambda d: next(r for r in d["observations"] if r["id"] == "gao_campus_2023").update(value=5), "bounded"),
    (lambda d: next(r for r in d["observations"] if r["id"] == "cief_classrooms").update(value=519), "reconcile"),
    (lambda d: next(r for r in d["observations"] if r["id"] == "cief_institutes").update(reference_basis="as_of"), "Directory"),
    (lambda d: next(r for r in d["records"] if r["source_id"] == "cief_directory").update(operating_status="active"), "operation"),
    (lambda d: d["series"]["classrooms_inventory"].update(measurement="reported_stock"), "population"),
])
def test_invalid_bounds_category_semantics_or_directory_totals_are_rejected(change, match):
    data = published()
    change(data)
    with pytest.raises(ValueError, match=match):
        validate(data)


def test_transcription_checksums_are_explicit_not_publisher_pdf_hashes():
    data = published()
    source = data["sources"]["gao_2023"]
    assert source["evidence_kind"] == "reviewed_selected_facts"
    assert source["assets"][0]["request_url"].endswith("/data/reviewed/confucius-snapshots.json")
    source["assets"][0]["request_url"] = source["publisher_url"]
    with pytest.raises(ValueError, match="transcription"):
        validate(data)
    data = published()
    data["sources"]["gao_2023"]["evidence_kind"] = "publisher_response"
    with pytest.raises(ValueError, match="transcription"):
        validate(data)


def test_bounded_exports_have_open_boundary_marks_not_exact_count_bars():
    data = published()
    for chart_id, identity, phrase in (
            ("confucius-campus", "gao_campus_2023", "Fewer than 5"),
            ("confucius-successors", "nas_successors_2023", "At least 28")):
        svg = BeautifulSoup(svg_counts(data, chart_id), "html.parser")
        mark = svg.select_one(f'[data-observation-id="{identity}"]')
        assert mark["data-value"] == ""
        assert mark["data-bound"]
        assert mark.select_one(".confucius-boundary")
        assert mark.select_one(".confucius-bound")
        assert not mark.select_one(".confucius-bar")
        assert phrase in mark.select_one(".confucius-reported").text
        boundary = mark.select_one(".confucius-boundary")
        interval = mark.select_one(".confucius-bound")
        expected_end = "452" if chart_id == "confucius-campus" else "122"
        assert interval["d"].endswith("V" + expected_end)
        assert float(boundary["cy"]) == pytest.approx(
            452 - float(mark["data-bound"]) / float(svg.svg["data-axis-max"]) * 330, abs=.01)
        assert not svg.select(".data-line")


def test_history_uses_calendar_spacing_and_vertical_count_columns_not_snapshot_rows():
    data = published()
    svg = BeautifulSoup(svg_counts(data, "confucius-institutes"), "html.parser")
    assert svg.svg["data-chart-layout"] == "timeline"
    marks = {int(n["data-observation-year"]): n for n in svg.select(".confucius-mark")}
    assert set(marks) == {2006, 2007, 2014, 2015, 2017, 2021, 2022, 2023}
    bars = {year: mark.select_one(".confucius-bar") for year, mark in marks.items()}
    center = lambda bar: float(bar["x"]) + float(bar["width"]) / 2
    one_year = center(bars[2007]) - center(bars[2006])
    seven_years = center(bars[2014]) - center(bars[2007])
    assert seven_years == pytest.approx(7 * one_year, abs=.1)
    assert all(float(bar["y"]) + float(bar["height"]) == pytest.approx(452, abs=.02) for bar in bars.values())
    assert float(bars[2015]["height"]) / float(bars[2006]["height"]) == pytest.approx(109 / 11, abs=.002)
    years = [int(n.text) for n in svg.select(".confucius-year")]
    assert [years[0], years[-1]] == [2006, 2023]
    assert not svg.select(".data-line")


def test_directory_comparison_remains_categorical_not_a_fake_time_series():
    svg = BeautifulSoup(svg_counts(published(), "confucius-directory"), "html.parser")
    assert svg.svg["data-chart-layout"] == "bars"
    assert not svg.select(".confucius-year")
    assert len(svg.select(".confucius-bar")) == 2
    assert {n["x"] for n in svg.select(".confucius-bar")} == {"58"}


def test_public_histories_reaching_2023_are_not_misclassified_as_old_snapshots():
    data = published()
    with public_charts():
        history = chart_rows(data, "confucius-institutes")
        assert [r["observation_year"] for r in history] == [2006, 2007, 2014, 2015, 2017, 2021, 2022, 2023]
        campus = chart_rows(data, "confucius-campus")
        assert campus[-1]["bound"] == 5 and campus[-1]["value"] is None
        assert chart_rows(data, "confucius-classrooms") == []
        assert len(chart_rows(data, "confucius-directory")) == 2
        timeline = BeautifulSoup(svg_counts(data, "confucius-institutes"), "html.parser")
        assert not timeline.svg.has_attr("data-freshness-snapshot-from")
        assert not timeline.select(".covid-band,.covid-label")
        directory = BeautifulSoup(svg_counts(data, "confucius-directory"), "html.parser")
        assert directory.svg["data-freshness-snapshot-from"] == "2024"
        assert not directory.select(".covid-band")
        single = dict(data, observations=[r for r in data["observations"] if r["id"] == "nas_listed_jun2023"])
        assert chart_rows(single, "confucius-institutes") == []


def test_complete_exports_include_nonplotted_values_and_all_supporting_records(tmp_path):
    data = published()
    gallery = {"language_learning": []}
    assert build_confucius(tmp_path, data, gallery) == len(CHARTS)
    assert json.loads((tmp_path / "site/downloads/confucius-programs.json").read_text()) == data
    values = list(csv.DictReader((tmp_path / "site/downloads/confucius-observations.csv").open()))
    records = list(csv.DictReader((tmp_path / "site/downloads/confucius-records.csv").open()))
    assert len(values) == len(data["observations"]) and len(records) == len(data["records"])
    assert {r["id"] for r in values} == {r["id"] for r in data["observations"]}
    assert {r["id"] for r in records} == {r["id"] for r in data["records"]}
    assert any(r["measurement"] == "proposed_replacements" for r in values)
    assert any(r["measurement"] == "retained_partnerships" for r in values)
    bound = next(r for r in values if r["id"] == "gao_campus_2023")
    assert bound["value"] == "" and bound["bound"] == "5" and bound["qualifier"] == "less_than"
    page = BeautifulSoup((tmp_path / "site/confucius.html").read_text(), "html.parser")
    assert len(page.select("[data-confucius-row]")) == len(values)
    assert len(page.select("[data-directory-id]")) == 17
    directory = page.select_one(".confucius-directory table")
    assert [n.get_text(strip=True) for n in directory.select("thead th")] == ["Listed program", "Source label"]
    assert all(len(row.select("th,td")) == 2 for row in directory.select("tbody tr"))
    assert not directory.find(string="Not verified")
    assert all(r["operating_status"] == "not_verified" for r in records if r["source_id"] == "cief_directory")
    for theme, background in (("themarginoferror", "#F7F5F0"), ("substack", "#F5F5F5")):
        for chart_id in CHARTS:
            figure = tmp_path / f"outputs/figures/language_learning/{theme}/{chart_id}.svg"
            svg = BeautifulSoup(figure.read_text(), "html.parser")
            assert svg.select_one(".chart-background")["fill"] == background
            assert len(svg.select(".confucius-mark")) == len(chart_rows(data, chart_id))
            assert not svg.select(".covid-band,.covid-label")
            png = figure.with_suffix(".png").read_bytes()
            assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == png_dimensions(figure.read_text())


def test_reference_precision_is_not_changed_to_invented_end_of_year_dates():
    assert reference_date("2006").year == 2006
    data = published()
    row = next(r for r in chart_rows(data, "confucius-institutes") if r["id"] == "nas_history_2006")
    assert row["reference"] == row["label"] == "2006"
    with pytest.raises(ValueError):
        reference_date("2023-13")
