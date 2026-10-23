"""Reviewed government republications of bilateral visitor statistics."""

import io
import re

from pypdf import PdfReader

from .language_sources import pdf_text
from .model import key, observation, validate
from .sources import attach, macau_observation


MGTO = "https://dataplus.macaotourism.gov.mo"
HK_DIGEST = "https://www.statistics.gov.hk/pub/B10100032003AN03B0600.pdf"
MACAU_2002 = (
    "https://www.dsec.gov.mo/getAttachment/8c86dc19-36cc-4a05-8133-5470c143c09b/"
    "P_TUR_PUB_2002_Y.aspx")
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
            "cross-definition 2020 change or index is calculated. The residence-based 2023 count is "
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


def parse_early_macau(header, continuation):
    compact = " ".join(header.split())
    if ("TABLE 1 : VISITOR ARRIVALS BY PLACE OF RESIDENCE" not in compact
            or "2001 2002 2001 2002 2001 2002 2001 2002" not in compact):
        raise ValueError("DSEC residence table or paired year columns changed")
    lines = continuation.splitlines()
    matches = [i for i, line in enumerate(lines) if line.strip() == "United States of America"]
    if len(matches) != 1 or matches[0] < 2:
        raise ValueError("DSEC U.S. residence row missing or ambiguous")
    fields = re.split(r"\s{2,}", lines[matches[0] - 2].strip())
    columns = (1, 2, 3, 4, 5, 6, 7, 9)
    if len(fields) != 12 or any(
            not re.fullmatch(r"\d{1,3}(?: \d{3})*", fields[i]) for i in columns):
        raise ValueError("DSEC country counts, shares or transport columns changed")
    counts = [int(fields[i].replace(" ", "")) for i in columns]
    for i in (0, 1):
        if sum(counts[i:6:2]) != counts[6 + i]:
            raise ValueError("DSEC sea, land and air arrivals do not reconcile with total")
    return {2001: counts[6], 2002: counts[7]}


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
    return attach(rows, asset, "DSEC Tourism Statistics 2002, table 1; 2001 and 2002")


def macau_recent(client):
    rows = macau_history(client)
    for year in (2025, 2026):
        for month in range(1, 9):
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
    rows = validate(list(reviewed.values()))
    if not all(any(r["year"] == y and r["frequency"] == "ytd" and r["period"].endswith("-08")
                   for r in rows) for y in (2025, 2026)):
        raise ValueError("Matching latest Macau cumulative periods are required")
    return rows, "DSEC 2001-2002 residence history; MGTO/DSEC monthly/YTD through August 2026", (
        "Direct 2025/2026 monthly and cumulative source-market tables, supplemented by complete U.S. "
        "first-half profiles when a monthly top-ten row is absent; travel-document issuing place, "
        "not U.S. residence. Original DSEC 2002 table 1 restores 2001/2002 all-mode residence "
        "arrivals before the 2008 worker/student exclusion. Other annual history retained.")
