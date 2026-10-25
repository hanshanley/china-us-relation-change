import json
from pathlib import Path

import pytest

from us_china_exchange.contact_backfill import (
    parse_cau_history, parse_educationusa_levels, parse_eric_academic_levels,
    parse_eric_country_history, parse_eric_legacy_levels, parse_hktdc, parse_nces, parse_nces_credit,
    parse_uis_digest,
)
from us_china_exchange.sources import SOURCE_POLICIES
from us_china_exchange.model import change


ROOT = Path(__file__).resolve().parents[1]


UIS_DIGEST = (
    "International flows of mobile students / 2008\n"
    "Top five destinations (host countries)\n"
    "China 441,186 1.7 0.4 U.S.A. (110,246), Japan (77,916) 51,038 -390,148 -1.5\n"
    "Hong Kong SAR of China 33,107 20.7 -1 7.3 Australia (13,334), U.S.A. (8,295), Canada (1,110) -2\n"
    "Macao, China 1,324 5.2 2.9 Australia (566), U.S.A. (421), U.K. (165) 12,648 11,324 44.6\n")


def test_uis_digest_selects_bilateral_counts_not_worldwide_totals_or_neighbouring_destinations():
    assert parse_uis_digest(UIS_DIGEST) == {"CHN": 110246, "HKG": 8295, "MAC": 421}
    assert parse_uis_digest(UIS_DIGEST.replace("flows", "\ufb02ows").replace("five", "\ufb01ve")) == {
        "CHN": 110246, "HKG": 8295, "MAC": 421}
    assert parse_uis_digest(UIS_DIGEST.replace("destinations (", "destinations(")) == {
        "CHN": 110246, "HKG": 8295, "MAC": 421}
    for invalid in (
            UIS_DIGEST.replace("/ 2008", "/ 2009"),
            UIS_DIGEST.replace("U.S.A. (421)", "U.S.A. (421) -1"),
            UIS_DIGEST.replace("U.S.A. (8,295)", "U.S.A. (...)"),
            UIS_DIGEST.replace("Macao, China", "Unspecified origin"),
            UIS_DIGEST + UIS_DIGEST.splitlines()[-1] + "\n"):
        with pytest.raises(ValueError):
            parse_uis_digest(invalid)


def test_uis_digest_backfill_preserves_existing_rows_and_a_separate_legacy_comparison(monkeypatch):
    from types import SimpleNamespace
    from us_china_exchange import contact_backfill
    from us_china_exchange.model import key

    fixtures = {
        2006: UIS_DIGEST.replace("2008", "2004").replace("Hong Kong SAR of China", "Hong Kong (China), SAR")
        .replace("110,246", "87,943").replace("8,295", "7,353").replace("(421)", "(374)"),
        2010: UIS_DIGEST,
        2011: UIS_DIGEST.replace("2008", "2009").replace("Hong Kong SAR of China", "China, Hong Kong SAR")
        .replace("Macao, China", "China, Macao SAR").replace("110,246", "124,225")
        .replace("8,295", "8,192").replace("(421)", "(422)"),
    }
    assets = {report["url"]: {"url": report["url"], "sha256": report["sha256"],
                             "retrieved_at": "2026-10-25T00:47:44+00:00"}
              for report in contact_backfill.UIS_DIGESTS.values()}

    def reader(body):
        edition = int(body.getvalue())
        report, plain = contact_backfill.UIS_DIGESTS[edition], fixtures[edition]
        pages = [SimpleNamespace(extract_text=lambda **_: "") for _ in range(203)]
        pages[report["header_page"] - 1] = SimpleNamespace(extract_text=lambda: plain.splitlines()[0])
        pages[report["data_page"] - 1] = SimpleNamespace(
            extract_text=lambda **_: "\n".join(plain.splitlines()[1:]))
        return SimpleNamespace(pages=pages)

    monkeypatch.setattr(contact_backfill, "PdfReader", reader)
    client = SimpleNamespace(get=lambda url: (
        str(next(y for y, r in contact_backfill.UIS_DIGESTS.items() if r["url"] == url)).encode(), assets[url]))
    prior = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
             if not (r["source_id"] == "uis" and r["origin"] in {"HKG", "MAC"}
                     and r["destination"] == "USA" and r["year"] in {2004, 2008, 2009})]
    result = contact_backfill.uis_legacy_student_history(client, prior)
    before, after = {key(r): r for r in prior}, {key(r): r for r in result}
    assert len(after) == len(before) + 6
    assert all(after[k] == r for k, r in before.items())
    additions = [r for k, r in after.items() if k not in before]
    assert {(r["origin"], r["destination"], r["year"], r["value"]) for r in additions} == {
        ("HKG", "USA", 2004, 7353), ("MAC", "USA", 2004, 374),
        ("HKG", "USA", 2008, 8295), ("MAC", "USA", 2008, 421),
        ("HKG", "USA", 2009, 8192), ("MAC", "USA", 2009, 422)}
    current = {r["origin"]: r for r in prior if r["source_id"] == "uis"
               and r["destination"] == "USA" and r["year"] == 2020}
    assert all(r["period_basis"] == "reporting" and r["period_start"] is None and r["period_end"] is None
               and change(r, current[r["origin"]])["reason"] == "Definitions or periods differ" for r in additions)
    assert not any(r["origin"] == "CHN" for r in additions)
    assert all(r["measure"] == "historical_students" and "not independently verified" in r["definition"]
               for r in additions)
    hong_kong = {r["year"]: r for r in additions if r["origin"] == "HKG"}
    assert change(hong_kong[2009], hong_kong[2008])["reason"] == "Definitions or periods differ"
    from us_china_exchange.public_freshness import annual_series
    assert not {r["series_id"] for r in additions} & set(annual_series(result))
    assert contact_backfill.uis_legacy_student_history(client, result) == result
    legacy = [dict(r, series_id=r["series_id"].replace("historical_students", "degree_students"),
                   measure="degree_students", comparability="uis:degree_students:legacy-isced97")
              for r in additions]
    migrated = contact_backfill.uis_legacy_student_history(client, prior + legacy)
    assert len(migrated) == len(prior + legacy)
    fields = ("origin", "destination", "year", "period", "period_basis", "frequency", "unit", "value",
              "source_id", "source_url", "source_vintage", "raw_sha256", "retrieved_at")
    for old in legacy:
        match = next(r for r in migrated if r["measure"] == "historical_students"
                     and r["origin"] == old["origin"] and r["year"] == old["year"])
        assert all(match[field] == old[field] for field in fields)
        assert key(old) not in {key(r) for r in migrated}
    legacy[0]["raw_sha256"] = "unreviewed"
    with pytest.raises(ValueError, match="conflicting provenance"):
        contact_backfill.uis_legacy_student_history(client, prior + legacy)
    additions[0]["value"] += 1
    with pytest.raises(ValueError, match="conflicts"):
        contact_backfill.uis_legacy_student_history(client, result)
    next(iter(assets.values()))["sha256"] = "unreviewed"
    with pytest.raises(ValueError, match="digest changed"):
        contact_backfill.uis_legacy_student_history(client, prior)


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


