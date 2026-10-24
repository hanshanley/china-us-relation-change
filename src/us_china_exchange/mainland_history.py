"""Reviewed historical U.S.-nationality student counts in mainland China."""

import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from .model import key, observation, validate
from .sources import attach


TIAN_HISTORY = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7088380/fullTextXML"
TIAN_SHA256 = "9f7e459b024ee9d24b6b2bbde0d7ec681ffe6a4d801cce9f3a5025ebb9631c0e"
UNIVERSITY_2017 = "https://fzgh.xawl.edu.cn/info/1130/1873.htm"
UNIVERSITY_SHA256 = "ca3a7419cafca3fccd532e12872fb4d23551ead0f481e2954889317bdcbdc123"


def parse_tian_history(content):
    root = ET.fromstring(content)
    if root.findtext(".//article-id[@pub-id-type='doi']") != "10.1007/s10734-020-00522-5":
        raise ValueError("Historical student article identity changed")
    table = root.find(".//table-wrap[@id='Tab3']")
    if table is None or table.findtext("label") != "Table 3":
        raise ValueError("Historical student country table missing")
    caption = table.find("caption")
    if caption is None or "top 10 countries" not in " ".join(caption.itertext()):
        raise ValueError("Historical student table population changed")
    records = [[" ".join("".join(c.itertext()).split()) for c in row]
               for row in table.findall(".//tr")]
    expected_header = ["Year Rank", ""] + [f"Top {i}" for i in range(1, 11)]
    if not records or records[0] != expected_header or len(records[1:]) % 2:
        raise ValueError("Historical student country/count columns changed")
    result = {}
    for countries, counts in zip(records[1::2], records[2::2]):
        if (len(countries) != 12 or len(counts) != 12
                or not re.fullmatch(r"\d{4}", countries[0])
                or countries[1] != "country" or counts[:2] != ["", "student number"]):
            raise ValueError("Historical student country/count rows changed")
        year = int(countries[0])
        if not 2000 <= year <= 2015:
            continue
        if countries.count("USA") != 1 or year in result:
            raise ValueError("Historical U.S. country/year missing or duplicated")
        value = counts[countries.index("USA")]
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", value):
            raise ValueError("Historical U.S. exact student count missing")
        result[year] = int(value.replace(",", ""))
    if set(result) != set(range(2000, 2016)):
        raise ValueError("Reviewed historical student periods incomplete")
    return result


def parse_university_2017(content):
    plain = " ".join(BeautifulSoup(content, "html.parser").get_text(" ", strip=True).split())
    pattern = (r"2017\s*\u5e74\u7684\u6570\u636e\u663e\u793a\uff0c"
               r"\u6765\u534e\u7559\u5b66\u7684\u7f8e\u56fd\u5b66\u751f\u4e3a"
               r"\s*(\d+(?:,\d{3})*)\s*\u4eba")
    matches = re.findall(pattern, plain)
    if len(matches) != 1 or "\u5218\u732e\u541b" not in plain:
        raise ValueError("University republication author, year or U.S. count changed")
    return int(matches[0].replace(",", ""))


def mainland_history(client, prior):
    existing = {key(r): r for r in prior}
    controls = {r["year"]: r for r in prior if r["source_id"] == "moe"
                and (r["origin"], r["destination"], r["measure"]) == ("USA", "CHN", "enrolled_students")}
    if not set(range(2006, 2017)) | {2018} <= set(controls):
        raise ValueError("Independent mainland student history controls missing")
    body, historical_asset = client.get(TIAN_HISTORY)
    if historical_asset["sha256"] != TIAN_SHA256:
        raise ValueError("Reviewed historical student article changed")
    values = parse_tian_history(body)
    if any(values[y] != controls[y]["value"] for y in range(2006, 2016)):
        raise ValueError("Scholarly history conflicts with an independently retained MOE count")
    body, university_asset = client.get(UNIVERSITY_2017)
    if university_asset["sha256"] != UNIVERSITY_SHA256:
        raise ValueError("Reviewed university student republication changed")
    latest = parse_university_2017(body)
    base = controls[2018]
    candidates = [(y, values[y], historical_asset) for y in range(2000, 2006)]
    candidates.append((2017, latest, university_asset))
    for year, value, asset in candidates:
        if year == 2017:
            vintage = "Liu Xianjun; China Association of Higher Education, university republication; 2017 count"
            detail = (
                "Xi'an University hosts Liu Xianjun's retrospective scholarly account, attributed to "
                "the China Association of Higher Education. Its internationalization section explicitly "
                "dates the U.S.-nationality total to 2017. A scholarly republication, not a newly "
                "retrieved original MOE statistical table. Includes degree and non-degree study.")
        else:
            vintage = "Tian and Liu, Higher Education 81 (2021), published online 2020; Table 3"
            detail = (
                "Selected numerical fact from the original scholarly article's republication of "
                "MOE country statistics, obtained via the public Europe PMC XML service. All ten "
                "2006-2015 overlaps reconcile with the independently retained MOE history. Only "
                "explicitly dated 2000-2015 rows were reviewed for use: the source's conflicting "
                "2016 count and mislabelled later periods are not imported or silently corrected.")
        row = observation(
            "moe", "USA", "CHN", "enrolled_students", year, value, base["definition"],
            period_basis=base["period_basis"], comparability=base["comparability"],
            notes=detail + " Reporting-year participation, not departures or a point-in-time physical "
            "stock. No exact within-year dates invented. Original article text and artwork are not redistributed.")
        row = attach([row], asset, vintage)[0]
        if key(row) in existing and existing[key(row)]["value"] != value:
            raise ValueError("Mainland history conflicts with a retained observation")
        existing.setdefault(key(row), row)
    return validate(list(existing.values()))
