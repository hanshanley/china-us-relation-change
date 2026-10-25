"""Reviewed bilateral opinion aggregates, with survey measures kept separate."""

import csv
import io
import json
import math
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .model import digest


PEW_TREND = "https://www.pewresearch.org/short-reads/2026/04/14/americans-views-of-china-have-grown-somewhat-more-positive-in-recent-years/"
GALLUP_HISTORY = "https://news.gallup.com/file/poll/703046/260312CountryRatings.pdf"
PEW_AGE = "https://www.pewresearch.org/wp-content/uploads/sites/20/2026/07/pg_2026.06.15_global-views-china-2026_report.pdf"
PEW_WARMTH = "https://www.pewresearch.org/wp-content/uploads/sites/20/2026/09/SR_26.09.23_views-of-china_topline.pdf"
PEW_CHINA = "https://www.pewresearch.org/global/wp-content/uploads/sites/2/2016/10/Pew-Research-Center-China-Report-FINAL-October-5-2016.pdf"
PEW_CHINA_EARLY = "https://www.pewresearch.org/global/wp-content/uploads/sites/2/2006/09/GAP-Asia-report-final-9-21-06.pdf"
PEW_CHINA_2005_METHODS = "https://www.pewresearch.org/wp-content/uploads/sites/2/pdf/249.pdf"
BAS_HISTORY = "https://www.rsis.edu.sg/wp-content/uploads/rsis-pubs/WP50.pdf"
BAS_METHODS = {
    1998: ("3N1P6O", "1998-12", "1999-01", 756),
    1999: ("8UIWTY", "1999-12", "2000-01", 712),
    2000: ("OXOAFT", "2000-12", "2001-01", 757),
    2001: ("ARBTMK", "2001-12", "2002-02", 615),
    2002: ("YD54UB", "2002-12", "2003-01", 662),
}
C100_CHINA_2007 = "https://www.committee100.org/wp-content/uploads/2017/01/2007-C-100_EN_Survey.pdf"
C100_AGE_2017 = "https://www.committee100.org/wp-content/uploads/2017/01/C100-Public-Opinion-Survey-2017.pdf"
C100_AGE_2017_CHINESE = "https://www.committee100.org/wp-content/uploads/2017/01/C100-Public-Opinions-Survey-2017-Chinese.pdf"
C100_AGE_BINS = ("General Population", "18-34", "35-49", "50+")
C100_AGE_QUALIFICATION = (
    "Literal source-reported Q1.2 age labels, not verified underlying coding or harmonized cohorts. "
    "Question bins are18-34/35-49/50+; English U.S. profile instead prints18-34/35-54/55+ "
    "and Chinese profile literally prints18-34/45-54/55+. No silent correction or rebinning. "
    "Age and item denominators are unknown; hidden/unprinted not-sure values are not reconstructed.")
C100_CHINA_DATE_CONFLICT = (
    "Cross-year round ending in January2017, not a single-calendar-year survey. "
    "English summary reports2016-12-06/2017-01-09; both country appendices report2016-12-12/2017-01-09; "
    "Chinese overall table reports2016-12-06/2017-01-08; Chinese introduction gives a combined "
    "2016-11-18/2016-12-23 window. No exact-day interval is selected; both canonical date fields "
    "remain unknown. Full-wave n3696 is not an age or item base.")
C100_AGE_SAMPLING = {
    "c100_reported_age_2007": "Publisher-described national ages18-60; seven cities/seven towns/ten villages.",
    "c100_reported_age_us": "U.S.18+; weighted landline/cell telephone.",
    "c100_reported_age_china": "China18+;70PSUs;face-to-face;excludes Tibet/Xinjiang/Hong Kong/Macao/Taiwan."}
PULSE_REPORT = "https://uscnpm.org/wp-content/uploads/2026/10/CHINA.PULSE_.Chinese.Public.Supports.Trade_.and_.Security.Cooperation.Still_.Sees_.the_.United.States.as_.a.Threat.pdf"
PULSE_DATA = "https://datawrapper.dwcdn.net/LU2Fb/1/dataset.csv"
REVIEWED_PATH = "data/reviewed/opinion-warmth.json"
UNITS = {"favorability": "percent", "warmth": "rating_points"}
AGE_GROUPS = {"pew_age": ("18-34", "35-49", "50+"),
              "pulse_age": ("18-29", "30-39", "40-49", "50+"),
              "pew_warmth_age": ("18-49", "50+")}


def normalize(value):
    return " ".join(str(value).replace("\xa0", " ").split())


def parse_pew_trend(body):
    headers = ["Date", "Label", "Phone trend Favorable", "Phone trend Unfavorable",
               "ATP Favorable", "ATP Unfavorable"]
    tables = BeautifulSoup(body, "html.parser").select("table")
    selected = [t for t in tables if [normalize(c.text) for c in t.select("tr")[0].find_all(["th", "td"])] == headers]
    if len(selected) != 1:
        raise ValueError("Pew opinion trend table missing or ambiguous")
    result = []
    for tr in selected[0].select("tr")[1:]:
        cells = [normalize(c.text) for c in tr.find_all(["th", "td"])]
        if len(cells) != 6 or not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", cells[0]):
            raise ValueError("Pew opinion trend columns changed")
        year = int(cells[0].split("/")[-1])
        for mode, columns in (("phone", (2, 3)), ("atp", (4, 5))):
            values = [cells[i] for i in columns]
            if not any(values):
                continue
            if not all(re.fullmatch(r"\d+%", v) for v in values):
                raise ValueError("Missing Pew favorability cannot become zero")
            result.append({"year": year, "period": cells[1], "mode": mode,
                           "favorable": int(values[0][:-1]), "unfavorable": int(values[1][:-1])})
    if not result or {r["mode"] for r in result} != {"phone", "atp"}:
        raise ValueError("Separate Pew phone and panel histories required")
    return result


def parse_gallup_history(body):
    pages = [page.extract_text() for page in PdfReader(io.BytesIO(body)).pages]
    if not any("telephone interviews conducted February 2-16, 2026" in page for page in pages):
        raise ValueError("Gallup survey mode or reference dates changed")
    selected = [page for page in pages if re.search(r"\bD\.\s+China\b", page)]
    if len(selected) != 1 or not all(label in normalize(selected[0]) for label in
                                   ("Total favorable", "Total unfavorable", "Asked of half sample")):
        raise ValueError("Gallup China history table missing or ambiguous")
    result = []
    pattern = (r"^(\d{4})\s+([A-Z][a-z]{2})\s+(\d{1,2})-(\d{1,2})\s*(\^)?\s+"
               r"((?:(?:\d+|\*)\s+){6}(?:\d+|\*))\s*$")
    for line in selected[0].splitlines():
        match = re.fullmatch(pattern, line.strip())
        if not match:
            if re.match(r"^20\d{2}\b", line.strip()):
                raise ValueError("Gallup historical date or response columns changed")
            continue
        year = int(match[1])
        if year < 2000:
            continue
        values = match[6].split()
        if not all(value.isdigit() for value in values[-2:]):
            raise ValueError("Gallup net percentages must be reported, not inferred")
        start = datetime.strptime(f"{year} {match[2]} {match[3]}", "%Y %b %d").date()
        end = datetime.strptime(f"{year} {match[2]} {match[4]}", "%Y %b %d").date()
        if start > end or any(not 0 <= int(value) <= 100 for value in values if value != "*"):
            raise ValueError("Invalid Gallup survey dates or percentages")
        result.append({"year": year, "period": f"{match[2]} {match[3]}-{match[4]}, {year}",
                       "field_start": start.isoformat(), "field_end": end.isoformat(),
                       "favorable": int(values[-2]), "unfavorable": int(values[-1]),
                       "half_sample": bool(match[5])})
    dates = [row["field_start"] for row in result]
    if (not result or len(set(dates)) != len(dates)
            or not set(range(2000, 2027)).issubset(row["year"] for row in result)):
        raise ValueError("Gallup history requires distinct polls and every year from 2000 to 2026")
    return sorted(result, key=lambda row: row["field_start"])


