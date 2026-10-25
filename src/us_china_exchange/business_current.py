"""Recent company surveys and investment positions, never company censuses."""

import csv
import html
import io
import json
import math
import re
from datetime import date, datetime
from pathlib import Path

import xlrd
from bs4 import BeautifulSoup
from openpyxl import load_workbook

from .indicator_charts import svg_indicator_chart
from .model import json_text
from .pipeline import write_atomic
from .theme import BLUE, CHART_THEMES, FONT, GRID, MUTED, PARTNER_COLORS, TEXT


BEA_RELEASE = "https://www.bea.gov/news/2026/direct-investment-country-and-industry-2025"
BEA_POSITIONS = "https://apps.bea.gov/international/xls/usdia-current/usdia-positionbyaccountforselectedcountries-2020-2025.xlsx"
BEA_DIRECTORY = "https://www.bea.gov/international/di1usdbal"
BEA_POSITION_HISTORY = (
    "https://apps.bea.gov/international/xls/Position%20Abroad%202000-2009.xls",
    "https://apps.bea.gov/international/xls/usdia-current/usdia-position-2010-2019.xlsx",
    "https://apps.bea.gov/international/xls/usdia-current/usdia-position-2020-2025.xlsx",
)
US_RELEASE = "https://www.amcham-shanghai.org/en/article/amcham-shanghai-releases-2026-report-business-climate-china"
GERMAN_RELEASE = "https://china.ahk.de/en/media-centre"
CHARTS = {
    "us-company-decisions": {
        "title": "AmCham Shanghai respondents",
        "subtitle": "AmCham Shanghai / PwC | September 2026 publication",
        "series": ["amcham:profitable", "amcham:optimistic", "amcham:redirecting", "amcham:increased"],
        "unit": "Percent of respondents", "mode": "bars", "source_id": "amcham_2026",
        "note": "262 survey respondents; item-level bases and fieldwork dates are not stated in the public release. Separate questions, not parts of one total."},
    "german-company-risk": {
        "title": "German member-company trade exposure",
        "subtitle": "German Chamber | Preliminary release, 6 October 2026",
        "series": ["ahk:significant", "ahk:moderate", "ahk:none"],
        "unit": "Percent of respondents", "mode": "bars", "source_id": "ahk_2026",
        "note": "381 answers to this question; 488 interim survey respondents overall, 1-29 September 2026. Conditional expectations, not realized losses. Published categories are not exhaustive."},
    "us-investment-mainland": {
        "title": "U.S. investment in mainland China",
        "subtitle": "BEA | Year-end positions, 2000-2025",
        "series": ["bea_position:CHN"], "unit": "USD", "mode": "levels", "columns": True, "source_id": "bea_2025",
        "note": "Historical-cost direct investment position. Immediate host country, not ultimate operating exposure. Dollars on the books, not company counts, sales or annual investment flows."},
    "us-investment-hong-kong": {
        "title": "U.S. investment in Hong Kong",
        "subtitle": "BEA | Year-end positions, 2000-2025",
        "series": ["bea_position:HKG"], "unit": "USD", "mode": "levels", "columns": True, "source_id": "bea_2025",
        "note": "Historical-cost direct investment position. Hong Kong is separate from mainland China; holding-company routing matters. Macau is not supplied in this selected-country extract."},
}


