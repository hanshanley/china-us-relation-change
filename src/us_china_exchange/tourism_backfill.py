"""Reviewed government republications of bilateral visitor statistics."""

import io
import json
import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .language_sources import pdf_text
from .model import digest, key, observation, validate
from .sources import attach, macau_observation, parse_ustr_macau_services, ustr_macau_services, workbook


MGTO = "https://dataplus.macaotourism.gov.mo"
USTR_MACAU_ARCHIVE = (
    "https://web.archive.org/web/20251218202809/"
    "https://ustr.gov/countries-regions/china-mongolia-taiwan/macau")
HK_DIGEST = "https://www.statistics.gov.hk/pub/B10100032003AN03B0600.pdf"
MACAU_2001 = (
    "https://www.dsec.gov.mo/getAttachment/536cc867-adab-455f-bc63-df3c8d3a31ea/"
    "P_TUR_PUB_2001_Y.aspx?disposition=attachment")
MACAU_2002 = (
    "https://www.dsec.gov.mo/getAttachment/8c86dc19-36cc-4a05-8133-5470c143c09b/"
    "P_TUR_PUB_2002_Y.aspx")
DSEC_VISITORS = "https://www.dsec.gov.mo/StatisticsJSON/AllReleases_en-US_TourismAndServices.json"
HK_REVIEWED_INPUT = (
    "https://raw.githubusercontent.com/hanshanley/china-us-relation-change/main/"
    "data/reviewed/hktb-monthly-2026-08.json")
HK_REPORTS = [
    (2008, "M12_MarketingPerformance_2008_1246941849.pdf",
     "9e2ac46cf301021f8c1b8862bf590c199792cc0b2b3cf9933085ddf61b8ead0e"),
    (2013, "M12_MarketPerformance_2013_1397114944.pdf",
     "05f86569407d19b790a40f35287b9569f58ba844a12002629d6b0280f1556a51"),
    (2018, "Market%20Performance%202018.pdf",
     "e7c2c1b49e4b134f407e5f44a198164b50aa6391a11bd58e8c24e1f6233b47a4"),
    (2023, "Market%20Performance%202023.pdf",
     "e1a0cf7653c17b30256ac4c7a06e3cfcdf1c6ca774373ae2efe89719c49809b7"),
]
HK_HALVES = [
    (2025, "Market%20Performance%20Jan-Jun.pdf",
     "a34d9acc89a83c5deac41763851f095807fb01852aaf6efbda2f5bacb99e1dc6"),
    (2026, "Market%20Performance%20Jan-Jun%202026.pdf",
     "9a0ab73bf4495f2f17c063ba349df6cf9bdf9861143fda2a2eac9f8f245c95d4"),
]


