"""Manual review of education and visitor aggregate republications."""

import io
import re
import unicodedata
from urllib.parse import urljoin

import xlrd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .model import key, observation, validate
from .sources import attach


NCES_HISTORY = [
    "https://nces.ed.gov/programs/digest/d01/dt416.asp",
    "https://nces.ed.gov/programs/digest/d04/tables/dt04_416.asp",
    "https://nces.ed.gov/programs/digest/d07/tables/dt07_406.asp",
    "https://nces.ed.gov/programs/digest/d10/tables/dt10_234.asp",
    "https://nces.ed.gov/programs/digest/d13/tables/dt13_310.20.asp",
    "https://nces.ed.gov/programs/digest/d15/tables/dt15_310.20.asp",
    "https://nces.ed.gov/programs/digest/d17/tables/dt17_310.20.asp",
]
COMMERCE_HISTORY = "https://legacy.export.gov/article?id=China-Education-and-Training"
MOE_HISTORY = [
    (2011, 23292, "https://portal.cscse.edu.cn/lxfwzx/xwdt85/xwdt/2024061911121395575/index.html"),
    (2012, 24583, "https://www.cscse.edu.cn/cscse/sy/xwdt/20130312122011429724/index.html"),
    (2014, 24203, "https://portal.cscse.edu.cn/lxfwzx/xwdt85/xwdt/2024061911124449816/index.html"),
    (2016, 23838, "https://edu.cnr.cn/list/20170301/t20170301_523629310.shtml"),
    (2018, 20996, "https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/201904/t20190412_377692.html"),
]
HKTDC = "https://research.hktdc.com/en/article/MzIwNjY2NTgx"
CAU_HISTORY = "https://libwx.cau.edu.cn/oldweb/gxyxkfz/gqyd/12_qw.pdf"
NCES_CREDIT = "https://nces.ed.gov/pubs2010/2010028.pdf"
EDUCATIONUSA_2021 = "https://educationusa.state.gov/sites/default/files/educationusa/2021_EAP_COMBINED_SMFF.pdf"
UIS_GED_2010 = (
    "https://forschungsnetzwerk.ams.at/dam/jcr%3Aeb9fabb4-ded0-423d-8d63-1f242fed24f5/"
    "Education%20data%202010.pdf")
UIS_GED_2010_SHA256 = "a7b62067a359731688e0b6e03a7ef0a12556f2dd78b6140ad8b81fa8b1e8fe62"
UIS_DIGESTS = {
    2006: {
        "url": "https://sel-gipes.com/uploads/1/2/3/3/12332890/2006_-_unesco_-_global_education_digest.pdf",
        "sha256": "86b49df4107b2fb0643b6985355ce28717f4a803adfc2271908969c0b7c520cb",
        "year": 2004, "table": 10, "header_page": 55, "data_page": 133, "layout": True,
    },
    2010: {
        "url": UIS_GED_2010, "sha256": UIS_GED_2010_SHA256,
        "year": 2008, "table": 10, "header_page": 8, "data_page": 177, "layout": False,
    },
    2011: {
        "url": "https://cisp.cachefly.net/assets/articles/attachments/35800_global_education_digest_2011_en.pdf",
        "sha256": "0a079b1e443eaf48b430400192cd50dbdb6c53ce4fbce4e77c62b9e594f9c5e9",
        "year": 2009, "table": 12, "header_page": 202, "data_page": 203, "layout": False,
    },
}
ERIC_HISTORY_REPORTS = {
    2001: ("ED661491", "a4200bb40b8eae452c60c32a2ed93e0c8b7634edfb8fca8e880834aaf989d569"),
    2003: ("ED661496", "46e102a1dbcbc72363033d90afa9a1707518358013b4906a698c4aeef902a3c3"),
    2005: ("ED661409", "68e1ec145148d32056873535588a821802dced446d8eb5ca00c8c6f423750dfc"),
    2007: ("ED661501", "9ce0578e6d466e904fdcab2507bfa883ca60543a813aac4dab0652dadf2dd1b7"),
    2008: ("ED661502", "4540056dde529aef8006141691420bb415bf8fa813d221810cea9becd04c98cb"),
    2009: ("ED661503", "6ebf24f4054a9b4aa3dafb48f081f8790eeac4b4bdd56e1a36479b40ea96de0b"),
    2010: ("ED661505", "afb1edb24dd65d8f98b79372e569f763c6cb0797788192ad66668c2a72920738"),
    2011: ("ED661506", "14a8c03ddbd5644354358d4caa2d3fc921b84b84af8ab29a5cc19e492cdd196c"),
    2012: ("ED661507", "ecb889b93e008fb8bd65f8b7c3e71cf4c2777f17c45a796991a3fb9764649570"),
    2013: ("ED661508", "fd4786fc5a346b02120040bd3d27568dcff28614232085705f009e22a9ff5506"),
    2015: ("ED661386", "65a2ed6a022ea2cf72021b8f0f6a3171aff64c973b80fad4b253a3f8952e5f6a"),
    2017: ("ED661395", "d78d633fd67ce3007920d867b59a0613583f49e04883980258eb0c05a09f953e"),
    2019: ("ED661414", "35c4720b750caf57b9680bb6f2111e136341cfa8eb33e338095ae832b06b730c"),
}


