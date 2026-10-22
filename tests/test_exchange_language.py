import copy
import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from openpyxl import Workbook
from PIL import Image

from us_china_exchange import language_sources
from us_china_exchange.language_analysis import CHARTS, chart_points, svg_language_chart, validate_language_data
from us_china_exchange.model import digest
from us_china_exchange.render import build_languages
from us_china_exchange.render import build


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/language_learning.json").read_text())


def test_reviewed_checkpoints_and_derived_values_are_not_new_learner_counts():
    data = validate_language_data(published())
    values = {(r["series_id"], r["year"]): r["value"] for r in data["observations"]}
    assert [values[("mla:chinese", y)] for y in (2002, 2013, 2021)] == [34153, 61997, 46492]
    assert [values[("ipeds:" + award, 2022)] for award in ("bachelors", "masters", "doctorates")] == [364, 26, 14]
    assert values[("ap:global_total", 2025)] == 18518
    assert values[("ap:standard_group", 2025)] == 4777
    assert [values[("ap_cohort:us_public", y)] for y in (2007, 2008, 2010, 2013)] == [1056, 1992, 3428, 5684]
    assert next(r for r in data["observations"] if (r["series_id"], r["year"]) == (
        "ap_cohort:us_public", 2008))["source_id"] == "ap_cohort_2014"
    assert {r["year"] for r in data["observations"] if r["series_id"] == "ap:global_total"} == set(range(2007, 2026))
    assert {r["year"] for r in data["observations"] if r["series_id"] == "ipeds:bachelors"} == set(range(2000, 2025))
    shares = {r["year"]: r for r in chart_points(data, "college-share")[0]["points"]}
    assert shares[2013]["plotted_value"] == pytest.approx(61997 / 1561176 * 100)
    assert shares[2021]["plotted_value"] == pytest.approx(46492 / 1182562 * 100)
    indexed = chart_points(data, "college-benchmarks")[0]["points"]
    assert next(r for r in indexed if r["year"] == 2021)["plotted_value"] == pytest.approx(46492 / 61997 * 100)
    assert 2020 not in shares
    assert not any(r["value"] == 34341 for r in data["observations"])