def reviewed_hktb_months(content, prior, retrieved_at):
    data = json.loads(content)
    if (data.get("version") != 1 or data.get("publisher") != "Hong Kong Tourism Board"
            or data.get("country") != "USA" or data.get("population") != "nationality_region"
            or data.get("transport_scope") != "all_mode" or data.get("unit") != "arrivals"
            or data.get("column_order") != ["previous_year_month", "current_year_month",
                                           "previous_year_ytd", "current_year_ytd"]
            or "not cached publisher PDFs" not in data.get("evidence_format", "")):
        raise ValueError("Reviewed HKTB input population, units or transcription identity changed")
    reviewed = datetime.strptime(data["reviewed_on"], "%Y-%m-%d")
    cumulative = {(r["year"], int(r["period"][-2:])): r["value"] for r in prior
                  if r["series_id"] == "hktb:USA:HKG:visitors" and r["frequency"] == "ytd"
                  and r["comparability"] == "hktb:us_nationality:all_mode"}
    rows, seen = [], set()
    for report in sorted(data["reports"], key=lambda r: (r["year"], r["month"])):
        year, month = report["year"], report["month"]
        if (isinstance(year, bool) or not isinstance(year, int) or isinstance(month, bool)
                or not isinstance(month, int) or not 1 <= month <= 12):
            raise ValueError("Reviewed HKTB report year/month must be integers")
        expected_url = ("https://www.discoverhongkong.com/content/dam/dhk/intl/corporate/newsroom/"
                        f"tourisum-statistics/{year}/tourism_stat_{month:02d}_{year}.pdf")
        if ((year, month) >= (reviewed.year, reviewed.month)
                or report["report_url"] != expected_url or (year, month) in seen):
            raise ValueError("Reviewed HKTB report period or primary URL changed")
        seen.add((year, month))
        for field in ("total", "overnight", "same_day"):
            if len(report[field]) != 4 or any(isinstance(v, bool) or not isinstance(v, int) or v < 0
                                            for v in report[field]):
                raise ValueError("Reviewed HKTB counts require four exact, nonnegative integers")
        totals = report["total"]
        if any(totals[i] != report["overnight"][i] + report["same_day"][i] for i in range(4)):
            raise ValueError("HKTB total arrivals do not reconcile with overnight and same-day counts")
        for y, monthly, ytd in ((year - 1, totals[0], totals[2]), (year, totals[1], totals[3])):
            previous = cumulative.get((y, month - 1))
            if previous is None or previous + monthly != ytd:
                raise ValueError("HKTB monthly arrivals do not reconcile with the preceding published cumulative total")
            if (y, month) in cumulative and cumulative[y, month] != ytd:
                raise ValueError("Reviewed HKTB cumulative count differs from retained source vintage")
            cumulative[y, month] = ytd
            for frequency, value in (("monthly", monthly), ("ytd", ytd)):
                rows.append(observation(
                    "hktb", "USA", "HKG", "visitors", y, value,
                    "HKTB all-mode U.S.-nationality visitor arrivals; includes overnight and same-day visits, "
                    "not the historical U.S.-residence population, unique people or leisure-only tourists",
                    frequency=frequency, month=month, comparability="hktb:us_nationality:all_mode",
                    notes="Selected U.S. numerical facts manually reviewed from HKTB tables 1-3. "
                    "Primary report: " + report["report_url"] + ". Published " + report["publication_month"] + ". "
                    "Source URL and checksum refer to the versioned reviewed JSON transcription, not a cached "
                    "publisher PDF; direct automated PDF retrieval was unavailable. Overnight + same-day and "
                    "the preceding cumulative total + this month both reconcile exactly. "
                    "Not annualized or spliced into the pre-2023 residence history."))
    if not rows:
        raise ValueError("Reviewed HKTB input contains no observations")
    asset = {"url": HK_REVIEWED_INPUT, "sha256": digest(content), "retrieved_at": retrieved_at}
    vintage = "HKTB July/August 2026 reports; selected U.S. facts reviewed " + data["reviewed_on"]
    return attach(validate(rows), asset, vintage), vintage, (
        "Monthly and matched January-July/August 2025/2026 nationality counts, manually verified in "
        "public HKTB reports. Checksums cover the versioned reviewed transcription, not publisher PDFs. "
        "Both stay-length components and successive cumulative totals reconcile with the retained first half.")


def parse_archived_macau_services(content):
    plain = " ".join(BeautifulSoup(content, "html.parser").get_text(" ", strip=True).split())
    match = re.search(r"Macau Trade Summary.*?(?=Stay in the Know)", plain)
    if not match or digest(match[0].encode()) != "ada54d78f1505dec3823d6f1e8fb35b7ee9b7ce7ea8a4942899ab10e7e2ba642":
        raise ValueError("Reviewed archived USTR statistical passage changed")
    profile = match[0]
    corrected = profile.replace("U.S. total services trade", "U.S. services trade", 1).replace(
        "$474 billion in 2024", "$474 million in 2024", 1)
    rows, year = parse_ustr_macau_services(corrected)
    overall = re.search(r"goods and services trade with Macau totaled an estimated \$([\d.]+) million in 2024", profile)
    goods = re.search(r"total goods trade \(exports plus imports\) with Macau was an estimated \$([\d.]+) million in 2024", profile)
    if (year != 2024 or not overall or not goods or sum(r["value"] for r in rows)
            != (Decimal(overall[1]) - Decimal(goods[1])) * 1_000_000):
        raise ValueError("Archived services do not reconcile with same-year USTR goods/combined totals")
    for row in rows:
        row["comparability"] = "ustr:macau:archived_2024_estimate"
        row["notes"] = (
            "Direct 2024 services amount from the original USTR page archived December 18, 2025; "
            "rounded estimated USD. Directional figures are unchanged: exports $440 million and imports "
            "$34 million. Source aggregate incorrectly says '$474 billion'; only that aggregate unit "
            "is corrected for validation, explicitly rather than silently. Independently quoted surplus "
            "$406 million and same-year $864.0 million combined trade less $390 million goods both "
            "reconcile exactly with the directional figures. No services amount is allocated from goods "
            "or derived from rounded prior-year growth. The original statistical passage is checksum-pinned "
            "separately from Wayback's dynamic wrapper; raw response checksum and actual capture URL are retained. "
            "This archival vintage is deliberately not used for growth against the current 2025 estimate, "
            "whose implied 2024 export base has been revised. It is not automatically rechecked daily.")
    return rows


