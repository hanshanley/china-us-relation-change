"""UBO-classified U.S. affiliate counts, with historical population breaks."""

import copy
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import xlrd
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from pypdf import PdfReader

from .model import json_text
from .pipeline import write_atomic


GEOGRAPHIES = {"CHN": "China", "HKG": "Hong Kong"}
CHARTS = {"china-ubo-us-affiliates": "CHN", "hong-kong-ubo-us-affiliates": "HKG"}


def parse_counts(content, source):
    notes = ""
    member = source["table_member"]
    if member:
        archive = zipfile.ZipFile(io.BytesIO(content))
        notes = " ".join(" ".join(page.extract_text() or "" for page in
                         PdfReader(io.BytesIO(archive.read(source["definition_member"]))).pages).split())
        content = archive.read(member)
    if content.startswith(b"PK"):
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        rows = list(book[source["worksheet"]].values)
        book.close()
    else:
        book = xlrd.open_workbook(file_contents=content)
        sheet = book.sheet_by_name(source["worksheet"])
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        book.release_resources()
    header = " ".join(str(v) for row in rows[:8] for v in row)
    if "Country of UBO" not in header or not re.search("Number of (?:Affiliates|affiliates)", header):
        raise ValueError("Expected affiliate counts by country of UBO, not another population")
    if not any(re.search(r"^(?:Total|Number of affiliates\b.*)$", str(row[1]).strip(), re.I) for row in rows[:8]):
        raise ValueError("The count column must be affiliates, not consolidated companies or money")
    match = re.search(r"Greater Than\s*\$\s*(\d+)\s*Million", header, re.I)
    if not match and notes:
        pattern = (r"Tables\s+J[\s-]*2\s+and\s+J[\s-]*3" if source["year"] <= 2001 else
                   r"Tables\s+III[ .-]*A[ .-]*4\s+and\s+III[ .-]*A[ .-]*5")
        start = re.search(pattern, notes, re.I)
        if start:
            match = re.search(r"greater than\s*\$\s*(\d+)\s*million",
                              notes[start.start():start.start() + 1800], re.I)
    if not match or int(match[1]) * 1_000_000 != source["size_threshold_usd"]:
        raise ValueError("Published count threshold differs or requires review")
    result = {}
    for i, row in enumerate(rows, 1):
        for geo, label in GEOGRAPHIES.items():
            if str(row[0]).strip() != label:
                continue
            if geo in result or source["cells"][geo] != f"B{i}":
                raise ValueError("Duplicate or moved affiliate country cell")
            value = row[1]
            if isinstance(value, str):
                value = value.strip()
                if value in {"D", "(D)"}:
                    result[geo] = (None, "suppressed")
                    continue
                if re.fullmatch(r"\d+|\d{1,3}(?:,\d{3})+", value):
                    value = int(value.replace(",", ""))
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0 or value != int(value)):
                raise ValueError("Invalid count or unreviewed range; never fill with zero")
            result[geo] = (int(value), source["status"])
    if set(result) != set(GEOGRAPHIES):
        raise ValueError("Both separately reported China and Hong Kong counts are required")
    return result