def parse_pew_age(body):
    pages = [p.extract_text() for p in PdfReader(io.BytesIO(body)).pages]
    pages = [p for p in pages if "Views of China by age" in p]
    if len(pages) != 1:
        raise ValueError("Pew opinion age-table page missing or ambiguous")
    match = re.search(r"U\.S\.\s+Favorable\s+(\d+)%?\s+(\d+)%?\s+(\d+)%?"
                      r"[^\n]*\n\s*Unfavorable\s+(\d+)\s+(\d+)\s+(\d+)", pages[0])
    if not match:
        raise ValueError("Pew U.S. age table missing; do not substitute global or leader opinions")
    return {age: {"favorable": int(match[i + 1]), "unfavorable": int(match[i + 4])}
            for i, age in enumerate(AGE_GROUPS["pew_age"])}


def parse_china_history(body):
    pages = [" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(body)).pages]
    pages = [p for p in pages if "Fluctuating views of the U.S." in p]
    if len(pages) != 1:
        raise ValueError("Historical China favorability figure missing")
    match = re.search(r"www\.pewresearch\.org ((?:\d+\s+){20})0 80 "
                      r"((?:20\d{2}\s+){10})Favorable Unfavorable", pages[0])
    if not match:
        raise ValueError("Published Chinese net favorability figure changed")
    values, years = list(map(int, match[1].split())), list(map(int, match[2].split()))
    if years != list(range(2007, 2017)):
        raise ValueError("Historical China survey rounds changed")
    return [{"year": year, "favorable": values[i], "unfavorable": values[i + 10]}
            for i, year in enumerate(years)]


def parse_early_china_history(body, methods_body):
    def pages(content):
        return [(p.extract_text() or "").replace("\u2013", "-").replace("\u2014", "-")
                for p in PdfReader(io.BytesIO(content)).pages]

    report, methods = pages(body), pages(methods_body)
    tables = [p for p in report if all(t in normalize(p) for t in
              ("Spring 2006 Survey", "Q.2", "a. The United States", "FAVORABLE", "UNFAVORABLE"))]
    if len(tables) != 1:
        raise ValueError("Early Pew China estimates require the original U.S.-opinion topline")
    numbers = r"(\d+(?:[ \t]+\d+){6})=100"
    matches = re.findall(r"^[ \t]*China[ \t]+" + numbers
                         + r"[ \t]*\n[ \t]*May,[ \t]*2005[ \t]+" + numbers
                         + r"[ \t]*(?:\n|$)", tables[0], re.M)
    if len(matches) != 1:
        raise ValueError("Early Pew China response rows missing or ambiguous")
    responses = {year: list(map(int, text.split()))
                 for year, text in zip((2006, 2005), matches[0])}
    if any(not 0 <= value <= 100 for values in responses.values() for value in values):
        raise ValueError("Invalid early Pew response percentages")

    current = [normalize(p) for p in report
               if "Methodological Appendix" in p and "Country: China" in p]
    earlier = [normalize(p) for p in methods if "ABOUT THE SURVEY" in p]
    if len(current) != 1 or len(earlier) != 1:
        raise ValueError("Both early Pew China sampling methods are required")
    china = current[0].split("Country: China", 1)[1].split("Country: India", 1)[0]
    if not all(t in china for t in (
            "Probability sample in six cities and surrounding rural areas",
            "Shanghai, Beijing, Guangzhou, Xinxiang, Jinzhong, and Luzhou",
            "Face-to-face adults 18 to 60", "April 7-18, 2006",
            "Sample size: 2180", "Disproportionately urban")):
        raise ValueError("Pew 2006 China age, coverage, dates or sample changed")
    if not all(t in earlier[0] for t in (
            "probability sample of 2,191", "six major cities and their surrounding rural areas",
            "Beijing, Chengdu, Guangzhou, Shanghai, Shenyang, and Wuhan",
            "not representative of the entire country", "adults ages 18-60")):
        raise ValueError("Pew 2005 China age, coverage or sample changed")
    if not any("China: May 21-31, 2005 (N=2,191)" in normalize(p) for p in methods):
        raise ValueError("Pew 2005 China fieldwork must match the original topline")

    result = []
    for year, start, end, n, cities in (
            (2005, "2005-05-21", "2005-05-31", 2191,
             "Beijing, Chengdu, Guangzhou, Shanghai, Shenyang and Wuhan"),
            (2006, "2006-04-07", "2006-04-18", 2180,
             "Shanghai, Beijing, Guangzhou, Xinxiang, Jinzhong and Luzhou")):
        values = responses[year]
        result.append(dict(year=year, field_start=start, field_end=end, n_total=n,
                           cities=cities, favorable=values[0], unfavorable=values[3]))
    return result


def parse_beijing_history(body):
    pages = [normalize(p.extract_text(extraction_mode="layout") or "") for p in PdfReader(io.BytesIO(body)).pages]
    methods = [p for p in pages if "The Beijing Area Study Survey" in p]
    footnotes = [p for p in pages if "100 degree feeling thermometer" in p]
    if len(methods) != 1 or len(footnotes) != 1:
        raise ValueError("Original Beijing survey methods and thermometer footnote required")
    if not all(token in methods[0] for token in (
            "survey of Beijing citizens", "probability proportional to size",
            "face-to-face", "December or January", "sample size was 757",
            "2001 sample size was 615", "2002 the sample size was 662")):
        raise ValueError("Historical Beijing population, method or wave sample changed")
    text = footnotes[0].split("100 degree feeling thermometer", 1)[1].split("This volatility", 1)[0]
    if "towards the US" not in text:
        raise ValueError("Beijing thermometer must concern the United States")
    result = []
    for clause in re.split(r";|,\s*and rose", text):
        numbers = [int(n) for n in re.findall(r"\b\d+\b", clause)]
        years = [n for n in numbers if 1998 <= n <= 2002]
        values = [n for n in numbers if 0 <= n <= 100]
        if len(years) != 1 or len(values) != 1 or len(numbers) != 2:
            raise ValueError("Ambiguous historical Beijing thermometer observation")
        result.append(dict(year=years[0], value=values[0], approximate="around" in clause))
    if [r["year"] for r in result] != list(range(1998, 2003)):
        raise ValueError("Five distinct original Beijing survey waves required")
    return result


def beijing_methods_url(year):
    return ("https://opendata.pku.edu.cn/dataset.xhtml?persistentId=doi%3A10.18170%2FDVN%2F"
            + BAS_METHODS[year][0])


def parse_beijing_methods(body, year):
    if year not in BAS_METHODS:
        raise ValueError("Only the reviewed early Beijing waves may qualify this archive")
    soup = BeautifulSoup(body, "html.parser")
    fields = {}
    for panel in soup.select(".metadata-panel-body"):
        for group in panel.select("div.form-group"):
            label = group.find("label", recursive=False)
            if label is not None:
                key = label.get_text(" ", strip=True)
                value = normalize(" ".join(child.get_text(" ", strip=True)
                                          for child in group.find_all("div", recursive=False)))
                fields.setdefault(key, []).append(value)

    def field(label):
        values = fields.get(label, [])
        if len(values) != 1 or not values[0]:
            raise ValueError("Original Beijing method field missing or ambiguous: " + label)
        return values[0]

    doi, start, end, total = BAS_METHODS[year]
    if (field("Dataset Persistent ID") != "doi:10.18170/DVN/" + doi
            or "Beijing Area Study" not in field("Title") or str(year) not in field("Title")):
        raise ValueError("Original Beijing dataset identity or wave changed")
    if field("Date of Collection") != "Start: " + start + " ; End: " + end:
        raise ValueError("Beijing collection months changed; do not invent exact days")
    universe = re.sub(r"\s+", "", field("\u603b\u4f53\u4eba\u7fa4"))
    if not all(token in universe for token in (
            "18\u5c81\u81f365\u5c81", "\u5317\u4eac\u5e02\u6b63\u5f0f\u7684\u975e\u519c\u4e1a\u6237\u53e3",
            "\u6709\u56fa\u5b9a\u4f4f\u6240", "\u516b\u4e2a\u5e02\u533a",
            "\u4e1c\u57ce", "\u897f\u57ce", "\u5d07\u6587", "\u5ba3\u6b66",
            "\u671d\u9633", "\u4e30\u53f0", "\u77f3\u666f\u5c71", "\u6d77\u6dc0")):
        raise ValueError("Beijing age, fixed-residence, urban-district or hukou frame changed")
    count = re.search(r"\u6709\u6548\u6837\u672c\u6570\u4e3a(\d+)\u4e2a", field("\u5e94\u7b54\u7387"))
    if count is None or int(count[1]) != total:
        raise ValueError("Original Beijing whole-wave sample changed")
    if (not all(token in field("\u62bd\u6837\u65b9\u6cd5") for token in ("PPS", "\u5206\u4e24\u9636\u6bb5"))
            or "\u9762\u8bbf" not in field("\u6536\u96c6\u6a21\u5f0f")
            or not all(token in field("\u6743\u91cd") for token in ("WEIGHT", "PSU"))):
        raise ValueError("Original Beijing sampling, interview mode or weight documentation changed")
    published = field("Publication Date")
    date.fromisoformat(published)
    return dict(start_month=start, end_month=end, n_total=total, metadata_published=published)


def parse_c100_china_2007(body):
    pages = [normalize(p.extract_text() or "") for p in PdfReader(io.BytesIO(body)).pages]
    tables = [p for p in pages if all(token in p for token in (
        "General Feelings", "(CHINA SURVEY) How would you describe your impressions of the U.S.?",
        "US Survey China Survey", "Congressional Staffers",
    ))]
    methods = [p for p in pages if "The survey of China was self-sponsored" in p]
    if len(tables) != 1 or len(methods) != 1 or not any("December 10, 2007" in p for p in pages):
        raise ValueError("Original C100 2007 country-opinion table, release and Chinese methods required")
    header = tables[0].split("US Survey China Survey", 1)[1].split("Very Favorable", 1)[0]
    populations = ("General Public Opinion Leaders Business Leaders Congressional Staffers "
                   "General Public Opinion Leaders Business Leaders")
    if not header.strip().startswith(populations) or re.findall(r"[\u2018'](07|05)", header) != ["07", "05"] * 4 + ["07"] * 3:
        raise ValueError("C100 country, respondent-group or wave columns changed")
    current = methods[0].split("(a) General Public:", 1)
    if len(current) != 2:
        raise ValueError("Chinese general-public sampling paragraph missing")
    current = current[1].split("(b) Opinion Leaders:", 1)[0]
    if not all(token in current for token in (
        "August 18 and September 7, 2007", "face-to-face interviews",
        "4,104 Chinese adults (18-60 years old)", "multi-stage random sampling",
        "seven cities, seven towns, and ten villages", "nationwide, statistically representative",
    )):
        raise ValueError("C100 Chinese general-public dates, age, sample or geography changed")
    responses = {}
    for label, response in (("FAVORABLE", "favorable"), ("UNFAVORABLE", "unfavorable"),
                            ("Not Sure", "not_sure")):
        match = re.search(r"(?<![A-Za-z])" + re.escape(label)
                          + r"\s+((?:\d+\s+){10}\d+)(?!\d)", tables[0])
        if not match:
            raise ValueError("C100 published response totals missing; do not derive a remainder")
        values = list(map(int, match[1].split()))
        if any(not 0 <= value <= 100 for value in values):
            raise ValueError("Invalid C100 response percentage")
        responses[response] = values[8]
    return responses


def parse_pulse(body):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")), delimiter="\t")
    if reader.fieldnames != ["Topic", "Fall/Winter 2025", "Spring/Summer 2026", "Demographic"]:
        raise ValueError("China Pulse wave labels or columns changed")
    selected = [r for r in reader if r["Demographic"] in {"Overall", "Age"}]
    if (len(selected) != 5 or sum(r["Demographic"] == "Overall" for r in selected) != 1
            or {r["Topic"] for r in selected if r["Demographic"] == "Age"} != set(AGE_GROUPS["pulse_age"])):
        raise ValueError("China Pulse population or age bands changed")
    for row in selected:
        for wave in ("Fall/Winter 2025", "Spring/Summer 2026"):
            if not re.fullmatch(r"\d+(?:\.\d+)?", row[wave]):
                raise ValueError("Missing China Pulse means cannot become zero")
            value = float(row[wave])
            row[wave] = int(value) if value.is_integer() else value
    return selected


def parse_c100_age_panel(events, visible_text):
    compact = re.sub(r"\s+", "", visible_text)
    if any(phrase not in compact for phrase in (
            "2017GENERALPUBLICAGEBREAKDOWN", "18-34", "35-49", "50+",
            "HowwouldyoudescribeyourimpressionofChina?",
            "HowwouldyoudescribeyourimpressionoftheU.S.?")):
        raise ValueError("Changed C100 question, country or literal age bins")
    selected = [event for event in events if 0 < event["x"] < 612 and 130 < event["y"] < 215]
    if [len(event["values"]) for event in selected] != [2, 2, 2, 2, 4, 4]:
        raise ValueError("Changed visible C100 age fragments or hidden responses")
    bounds = ((160, 170, 140, 155), (245, 255, 140, 155),
              (160, 170, 190, 205), (245, 255, 190, 205),
              (350, 360, 140, 155), (350, 360, 190, 205))
    for event, (xmin, xmax, ymin, ymax) in zip(selected, bounds):
        if not xmin < event["x"] < xmax or not ymin < event["y"] < ymax:
            raise ValueError("Changed C100 country/response geometry")
    values = {
        ("USA", "favorable"): selected[2]["values"] + selected[3]["values"],
        ("USA", "unfavorable"): selected[0]["values"] + selected[1]["values"],
        ("CHN", "favorable"): selected[5]["values"],
        ("CHN", "unfavorable"): selected[4]["values"]}
    if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100
           for numbers in values.values() for value in numbers):
        raise ValueError("Invalid printed C100 percentage")
    return [dict(country=country, response=response, age=age, value=value)
            for (country, response), numbers in values.items()
            for age, value in zip(C100_AGE_BINS, numbers)]


