"""Frozen, offline business-presence indicators with distinct counting units."""

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .indicator_charts import svg_indicator_chart
from .public_freshness import current_groups
from .model import json_text
from .pipeline import write_atomic
from .theme import BLUE, CHART_THEMES, GOLD, GREEN, MUTED, PARTNER_COLORS


RETIRED_CHARTS = {"us-parent-companies", "us-affiliates-europe", "us-affiliates-index"}
BENCHMARK_CHART = "us-parent-companies-china"
COLORS = {"bea_affiliates:china": PARTNER_COLORS["CHN"], "bea_parents:china": PARTNER_COLORS["CHN"],
          "eurostat_affiliates:china": BLUE, "eurostat_historical_eu:china": MUTED,
          "eurostat_uk:china": GOLD, "eurostat_norway:china": GREEN, "ssb_norway:china": GREEN,
          "bundesbank_germany:china": "#79638A", "eurostat_germany:china": "#A397AC",
          "eurostat_netherlands:china": "#617C78",
          "tillvaxtanalys_sweden:china": "#526F76", "statfin_finland:china": "#6F7354",
          "eurostat_france:china": "#8A6556", "eurostat_finland:china": "#999D7D",
          "eurostat_sweden:china": "#97AAAE",
          "eurostat_italy:china": "#7E6D7A", "eurostat_italy_legal:china": "#7E6D7A"}
ORIGINS = {"bea_affiliates:china": "us", "bea_parents:china": "us",
           "eurostat_affiliates:china": "eu", "eurostat_historical_eu:china": "eu",
           "eurostat_uk:china": "uk", "eurostat_norway:china": "norway", "ssb_norway:china": "norway",
           "bundesbank_germany:china": "germany", "eurostat_germany:china": "germany",
           "eurostat_netherlands:china": "netherlands",
           "tillvaxtanalys_sweden:china": "sweden", "statfin_finland:china": "finland",
           "eurostat_france:china": "france", "eurostat_finland:china": "finland",
           "eurostat_sweden:china": "sweden",
           "eurostat_italy:china": "italy", "eurostat_italy_legal:china": "italy"}
