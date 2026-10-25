import copy
import csv
import json
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup

from us_china_exchange.immigration_analysis import CHARTS, build_immigration, validate_immigration_data
from us_china_exchange.immigration_sources import count, parse_admissions, parse_birth, parse_latest, parse_macau_abode, parse_macau_abode_2008, parse_stock, STOCK_YEARS
from us_china_exchange.theme import CHART_THEMES


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/immigration.json").read_text())


def test_regional_panels_keep_an_unavailable_population_missing(tmp_path):
    data = published()
    for row in data["observations"]:
        if row["series_id"] == "un_stock:CHN:USA":
            row.update(value=None, status="missing")
    build_immigration(tmp_path, data, defaultdict(list))
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    panes = page.select("#migrant-stock-to-us > .comparison-panels > .comparison-pane")
    assert len(panes) == 2
    assert "No reported observations" in panes[0].select_one(".gap").text
    assert not panes[0].select("img")
    assert panes[1].select_one(".comparison-chart img")
    rows = list(csv.DictReader((tmp_path / "site/downloads/immigration-observations.csv").open()))
    assert all(row["value"] == "" for row in rows if row["series_id"] == "un_stock:CHN:USA")


def test_birthplace_and_nationality_counts_are_separate_fiscal_populations():
    data = validate_immigration_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert len(rows) == 181
    assert [rows[(f"ohss_birth:{geo}", 1989)]["value"] for geo in ("CHN", "HKG", "MAC")] == [32272, 9740, 246]
    assert [rows[("ohss_birth:CHN", year)]["value"] for year in (2000, 2014, 2024)] == [45652, 76089, 71470]
    assert rows[("ohss_birth:HKG", 2024)]["value"] == 1950
    assert rows[("ohss_birth:MAC", 2024)]["value"] == 80
    assert rows[("ohss_nationality:total", 2025)]["value"] == 65670
    assert rows[("ohss_nationality:new_arrivals", 2025)]["value"] == 27020
    assert rows[("ohss_nationality:adjustments", 2025)]["value"] == 38650
    assert [rows[("ohss_nationality:new_arrivals", year)]["value"] for year in range(2020, 2026)] == [
        12726, 11278, 25115, 21890, 23570, 27020]
    assert rows[("ohss_nationality:new_arrivals", 2020)]["status"] == "observed"
    assert rows[("ohss_nationality:new_arrivals", 2023)]["status"] == "rounded"
    assert ("ohss_birth:CHN", 2025) not in rows
    assert rows[("ohss_birth:CHN", 2024)]["status"] == "rounded"
    data = copy.deepcopy(data)
    data["series"]["ohss_birth:CHN"]["scope"] = "Chinese nationality"
    with pytest.raises(ValueError, match="Birthplace"):
        validate_immigration_data(data)
    data = published()
    next(r for r in data["observations"] if r["series_id"] == "ohss_nationality:total")["source_id"] = "ohss_birth_2024"
    with pytest.raises(ValueError, match="population/source"):
        validate_immigration_data(data)


def test_birth_parser_rejects_wrong_population_and_keeps_suppression():
    records = [
        ["PERSONS OBTAINING LAWFUL PERMANENT RESIDENT STATUS BY COUNTRY OF BIRTH"],
        ["Region and country of birth", 2023, 2024],
        ["China, People's Republic", 59260, 71470], ["Hong Kong", "D", 1950], ["Macau", "-", 80],
        ["Notes: rounded to nearest 10"],
    ]
    points = parse_birth(records, 2023, 2024, rounded=True)
    assert ("HKG", 2023, None, "suppressed") in points
    assert ("MAC", 2023, 0, "rounded") in points
    records[0][0] = "VISITOR ARRIVALS BY COUNTRY OF NATIONALITY"
    with pytest.raises(ValueError, match="birthplace"):
        parse_birth(records, 2023, 2024)
    with pytest.raises(ValueError, match="multiple"):
        count(71471, rounded=True)