def parse_c100_reported_ages(english_body, chinese_body, earlier_body):
    expected = (
        (english_body, "009e65debd1f52c20913a6b0f968ea5ba4ecf19a86dee4a24e46e6f7feb52879"),
        (chinese_body, "f349e5026d8daaad39433abaa03b001ce0dea6ac7ab6cdc78b1aa3a11ae5e80c"),
        (earlier_body, "361c7c5a53e3d95ba8d4872c2b331adde2b2977e0a39c712ea6512d049e249fd"))
    if any(digest(body) != fingerprint for body, fingerprint in expected):
        raise ValueError("C100 source edition changed; review reported bins and method conflicts")
    reader = PdfReader(io.BytesIO(english_body))
    page = reader.pages[15]
    if list(map(float, page.mediabox)) != [0, 0, 612, 792]:
        raise ValueError("Changed original C100 question panel")
    events, fragments = [], []

    def visit(text, cm, tm, font, size):
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        if 0 < x < 612 and 0 < y < 792:
            fragments.append(text)
        if re.fullmatch(r"(?:\d+\s*%\s*)+", normalize(text)):
            events.append(dict(x=x, y=y, values=list(map(int, re.findall(r"(\d+)\s*%", text)))))

    page.extract_text(visitor_text=visit)
    points = parse_c100_age_panel(events, normalize(" ".join(fragments)))
    summary, us, china = (normalize(reader.pages[index - 1].extract_text()) for index in (104, 104, 106))
    if any(phrase not in text for text, phrases in (
            (summary, ("December 6, 2016", "January 9, 2017")),
            (us, ("November 18th and December 20th, 2016", "1,019 US respondents",
                  "landline and cell phone", "Results were weighted")),
            (china, ("December 12, 2016- January 9, 2017", "3696 Chinese adults aged 18+",
                     "excluding Tibet, Xinjiang, Hong Kong, Macao and Taiwan", "effective PSUs is 70")))
           for phrase in phrases):
        raise ValueError("Changed C100 country-specific fieldwork or sampling frame")
    chinese = PdfReader(io.BytesIO(chinese_body))
    if (len(chinese.pages) != 59
            or digest(chinese.pages[54].images[0].data) != "2b749debb1489535186237b623f78db59dda3f31c49f6cb95f18704cb4bad91a"
            or digest(chinese.pages[54].images[1].data) != "6417ce273e11a8fd72b85520436753122092a18f5e3626de424c55c5b4197f59"):
        raise ValueError("Changed Chinese original table/profile images require visual review")
    earlier = normalize(PdfReader(io.BytesIO(earlier_body)).pages[14].extract_text(extraction_mode="layout"))
    section = earlier.split("China:", 1)[1].split("Assessment of General Public", 1)[0]
    match = re.search(r"Younger Chinese aged 18 to 29 years old \((\d+)%\) express more positive opinions of the U.S.", section)
    if not match:
        raise ValueError("Missing explicit2007age narrative; do not infer an age response")
    return points + [dict(country="CHN", response="favorable", age="18-29", value=int(match[1]), earlier=True)]


