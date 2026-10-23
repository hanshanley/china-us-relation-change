import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from us_china_exchange.model import change
from us_china_exchange.render import svg_chart
from us_china_exchange.tourism_backfill import (
    parse_early_hong_kong, parse_early_macau, parse_hong_kong_profile, parse_macau_months, parse_top_ten,
)


ROOT = Path(__file__).resolve().parents[1]


def test_early_macau_uses_residence_totals_not_mode_counts_shares_or_nationality():
    header = ("TABLE 1 : VISITOR ARRIVALS BY PLACE OF RESIDENCE\n"
              "2001 2002 2001 2002 2001 2002 2001 2002")
    row = ("US  51 379  50 170  16 998  20 850  5 230  5 884  73 607  0.72  76 904  0.67  4.48\n"
           "Estados Unidos da America\nUnited States of America")
    assert parse_early_macau(header, row) == {2001: 73607, 2002: 76904}
    with pytest.raises(ValueError, match="residence table"):
        parse_early_macau(header.replace("PLACE OF RESIDENCE", "NATIONALITY"), row)
    with pytest.raises(ValueError, match="reconcile"):
        parse_early_macau(header, row.replace("76 904", "86 648"))
    with pytest.raises(ValueError, match="counts"):
        parse_early_macau(header, row.replace("50 170", "50 17"))
    with pytest.raises(ValueError, match="U.S. residence"):
        parse_early_macau(header, row.replace("United States of America", "Canada"))


def test_early_hong_kong_preserves_seven_digit_count_and_residence_columns():
    plain = (
        "Visitor Arrivals by Country/Territory of Residence\n"
        "1992 1997 1998 1999 2000 2001 2002\n"
        "United States of 694 290 861 217 828 326 858 925 966 008 935 717 1 000 844\nAmerica")
    assert parse_early_hong_kong(plain) == {2000: 966008, 2001: 935717, 2002: 1000844}
    with pytest.raises(ValueError, match="digit grouping"):
        parse_early_hong_kong(plain.replace("1 000 844", "1 844"))
    with pytest.raises(ValueError, match="year columns"):
        parse_early_hong_kong(plain.replace("2002", "2003"))


def test_hong_kong_profile_reads_hong_kong_not_macau_or_package_tour_counts():
    plain = (
        "MARKET PROFILE : U.S.A.\nTotal i) 171 1,777 93,814 147,941 162,460 82,121 7.4%\n"
        "Arrivals to Hong Kong 1,365 25,987 596,958 884,261 1,026,030 552,528 12.9%\n"
        "Total package tours 0 0 517 2,688 2,765 1,103")
    assert parse_hong_kong_profile(plain)[-1] == 552528
    with pytest.raises(ValueError, match="another country"):
        parse_hong_kong_profile(plain.replace("U.S.A.", "CANADA"))
    with pytest.raises(ValueError, match="six-column"):
        parse_hong_kong_profile(plain.replace(" 552,528", " unavailable"))


def test_macau_monthly_and_ytd_columns_allow_different_source_market_ranks():
    halves = [
        "2026 Aug\nOther market 30,738\nRepublic of Korea\n"
        "Country label 11,713\nUnited States of America\n(-0.4)\n0.3",
        "2026 Jan - Aug\nOther market 143,174\nThailand\n"
        "Other market 110,543\nIndonesia\nCountry label 109,693\nUnited States of America\n(+5.5)\n0.4"]
    assert parse_top_ten(halves, 2026, 8) == {"monthly": 11713, "ytd": 109693}
    missing = [halves[0].replace("United States of America", "Another country"), halves[1]]
    assert parse_top_ten(missing, 2026, 8) == {"ytd": 109693}
    with pytest.raises(ValueError, match="period caption"):
        parse_top_ten(halves[::-1], 2026, 8)
    with pytest.raises(ValueError, match="exceed"):
        parse_top_ten([halves[0].replace("11,713", "200,000"), halves[1]], 2026, 8)
    with pytest.raises(ValueError, match="ambiguous"):
        parse_top_ten([halves[0] + "\n1\nUnited States of America", halves[1]], 2026, 8)


def test_hong_kong_recovery_keeps_population_break_and_matched_halves():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    hk = [r for r in rows if r["source_id"] == "hktb"]
    annual = {r["year"]: r for r in hk if r["frequency"] == "annual"}
    assert set(annual) == set(range(2000, 2026))
    assert annual[2002]["value"] == 1000844
    assert annual[2023]["value"] == 596958
    assert change(annual[2025], annual[2020])["reason"] == "Definitions or periods differ"
    chart = BeautifulSoup(svg_chart(hk), "html.parser")
    assert "Population-definition breaks: 2023" in chart.get_text(" ", strip=True)
    assert chart.select_one(".data-line")["d"].count("M") == 2
    assert "Definitions differ" in svg_chart(hk, indexed=True)
    partial = {r["year"]: r for r in hk if r["frequency"] == "ytd"}
    assert {y: r["value"] for y, r in partial.items()} == {2025: 489417, 2026: 552528}
    assert change(partial[2026], partial[2025])["absolute"] == 63111


def test_complete_macau_profile_fills_a_top_ten_omission_without_subtraction():
    plain = "VISITOR ARRIVALS FROM U.S.A.\n" + "\n".join(
        month + " 3,409 6,427 1,405 11,241 12.1% 1,214"
        for month in ("Jan", "Feb", "Mar", "Apr", "May", "Jun"))
    assert parse_macau_months(plain)[5] == 11241
    with pytest.raises(ValueError, match="reconcile"):
        parse_macau_months(plain.replace("May 3,409", "May 3,410"))
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    may = next(r for r in rows if r["source_id"] == "macau_tourism"
               and r["period"] == "2025-05" and r["frequency"] == "monthly")
    assert may["value"] == 11241 and "monthly profile" in may["source_vintage"]


def test_macau_latest_month_and_matching_cumulative_counts_are_not_confused():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    selected = {(r["year"], r["frequency"]): r for r in rows
                if r["source_id"] == "macau_tourism" and r["period"].endswith("-08")}
    assert {k: r["value"] for k, r in selected.items()} == {
        (2025, "monthly"): 11755, (2025, "ytd"): 104008,
        (2026, "monthly"): 11713, (2026, "ytd"): 109693}
    assert change(selected[2026, "ytd"], selected[2025, "ytd"])["absolute"] == 5685