def test_macau_approval_parser_uses_country_rows_and_calendar_years_not_resident_stocks():
    rows = [[None] * 12 for _ in range(12)]
    rows[0][2] = "INDIVIDUALS NEWLY GRANTED RIGHT OF ABODE BY COUNTRY OR TERRITORY"
    rows[4][0] = "Country or territory"
    for column, year, value in zip((3, 5, 7, 9, 11), (2010, 2015, 2023, 2024, 2025), (91, 67, 24, 25, 34)):
        rows[4][column] = year
        rows[6][column] = 1000
        rows[9][column] = value
    rows[7][1] = "Total"
    rows[10][2] = "Estados Unidos da América"
    rows[11][2] = "United States of America"
    assert parse_macau_abode(rows) == {2010: 91, 2015: 67, 2023: 24, 2024: 25, 2025: 34}
    rows[9][11] = 1001
    with pytest.raises(ValueError, match="exceed"):
        parse_macau_abode(rows)
    data = published()
    data["series"]["dsec_abode:USA:MAC"]["period_basis"] = "fiscal ending year"
    with pytest.raises(ValueError, match="calendar-year"):
        validate_immigration_data(data)


def test_latest_parser_reads_reported_annual_totals_not_quarters():
    rows = [[None] * 16 for _ in range(9)]
    rows[3][0] = "PERSONS OBTAINING LAWFUL PERMANENT RESIDENT STATUS BY COUNTRY OF NATIONALITY: FISCAL YEAR 2025"
    rows[5] = ["Region and country of nationality", "Total", None, None, None, None,
               "Adjustments of status", None, None, None, None, "New arrivals", None, None, None, None]
    rows[6] = [None, "Total", "Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4",
               "Total", "Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4",
               "Total", "Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4"]
    rows[8] = ["China, People's Republic", 65670, 17410, 16710, 14390, 17160,
               38650, 10260, 9060, 8920, 10400, 27020, 7140, 7650, 5470, 6760]
    assert parse_latest(rows) == {"total": 65670, "adjustments": 38650, "new_arrivals": 27020}
    rows[3][0] = rows[3][0].replace("2025", "2026")
    with pytest.raises(ValueError, match="nationality/year"):
        parse_latest(rows)


def test_legacy_macau_approvals_require_the_revised_population_and_exact_years():
    rows = [[""] * 13 for _ in range(13)]
    rows[0][2] = "INDIVIDUALS AUTHORIZED TO RESIDE IN MACAO BY COUNTRY/TERRITORY OF ISSUANCE OF IDENTITY DOCUMENT"
    rows[5][0] = "Country / Territory"
    rows[5][9], rows[5][11] = "2007", "2008"
    rows[7][1] = "Total"
    rows[7][9], rows[7][11] = 6115, 7917
    rows[10][6], rows[10][8] = "Estados Unidos", "United States"
    rows[10][9], rows[10][11] = 109, 112
    rows[12][1] = "Note: direct comparison with data prior to 2007 is not appropriate."
    assert parse_macau_abode_2008(rows) == {2007: 109, 2008: 112}
    changed = copy.deepcopy(rows)
    changed[5][9] = "2006"
    with pytest.raises(ValueError, match="year columns"):
        parse_macau_abode_2008(changed)
    changed = copy.deepcopy(rows)
    changed[12][1] = ""
    with pytest.raises(ValueError, match="boundary"):
        parse_macau_abode_2008(changed)
    changed = copy.deepcopy(rows)
    changed[10][11] = 7918
    with pytest.raises(ValueError, match="exceed"):
        parse_macau_abode_2008(changed)
    rows[0][2] = "END-YEAR BALANCE OF NON-RESIDENT WORKERS"
    with pytest.raises(ValueError, match="population"):
        parse_macau_abode_2008(rows)


