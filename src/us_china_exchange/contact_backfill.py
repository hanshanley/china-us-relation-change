"""Manual review of government-republished education and visitor aggregates."""

import re
from urllib.parse import urljoin

import xlrd
from bs4 import BeautifulSoup

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


def text(value):
    return " ".join(str(value).replace("\xa0", " ").split())


def parse_nces(records):
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
    for label, geo in [("China", "CHN"), ("Hong Kong", "HKG")]:
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
                 for geo in ("CHN", "HKG")}
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
        for (geo, year), value in parse_nces(records).items():
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
    if set(reviewed) != {(geo, year) for geo in ("CHN", "HKG") for year in range(2000, 2018)}:
        raise ValueError("Government student history is not complete for 2000-2017")
    for row in reviewed.values():
        if key(row) in existing and existing[key(row)]["value"] != row["value"]:
            raise ValueError("Backfill cannot overwrite a conflicting retained observation")
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
    return rows, "MOE reviewed historical reporting years 2011, 2012, 2014, 2016, 2018", (
        "Reported U.S.-nationality degree and non-degree students, not U.S. credit-program participants or "
        "tertiary degree-only counts. Historical snapshots do not establish later enrollment. "
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
            "Pre-2023 nationality counts and 2026 all-mode partials remain unverified.")
        rows.extend(attach([row], asset, "HKTDC U.S. Market Profile, 2026; HKTB nationality counts 2023-2025"))
    return rows, "HKTDC U.S. Market Profile; HKTB 2023-2025 nationality arrivals", (
        "Official HKTDC republication of HKTB arrivals. Nationality, not residence, all purposes and modes. "
        "Browser-rendered public report text retained with checksum; no challenge bypass. "
        "Not spliced into older residence-based figures or NTTO resident-air estimates.")