def text(value):
    return " ".join(str(value).replace("\xa0", " ").split())


def parse_nces(records, countries=(("China", "CHN"), ("Hong Kong", "HKG"))):
    headers = []
    for row in records:
        columns = {}
        for index, cell in enumerate(row):
            match = re.fullmatch(r"(\d{4})[-\u2013](\d{2}|\d{4})", text(cell))
            if match:
                year = int(match[1]) + 1
                if int(match[2]) != (year if len(match[2]) == 4 else year % 100):
                    raise ValueError("NCES academic-year boundary changed")
                columns[year] = index
        if len(columns) >= 3:
            headers.append(columns)
    if len(headers) != 1:
        raise ValueError("NCES academic-year header missing or ambiguous")
    columns = headers[0]
    result = {}
    for label, geo in countries:
        selected = [r for r in records if r and text(r[0]).rstrip(". ").strip() == label]
        if len(selected) != 1:
            raise ValueError("NCES country row missing or ambiguous: " + label)
        for year, index in columns.items():
            if not 2000 <= year <= 2017:
                continue
            value = text(selected[0][index]).replace(",", "")
            if not re.fullmatch(r"\d+(?:\.0)?", value):
                raise ValueError("NCES count column or missingness changed")
            result[geo, year] = int(float(value))
    return result


def government_student_history(client, prior):
    """Read only government republications; never request an IIE resource."""
    existing = {key(r): r for r in prior}
    reference = {geo: next(r for r in prior if r["origin"] == geo and r["destination"] == "USA"
                           and r["measure"] == "international_students" and r["year"] == 2018)
                 for geo in ("CHN", "HKG", "TWN")}
    reviewed = {}
    for url in NCES_HISTORY:
        body, asset = client.get(url)
        soup = BeautifulSoup(body, "html.parser")
        if "Open Doors" not in soup.get_text(" ", strip=True):
            raise ValueError("NCES table no longer identifies the underlying Open Doors population")
        records = []
        for tr in soup.select("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"], recursive=False):
                cells.extend([text(cell.get_text(" ", strip=True))] + [""] * (int(cell.get("colspan", 1)) - 1))
            records.append(cells)
        if not any(r and r[0] == "China" for r in records):
            downloads = sorted({urljoin(url, a["href"]) for a in soup.select("a[href]")
                                if a["href"].lower().endswith(".xls")})
            if len(downloads) != 1:
                raise ValueError("NCES legacy workbook link missing or ambiguous")
            body, asset = client.get(downloads[0])
            sheet = xlrd.open_workbook(file_contents=body).sheet_by_index(0)
            records = [sheet.row_values(i) for i in range(sheet.nrows)]
        for (geo, year), value in parse_nces(
                records, (("China", "CHN"), ("Hong Kong", "HKG"), ("Taiwan", "TWN"))).items():
            old = reviewed.get((geo, year))
            if old and old["value"] != value:
                raise ValueError("NCES country-count vintages disagree; review before merging")
            base = reference[geo]
            row = observation("iie", geo, "USA", "international_students", year, value,
                              base["definition"], period_basis="academic",
                              comparability=base["comparability"],
                              notes="Historical Open Doors aggregate republished by U.S. NCES; government table "
                              "retrieved instead of the permission-restricted IIE website. Includes the original "
                              "international-student population, not an enrolled-only or departure count. "
                              "Academic year ending shown; government-source geography includes U.S. outlying areas.")
            reviewed[geo, year] = attach([row], asset, "NCES Digest government republication: " + url)[0]
    body, asset = client.get(COMMERCE_HISTORY)
    soup = BeautifulSoup(body, "html.parser")
    tables = [t for t in soup.select("table") if "2017/18" in t.text and "363,341" in t.text]
    if len(tables) != 1:
        raise ValueError("Commerce government-republished Chinese student table changed")
    for tr in tables[0].select("tr"):
        cells = [text(c.text) for c in tr.find_all(["th", "td"])]
        if not cells or not re.fullmatch(r"\d{4}/\d{2}", cells[0]):
            continue
        year = int(cells[0][:4]) + 1
        value = int(cells[1].replace(",", ""))
        if year == 2018 and value != reference["CHN"]["value"]:
            raise ValueError("Government republication does not reconcile with retained IIE overlap")
        if not 2000 <= year <= 2017:
            continue
        if ("CHN", year) in reviewed and reviewed["CHN", year]["value"] != value:
            raise ValueError("NCES and Commerce government republications disagree")
        base = reference["CHN"]
        row = observation("iie", "CHN", "USA", "international_students", year, value, base["definition"],
                          period_basis="academic", comparability=base["comparability"],
                          notes="IIE Open Doors aggregate republished by the U.S. Department of Commerce, "
                          "China Education and Training guide, 2019. Only the government republication was "
                          "retrieved; direct IIE automatic retrieval remains paused. Includes OPT, not enrolled-only.")
        reviewed["CHN", year] = attach([row], asset, "U.S. Commerce 2019 guide; government republication of Open Doors")[0]
    if set(reviewed) != {(geo, year) for geo in ("CHN", "HKG", "TWN") for year in range(2000, 2018)}:
        raise ValueError("Government student history is not complete for 2000-2017")
    for row in reviewed.values():
        if key(row) in existing and existing[key(row)]["value"] != row["value"]:
            raise ValueError("Backfill cannot overwrite a conflicting retained observation")
        existing.setdefault(key(row), row)
    return validate(list(existing.values()))