def macau_services_history(client):
    rows, vintage, notes = ustr_macau_services(client)
    body, asset = client.get(USTR_MACAU_ARCHIVE)
    rows.extend(attach(parse_archived_macau_services(body), asset,
                       "USTR 2024 estimates; original government page archived December 18, 2025"))
    return rows, vintage, notes


def parse_dsec_visitors(content, year, month):
    book = workbook(content)
    expected_dates = [datetime(y, month, 1) for y in (year - 1, year, year - 1, year)]
    columns = (3, 4, 6, 8)

    def counts(number, title):
        table = list(book[str(number)].values)
        if (table[2][0] != title or [table[5][c] for c in columns] != expected_dates
                or any(table[8][c] != "No." for c in columns)
                or not re.search(r"Jan\.\s*-", str(table[4][6]))):
            raise ValueError("DSEC visitor population, periods, count columns or cumulative header changed")
        countries = [r for r in table if r[2] == "USA"]
        if len(countries) != 1:
            raise ValueError("DSEC U.S. visitor row missing or ambiguous")
        values = [countries[0][c] for c in columns]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0
               or not float(v).is_integer() for v in values):
            raise ValueError("DSEC visitor counts are missing or invalid")
        return [int(v) for v in values]

    suffix = " BY ISSUING PLACE OF TRAVEL DOCUMENT"
    total = counts(1, "VISITOR ARRIVALS" + suffix)
    modes = [counts(n, "VISITOR ARRIVALS BY " + mode + " AND" + suffix)
             for n, mode in ((2, "SEA"), (3, "LAND"), (4, "AIR"))]
    same_day = counts(5, "SAME-DAY VISITOR ARRIVALS" + suffix)
    overnight = counts(9, "OVERNIGHT VISITOR ARRIVALS" + suffix)
    if any(total[i] != sum(v[i] for v in modes) or total[i] != same_day[i] + overnight[i]
           for i in range(4)):
        raise ValueError("DSEC visitor modes or same-day/overnight totals do not reconcile")
    if total[0] > total[2] or total[1] > total[3]:
        raise ValueError("DSEC monthly arrivals exceed cumulative arrivals")
    if month == 1 and (total[0] != total[2] or total[1] != total[3]):
        raise ValueError("DSEC January monthly and cumulative arrivals do not agree")
    rows = []
    for y, monthly, cumulative in ((year - 1, total[0], total[2]), (year, total[1], total[3])):
        base = macau_observation(y, cumulative, "")
        for frequency, value in (("monthly", monthly), ("ytd", cumulative)):
            rows.append(observation(
                "macau_tourism", "USA", "MAC", "visitors", y, value, base["definition"],
                frequency=frequency, month=month, comparability=base["comparability"],
                notes=base["notes"] + " Direct DSEC table 1 U.S. travel-document row; monthly and "
                "January-to-month count columns, not percentages. Sea + land + air and same-day + overnight "
                "independently reconcile with each published total, for both comparison years."))
        if month == 12:
            rows.append(macau_observation(
                y, cumulative, "Direct DSEC January-December count, not annualized from a shorter period."))
    return validate(rows)