def collect_c100_reported_age_archive(client, data, earlier_body, earlier_asset):
    english_body, english_asset = client.get(C100_AGE_2017)
    chinese_body, chinese_asset = client.get(C100_AGE_2017_CHINESE)
    points = parse_c100_reported_ages(english_body, chinese_body, earlier_body)
    data["sources"]["c100_reported_age_2017"] = dict(
        name="Committee of 100 / Brunswick Insights / Horizon Research, source-reported 2017 age panel",
        published="2017", url=C100_AGE_2017, assets=[english_asset, chinese_asset],
        locator="English PDF16 Q1.2; methods104-106. Chinese physicalPDF11/55/56, printed16/104-107.",
        notes=C100_AGE_QUALIFICATION + " " + C100_CHINA_DATE_CONFLICT)
    data["sources"]["c100_reported_age_2007"] = dict(
        name="Committee of 100 / Horizon Research, explicit2007Chinese age narrative",
        published="2007-12-10", url=C100_CHINA_2007, assets=[earlier_asset],
        locator="PDF15/printed13 Q1China age narrative; methodsPDF62.",
        notes="Only explicit18-29favorable response. Ages18-60 frame; seven cities/seven towns/ten villages. "
              "Not a later18-34cohort, inferred complement or continuous national trend.")
    data["surveys"]["c100_reported_age_us_2016"] = dict(
        year=2016, period="Nov18-Dec20,2016 interviews (2017 report)",
        field_start="2016-11-18", field_end="2016-12-20", n_total=1019, n_item=None,
        notes="U.S.18+ weighted landline/cell telephone wave. Full-wave sample, not age/item denominators. " + C100_AGE_QUALIFICATION)
    data["surveys"]["c100_reported_age_china_2017"] = dict(
        year=2017, period="Dec2016-Jan2017 cross-year round (ending-year index; exact dates disputed)",
        field_start=None, field_end=None, n_total=3696, n_item=None,
        notes=C100_CHINA_DATE_CONFLICT + " " + C100_AGE_QUALIFICATION)
    data["surveys"]["c100_reported_age_china_2007"] = dict(
        year=2007, period="Aug18-Sep7,2007 Chinese age narrative",
        field_start="2007-08-18", field_end="2007-09-07", n_total=4104, n_item=None,
        notes="Chinese ages18-60 full-wave frame;18-29question subgroup/item base unknown. "
              "Publisher-described national sample in seven cities/seven towns/ten villages.")
    for point in points:
        earlier = point.get("earlier", False)
        country, age, response = point["country"], point["age"], point["response"]
        prefix = "c100_reported_age_2007" if earlier else (
            "c100_reported_age_us" if country == "USA" else "c100_reported_age_china")
        sid = prefix + ":" + ("general_public" if age == "General Population" else age) + ":" + response
        survey_id = "c100_reported_age_" + ("china_2007" if earlier else "us_2016" if country == "USA" else "china_2017")
        source_id = "c100_reported_age_2007" if earlier else "c100_reported_age_2017"
        data["series"][sid] = dict(
            label=("General public" if age == "General Population" else age) + " (source-reported)",
            respondent_country=country, target_country="CHN" if country == "USA" else "USA",
            measure="favorability", unit="percent", age="18+" if age == "General Population" else age,
            cadence="survey_rounds", sampling=C100_AGE_SAMPLING[prefix],
            notes=("Explicit2007age narrative only;18-29is not the later18-34bin." if earlier else C100_AGE_QUALIFICATION))
        survey = data["surveys"][survey_id]
        data["observations"].append(dict(
            series_id=sid, survey_id=survey_id, source_id=source_id,
            year=survey["year"], period=survey["period"], value=point["value"], status="observed",
            comparability=prefix + ":literal_unharmonized_question_bins",
            notes=("Only explicit favorable response; no missing complement inferred." if earlier else
                   "Visible Q1.2own impression of the other country, not a government or perception of others' views. "
                   + C100_AGE_QUALIFICATION)))
    return data