def validate(data):
    if data.get("version") != 1 or not data.get("context"):
        raise ValueError("Invalid inward-affiliate dataset")
    cutoff = date.fromisoformat(data["as_of"])
    if set(data["series"]) != {"bea_mousa:" + geo for geo in GEOGRAPHIES}:
        raise ValueError("Mainland and Hong Kong must remain separately identified")
    for sid, definition in data["series"].items():
        if (definition["unit"] != "affiliates" or definition["country_basis"] != "UBO"
                or definition["origin"] != sid.split(":")[1] or definition["destination"] != "USA"
                or definition["measure"] != "majority_owned_us_affiliates"
                or definition["period_basis"] != "fiscal ending year"):
            raise ValueError("Affiliate ownership, direction, period or counting unit changed")
    for source in data["sources"].values():
        if ("majority-owned" not in source["scope"].lower()
                or source["bank_coverage"] not in {"nonbank_only", "including_banks"}
                or ("nonbank" in source["scope"].lower()) != (source["bank_coverage"] == "nonbank_only")
                or source["size_threshold_usd"] not in {3_000_000, 10_000_000, 15_000_000, 20_000_000}
                or source["status"] not in {"observed", "provisional"}
                or set(source["cells"]) != set(GEOGRAPHIES)):
            raise ValueError("Unreviewed affiliate population or threshold")
        for asset in [source["asset"]] + ([source["page_asset"]] if source.get("page_asset") else []):
            if (not re.fullmatch("[0-9a-f]{64}", asset["sha256"]) or not asset["url"].startswith("https://")
                    or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None):
                raise ValueError("Invalid original affiliate source provenance")
    seen = set()
    for row in data["observations"]:
        source = data["sources"][row["source_id"]]
        key = row["series_id"], row["year"]
        if key in seen or row["series_id"] not in data["series"]:
            raise ValueError("Duplicate or unknown affiliate observation")
        seen.add(key)
        if (type(row["year"]) is not int or not 2000 <= row["year"] <= cutoff.year
                or row["year"] != source["year"]
                or row["bank_coverage"] != source["bank_coverage"]
                or row["size_threshold_usd"] != source["size_threshold_usd"]
                or row["comparability"] != f'{source["bank_coverage"]}:USD{source["size_threshold_usd"]}'):
            raise ValueError("Affiliate year or comparability block changed")
        if row["status"] not in {"observed", "provisional", "suppressed"}:
            raise ValueError("Unreviewed affiliate status")
        if row["value"] is not None and row["status"] != source["status"]:
            raise ValueError("Affiliate release status differs from its source")
        if ((row["value"] is None) != (row["status"] == "suppressed")
                or row["value"] is not None and (type(row["value"]) is not int or row["value"] < 0)):
            raise ValueError("Affiliate missingness or count changed")
    expected = {(sid, source_id) for sid in data["series"] for source_id in data["sources"]}
    if not seen or {(row["series_id"], row["source_id"]) for row in data["observations"]} != expected:
        raise ValueError("Every source year requires both country count records")
    return data


