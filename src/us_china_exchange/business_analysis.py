"""Frozen, offline business-presence indicators with distinct counting units."""

import csv
import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .indicator_charts import svg_indicator_chart
from .model import json_text
from .pipeline import write_atomic
from .theme import BLUE, CHART_THEMES, PARTNER_COLORS


CHARTS = {
    "us-parent-companies": {
        "title": "U.S. parent companies by host market",
        "subtitle": "Distinct U.S. parents | verified benchmark observations",
        "series": ["bea_parents:china", "bea_parents:europe"], "unit": "U.S. parents", "mode": "levels",
        "note": "BEA benchmark tables. Parent companies, not affiliate entities or offices; a parent may appear in both markets. Reporting exclusions and benchmark coverage differ. Points are not annual estimates."},
    "us-affiliates-china": {
        "title": "U.S.-parent affiliates in China",
        "subtitle": "Majority-owned foreign affiliates | fiscal year ending",
        "series": ["bea_affiliates:china"], "unit": "Affiliates", "mode": "levels",
        "note": "BEA. Nonbank coverage before 2009; reporting cutoffs $7m through 2003, $10m in 2004-08, $25m from 2009. Benchmark boundaries disconnected. Entity counts include holding companies, not all firms or offices."},
    "us-affiliates-europe": {
        "title": "U.S.-parent affiliates in Europe",
        "subtitle": "BEA-defined Europe, not EU27 | fiscal year ending",
        "series": ["bea_affiliates:europe"], "unit": "Affiliates", "mode": "levels",
        "note": "BEA Europe includes the UK and non-EU countries. Nonbank/reporting regimes change in 2004/2009; benchmarks can change coverage. Small exempt entities excluded. Affiliates, not distinct parents or offices."},
    "us-affiliates-index": {
        "title": "U.S. affiliates: China and Europe",
        "subtitle": "Latest comparable benchmark regime | 2020 = 100",
        "series": ["bea_affiliates:china", "bea_affiliates:europe"], "unit": "2020 = 100", "mode": "index",
        "baseline": 2020, "first_year": 2019,
        "note": "Each market uses its own 2020 affiliate count. Only the matching post-2019 benchmark regime is shown; earlier history remains in the level charts. Counts exclude small affiliates and include holding entities."},
    "eu-affiliates-china": {
        "title": "EU-controlled enterprises in China",
        "subtitle": "Fixed EU27 membership, excluding UK | Eurostat",
        "series": ["eurostat_affiliates:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat outward FATS, NACE B-S except O. Enterprise units, not European parent counts or all Europe. Confidential/missing years are gaps; 2021 method boundary disconnected. Not matched to BEA size or ownership coverage."},
}


def validate_business_data(data):
    if set(data) != {"version", "series", "observations", "sources", "coverage", "context"} or data["version"] != 1:
        raise ValueError("Invalid business-presence schema")
    units = {"bea_parents:china": "U.S. parents", "bea_parents:europe": "U.S. parents",
             "bea_affiliates:china": "affiliates", "bea_affiliates:europe": "affiliates",
             "eurostat_affiliates:china": "enterprises"}
    if not data["series"] or not data["sources"] or not isinstance(data["observations"], list):
        raise ValueError("Business definitions, observations and provenance required")
    for sid, definition in data["series"].items():
        if sid not in units or set(definition) != {"label", "measure", "unit", "scope", "cadence", "period_basis", "notes"}:
            raise ValueError("Invalid business series identity")
        if not all(isinstance(v, str) and v for v in definition.values()) or definition["unit"] != units[sid]:
            raise ValueError("Business counting units and populations must remain explicit")
        expected = ("controlled_enterprises", "annual", "reference year") if sid.startswith("eurostat") else (
            ("parent_companies", "benchmark", "fiscal ending year") if sid.startswith("bea_parents")
            else ("majority_owned_affiliates", "annual", "fiscal ending year"))
        if tuple(definition[k] for k in ("measure", "cadence", "period_basis")) != expected:
            raise ValueError("Business measure, timing or observation cadence changed")
        if sid.startswith("bea_parents:") and (definition["measure"] != "parent_companies" or definition["cadence"] != "benchmark"):
            raise ValueError("Benchmark parents must not become annual affiliate counts")
        if sid.startswith("bea_affiliates:") and definition["measure"] != "majority_owned_affiliates":
            raise ValueError("BEA affiliates must not be relabelled parent companies")
        if sid.startswith("eurostat") and ("EU27_2020" not in definition["scope"] or "excluding the UK" not in definition["scope"]):
            raise ValueError("Eurostat EU27 must not be relabelled all Europe")
    for item in data["sources"].values():
        if set(item) != {"name", "vintage", "assets", "locator", "notes"} or not item["assets"]:
            raise ValueError("Business source provenance incomplete")
        for asset in item["assets"]:
            if set(asset) != {"url", "request_url", "sha256", "retrieved_at"} or not re.fullmatch("[0-9a-f]{64}", asset["sha256"]):
                raise ValueError("Invalid business source asset")
            for field in ("url", "request_url"):
                parsed = urlsplit(asset[field])
                if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username is not None:
                    raise ValueError("Invalid public business source URL")
            if datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
                raise ValueError("Business retrieval timestamps need timezones")
    seen = set()
    for r in data["observations"]:
        if set(r) != {"series_id", "year", "value", "source_id", "status", "notes", "comparability"}:
            raise ValueError("Incomplete business observation")
        if r["series_id"] not in data["series"] or r["source_id"] not in data["sources"]:
            raise ValueError("Business observation provenance missing")
        if isinstance(r["year"], bool) or not isinstance(r["year"], int) or not 2000 <= r["year"] <= 9999:
            raise ValueError("Invalid business observation year")
        key = r["series_id"], r["year"]
        if key in seen:
            raise ValueError("Duplicate business observation")
        seen.add(key)
        if r["status"] not in {"observed", "estimated", "provisional", "low_reliability", "suppressed", "missing"}:
            raise ValueError("Invalid business status")
        if (r["value"] is None) != (r["status"] in {"missing", "suppressed"}):
            raise ValueError("Business missingness and status disagree")
        if r["value"] is not None and (isinstance(r["value"], bool) or not isinstance(r["value"], int) or r["value"] < 0):
            raise ValueError("Invalid business count")
        if not r["comparability"] or not isinstance(r["notes"], str):
            raise ValueError("Business comparability definition required")
        if r["series_id"].startswith("bea_") and r["source_id"] != r["series_id"].split(":")[0] + "_" + str(r["year"]):
            raise ValueError("BEA business year/source identity mismatch")
        if r["series_id"].startswith("eurostat") and r["source_id"] != ("fats_out2_r2" if r["year"] <= 2020 else "fats_out_part"):
            raise ValueError("Eurostat method/source boundary mismatch")
    if not all(data["context"].get(k) for k in ("question", "interpretation", "geography", "rights")):
        raise ValueError("Business interpretation and coverage caveats required")
    if any(set(c) != {"id", "status", "description"} for c in data["coverage"]):
        raise ValueError("Invalid business coverage")
    return data


def chart_groups(data, chart_id):
    config, result = CHARTS[chart_id], []
    for sid in config["series"]:
        if sid not in data["series"]:
            continue
        definition = data["series"][sid]
        expected = "affiliates" if config["mode"] == "index" else config["unit"].lower()
        if definition["unit"].lower() != expected:
            raise ValueError("Business chart units do not match")
        rows = sorted((r for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
        ref = next((r for r in rows if r["year"] == config.get("baseline")), None)
        points = []
        for r in rows:
            if r["value"] is None:
                continue
            denominator, value = None, r["value"]
            if config["mode"] == "index":
                if ref is None or not ref["value"] or ref["comparability"] != r["comparability"]:
                    continue
                denominator = ref["value"]
                value = value / denominator * 100
            points.append(dict(r, plotted_value=value, denominator=denominator,
                               reported_unit=definition["unit"], plotted_unit=config["unit"]))
        result.append({"id": sid, "label": definition["label"], "color": PARTNER_COLORS["CHN"] if sid.endswith(":china") else BLUE,
                       "cadence": definition["cadence"], "scheduled_years": [r["year"] for r in rows], "points": points})
    return result


def svg_business_chart(data, chart_id, theme="themarginoferror"):
    config = dict(CHARTS[chart_id])
    groups = chart_groups(data, chart_id)
    if config["mode"] == "index":
        values = [p["plotted_value"] for g in groups for p in g["points"]]
        if values:
            config["y_min"] = math.floor(min(values) / 5) * 5
            config["y_max"] = max(config["y_min"] + 5, math.ceil(max(values) / 5) * 5)
            config["note"] += " Non-zero index axis."
    selected = [r for r in data["observations"] if r["series_id"] in config["series"]]
    if selected:
        last_year = max(r["year"] for r in selected)
        config["last_year"] = last_year
        latest = [r for r in selected if r["year"] == last_year]
        if any(r["status"] == "suppressed" for r in latest):
            config["note"] += f" {last_year} confidential."
        elif any(r["status"] == "provisional" for r in latest):
            config["note"] += f" {last_year} provisional."
        if any(r["status"] == "estimated" for r in selected):
            config["note"] += " Includes source estimates."
    return svg_indicator_chart(
        config, groups, theme,
        "Business entity counts, not people, branch locations or cross-border flows. Exact definitions and observations accompany this figure.",
        "business-point")


def build_business(root, data, gallery):
    from .render import esc, export_figure, figure_links, remove_figure

    validate_business_data(data)
    cards, plotted, count = [], [], 0
    for chart_id, config in CHARTS.items():
        paths = {}
        for theme in CHART_THEMES:
            svg = svg_business_chart(data, chart_id, theme)
            relative = Path("business_presence") / theme / chart_id
            if svg is None:
                remove_figure(root, relative)
            else:
                paths[theme] = export_figure(root, relative, svg)
        body = '<p class="gap">No verified observations for this indicator in the frozen snapshot.</p>'
        if paths:
            count += 1
            body = (f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(config["title"])}">'
                    f'<img src="{esc(paths["themarginoferror"]["png"])}" width="1000" height="600" loading="lazy" '
                    f'alt="{esc(config["title"])} - {esc(config["subtitle"])}"></div>'
                    f'<p class="chart-note">{esc(config["note"])}</p>' + figure_links(paths))
            links = {t: {k: p.removeprefix("figures/") for k, p in files.items()} for t, files in paths.items()}
            gallery["business_presence"].append(
                f'<article><h3>{esc(config["title"])}</h3><p>{esc(config["subtitle"])}</p>{figure_links(links)}</article>')
            exact = []
            for group in chart_groups(data, chart_id):
                for p in group["points"]:
                    definition, provenance = data["series"][group["id"]], data["sources"][p["source_id"]]
                    plotted.append(dict(p, chart_id=chart_id, label=group["label"], scope=definition["scope"],
                                        definition_notes=definition["notes"], period_basis=definition["period_basis"],
                                        source_name=provenance["name"], source_vintage=provenance["vintage"]))
                    exact.append(f'<tr><th scope="row">{esc(group["label"])}</th><td>{p["year"]}</td><td>{p["value"]:,}</td>'
                                 f'<td>{p["plotted_value"]:,.4f}</td><td>{esc(p["status"])}</td>'
                                 f'<td>{esc(provenance["vintage"])}</td></tr>')
            body += ('<details><summary>Exact reported and plotted values</summary><div class="table-scroll"><table>'
                     '<thead><tr><th>Series</th><th>Year / ending year</th><th>Reported count</th>'
                     f'<th>{esc(config["unit"])}</th><th>Status</th><th>Source vintage</th></tr></thead><tbody>'
                     + "".join(exact) + '</tbody></table></div></details>')
        cards.append(f'<section class="series-panel" id="{chart_id}"><h2>{esc(config["title"])}</h2>{body}</section>')
    raw = []
    for r in data["observations"]:
        definition, provenance = data["series"][r["series_id"]], data["sources"][r["source_id"]]
        raw.append(dict(r, **{k: v for k, v in definition.items() if k != "notes"}, definition_notes=definition["notes"],
                        source_name=provenance["name"], source_vintage=provenance["vintage"],
                        source_locator=provenance["locator"], source_assets=json.dumps(provenance["assets"], sort_keys=True)))
    write_atomic(root / "site/downloads/business-presence.json", json_text(data))
    for name, rows in [("business-observations", raw), ("business-chart-values", plotted)]:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=sorted({k for r in rows for k in r}), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        write_atomic(root / "site/downloads" / (name + ".csv"), stream.getvalue())
    coverage = "".join(f'<tr><th scope="row">{esc(c["id"].replace("_", " "))}</th><td>{esc(c["status"])}</td>'
                       f'<td>{esc(c["description"])}</td></tr>' for c in data["coverage"])
    sources = "".join(
        f'<li><strong>{esc(s["name"])} - {esc(s["vintage"])}</strong>. {esc(s["locator"])}. {esc(s["notes"])}<ul>'
        + "".join(f'<li><a href="{esc(a["url"])}">Primary source</a>; retrieved {esc(a["retrieved_at"])}; '
                  f'SHA-256 <code>{a["sha256"]}</code></li>' for a in s["assets"]) + '</ul></li>'
        for s in data["sources"].values())
    latest = {}
    for sid in data["series"]:
        rows = [r for r in data["observations"] if r["series_id"] == sid and r["value"] is not None]
        if rows:
            r = max(rows, key=lambda r: r["year"])
            latest[sid] = f'{r["value"]:,} in {r["year"]}'
    headline = (f'<p>Latest verified benchmark parent counts: China <strong>{latest.get("bea_parents:china", "unavailable")}</strong>; '
                f'Europe <strong>{latest.get("bea_parents:europe", "unavailable")}</strong>. '
                f'The separate annual majority-owned affiliate counts are China {latest.get("bea_affiliates:china", "unavailable")} '
                f'and Europe {latest.get("bea_affiliates:europe", "unavailable")}. Do not substitute one counting unit for the other.</p>'
                f'<p>{esc(data["context"].get("release_timing", ""))}</p>')
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Business presence | China and Europe</title>'
                '<link rel="stylesheet" href="assets/style.css"></head><body><div class="page"><header>'
                '<p><a href="index.html">Exchange dashboard</a>' +
                (' · <a href="language-learning.html">Language learning</a>' if (root / "site/language-learning.html").is_file() else "") + '</p>'
                f'<h1>Business ties.</h1><p class="lead">{esc(data["context"]["question"])}</p>'
                '<p><strong>Parent companies, affiliate enterprises and physical branches are different counting units.</strong> '
                'This page covers both U.S. companies in China versus Europe and EU-controlled enterprises in China, '
                'without pretending those sources have matched populations.</p>'
                f'<p>{esc(data["context"]["interpretation"])}</p><p>{esc(data["context"]["geography"])}</p>'
                '<p>These are business-presence stocks, not annual openings, closures, investment flows or a census of '
                'office locations. No current count of all American-owned businesses in China is established by this publication.</p>'
                '<p><a href="downloads/business-presence.json" download>Complete dataset and provenance · JSON</a> · '
                '<a href="downloads/business-observations.csv" download>Every source observation · CSV</a> · '
                '<a href="downloads/business-chart-values.csv" download>Every plotted value · CSV</a></p></header><main>'
                '<section class="series-panel"><h2>What the counts establish</h2>' + headline +
                '<p>Thresholds are nominal dollars, not inflation-adjusted. Apparent growth across survey benchmarks can '
                'reflect improved coverage. Benchmark parent observations remain isolated; annual affiliate lines break '
                'at the 2004, 2009, 2014 and 2019 regime boundaries. Eurostat changes methodology in 2021.</p></section>'
                + "".join(cards) + '<section class="series-panel"><h2>Coverage and unresolved counts</h2>'
                '<div class="table-scroll"><table><thead><tr><th>Indicator</th><th>Status</th><th>Definition</th></tr></thead>'
                '<tbody>' + coverage + '</tbody></table></div></section><section class="series-panel"><h2>Primary sources</h2>'
                f'<p>{esc(data["context"]["rights"])}</p><details><summary>Sources, vintages and checksums</summary><ul>'
                + sources + '</ul></details></section></main></div></body></html>')
    write_atomic(root / "site/business-presence.html", document)
    return count