def test_government_student_country_selection_preserves_separate_taiwan_counts():
    records = [
        ["Place", "1999-2000", "", "2000-01", "", "2016-17", ""],
        ["China", 54466, 10.6, 59939, 10.9, 350755, 32.5],
        ["Hong Kong", 7545, 1.5, 7627, 1.4, 7547, .7],
        ["Taiwan", 29234, 5.7, 28566, 5.2, 21516, 2.0],
    ]
    assert parse_nces(records, (("Taiwan", "TWN"),)) == {
        ("TWN", 2000): 29234, ("TWN", 2001): 28566, ("TWN", 2017): 21516}
    with pytest.raises(ValueError, match="country row"):
        parse_nces(records, (("Macau", "MAC"),))


def test_educationusa_uses_exact_level_counts_not_percentages_visa_totals_or_opt():
    plain = ("Macau Source: 2021 Open Doors Students in U.S. by Academic Level % Number "
             "% Change (2020 to 2021) Undergraduate 61.4% 259 -19.1% Graduate 21.1% 89 3.5% "
             "Non -Degree 0.7% 3 -81.3% OPT 16.8% 71 -12.3% F -80.88%")
    assert parse_educationusa_levels(plain, "Macau") == [259, 89, 3, 71]
    for incorrect in (plain.replace("Macau", "Hong Kong"), plain.replace("2021", "2022"),
                      plain.replace("3 -81.3%", "--- -81.3%"), plain + " OPT 16.8% 71 -12.3%"):
        with pytest.raises(ValueError):
            parse_educationusa_levels(incorrect, "Macau")
    assert parse_educationusa_levels(plain.replace("0.7% 3", "0% 0"), "Macau")[2] == 0