def dsec_recent_visitors(client):
    body, _ = client.get(DSEC_VISITORS)
    publications = json.loads(body)["VisitorArrivals"]["Containers"]["VisitorArrivals"]["LatestPublication"]["Monthly"]
    latest = max(publications, key=lambda p: (int(p["Year"]), int(p["Period"])))
    year, month = int(latest["Year"]), int(latest["Period"])
    now = datetime.now()
    if not 1 <= month <= 12 or (year, month) >= (now.year, now.month):
        raise ValueError("DSEC visitor report is not a completed month")
    files = [f for f in latest["File"] if f["Type"] == ".xlsx" and f["Link"].startswith("/getAttachment/")]
    if len(files) != 1:
        raise ValueError("DSEC latest visitor workbook missing or ambiguous")
    content, asset = client.get(urljoin(DSEC_VISITORS, files[0]["Link"]))
    vintage = f"DSEC Visitor Arrivals {year}-{month:02d}, tables 1-5 and 9"
    return attach(parse_dsec_visitors(content, year, month), asset, vintage), vintage, (
        "Direct monthly and January-to-month counts for U.S.-issued travel documents, not U.S. residents. "
        "The current DSEC country workbook takes priority over a stale MGTO latest-report endpoint. "
        "Matched prior/current-year periods and two independent component controls are verified.")


def parse_early_hong_kong(plain):
    compact = " ".join(plain.split())
    if ("Visitor Arrivals by Country/Territory of Residence" not in compact
            or "1992 1997 1998 1999 2000 2001 2002" not in compact):
        raise ValueError("C&SD historical arrival table or year columns changed")
    match = re.search(r"United States of\s+((?:\d+\s+)+)America", plain)
    groups = match[1].split() if match else []
    if (len(groups) != 15 or any(len(g) != 3 for g in groups[:12])
            or [len(g) for g in groups[12:]] != [1, 3, 3]):
        raise ValueError("C&SD U.S. count row or digit grouping changed")
    return {2000: int("".join(groups[8:10])),
            2001: int("".join(groups[10:12])),
            2002: int("".join(groups[12:]))}


def parse_hong_kong_profile(plain):
    if not re.search(r"MARKET PROFILE\s*:\s*U\.S\.A\.", plain):
        raise ValueError("Expected the U.S. market profile, not another country")
    match = re.search(
        r"Arrivals\s+to\s+Hong\s+Kong(?:\s+SAR)?\s+"
        r"((?:\d[\d,]*\s+){5}\d[\d,]*)(?![\d,])", plain)
    if not match:
        raise ValueError("HKTB six-column Hong Kong arrival row changed")
    return [int(v.replace(",", "")) for v in match[1].split()]


def reviewed_profile(client, year, filename, checksum):
    url = f"{MGTO}/document/CHT/Book/MarketPerformance/{year}/{filename}"
    body, asset = client.get(url)
    if asset["sha256"] != checksum:
        raise ValueError("Reviewed tourism report changed; review the new vintage before importing")
    matches = [p for p in pdf_text(body)
               if re.search(r"MARKET PROFILE\s*:\s*U\.S\.A\.", p)
               and re.search(r"Arrivals\s+to\s+Hong\s+Kong", p)]
    if len(matches) != 1:
        raise ValueError("U.S. market profile missing or ambiguous")
    return matches[0], asset


