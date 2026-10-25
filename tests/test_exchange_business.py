import copy
import csv
import io
import importlib.util
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from PIL import Image, ImageColor
from openpyxl import Workbook

from us_china_exchange.business_analysis import BENCHMARK_CHART, CHARTS, COLORS, RETIRED_CHARTS, build_business, chart_groups, svg_business_chart, validate_business_data
from us_china_exchange.business_sources import NORDIC_QUERIES, SWEDEN_COUNTRIES, SWEDEN_QUALITY, count_cell, country_counts, parse_eurostat, parse_germany, parse_norway, parse_nordic, parse_ons
from us_china_exchange.render import build
from us_china_exchange.theme import CHART_THEMES, PARTNER_COLORS


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/business_presence.json").read_text())


def eurostat():
    codes = {"freq": "A", "nace_r2": "B-S_X_O", "indic_sbs": "ENT_NR", "partner": "CN_X_HK", "geo": "EU27_2020"}
    return {
        "id": list(codes) + ["time"], "size": [1] * 5 + [3],
        "dimension": dict({k: {"category": {"index": {v: 0}}} for k, v in codes.items()},
                          time={"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}),
        "extension": {"id": "FATS_OUT_PART"}, "value": {"0": 6900, "1": 7191, "2": 0},
        "status": {"0": "e", "2": "|C"},
    }


def test_distinct_parent_and_affiliate_checkpoints_remain_different_units():
    data = validate_business_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert [rows[("bea_parents:china", y)]["value"] for y in (2004, 2009, 2014, 2019)] == [581, 841, 1244, 1134]
    assert rows[("bea_affiliates:china", 2000)]["value"] == 458
    assert rows[("bea_affiliates:china", 2023)]["value"] == 1950
    assert rows[("bea_affiliates:china", 2023)]["status"] == "provisional"
    assert rows[("eurostat_affiliates:china", 2023)]["value"] is None
    assert rows[("eurostat_affiliates:china", 2023)]["status"] == "suppressed"
    assert rows[("eurostat_affiliates:china", 2021)]["status"] == "estimated"
    assert ("bea_parents:china", 2023) not in rows
    assert all(sid.endswith(":china") for sid in data["series"])
    assert [rows[("eurostat_historical_eu:china", y)]["value"] for y in (2009, 2011, 2012)] == [5688, 6607, 6860]
    assert [rows[("eurostat_uk:china", y)]["value"] for y in (2010, 2018, 2019)] == [681, 709, 531]
    assert rows[("eurostat_uk:china", 2019)]["status"] == "estimated"
    assert rows[("eurostat_norway:china", 2023)]["value"] == 88
    assert len([r for r in rows.values() if not r["series_id"].startswith(("tillvaxtanalys_", "statfin_", "eurostat_france:"))]) == 109
    assert rows[("ssb_norway:china", 2023)]["value"] == 89
    assert rows[("ssb_norway:china", 2024)]["value"] == 80


def test_german_workbook_counts_entities_not_employment_and_does_not_splice_other_vintages():
    book = Workbook()
    book.active.title = "DATA"
    for r in [[], [], [None, 45291, 45657],
              ["BBFOFATS.A.DE.ENT.BTSXO.CN", 1929, 1911],
              ["BBFOFATS.A.DE.EMP.BTSXO.CN", 543341, 550000],
              ["BBFOFATS.A.DE.ENT.BTSXO.HK", 345, 318]]:
        book.active.append(r)
    book.create_sheet("Methodology").append([
        "Foreign affiliates ultimately controlled by German investors; more than 50%; total assets exceed €3 million"])
    book.create_sheet("Economic activity").append([
        "BTSXO", "All economic activities (without agriculture, public administration, private households)"])

    def parse():
        stream = io.BytesIO()
        book.save(stream)
        return parse_germany(stream.getvalue())

    assert parse() == [(2023, 1929, "observed"), (2024, 1911, "provisional")]
    book["DATA"].cell(4, 3, "X")
    assert parse()[1] == (2024, None, "missing")
    book["DATA"].cell(4, 1, "BBFOFATS.A.DE.EMP.BTSXO.CN")
    with pytest.raises(ValueError, match="enterprise-count"):
        parse()
    groups = (chart_groups(published(), "germany-affiliates-china-eurostat")
              + chart_groups(published(), "germany-affiliates-china"))
    assert [g["id"] for g in groups] == ["eurostat_germany:china", "bundesbank_germany:china"]
    assert [[p["year"] for p in g["points"]] for g in groups] == [
        list(range(2010, 2024)), list(range(2021, 2025))]
    assert [next(p["value"] for p in g["points"] if p["year"] == 2023) for g in groups] == [1921, 1929]
    assert groups[0]["points"][10]["comparability"] != groups[0]["points"][11]["comparability"]


def test_eurostat_confidential_zero_is_not_published_and_wrong_populations_fail():
    data = eurostat()
    points = parse_eurostat(data, "fats_out_part")
    assert [r[1:3] for r in points] == [(6900, "estimated"), (7191, "observed"), (None, "suppressed")]
    data["dimension"]["partner"]["category"]["index"] = {"CN": 0}
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out_part")
    data = eurostat()
    data["status"]["0"] = "x"
    with pytest.raises(ValueError, match="Unknown"):
        parse_eurostat(data, "fats_out_part")
    data = eurostat()
    data["status"]["1"] = "b"
    points = parse_eurostat(data, "fats_out_part")
    assert points[0][-1] != points[1][-1]
    with pytest.raises(ValueError, match="count"):
        count_cell(1.5)
    data = eurostat()
    data["dimension"]["geo"]["category"]["index"] = {"UK": 0}
    assert parse_eurostat(data, "fats_out_part", "UK")[0][1] == 6900
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out_part")


def test_norwegian_history_uses_own_full_population_not_a_eurostat_endpoint_splice():
    data = {
        "source": "Statistics Norway", "class": "dataset",
        "extension": {"px": {"tableid": "09827"}},
        "id": ["Land", "ContentsCode", "Tid"], "size": [1, 1, 2],
        "dimension": {
            "Land": {"category": {"index": {"CN": 0}}},
            "ContentsCode": {"category": {"index": {"Foretak": 0},
                "unit": {"Foretak": {"base": "enterprises", "decimals": 0}}}},
            "Tid": {"category": {"index": {"2023": 0, "2024": 1}}}},
        "value": [89, 80],
    }
    assert parse_norway(data) == [(2023, 89, "observed"), (2024, 80, "observed")]
    data["value"][1] = None
    assert parse_norway(data)[1] == (2024, None, "missing")
    data["dimension"]["Land"]["category"]["index"] = {"HK": 0}
    with pytest.raises(ValueError, match="country"):
        parse_norway(data)
    groups = chart_groups(published(), "norway-affiliates-china")
    assert len(groups) == 1 and groups[0]["id"] == "ssb_norway:china"
    assert [p["year"] for p in groups[0]["points"]] == list(range(2008, 2025))


def nordic_fixture(country):
    if country == "sweden":
        dimensions = ["Tid", "Etableringsland", "variabel"]
        years, geo, metric, label = ["2009", "2010", "2024"], "cn", "2", "Antal dotterbolag"
        publisher = "Myndigheten f\u00f6r tillv\u00e4xtpolitiska utv\u00e4rderingar och analyser"
        values, flags = [None, 433, 885], {"0": ".."}
    else:
        dimensions = ["timeperiod_y", "valtio_27_20180101", "contentscode"]
        years, geo, metric, label = ["2020", "2021", "2024"], "156", "ofats_count", "Number of affiliates"
        publisher = "Statistics Finland, finnish affiliates abroad"
        values, flags = [250, 249, 242], {}
    return {
        "class": "dataset", "source": publisher, "id": dimensions, "size": [3, 1, 1],
        "dimension": {
            dimensions[0]: {"category": {"index": {year: i for i, year in enumerate(years)}}},
            dimensions[1]: {"category": {"index": {geo: 0}}},
            dimensions[2]: {"category": {"index": {metric: 0}, "label": {metric: label}}},
        }, "value": values, "status": flags,
    }


@pytest.mark.parametrize("country,values", [("sweden", [None, 433, 885]), ("finland", [250, 249, 242])])
def test_nordic_parsers_keep_reported_counts_and_reject_wrong_country_or_unit(country, values):
    data = nordic_fixture(country)
    assert [point[1] for point in parse_nordic(data, country)] == values
    if country == "sweden":
        assert parse_nordic(data, country)[0][2] == "missing"
    else:
        assert parse_nordic(data, country)[0][3] != parse_nordic(data, country)[1][3]
    for dimension, replacement in [(1, "hk"), (2, "parent_groups")]:
        changed = copy.deepcopy(data)
        changed["dimension"][changed["id"][dimension]]["category"]["index"] = {replacement: 0}
        with pytest.raises(ValueError, match="country or affiliate counting unit"):
            parse_nordic(changed, country)
    data["status"]["1"] = "unreviewed"
    with pytest.raises(ValueError, match="Unreviewed"):
        parse_nordic(data, country)


def test_nordic_selective_collection_preserves_every_other_country_and_is_idempotent():
    spec = importlib.util.spec_from_file_location("business_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prior = published()
    prior["observations"] = [r for r in prior["observations"]
                             if not r["series_id"].startswith(("tillvaxtanalys_", "statfin_", "eurostat_france:"))]
    before = copy.deepcopy(prior)

    def asset(url, checksum="b" * 64):
        return dict(url=url, request_url=url, sha256=checksum, retrieved_at="2026-10-25T00:00:00+00:00")

    def post(url, query):
        country = "sweden" if url == SWEDEN_COUNTRIES else "finland"
        assert query == NORDIC_QUERIES[country]
        return json.dumps(nordic_fixture(country)).encode(), asset(url)

    client = SimpleNamespace(post_json=post, get=lambda url: (
        b"Reviewed methodology", asset(url, "5d7b77577caf3a9fb159c106bd7fe4e9196ef50f8e09b903b7cbb678d5301289")
        if url == SWEDEN_QUALITY else asset(url)))
    result = module.collect_nordic(client, prior)
    retained = {(r["series_id"], r["year"]): r for r in result["observations"]}
    assert len(prior["observations"]) == 109 and len(retained) == 115
    assert all(retained[r["series_id"], r["year"]] == r for r in prior["observations"])
    assert prior == before
    validate_business_data(result)
    assert module.collect_nordic(client, result) == result


def test_new_nordic_histories_retain_missing_years_and_source_definition_boundaries():
    data = published()
    sweden = {r["year"]: r for r in data["observations"] if r["series_id"] == "tillvaxtanalys_sweden:china"}
    assert set(sweden) == set(range(2000, 2025))
    assert all(sweden[y]["value"] is None and sweden[y]["status"] == "missing" for y in range(2000, 2010))
    assert sum(row["value"] is not None for row in sweden.values()) == 15
    for previous, current in [(2017, 2018), (2018, 2019), (2020, 2021)]:
        assert sweden[previous]["comparability"] != sweden[current]["comparability"]
    for chart, expected_years in [("sweden-affiliates-china", range(2010, 2025)),
                                   ("finland-affiliates-china", range(2020, 2025))]:
        doc = ElementTree.fromstring(svg_business_chart(data, chart))
        bars = [node for node in doc.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in bars] == list(expected_years)
        assert not any(node.get("class") == "data-line" for node in doc.iter())


def test_ons_parser_uses_enterprises_not_employment_and_verifies_year():
    book = Workbook()
    book.remove(book.active)
    for year, name, count in [(2018, "Table 1", 709), (2019, "Table 2", 531)]:
        sheet = book.create_sheet(name)
        sheet.cell(1, 1, f"UK Outward Foreign Affiliate Statistics: {year}")
        sheet.cell(9, 2, "TOTAL ACTIVITY")
        sheet.cell(10, 2, "ENT")
        sheet.append(["China", count, 124879, 15247499])
    stream = io.BytesIO()
    book.save(stream)
    assert parse_ons(stream.getvalue()) == [(2018, 709, "estimated"), (2019, 531, "estimated")]
    book["Table 2"].cell(1, 1, "2020")
    stream = io.BytesIO()
    book.save(stream)
    with pytest.raises(ValueError, match="year"):
        parse_ons(stream.getvalue())


def test_france_keeps_its_missing_cell_and_each_reported_population_boundary():
    data = published()
    rows = {r["year"]: r for r in data["observations"] if r["series_id"] == "eurostat_france:china"}
    assert set(rows) == set(range(2007, 2024))
    assert rows[2008]["value"] is None and rows[2008]["status"] == "missing"
    assert rows[2023]["value"] == 2153
    assert "China except Hong Kong" in data["series"]["eurostat_france:china"]["scope"]
    for previous, current in [(2007, 2009), (2009, 2010), (2015, 2016), (2020, 2021)]:
        assert rows[previous]["comparability"] != rows[current]["comparability"]
    doc = ElementTree.fromstring(svg_business_chart(data, "france-affiliates-china"))
    bars = [n for n in doc.iter() if n.get("class") == "annual-column"]
    assert [int(n.get("data-year")) for n in bars] == [y for y in range(2007, 2024) if y != 2008]
    assert not any(n.get("class") == "data-line" for n in doc.iter())


def test_earlier_eu_membership_and_classification_are_not_relabelled_as_current():
    data = eurostat()
    data["id"][1] = "nace_r1"
    data["id"][2] = "indic_bp"
    del data["dimension"]["nace_r2"], data["dimension"]["indic_sbs"]
    data["dimension"]["nace_r1"] = {"category": {"index": {"C-O_X_L": 0}}}
    data["dimension"]["indic_bp"] = {"category": {"index": {"ENT": 0}}}
    data["dimension"]["geo"]["category"]["index"] = {"EU27_2007": 0}
    data["dimension"]["time"]["category"]["index"] = {"2007": 0, "2008": 1, "2009": 2}
    data["extension"]["id"] = "FATS_OUT2"
    data["value"], data["status"] = {"2": 5688}, {}
    points = parse_eurostat(data, "fats_out2", "EU27_2007")
    assert [(r[0], r[1]) for r in points] == [(2007, None), (2008, None), (2009, 5688)]
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out2")


def test_count_parser_skips_contents_but_rejects_duplicate_country_rows():
    def sheet(name, rows):
        return SimpleNamespace(name=name, nrows=len(rows), row_values=lambda i: rows[i],
                               cell_value=lambda i, j: rows[i][j])
    contents = sheet("Contents", [["Number of U.S. Parents", ""]])
    table = sheet("Table I.K2", [["Number of U.S. Parents", "All industries"], ["China", 1134], ["Europe", 2701]])
    assert country_counts([contents, table], "Number of U.S. Parents") == {"China": (1134, "observed"), "Europe": (2701, "observed")}
    with pytest.raises(ValueError, match="Ambiguous"):
        country_counts([table, table], "Number of U.S. Parents")


def test_annual_histories_and_method_boundaries_are_not_endpoint_snapshots():
    data = published()
    doc = ElementTree.fromstring(svg_business_chart(data, BENCHMARK_CHART))
    assert not [n for n in doc.iter() if n.get("class") == "data-line"]
    assert len([n for n in doc.iter() if n.get("class") == "annual-column"]) == 4
    doc = ElementTree.fromstring(svg_business_chart(data, "us-affiliates-china"))
    assert not [n for n in doc.iter() if n.get("class") == "data-line"]
    assert len([n for n in doc.iter() if n.get("class") == "annual-column"]) == 24
    assert len(chart_groups(data, "us-affiliates-china")[0]["points"]) == 24
    assert sum(len(g["points"]) for g in chart_groups(data, "eu-affiliates-china")) == 12
    assert len(chart_groups(data, "uk-affiliates-china")[0]["points"]) == 10
    assert len(chart_groups(data, "norway-affiliates-china")[0]["points"]) == 17
    doc = ElementTree.fromstring(svg_business_chart(data, "eu-affiliates-china"))
    path = next(n for n in doc.iter() if n.get("class") == "data-line" and n.get("data-series-id") == "eurostat_affiliates:china")
    assert path.get("d").count("M") == 2
    assert "2023 confidential" in "".join(doc.itertext())
    assert "2023" in [n.text for n in doc.iter() if n.get("class") == "year-tick"]


def test_complete_business_downloads_exact_points_backgrounds_and_stale_cleanup(tmp_path):
    data = published()
    for base in (tmp_path / "outputs/figures/business_presence", tmp_path / "site/figures/business_presence"):
        (base / "substack").mkdir(parents=True)
        for chart_id in RETIRED_CHARTS:
            (base / "substack" / (chart_id + ".svg")).write_text("Obsolete wrong-destination chart")
    assert build_business(tmp_path, data, defaultdict(list)) == 10
    assert not any((tmp_path / "outputs/figures/business_presence/substack" / (cid + ".svg")).exists()
                   for cid in RETIRED_CHARTS)
    assert json.loads((tmp_path / "site/downloads/business-presence.json").read_text()) == data
    with (tmp_path / "site/downloads/business-observations.csv").open() as f:
        raw = list(csv.DictReader(f))
    assert len(raw) == len(data["observations"])
    for actual, expected in zip(raw, data["observations"]):
        assert all(actual[k] == ("" if v is None else str(v)) for k, v in expected.items())
        assert actual["unit"] == data["series"][expected["series_id"]]["unit"]
        assert json.loads(actual["source_assets"]) == data["sources"][expected["source_id"]]["assets"]
    with (tmp_path / "site/downloads/business-chart-values.csv").open() as f:
        plotted = list(csv.DictReader(f))
    wanted = {(cid, g["id"], p["year"]): p["plotted_value"]
              for cid in CHARTS for g in chart_groups(data, cid) for p in g["points"]}
    assert len(plotted) == len(wanted)
    for r in plotted:
        assert float(r["plotted_value"]) == wanted[(r["chart_id"], r["series_id"], int(r["year"]))]
    base = tmp_path / "outputs/figures/business_presence"
    for path in base.glob("*/*.svg"):
        doc = ElementTree.fromstring(path.read_text())
        points = [n for n in doc.iter() if n.get("class") == "business-point"]
        expected = {k[1:]: v for k, v in wanted.items() if k[0] == path.stem}
        assert len(points) == len(expected)
        for p in points:
            assert float(p.get("data-value")) == expected[(p.get("data-series-id"), int(p.get("data-year")))]
            assert p.get("fill") == COLORS[p.get("data-series-id")]
        for suffix in (".png", ".svg"):
            p = path.with_suffix(suffix)
            assert p.read_bytes() == (tmp_path / "site/figures/business_presence" / p.relative_to(base)).read_bytes()
        with Image.open(path.with_suffix(".png")) as image:
            assert image.size == (3000, 1800)
            assert image.getpixel((0, 0)) == (*ImageColor.getrgb(CHART_THEMES[path.parent.name]["background"]), 255)
    page = BeautifulSoup((tmp_path / "site/business-presence.html").read_text(), "html.parser")
    assert "different counting units" in page.header.text
    assert "EU27" in page.header.text and "not matched" in page.header.text
    table = page.select("#annual-values tbody tr")
    assert len(table) == 25 and table[0].th.text == "2000" and table[-1].th.text == "2024"
    assert page.select_one("#business-benchmark-background").get("open") is None
    assert page.select_one("#" + BENCHMARK_CHART).find_parent("details")["id"] == "business-benchmark-background"
    assert not page.select('#us-affiliates-europe,#us-affiliates-index,#us-parent-companies')
    custom = base / "substack/custom.svg"
    custom.write_text("User-owned")
    data["observations"] = [r for r in data["observations"] if not r["series_id"].startswith("eurostat")]
    build_business(tmp_path, data, defaultdict(list))
    assert not list(base.glob("*/eu-affiliates-china.*"))
    assert custom.read_text() == "User-owned"


def test_invalid_business_input_is_rejected_before_writes_and_deleted_input_withdraws_exports(tmp_path):
    path = tmp_path / "data/site"
    path.mkdir(parents=True)
    (path / "observations.json").write_text(json.dumps(json.loads((ROOT / "data/site/observations.json").read_text())[:1]))
    data = published()
    data["series"]["bea_parents:china"]["unit"] = "affiliates"
    frozen = path / "business_presence.json"
    frozen.write_text(json.dumps(data))
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="counting units"):
        build(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    frozen.write_text(json.dumps(published()))
    with pytest.raises(ValueError, match="current business evidence"):
        build(tmp_path)
    (path / "business_current.json").write_text((ROOT / "data/site/business_current.json").read_text())
    assert build(tmp_path)["business_charts"] == 11
    page = BeautifulSoup((tmp_path / "site/business-presence.html").read_text(), "html.parser")
    assert not page.select('a[href="language-learning.html"]')
    frozen.unlink()
    assert build(tmp_path)["business_charts"] == 0
    assert not (tmp_path / "site/business-presence.html").exists()
    assert not list((tmp_path / "site/downloads").glob("business-*"))
    assert not list((tmp_path / "outputs/figures/business_presence").glob("*/*.*"))


def test_publication_is_business_only_with_complete_data_original_downloads_and_provenance(tmp_path):
    spec = importlib.util.spec_from_file_location("business_publication", ROOT / "scripts/build_business_publication.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "published"
    manifest = module.build_publication(ROOT, output, "verified-source-revision")
    page = BeautifulSoup((output / "index.html").read_text(), "html.parser")
    assert page.select_one('link[rel="canonical"]')["href"] == manifest["canonical_url"]
    assert "Interactive analysis" in page.select_one(".publication-header nav").text
    assert not page.select('a[href="language-learning.html"],iframe')
    assert len(page.select("svg[role=img]")) == 13
    assert not page.select("#business-controls,#annual-values,#module-chart,#uk-affiliates-china,#eu-affiliates-china")
    assert len(page.select(".business-card.native-chart,.business-card .native-chart")) == 13
    assert len(page.select(".business-count-card")) == 7
    assert len(page.select("#business-inward-data table tbody tr")) == 25
    assert page.select_one("#business-data").get("open") is None
    assert set(p.name for p in (output / "downloads").iterdir()) == {
        "business-presence.json", "business-observations.csv", "business-chart-values.csv", "business-current.json",
        "business-current-observations.csv", "business-current-chart-values.csv",
        "business-inward.json", "business-inward-observations.csv", "business-inward-chart-values.csv"}
    data = json.loads((output / "downloads/business-presence.json").read_text())
    assert data == published() and manifest["historical_observations"] == 156
    assert manifest["observations"] == 59
    assert manifest["inward_observations"] == 50
    assert manifest["source_revision"] == "verified-source-revision"
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == checksum
    with (output / "downloads/business-observations.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 156
    for link in page.select('a[href^="figures/"]'):
        assert link.has_attr("data-original-chart") and (output / link["href"].split("?")[0]).is_file()
    assert not (output / "business-presence.html").exists()
    assert not any("weibo" in str(p.relative_to(output)) or "language" in str(p.relative_to(output))
                   for p in output.rglob("*"))
    custom = output / "figures/business_presence/substack/custom.svg"
    custom.write_text("User-owned")
    source = tmp_path / "source"
    (source / "data/site").mkdir(parents=True)
    (source / "src/us_china_exchange").mkdir(parents=True)
    (source / "src/us_china_exchange/static").symlink_to(ROOT / "src/us_china_exchange/static", target_is_directory=True)
    data["observations"] = [r for r in data["observations"] if not r["series_id"].startswith("eurostat")]
    (source / "data/site/business_presence.json").write_text(json.dumps(data))
    (source / "data/site/business_current.json").write_text((ROOT / "data/site/business_current.json").read_text())
    module.build_publication(source, output, "next-revision")
    assert not list((output / "figures/business_presence").glob("*/eu-affiliates-china.*"))
    assert custom.read_text() == "User-owned"
    assert not list((output / "figures/business_presence").glob("*/*ubo-us-affiliates.*"))
    assert not list((output / "downloads").glob("business-inward*"))
