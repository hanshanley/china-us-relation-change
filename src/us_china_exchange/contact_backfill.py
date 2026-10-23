"""Manual review of education and visitor aggregate republications."""

import io
import re
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