def rebuild(data, cache):
    result = copy.deepcopy(validate(data))
    observations = []
    for source_id, source in sorted(data["sources"].items(), key=lambda item: item[1]["year"]):
        asset = source["asset"]
        content = (Path(cache) / asset["sha256"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Original affiliate workbook checksum mismatch")
        if source.get("page_asset"):
            page_asset = source["page_asset"]
            page = (Path(cache) / page_asset["sha256"]).read_bytes()
            if hashlib.sha256(page).hexdigest() != page_asset["sha256"]:
                raise ValueError("Original affiliate index checksum mismatch")
            text = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
            if source["scope"] not in text or str(source["year"]) not in text:
                raise ValueError("Affiliate table's primary scope or year differs")
        for geo, (value, status) in parse_counts(content, source).items():
            observations.append({
                "series_id": "bea_mousa:" + geo, "year": source["year"], "value": value,
                "source_id": source_id, "status": status, "period": str(source["year"]),
                "bank_coverage": source["bank_coverage"], "size_threshold_usd": source["size_threshold_usd"],
                "comparability": f'{source["bank_coverage"]}:USD{source["size_threshold_usd"]}',
            })
    result["observations"] = sorted(observations, key=lambda row: (row["year"], row["series_id"]))
    return validate(result)


def export(data, directory):
    validate(data)
    rows = []
    for row in data["observations"]:
        source = data["sources"][row["source_id"]]
        geo = row["series_id"].split(":")[1]
        rows.append(dict(row, **data["series"][row["series_id"]],
                         source_url=source["asset"]["url"], raw_sha256=source["asset"]["sha256"],
                         retrieved_at=source["asset"]["retrieved_at"], source_vintage=source["vintage"],
                         table_member=source["table_member"], worksheet=source["worksheet"],
                         cell=source["cells"][geo], source_scope=source["scope"],
                         definition_member=source["definition_member"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    directory = Path(directory)
    write_atomic(directory / "business-inward.json", json_text(data))
    write_atomic(directory / "business-inward-observations.csv", stream.getvalue())


def chart_groups(data, geo):
    from .theme import PARTNER_COLORS

    sid = "bea_mousa:" + geo
    rows = sorted((row for row in data["observations"] if row["series_id"] == sid), key=lambda row: row["year"])
    latest = rows[-1]
    points = [dict(row, plotted_value=row["value"], reported_unit="affiliates", plotted_unit="Affiliates",
                   period=f'Fiscal year ending {row["year"]}')
              for row in rows if row["comparability"] == latest["comparability"] and row["value"] is not None]
    return [{"id": sid, "label": data["series"][sid]["label"], "color": PARTNER_COLORS[geo],
             "cadence": "annual", "period_basis": "fiscal ending year",
             "scheduled_years": [row["year"] for row in rows if row["comparability"] == latest["comparability"]],
             "points": points}]


def svg_count_chart(data, chart_id, theme):
    from .indicator_charts import svg_indicator_chart

    geo = CHARTS[chart_id]
    groups = chart_groups(data, geo)
    years = [point["year"] for point in groups[0]["points"]]
    latest = max((row for row in data["observations"] if row["series_id"] == groups[0]["id"]),
                 key=lambda row: row["year"])
    config = {"title": "U.S. affiliates: " + data["series"]["bea_mousa:" + geo]["label"],
              "subtitle": f"BEA | Fiscal years ending {min(years)}-{max(years)}",
              "mode": "levels", "unit": "Affiliates", "covid_context": False,
              "first_year": min(groups[0]["scheduled_years"]), "last_year": max(groups[0]["scheduled_years"]),
              "note": "BEA majority-owned U.S. affiliates by UBO; above $20m. Includes banks; not every firm or office. "
                      f'Benchmark frames can change; {latest["year"]} is {latest["status"]}. Earlier populations are separate.'}
    return svg_indicator_chart(config, groups, theme, data["context"]["comparability"], "business-point")


def withdraw(root):
    from .render import remove_figure
    from .theme import CHART_THEMES

    for chart_id in CHARTS:
        for theme in CHART_THEMES:
            remove_figure(root, Path("business_presence") / theme / chart_id)
    for name in ("business-inward.json", "business-inward-observations.csv", "business-inward-chart-values.csv"):
        (root / "site/downloads" / name).unlink(missing_ok=True)


def build(root, data, gallery):
    from .render import esc, export_figure, figure_links
    from .theme import CHART_THEMES

    validate(data)
    export(data, root / "site/downloads")
    cards, plotted = [], []
    for chart_id, geo in CHARTS.items():
        groups = chart_groups(data, geo)
        last = max((row for row in data["observations"] if row["series_id"] == groups[0]["id"]),
                   key=lambda row: row["year"])
        source = data["sources"][last["source_id"]]
        paths = {theme: export_figure(root, Path("business_presence") / theme / chart_id,
                                     svg_count_chart(data, chart_id, theme)) for theme in CHART_THEMES}
        label = data["series"]["bea_mousa:" + geo]["label"]
        cards.append(
            f'<section class="comparison-pane business-card" id="{chart_id}"><h3>{esc(label)}</h3>'
            '<p class="chart-context">Majority-owned U.S. affiliates · Country of ultimate beneficial owner</p>'
            f'<div class="comparison-chart" tabindex="0" role="region" aria-label="U.S. affiliates: {esc(label)}">'
            f'<img src="{esc(paths["themarginoferror"]["png"])}" width="1000" height="600" alt="U.S. affiliates: {esc(label)}"></div>'
            '<p class="chart-note">Including banks; assets, sales or net income/loss above $20m. '
            f'Reporting units, not every legal company or office. Benchmark frames can change; '
            f'{last["year"]} is {"preliminary" if last["status"] == "provisional" else "reported"}.</p>'
            f'<p class="business-source"><a href="{esc(source["asset"]["url"])}">Original BEA table</a></p>'
            f'{figure_links(paths)}</section>')
        links = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                 for theme, files in paths.items()}
        gallery["business_presence"].append(f'<article><h3>U.S. affiliates: {esc(label)}</h3>{figure_links(links)}</article>')
        plotted.extend(dict(point, chart_id=chart_id, label=groups[0]["label"], color=groups[0]["color"])
                       for point in groups[0]["points"])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in plotted for key in row}), lineterminator="\n")
    writer.writeheader()
    writer.writerows(plotted)
    write_atomic(root / "site/downloads/business-inward-chart-values.csv", stream.getvalue())
    indexed = {(row["series_id"], row["year"]): row for row in data["observations"]}
    table = []
    for year in sorted({row["year"] for row in data["observations"]}):
        mainland, hong_kong = [indexed["bea_mousa:" + geo, year] for geo in GEOGRAPHIES]
        population = "Nonbank only" if mainland["bank_coverage"] == "nonbank_only" else "Including banks"
        value = lambda row: f'{row["value"]:,}' if row["value"] is not None else "Suppressed"
        table.append(f'<tr><th scope="row">{year}</th><td>{value(mainland)}</td><td>{value(hong_kong)}</td>'
                     f'<td>{population}; above ${mainland["size_threshold_usd"] // 1_000_000}m</td></tr>')
    sources = "".join(
        f'<li>{source["year"]}: <a href="{esc(source["asset"]["url"])}">{esc(source["vintage"])}</a>; '
        f'{esc(source["table_member"] or source["worksheet"])}; China {source["cells"]["CHN"]}, '
        f'Hong Kong {source["cells"]["HKG"]}. SHA-256 <code>{source["asset"]["sha256"]}</code></li>'
        for source in data["sources"].values())
    return (
        '<section class="series-panel" id="us-affiliate-counts"><h2>China-linked affiliates in the United States</h2>'
        '<p class="chart-context">Counts by ultimate beneficial owner, not the immediate foreign parent. '
        'Mainland China and Hong Kong are separate, with independent vertical scales. '
        'The comparable $20m-threshold history below starts in 2012; earlier observations use different populations.</p>'
        '<div class="comparison-panels business-affiliates">' + "".join(cards) + '</div>'
        '<details id="business-inward-data"><summary>All reported counts, 2000-2024, and why the definitions matter</summary>'
        '<p>The full history has four distinct populations: nonbank above $3m in 2000-01; nonbank above $10m in 2002-06; '
        'including banks above $15m in 2007-11; including banks above $20m in 2012-24. '
        'The earlier levels are not joined to the current chart as a single comparable trend. '
        'Survey benchmarks also update coverage; a change is not necessarily a new firm or an exit. '
        'Macau is not supplied by these count tables and is not assigned zero.</p>'
        '<p><a href="downloads/business-inward.json" download>Every reported count and source · JSON</a> · '
        '<a href="downloads/business-inward-observations.csv" download>All 50 country-year observations · CSV</a> · '
        '<a href="downloads/business-inward-chart-values.csv" download>Current-definition plotted values · CSV</a></p>'
        '<div class="table-scroll"><table><thead><tr><th>Fiscal year ending</th><th>Mainland China UBO</th>'
        '<th>Hong Kong UBO</th><th>Count coverage</th></tr></thead><tbody>' + "".join(table) +
        '</tbody></table></div><h3>Original annual tables</h3><ul>' + sources +
        '</ul></details></section>', len(CHARTS))