def parse_cau_history(plain):
    if " ".join(str(y) for y in range(2006, 2016)) not in " ".join(plain.split()):
        raise ValueError("Reviewed MOE-republication year columns changed")
    result = {}
    for rank in (2, 3):
        match = re.search(r"^\s*" + str(rank) + r"\s+(.*?)(?=^\s*" + str(rank + 1) + r"\s+)",
                          plain, re.MULTILINE | re.DOTALL)
        pairs = re.findall(r"([\u4e00-\u9fff]+)\s+(\d+)", match[1]) if match else []
        if len(pairs) != 10:
            raise ValueError("Reviewed country/rank table must have ten annual cells per row")
        for year, (country, value) in zip(range(2006, 2016), pairs):
            if country == "\u7f8e\u56fd":
                if year in result:
                    raise ValueError("Duplicate U.S. country count in a reporting year")
                result[year] = int(value)
    if set(result) != set(range(2006, 2016)):
        raise ValueError("MOE historical U.S. country coverage is incomplete")
    return result


def mainland_history(client, reference):
    body, asset = client.get(CAU_HISTORY)
    if asset["sha256"] != "f3b962ef79a090a99a2ae129831b85fde7f9900c592e53ead2def90618a023e1":
        raise ValueError("Reviewed CAU historical education report changed")
    plain = PdfReader(io.BytesIO(body)).pages[36].extract_text()
    existing = {r["year"]: r for r in reference}
    values = parse_cau_history(plain)
    if any(values[y] != existing[y]["value"] for y in (2011, 2012, 2014)):
        raise ValueError("Academic republication does not reconcile with original MOE overlaps")
    rows = []
    for year, value in values.items():
        if year in existing:
            continue
        base = reference[0]
        row = observation(
            "moe", "USA", "CHN", "enrolled_students", year, value, base["definition"],
            period_basis="reporting", comparability=base["comparability"],
            notes="MOE/China Education Yearbook aggregate republished in Zhang Hongwei and Li Chenying's "
            "original China Agricultural University Library research report, table 3, PDF/printed page 37. "
            "The study explicitly identifies the yearbook and MOE website as data sources. All three "
            "retained overlapping MOE years (2011, 2012, 2014) reconcile exactly. "
            "A university-authored statistical republication, not an original MOE web release; "
            "degree and non-degree reporting-year participation, not a point-in-time physical stock.")
        rows.extend(attach([row], asset, "CAU Library 2017 research report; MOE/China Education Yearbook 2006-2015"))
    return rows


def parse_nces_credit(plain):
    compact = " ".join(plain.split())
    if ("Academic years 1997\u201398 and 2007\u201308" not in compact
            or "top 25 destinations" not in compact):
        raise ValueError("NCES academic-credit destination table or periods changed")
    match = re.search(r"^China\s+\d+\s+[\d,]+\s+[\d.]+\s+\d+\s+([\d,]+)\s+[\d.]+\s+[\d.]+\s*$",
                      plain, re.MULTILINE)
    if not match:
        raise ValueError("NCES China credit-study count columns changed")
    return int(match[1].replace(",", ""))


def government_credit_history(client, prior):
    body, asset = client.get(NCES_CREDIT)
    plain = PdfReader(io.BytesIO(body)).pages[329].extract_text()
    value = parse_nces_credit(plain)
    base = next(r for r in prior if r["origin"] == "USA" and r["destination"] == "CHN"
                and r["measure"] == "study_abroad" and r["year"] == 2018)
    row = observation(
        "iie", "USA", "CHN", "study_abroad", 2008, value, base["definition"],
        period_basis="academic", comparability=base["comparability"],
        notes="NCES Condition of Education 2010, table A-40-2, PDF page 330/printed page 294, "
        "government republication of Open Doors. U.S. citizens and permanent residents enrolled in "
        "U.S. degree programs receiving home-institution academic credit; not full degrees overseas. "
        "The 1997/98 comparison column is outside scope. Direct IIE retrieval remains paused.")
    row = attach([row], asset, "NCES Condition of Education 2010; academic-credit destination table A-40-2")[0]
    existing = {key(r): r for r in prior}
    if key(row) in existing and existing[key(row)]["value"] != value:
        raise ValueError("NCES credit-history backfill conflicts with a retained observation")
    existing.setdefault(key(row), row)
    return validate(list(existing.values()))


def parse_uis_digest(plain, year=2008):
    plain = unicodedata.normalize("NFKC", plain)
    compact = " ".join(plain.split())
    caption = (r"International\s+flows\s+of\s+mobile\s+students"
               r"(?:\s+at\s+the\s+tertiary\s+level)?\s*/\s*" + str(year) + r"\b")
    caption_found = bool(re.search(caption, compact, re.IGNORECASE))
    destinations_found = "topfivedestinations(hostcountries)" in "".join(compact.lower().split())
    if not caption_found or not destinations_found:
        raise ValueError(f"UIS historical mobility table or reporting year changed: expected {year}; "
                         f"caption={caption_found}; destinations={destinations_found}; "
                         f"heading={compact[:180]!r}")
    values = {}
    countries = {
        "CHN": ("China",),
        "HKG": ("Hong Kong SAR of China", "China, Hong Kong SAR", "Hong Kong (China), SAR"),
        "MAC": ("Macao, China", "China, Macao SAR"),
    }
    for geo, labels in countries.items():
        selected = [" ".join(line.split()) for line in plain.splitlines()
                    if any(line.strip().startswith(label + " ") for label in labels)]
        if len(selected) != 1:
            raise ValueError("UIS historical country row missing or ambiguous: " + geo)
        matches = re.findall(r"\bU\.S\.A\.\s+\((\d+(?:,\d{3})*)\)(?=,\s|$)", selected[0])
        if len(matches) != 1:
            raise ValueError("UIS exact U.S. destination count or unshifted year missing: " + geo)
        values[geo] = int(matches[0].replace(",", ""))
    return values