def test_annual_admissions_keep_reported_precision_and_do_not_become_stock_changes():
    data = published()
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert [rows[("ohss_nationality:new_arrivals", year)]["value"] for year in range(2020, 2026)] == [
        12726, 11278, 25115, 21890, 23570, 27020]
    assert rows[("ohss_nationality:adjustments", 2020)]["value"] == 29023
    assert rows[("ohss_nationality:total", 2024)]["value"] == 70090
    assert rows[("ohss_nationality:new_arrivals", 2020)]["status"] == "observed"
    assert rows[("ohss_nationality:new_arrivals", 2023)]["status"] == "rounded"
    for year, values in {
            2016: (43796, 38117, 81913), 2017: (37867, 33932, 71799),
            2018: (30006, 35591, 65597), 2019: (27004, 35340, 62344)}.items():
        reported = [rows[(f"ohss_nationality:{kind}", year)] for kind in ("new_arrivals", "adjustments", "total")]
        assert tuple(r["value"] for r in reported) == values
        assert all(r["status"] == "observed" and r["source_id"] == f"ohss_nationality_{year}" for r in reported)
    data["observations"] = [r for r in data["observations"]
                            if r["series_id"] != "ohss_nationality:adjustments" or r["year"] == 2025]
    with pytest.raises(ValueError, match="same reported fiscal years"):
        validate_immigration_data(data)

def test_extended_histories_preserve_supported_prior_vintages_but_reject_new_gaps():
    data = published()
    data["observations"] = [r for r in data["observations"]
                            if (r["series_id"], r["year"]) != ("dsec_abode:USA:MAC", 2007)]
    assert len(validate_immigration_data(data)["observations"]) == 180
    data["observations"] = [
        r for r in data["observations"]
        if not (r["series_id"].startswith("ohss_nationality:") and r["year"] < 2020)
        and not (r["series_id"].startswith("ohss_birth:") and r["year"] < 2000)
        and not (r["series_id"] == "dsec_abode:USA:MAC" and r["year"] < 2010)]
    assert len(validate_immigration_data(data)["observations"]) == 133
    data["observations"] = [r for r in data["observations"]
                            if (r["series_id"], r["year"]) != ("ohss_nationality:total", 2022)]
    with pytest.raises(ValueError, match="complete reviewed annual history"):
        validate_immigration_data(data)


def test_older_admission_header_is_not_mistaken_for_quarters_or_rounded_counts():
    rows = [[None] * 16 for _ in range(7)]
    rows[1][0] = "PERMANENT RESIDENT STATUS BY COUNTRY OF NATIONALITY: FISCAL YEAR 2020"
    rows[3] = [None, "Total", None, None, None, None, "Adjustments of status", None, None, None, None,
               "New arrivals", None, None, None, None]
    rows[4] = ["Region and country of nationality", "Total", 1, 2, 3, 4, "Total", 1, 2, 3, 4, "Total", 1, 2, 3, 4]
    rows[6] = ["China, People's Republic", 41749, 15534, 12300, 5596, 8319,
               29023, 7476, 8638, 5108, 7801, 12726, 8058, 3662, 488, 518]
    assert parse_admissions(rows, 2020) == {"total": 41749, "adjustments": 29023, "new_arrivals": 12726}
    rows[4][1] = "Quarter 1"
    with pytest.raises(ValueError, match="annual reported totals"):
        parse_admissions(rows, 2020)