def parse_positions(content, all_industries=False):
    if content.startswith(b"PK"):
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        tables = [(sheet.title, list(sheet.values)) for sheet in book if re.fullmatch(r"\d{4}", sheet.title)]
        book.close()
    else:
        book = xlrd.open_workbook(file_contents=content)
        tables = [(sheet.name, [sheet.row_values(i) for i in range(sheet.nrows)])
                  for sheet in book.sheets() if re.fullmatch(r"\d{4}", sheet.name)]
        book.release_resources()
    result = []
    for title, rows in tables:
        year = int(title)
        if (not str(rows[0][0]).startswith("U.S. Direct Investment Position Abroad on a Historical-Cost Basis")
                or not str(rows[0][0]).endswith(str(year))
                or rows[1][0] != "[Millions of dollars]"
                or rows[2][1] != ("All industries" if all_industries else "Total")):
            raise ValueError("Unexpected BEA position, units or year header")
        for country, geo in (("China", "CHN"), ("Hong Kong", "HKG")):
            matches = [(i, r) for i, r in enumerate(rows, 1) if r[0] == country]
            if len(matches) != 1:
                raise ValueError("BEA country must have exactly one row")
            row_number, row = matches[0]
            value = row[1]
            if isinstance(value, str) and re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)", value):
                value = int(value.replace(",", ""))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("BEA missing, suppressed or ranged values require review, not zero")
            if value != int(value):
                raise ValueError("Unexpected BEA reporting precision")
            result.append({"series_id": "bea_position:" + geo, "year": year, "value": int(value) * 1_000_000,
                           "source_id": "bea_2025", "status": "observed",
                           "comparability": "bea_historical_cost_immediate_host",
                           "period": f"31 December {year}", "notes": f"Worksheet {year}, cell B{row_number}; source reports millions of dollars."})
    if not result:
        raise ValueError("No dated BEA position worksheets")
    return result