def test_government_mobility_backfill_keeps_credit_enrollment_and_opt_populations_separate():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    for geo, value in (("CHN", 251933), ("HKG", 4841), ("MAC", 351), ("TWN", 14642)):
        enrolled = next(r for r in rows if r["source_id"] == "iie" and r["origin"] == geo
                        and r["destination"] == "USA" and r["measure"] == "enrolled_students"
                        and r["year"] == 2021)
        assert enrolled["value"] == value and enrolled["period"] == "2020/21"
        standard = next(r for r in rows if r["source_id"] == "iie" and r["origin"] == geo
                        and r["destination"] == "USA" and r["measure"] == "enrolled_students"
                        and r["year"] == 2024)
        assert change(standard, enrolled) == {
            "absolute": None, "percent": None, "reason": "Definitions or periods differ"}
        assert "regardless of visa status" in enrolled["definition"]
        credits = [r for r in rows if r["source_id"] == "iie" and r["origin"] == "USA"
                   and r["destination"] == geo and r["measure"] == "study_abroad"]
        assert set(range(2014, 2025)) <= {r["year"] for r in credits}
        assert all(r["source_url"].startswith("https://educationusa.state.gov/")
                   and r["period_basis"] == "academic" for r in credits if 2014 <= r["year"] <= 2017)
    assert next(r["value"] for r in rows if r["source_id"] == "iie" and r["origin"] == "HKG"
                and r["measure"] == "international_students" and r["year"] == 2017) == 7547
    macau = [r for r in rows if r["source_id"] == "iie" and r["origin"] == "MAC"
             and r["measure"] == "international_students"]
    assert {r["year"] for r in macau} == set(range(2000, 2026))


def test_eric_country_levels_preserve_columns_exclude_opt_and_restore_comparable_history():
    header = ("TOTAL UNDERGRADUATE GRADUATE NON-DEGREE OPTIONAL PRACTICAL TRAINING\n"
              "2019/20 2018/19 2019/20\n")
    line = ("China 372,532 148,880 148,160 39.8 -0.5 133,396 137,096 36.8 2.8 "
            "17,235 15,896 4.3 -7.8 70,037 71,380 19.2 1.9")
    previous, current = parse_eric_academic_levels(header + line, "China", 2020)
    assert sum(previous[:3]) == 299511 and sum(current[:3]) == 301152
    assert parse_eric_academic_levels(header + line.replace("39.8", "\u2014"), "China", 2020) == (previous, current)
    assert parse_eric_academic_levels(header + line + "\n" + line, "China", 2020) == (previous, current)
    for invalid in (header.replace("2018/19", "2017/18") + line,
                    header + line.replace("372,532", "372,533"),
                    header + line.replace("148,880", "148 880")):
        with pytest.raises(ValueError):
            parse_eric_academic_levels(invalid, "China", 2020)
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    for geo in ("CHN", "HKG", "MAC", "TWN"):
        history = {r["year"]: r for r in rows if r["origin"] == geo and r["destination"] == "USA"
                   and r["measure"] == "enrolled_students"}
        assert set(history) == set(range(2007, 2026))
        assert change(history[2025], history[2020])["percent"] is not None
        assert change(history[2024], history[2023])["percent"] is None
        assert all(history[y]["source_url"].startswith("https://files.eric.ed.gov/")
                   for y in (2019, 2020, 2022, 2023))


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


def test_legacy_exact_levels_exclude_opt_but_never_treat_unsplit_other_as_enrollment():
    header = "Undergraduate Graduate OPT OPT Other Other Total\n2006/07\n"
    line = "  China, PRC 9,988 14.7 47,968 70.8 7,171 10.6 2,596 3.8 67,723"
    counts = parse_eric_legacy_levels(header + line, "China, PRC", 2007)
    assert counts == [9988, 47968, 2596, 7171]
    assert sum(counts[:3]) == 60552
    later_header = "Undergraduate Graduate Non-Degree OPT OPT Total\n2007/08\n"
    assert parse_eric_legacy_levels(
        later_header + "China 16,450 20.3 53,047 65.4 3,912 4.8 7,718 9.5 81,127",
        "China", 2008) == [16450, 53047, 3912, 7718]
    for invalid in (header.replace("2006/07", "2005/06") + line,
                    header + line.replace("67,723", "67,724"),
                    header + line.replace("2,596", "\u2014"),
                    header + "China, PRC 9,988 14.7 47,968 70.8 9,767 14.4 67,723"):
        with pytest.raises(ValueError):
            parse_eric_legacy_levels(invalid, "China, PRC", 2007)


def test_eric_credit_decade_keeps_reported_zeros_years_and_direction_exact():
    years = list(range(1999, 2009))
    header = "Destination " + " ".join(f"{y-1}/{str(y)[-2:]}" for y in years) + " % Change\n"
    line = "Macau 0 0 5 2 0 0 0 0 3 4 33.3"
    assert parse_eric_country_history(header + line, "Macau", years, destinations=True) == {
        1999: 0, 2000: 0, 2001: 5, 2002: 2, 2003: 0,
        2004: 0, 2005: 0, 2006: 0, 2007: 3, 2008: 4}
    for invalid in (header.replace("2007/08", "2008/09") + line,
                    header + line.replace("5", "\u2014", 1),
                    header + line.replace(" 4 33.3", " 4 999 999 33.3"),
                    header + line + "\n" + line.replace(" 5 ", " 6 ")):
        with pytest.raises(ValueError):
            parse_eric_country_history(invalid, "Macau", years, destinations=True)
    with pytest.raises(ValueError, match="header"):
        parse_eric_country_history(header + line, "Macau", years)


