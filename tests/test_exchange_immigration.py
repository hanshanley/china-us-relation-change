import copy
import csv
import json
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup

from us_china_exchange.immigration_analysis import CHARTS, build_immigration, validate_immigration_data
from us_china_exchange.immigration_sources import count, parse_birth, parse_latest, parse_stock, STOCK_YEARS


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/immigration.json").read_text())


def test_birthplace_and_nationality_counts_are_separate_fiscal_populations():
    data = validate_immigration_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert len(rows) == 102
    assert [rows[("ohss_birth:CHN", year)]["value"] for year in (2000, 2014, 2024)] == [45652, 76089, 71470]
    assert rows[("ohss_birth:HKG", 2024)]["value"] == 1950
    assert rows[("ohss_birth:MAC", 2024)]["value"] == 80
    assert rows[("ohss_nationality:total", 2025)]["value"] == 65670
    assert rows[("ohss_nationality:new_arrivals", 2025)]["value"] == 27020
    assert rows[("ohss_nationality:adjustments", 2025)]["value"] == 38650
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


def test_immigration_exports_include_all_counts_and_fiscal_dates(tmp_path):
    data = published()
    assert build_immigration(tmp_path, data, defaultdict(list)) == len(CHARTS)
    assert json.loads((tmp_path / "site/downloads/immigration.json").read_text()) == data
    with (tmp_path / "site/downloads/immigration-observations.csv").open() as stream:
        raw = list(csv.DictReader(stream))
    assert len(raw) == len(data["observations"]) == 102
    row = next(r for r in raw if r["series_id"] == "ohss_nationality:total")
    assert row["fiscal_period_start"] == "2024-10-01" and row["fiscal_period_end"] == "2025-09-30"
    assert row["value"] == "65670"
    assert row["notes"] != row["definition_notes"]
    page = BeautifulSoup((tmp_path / "site/immigration.html").read_text(), "html.parser")
    assert "nationality" in page.select_one("#latest-admissions").text.lower()
    assert "not_verified" in page.text
    svg = ElementTree.fromstring((tmp_path / "site/figures/immigration/themarginoferror/green-card-grants.svg").read_text())
    points = [n for n in svg.iter() if n.get("class") == "immigration-point"]
    assert len(points) == 75 and {int(p.get("data-year")) for p in points} == set(range(2000, 2025))
    assert not any(p.get("data-year") == "2025" for p in points)
    stock_row = next(r for r in raw if r["series_id"] == "un_stock:USA:CHN")
    assert stock_row["fiscal_period_start"] == stock_row["fiscal_period_end"] == ""
    assert stock_row["observation_date"] == "2000-07-01"


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