def reviewed_snapshot(bea_client, survey_client):
    release, release_asset = bea_client.get(BEA_RELEASE)
    workbook, position_asset = bea_client.get(BEA_POSITIONS)
    directory, directory_asset = bea_client.get(BEA_DIRECTORY)
    linked = {a["href"] for a in BeautifulSoup(directory, "html.parser").select("a[href]")}
    if not set(BEA_POSITION_HISTORY) <= linked:
        raise ValueError("BEA historical position links require review")
    positions, history_assets = [], []
    for url in BEA_POSITION_HISTORY:
        body, asset = bea_client.get(url)
        history_assets.append(asset)
        for row in parse_positions(body, all_industries=True):
            row.update(source_url=asset["url"], raw_sha256=asset["sha256"],
                       retrieved_at=asset["retrieved_at"],
                       source_vintage="BEA linked historical-cost position table: " + url.rsplit("/", 1)[1])
            positions.append(row)
    expected = {(f"bea_position:{geo}", year) for geo in ("CHN", "HKG") for year in range(2000, 2026)}
    if len(positions) != len(expected) or {(r["series_id"], r["year"]) for r in positions} != expected:
        raise ValueError("BEA history must contain every reported country-year, without duplicates")
    recent = {(r["series_id"], r["year"]): r["value"] for r in parse_positions(workbook)}
    if {k: r["value"] for r in positions if (k := (r["series_id"], r["year"])) in recent} != recent:
        raise ValueError("BEA detailed and selected-country position totals disagree")
    us, us_asset = survey_client.get(US_RELEASE)
    german, german_asset = survey_client.get(GERMAN_RELEASE)
    text = lambda body: " ".join(BeautifulSoup(body, "html.parser").get_text(" ", strip=True).split())
    if "July 21, 2026" not in text(release):
        raise ValueError("BEA release edition requires review")
    us_text, german_text = text(us), text(german)
    for token in ("262 AmCham Shanghai members", "(78%) profitable in 2025", "58% of respondents",
                  "28% of respondents", "39%"):
        if token not in us_text:
            raise ValueError("American chamber finding requires primary-source review")
    for token in ("33%", "47%", "14%", "488 Mitgliedsunternehmen", "381 Unternehmen", "29. September 2026"):
        if token not in german_text:
            raise ValueError("German chamber interim finding requires primary-source review")
    source = lambda name, release_date, assets, locator, notes: dict(
        name=name, release_date=release_date, assets=assets, locator=locator, notes=notes)
    data = {
        "version": 1, "as_of": "2026-10-25",
        "context": {
            "interpretation": "Company decisions and investment are separate measures. Neither is a census of businesses or offices.",
            "survey_comparison": "Different member populations and questions: these are not matched U.S.-European estimates. Germany is not an EU-wide sample.",
            "investment": "U.S. outward direct investment only, on a historical-cost basis and by immediate host. Includes equity and net intercompany debt, not just new projects. Position changes are not investment flows.",
            "archive": "Affiliate/enterprise counts form a separate complete dataset. Newly recovered Swedish/Finnish/French histories are distinct from earlier U.S./German/Norwegian reference series; stale counts remain download-only."},
        "sources": {
            "amcham_2026": source("AmCham Shanghai / PwC China, 2026 China Business Report public release",
                                  "2026-09-10", [us_asset], "Public findings and methodology paragraph.",
                                  "Page metadata says 9 September; the press-release dateline is 10 September. Captured through the normal unauthenticated JavaScript-rendered public website. No member-only report retrieved."),
            "ahk_2026": source("German Chamber of Commerce in China, 2026/27 preliminary finding",
                               "2026-10-06", [german_asset], "Pre-Result, 6 October 2026: result and methodology.",
                               "Interim responses through 29 September, not the completed survey. German findings translated into English. Full release announced for 7 December 2026, still future at review."),
            "bea_2025": source("U.S. Bureau of Economic Analysis, Direct Investment by Country and Industry, 2025",
                               "2026-07-21", [release_asset, directory_asset, *history_assets, position_asset],
                               "Annual worksheets 2000-2025; China and Hong Kong rows, All industries column B. Recent totals independently matched to the selected-country Total column.",
                               "Historical blocks use BEA's currently linked 2000-2009, 2010-2019 and 2020-2025 workbooks, with the exact asset and locator on each observation. The July 2026 release date describes the latest block, not a claim that every historical year was revised then. Source millions converted to nominal USD. Not affiliate counts or annual flows; no 2026 year-end value inferred.")},
        "surveys": {
            "amcham_2026": {"overall_n": 262, "item_n": None, "field_start": None, "field_end": None,
                            "preliminary": False, "fieldwork_note": "Exact fieldwork dates and item-level bases are not stated in the public release."},
            "ahk_2026": {"overall_n": 488, "item_n": 381, "field_start": "2026-09-01", "field_end": "2026-09-29",
                         "preliminary": True, "fieldwork_note": "Interim cutoff only. Survey scheduled through 7 October; full release scheduled 7 December 2026."}},
        "series": {}, "observations": positions}
    for geo, label in (("CHN", "Mainland China"), ("HKG", "Hong Kong")):
        data["series"]["bea_position:" + geo] = {
            "label": label, "measure": "direct_investment_position", "unit": "USD",
            "scope": "U.S. direct investment abroad; immediate host " + label,
            "cadence": "annual", "period_basis": "year-end", "source_id": "bea_2025"}
    findings = [
        ("amcham:profitable", "Profitable China operations (2025)", 78, 2025, "2025 performance, reported in the 2026 survey"),
        ("amcham:optimistic", "Optimistic about the five-year outlook", 58, 2026, "Outlook reported in the 2026 survey"),
        ("amcham:redirecting", "Redirecting planned China investment elsewhere", 39, 2026, "Investment plans reported in the 2026 survey"),
        ("amcham:increased", "Increased investment in China (2025)", 28, 2025, "2025 investment, reported in the 2026 survey"),
        ("ahk:significant", "Significant impact if EU-China trade escalates", 33, 2026, "Conditional expectations; interim responses 1-29 September 2026"),
        ("ahk:moderate", "Moderate impact if EU-China trade escalates", 47, 2026, "Conditional expectations; interim responses 1-29 September 2026"),
        ("ahk:none", "No impact if EU-China trade escalates", 14, 2026, "Conditional expectations; interim responses 1-29 September 2026")]
    for sid, label, value, year, period in findings:
        source_id = "amcham_2026" if sid.startswith("amcham:") else "ahk_2026"
        data["series"][sid] = {"label": label, "measure": "survey_share", "unit": "percent",
                              "scope": ("AmCham Shanghai member respondents; not a census of U.S. businesses" if source_id == "amcham_2026"
                                        else "German Chamber member respondents; not an EU-wide sample"),
                              "cadence": "snapshot", "period_basis": "reported reference period", "source_id": source_id}
        data["observations"].append(dict(series_id=sid, year=year, value=value, source_id=source_id,
                                         status="rounded", comparability=source_id + ":" + sid,
                                         period=period, notes=data["surveys"][source_id]["fieldwork_note"]))
    return validate(data)