def uis_degree_history(client, prior):
    existing = {key(r): r for r in prior}
    for edition, report in UIS_DIGESTS.items():
        body, asset = client.get(report["url"])
        if asset["sha256"] != report["sha256"]:
            raise ValueError("Reviewed UIS historical digest changed")
        reader = PdfReader(io.BytesIO(body))
        heading = reader.pages[report["header_page"] - 1].extract_text()
        plain = reader.pages[report["data_page"] - 1].extract_text(
            **({"extraction_mode": "layout"} if report["layout"] else {}))
        year = report["year"]
        values = parse_uis_digest(heading + "\n" + plain, year)
        # Legacy "China" can aggregate mainland and Taiwan; never relabel it mainland-only.
        for geo in ("HKG", "MAC"):
            value = values[geo]
            base = next(r for r in prior if r["source_id"] == "uis" and r["origin"] == geo
                        and r["destination"] == "USA" and r["measure"] == "degree_students"
                        and r["year"] == 2023)
            locator = (f"UNESCO Global Education Digest {edition}, table {report['table']}, "
                       f"PDF page {report['data_page']}; reporting year {year}")
            row = observation(
                "uis", geo, "USA", "degree_students", year, value,
                base["definition"] + "; historical ISCED 1997 levels 5 and 6",
                period_basis="reporting", comparability="uis:degree_students:legacy-isced97",
                notes=locator + ". Original UNESCO report retained at the public source URL, "
                "not a newly retrieved current UIS release. Exact country-specific U.S. destination "
                "count in brackets, not worldwide outbound or all-origin host totals. The U.S. "
                "cells carry no reference-year offset. Only separately identified Hong Kong/Macau "
                "counts are imported; the historical China category is not verified mainland-only. "
                "ISCED 1997 levels 5/6 retain a separate comparison identity: cross-definition "
                "growth against current UIS is not assumed. No within-year dates invented. "
                "Only selected numerical facts are retained; original reports are not redistributed.")
            row = attach([row], asset, locator)[0]
            if key(row) in existing and existing[key(row)]["value"] != value:
                raise ValueError("UIS historical fact conflicts with a retained observation")
            existing.setdefault(key(row), row)
    return validate(list(existing.values()))


def parse_educationusa_levels(plain, country):
    compact = " ".join(plain.split())
    compact = re.sub(r"Non\s*-\s*Degree", "Non-Degree", compact)
    if (not compact.startswith(country + " ") or "Source: 2021 Open Doors" not in compact
            or "Students in U.S. by Academic Level % Number" not in compact
            or "Change (2020 to 2021)" not in compact):
        raise ValueError("EducationUSA country, academic-level table or reporting year changed")
    counts = []
    for label in ("Undergraduate", "Graduate", "Non-Degree", "OPT"):
        matches = re.findall(
            r"\b" + label + r"\s+\d+(?:\.\d+)?%\s+(\d{1,3}(?:,\d{3})*|\d+)\s+[+-]?\d+(?:\.\d+)?%",
            compact)
        if len(matches) != 1:
            raise ValueError("EducationUSA academic-level count missing or ambiguous: " + label)
        counts.append(int(matches[0].replace(",", "")))
    return counts


def parse_eric_academic_levels(plain, country, year):
    compact = "".join(plain.split())
    if ("TOTALUNDERGRADUATEGRADUATENON-DEGREEOPTIONALPRACTICALTRAINING" not in compact
            or f"{year - 2}/{str(year - 1)[-2:]}" not in compact
            or f"{year - 1}/{str(year)[-2:]}" not in compact):
        raise ValueError("ERIC academic-level header or years changed")
    matches = {tuple(line.strip()[len(country) + 1:].split()) for line in plain.splitlines()
               if line.strip().startswith(country + " ")}
    if len(matches) != 1:
        raise ValueError("ERIC country academic-level row missing or conflicting")
    fields = list(matches.pop())
    if len(fields) != 17:
        raise ValueError("ERIC academic-level columns changed")
    positions = (0, 1, 2, 5, 6, 9, 10, 13, 14)
    if any(not re.fullmatch(r"\d+(?:,\d{3})*", fields[i]) for i in positions):
        raise ValueError("ERIC exact academic-level count missing")
    numeric = {i: int(fields[i].replace(",", "")) for i in positions}
    previous = [numeric[i] for i in (1, 5, 9, 13)]
    current = [numeric[i] for i in (2, 6, 10, 14)]
    if sum(current) != numeric[0]:
        raise ValueError("ERIC academic-level counts do not reconcile with the printed total")
    return previous, current