def validate_opinion_data(data):
    if set(data) != {"version", "series", "surveys", "observations", "sources", "context"} or data["version"] != 1:
        raise ValueError("Invalid public-opinion schema")
    if not all(data[k] for k in ("series", "surveys", "observations", "sources", "context")):
        raise ValueError("Opinion values, definitions and provenance are required")
    method_urls = {beijing_methods_url(year) for year in BAS_METHODS}
    bas_urls = {asset.get("request_url", asset["url"])
                for asset in data["sources"].get("bas_beijing_history", {}).get("assets", [])}
    bas_qualified = method_urls <= bas_urls
    if bas_urls.intersection(method_urls) and not bas_qualified:
        raise ValueError("All five original Beijing method records are required for the qualified frame")
    for sid, s in data["series"].items():
        if set(s) != {"label", "respondent_country", "target_country", "measure", "unit", "age",
                      "cadence", "sampling", "notes"}:
            raise ValueError("Invalid opinion series definition")
        if ((s["respondent_country"], s["target_country"]) not in {("USA", "CHN"), ("CHN", "USA")}
                or s["measure"] not in UNITS or s["unit"] != UNITS[s["measure"]]):
            raise ValueError("Opinion directions, percentages and rating points must remain distinct")
        chinese = sid.startswith(("pulse:", "pulse_age:", "pew_china:", "pew_china_18_60:",
                                  "bas_beijing:", "c100_china_18_60:", "c100_reported_age_china:",
                                  "c100_reported_age_2007:"))
        warmth = sid.startswith(("pulse:", "pulse_age:", "pew_warmth:", "pew_warmth_age:", "bas_beijing:"))
        if s["respondent_country"] != ("CHN" if chinese else "USA") or s["measure"] != ("warmth" if warmth else "favorability"):
            raise ValueError("Opinion series cannot change its respondent population or question scale")
        family = next((f for f in AGE_GROUPS if sid.startswith(f + ":")), None)
        if family and (s["age"] not in AGE_GROUPS[family] or s["age"] != sid.split(":")[1]
                       or s["label"] != s["age"]):
            raise ValueError("Published age groups must not be relabelled or rebinned")
        if sid.startswith("pew_china_18_60:") and s["age"] != "18-60":
            raise ValueError("Early Pew China city-area samples cover ages 18-60, not all adults")
        if sid.startswith("bas_beijing:") and (
                sid != "bas_beijing:us_warmth" or s["age"] != ("18-65" if bas_qualified else "Not specified")
                or "Beijing" not in s["sampling"] or "not nationally representative" not in s["sampling"]):
            raise ValueError("Historical Beijing warmth is not a national or verified all-adult sample")
        if sid.startswith("bas_beijing:") and bas_qualified and not all(token in s["sampling"] for token in (
                "eight urban districts", "fixed residence", "non-agricultural Beijing hukou")):
            raise ValueError("Qualified Beijing warmth must retain the restricted urban registration frame")
        if sid.startswith("c100_china_18_60:") and (
                sid.split(":")[-1] not in {"favorable", "unfavorable", "not_sure"}
                or s["age"] != "18-60" or not all(token in s["sampling"] for token in
                    ("publisher-described national", "seven cities", "seven towns", "ten villages"))):
            raise ValueError("C100 2007 requires its qualified national ages18-60 general-public frame")
        if not all(isinstance(s[k], str) and s[k] for k in s):
            raise ValueError("Opinion population and method required")
        if sid.startswith("c100_reported_age_"):
            family, age, response = sid.split(":")
            expected_age = "18+" if age == "general_public" else age
            earlier = family == "c100_reported_age_2007"
            if (family not in {"c100_reported_age_us", "c100_reported_age_china", "c100_reported_age_2007"}
                    or response not in {"favorable", "unfavorable"}
                    or (earlier and (age != "18-29" or response != "favorable"))
                    or (not earlier and age not in {"general_public", "18-34", "35-49", "50+"})
                    or s["age"] != expected_age or "source-reported" not in s["label"]
                    or s["sampling"] != C100_AGE_SAMPLING.get(family)
                    or (not earlier and s["notes"] != C100_AGE_QUALIFICATION)):
                raise ValueError("C100 source-reported question bins cannot be relabelled, harmonized or complemented")
    for survey_id, survey in data["surveys"].items():
        if set(survey) != {"year", "period", "field_start", "field_end", "n_total", "n_item", "notes"}:
            raise ValueError("Invalid survey identity")
        first_year = 1998 if survey_id.startswith("bas_beijing_") else 2000
        if not isinstance(survey["year"], int) or isinstance(survey["year"], bool) or not first_year <= survey["year"] <= 9999:
            raise ValueError("Invalid survey year")
        if (survey["field_start"] is None) != (survey["field_end"] is None):
            raise ValueError("Survey field dates are either both verified or both unknown")
        if survey["field_start"]:
            start, end = (date.fromisoformat(survey[k]) for k in ("field_start", "field_end"))
            if start > end or not start.year <= survey["year"] <= end.year:
                raise ValueError("Survey period must match actual field dates")
        for k in ("n_total", "n_item"):
            n = survey[k]
            if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n <= 0):
                raise ValueError("Invalid survey sample size")
        if survey["n_item"] is not None and survey["n_total"] is not None and survey["n_item"] > survey["n_total"]:
            raise ValueError("Question-specific sample cannot exceed the full survey")
    for source in data["sources"].values():
        if set(source) != {"name", "published", "url", "assets", "locator", "notes"} or not source["assets"]:
            raise ValueError("Opinion primary-source provenance incomplete")
        published = source["published"]
        suffix = "-01-01" if re.fullmatch(r"\d{4}", published) else "-01" if re.fullmatch(r"\d{4}-\d{2}", published) else ""
        date.fromisoformat(published + suffix)
        for asset in source["assets"]:
            if not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
                raise ValueError("Invalid opinion source fingerprint")
            parsed = urlsplit(asset["url"])
            if parsed.scheme != "https" or not parsed.netloc or parsed.username:
                raise ValueError("Invalid public opinion source URL")
            if datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
                raise ValueError("Opinion source retrieval timestamps require timezones")
    seen = set()
    for row in data["observations"]:
        if set(row) != {"series_id", "survey_id", "source_id", "year", "period", "value", "status", "comparability", "notes"}:
            raise ValueError("Invalid opinion observation")
        if row["series_id"] not in data["series"] or row["source_id"] not in data["sources"] or row["survey_id"] not in data["surveys"]:
            raise ValueError("Opinion observation is missing its source or survey")
        survey = data["surveys"][row["survey_id"]]
        if any(row[k] != survey[k] for k in ("year", "period")):
            raise ValueError("Chart labels cannot substitute publication year for survey timing")
        if row["year"] > int(data["sources"][row["source_id"]]["published"][:4]):
            raise ValueError("A source cannot report a survey from a later year")
        key = row["series_id"], row["survey_id"]
        if key in seen:
            raise ValueError("Duplicate opinion observation")
        seen.add(key)
        value = row["value"]
        if row["status"] not in {"observed", "missing"} or (value is None) != (row["status"] == "missing"):
            raise ValueError("Opinion missingness must not become zero")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int))
                                  or not math.isfinite(value) or not 0 <= value <= 100):
            raise ValueError("Opinion percentages and ratings must stay between 0 and 100")
        if not row["comparability"] or not isinstance(row["notes"], str):
            raise ValueError("Opinion comparability and notes required")
        if row["series_id"].startswith("c100_reported_age_"):
            family = row["series_id"].split(":")[0]
            earlier = family == "c100_reported_age_2007"
            us = family == "c100_reported_age_us"
            expected_survey = "c100_reported_age_" + ("china_2007" if earlier else "us_2016" if us else "china_2017")
            expected_source = "c100_reported_age_2007" if earlier else "c100_reported_age_2017"
            source = data["sources"][row["source_id"]]
            if (row["survey_id"] != expected_survey or row["source_id"] != expected_source
                    or row["year"] != (2007 if earlier else 2016 if us else 2017)
                    or row["comparability"] != family + ":literal_unharmonized_question_bins"
                    or survey["n_total"] != (4104 if earlier else 1019 if us else 3696)
                    or survey["n_item"] is not None or row["status"] != "observed"
                    or source["published"] != ("2007-12-10" if earlier else "2017")
                    or source["url"] != (C100_CHINA_2007 if earlier else C100_AGE_2017)):
                raise ValueError("C100 reported age cells require their original country/wave/source and unknown item bases")
            expected_assets = (
                [(C100_CHINA_2007, "361c7c5a53e3d95ba8d4872c2b331adde2b2977e0a39c712ea6512d049e249fd")] if earlier else [
                    (C100_AGE_2017, "009e65debd1f52c20913a6b0f968ea5ba4ecf19a86dee4a24e46e6f7feb52879"),
                    (C100_AGE_2017_CHINESE, "f349e5026d8daaad39433abaa03b001ce0dea6ac7ab6cdc78b1aa3a11ae5e80c")])
            if [(asset["url"], asset["sha256"]) for asset in source["assets"]] != expected_assets:
                raise ValueError("C100 reported age edition provenance cannot be substituted")
            if us and (survey["field_start"], survey["field_end"]) != ("2016-11-18", "2016-12-20"):
                raise ValueError("C100 U.S.2017report is actual2016fieldwork")
            if earlier and (survey["field_start"], survey["field_end"]) != ("2007-08-18", "2007-09-07"):
                raise ValueError("C1002007age narrative requires its original wave")
            if not earlier and not us and (
                    survey["field_start"] is not None or survey["field_end"] is not None
                    or C100_CHINA_DATE_CONFLICT not in survey["notes"]):
                raise ValueError("Conflicting C100 China exact dates cannot be silently resolved")
        if row["series_id"].startswith("pulse") and row["comparability"] != "china_pulse_october_2026_weights":
            raise ValueError("Do not splice unweighted and reweighted China Pulse releases")
        if row["series_id"].startswith("gallup_us:") and (
                row["source_id"] != "gallup_us_history" or row["comparability"] != "gallup_us_telephone"
                or not survey["field_start"] or not survey["field_end"]):
            raise ValueError("Gallup telephone polls require their own source, dates and comparability")
        if row["series_id"].startswith("pew_china_18_60:") and (
                row["source_id"] != "pew_china_2005_2006" or row["year"] not in (2005, 2006)
                or row["comparability"] != "pew_china_18_60_coverage_" + str(row["year"])
                or not survey["field_start"] or not survey["field_end"]):
            raise ValueError("Early Pew China rounds require their own source, dates and city-area coverage")
        if row["series_id"].startswith("bas_beijing:") or row["source_id"] == "bas_beijing_history":
            year = row["year"]
            expected_n = (BAS_METHODS.get(year, (None, None, None, None))[3]
                          if bas_qualified else {2000: 757, 2001: 615, 2002: 662}.get(year))
            precision = "Approximate mean" if year in (1998, 1999, 2002) else "Reported integer mean"
            if (row["series_id"] != "bas_beijing:us_warmth" or row["source_id"] != "bas_beijing_history"
                    or year not in range(1998, 2003)
                    or row["survey_id"] != "bas_beijing_" + str(year)
                    or row["comparability"] != "bas_beijing_coverage_" + str(year)
                    or survey["field_start"] is not None or survey["field_end"] is not None
                    or survey["n_total"] != expected_n or survey["n_item"] is not None
                    or precision not in row["notes"]
                    or data["sources"][row["source_id"]]["published"] != "2003"
                    or data["sources"][row["source_id"]]["url"] != BAS_HISTORY):
                raise ValueError("Historical Beijing waves require their own source, precision and unknown dates")
            if bas_qualified:
                _, start, end, _ = BAS_METHODS[year]
                if start + " to " + end not in survey["notes"] or "month precision" not in survey["notes"]:
                    raise ValueError("Qualified Beijing waves must retain their actual month windows")
        if row["series_id"].startswith("c100_china_18_60:") or row["source_id"] == "c100_china_2007":
            if (not row["series_id"].startswith("c100_china_18_60:")
                    or row["source_id"] != "c100_china_2007" or row["survey_id"] != "c100_china_2007"
                    or row["year"] != 2007 or row["comparability"] != "c100_china_18_60_2007_coverage"
                    or survey["field_start"] != "2007-08-18" or survey["field_end"] != "2007-09-07"
                    or survey["n_total"] != 4104 or survey["n_item"] is not None
                    or data["sources"][row["source_id"]]["published"] != "2007-12-10"
                    or data["sources"][row["source_id"]]["url"] != C100_CHINA_2007):
                raise ValueError("C100 general-public totals cannot acquire a different wave, source or population")
    return data