def validate(data):
    if data.get("version") != 1 or not data.get("observations") or not data.get("context"):
        raise ValueError("Incomplete current-business dataset")
    cutoff = date.fromisoformat(data["as_of"])
    for sid, source in data["sources"].items():
        if date.fromisoformat(source["release_date"]) > cutoff or not source["assets"]:
            raise ValueError("Unreleased business evidence")
        for asset in source["assets"]:
            if not re.fullmatch("[0-9a-f]{64}", asset["sha256"]):
                raise ValueError("Missing primary-source checksum")
            if not asset["url"].startswith("https://") or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
                raise ValueError("Invalid primary-source provenance")
    for sid, survey in data["surveys"].items():
        n, item = survey["overall_n"], survey["item_n"]
        if sid not in data["sources"] or isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("Invalid overall survey sample")
        if item is not None and (isinstance(item, bool) or not isinstance(item, int) or not 0 < item <= n):
            raise ValueError("Invalid item denominator")
        if bool(survey["field_start"]) != bool(survey["field_end"]):
            raise ValueError("Incomplete survey fieldwork range")
        if survey["field_end"] and not date.fromisoformat(survey["field_start"]) <= date.fromisoformat(survey["field_end"]) <= cutoff:
            raise ValueError("Invalid survey fieldwork dates")
    seen = set()
    for row in data["observations"]:
        definition = data["series"][row["series_id"]]
        key = row["series_id"], row["year"]
        value = row["value"]
        if key in seen or row["source_id"] != definition["source_id"] or row["source_id"] not in data["sources"]:
            raise ValueError("Duplicate or mismatched business observation")
        seen.add(key)
        if isinstance(row["year"], bool) or not isinstance(row["year"], int) or not 2000 <= row["year"] <= cutoff.year:
            raise ValueError("Invalid business reference year")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Missing or invalid business value")
        if not row["period"] or not row["comparability"]:
            raise ValueError("Missing business reference period")
        if definition["measure"] == "survey_share":
            if definition["unit"] != "percent" or not 0 <= value <= 100 or row["source_id"] not in data["surveys"]:
                raise ValueError("Invalid survey percentage or population")
        else:
            if definition["measure"] != "direct_investment_position" or definition["unit"] != "USD":
                raise ValueError("Investment positions cannot be relabelled counts or flows")
            if date(row["year"], 12, 31) > cutoff:
                raise ValueError("Investment reference year has not ended")
            assets = data["sources"][row["source_id"]]["assets"]
            if (not row.get("source_vintage") or not any(
                    row.get("source_url") == asset["url"] and row.get("raw_sha256") == asset["sha256"]
                    and row.get("retrieved_at") == asset["retrieved_at"] for asset in assets)):
                raise ValueError("Investment history requires per-observation workbook provenance")
    return data