def parse_eric_legacy_levels(plain, country, year):
    compact = "".join(plain.split()).upper()
    opt_first = "OPTOPTOTHEROTHERTOTAL" in compact
    if (not (opt_first or "OPTOPTTOTAL" in compact) or "GRADUATE" not in compact
            or f"{year - 1}/{str(year)[-2:]}" not in compact):
        raise ValueError("ERIC legacy academic-level header or year changed")
    matches = {tuple(line.strip()[len(country) + 1:].split()) for line in plain.splitlines()
               if line.strip().startswith(country + " ")}
    if len(matches) != 1:
        raise ValueError("ERIC legacy country row missing or conflicting")
    fields = list(matches.pop())
    if len(fields) != 9:
        raise ValueError("ERIC legacy academic-level columns changed")
    if any(not re.fullmatch(r"\d+(?:,\d{3})*", fields[i]) for i in (0, 2, 4, 6, 8)):
        raise ValueError("ERIC legacy exact academic-level count missing")
    counts = [int(fields[i].replace(",", "")) for i in (0, 2, 4, 6)]
    if sum(counts) != int(fields[8].replace(",", "")):
        raise ValueError("ERIC legacy academic levels do not reconcile with the printed total")
    if opt_first:
        counts[2], counts[3] = counts[3], counts[2]
    return counts


def parse_eric_country_history(plain, country, years, *, destinations=False):
    compact = "".join(plain.split()).upper()
    header = "DESTINATION" if destinations else "PLACEOFORIGIN"
    if header not in compact or any(
            f"{year - 1}/{str(year)[-2:]}" not in compact for year in years):
        raise ValueError("ERIC country-history header or academic years changed")
    matches = {tuple(line.strip()[len(country) + 1:].split()) for line in plain.splitlines()
               if line.strip().startswith(country + " ")}
    if len(matches) != 1:
        raise ValueError("ERIC country-history row missing or conflicting")
    fields = list(matches.pop())
    if len(fields) not in {len(years) + 1, len(years) + 2}:
        raise ValueError("ERIC country-history columns changed")
    if any(not re.fullmatch(r"\d+(?:,\d{3})*", value) for value in fields[:len(years)]):
        raise ValueError("ERIC country-history exact count missing")
    return {year: int(value.replace(",", "")) for year, value in zip(years, fields)}


