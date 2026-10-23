import json
from pathlib import Path

import pytest

from us_china_exchange.contact_backfill import parse_hktdc, parse_nces
from us_china_exchange.sources import SOURCE_POLICIES


ROOT = Path(__file__).resolve().parents[1]


def test_government_student_columns_are_counts_and_academic_ending_years():
    records = [
        ["Place", "1999-2000", "", "2000-01", "", "2016-17", ""],
        ["China", 54466, 10.6, 59939, 10.9, 350755, 32.5],
        ["Hong Kong", 7545, 1.5, 7627, 1.4, 7547, .7],
    ]
    assert parse_nces(records) == {
        ("CHN", 2000): 54466, ("CHN", 2001): 59939, ("CHN", 2017): 350755,
        ("HKG", 2000): 7545, ("HKG", 2001): 7627, ("HKG", 2017): 7547}
    records[1][1] = "---"
    with pytest.raises(ValueError, match="missingness"):
        parse_nces(records)
    records[0][1] = "1999-2001"
    with pytest.raises(ValueError, match="boundary"):
        parse_nces(records)


def test_hong_kong_parser_does_not_substitute_continental_totals_or_residence_counts():
    plain = ("8.2 Tourism Statistics\n2023\n2024\n2025\n"
             "Number of US natioanls visiting Hong Kong\n596,958\n884,262\n1,026,030\n"
             "Number of North and Latin American nationals visiting Hong Kong\n914,362\n1,361,674\n1,581,058\n"
             "Source: Hong Kong Tourism Board\n8.3 Bilateral Investment")
    assert parse_hktdc(plain) == {2023: 596958, 2024: 884262, 2025: 1026030}
    with pytest.raises(ValueError, match="nationality"):
        parse_hktdc(plain.replace("US natioanls", "US residents"))
    with pytest.raises(ValueError, match="years"):
        parse_hktdc(plain.replace("2025", "2026"))


def test_frozen_backfills_have_full_inbound_histories_without_accessing_restricted_iie():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    for geo in ("CHN", "HKG"):
        selected = [r for r in rows if r["origin"] == geo and r["destination"] == "USA"
                    and r["measure"] == "international_students" and r["frequency"] == "annual"]
        assert {r["year"] for r in selected} == set(range(2000, 2026))
        assert all(r["source_url"].startswith(("https://nces.ed.gov/", "https://legacy.export.gov/"))
                   for r in selected if r["year"] < 2018)
        assert all(r["period_basis"] == "academic" for r in selected)
    assert SOURCE_POLICIES["iie"]["automatic_retrieval"] is False
    moe = [r for r in rows if r["source_id"] == "moe"]
    assert {r["year"] for r in moe} == {2011, 2012, 2014, 2016, 2018}
    assert all(r["period_basis"] == "reporting" and r["period_start"] is None and r["period_end"] is None
               and "degree and non-degree" in r["definition"] for r in moe)
    hk = {r["year"]: r for r in rows if r["source_id"] == "hktb"}
    assert hk[2023]["value"] == 596958
    assert all("nationality" in r["definition"] and "residence" in r["definition"] for r in hk.values())


def test_air_half_years_use_direct_filters_not_subtraction_of_rounded_totals():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    selected = {(r["destination"], r["year"]): r for r in rows
                if r["source_id"] == "ntto_siat" and r["frequency"] == "ytd"}
    assert {k: r["value"] for k, r in selected.items()} == {
        ("CHN", 2025): 442000, ("CHN", 2026): 474000,
        ("HKG", 2025): 304000, ("HKG", 2026): 251000}
    assert all(r["period_start"].endswith("-01-01") and r["period_end"].endswith("-06-30")
               and "explicit Q1-Q2 selection" in r["notes"] for r in selected.values())