def hong_kong_history(client):
    body, asset = client.get(HK_DIGEST)
    if asset["sha256"] != "6e1f60cfa1ac0f21a47ddfeee75ebf71bde019e3cabb0daed0301198fa3ff2e7":
        raise ValueError("Reviewed C&SD annual digest changed")
    plain = PdfReader(io.BytesIO(body)).pages[231].extract_text()
    values = {year: (value, asset, "C&SD Annual Digest 2003, table 9.20, printed page 200")
              for year, value in parse_early_hong_kong(plain).items()}
    for edition, filename, checksum in HK_REPORTS:
        plain, asset = reviewed_profile(client, edition, filename, checksum)
        years = list(range(edition - 5, edition + 1))
        if any(str(y) not in plain for y in years):
            raise ValueError("Reviewed annual market-profile years changed")
        for year, value in zip(years, parse_hong_kong_profile(plain)):
            if year > 2022:
                continue
            if year in values and values[year][0] != value:
                raise ValueError("Overlapping Hong Kong residence-arrival vintages disagree")
            values.setdefault(year, (value, asset, f"MGTO Market Performance {edition}; HKTB republication"))
    if set(values) != set(range(2000, 2023)):
        raise ValueError("Hong Kong residence history is not complete for 2000-2022")
    rows = []
    for year, (value, asset, vintage) in values.items():
        row = observation(
            "hktb", "USA", "HKG", "visitors", year, value,
            "HKTB all-mode visitor arrivals attributed to U.S. country of residence, republished by "
            "C&SD/MGTO; not U.S. nationality, unique people or leisure-only tourists",
            comparability="hktb:us_residence:all_mode",
            notes="Historical country-of-residence classification. The retained series changes to the "
            "separately reported nationality classification at 2023; the chart breaks there and no "
            "cross-definition change or index is calculated. The residence-based 2023 count is "
            "594,752, not the retained nationality-based 596,958. Arrival cards ceased on 16 October "
            "2024; C&SD table 650-80001 documents the change to nationality/region. "
            "Official republications only; original reports are not redistributed.")
        rows.extend(attach([row], asset, vintage))
    for year, filename, checksum in HK_HALVES:
        plain, asset = reviewed_profile(client, year, filename, checksum)
        if f"{year} Jan-Jun" not in plain:
            raise ValueError("Hong Kong matched first-half caption changed")
        row = observation(
            "hktb", "USA", "HKG", "visitors", year, parse_hong_kong_profile(plain)[-1],
            "HKTB all-mode U.S.-nationality visitor arrivals, republished by MGTO; not the historical "
            "U.S.-residence classification or NTTO air-travel estimates",
            frequency="ytd", month=6, comparability="hktb:us_nationality:all_mode",
            notes="Direct January-June total in the U.S. market profile's Hong Kong comparison row; "
            "not inferred from rounded growth rates, Macau arrivals, or survey estimates. "
            "2025 and 2026 cover the same six months. The report's 2024 annual count differs by one "
            "from the retained HKTDC vintage; no retained annual observation is overwritten.")
        rows.extend(attach([row], asset, f"MGTO Market Performance {year} Jan-Jun; HKTB republication"))
    return validate(rows)


def top_ten_halves(content):
    reader = PdfReader(io.BytesIO(content))
    if len(reader.pages) != 1:
        raise ValueError("Expected a single-page MGTO monthly source-market report")
    lines = reader.pages[0].extract_text(extraction_mode="layout").splitlines()
    split = max(map(len, lines), default=0) // 2
    if not split:
        raise ValueError("MGTO source-market PDF has no extractable layout")
    return ["\n".join(line[:split] for line in lines),
            "\n".join(line[split:] for line in lines)]


def parse_top_ten(halves, year, month):
    label = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1]
    values = {}
    for index, (frequency, plain) in enumerate(zip(("monthly", "ytd"), halves)):
        caption = (rf"{year}\s+{label}" if index == 0 else
                   rf"{year}\s+Jan\s*-\s*{label}")
        if not re.search(caption, plain):
            raise ValueError("MGTO monthly/cumulative report columns or period caption changed")
        lines = plain.splitlines()
        matches = [i for i, line in enumerate(lines) if line.strip() == "United States of America"]
        if len(matches) > 1:
            raise ValueError("U.S. source-market row is ambiguous")
        if matches:
            match = re.search(r"(\d[\d,]*)\s*$", lines[matches[0] - 1]) if matches[0] else None
            if not match:
                raise ValueError("U.S. country row has no aligned count")
            values[frequency] = int(match[1].replace(",", ""))
    if "monthly" in values and "ytd" in values and values["monthly"] > values["ytd"]:
        raise ValueError("Monthly Macau arrivals exceed the cumulative total")
    if month == 1 and len(values) == 2 and values["monthly"] != values["ytd"]:
        raise ValueError("January monthly and cumulative Macau counts must agree")
    return values