def collect(client, reviewed_body):
    data = {"version": 1, "series": {}, "surveys": {}, "observations": [], "sources": {}, "context": {
        "interpretation": "Country opinions, not opinions of an ethnicity, approval of a government, or evidence that a social-media trend caused a change.",
        "scales": "Percent favorable and mean 0-100 warmth ratings are different measures. Fifty is neutral on the warmth scale, not fifty percent favorable.",
        "age": "Original age bands are retained. Ages 18-34 include 34-year-olds; Chinese 18-29 and U.S. 18-34 groups are not matched cohorts.",
        "rights": "Only reported aggregate numerical facts and our own charts are redistributed; no microdata, publisher graphics or full source reports."}}

    def source(sid, name, published, url, assets, locator, notes=""):
        data["sources"][sid] = dict(name=name, published=published, url=url, assets=assets, locator=locator, notes=notes)

    def survey(sid, year, period, start=None, end=None, total=None, item=None, notes=""):
        data["surveys"][sid] = dict(year=year, period=period, field_start=start, field_end=end,
                                   n_total=total, n_item=item, notes=notes)

    def series(sid, label, country, measure, age="All adults", cadence="survey_rounds", sampling=""):
        data["series"][sid] = dict(label=label, respondent_country=country, target_country="CHN" if country == "USA" else "USA",
                                   measure=measure, unit=UNITS[measure], age=age, cadence=cadence, sampling=sampling,
                                   notes="Reported survey estimates; nonresponse is not a neutral opinion.")

    def observation(sid, survey_id, source_id, value, comparability, notes=""):
        wave = data["surveys"][survey_id]
        data["observations"].append(dict(series_id=sid, survey_id=survey_id, source_id=source_id,
                                         year=wave["year"], period=wave["period"], value=value,
                                         status="observed", comparability=comparability, notes=notes))

    body, asset = client.get(GALLUP_HISTORY)
    source("gallup_us_history", "Gallup", "2026-03-12",
           "https://news.gallup.com/poll/703040/americans-views-canada-great-britain-drop-new-lows.aspx",
           [asset], "Country ratings final topline, PDF page 4, Q17 D: China, all 2000-2026 rounds; pages 1-2 methods.",
           "Telephone surveys of U.S. adults, not Pew's panel. Sampling frames and weights evolved. "
           "2026 fieldwork February 2-16; full sample 1,001, each country item approximately 800. "
           "Published net percentages are retained despite rounding; every reported 2000 round is kept.")
    for response in ("favorable", "unfavorable"):
        series("gallup_us:" + response, response.title(), "USA", "favorability", cadence="annual",
               sampling="Gallup telephone surveys; current random-digit-dial landline/cellular sample. "
               "Earlier sampling frames and weights evolved; separate from Pew phone and panel surveys.")
    for row in parse_gallup_history(body):
        wave = "gallup_us_" + row["field_start"]
        notes = "Asked of half the sample." if row["half_sample"] else ""
        if row["year"] == 2026:
            notes = "Full n=1,001; country items approximately 800, so no exact item base is inferred."
        survey(wave, row["year"], row["period"], row["field_start"], row["field_end"],
               1001 if row["year"] == 2026 else None, notes=notes)
        for response in ("favorable", "unfavorable"):
            observation("gallup_us:" + response, wave, "gallup_us_history", row[response],
                        "gallup_us_telephone", "Published net; not an annual average. " + notes)

    body, asset = client.get(PEW_TREND)
    source("pew_us_trend", "Pew Research Center", "2026-04-14", PEW_TREND, [asset],
           "First embedded table: full U.S. favorable/unfavorable phone and ATP trends.",
           "Chart dates such as March 1 are positioning dates, not verified fieldwork. Unknown historical field dates stay null. Phone and probability-panel histories are separate.")
    for row in parse_pew_trend(body):
        mode = row["mode"] + ("_summer" if row["period"].startswith("Summer") else "")
        wave = "pew_" + mode + "_" + str(row["year"])
        current = row["mode"] == "atp" and row["year"] == 2026
        survey(wave, row["year"], row["period"], "2026-03-23" if current else None,
               "2026-03-29" if current else None, 3507 if current else None)
        for response in ("favorable", "unfavorable"):
            sid = "pew_us_" + mode + ":" + response
            series(sid, response.title(), "USA", "favorability", cadence="annual",
                   sampling="Probability-based American Trends Panel; online plus some live telephone in recent waves." if row["mode"] == "atp"
                   else "Telephone surveys; separate from the American Trends Panel.")
            observation(sid, wave, "pew_us_trend", row[response], "pew_us_" + row["mode"])

    body, asset = client.get(PEW_AGE)
    source("pew_us_age", "Pew Research Center", "2026-07-15",
           "https://www.pewresearch.org/global/2026/07/15/appendix-detailed-tables-global-views-china-2026/",
           [asset], "Appendix: Views of China by age, U.S. row; U.S. survey methodology.",
           "This is the same March 23-29 U.S. survey as the April trend release, not another survey in July.")
    for age, responses in parse_pew_age(body).items():
        for response, value in responses.items():
            sid = "pew_age:" + age + ":" + response
            series(sid, age, "USA", "favorability", age=age, sampling="Probability-based American Trends Panel.")
            observation(sid, "pew_atp_2026", "pew_us_age", value, "pew_us_atp",
                        "Age-group sample size is not inferred from the full survey of 3,507.")

    body, asset = client.get(PEW_WARMTH)
    text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(body)).pages)
    if not all(token in text for token in ("THERMO_CHINA", "N=1,168", "SEPTEMBER 14-20, 2026")):
        raise ValueError("Pew feeling-thermometer question or item base changed")
    reviewed = json.loads(reviewed_body)
    if reviewed["version"] != 1 or reviewed["published"] != "2026-09-23":
        raise ValueError("Warmth means require reviewed publisher evidence")
    transcription = {"url": "https://github.com/hanshanley/china-us-relation-change/blob/main/" + REVIEWED_PATH,
                     "request_url": reviewed["source_url"], "sha256": digest(reviewed_body),
                     "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "sha256_scope": reviewed["sha256_scope"]}
    source("pew_us_warmth", "Pew Research Center", reviewed["published"], reviewed["source_url"],
           [asset, transcription], "Article's published mean-rating table and age paragraph; topline THERMO_CHINA.",
           reviewed["extraction"])
    series("pew_warmth:all", "U.S. adults", "USA", "warmth", sampling="Probability-based American Trends Panel.")
    for row in reviewed["means"]:
        wave = "pew_warmth_" + str(row["year"])
        survey(wave, row["year"], row["period"], row["field_start"], row["field_end"],
               5193 if row["year"] == 2026 else None, 1168 if row["year"] == 2026 else None,
               "In 2026 only the 1,168 respondents assigned the China item form its base, not all 5,193 respondents.")
        observation("pew_warmth:all", wave, "pew_us_warmth", row["value"], "pew_warmth",
                    "Published mean, not calculated from rounded rating-category percentages.")
    for row in reviewed["age_means_2026"]:
        sid = "pew_warmth_age:" + row["age"]
        series(sid, row["age"], "USA", "warmth", age=row["age"], sampling="Probability-based American Trends Panel.")
        observation(sid, "pew_warmth_2026", "pew_us_warmth", row["value"], "pew_warmth")

    body, report_asset = client.get(PULSE_REPORT)
    text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(body)).pages)
    if not all(term in text for term in ("April 16 to June 26, 2026", "2,500 Chinese adults",
                                        "Quota sampling", "same weights", "fall/winter 2025")):
        raise ValueError("China Pulse dates, sample or reweighting changed")
    body, chart_asset = client.get(PULSE_DATA)
    source("china_pulse", "The Carter Center / Emory University, China Pulse", "2026-10",
           "https://uscnpm.org/china-pulse/chinese-public-supports-trade-and-security-cooperation-still-sees-the-united-states-as-a-threat/",
           [report_asset, chart_asset], "Datawrapper LU2Fb: Overall and Age rows; report pages 4 and 15-16.",
           "October 2026 release; exact publication day is not supplied in the PDF. Both waves use the October release's raking weights. The reweighted 2025 mean is 33, not the earlier release's 34. Quota panel, not documented as a national probability sample; not Pew.")
    for year, period, start, end, n in [
            (2025, "Oct 2025-Jan 2026", "2025-10-27", "2026-01-01", 2506),
            (2026, "Apr-Jun 2026", "2026-04-16", "2026-06-26", 2500)]:
        survey("pulse_" + str(year), year, period, start, end, n, notes="Full survey base, not a reported age-subgroup base. Quota panel, reweighted in the October 2026 report.")
    for row in parse_pulse(body):
        age = row["Topic"] if row["Demographic"] == "Age" else "All adults"
        sid = "pulse_age:" + age if row["Demographic"] == "Age" else "pulse:all"
        series(sid, age if row["Demographic"] == "Age" else "Chinese adults", "CHN", "warmth", age=age,
               sampling="China-based respondent panel; quota sampling and raking weights.")
        for year, wave in ((2025, "Fall/Winter 2025"), (2026, "Spring/Summer 2026")):
            observation(sid, "pulse_" + str(year), "china_pulse", row[wave], "china_pulse_october_2026_weights")

    body, asset = client.get(PEW_CHINA)
    source("pew_china_history", "Pew Research Center", "2016-10-05",
           "https://www.pewresearch.org/global/2016/10/05/chinese-public-sees-more-powerful-role-in-world-names-u-s-as-top-threat/",
           [asset], "Page 13: Fluctuating views of the U.S., Q10a; published net percentages.",
           "Nets are read directly, not summed from separately rounded response components. Earlier survey coverage varies; no line is drawn across these samples or to the different 2025-2026 China Pulse measure.")
    for response in ("favorable", "unfavorable"):
        series("pew_china:" + response, response.title(), "CHN", "favorability",
               sampling="Historical Pew face-to-face surveys; sample coverage varies by round.")
    for row in parse_china_history(body):
        wave, current = "pew_china_" + str(row["year"]), row["year"] == 2016
        survey(wave, row["year"], "Spring " + str(row["year"]), "2016-04-06" if current else None,
               "2016-05-08" if current else None, 3154 if current else None,
               notes="The retrospective figure does not give historical field dates or subgroup sample sizes.")
        for response in ("favorable", "unfavorable"):
            observation("pew_china:" + response, wave, "pew_china_history", row[response],
                        "pew_china_coverage_" + str(row["year"]))

    body, asset = client.get(PEW_CHINA_EARLY)
    methods_body, methods_asset = client.get(PEW_CHINA_2005_METHODS)
    source("pew_china_2005_2006", "Pew Research Center", "2006-09-21", PEW_CHINA_EARLY,
           [asset, methods_asset],
           "2006 report PDF page 12, Q2a China rows: published favorable/unfavorable nets; "
           "page 11 methods. November 2005 report PDF pages 6-7: China sampling and fieldwork.",
           "Ages 18-60 in six city areas and surrounding rural areas, disproportionately urban, "
           "not nationally representative. City sets differ between rounds. Neither round is "
           "joined to the later all-adult series or to China Pulse warmth scores.")
    for response in ("favorable", "unfavorable"):
        series("pew_china_18_60:" + response, response.title(), "CHN", "favorability", age="18-60",
               sampling="Face-to-face probability samples within six city areas and surrounding rural areas; "
               "disproportionately urban, not nationally representative; city sets vary by round.")
    for row in parse_early_china_history(body, methods_body):
        year, wave = row["year"], "pew_china_" + str(row["year"])
        survey(wave, year, "May 21-31, 2005" if year == 2005 else "April 7-18, 2006",
               row["field_start"], row["field_end"], row["n_total"],
               notes="Ages 18-60; " + row["cities"] + " and surrounding rural areas. "
               "Disproportionately urban, not nationally representative. Full survey sample; "
               "an exact question-specific base is not supplied.")
        for response in ("favorable", "unfavorable"):
            observation("pew_china_18_60:" + response, wave, "pew_china_2005_2006", row[response],
                        "pew_china_18_60_coverage_" + str(year),
                        "Published Q2a net about the United States, not a sum of rounded components.")
    body, asset = client.get(BAS_HISTORY)
    bas_methods, method_assets = {}, []
    for year in BAS_METHODS:
        method_body, method_asset = client.get(beijing_methods_url(year))
        bas_methods[year] = parse_beijing_methods(method_body, year)
        method_assets.append(method_asset)
    source("bas_beijing_history", "Alastair Iain Johnston / RSIS, Beijing Area Study", "2003",
           BAS_HISTORY, [asset] + method_assets,
           "Working Paper 50, printed/PDF page13 footnote33; page8 footnote20. "
           "PKU original BAS1998-2002 dataset metadata: population, collection months, sampling and response counts.",
           "Publication year only; no month/day verified. Historical Beijing respondents, not national China. "
           "Reported 0-100 warmth means, not favorable percentages. The source explicitly qualifies "
           "1998, 1999 and 2002 as approximate. Separately published PKU2016catalogue records qualify "
           "ages18-65, fixed residence, eight urban districts and non-agricultural Beijing hukou. "
           "Provider collection months cross calendar years; the2001wave ends February2002, alongside "
           "RSIS's generic December/January description. Exact days, original thermometer item bases "
           "and weighting of the published means are not recovered. Restricted questionnaire/codebook/"
           "microdata files are not retrieved; public metadata is not a complete numeric survey download. "
           "No connection to Pew or China Pulse or broader later Beijing populations is inferred.")
    series("bas_beijing:us_warmth", "Beijing registered-urban respondents", "CHN", "warmth", age="18-65",
           sampling="Beijing Area Study; ages18-65 with fixed residence and non-agricultural Beijing hukou "
           "in eight urban districts; not nationally representative. Paper face-to-face, two-stage "
           "probability-proportional-to-size samples. Separate from broader later Beijing resident frames.")
    for row in parse_beijing_history(body):
        year, wave = row["year"], "bas_beijing_" + str(row["year"])
        method = bas_methods[year]
        survey(wave, year, str(year) + " BAS wave", total=method["n_total"],
               notes="Survey-wave label, not publication or single calendar year. PKU provider collection "
               "window " + method["start_month"] + " to " + method["end_month"] + " (month precision; "
               "exact days unknown). Ages18-65; fixed residence, eight urban districts and non-agricultural "
               "Beijing hukou. Full-wave samples are not thermometer-item bases. PKU metadata published "
               + method["metadata_published"] + "; original RSIS summary describes December/January.")
        precision = "Approximate mean; source says around." if row["approximate"] else "Reported integer mean."
        observation("bas_beijing:us_warmth", wave, "bas_beijing_history", row["value"],
                    "bas_beijing_coverage_" + str(year),
                    precision + " Historical Beijing warmth only; not a national favorable percentage.")
    body, asset = client.get(C100_CHINA_2007)
    responses = parse_c100_china_2007(body)
    source("c100_china_2007", "Committee of 100 / Horizon Research, 2007 Chinese general public",
           "2007-12-10", C100_CHINA_2007, [asset],
           "Original report PDF page 14 / printed12, Q1 Chinese general-public column; "
           "PDF page62 / printed60 country sampling; PDF page3 release date.",
           "Published totals about the United States as a country, not its people or government. "
           "Publisher describes a national sample of ages18-60, drawn from seven cities, seven towns "
           "and ten villages. Not an unrestricted all-adult sample or the elite groups. "
           "Keep separate from Pew and 0-100 warmth means; archive-only, not a continuous national trend.")
    survey("c100_china_2007", 2007, "Aug 18-Sep 7, 2007", "2007-08-18", "2007-09-07", 4104,
           notes="Chinese general public ages18-60, face-to-face multistage sampling in seven cities, "
           "seven towns and ten villages. Publisher-described national coverage within that age frame. "
           "4,104 is the whole-wave sample; an exact item denominator is not supplied.")
    for response, label in (("favorable", "Favorable"), ("unfavorable", "Unfavorable"), ("not_sure", "Not sure")):
        sid = "c100_china_18_60:" + response
        series(sid, label, "CHN", "favorability", age="18-60",
               sampling="Face-to-face, multistage, publisher-described national ages18-60 sample; "
               "seven cities, seven towns and ten villages. Separate from unrestricted all-adult populations.")
        observation(sid, "c100_china_2007", "c100_china_2007", responses[response],
                    "c100_china_18_60_2007_coverage",
                    "Published Q1 response total from the Chinese general-public column, "
                    "not an elite response, rounded-component sum or inferred remainder.")
    data = collect_c100_reported_age_archive(client, data, body, asset)
    data["observations"].sort(key=lambda r: (r["series_id"], r["year"], r["period"]))
    return validate_opinion_data(data)