def test_immigration_exports_include_all_counts_and_fiscal_dates(tmp_path):
    data = published()
    assert build_immigration(tmp_path, data, defaultdict(list)) == len(CHARTS)
    assert json.loads((tmp_path / "site/downloads/immigration.json").read_text()) == data
    with (tmp_path / "site/downloads/immigration-observations.csv").open() as stream:
        raw = list(csv.DictReader(stream))
    assert len(raw) == len(data["observations"]) == 181
    row = next(r for r in raw if r["series_id"] == "ohss_nationality:total" and r["year"] == "2025")
    assert row["fiscal_period_start"] == "2024-10-01" and row["fiscal_period_end"] == "2025-09-30"
    assert row["value"] == "65670"
    assert row["notes"] != row["definition_notes"]
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    assert "nationality" in page.select_one("#latest-admissions").text.lower()
    assert "not_verified" in page.text
    svg = ElementTree.fromstring((tmp_path / "site/figures/immigration/themarginoferror/green-card-grants.svg").read_text())
    points = [n for n in svg.iter() if n.get("class") == "immigration-point"]
    assert len(points) == 108 and {int(p.get("data-year")) for p in points} == set(range(1989, 2025))
    assert not any(p.get("data-year") == "2025" for p in points)
    stock_row = next(r for r in raw if r["series_id"] == "un_stock:USA:CHN")
    assert stock_row["fiscal_period_start"] == stock_row["fiscal_period_end"] == ""
    assert stock_row["observation_date"] == "2000-07-01"
    approvals = [r for r in raw if r["series_id"] == "dsec_abode:USA:MAC"]
    assert [int(r["year"]) for r in approvals] == list(range(2007, 2026))
    assert [(int(r["year"]), int(r["value"])) for r in approvals[:3]] == [(2007, 109), (2008, 112), (2009, 125)]
    assert all(r["fiscal_period_start"] == r["fiscal_period_end"] == "" for r in approvals)
    assert approvals[-1]["calendar_period_start"] == "2025-01-01"
    assert approvals[-1]["calendar_period_end"] == "2025-12-31"
    assert approvals[-1]["value"] == "34"


def test_bilateral_stocks_retain_source_populations_and_actual_benchmark_years():
    data = validate_immigration_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert [rows[("un_stock:USA:CHN", y)]["value"] for y in STOCK_YEARS] == [49655, 59103, 69836, 63341, 55280, 60434]
    assert rows[("un_stock:CHN:USA", 2024)]["value"] == 2488775
    assert rows[("un_stock:USA:HKG", 2024)]["value"] == 14298
    assert all(r["status"] == "estimated" for r in rows.values() if r["series_id"].startswith("un_stock:"))
    assert ("un_stock:USA:CHN", 2025) not in rows
    changed = copy.deepcopy(data)
    changed["series"]["un_stock:USA:CHN"]["data_type"] = "B"
    with pytest.raises(ValueError, match="citizenship/birthplace"):
        validate_immigration_data(changed)
    changed = copy.deepcopy(data)
    next(r for r in changed["observations"] if r["series_id"] == "un_stock:USA:CHN")["year"] = 2001
    with pytest.raises(ValueError, match="invented years"):
        validate_immigration_data(changed)


def test_covid_context_covers_immigration_flows_but_not_stocks_or_snapshots(tmp_path):
    data = published()
    build_immigration(tmp_path, data, defaultdict(list))
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    flows = {
        "annual-china-to-us", "annual-china-adjustments", "green-card-grants",
        "hong-kong-green-cards", "macau-green-cards", "macau-residence-approvals",
    }
    for chart_id in CHARTS:
        section = page.select_one("#" + chart_id)
        note = section.select_one(".immigration-covid-note")
        assert bool(note) == (chart_id in flows)
        if note:
            assert "not a universal ban" in note.text
            assert "fiscal years" in note.text and "not border arrivals" in note.text
            assert section.select(".immigration-covid-sources a")
        for theme in CHART_THEMES:
            paths = list((tmp_path / "site/figures/immigration" / theme).glob(chart_id + "*.svg"))
            assert paths
            for path in paths:
                svg = BeautifulSoup(path.read_text(), "html.parser")
                assert bool(svg.select(".covid-band")) == (chart_id == "annual-china-to-us")
                if chart_id in flows:
                    footnote = " ".join(node.text for node in svg.select(".figure-source"))
                    assert "universal ban" in footnote
                    assert "In-country status adjustments are not border arrivals" in svg.find("desc").text
                    assert all(float(node["y"]) <= 580 for node in svg.select(".figure-source"))
        if chart_id in flows - {"annual-china-to-us", "macau-residence-approvals"}:
            assert "March 18, 2020" in note.text and "June 4, 2020" in note.text
    assert json.loads((tmp_path / "site/downloads/immigration.json").read_text()) == data