def parse_macau_months(plain):
    if "VISITOR ARRIVALS FROM U.S.A." not in plain:
        raise ValueError("Expected the complete U.S. monthly Macau profile")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    result = {}
    pattern = (r"^[^\d\n]*?(" + "|".join(months) + r")\s+"
               r"(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)")
    for match in re.finditer(pattern, plain, re.MULTILINE):
        month = months.index(match[1]) + 1
        sea, land, air, total = [int(match[i].replace(",", "")) for i in range(2, 6)]
        if month in result or sea + land + air != total:
            raise ValueError("Macau monthly sea/land/air counts do not reconcile")
        result[month] = total
    if set(result) != set(range(1, 7)):
        raise ValueError("Expected all six directly reported Macau monthly counts")
    return result


def parse_early_macau(header, continuation, years=(2001, 2002)):
    compact = " ".join(header.split())
    if ("TABLE 1 : VISITOR ARRIVALS BY PLACE OF RESIDENCE" not in compact
            or " ".join(map(str, years * 4)) not in compact):
        raise ValueError("DSEC residence table or paired year columns changed")
    lines = continuation.splitlines()
    matches = [i for i, line in enumerate(lines) if line.strip() == "United States of America"]
    if len(matches) != 1 or matches[0] < 2:
        raise ValueError("DSEC U.S. residence row missing or ambiguous")
    fields = re.split(r"\s{2,}", lines[matches[0] - 2].strip())
    columns = (1, 2, 3, 4, 5, 6, 7, 9)
    if len(fields) != 12 or any(
            not re.fullmatch(r"\d{1,3}(?:[ ,]\d{3})*", fields[i]) for i in columns):
        raise ValueError("DSEC country counts, shares or transport columns changed")
    counts = [int(fields[i].replace(" ", "").replace(",", "")) for i in columns]
    for i in (0, 1):
        if sum(counts[i:6:2]) != counts[6 + i]:
            raise ValueError("DSEC sea, land and air arrivals do not reconcile with total")
    return dict(zip(years, counts[6:]))


def macau_history(client):
    body, asset = client.get(MACAU_2002)
    if asset["sha256"] != "e3ab0b4ae3b1e0a5283406f1e8609701e11bd4c6ba2f12650f5ea374168f2eef":
        raise ValueError("Reviewed DSEC Tourism Statistics 2002 report changed")
    pages = PdfReader(io.BytesIO(body)).pages
    values = parse_early_macau(pages[52].extract_text(),
                              pages[53].extract_text(extraction_mode="layout"))
    rows = [macau_observation(
        year, value,
        "DSEC Tourism Statistics 2002, table 1, physical pages 53-54; directly published "
        "all-mode residence totals. Sea + land + air reconciles in each year. Not table 12 "
        "nationality counts, sea-only arrivals, package tours, or combined U.S./Canada hotel "
        "guests. This pre-2008 population includes non-resident workers and students.")
        for year, value in values.items()]
    rows = attach(rows, asset, "DSEC Tourism Statistics 2002, table 1; 2001 and 2002")
    body, asset = client.get(MACAU_2001)
    if asset["sha256"] != "4e5b552ed0e07c87ff0244b4953ae38d761e0f090165a93320e8712719d0ee22":
        raise ValueError("Reviewed DSEC Tourism Statistics 2001 report changed")
    page = PdfReader(io.BytesIO(body)).pages[54]
    earlier = parse_early_macau(page.extract_text(), page.extract_text(extraction_mode="layout"),
                                years=(2000, 2001))
    if earlier[2001] != values[2001]:
        raise ValueError("Independent DSEC annual reports disagree on the 2001 residence total")
    row = macau_observation(
        2000, earlier[2000],
        "DSEC Tourism Statistics 2001, table 1, PDF/printed page 55; directly reported "
        "U.S.-resident all-mode arrivals. Sea 52708 + land 16550 + air 5095 equals total "
        "74353. The 2001 overlap 73607 reconciles with the independent 2002 report. "
        "Not nationality, package tours, overnight-only arrivals or combined U.S./Canada "
        "hotel guests. This pre-2008 population includes non-resident workers and students.")
    return rows + attach([row], asset, "DSEC Tourism Statistics 2001, table 1; 2000 with independent 2001 overlap")


