import copy
import csv
import hashlib
import importlib.util
import io
import json
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from openpyxl import Workbook

from us_china_exchange import immigration_sources
from us_china_exchange.immigration_analysis import CHARTS, build_immigration, validate_immigration_data
from us_china_exchange.immigration_sources import count, parse_admissions, parse_birth, parse_latest, parse_macau_abode, parse_macau_abode_2008, parse_stock, STOCK_YEARS
from us_china_exchange.theme import CHART_THEMES


ROOT = Path(__file__).resolve().parents[1]


def public_model_extractor():
    spec = importlib.util.spec_from_file_location(
        "public_migration_extractor", ROOT / "scripts/extract_public_migration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_query():
    with (ROOT / "data/reviewed/modelled-migration-us-china-full-query.csv").open(newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize("cached", [True, False])
def test_public_model_extract_preserves_all_source_fields_and_terminal_missingness(tmp_path, monkeypatch, cached):
    module = public_model_extractor()
    source = ROOT / "data/reviewed/modelled-migration-us-china-full-query.csv"
    source_path = source if cached else tmp_path / "cache/source.csv"
    output = tmp_path / "output"
    monkeypatch.setattr(module, "SOURCE_SHA256", module.sha256(source))
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: io.BytesIO(source.read_bytes()))
    monkeypatch.setattr("sys.argv", ["extract", "--source-csv", str(source_path), "--output", str(output)])
    module.main()
    with (output / source.name).open(newline="") as stream:
        assert list(csv.DictReader(stream)) == model_query()
    with (output / "modelled-migration-us-china.csv").open(newline="") as stream:
        flows = list(csv.DictReader(stream))
    original = {(r["Origin ISO"], r["Destination ISO"], r["Year"]): r for r in model_query()}
    assert len(original) == 70
    assert {(r["origin"], r["destination"], int(r["year"])) for r in flows} == {
        (o, d, y) for o, d in module.PAIRS for y in range(1990, 2024)}
    for row in flows:
        native = original[(row["origin"], row["destination"], row["year"])]
        assert (row["mean"], row["standard_deviation"], row["source_row_index"]) == (
            native["mig_prev"], native["mig_prev_std"], native[""])
        assert row["status"] == "modelled_estimate"
    for origin, destination in module.PAIRS:
        assert all(original[(origin, destination, "2024")][f] == "" for f in module.NUMERIC if f.startswith("mig_"))
    metadata = json.loads((output / "modelled-migration-us-china.json").read_text())
    assert metadata["source_rows"] == model_query()
    assert metadata["observations"] == flows
    for filename, digest in metadata["derived_files_sha256"].items():
        assert module.sha256(output / filename) == digest
    assert module.sha256(output / module.LICENSE_NAME) == module.LICENSE_SHA256


@pytest.mark.parametrize("cached", [True, False])
def test_public_model_extract_rejects_bad_source_before_writing_outputs(tmp_path, monkeypatch, cached):
    module = public_model_extractor()
    source = tmp_path / "bad-source.csv"
    if cached:
        source.write_bytes(b"not the pinned numerical dataset")
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: io.BytesIO(b"bad download"))
    monkeypatch.setattr("sys.argv", ["extract", "--source-csv", str(source), "--output", str(tmp_path / "output")])
    with pytest.raises(ValueError, match="checksum"):
        module.main()
    assert not (tmp_path / "output").exists()
    assert not source.with_suffix(".csv.part").exists()
    assert source.exists() == cached


@pytest.mark.parametrize("change", ["missing_year", "duplicate", "invented_2024", "blank_flow", "negative_std", "infinite_mean"])
def test_public_model_extract_rejects_incomplete_or_invented_flows(change):
    rows = model_query()
    module = public_model_extractor()
    if change == "missing_year":
        rows.pop(0)
    elif change == "duplicate":
        rows.append(rows[0].copy())
    elif change == "invented_2024":
        next(r for r in rows if r["Year"] == "2024")["mig_prev"] = "0"
    else:
        field, value = {"blank_flow": ("mig_prev", ""),
                        "negative_std": ("mig_prev_std", "-1"),
                        "infinite_mean": ("mig_prev", "inf")}[change]
        rows[0][field] = value
    with pytest.raises(ValueError):
        module.extract(rows)


def published():
    return json.loads((ROOT / "data/site/immigration.json").read_text())


