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
PEW_AGE = "https://www.pewresearch.org/wp-content/uploads/sites/20/2026/07/pg_2026.06.15_global-views-china-2026_report.pdf"
PEW_WARMTH = "https://www.pewresearch.org/wp-content/uploads/sites/20/2026/09/SR_26.09.23_views-of-china_topline.pdf"
PEW_CHINA = "https://www.pewresearch.org/global/wp-content/uploads/sites/2/2016/10/Pew-Research-Center-China-Report-FINAL-October-5-2016.pdf"
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
        if year < 2010:
            continue
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
            for i, year in enumerate(years) if year >= 2010]


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


def validate_opinion_data(data):
    if set(data) != {"version", "series", "surveys", "observations", "sources", "context"} or data["version"] != 1:
        raise ValueError("Invalid public-opinion schema")
    if not all(data[k] for k in ("series", "surveys", "observations", "sources", "context")):
        raise ValueError("Opinion values, definitions and provenance are required")
    for sid, s in data["series"].items():
        if set(s) != {"label", "respondent_country", "target_country", "measure", "unit", "age",
                      "cadence", "sampling", "notes"}:
            raise ValueError("Invalid opinion series definition")
        if ((s["respondent_country"], s["target_country"]) not in {("USA", "CHN"), ("CHN", "USA")}
                or s["measure"] not in UNITS or s["unit"] != UNITS[s["measure"]]):
            raise ValueError("Opinion directions, percentages and rating points must remain distinct")
        chinese = sid.startswith(("pulse:", "pulse_age:", "pew_china:"))
        warmth = sid.startswith(("pulse:", "pulse_age:", "pew_warmth:", "pew_warmth_age:"))
        if s["respondent_country"] != ("CHN" if chinese else "USA") or s["measure"] != ("warmth" if warmth else "favorability"):
            raise ValueError("Opinion series cannot change its respondent population or question scale")
        family = next((f for f in AGE_GROUPS if sid.startswith(f + ":")), None)
        if family and (s["age"] not in AGE_GROUPS[family] or s["age"] != sid.split(":")[1]
                       or s["label"] != s["age"]):
            raise ValueError("Published age groups must not be relabelled or rebinned")
        if not all(isinstance(s[k], str) and s[k] for k in s):
            raise ValueError("Opinion population and method required")
    for survey in data["surveys"].values():
        if set(survey) != {"year", "period", "field_start", "field_end", "n_total", "n_item", "notes"}:
            raise ValueError("Invalid survey identity")
        if not isinstance(survey["year"], int) or isinstance(survey["year"], bool) or not 2010 <= survey["year"] <= 9999:
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
        date.fromisoformat(published + "-01" if re.fullmatch(r"\d{4}-\d{2}", published) else published)
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
        if row["series_id"].startswith("pulse") and row["comparability"] != "china_pulse_october_2026_weights":
            raise ValueError("Do not splice unweighted and reweighted China Pulse releases")
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
    data["observations"].sort(key=lambda r: (r["series_id"], r["year"], r["period"]))
    return validate_opinion_data(data)