def macau_recent(client):
    rows = macau_history(client)
    for year, last_month in ((2025, 12), (2026, 8)):
        for month in range(1, last_month + 1):
            url = (f"{MGTO}/Publication/Report/TopTenVisitorSourceMarkets"
                   f"?year={year}&month={month}&lang=E")
            body, asset = client.get(url)
            for frequency, value in parse_top_ten(top_ten_halves(body), year, month).items():
                base = macau_observation(year, value, "")
                row = observation(
                    "macau_tourism", "USA", "MAC", "visitors", year, value,
                    base["definition"], frequency=frequency, month=month,
                    comparability=base["comparability"],
                    notes=base["notes"] + " Direct MGTO/DSEC top-ten source-market table; monthly "
                    "and January-to-month cumulative columns are read separately by PDF coordinates, "
                    "not row rank, percentages, or subtraction of rounded figures. A country absent "
                    "from a top-ten column is unreported, not zero.")
                rows.extend(attach([row], asset, f"MGTO/DSEC {year}-{month:02d} monthly and cumulative arrivals"))
    reviewed = {key(r): r for r in rows}
    for year, filename, checksum in HK_HALVES:
        plain, asset = reviewed_profile(client, year, filename, checksum)
        if f"{year} Jan-Jun" not in plain:
            raise ValueError("Macau first-half report caption changed")
        body, _ = client.get(asset["request_url"])
        pages = [p for p in pdf_text(body) if "VISITOR ARRIVALS FROM U.S.A." in p]
        if len(pages) != 1:
            raise ValueError("Complete U.S. monthly profile is missing or ambiguous")
        for month, value in parse_macau_months(pages[0]).items():
            base = macau_observation(year, value, "")
            row = observation(
                "macau_tourism", "USA", "MAC", "visitors", year, value, base["definition"],
                frequency="monthly", month=month, comparability=base["comparability"],
                notes=base["notes"] + " Direct U.S. monthly profile in the first-half report; "
                "sea + land + air equals the published total. This complete country profile "
                "fills source-market top-ten omissions without inventing a zero or deriving "
                "a month from cumulative counts.")
            row = attach([row], asset, f"MGTO Market Performance {year} Jan-Jun; U.S. monthly profile")[0]
            if key(row) in reviewed and reviewed[key(row)]["value"] != value:
                raise ValueError("Overlapping Macau monthly source vintages disagree")
            reviewed.setdefault(key(row), row)
    current, current_vintage, current_notes = dsec_recent_visitors(client)
    for row in current:
        if key(row) in reviewed and reviewed[key(row)]["value"] != row["value"]:
            raise ValueError("DSEC and MGTO overlapping visitor counts disagree")
        reviewed.setdefault(key(row), row)
    rows = validate(list(reviewed.values()))
    latest = max((r for r in rows if r["frequency"] == "ytd"), key=lambda r: r["period"])
    if not any(r["year"] == latest["year"] - 1 and r["frequency"] == "ytd"
               and r["period"].endswith(latest["period"][-3:]) for r in rows):
        raise ValueError("Matching latest Macau cumulative periods are required")
    complete = {r["period"]: r["value"] for r in rows
                if r["year"] == 2025 and r["frequency"] == "monthly"}
    december = next((r["value"] for r in rows if r["period"] == "2025-12" and r["frequency"] == "ytd"), None)
    if len(complete) != 12 or sum(complete.values()) != december:
        raise ValueError("Complete 2025 Macau monthly counts must reconcile with December cumulative total")
    return rows, "DSEC 2000-2002; full monthly 2025; " + current_vintage, (
        "Direct 2025/2026 monthly and cumulative source-market tables, supplemented by complete U.S. "
        "first-half profiles when a monthly top-ten row is absent; travel-document issuing place, "
        "not U.S. residence. All twelve 2025 monthly counts reconcile with the December cumulative total. "
        f"{current_notes} "
        "Original DSEC 2001/2002 table 1 restores 2000-2002 all-mode residence "
        "arrivals before the 2008 worker/student exclusion. Other annual history retained.")