def test_arrivals_history_reaches_2000_without_splicing_or_imputing():
    from us_china_exchange.immigration_analysis import chart_groups

    data = validate_immigration_data(published())
    rows = {r["year"]: r for r in data["observations"] if r["series_id"] == "ohss_birth_arrivals:CHN"}
    assert [rows[y]["value"] for y in (2000, 2001, 2002, 2006, 2019, 2024)] == [
        28360, 23763, 31833, 37321, 26395, 24140]
    assert [rows[y]["status"] for y in (2003, 2004, 2005)] == ["missing"] * 3
    assert all(rows[y]["value"] is None for y in (2003, 2004, 2005))
    assert rows[2024]["status"] == "rounded"
    assert len([r for r in data["observations"] if r["series_id"] != "ohss_birth_arrivals:CHN"]) == 181
    groups = chart_groups(data, "new-permanent-resident-arrivals")
    assert groups[0]["id"] == "ohss_birth_arrivals:CHN"
    assert [p["year"] for p in groups[0]["points"]] == [2000, 2001, 2002, *range(2006, 2025)]
    assert any(r["series_id"] == "ohss_nationality:new_arrivals" for r in data["observations"])
    rows[2004].update(value=0, status="observed")
    with pytest.raises(ValueError, match="not imputed or zero"):
        validate_immigration_data(data)


def test_arrivals_parser_requires_birthplace_new_arrivals_and_full_class_total():
    parse = immigration_sources.parse_birth_arrivals
    rows = [
        ["PERSONS OBTAINING LAWFUL PERMANENT RESIDENT STATUS BY COUNTRY OF BIRTH: FISCAL YEAR 2006"],
        ["Region and country of birth", "Adjustments of status", None, None, None, None, None, None, "  New arrivals  "],
        [None, "Total", None, None, None, None, None, None, "Total"],
        ["China, People's Republic", 49986, 1594, 7865, 13036, 7, 27454, 30, 37321, 14979, 1619, 20699, 13, "-", 11],
    ]
    assert parse(rows, 2006) == (37321, "observed")
    changed = copy.deepcopy(rows)
    changed[0][0] = changed[0][0].replace("COUNTRY OF BIRTH", "COUNTRY OF LAST RESIDENCE")
    with pytest.raises(ValueError, match="birthplace"):
        parse(changed, 2006)
    changed = copy.deepcopy(rows)
    changed[1][8] = "Total grants"
    with pytest.raises(ValueError, match="new arrivals"):
        parse(changed, 2006)
    changed = copy.deepcopy(rows)
    changed[2][8] = "Employment-based preferences"
    with pytest.raises(ValueError, match="all-class"):
        parse(changed, 2006)
    changed = copy.deepcopy(rows)
    changed[3][8] = 87307
    with pytest.raises(ValueError, match="reconcile"):
        parse(changed, 2006)


def test_regional_panels_keep_an_unavailable_population_missing(tmp_path):
    data = published()
    for row in data["observations"]:
        if row["series_id"] == "un_stock:USA:CHN":
            row.update(value=None, status="missing")
    build_immigration(tmp_path, data, defaultdict(list))
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    archive = page.select('a[href="https://doi.org/10.17632/r2r444tpzs.2"]')
    assert len(archive) == 3
    assert all("Original table:" in a.text and "extracted XLS member" in a.parent.text for a in archive)
    panes = page.select("#migrant-stock-from-us > .comparison-panels > .comparison-pane")
    assert len(panes) == 2
    assert "No reported observations" in panes[0].select_one(".gap").text
    assert not panes[0].select("img")
    assert panes[1].select_one(".comparison-chart img")
    rows = list(csv.DictReader((tmp_path / "site/downloads/immigration-observations.csv").open()))
    assert all(row["value"] == "" for row in rows if row["series_id"] == "un_stock:USA:CHN")


def test_birthplace_and_nationality_counts_are_separate_fiscal_populations():
    data = validate_immigration_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert len(rows) == 206
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
    assert len(validate_immigration_data(data)["observations"]) == 205
    data["observations"] = [
        r for r in data["observations"]
        if not (r["series_id"].startswith("ohss_nationality:") and r["year"] < 2020)
        and not (r["series_id"].startswith("ohss_birth:") and r["year"] < 2000)
        and not (r["series_id"] == "dsec_abode:USA:MAC" and r["year"] < 2010)]
    assert len(validate_immigration_data(data)["observations"]) == 158
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


