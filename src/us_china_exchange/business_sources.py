"""Manually reviewed business-presence aggregates, not bilateral flows."""

import io
import json
import math
import re
import zipfile
from pathlib import PurePosixPath

import xlrd
from openpyxl import load_workbook

from .language_sources import row, series, source


BEA_CURRENT = "https://www.bea.gov/sites/default/files/2025-08/selected-mofas-cntry.xls"
BEA_ARCHIVES = {
    2000: "https://apps.bea.gov/international/zip/USDIA2000revised.ZIP",
    2001: "https://apps.bea.gov/international/zip/USDIA2001revised.zip",
    2002: "https://apps.bea.gov/international/zip/USDIA2002revised.zip",
    2003: "https://apps.bea.gov/international/zip/usdia2003revised.zip",
    2004: "https://apps.bea.gov/international/zip/usdia2004revised.zip",
    2005: "https://apps.bea.gov/international/zip/USDIA2005revised.zip",
    2006: "https://apps.bea.gov/international/zip/USDIA2006revised.zip",
    2007: "https://apps.bea.gov/international/zip/USDIA2007revised.zip",
    2008: "https://apps.bea.gov/international/pdf/usdia_2008r/USDIA_08R.zip",
}
PARENT_BOOKS = {
    2009: "https://apps.bea.gov/international/xls/usdia_2009r/Part%20I%20K1-K2.xls",
    2014: "https://apps.bea.gov/international/xls/usdia2014r/PartI-K1-K2.xls",
    2019: "https://apps.bea.gov/international/xls/usdia2019r/PartI-K1-K2.xls",
}
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ONS_DATA = "https://www.ons.gov.uk/file?uri=/businessindustryandtrade/internationaltrade/datasets/ukoutwardforeignaffiliatestatisticsofats/2019/ofatspublicationfinal.xlsx"
ONS_COVERAGE = "https://www.ons.gov.uk/aboutus/transparencyandgovernance/freedomofinformationfoi/ukoutwardforeignaffiliatestatisticsofats2015to2025"
SSB_COUNTRIES = "https://data.ssb.no/api/v0/en/table/09827"
SSB_CHINA_QUERY = {
    "query": [
        {"code": "Land", "selection": {"filter": "item", "values": ["CN"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Foretak"]}},
        {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
    ],
    "response": {"format": "json-stat2"},
}


def count_cell(value):
    if value in {"(D)", "D"}:
        return None, "suppressed"
    if value in {"", ":", None}:
        return None, "missing"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value != int(value):
        raise ValueError("Invalid business entity count")
    return int(value), "observed"


def country_counts(sheets, title):
    found = {}
    for sheet in sheets:
        if sheet.name.lower().startswith(("contents", "footnotes")):
            continue
        heading = " ".join(str(v) for i in range(min(sheet.nrows, 15)) for v in sheet.row_values(i))
        if title not in heading:
            continue
        parent_header = any(" ".join(str(sheet.cell_value(i, 1)).split()).lower() == "all industries"
                            for i in range(min(15, sheet.nrows)))
        affiliate_header = re.search(r"number\s+of\s+affiliates", heading, re.I)
        if not (parent_header if title == "Number of U.S. Parents" else affiliate_header):
            raise ValueError("Business count column definition changed")
        for i in range(sheet.nrows):
            label = str(sheet.cell_value(i, 0)).strip()
            if label in {"China", "Europe"}:
                if label in found:
                    raise ValueError("Ambiguous business country row")
                found[label] = count_cell(sheet.cell_value(i, 1))
    if set(found) != {"China", "Europe"}:
        raise ValueError("Missing China/Europe business-count rows")
    return found


def parse_norway(data):
    if (data.get("source") != "Statistics Norway" or data.get("class") != "dataset"
            or data.get("extension", {}).get("px", {}).get("tableid") != "09827"
            or data.get("id") != ["Land", "ContentsCode", "Tid"]
            or data.get("size", [])[:2] != [1, 1]):
        raise ValueError("Norwegian subsidiary dataset identity changed")
    dimensions = data["dimension"]
    if (dimensions["Land"]["category"]["index"] != {"CN": 0}
            or dimensions["ContentsCode"]["category"]["index"] != {"Foretak": 0}
            or dimensions["ContentsCode"]["category"]["unit"]["Foretak"] != {
                "base": "enterprises", "decimals": 0}):
        raise ValueError("Norwegian country, counting unit or measure changed")
    years = dimensions["Tid"]["category"]["index"]
    if (not years or data["size"] != [1, 1, len(years)]
            or not isinstance(data["value"], list) or len(data["value"]) != len(years)
            or set(years.values()) != set(range(len(years))) or data.get("status")):
        raise ValueError("Norwegian periods or source flags require review")
    return [(int(year), *count_cell(data["value"][position])) for year, position in sorted(years.items())]


def norwegian_affiliates(client):
    body, asset = client.post_json(SSB_COUNTRIES, SSB_CHINA_QUERY)
    data = json.loads(body)
    points = parse_norway(data)
    definitions = {"ssb_norway:china": series(
        "Norway", "controlled_enterprises", "enterprises",
        "Subsidiary enterprises in China, separately from Hong Kong and Macao, under direct or indirect Norwegian control; all industries",
        "annual", "reference year",
        "Statistics Norway's own complete country history. All-industry coverage is broader than the "
        "old Eurostat B-S except O series; those values are preserved separately, not spliced. "
        "Counts are subsidiary enterprises, not unique Norwegian parents or physical offices.")}
    sources = {"ssb_09827": source(
        "Statistics Norway", "Table 09827; updated " + data["updated"], [asset],
        "Public API POST: Land=CN; ContentsCode=Foretak; Tid=all; all-industry country table",
        " ".join(data.get("note", [])) + " Hong Kong and Macao are separately coded countries. "
        "The original Eurostat population is not silently extended with this broader population.")}
    observations = [row("ssb_norway:china", year, value, "ssb_09827", status,
                        "Direct Statistics Norway all-industry country count, not a subset allocated from Asia.",
                        "ssb:09827:CN:all_industries") for year, value, status in points]
    return definitions, observations, sources


def collect_business(client):
    definitions, observations, sources = {}, [], {}
    for region, label in [("china", "United States")]:
        definitions["bea_affiliates:" + region] = series(
            label, "majority_owned_affiliates", "affiliates",
            f"Foreign affiliates in {'mainland China, excluding Hong Kong and Macau' if region == 'china' else 'BEA-defined Europe, not EU27'}; combined U.S.-parent ownership over 50%",
            "annual", "fiscal ending year",
            "Entities, not unique parent companies, offices or storefronts. U.S. parents are U.S.-resident, "
            "not necessarily ultimately U.S.-owned. Includes holding companies. Nonbank coverage before 2009; "
            "reporting cutoffs $7m through 2003, $10m in 2004-2008, $25m from 2009. "
            "Counts exclude benchmark-exempt affiliates. Lines break at benchmark regimes.")
        definitions["bea_parents:" + region] = series(
            label, "parent_companies", "U.S. parents",
            "Distinct U.S.-resident parent companies with affiliates in China; at least 10% foreign-affiliate ownership; BEA reporting exclusions apply",
            "benchmark", "fiscal ending year",
            "Benchmark observations only, not an annual census. A parent is counted once per host country/region, "
            "but can appear in both China and Europe: never add these counts. Country attribution and reporting "
            "exclusions follow each benchmark. Not restricted to ultimately American-owned companies. "
            "Do not substitute majority-owned affiliate counts for parent counts.")
    for year, url in BEA_ARCHIVES.items():
        body, asset = client.get(url)
        archive = zipfile.ZipFile(io.BytesIO(body))
        members = [n for n in archive.namelist()
                   if re.fullmatch(r"tab3a1[a-z]?(?:_new)?\.xls", PurePosixPath(n).name.lower())]
        if not members:
            raise ValueError(f"Missing historical majority-owned affiliate tables: {year}")
        sheets = [sheet for n in members for sheet in xlrd.open_workbook(file_contents=archive.read(n)).sheets()]
        counts = country_counts(sheets, "Selected Data for Foreign Affiliates")
        source_id = f"bea_affiliates_{year}"
        sources[source_id] = source(
            "U.S. Bureau of Economic Analysis", f"Revised {year} operations; historical benchmark regime",
            [asset], "Table III.A1, Number of affiliates; " + ", ".join(members),
            "Majority-owned nonbank affiliates; benchmark-exempt entities excluded. "
            "Not comparable across the 2004 reporting-regime or 2009 banking/threshold changes.")
        for region, label in [("china", "China")]:
            value, status = counts[label]
            observations.append(row("bea_affiliates:" + region, year, value, source_id, status,
                                    f"Nonbank affiliate count; {'1999' if year < 2004 else '2004'} benchmark reporting regime.",
                                    "bea_affiliates:" + ("1999" if year < 2004 else "2004")))
        if year == 2004:
            parent = [n for n in archive.namelist() if PurePosixPath(n).name.lower() == "tab1m2.xls"]
            if len(parent) != 1:
                raise ValueError("Missing 2004 parent-company country table")
            parent_sheets = xlrd.open_workbook(file_contents=archive.read(parent[0])).sheets()
            counts = country_counts(parent_sheets, "Number of U.S. Parents")
            sources["bea_parents_2004"] = source(
                "U.S. Bureau of Economic Analysis", "Revised 2004 benchmark", [asset],
                parent[0] + "; Table I.M2; All industries",
                "U.S. parents counted once in each country where they have affiliates. Reporting exclusions apply; "
                "the 2004 benchmark changed the affiliate reporting cutoff from $7m to $10m.")
            for region, label in [("china", "China")]:
                value, status = counts[label]
                observations.append(row("bea_parents:" + region, 2004, value, "bea_parents_2004", status,
                                        comparability="bea_parents:2004"))
    body, asset = client.get(BEA_CURRENT)
    book = xlrd.open_workbook(file_contents=body)
    for year in range(2009, 2024):
        sheet = book.sheet_by_name(str(year))
        header = " ".join(str(v) for i in range(5) for v in sheet.row_values(i))
        if str(year) not in header or "$25 million" not in header:
            raise ValueError("BEA annual year or affiliate reporting threshold changed")
        counts = country_counts([sheet], "Majority-Owned Foreign Affiliates")
        source_id = f"bea_affiliates_{year}"
        sources[source_id] = source(
            "U.S. Bureau of Economic Analysis", f"2009-2023 selected-data workbook; {year} fiscal year",
            [asset], f"Sheet {year}; China/Europe rows; Number of affiliates above $25m",
            "Majority-owned affiliates across all industries. Assets, sales or net income/loss must exceed $25m. "
            "Not all small businesses or physical offices; includes holding entities. "
            "2014 and 2019 benchmarks can change coverage: their boundaries are not connected.")
        for region, label in [("china", "China")]:
            value, status = counts[label]
            if year == 2023 and value is not None:
                status = "provisional"
            observations.append(row("bea_affiliates:" + region, year, value, source_id, status,
                                    "All-industry majority-owned affiliate count above $25m; "
                                    + ("preliminary source year." if year == 2023 else "revised source year."),
                                    "bea_affiliates:" + str(2019 if year >= 2019 else 2014 if year >= 2014 else 2009)))
    for year, url in PARENT_BOOKS.items():
        body, asset = client.get(url)
        book = xlrd.open_workbook(file_contents=body)
        counts = country_counts(book.sheets(), "Number of U.S. Parents")
        source_id = f"bea_parents_{year}"
        sources[source_id] = source(
            "U.S. Bureau of Economic Analysis", f"Revised {year} benchmark", [asset],
            "Table I.K2; Number of U.S. parents; country rows, All industries",
            "Unique within each host region, not across regions; includes parents with minority-owned affiliates. "
            "Benchmark reporting exclusions and coverage apply; these points are not an annual series.")
        for region, label in [("china", "China")]:
            value, status = counts[label]
            observations.append(row("bea_parents:" + region, year, value, source_id, status,
                                    comparability=f"bea_parents:{year}"))
    definitions["eurostat_affiliates:china"] = series(
        "EU27 (current members)", "controlled_enterprises", "enterprises",
        "China except Hong Kong; ultimately controlled from fixed EU27_2020 membership, excluding the UK; market producers NACE B-S except O",
        "annual", "reference year",
        "Eurostat enterprise units, not unique European parents or all Europe. Macao is a separate partner. "
        "Not matched to BEA's size cutoff, U.S.-resident parent basis or consolidation. "
        "EBS methodology changes from 2021; do not join across that boundary or treat confidential cells as zero.")
    definitions["eurostat_historical_eu:china"] = series(
        "EU27 (2007 members)", "controlled_enterprises", "enterprises",
        "China except Hong Kong; EU27_2007 control, including the UK and excluding Croatia",
        "annual", "reference year",
        "Historical EU membership, not the current EU27. NACE Rev. 1.1 through 2009 and Rev. 2 from 2010; "
        "both classification and membership boundaries remain disconnected. No splice into current-membership counts.")
    definitions["eurostat_uk:china"] = series(
        "United Kingdom", "controlled_enterprises", "enterprises",
        "UK-controlled enterprises in China; Eurostat NACE B-S except O through 2017, ONS total published activity in 2018-2019",
        "annual", "reference year",
        "Eurostat historical UK series and revised ONS 2018/2019 estimates. Source and sector boundary in 2018 is disconnected; "
        "ONS total activity includes agriculture. The 2018 China count agrees across both sources. "
        "No UK outward affiliate statistics from 2020 onward verified; investment flows are not substituted.")
    definitions["eurostat_norway:china"] = series(
        "Norway", "controlled_enterprises", "enterprises",
        "Norwegian-controlled enterprises in China except Hong Kong; NACE B-S except O",
        "annual", "reference year",
        "Norway is outside the EU and is shown separately, not added to an all-Europe total. "
        "Eurostat's 2021 methodology boundary is disconnected.")
    queries = [
        ("fats_out2_r2", "EU27_2020", "eurostat_affiliates:china", None),
        ("fats_out_part", "EU27_2020", "eurostat_affiliates:china", None),
        ("fats_out2", "EU27_2007", "eurostat_historical_eu:china", 2009),
        ("fats_out2_r2", "EU27_2007", "eurostat_historical_eu:china", 2013),
        ("fats_out2_r2", "UK", "eurostat_uk:china", None),
        ("fats_out2_r2", "NO", "eurostat_norway:china", None),
        ("fats_out_part", "NO", "eurostat_norway:china", None),
    ]
    for dataset, geo, sid, end in queries:
        indicator = "indic_sbs=ENT_NR" if dataset == "fats_out_part" else "indic_bp=ENT"
        activity = "nace_r1=C-O_X_L" if dataset == "fats_out2" else "nace_r2=B-S_X_O"
        url = EUROSTAT + dataset + f"?lang=EN&geo={geo}&partner=CN_X_HK&" + indicator + "&" + activity
        body, asset = client.get(url)
        data = json.loads(body)
        points = parse_eurostat(data, dataset, geo)
        source_id = dataset if geo == "EU27_2020" else dataset + "_" + geo
        sources[source_id] = source(
            "Eurostat", data["label"] + "; updated " + data["updated"], [asset],
            f"A; {geo}; CN_X_HK; {activity}; " + indicator,
            "Keep each control geography, membership and activity classification explicit. "
            "Preserve estimated, break and confidential flags; methodology boundaries remain disconnected. "
            "No reconstruction of confidential totals from member-country values.")
        observations.extend(row(sid, year, value, source_id, status,
                                "Eurostat source flags: " + (flag or "none"), comparability)
                            for year, value, status, flag, comparability in points if end is None or year <= end)
    body, asset = client.get(ONS_DATA)
    ons = parse_ons(body)
    sources["ons_2019"] = source(
        "Office for National Statistics", "2018 revised and 2019 estimates; released May 20, 2022", [asset],
        "Table 1 (2018), Table 2 (2019); China row, TOTAL ACTIVITY / ENT",
        "Foreign enterprise counts, not employment or turnover. Total activity includes agriculture; "
        "survey-based estimates. Later ONS vintage supersedes overlapping Eurostat UK values.")
    for year, value, status in ons:
        observations = [r for r in observations if (r["series_id"], r["year"]) != ("eurostat_uk:china", year)]
        observations.append(row("eurostat_uk:china", year, value, "ons_2019", status,
                                "ONS total-activity enterprise estimate, including agriculture; 2018 revised.",
                                "ons:uk:total_activity:2018_2019"))
    _, asset = client.get(ONS_COVERAGE)
    sources["ons_coverage"] = source(
        "Office for National Statistics", "July 15, 2025 disclosure; checked with current dataset listing", [asset],
        "Response 2a: outward affiliate statistics unavailable from 2020",
        "Do not substitute new inward-affiliate statistics or FDI investment values for UK-controlled enterprises in China.")
    # The original methodology documents are retained as provenance, not redistributed.
    for name, url in [
        ("bea_current_notes", "https://www.bea.gov/international/usdia2023p-info"),
        ("bea_release", "https://www.bea.gov/news/2025/activities-us-multinational-enterprises-2023"),
        ("bea_geography", "https://apps.bea.gov/international/bp_web/geographic_area_definitions.pdf"),
        ("eurostat_methods", "https://ec.europa.eu/eurostat/cache/metadata/en/fats_out_sims.htm"),
    ]:
        _, asset = client.get(url)
        sources[name] = source("BEA" if name.startswith("bea") else "Eurostat",
                               "Reviewed source definitions", [asset], "Definitions and source coverage")
    norway_definitions, norway_observations, norway_sources = norwegian_affiliates(client)
    definitions.update(norway_definitions)
    observations.extend(norway_observations)
    sources.update(norway_sources)
    coverage = []
    for sid in definitions:
        selected = [r for r in observations if r["series_id"] == sid]
        actual = [str(r["year"]) for r in selected if r["value"] is not None]
        confidential = [str(r["year"]) for r in selected if r["status"] == "suppressed"]
        coverage.append({"id": sid, "status": "benchmark_only" if sid.startswith("bea_parents") else "annual",
                         "description": "Verified values: " + ", ".join(actual) +
                         (". Confidential: " + ", ".join(confidential) if confidential else "") +
                         ". All series concern businesses in China; definitions and gaps are retained."})
    return {
        "version": 1, "series": definitions,
        "observations": sorted(observations, key=lambda r: (r["series_id"], r["year"])),
        "sources": sources,
        "coverage": coverage,
        "context": {
            "question": "How has U.S. and European business presence in China changed over time?",
            "interpretation": "Company counts, affiliate entities and branch locations are distinct. U.S. parents and ultimately EU-controlled enterprises are not matched ownership populations; BEA and Eurostat levels must not be used to rank otherwise comparable business presence.",
            "geography": "China is the host in every chart. European coverage includes current EU27, a separately labelled historical EU membership group, the United Kingdom and Norway. These are not summed into an all-Europe total; Switzerland and other European origins remain outside verified coverage.",
            "rights": "Publish aggregate statistics and original charts only; raw workbooks and reports remain local. Sources and retrieval checksums accompany every observation.",
            "release_timing": "As checked October 22, 2026, BEA's latest activity release covers 2023. The published schedule puts the 2024 activity release on November 20, 2026; no 2024 value is inferred.",
        },
    }


def parse_eurostat(data, dataset, geo="EU27_2020"):
    indicator = "indic_sbs" if dataset == "fats_out_part" else "indic_bp"
    activity = {"nace_r1": "C-O_X_L"} if dataset == "fats_out2" else {"nace_r2": "B-S_X_O"}
    wanted = {"freq": "A", **activity, indicator: "ENT" if indicator == "indic_bp" else "ENT_NR",
              "partner": "CN_X_HK", "geo": geo}
    if data.get("extension", {}).get("id", "").lower() != dataset or set(data["id"]) != set(wanted) | {"time"}:
        raise ValueError("Eurostat business dataset identity changed")
    for name, code in wanted.items():
        if data["dimension"][name]["category"]["index"] != {code: 0} or data["size"][data["id"].index(name)] != 1:
            raise ValueError("Eurostat returned a different geography, population or measure")
    times = data["dimension"]["time"]["category"]["index"]
    if not times or len(times) != data["size"][data["id"].index("time")]:
        raise ValueError("Eurostat time axis does not reconcile")
    result, segment = [], 0
    for year, position in sorted(times.items()):
        flag = data.get("status", {}).get(str(position), "")
        flags = set(re.sub(r"[|\s]", "", flag))
        if flags - set("Cbdeipru"):
            raise ValueError("Unknown Eurostat business observation flag")
        value = data.get("value", {}).get(str(position))
        if "C" in flags:
            value, status = None, "suppressed"
        elif value is None:
            status = "missing"
        else:
            value, status = count_cell(value)
            status = "provisional" if "p" in flags else "estimated" if flags & {"e", "i"} else "low_reliability" if "u" in flags else status
        if "b" in flags or "d" in flags:
            segment += 1
        comparability = f"{dataset}:{geo}:{segment}"
        if "d" in flags:
            comparability += ":" + year
        result.append((int(year), value, status, flag, comparability))
    return result


def parse_ons(body):
    book = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    result = []
    for year, name in [(2018, "Table 1"), (2019, "Table 2")]:
        rows = list(book[name].iter_rows(min_col=1, max_col=4, values_only=True))
        if str(year) not in str(rows[0][0]) or rows[8][1] != "TOTAL ACTIVITY" or rows[9][1] != "ENT":
            raise ValueError("ONS year, sector total or enterprise-count column changed")
        matches = [r for r in rows if r[0] == "China"]
        if len(matches) != 1:
            raise ValueError("ONS China row missing or ambiguous")
        value, status = count_cell("(D)" if matches[0][1] == "C" else matches[0][1])
        result.append((year, value, "estimated" if value is not None else status))
    return result
