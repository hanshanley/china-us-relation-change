"""Manual review of official green-card tables; never infer migration from visits."""

import io
import zipfile
from pathlib import PurePosixPath

import xlrd
from openpyxl import load_workbook

from .language_sources import row, series, source


ASSETS = {
    2004: "https://ohss.dhs.gov/sites/default/files/2023-12/LPR2004_2.zip",
    2014: "https://ohss.dhs.gov/sites/default/files/2023-12/YRBK%25202014%2520LPR%2520Excel%2520Final_0.zip",
    2024: "https://ohss.dhs.gov/system/files/2026-06/2026_0604_ohss_yearbook_lawful_permanent_residents_fy2024.xlsx",
    2025: "https://ohss.dhs.gov/system/files/2026-06/2026_0604_ohss_legal-immigration-adjustment-of-status-fy-2025q4.xlsx",
}
COUNTRIES = {"China, People's Republic": "CHN", "Hong Kong": "HKG", "Macau": "MAC"}
UN_STOCK = "https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx"
STOCK_YEARS = [2000, 2005, 2010, 2015, 2020, 2024]
STOCK_PAIRS = {("CHN", "USA"): "B", ("HKG", "USA"): "B",
               ("USA", "CHN"): "C R", ("USA", "HKG"): "B R"}


def parse_stock(records):
    header = records[10]
    if (header[4], header[6]) != ("Location code of destination", "Location code of origin"):
        raise ValueError("UN destination/origin identity columns changed")
    if [str(value) for value in header[9:15]] != [str(y) for y in STOCK_YEARS]:
        raise ValueError("UN both-sexes benchmark columns changed")
    codes = {156: "CHN", 344: "HKG", 446: "MAC", 840: "USA"}
    values = {}
    for record in records[11:]:
        pair = codes.get(record[6]), codes.get(record[4])
        if pair not in STOCK_PAIRS:
            continue
        if pair in values or record[3] != STOCK_PAIRS[pair]:
            raise ValueError("UN bilateral population is ambiguous or its data type changed")
        values[pair] = [count(value) for value in record[9:15]]
    if set(values) != set(STOCK_PAIRS):
        raise ValueError("UN reviewed bilateral stock coverage incomplete")
    return values


def stock(client):
    content, asset = client.get_public_download(UN_STOCK)
    records = list(load_workbook(io.BytesIO(content), read_only=True, data_only=True)["Table 1"].values)
    definitions, observations = {}, []
    labels = {("CHN", "USA"): "China-born in the U.S.", ("HKG", "USA"): "Hong Kong-born in the U.S.",
              ("USA", "CHN"): "U.S. citizens in mainland China", ("USA", "HKG"): "U.S.-born in Hong Kong"}
    for pair, values in parse_stock(records).items():
        origin, destination = pair
        sid = f"un_stock:{origin}:{destination}"
        definition = series(labels[pair], "migrant_stock", "estimated residents",
                            labels[pair] + "; UN destination-specific population definition",
                            "benchmark", basis="mid-year July 1",
                            notes="Estimated resident stock, not annual immigration or permanent-residency grants. "
                            "UN type C uses foreign citizenship; B uses foreign birth; R includes refugee adjustments. "
                            "The U.S. destination population includes the territories specified in UN coverage note 36.")
        definitions[sid] = dict(definition, origin=origin, destination=destination, data_type=STOCK_PAIRS[pair])
        for year, (value, status) in zip(STOCK_YEARS, values):
            observations.append(row(sid, year, value, "un_stock_2024",
                                    "estimated" if status == "observed" else status,
                                    "UN 2024 revision; 1 July benchmark. Not an annual flow.", sid))
    return definitions, observations, source(
        "United Nations DESA, Population Division", "International Migrant Stock 2024",
        [asset], "Table 1; both sexes combined; destination/origin codes 156, 344 and 840; mid-year 2000–2024",
        "CC BY 3.0 IGO. Adapted selected numerical aggregates; UN country codes and population definitions retained. "
        "Mainland China uses foreign-citizenship estimates (C R), Hong Kong foreign-born estimates (B R), "
        "and the U.S. foreign-born estimates (B). Benchmark stocks include UN estimates, not new yearly arrivals.")