def government_eric_history(client, prior):
    """Recover exact historical facts from checksum-pinned federal deposits."""
    existing = {key(r): r for r in prior}
    documents = {}
    countries = {"CHN": "China", "HKG": "Hong Kong", "MAC": "Macau", "TWN": "Taiwan"}

    def report(year):
        if year not in documents:
            document, checksum = ERIC_HISTORY_REPORTS[year]
            body, asset = client.get("https://files.eric.ed.gov/fulltext/" + document + ".pdf")
            if asset["sha256"] != checksum:
                raise ValueError("Reviewed ERIC historical report changed")
            documents[year] = PdfReader(io.BytesIO(body)), asset
        return documents[year]

    def retain(edition, pages, geo, measure, year, value, detail):
        reader, asset = report(edition)
        origin, destination = ("USA", geo) if measure == "study_abroad" else (geo, "USA")
        base = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == origin
                    and r["destination"] == destination and r["measure"] == measure
                    and r["year"] == (2024 if measure == "study_abroad" else 2025))
        document = ERIC_HISTORY_REPORTS[edition][0]
        locator = (f"IIE Open Doors {edition}; original federal ERIC deposit {document}; PDF pages "
                   + ", ".join(map(str, pages)))
        row = observation(
            "iie", origin, destination, measure, year, value, base["definition"],
            period_basis="academic", comparability=base["comparability"],
            notes=locator + ". " + detail + " Exact published counts, not rounded-share estimates. "
            "Selected numerical facts only; the original book is not redistributed. "
            "Direct IIE-hosted retrieval remains paused.")
        row = attach([row], asset, locator)[0]
        if key(row) in existing and existing[key(row)]["value"] != value:
            raise ValueError("ERIC historical fact conflicts with a retained observation")
        existing.setdefault(key(row), row)

    total_tables = [
        (2001, 26, "Macao"), (2003, 26, "Macao"), (2005, 27, "Macau"),
        (2007, 38, "Macau, China"), (2008, 37, "Macau"), (2010, 55, "Macau"),
        (2011, 55, "Macau"), (2013, 45, "Macau"), (2015, 52, "Macau"),
    ]
    for edition, page, label in total_tables:
        reader, asset = report(edition)
        values = parse_eric_country_history(reader.pages[page - 1].extract_text(), label,
                                           [edition - 1, edition])
        for year, value in values.items():
            retain(edition, [page], "MAC", "international_students", year, value,
                   "Country-origin total includes OPT; the printed Macao/Macau row is kept "
                   "separate from mainland China and Hong Kong.")

    totals = {(r["origin"], r["year"]): r["value"] for r in existing.values()
              if r["source_id"] == "iie" and r["destination"] == "USA"
              and r["measure"] == "international_students"}
    level_tables = [(2007, 42), (2008, 41), (2009, 68), (2010, 59),
                    (2011, 59), (2012, 51), (2013, 49)]
    for edition, page in level_tables:
        reader, asset = report(edition)
        plain = reader.pages[page - 1].extract_text(
            **({"extraction_mode": "layout"} if edition == 2007 else {}))
        for geo, label in countries.items():
            if edition == 2007 and geo != "TWN":
                label = {"CHN": "China, PRC", "HKG": "Hong Kong, China", "MAC": "Macau, China"}[geo]
            counts = parse_eric_legacy_levels(plain, label, edition)
            control = totals.get((geo, edition))
            provenance, pages = "", [page]
            if (edition, geo) == (2013, "TWN"):
                original = parse_eric_country_history(
                    reader.pages[44].extract_text(), label, [2012, 2013])[2013]
                provenance = (f"The original country-total table on PDF page 45 reports {original}; "
                              f"the retained NCES republication reports {control}. This source-vintage "
                              "difference is disclosed, not silently overwritten or allocated to OPT. ")
                control, pages = original, [45, page]
            if sum(counts) != control:
                raise ValueError("ERIC legacy levels disagree with the independent country total")
            retain(edition, pages, geo, "enrolled_students", edition, sum(counts[:3]),
                   f"Undergraduate {counts[0]} + graduate {counts[1]} + non-degree/Other "
                   f"{counts[2]}; separately reported OPT {counts[3]} excluded. "
                   "Other means intensive English and other non-degree students, not OPT. "
                   "The 2007 table prints OPT before Other; subsequent tables reverse those columns. "
                   + provenance + "All four levels reconcile with the independent country-total table.")

    for edition, first_page in [(2015, 56), (2017, 56), (2019, 48)]:
        reader, asset = report(edition)
        for geo, label in countries.items():
            page = first_page + (geo != "CHN")
            if geo == "TWN":
                label = "T aiwan"
            levels = parse_eric_academic_levels(reader.pages[page - 1].extract_text(), label, edition)
            for year, counts in zip((edition - 1, edition), levels):
                if sum(counts) != totals.get((geo, year)):
                    raise ValueError("ERIC historical levels disagree with the independent country total")
                retain(edition, [page], geo, "enrolled_students", year, sum(counts[:3]),
                       f"Exact undergraduate {counts[0]}, graduate {counts[1]} and non-degree "
                       f"{counts[2]} counts summed; OPT {counts[3]} excluded. "
                       "All four levels reconcile with the separately retained country total.")

    credit_tables = [
        (2009, [92, 93], list(range(1999, 2009))),
        (2011, [84], [2009, 2010]), (2013, [73, 74], [2011, 2012]),
        (2015, [91, 92], [2013, 2014]),
    ]
    for edition, pages, years in credit_tables:
        reader, asset = report(edition)
        plain = "\n".join(reader.pages[p - 1].extract_text() for p in pages)
        for geo, label in countries.items():
            if edition == 2015 and geo == "TWN":
                label = "T aiwan"
            values = parse_eric_country_history(plain, label, years, destinations=True)
            for year, value in values.items():
                if year >= 2000:
                    retain(edition, pages, geo, "study_abroad", year, value,
                           "U.S. home-institution academic-credit participation by destination; "
                           "not whole degrees abroad or non-credit visits. Academic ending year shown. "
                           "A printed zero is retained; no unlisted country is inferred to have zero.")
    return validate(list(existing.values()))


def government_enrollment_history(client, prior):
    reports = [
        (2020, "ED661341", "5eadfd853ca4a8be8e4ad2d3f2060c7af75300aba1d18509ac9dc0b86ccf24e6",
         {"CHN": ("China", 46), "HKG": ("Hong Kong", 47), "MAC": ("Macau", 47), "TWN": ("Taiwan", 47)}),
        (2023, "ED661412", "9e7875404730421b5d9acf2c0fe194d07eef03095362741389dbf8dad6af7e71",
         {"CHN": ("China", 54), "HKG": ("Hong Kong", 54), "MAC": ("Macau", 54), "TWN": ("Taiwan", 54)}),
    ]
    existing = {key(r): r for r in prior}
    totals = {(r["origin"], r["year"]): r["value"] for r in prior
              if r["source_id"] == "iie" and r["destination"] == "USA"
              and r["measure"] == "international_students"}
    for last_year, document, checksum, countries in reports:
        body, asset = client.get("https://files.eric.ed.gov/fulltext/" + document + ".pdf")
        if asset["sha256"] != checksum:
            raise ValueError("Reviewed ERIC country-level report changed")
        pages = PdfReader(io.BytesIO(body)).pages
        for geo, (country, page) in countries.items():
            levels = parse_eric_academic_levels(pages[page].extract_text(), country, last_year)
            for year, counts in zip((last_year - 1, last_year), levels):
                if sum(counts) != totals.get((geo, year)):
                    raise ValueError("ERIC levels do not reconcile with the retained country/year total")
                base_year = 2021 if 2021 <= year <= 2023 else 2025
                base = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == geo
                            and r["destination"] == "USA" and r["measure"] == "enrolled_students"
                            and r["year"] == base_year)
                row = observation(
                    "iie", geo, "USA", "enrolled_students", year, sum(counts[:3]), base["definition"],
                    period_basis="academic", comparability=base["comparability"],
                    notes=f"IIE Open Doors {last_year}, original report deposited in the federal ERIC "
                    f"repository ({document}), table 1.15, PDF page {page + 1}. Exact undergraduate "
                    f"{counts[0]}, graduate {counts[1]} and non-degree {counts[2]} counts summed; "
                    f"OPT {counts[3]} excluded. The four counts reconcile with the independently retained "
                    "country/year total. No rounded-share back-calculation. Original IIE authorship and "
                    "source restrictions remain; selected numerical facts only, not a redistributed report. "
                    "Pandemic-expanded census years retain their separate comparison identity. "
                    "Direct IIE-hosted retrieval remains paused.")
                row = attach([row], asset, f"IIE Open Doors {last_year}; original ERIC deposit {document}, table 1.15")[0]
                if key(row) in existing and existing[key(row)]["value"] != row["value"]:
                    raise ValueError("ERIC enrollment history conflicts with a retained observation")
                existing.setdefault(key(row), row)
    return validate(list(existing.values()))