@pytest.mark.parametrize("year", [2016, 2017, 2018, 2019])
def test_admission_source_retains_the_explicit_nationality_correction(year, monkeypatch):
    url = f"https://ohss.dhs.gov/reviewed-fy{year}.xlsx"
    monkeypatch.setattr(immigration_sources, "ADMISSION_ASSETS", {year: url})
    correction = (
        "Note: Previously published numbers in this table were computed using Country of Birth. "
        "On September 2019, numbers in this table were updated to account for Country of Nationality.")

    class Client:
        def __init__(self, footer):
            self.footer = footer

        def get(self, requested):
            assert requested == url
            book = Workbook()
            sheet = book.active
            sheet.title = "Table 1A"
            sheet.append([f"PERMANENT RESIDENT STATUS BY COUNTRY OF NATIONALITY: FISCAL YEAR {year}"])
            sheet.append(["Region and country of nationality", "Total", None, None, None, None,
                          "Adjustments of status", None, None, None, None,
                          "New arrivals", None, None, None, None])
            sheet.append([None, "Total", 1, 2, 3, 4, "Total", 1, 2, 3, 4, "Total", 1, 2, 3, 4])
            sheet.append(["China, People's Republic", 30, None, None, None, None,
                          20, None, None, None, None, 10, None, None, None, None])
            sheet.append([self.footer])
            stream = io.BytesIO()
            book.save(stream)
            body = stream.getvalue()
            return body, {"url": url, "request_url": url,
                          "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at": "2026-10-24T22:52:10+00:00"}

    observations, sources = immigration_sources.admissions(Client(correction if year < 2019 else ""))
    assert {row["year"] for row in observations} == {year}
    assert {row["series_id"]: row["value"] for row in observations} == {
        "ohss_nationality:total": 30, "ohss_nationality:adjustments": 20,
        "ohss_nationality:new_arrivals": 10}
    source = sources[f"ohss_nationality_{year}"]
    if year < 2019:
        assert "September 2019" in source["vintage"]
        assert "Country of Birth" in source["notes"] and "Country of Nationality" in source["notes"]
        for footer in ("", correction.replace("September 2019", "October 2019"),
                       correction.replace("account for Country of Nationality", "account for Country of Birth")):
            with pytest.raises(ValueError, match="nationality correction"):
                immigration_sources.admissions(Client(footer))
    else:
        assert "September 2019" not in source["vintage"]


def test_immigration_exports_include_all_counts_and_fiscal_dates(tmp_path):
    from us_china_exchange.immigration_analysis import RETIRED_CHARTS

    data = published()
    retired_paths = [tmp_path / directory / "immigration" / theme / f"{chart_id}{suffix}.{extension}"
                     for directory in ("site/figures", "outputs/figures")
                     for theme in CHART_THEMES for chart_id in RETIRED_CHARTS
                     for suffix in ("", "-chn", "-hkg-mac") for extension in ("svg", "png")]
    for path in retired_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Previously published chart")
    assert build_immigration(tmp_path, data, defaultdict(list)) == len(CHARTS)
    assert all(not path.exists() for path in retired_paths)
    assert json.loads((tmp_path / "site/downloads/immigration.json").read_text()) == data
    with (tmp_path / "site/downloads/immigration-observations.csv").open() as stream:
        raw = list(csv.DictReader(stream))
    assert len(raw) == len(data["observations"]) == 206
    row = next(r for r in raw if r["series_id"] == "ohss_nationality:total" and r["year"] == "2025")
    assert row["fiscal_period_start"] == "2024-10-01" and row["fiscal_period_end"] == "2025-09-30"
    assert row["value"] == "65670"
    assert row["notes"] != row["definition_notes"]
    arrival_rows = {int(r["year"]): r for r in raw if r["series_id"] == "ohss_birth_arrivals:CHN"}
    assert arrival_rows[2000]["fiscal_period_start"] == "1999-10-01"
    assert arrival_rows[2000]["fiscal_period_end"] == "2000-09-30"
    assert arrival_rows[2000]["value"] == "28360"
    assert all(arrival_rows[y]["value"] == "" and arrival_rows[y]["status"] == "missing"
               for y in (2003, 2004, 2005))
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    assert all(not page.select("#" + chart_id) for chart_id in RETIRED_CHARTS)
    assert not any(chart_id in link["href"] for chart_id in RETIRED_CHARTS for link in page.select("a[href]"))
    assert {r["series_id"] for r in raw} == set(data["series"])
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
    assert page.select_one("main > section[id]")["id"] == "green-card-grants"
    arrival_title = page.select_one("#new-permanent-resident-arrivals h2").text
    assert "New" in arrival_title and "arrivals" in arrival_title
    history_link = page.select_one("#new-permanent-resident-arrivals .immigration-history-link")
    assert history_link.a["href"] == "immigration.html?indicator=green-card-grants"
    assert "FY1989-FY2024" in history_link.text and "not new arrivals alone" in history_link.text


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
        "new-permanent-resident-arrivals", "annual-china-adjustments", "green-card-grants",
        "hong-kong-green-cards", "macau-green-cards", "macau-residence-approvals",
        "new-permanent-resident-arrivals-nationality",
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
                assert bool(svg.select(".covid-band")) == (chart_id.startswith("new-permanent-resident-arrivals"))
                if chart_id in flows:
                    footnote = " ".join(node.text for node in svg.select(".figure-source"))
                    assert "universal ban" in footnote
                    assert "In-country status adjustments are not border arrivals" in svg.find("desc").text
                    assert all(float(node["y"]) <= 580 for node in svg.select(".figure-source"))
        if chart_id in flows - {"new-permanent-resident-arrivals", "new-permanent-resident-arrivals-nationality",
                                "macau-residence-approvals"}:
            assert "March 18, 2020" in note.text and "June 4, 2020" in note.text
    assert json.loads((tmp_path / "site/downloads/immigration.json").read_text()) == data