CHARTS = {
    "us-affiliates-china": {
        "title": "U.S.-parent affiliates in China",
        "subtitle": "Earlier reference | 2000-2023 | fiscal year ending",
        "series": ["bea_affiliates:china"], "unit": "Affiliates", "mode": "levels",
        "note": "BEA. Nonbank coverage before 2009; reporting cutoffs $7m through 2003, $10m in 2004-08, $25m from 2009. Benchmark boundaries disconnected. Entity counts include holding companies, not all firms or offices."},
    "eu-affiliates-china": {
        "title": "EU-reporting groups in China",
        "subtitle": "Annual observations | different memberships kept separate",
        "series": ["eurostat_historical_eu:china", "eurostat_affiliates:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat. EU27 2023 is confidential; 2022 is the latest disclosed value. Historical EU27 includes UK, excludes Croatia; current EU27 reverses those members. Membership, NACE and 2021 method breaks stay disconnected. Not matched to BEA coverage."},
    "uk-affiliates-china": {
        "title": "UK-controlled enterprises in China",
        "subtitle": "Annual observations, 2009-2019 | not UK investment flows",
        "series": ["eurostat_uk:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat history; NACE Rev. 1.1 in 2009 and Rev. 2 from 2010 stay disconnected. ONS revised 2018/2019 estimates; survey breaks and 2018 source/sector boundary disconnected. ONS total activity includes agriculture. No later outward-affiliate counts verified; do not fill with inward or FDI data."},
    "norway-affiliates-china": {
        "title": "Norwegian-controlled enterprises in China",
        "subtitle": "Earlier reference | From 2008 | Statistics Norway",
        "series": ["ssb_norway:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Statistics Norway, all industries. Direct or indirect Norwegian control; Hong Kong and Macao reported separately. "
        "This full source history replaces the narrower Eurostat view, not just its last year. "
        "Norway is outside the EU; counts are enterprises, not Norwegian parents or office locations."},
    "germany-affiliates-china": {
        "title": "German-controlled enterprises in China",
        "subtitle": "Earlier reference | Bundesbank | 2021-2024",
        "series": ["bundesbank_germany:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Bundesbank: German majority control, assets above EUR 3m; includes branches. "
        "Hong Kong and Macau are separate. The longer Eurostat history has a different population and is shown separately."},
    "germany-affiliates-china-eurostat": {
        "title": "German enterprises: the longer Eurostat history",
        "subtitle": "Earlier reference | Eurostat | 2010-2023",
        "series": ["eurostat_germany:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat, NACE B-S except O; China except Hong Kong. "
        "The 2021 methodology boundary is retained. Not spliced with the Bundesbank counts; Germany overlaps EU27."},
    "sweden-affiliates-china": {
        "title": "Swedish-group subsidiaries in China",
        "subtitle": "National annual observations, 2010-2024",
        "series": ["tillvaxtanalys_sweden:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Swedish Agency for Growth Policy Analysis. Subsidiaries, not parents; this national history starts in 2010. "
        "2018: EGR coverage/imputation; 2019: frame repair; 2021: ownership-concept change. "
        "The longer Eurostat population is separate. Hong Kong and Macau separate."},
    "finland-affiliates-china": {
        "title": "Finnish-reported affiliates in China",
        "subtitle": "Supplementary annual history, 2020-2024",
        "series": ["statfin_finland:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Statistics Finland. Active affiliates and branches, all sizes/industries; not unique parents. "
        "2021: EBS methodology boundary. Earlier matching national counts unavailable; the longer Eurostat population is separate. Hong Kong and Macau separate."},
    "france-affiliates-china": {
        "title": "French-controlled enterprises in China",
        "subtitle": "China except Hong Kong | Eurostat, 2007-2023",
        "series": ["eurostat_france:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat. 2008 unreported; 2007 pilot/2009 frame, 2010 NACE, 2016 source and 2021 EBS breaks. "
        "Not spliced with rounded INSEE counts. The reported host category is China except Hong Kong."},
    "netherlands-affiliates-china": {
        "title": "Dutch-controlled enterprises in China",
        "subtitle": "China except Hong Kong | 2007-2024 | 2024 provisional",
        "series": ["eurostat_netherlands:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat and CBS. Dutch-resident ultimate control; financial/nonfinancial affiliates, not parents. "
        "NACE changes in 2010; the 2021 method is not directly comparable with earlier years. "
        "No comparable 2019 change or pre-2007 count inferred. Netherlands overlaps EU27; do not sum them."},
    "finland-affiliates-china-eurostat": {
        "title": "Finnish-controlled enterprises: the longer history",
        "subtitle": "China except Hong Kong | Eurostat, 2007-2023",
        "series": ["eurostat_finland:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat, Finnish-UCI market producers. 2010 NACE, 2013 YTY system and 2021 EBS boundaries retained. "
        "The broader national affiliate/branch counts above are a different population, not a splice or a matched comparison."},
    "italy-affiliates-china": {
        "title": "Italian-controlled legal units in China",
        "subtitle": "Legal-unit history, 2007-2023 | Eurostat / ISTAT",
        "series": ["eurostat_italy_legal:china"], "unit": "Legal units", "mode": "levels",
        "note": "Italian ultimate control. Eurostat legal units through 2020; ISTAT continues the same unit "
        "through 2023 (national label: Cina), with matching 2019/2020 controls. Keep the 2010 NACE and "
        "2021 source boundaries. Grouped enterprise counts are separate in downloads, never spliced here. "
        "No pre-2007, cross-source 2019 change or unpublished 2024/2025 count is inferred."},
    "sweden-affiliates-china-eurostat": {
        "title": "Swedish-controlled enterprises: the longer history",
        "subtitle": "China except Hong Kong | Eurostat, 2007-2023",
        "series": ["eurostat_sweden:china"], "unit": "Enterprises", "mode": "levels",
        "note": "Eurostat, Swedish ultimate control; official imputation can apply. 2009 confidential, not zero. "
        "Keep 2008 classification/2010 table, 2018 enterprise-unit/EGR and 2021 EBS boundaries. "
        "Not spliced into national subsidiary counts."},
    BENCHMARK_CHART: {
        "title": "U.S. parent companies with China affiliates",
        "subtitle": "Supplementary benchmark observations | NOT an annual series",
        "series": ["bea_parents:china"], "unit": "U.S. parents", "mode": "levels",
        "note": "BEA benchmarks only: 2004, 2009, 2014 and 2019. Distinct reported U.S. parents, not annual affiliate entities. Reporting exclusions and benchmark coverage differ. No annual interpolation or current company census."},
}


def validate_business_data(data):
    if set(data) != {"version", "series", "observations", "sources", "coverage", "context"} or data["version"] != 1:
        raise ValueError("Invalid business-presence schema")
    units = {sid: "U.S. parents" if sid.startswith("bea_parents") else "affiliates" if sid.startswith("bea_affiliates")
             else "legal units" if sid == "eurostat_italy_legal:china" else "enterprises" for sid in COLORS}
    if not data["series"] or not data["sources"] or not isinstance(data["observations"], list):
        raise ValueError("Business definitions, observations and provenance required")
    for sid, definition in data["series"].items():
        if sid not in units or set(definition) != {"label", "measure", "unit", "scope", "cadence", "period_basis", "notes"}:
            raise ValueError("Invalid business series identity")
        if not all(isinstance(v, str) and v for v in definition.values()) or definition["unit"] != units[sid]:
            raise ValueError("Business counting units and populations must remain explicit")
        controlled_measure = "controlled_legal_units" if sid == "eurostat_italy_legal:china" else "controlled_enterprises"
        expected = (controlled_measure, "annual", "reference year") if sid.startswith(
            ("eurostat", "ssb_", "bundesbank_", "tillvaxtanalys_", "statfin_")) else (
            ("parent_companies", "benchmark", "fiscal ending year") if sid.startswith("bea_parents")
            else ("majority_owned_affiliates", "annual", "fiscal ending year"))
        if tuple(definition[k] for k in ("measure", "cadence", "period_basis")) != expected:
            raise ValueError("Business measure, timing or observation cadence changed")
        if sid.startswith("bea_parents:") and (definition["measure"] != "parent_companies" or definition["cadence"] != "benchmark"):
            raise ValueError("Benchmark parents must not become annual affiliate counts")
        if sid.startswith("bea_affiliates:") and definition["measure"] != "majority_owned_affiliates":
            raise ValueError("BEA affiliates must not be relabelled parent companies")
        if sid == "eurostat_affiliates:china" and ("EU27_2020" not in definition["scope"] or "excluding the UK" not in definition["scope"]):
            raise ValueError("Eurostat EU27 must not be relabelled all Europe")
        if sid == "eurostat_historical_eu:china" and ("EU27_2007" not in definition["scope"] or "including the UK" not in definition["scope"]):
            raise ValueError("Historical EU membership must remain distinct")
        if sid == "eurostat_netherlands:china" and not all(
                token in definition["scope"] for token in ("Dutch-resident UCI", "China except Hong Kong")):
            raise ValueError("Dutch control and host-country scope must remain explicit")
        if sid.startswith("eurostat_italy") and not all(
                token in definition["scope"] for token in ("Italy-resident UCI", "China except Hong Kong")):
            raise ValueError("Italian control and host-country scope must remain explicit")
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
        expected_source = {
            "eurostat_affiliates:china": "fats_out2_r2" if r["year"] <= 2020 else "fats_out_part",
            "eurostat_historical_eu:china": "fats_out2_EU27_2007" if r["year"] <= 2009 else "fats_out2_r2_EU27_2007",
            "eurostat_uk:china": ("fats_out2_UK" if r["year"] <= 2009 else
                                 "ons_2019" if r["year"] in {2018, 2019} else "fats_out2_r2_UK"),
            "eurostat_norway:china": "fats_out2_r2_NO" if r["year"] <= 2020 else "fats_out_part_NO",
            "eurostat_germany:china": "fats_out2_r2_DE" if r["year"] <= 2020 else "fats_out_part_DE",
            "eurostat_netherlands:china": (
                "fats_out2_NL" if r["year"] <= 2009 else "fats_out2_r2_NL" if r["year"] <= 2020
                else "cbs_netherlands_2026" if r["year"] == 2024 and r["source_id"] == "cbs_netherlands_2026"
                else "fats_out_part_NL"),
            "eurostat_france:china": ("fats_out2_FR" if r["year"] <= 2009 else
                                     "fats_out2_r2_FR" if r["year"] <= 2020 else "fats_out_part_FR"),
            "eurostat_finland:china": ("fats_out2_FI" if r["year"] <= 2009 else
                                      "fats_out2_r2_FI" if r["year"] <= 2020 else "fats_out_part_FI"),
            "eurostat_italy_legal:china": (
                "fats_out2_IT" if r["year"] <= 2009 else "fats_out2_r2_IT" if r["year"] <= 2020
                else f"istat_italy_legal_{r['year']}"),
            "eurostat_italy:china": "fats_out_part_IT",
            "eurostat_sweden:china": ("fats_out2_SE" if r["year"] <= 2009 else
                                     "fats_out2_r2_SE" if r["year"] <= 2020 else "fats_out_part_SE"),
        }
        if ((r["series_id"] == "eurostat_italy_legal:china" and not 2007 <= r["year"] <= 2023)
                or (r["series_id"] == "eurostat_italy:china" and r["year"] < 2021)):
            raise ValueError("Italian legal-unit and enterprise populations must not be spliced")
        if r["series_id"].startswith("eurostat") and r["source_id"] != expected_source[r["series_id"]]:
            raise ValueError("European method/source boundary mismatch")
        if r["series_id"] == "ssb_norway:china" and r["source_id"] != "ssb_09827":
            raise ValueError("Norwegian country table source mismatch")
        if r["series_id"] == "bundesbank_germany:china" and r["source_id"] != "bundesbank_outward_fats":
            raise ValueError("German country table source mismatch")
        if r["series_id"] == "tillvaxtanalys_sweden:china" and r["source_id"] != "sweden_country_table":
            raise ValueError("Swedish country table source mismatch")
        if r["series_id"] == "statfin_finland:china" and r["source_id"] != "finland_13k8":
            raise ValueError("Finnish country table source mismatch")
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
        if definition["unit"].lower() != config["unit"].lower():
            raise ValueError("Business chart units do not match")
        rows = sorted((r for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
        points = []
        for r in rows:
            if r["value"] is None:
                continue
            points.append(dict(r, plotted_value=r["value"], denominator=None,
                               reported_unit=definition["unit"], plotted_unit=config["unit"]))
        result.append({"id": sid, "label": definition["label"], "color": COLORS[sid],
                       "cadence": definition["cadence"], "period_basis": definition["period_basis"],
                       "scheduled_years": [r["year"] for r in rows], "points": points})
    return current_groups(result)


def svg_business_chart(data, chart_id, theme="themarginoferror"):
    config = dict(CHARTS[chart_id])
    groups = chart_groups(data, chart_id)
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


def build_business(root, data, gallery, publication=False):
    from .render import esc, export_figure, figure_links, remove_figure

    validate_business_data(data)
    for chart_id in RETIRED_CHARTS:
        for theme in CHART_THEMES:
            remove_figure(root, Path("business_presence") / theme / chart_id)
    cards, plotted, count = {}, [], 0
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
            figure = (svg_business_chart(data, chart_id) if publication else
                      f'<img src="{esc(paths["themarginoferror"]["png"])}" width="1000" height="600" loading="lazy" '
                      f'alt="{esc(config["title"])} - {esc(config["subtitle"])}">')
            downloads = figure_links(paths)
            if publication:
                downloads = downloads.replace("<a ", "<a data-original-chart ")
            body = (f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(config["title"])}">'
                    + figure + '</div>' +
                    f'<p class="chart-note">{esc(config["note"])}</p>' + downloads)
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
        origin = ORIGINS[config["series"][0]]
        cards[chart_id] = (f'<section class="series-panel" id="{chart_id}" data-business-origin="{origin}">'
                           f'<h2>{esc(config["title"])}</h2>{body}</section>')
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
    columns = [("bea_affiliates:china", "U.S. affiliates"), ("eurostat_affiliates:china", "EU27 current members"),
               ("eurostat_historical_eu:china", "EU27 2007 members"), ("eurostat_uk:china", "UK enterprises"),
               ("ssb_norway:china", "Norwegian enterprises (all industries)"),
               ("eurostat_germany:china", "Germany (Eurostat)"),
               ("bundesbank_germany:china", "Germany (Bundesbank; assets above EUR 3m)"),
               ("tillvaxtanalys_sweden:china", "Swedish-group subsidiaries"),
               ("statfin_finland:china", "Finnish-reported affiliates"),
               ("eurostat_france:china", "France (Eurostat; China except Hong Kong)")]
    observations = {(r["series_id"], r["year"]): r for r in data["observations"]}
    annual = [r for r in data["observations"] if data["series"][r["series_id"]]["cadence"] == "annual"]
    first = min((r["year"] for r in annual), default=2000)
    last = max((r["year"] for r in annual), default=first)
    yearly = []
    for year in range(first, last + 1):
        cells = []
        for sid, _ in columns:
            r = observations.get((sid, year))
            value = ("Confidential" if r and r["status"] == "suppressed" else "Not reported") if r is None or r["value"] is None else (
                f'{r["value"]:,}' + (f' ({r["status"]})' if r["status"] != "observed" else ""))
            cells.append(f'<td data-business-origin="{ORIGINS[sid]}">{esc(value)}</td>')
        yearly.append(f'<tr data-business-year="{year}"><th scope="row">{year}</th>{"".join(cells)}</tr>')
    annual_table = ('<section class="series-panel" id="annual-values"><h2>Every reported year in China</h2>'
                    '<p>Not just endpoints: every available annual count is shown below. Columns have different '
                    'ownership, reporting and sector coverage; they are not a matched ranking or an all-Europe total. '
                    'The historical EU group already includes the UK: overlapping columns must not be added.</p>'
                    '<div class="table-scroll"><table><thead><tr><th>Year / ending year</th>' +
                    "".join(f'<th data-business-origin="{ORIGINS[sid]}">{esc(label)}</th>' for sid, label in columns) +
                    '</tr></thead><tbody>' + "".join(yearly) + '</tbody></table></div></section>')
    annual_cards = "".join(card for chart_id, card in cards.items() if chart_id != BENCHMARK_CHART)
    benchmark = ('<details class="series-panel" id="business-benchmark-background">'
                 '<summary>Supplementary company-count benchmarks — not an annual series</summary>'
                 '<p>These four isolated U.S. parent-company observations are background only. They are not '
                 'substituted for the annual affiliate histories above, interpolated or presented as a current census.</p>'
                 + cards[BENCHMARK_CHART] + '</details>')
    controls = (f'<form id="business-controls" class="controls" hidden aria-label="Explore China business histories">'
                '<label>Investor origin<select id="business-origin"><option value="all">All reported origins</option>'
                '<option value="us">United States</option><option value="eu">EU reporting groups</option>'
                '<option value="uk">United Kingdom</option><option value="norway">Norway</option>'
                '<option value="germany">Germany</option></select></label>'
                f'<label>Table start year<input id="business-start" type="number" min="{first}" max="{last}" value="{first}" step="1"></label>'
                f'<label>Table end year<input id="business-end" type="number" min="{first}" max="{last}" value="{last}" step="1"></label>'
                '<p id="business-filter-status" role="status" aria-live="polite">'
                'Charts retain their full reported history. Year filters apply to the exact table only; downloads are complete.</p></form>') if publication else ""
    navigation = ('<p><a href="index.html">Exchange dashboard</a>' +
                  (' · <a href="language-learning.html">Language learning</a>' if (root / "site/language-learning.html").is_file() else "") + '</p>')
    if publication:
        navigation = ('<p class="eyebrow"><a href="https://www.themarginoferror.com/interactive-analysis/">'
                      'Interactive analysis</a> / China business presence</p>')
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1"><title>U.S. and European businesses in China over time</title>'
                '<link rel="stylesheet" href="assets/style.css"></head><body><div class="page"><header>' + navigation +
                f'<h1>Businesses in China.</h1><p class="lead">{esc(data["context"]["question"])}</p>'
                f'<p><strong>Annual histories, {first}-{last} where reported. China is the host in every chart.</strong> '
                'The main graphs track U.S., EU, German, UK and Norwegian business presence in China over time—not U.S. '
                'businesses located in Europe. Sparse company-count benchmarks are secondary.</p>'
                '<p><strong>Parent companies, affiliate enterprises and physical branches are different counting units.</strong> '
                'Annual affiliate/enterprise counts are not an annual census of unique parent companies or physical offices.</p>'
                f'<p>{esc(data["context"]["interpretation"])}</p><p>{esc(data["context"]["geography"])}</p>'
                '<p><a href="downloads/business-presence.json" download>Complete dataset and provenance · JSON</a> · '
                '<a href="downloads/business-observations.csv" download>Every source observation · CSV</a> · '
                '<a href="downloads/business-chart-values.csv" download>Every plotted value · CSV</a></p></header><main>'
                + controls + annual_cards + annual_table + benchmark +
                '<section class="series-panel"><h2>Coverage and unresolved counts</h2>'
                f'<p>{esc(data["context"].get("release_timing", ""))}</p>'
                '<p>Missing and confidential values stay blank, not zero or invented annual estimates. '
                'Membership, sector, source, survey and reporting-threshold breaks remain disconnected. '
                'Colors identify investor origins consistently across these China-hosted charts.</p>'
                '<div class="table-scroll"><table><thead><tr><th>Indicator</th><th>Status</th><th>Definition</th></tr></thead>'
                '<tbody>' + coverage + '</tbody></table></div></section><section class="series-panel"><h2>Primary sources</h2>'
                f'<p>{esc(data["context"]["rights"])}</p><details><summary>Sources, vintages and checksums</summary><ul>'
                + sources + '</ul></details></section></main></div></body></html>')
    write_atomic(root / "site/business-presence.html", document)
    return count