def government_mobility_history(client, prior):
    body, asset = client.get(EDUCATIONUSA_2021)
    if asset["sha256"] != "cc3d1155da82fbb60eda18751c780657f44ee8de500412cef2280362bde4296c":
        raise ValueError("Reviewed EducationUSA mobility report changed")
    report = PdfReader(io.BytesIO(body))
    existing = {key(r): r for r in prior}
    countries = {
        "CHN": ("China", 11, [13763, 12790, 11688, 11910, 11613, 11639, 2481]),
        "HKG": ("Hong Kong", 18, [1596, 1508, 1612, 1641, 1859, 2314, 543]),
        "MAC": ("Macau", 28, [18, 3, 4, 33, 4, 23, 7]),
        "TWN": ("Taiwan", 55, [801, 880, 980, 1002, 857, 1270, 451]),
    }
    candidates = []
    for geo, (country, page, credits) in countries.items():
        counts = parse_educationusa_levels(report.pages[page].extract_text(), country)
        total = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == geo
                     and r["destination"] == "USA" and r["measure"] == "international_students"
                     and r["year"] == 2021)
        if sum(counts) != total["value"]:
            raise ValueError("EducationUSA academic levels do not reconcile with the retained country total")
        base = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == geo
                    and r["destination"] == "USA" and r["measure"] == "enrolled_students")
        row = observation(
            "iie", geo, "USA", "enrolled_students", 2021, sum(counts[:3]),
            base["definition"] + "; expanded pandemic census includes coursework from outside the U.S. "
            "regardless of visa status",
            period_basis="academic", comparability="iie:enrolled_students:pandemic-expanded",
            notes="EducationUSA 2021 Student Mobility Facts and Figures, government republication, "
            f"PDF page {page + 1}. Adds the published undergraduate, graduate and non-degree counts; "
            f"excludes the separately published OPT count {counts[3]}. All four level counts reconcile "
            "exactly with the retained 2020/21 country total. No rounded percentages are used. "
            "Pandemic reporting can include enrolled students outside the United States; not a physical "
            "border-crossing count. Direct IIE retrieval remains paused.")
        candidates.extend(attach([row], asset, f"EducationUSA 2021 government republication; PDF page {page + 1}"))
        base = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == "USA"
                    and r["destination"] == geo and r["measure"] == "study_abroad" and r["year"] == 2018)
        for year, value in enumerate(credits, 2014):
            row = observation(
                "iie", "USA", geo, "study_abroad", year, value, base["definition"],
                period_basis="academic", comparability=base["comparability"],
                notes="EducationUSA 2021 Student Mobility Facts and Figures, government republication, "
                f"PDF page {page + 1}, separately labelled U.S. study-abroad chart. Exact value labels "
                "manually reviewed in the checksum-pinned raster chart; not inferred from line coordinates, "
                "shares or visa totals. Academic ending years, following Open Doors: all three retained "
                "overlaps (2018, 2019, 2020) reconcile exactly. Academic-credit participation, not "
                "whole-degree enrollment or all U.S. nationals. Direct IIE retrieval remains paused.")
            if year >= 2018 and (key(row) not in existing or existing[key(row)]["value"] != value):
                raise ValueError("EducationUSA credit-chart overlaps disagree with retained observations")
            candidates.extend(attach([row], asset, f"EducationUSA 2021 government republication; PDF page {page + 1}"))
    base = next(r for r in prior if r["source_id"] == "iie" and r["origin"] == "MAC"
                and r["destination"] == "USA" and r["measure"] == "international_students" and r["year"] == 2018)
    for year, value in enumerate([573, 586, 605, 555, 558, 503, 422], 2015):
        row = observation(
            "iie", "MAC", "USA", "international_students", year, value, base["definition"],
            period_basis="academic", comparability=base["comparability"],
            notes="EducationUSA 2021 Student Mobility Facts and Figures, government republication, "
            "PDF page 29, Macau-only inbound chart. Exact printed raster-chart labels manually reviewed "
            "against the checksum-pinned report; 2018-2021 overlap exactly with all four retained "
            "country totals. Includes OPT, not enrolled-only; Macau is not allocated from a combined "
            "Hong Kong/Macau figure. Direct IIE retrieval remains paused.")
        if year >= 2018 and (key(row) not in existing or existing[key(row)]["value"] != value):
            raise ValueError("EducationUSA Macau inbound-chart overlaps disagree with retained observations")
        candidates.extend(attach([row], asset, "EducationUSA 2021 government republication; PDF page 29"))
    for row in candidates:
        if key(row) in existing and existing[key(row)]["value"] != row["value"]:
            raise ValueError("EducationUSA backfill conflicts with a retained observation")
        existing.setdefault(key(row), row)
    return validate(list(existing.values()))