def test_language_population_validation_rejects_global_to_us_relabelling_and_bad_subsets():
    data = published()
    data["series"]["ap:global_total"]["scope"] = "U.S.-only learners"
    with pytest.raises(ValueError, match="relabelled"):
        validate_language_data(data)
    data = published()
    next(r for r in data["observations"] if r["series_id"] == "ap:standard_group")["value"] = 10 ** 8
    with pytest.raises(ValueError, match="subset"):
        validate_language_data(data)
    data = published()
    next(r for r in data["observations"] if (r["series_id"], r["year"]) == (
        "ap:japanese_standard_group", 2025))["value"] = 10000
    with pytest.raises(ValueError, match="subset"):
        validate_language_data(data)
    data = published()
    data["observations"].append(copy.deepcopy(data["observations"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_language_data(data)
    data = published()
    data["context"]["nexus_response_scope"]["us_program_responses"] += 1
    with pytest.raises(ValueError, match="geographies"):
        validate_language_data(data)


def test_zero_baselines_missing_rounds_and_doctoral_breaks_are_not_silently_connected():
    data = published()
    next(r for r in data["observations"] if (r["series_id"], r["year"]) == ("mla:chinese", 2013))["value"] = 0
    assert chart_points(data, "college-benchmarks")[0]["points"] == []
    data = published()
    next(r for r in data["observations"] if (r["series_id"], r["year"]) == ("mla:chinese", 2016)).update(
        value=None, status="missing")
    doc = ElementTree.fromstring(svg_language_chart(data, "college-enrollments"))
    path = next(n for n in doc.iter() if n.get("class") == "data-line")
    assert path.get("d").count("M") == 2
    doc = ElementTree.fromstring(svg_language_chart(published(), "chinese-graduate-awards"))
    path = next(n for n in doc.iter() if n.get("data-series-id") == "ipeds:doctorates" and n.get("class") == "data-line")
    assert path.get("d").count("M") == 3


def test_all_language_exports_and_complete_csv_round_trip(tmp_path):
    data = published()
    gallery = defaultdict(list)
    count = build_languages(tmp_path, data, gallery)
    assert count == len(CHARTS)
    assert json.loads((tmp_path / "site/downloads/language-learning.json").read_text()) == data
    downloaded = list(csv.DictReader((tmp_path / "site/downloads/language-observations.csv").open()))
    assert len(downloaded) == len(data["observations"])
    for actual, expected in zip(downloaded, data["observations"]):
        assert all(actual[k] == ("" if v is None else str(v)) for k, v in expected.items())
        assert actual["scope"] == data["series"][expected["series_id"]]["scope"]
        assert json.loads(actual["source_assets"]) == data["sources"][expected["source_id"]]["assets"]
    plotted = list(csv.DictReader((tmp_path / "site/downloads/language-chart-values.csv").open()))
    expected = {(cid, group["id"], p["year"]): p for cid in CHARTS for group in chart_points(data, cid) for p in group["points"]}
    assert len(plotted) == len(expected)
    for r in plotted:
        p = expected[(r["chart_id"], r["series_id"], int(r["year"]))]
        assert float(r["plotted_value"]) == p["plotted_value"]
    figures = tmp_path / "outputs/figures/language_learning"
    for path in figures.glob("*/*.svg"):
        assert path.read_bytes() == (tmp_path / "site/figures/language_learning" / path.relative_to(figures)).read_bytes()
        with Image.open(path.with_suffix(".png")) as image:
            assert image.size == (3000, 1800)
        doc = ElementTree.fromstring(path.read_text())
        points = [n for n in doc.iter() if n.get("class") == "language-point"]
        wanted = {(group["id"], p["year"]): p for group in chart_points(data, path.stem) for p in group["points"]}
        assert len(points) == len(wanted)
        for point in points:
            assert float(point.get("data-value")) == wanted[(point.get("data-series-id"), int(point.get("data-year")))]["plotted_value"]
        if path.parent.name == "themarginoferror":
            other = ElementTree.fromstring((path.parent.parent / "substack" / path.name).read_text())
            next(n for n in other.iter() if n.get("class") == "chart-background").set("fill", "#F7F5F0")
            assert ElementTree.tostring(doc) == ElementTree.tostring(other)
    page = BeautifulSoup((tmp_path / "site/language-learning.html").read_text(), "html.parser")
    assert "global, not U.S.-only" in page.header.text
    assert "not the full 2021 census" in page.text
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    build_languages(tmp_path, data, defaultdict(list))
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    data["observations"] = [r for r in data["observations"] if not r["series_id"].startswith("ap:")]
    custom = figures / "substack/custom.svg"
    custom.write_text("User figure")
    build_languages(tmp_path, data, defaultdict(list))
    assert not list(figures.glob("*/ap-chinese-global.*"))
    assert custom.read_text() == "User figure"


def test_invalid_language_input_cannot_partially_rewrite_publication_and_removed_input_withdraws_exports(tmp_path):
    source = tmp_path / "data/site"
    source.mkdir(parents=True)
    canonical = json.loads((ROOT / "data/site/observations.json").read_text())
    (source / "observations.json").write_text(json.dumps(canonical[:1]))
    language_path = source / "language_learning.json"
    data = published()
    data["series"]["mla:korean"]["unit"] = "awards"
    language_path.write_text(json.dumps(data))
    (tmp_path / "site").mkdir()
    (tmp_path / "site/index.html").write_text("Last valid publication")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="units"):
        build(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    data = published()
    next(r for r in data["observations"] if r["series_id"] == "schools:k12_estimate").update(value=None, status="missing")
    language_path.write_text(json.dumps(data))
    assert build(tmp_path)["language_charts"] == len(CHARTS)
    custom = tmp_path / "outputs/figures/language_learning/substack/custom.svg"
    custom.write_text("User-owned")
    language_path.unlink()
    assert build(tmp_path)["language_charts"] == 0
    assert not (tmp_path / "site/language-learning.html").exists()
    assert not list((tmp_path / "site/downloads").glob("language-*"))
    assert not list((tmp_path / "site/figures/language_learning").glob("*/*.png"))
    assert list((tmp_path / "outputs/figures/language_learning").glob("*/*.svg")) == [custom]


def zipped_csv(name, rows, bom=False, extra=None):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue().encode("utf-8-sig" if bom else "cp1252")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(name, content)
        if extra:
            z.writestr(extra, content.replace(b"5", b"9"))
    return archive.getvalue()


@pytest.mark.parametrize("legacy", [False, True])
def test_ipeds_filters_geography_second_majors_revisions_and_legacy_totals(legacy):
    year = 2000 if legacy else 2022
    hd = [
        dict(unitid="1", stabbr="CA", deggrant="1", pset4flg="1"),
        dict(unitid="2", stabbr="PR", deggrant="1", pset4flg="1"),
        dict(unitid="3", stabbr="CA", deggrant="1", pset4flg="2"),
    ]
    records = []
    for unit, major, value in [("1", "1", "5"), ("1", "2", "99"), ("2", "1", "99"), ("3", "1", "99")]:
        r = dict(unitid=unit, cipcode="16.0301", awlevel="05")
        if legacy:
            if major == "2":
                continue
            r.update(crace15="2" if unit == "1" else value, crace16="3" if unit == "1" else value)
        else:
            r.update(majornum=major, ctotalt=value, xctotalt="R")
        records.append(r)
    directory = zipped_csv("hd.csv", hd, bom=True)
    completions = zipped_csv("c_a.csv" if legacy else "c_a_rv.csv", records,
                             extra=None if legacy else "c_a.csv")

    def get(url):
        body = directory if ("HD" in url or "hd.zip" in url) else completions
        return body, dict(url=url, request_url=url, sha256=digest(body), retrieved_at="2026-10-22T14:00:00+00:00")

    _, observations, sources = language_sources.ipeds(SimpleNamespace(get=get), [year])
    bachelor = next(r for r in observations if r["series_id"] == "ipeds:bachelors")
    assert bachelor["value"] == 5
    assert "no_major_split" in bachelor["comparability"] if legacy else True
    assert next(r for r in observations if r["series_id"] == "ipeds:masters")["value"] is None
    assert "CRACE15+CRACE16" in sources[f"ipeds_{year}"]["locator"] if legacy else "_rv.csv" in sources[f"ipeds_{year}"]["locator"]
    if not legacy:
        completions = zipped_csv("c_a.csv", [{k: v for k, v in r.items() if k != "majornum"} for r in records])
        with pytest.raises(ValueError, match="first-major"):
            language_sources.ipeds(SimpleNamespace(get=get), [year])


def test_ap_parser_does_not_confuse_total_with_passing_or_standard_counts(monkeypatch):
    text = ("Global AP Chinese Language and Culture May 2025\nTotal Group\nNumber of Students 18,518 -\n"
            "3 or Higher / % 16,518 89.2\nStandard Group**\nNumber of Students 4,777 -")
    monkeypatch.setattr(language_sources, "pdf_text", lambda body: [text])
    assert language_sources.parse_ap_chinese(b"fixture", 2025) == (18518, 4777)
    with pytest.raises(ValueError, match="geography/year"):
        language_sources.parse_ap_chinese(b"fixture", 2024)
    monkeypatch.setattr(language_sources, "pdf_text", lambda body: [text.replace("Chinese", "Japanese")])
    with pytest.raises(ValueError, match="subject"):
        language_sources.parse_ap_chinese(b"fixture", 2025)
    assert language_sources.parse_ap_language(b"fixture", 2025, "Japanese") == (18518, 4777)


def test_ap_history_ignores_empty_participation_counts_in_percentage_only_years():
    header = "<tr>" + "".join(f"<th>{s}</th>" for s in ["Year", "5", "4", "3", "2", "1", "3+", "Test Takers", "Mean Score"]) + "</tr>"
    def table(group, count):
        return (f"<table><caption>Past AP Japanese Language and Culture Score Distributions ({group} Group)</caption>" +
                header + "<tr>" + "".join(f"<td>{s}</td>" for s in ["2025", "43%", "11%", "20%", "8%", "18%", "74%", count, "3.55"]) +
                "</tr><tr>" + "".join(f"<td>{s}</td>" for s in ["2026", "47%", "10%", "15%", "7%", "21%", "72%", "", ""]) + "</tr></table>")
    body = (table("Total", "3,269") + table("Standard", "1,446")).encode()
    assert language_sources.parse_ap_history(body, "Japanese") == {"total": {2025: 3269}, "standard": {2025: 1446}}
    with pytest.raises(ValueError, match="tables missing"):
        language_sources.parse_ap_history(body, "Chinese")


def test_ap_language_benchmarks_have_matching_years_populations_and_colours():
    data = published()
    for chart_id in ["ap-chinese-global", "ap-language-standard-group"]:
        groups = chart_points(data, chart_id)
        assert len(groups) == 2
        assert [g["color"] for g in groups] == ["#7B2D26", "#3D6F8C"]
        assert all({p["year"] for p in g["points"]} == set(range(2007, 2026)) for g in groups)
        doc = ElementTree.fromstring(svg_language_chart(data, chart_id))
        years = [int(n.text) for n in doc.iter() if n.get("class") == "year-tick"]
        assert years[0] == 2007 and years[-1] == 2025 and 2026 not in years
    values = {(r["series_id"], r["year"]): r["value"] for r in data["observations"]}
    assert values[("ap:japanese_total", 2025)] == 3269
    assert values[("ap:japanese_standard_group", 2025)] == 1446
    assert not any(s.startswith("ap:") and "korean" in s for s in data["series"])


def test_us_ap_cohorts_exclude_standard_group_counts_and_use_later_reviewed_vintages(monkeypatch):
    heading = "Chinese Language\nand Culture\nScore Distributions\nU.S. public schools only; graduating classes\n"
    tables = {
        2011: heading + "".join(f"{score} N/A N/A {10 - i} / 20.0% {20 - i} / 20.0%\n"
                                for i, score in enumerate("54321")) +
              "".join(f"{score} N/A N/A 1 / 20.0% 2 / 20.0%\n" for score in "54321"),
        2013: heading + "".join(f"{year}\n" + "".join(f"{start+i}\n" for i in range(5))
                                for year, start in [(2007, 1), (2011, 11), (2012, 21)]),
        2014: heading + "".join(f"{score} — — 5 20.0% 30 20.0% 40 20.0%\n" for score in "54321"),
    }
    monkeypatch.setattr(language_sources, "pdf_text", lambda body: [
        "Contents: Chinese Language and Culture", tables[int(body)]])

    def get(url):
        year = 2011 if "2011" in url else 2013 if "9th-annual" in url else 2014
        body = str(year).encode()
        return body, dict(url=url, request_url=url, sha256=digest(body), retrieved_at="2026-10-22T14:00:00+00:00")

    definitions, observations, _ = language_sources.ap_us_cohorts(SimpleNamespace(get=get))
    assert definitions["ap_cohort:us_public"]["period_basis"] == "graduating class"
    assert {r["year"]: r["value"] for r in observations} == {
        2007: 15, 2008: 25, 2009: 40, 2010: 90, 2011: 65, 2012: 150, 2013: 200}


def test_mla_matched_panel_keeps_explicit_zeros_but_excludes_nonresponse_and_new_entrants(monkeypatch):
    headers = ["INST_ID", "SRVY_YEAR", "TERM", "LANGUAGE", "ALL LEVEL TOTAL", "N_RESP", "ZERO_ERL"]
    rows = []
    for year, institution, counts in [
        (2013, 1, [10, 2, 1, 20]), (2013, 2, [5, 0, 0, 5]),
        (2021, 1, [8, 3, 2, 16]), (2021, 3, [4, 0, 0, 0]), (2021, 4, [100, 0, 0, 0]),
        (2013, 6, [50, None, 0, 0]), (2021, 6, [30, 2, 0, 0]),
    ]:
        rows += [[institution, year, "Fall", language, count, None, None]
                 for language, count in zip(["CHINESE", "JAPANESE", "KOREAN", "SPANISH"], counts)]
    rows += [[3, 2013, "Fall", None, 0, None, "Z"], [2, 2021, "Fall", None, 0, "NR", None]]
    report = "Table 5 Fall Enrollments in the Fifteen\n"
    for label, lang in [("Mandarin", "CHINESE"), ("Japanese", "JAPANESE"), ("Korean", "KOREAN"),
                        ("Spanish", "SPANISH"), ("Total", None)]:
        values = [0] * 10
        for pos, year in [(7, 2013), (9, 2021)]:
            values[pos] = sum(r[4] for r in rows if r[1] == year and r[5] != "NR" and r[4] is not None
                              and (lang is None or r[3] == lang))
        report += label + " " + " ".join(map(str, values + [0, 0])) + "\n"
    monkeypatch.setattr(language_sources, "pdf_text", lambda body: [report])
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "FL history"
    sheet.append(headers)
    for r in rows:
        sheet.append(r)
    stream = io.BytesIO()
    workbook.save(stream)

    def get(url):
        body = stream.getvalue() if url.endswith(".xlsx") else b"PDF"
        return body, dict(url=url, request_url=url, sha256=digest(body), retrieved_at="2026-10-22T14:00:00+00:00")

    definitions, observations, _ = language_sources.mla(SimpleNamespace(get=get))
    assert "Matched set of 2" in definitions["mla_matched:chinese"]["scope"]
    assert [(r["year"], r["value"]) for r in observations if r["series_id"] == "mla_matched:chinese"] == [(2013, 10), (2021, 12)]