def count(value, rounded=False):
    if isinstance(value, str):
        value = value.strip()
        if value == "D":
            return None, "suppressed"
        if value in {"", "N/A"}:
            return None, "missing"
        if value == "-":
            return 0, "rounded" if rounded else "observed"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or int(value) != value:
        raise ValueError("Invalid reported immigration count")
    if rounded and value % 10:
        raise ValueError("OHSS rounded count is not a multiple of ten")
    return int(value), "rounded" if rounded else "observed"


def parse_birth(records, first, last, rounded=False):
    text = " ".join(str(v) for r in records[:5] for v in r if v).lower()
    if "country of birth" not in text or not any(s in text for s in ["immigrants admitted", "permanent resident"]):
        raise ValueError("Immigration table must count permanent-resident grants by birthplace")
    header = next(r for r in records if str(r[0]).strip().lower() == "region and country of birth")
    columns = {int(v): i for i, v in enumerate(header) if isinstance(v, (float, int)) and 1980 <= v <= 2100}
    if not set(range(first, last + 1)) <= columns.keys():
        raise ValueError("Immigration history year columns incomplete")
    if rounded and "nearest 10" not in " ".join(str(v) for r in records for v in r if v).lower():
        raise ValueError("OHSS rounding disclosure changed")
    result = []
    for name, geo in COUNTRIES.items():
        matches = [r for r in records if str(r[0]).strip() == name]
        if len(matches) != 1:
            raise ValueError("Immigration country row missing or ambiguous")
        result += [(geo, year, *count(matches[0][columns[year]], rounded)) for year in range(first, last + 1)]
    return result


def parse_latest(records):
    text = " ".join(str(v) for r in records[:8] for v in r if v).lower()
    if "country of nationality" not in text or "fiscal year 2025" not in text:
        raise ValueError("Latest immigration nationality/year identity changed")
    if list(records[5][:12]) != ["Region and country of nationality", "Total", None, None, None, None,
                                  "Adjustments of status", None, None, None, None, "New arrivals"]:
        raise ValueError("Latest immigration admission-type columns changed")
    if [records[6][i] for i in (1, 6, 11)] != ["Total"] * 3:
        raise ValueError("Use annual reported totals, not selected quarters")
    matches = [r for r in records if str(r[0]).strip() == "China, People's Republic"]
    if len(matches) != 1:
        raise ValueError("Latest China nationality row missing or ambiguous")
    values = {kind: count(matches[0][i], rounded=True)[0]
              for kind, i in [("total", 1), ("adjustments", 6), ("new_arrivals", 11)]}
    if any(v is None for v in values.values()) or abs(values["total"] - values["adjustments"] - values["new_arrivals"]) > 10:
        raise ValueError("Reported admission types do not reconcile within rounding precision")
    return values