def chart_groups(data, chart_id):
    config = CHARTS[chart_id]
    groups = []
    investment_colors = {"CHN": BLUE, "HKG": PARTNER_COLORS["CHN"]}
    for sid in config["series"]:
        definition = data["series"][sid]
        points = sorted((dict(r, plotted_value=r["value"], reported_unit=definition["unit"], plotted_unit=config["unit"])
                         for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
        color = (PARTNER_COLORS["CHN"] if sid.startswith("amcham:") else BLUE
                 if sid.startswith("ahk:") else investment_colors[sid.split(":")[1]])
        groups.append(dict(id=sid, label=definition["label"], color=color, cadence=definition["cadence"],
                           period_basis=definition["period_basis"], scheduled_years=[r["year"] for r in points], points=points))
    return groups


def svg_current_chart(data, chart_id, theme="themarginoferror"):
    config, groups = CHARTS[chart_id], chart_groups(data, chart_id)
    if config["mode"] != "bars":
        return svg_indicator_chart(config, groups, theme, data["context"]["investment"], "business-point")
    esc = lambda value: html.escape(str(value), quote=True)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" role="img" data-axis-max="100" data-bar-orientation="horizontal" aria-label="{esc(config["title"])}">',
             f'<title>{esc(config["title"])}</title><desc>{esc(config["note"])}</desc>',
             f'<rect class="chart-background" width="1000" height="600" fill="{CHART_THEMES[theme]["background"]}"/>',
             f'<g font-family="{esc(FONT)}" fill="{TEXT}">',
             f'<text x="80" y="48" font-size="27">{esc(config["title"])}</text>',
             f'<text x="80" y="85" font-size="18" fill="{MUTED}">{esc(config["subtitle"])}</text>',
             '<text class="axis-unit" x="80" y="126" font-size="18" fill="#6B6B6B">Percent of respondents</text>']
    for i, group in enumerate(groups):
        r = group["points"][0]
        y = 180 + i * 78
        parts.extend([
            f'<text x="80" y="{y}" font-size="20">{esc(group["label"])}</text>',
            f'<text x="920" y="{y}" text-anchor="end" font-size="22">{r["value"]}%</text>',
            f'<rect x="80" y="{y + 16}" width="840" height="9" fill="{GRID}" fill-opacity=".45"/>',
            f'<rect class="business-point" data-series-id="{group["id"]}" data-label="{esc(group["label"])}" '
            f'data-year="{r["year"]}" data-value="{r["value"]}" data-period="{esc(r["period"])}" data-status="{r["status"]}" '
            f'x="80" y="{y + 16}" width="{r["value"] * 8.4}" height="9" fill="{group["color"]}">'
            f'<title>{esc(group["label"])}: {r["value"]}%</title></rect>'])
    import textwrap
    for i, line in enumerate(textwrap.wrap(config["note"], 108)):
        parts.append(f'<text class="figure-source" x="80" y="{530 + i * 19}" fill="{MUTED}" font-size="14">{esc(line)}</text>')
    return "".join(parts) + "</g></svg>"


def csv_text(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({k for r in rows for k in r}), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def build_current_business(root, archive, gallery):
    from . import business_inward
    from .business_analysis import CHARTS as COUNT_CHARTS, build_business, validate_business_data
    from .public_freshness import public_charts
    from .render import esc, export_figure, figure_links

    path = root / "data/site/business_current.json"
    if not path.is_file():
        raise ValueError("Reviewed current business evidence is required; do not restore stale graphs")
    data = validate(json.loads(path.read_text()))
    validate_business_data(archive)
    inward_path = root / "data/site/business_inward.json"
    inward = business_inward.validate(json.loads(inward_path.read_text())) if inward_path.is_file() else None
    inward_section, inward_count = "", 0
    if inward is not None:
        inward_section, inward_count = business_inward.build(root, inward, gallery)
    else:
        business_inward.withdraw(root)
    with public_charts():
        count_charts = build_business(root, archive, gallery)
    counts_page = BeautifulSoup((root / "site/business-presence.html").read_text(), "html.parser")
    count_cards, reference_cards = [], []
    for section in counts_page.select("main > section.series-panel"):
        if not section.select_one(".comparison-chart"):
            continue
        section["class"] = ["comparison-pane", "business-card", "business-count-card"]
        section.h2.name = "h3"
        context = counts_page.new_tag("p", attrs={"class": "chart-context"})
        context.string = COUNT_CHARTS[section["id"]]["subtitle"]
        section.h3.insert_after(context)
        if section["id"] in {"sweden-affiliates-china", "finland-affiliates-china", "france-affiliates-china",
                             "netherlands-affiliates-china", "finland-affiliates-china-eurostat",
                             "italy-affiliates-china", "sweden-affiliates-china-eurostat", "spain-affiliates-china",
                             "denmark-affiliates-china", "austria-affiliates-china", "poland-affiliates-china"}:
            count_cards.append(str(section))
        else:
            config = COUNT_CHARTS[section["id"]]
            latest = max((row for row in archive["observations"]
                          if row["series_id"] in config["series"] and row["value"] is not None),
                         key=lambda row: row["year"])
            source = archive["sources"][latest["source_id"]]
            vintage = counts_page.new_tag("p", attrs={"class": "business-source"})
            vintage.string = (f'Previously available reference: latest period {latest["year"]}. '
                              f'{source["name"]}; {source["vintage"]}.')
            section.h3.insert_after(vintage)
            reference_cards.append(str(section))
    count_section = (
        '<section class="series-panel" id="affiliate-presence"><h2>Affiliates operating in China</h2>'
        '<p class="chart-context">Swedish/Finnish/Danish 2024, provisional Dutch 2024 and French/Spanish 2023 counts, with every reported historical year. '
        'Separate Finnish- and Swedish-UCI Eurostat histories reach 2007; neither is spliced into the broader national counts. '
        'Italian legal-unit counts run from 2007 to 2023; newer grouped-enterprise counts remain separate in downloads. '
        'These count subsidiary or affiliate '
        'entities, not unique parent companies or offices. Country sources have different ownership, sector '
        'and reporting thresholds: they are not a matched ranking or a total to add together. '
        'Shorter histories and methodology changes remain explicit.</p>'
        '<div class="comparison-panels business-counts">' + "".join(count_cards) + '</div></section>'
    ) if count_cards else ""
    reference_section = (
        '<details class="series-panel" id="business-count-references">'
        '<summary>Earlier U.S., German and Norwegian count references</summary>'
        '<p class="chart-context">Previously available source histories, not newly recovered current evidence. '
        'The U.S. outward count still ends in 2023 and does not supply 2024/2025 counts. '
        'German sources have different reporting populations and remain separate. '
        'These reference histories are not a matched country ranking.</p>'
        '<div class="comparison-panels business-counts">' + "".join(reference_cards) + '</div></details>'
    ) if reference_cards else ""
    write_atomic(root / "site/downloads/business-presence.json", json_text(archive))
    historical = [dict(r, **{k: v for k, v in archive["series"][r["series_id"]].items() if k != "notes"},
                       definition_notes=archive["series"][r["series_id"]]["notes"],
                       source_provenance=json.dumps(archive["sources"][r["source_id"]], sort_keys=True))
                  for r in archive["observations"]]
    write_atomic(root / "site/downloads/business-observations.csv", csv_text(historical))
    cards, plotted = {}, []
    for cid, config in CHARTS.items():
        paths = {theme: export_figure(root, Path("business_presence") / theme / cid, svg_current_chart(data, cid, theme))
                 for theme in CHART_THEMES}
        source = data["sources"][config["source_id"]]
        cards[cid] = (
            f'<section class="comparison-pane business-card" id="{cid}"><h3>{esc(config["title"])}</h3>'
            f'<p class="chart-context">{esc(config["subtitle"])}</p>'
            f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(config["title"])}">'
            f'<img src="{esc(paths["themarginoferror"]["png"])}" width="1000" height="600" alt="{esc(config["title"])}"></div>'
            f'<p class="chart-note">{esc(config["note"])}</p>'
            f'<p class="business-source"><a href="{esc(source["assets"][0]["url"])}">Primary source</a>'
            f' · Published {source["release_date"]}</p>{figure_links(paths)}</section>')
        links = {t: {k: p.removeprefix("figures/") for k, p in files.items()} for t, files in paths.items()}
        gallery["business_presence"].append(f'<article><h3>{esc(config["title"])}</h3>{figure_links(links)}</article>')
        for group in chart_groups(data, cid):
            for point in group["points"]:
                plotted.append(dict(point, chart_id=cid, label=group["label"], color=group["color"]))
    records = []
    for row in data["observations"]:
        definition, source = data["series"][row["series_id"]], data["sources"][row["source_id"]]
        survey = data["surveys"].get(row["source_id"], {})
        records.append(dict(row, **definition, overall_n=survey.get("overall_n"), item_n=survey.get("item_n"),
                            field_start=survey.get("field_start"), field_end=survey.get("field_end"),
                            preliminary=survey.get("preliminary", False),
                            source_release=source["release_date"], source_assets=json.dumps(source["assets"], sort_keys=True),
                            source_locator=source["locator"], source_notes=source["notes"]))
    write_atomic(root / "site/downloads/business-current.json", json_text(data))
    write_atomic(root / "site/downloads/business-current-observations.csv", csv_text(records))
    write_atomic(root / "site/downloads/business-current-chart-values.csv", csv_text(plotted))
    exact = "".join(f'<tr><th scope="row">{esc(data["series"][r["series_id"]]["label"])}</th>'
                    f'<td>{esc(r["period"])}</td><td>{r["value"]:,}</td>'
                    f'<td>{esc(data["series"][r["series_id"]]["unit"])}</td></tr>' for r in data["observations"])
    sources = "".join(
        f'<li><strong>{esc(s["name"])}</strong> · {s["release_date"]}. {esc(s["locator"])} {esc(s["notes"])}<ul>' +
        "".join(f'<li><a href="{esc(a["url"])}">Source asset</a> · retrieved {esc(a["retrieved_at"])} · '
                f'SHA-256 <code>{a["sha256"]}</code></li>' for a in s["assets"]) + '</ul></li>'
        for s in data["sources"].values())
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Business links across China and the U.S.</title><link rel="stylesheet" href="assets/style.css"></head>'
        '<body><div class="page"><header><h1>Business links across China and the U.S.</h1></header><main>'
        '<section class="series-panel" id="investment-positions"><h2>U.S. investment already on the books</h2>'
        '<p class="chart-context">Year-end positions from 2000 through 2025, the latest year in BEA&#39;s July 2026 release. '
        'These are nominal dollar positions, not annual flows or company counts. Mainland China and Hong Kong are separate, with independent vertical scales. '
        'Changes can reflect transactions, exchange rates and other valuation adjustments.</p>'
        '<div class="comparison-panels business-investment">' + cards["us-investment-mainland"] + cards["us-investment-hong-kong"] + '</div></section>'
        + inward_section + count_section +
        '<section class="series-panel" id="company-decisions"><h2>What companies are saying now</h2>'
        '<p class="chart-context">Recent member-company findings, not a count of every foreign business. '
        'The American and German chambers ask different questions and must not be read as a country ranking.</p>'
        '<div class="comparison-panels business-surveys">' + cards["us-company-decisions"] + cards["german-company-risk"] + '</div>'
        '<p class="chart-note">The German finding is not an EU-wide survey. Its full report is scheduled for 7 December 2026; '
        'only the published preliminary question is shown here.</p></section>'
        + reference_section +
        '<details id="business-data"><summary>Data, sources & historical archive</summary>'
        '<p><a href="downloads/business-current.json" download>Complete current evidence and provenance · JSON</a> · '
        '<a href="downloads/business-current-observations.csv" download>Every current observation · CSV</a> · '
        '<a href="downloads/business-current-chart-values.csv" download>Every plotted value · CSV</a></p>'
        '<div class="table-scroll"><table><thead><tr><th>Measure</th><th>Reference period</th><th>Reported value</th><th>Unit</th></tr></thead><tbody>' +
        exact + '</tbody></table></div><h3>Primary sources</h3><ul>' + sources +
        '</ul><h3>Complete company-count data</h3><p>The new country histories and earlier reference histories remain distinct. '
        'Older UK/EU and parent-company benchmarks remain download-only; they are not a current business census. '
        'Missing years and source/ownership changes remain explicit.</p>'
        '<p><a href="downloads/business-presence.json" download>All count data and provenance · JSON</a> · '
        '<a href="downloads/business-observations.csv" download>Every count observation · CSV</a> · '
        '<a href="downloads/business-chart-values.csv" download>Every plotted count · CSV</a></p>'
        '</details></main></div></body></html>')
    write_atomic(root / "site/business-presence.html", document)
    return len(CHARTS) + inward_count + count_charts