def mainland_students(client):
    rows = []
    for year, expected, url in MOE_HISTORY:
        body, asset = client.get(url)
        plain = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
        match = re.search(r"美国\s*([\d,]+)\s*人", plain)
        if not match or int(match[1].replace(",", "")) != expected or str(year) not in plain:
            raise ValueError("Reviewed MOE U.S. student count changed")
        row = observation(
            "moe", "USA", "CHN", "enrolled_students", year, expected,
            "MOE annual reported U.S.-nationality foreign students in mainland higher education, research "
            "and other teaching institutions; degree and non-degree study; not an enrolled-at-one-date stock, "
            "U.S.-university credit study abroad, all U.S. residents, or student departures",
            period_basis="reporting", comparability="moe:us_nationality:degree_and_nondegree",
            notes="Selected historical reporting years only; gaps are not zeros. Reporting-year labels do not "
            "invent calendar or academic-year boundaries. MOE reports reproduced by its CSCSE center in "
            "2011/2012/2014, by China National Radio's education briefing report in 2016, and MOE directly in 2018. "
            "No current U.S.-nationality total is inferred from program announcements.")
        reviewed = attach([row], asset, f"MOE {year} international-student report; reviewed government/briefing republication")[0]
        if asset["url"] != url:
            reviewed["source_url"] = url
            reviewed["notes"] += f" Requested official locator: {url}; publisher-resolved retrieval URL: {asset['url']}."
        rows.append(reviewed)
    rows.extend(mainland_history(client, rows))
    return rows, "MOE reporting years 2006-2016 and 2018; original and explicitly attributed republications", (
        "Reported U.S.-nationality degree and non-degree students, not U.S. credit-program participants or "
        "tertiary degree-only counts. Historical snapshots do not establish later enrollment. "
        "CAU's original yearbook/MOE research table restores seven earlier/intermediate years; "
        "2011, 2012 and 2014 overlap exactly with retained ministry reports. "
        "The reviewed 2017 ministry briefing ranks source countries without a U.S. count, so no number is inferred. "
        "Original statistical aggregates only; reports are not redistributed.")


def parse_hktdc(plain):
    block = re.search(r"8\.2\s+Tourism Statistics\s+(.*?)\s+8\.3", plain, re.S)
    if not block:
        raise ValueError("HKTDC tourism table missing")
    match = re.search(r"((?:20\d{2}\s+){3})Number of US natio(?:na|an)ls\s+visiting Hong Kong\s+"
                      r"([\d,]+)\s+([\d,]+)\s+([\d,]+)", block[1])
    if not match:
        raise ValueError("HKTDC U.S.-nationality row or annual columns changed")
    years = [int(y) for y in match[1].split()]
    if years != [2023, 2024, 2025]:
        raise ValueError("HKTDC reviewed annual years changed")
    return dict(zip(years, [int(match[i].replace(",", "")) for i in (2, 3, 4)]))


def hong_kong_visitors(client):
    from .tourism_backfill import hong_kong_history

    try:
        body, asset = client.get(HKTDC)
        values = parse_hktdc(body.decode())
    except (ValueError, UnicodeDecodeError):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(HKTDC, timeout=60000, wait_until="domcontentloaded")
                page.get_by_text("8.2 Tourism Statistics", exact=False).first.wait_for(timeout=45000)
                plain = page.locator("body").inner_text()
                values = parse_hktdc(plain)
                body, asset = client.remember(HKTDC, plain.encode(), HKTDC)
            finally:
                browser.close()
    rows = []
    for year, value in values.items():
        row = observation(
            "hktb", "USA", "HKG", "visitors", year, value,
            "HKTB all-mode visitor arrivals attributed to U.S. nationality, as republished in HKTDC's "
            "U.S. Market Profile; not U.S. residence, unique people, leisure-only tourists or air-survey estimates",
            comparability="hktb:us_nationality:all_mode",
            notes="HKTDC section 8.2 explicitly reports U.S. nationals; the 2023 count is 596,958, not the "
            "594,752 U.S.-residence figure found in other releases. Do not splice these populations. "
            "Source checksum identifies retained browser-visible report text, not original HTML or a PDF. "
            "Historical residence-based arrivals are a separate comparison segment, not a continuous "
            "nationality series. Matched January-June 2025/2026 all-mode counts are separately labelled.")
        rows.extend(attach([row], asset, "HKTDC U.S. Market Profile, 2026; HKTB nationality counts 2023-2025"))
    rows.extend(hong_kong_history(client))
    return rows, "HKTB residence arrivals 2000-2022; nationality 2023-2025 and January-June 2025/2026", (
        "Official HKTDC republication of HKTB arrivals. Nationality, not residence, all purposes and modes. "
        "Browser-rendered public report text retained with checksum; no challenge bypass. "
        "C&SD/MGTO republications restore 2000-2022 residence history as a separate comparability segment; "
        "charts break at 2023 and cross-definition changes/indices are unavailable. MGTO provides "
        "direct matched first-half 2025/2026 nationality totals. NTTO air estimates remain separate.")