def collect(client):
    definitions, observations, sources = {}, [], {}
    for year in (2004, 2014, 2024):
        body, asset = client.get(ASSETS[year])
        if year < 2024:
            archive = zipfile.ZipFile(io.BytesIO(body))
            names = [n for n in archive.namelist() if PurePosixPath(n).name.lower().replace(" ", "") == "table3d.xls"]
            if len(names) != 1:
                raise ValueError("Historical birthplace table missing or ambiguous")
            sheet = xlrd.open_workbook(file_contents=archive.read(names[0])).sheet_by_index(0)
            records = [sheet.row_values(i) for i in range(sheet.nrows)]
            first, last = (2000, 2004) if year == 2004 else (2005, 2014)
        else:
            book = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
            records = list(book["Table 3"].values)
            first, last = 2015, 2024
        sid = f"ohss_birth_{year}"
        sources[sid] = source("U.S. Department of Homeland Security / OHSS", f"{year} Yearbook of Immigration Statistics",
                              [asset], f"Table 3; country of birth; fiscal years {first}-{last}",
                              "Lawful permanent-resident status grants, including new arrivals and adjustments within the U.S. "
                              + ("Published cells rounded to nearest ten." if year == 2024 else "Historical reported counts; older source vintage."))
        for geo, reported_year, value, status in parse_birth(records, first, last, rounded=year == 2024):
            observations.append(row(f"ohss_birth:{geo}", reported_year, value, sid, status,
                                    "Fiscal year ending September 30. " + ("Rounded to nearest ten." if status == "rounded" else ""),
                                    f"ohss_birth:{geo}"))
    for name, geo in COUNTRIES.items():
        definitions[f"ohss_birth:{geo}"] = series(
            {"CHN": "Mainland China-born", "HKG": "Hong Kong-born", "MAC": "Macau-born"}[geo],
            "permanent_resident_grants", "status grants", f"U.S. lawful permanent-resident grants; country of birth: {name}",
            "annual", basis="fiscal ending year", notes="Includes arrivals and adjustments of status; not nationality, ethnicity or a count of new border crossings.")
    body, asset = client.get(ASSETS[2025])
    records = list(load_workbook(io.BytesIO(body), read_only=True, data_only=True)["Table 1A"].values)
    latest = parse_latest(records)
    sources["ohss_nationality_2025"] = source(
        "U.S. Department of Homeland Security / OHSS", "Legal Immigration and Adjustment of Status Report, FY2025 Q4",
        [asset], "Table 1A; China, People's Republic; annual Total columns 2, 7 and 12",
        "Country of nationality, not country of birth. Cells rounded to nearest ten; totals may differ due to rounding. Do not splice into the birthplace history.")
    for kind, label in [("total", "Total grants"), ("new_arrivals", "New arrivals"), ("adjustments", "Adjustments within the U.S.")]:
        key = "ohss_nationality:" + kind
        definitions[key] = series(label, "permanent_resident_grants", "status grants",
                                  "DHS China, People's Republic nationality category; U.S. permanent-resident grants",
                                  "annual", basis="fiscal ending year",
                                  notes="Different population from the birthplace history. Not a visa issuance count.")
        observations.append(row(key, 2025, latest[kind], "ohss_nationality_2025", "rounded",
                                "Fiscal year October 1, 2024–September 30, 2025; rounded to nearest ten.", key))
    stock_definitions, stock_rows, stock_source = stock(client)
    definitions.update(stock_definitions)
    observations.extend(stock_rows)
    sources["un_stock_2024"] = stock_source
    return {
        "version": 1, "series": definitions, "observations": sorted(observations, key=lambda r: (r["series_id"], r["year"])),
        "sources": sources,
        "coverage": [
            {"id": "to_us_birthplace", "status": "available", "description": "China, Hong Kong and Macau birthplace series, FY2000–FY2024; all permanent-resident status grants."},
            {"id": "to_us_nationality", "status": "available", "description": "China nationality category, FY2025 reported annual totals. Hong Kong and Macau are not separately identified in this table."},
            {"id": "from_us", "status": "not_verified", "description": "A comparable annual U.S.-to-mainland-China permanent-residency series has not been verified. All-foreigner visas, residence permits and border crossings are not substitutes."},
            {"id": "bilateral_resident_stocks", "status": "available", "description": "UN bilateral resident estimates in both directions for mainland China and Hong Kong: 2000, 2005, 2010, 2015, 2020 and 2024. Mainland destination uses U.S. citizenship, not U.S. birthplace. These stocks are not immigration flows."},
            {"id": "macau_resident_stock", "status": "not_verified", "description": "The reviewed UN bilateral table does not separately report the U.S.–Macau pair. No zero or allocation from mainland China is inferred."},
        ],
        "context": {"definition": "The OHSS series count grants of U.S. permanent-resident status; the UN series count resident stocks. Neither is a measure of net migration. Grants include adjustments by people already in the United States, not only new physical arrivals. Birthplace is not a departure country.",
                    "periods": "U.S. fiscal years end September 30, not December 31. Birthplace and nationality series remain separate.",
                    "rounding": "FY2015–2024 birthplace counts and FY2025 nationality counts are rounded to the nearest ten. Earlier figures use older, exact-count vintages.",
                    "resident_stocks": "UN stocks refer to 1 July in actual published benchmark years. China destination estimates use foreign citizenship; Hong Kong and U.S. destination estimates use foreign birth. Refugee adjustments are included where flagged R. These are not new immigration or net migration. No annual observations are invented between benchmarks.",
                    "rights": "Selected statistical aggregates and original figures only; no source workbooks are redistributed. UN estimates: United Nations DESA, Population Division, International Migrant Stock 2024, adapted under CC BY 3.0 IGO."},
    }