def test_frozen_eric_history_is_complete_without_rewriting_a_conflicting_source_vintage():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    values = {(r["origin"], r["destination"], r["measure"], r["year"]): r
              for r in rows if r["source_id"] == "iie"}
    for geo in ("CHN", "HKG", "MAC", "TWN"):
        credits = [values["USA", geo, "study_abroad", year] for year in range(2000, 2025)]
        assert all(r["value"] is not None and r["period_basis"] == "academic" for r in credits)
        assert all(r["source_url"].startswith("https://files.eric.ed.gov/")
                   for r in credits if r["year"] < 2014 and not (geo == "CHN" and r["year"] == 2008))
        assert values["USA", geo, "study_abroad", 2025]["value"] is None
    assert values["MAC", "USA", "international_students", 2000]["value"] == 297
    assert values["USA", "MAC", "study_abroad", 2000]["value"] == 0
    assert values["USA", "MAC", "study_abroad", 2001]["value"] == 5
    assert values["CHN", "USA", "enrolled_students", 2007]["value"] == 60552
    assert values["MAC", "USA", "enrolled_students", 2007]["value"] == 359
    original = values["TWN", "USA", "enrolled_students", 2013]
    assert original["value"] == 18450
    assert "21867" in original["notes"] and "21897" in original["notes"]
    assert values["TWN", "USA", "international_students", 2013]["value"] == 21897


def test_frozen_backfills_have_full_inbound_histories_without_accessing_restricted_iie():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    for geo in ("CHN", "HKG", "TWN"):
        selected = [r for r in rows if r["origin"] == geo and r["destination"] == "USA"
                    and r["measure"] == "international_students" and r["frequency"] == "annual"]
        assert {r["year"] for r in selected} == set(range(2000, 2026))
        assert all(r["source_url"].startswith(("https://nces.ed.gov/", "https://legacy.export.gov/"))
                   for r in selected if r["year"] < 2018)
        assert all(r["period_basis"] == "academic" for r in selected)
    assert SOURCE_POLICIES["iie"]["automatic_retrieval"] is False
    moe = [r for r in rows if r["source_id"] == "moe"]
    assert set(range(2006, 2017)) | {2018} <= {r["year"] for r in moe}
    assert all(r["period_basis"] == "reporting" and r["period_start"] is None and r["period_end"] is None
               and "degree and non-degree" in r["definition"] for r in moe)
    hk = {r["year"]: r for r in rows if r["source_id"] == "hktb"}
    assert hk[2023]["value"] == 596958
    assert all("nationality" in r["definition"] and "residence" in r["definition"] for r in hk.values())


def test_historical_country_rank_changes_do_not_shift_moe_years():
    countries = ["Japan", "Japan"] + ["US"] * 8
    country_names = {"Japan": "\u65e5\u672c", "US": "\u7f8e\u56fd"}
    plain = " ".join(str(y) for y in range(2006, 2016)) + "\n2 " + " ".join(
        country_names[c] + " " + str(100 + i) for i, c in enumerate(countries))
    plain += "\n3 " + " ".join(country_names["US" if i < 2 else "Japan"] + " " + str(200 + i)
                              for i in range(10)) + "\n4 "
    assert parse_cau_history(plain) == dict(
        [(2006, 200), (2007, 201)] + [(2006 + i, 100 + i) for i in range(2, 10)])
    with pytest.raises(ValueError, match="year columns"):
        parse_cau_history(plain.replace("2015", "2017"))
    with pytest.raises(ValueError, match="ten annual cells"):
        parse_cau_history(plain.replace("\u7f8e\u56fd 109", ""))


def test_nces_credit_count_is_not_a_rank_share_or_out_of_scope_comparison():
    plain = ("top 25 destinations\nAcademic years 1997\u201398 and 2007\u201308\n"
             "China 11 2,116 1.9 5 13,165 5.0 522.2")
    assert parse_nces_credit(plain) == 13165
    with pytest.raises(ValueError, match="periods"):
        parse_nces_credit(plain.replace("2007\u201308", "2008\u201309"))


def test_air_half_years_use_direct_filters_not_subtraction_of_rounded_totals():
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    selected = {(r["destination"], r["year"]): r for r in rows
                if r["source_id"] == "ntto_siat" and r["frequency"] == "ytd"}
    assert {k: r["value"] for k, r in selected.items()} == {
        ("CHN", 2025): 442000, ("CHN", 2026): 474000,
        ("HKG", 2025): 304000, ("HKG", 2026): 251000}
    assert all(r["period_start"].endswith("-01-01") and r["period_end"].endswith("-06-30")
               and "explicit Q1-Q2 selection" in r["notes"] for r in selected.values())
