"""Dependency-light, deterministic static publication, including complete downloads."""

import csv
import html
import io
import json
import math
import textwrap
from collections import defaultdict
from pathlib import Path

from .model import START_YEAR, GEOGRAPHIES, MEASURES, change, coverage, json_text, validate
from .pipeline import load, write_atomic
from .theme import CHART_THEMES, FONT, GRID, MUTED, PARTNER_COLORS, TEXT


SOURCE_NAMES = {
    "bea": "U.S. Bureau of Economic Analysis",
    "ntto": "U.S. National Travel and Tourism Office",
    "uis": "UNESCO Institute for Statistics",
    "iie": "IIE Open Doors",
    "taiwan_tourism": "Taiwan Tourism Administration",
    "macau_tourism": "Macao Government Tourism Office / DSEC",
    "comtrade": "UN Comtrade (U.S. reporter)",
}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value, unit="", compact=False):
    if value is None:
        return "Not available"
    if compact and abs(value) >= 1_000_000_000:
        return ("$" if unit == "USD" else "") + f"{value / 1_000_000_000:,.1f}B"
    if compact and abs(value) >= 1_000_000:
        return ("$" if unit == "USD" else "") + f"{value / 1_000_000:,.1f}M"
    if compact and abs(value) >= 1000:
        return ("$" if unit == "USD" else "") + f"{value / 1000:,.0f}k"
    return ("$" if unit == "USD" else "") + (
        f"{value:,.0f}" if value == int(value) else f"{value:,}")


def baseline(rows, year=2020):
    return next((r for r in rows if r["year"] == year and r["value"] is not None), None)


def comparison(result, unit):
    if result["absolute"] is None:
        return esc(result["reason"])
    absolute = result["absolute"]
    sign = "+" if absolute > 0 else "\u2212" if absolute < 0 else ""
    percent = result["percent"]
    return (sign + number(abs(absolute), unit) +
            (f" ({'+' if percent > 0 else ''}{percent:.1f}%)" if percent is not None
             else " \u00b7 " + result["reason"]))


def svg_chart(rows, indexed=False, theme="themarginoferror"):
    background = CHART_THEMES[theme]["background"]
    annual = sorted((r for r in rows if r["frequency"] == "annual"), key=lambda r: r["year"])
    present = [r for r in annual if r["value"] is not None]
    if not present:
        return '<p class="gap">No verified annual observations for this series.</p>'
    ref = baseline(annual)
    if indexed and (ref is None or not ref["value"]):
        return '<p class="gap">A comparable, nonzero 2020 baseline is not available.</p>'
    if indexed and any(change(r, ref)["absolute"] is None for r in present):
        return '<p class="gap">Definitions differ from the 2020 baseline; an index would not be comparable.</p>'
    unit = present[0]["unit"]
    end = max(r["year"] for r in annual)
    end = max(2021, end)
    values = {r["year"]: (r["value"] / ref["value"] * 100 if indexed else r["value"])
              for r in present}
    maximum = max(values.values()) * 1.13 or 1
    magnitude = 10 ** math.floor(math.log10(maximum))
    maximum = math.ceil(maximum / magnitude) * magnitude
    x = lambda year: 88 + (year - START_YEAR) / (end - START_YEAR) * 754
    y = lambda value: 350 - value / maximum * 235
    sample = present[0]
    partner = sample["destination"] if sample["origin"] == "USA" else sample["origin"]
    color = PARTNER_COLORS[partner]
    heading = MEASURES[sample["measure"]]
    direction = f"{GEOGRAPHIES[sample['origin']]} to {GEOGRAPHIES[sample['destination']]}"
    title = f"{heading}: {direction}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 470" role="img" aria-label="{esc(title)}">',
             f"<title>{esc(title)}</title>",
             f"<desc>Annual history from {START_YEAR} where available. Missing years and definition changes break the line. Exact values are in the complete data download.</desc>",
             f'<rect class="chart-background" width="900" height="470" fill="{background}"/>',
             f'<g font-family="{esc(FONT)}" font-size="15" fill="{MUTED}">',
             f'<text x="88" y="35" font-size="23" font-weight="bold" fill="{TEXT}">{esc(heading)}</text>',
             f'<text x="88" y="62" font-size="17">{esc(direction)}</text>']
    for fraction in [0, 0.5, 1]:
        value = maximum * fraction
        label = f"{value:.0f}" if indexed else number(value, unit, compact=True)
        parts.append(f'<path d="M88 {y(value):.2f}H842" stroke="{GRID}" stroke-opacity="0.6" stroke-width="0.5"/>'
                     f'<text x="76" y="{y(value) + 5:.2f}" text-anchor="end">{esc(label)}</text>')
    for year in sorted(set(range(START_YEAR, end - 1, 5)) | {end}):
        parts.append(f'<text x="{x(year):.2f}" y="378" text-anchor="middle">{year}</text>')
    parts.append(f'<path d="M88 115V350H842" stroke="{GRID}" stroke-width="0.8" fill="none"/>')
    parts.append(f'<path d="M{x(2020):.2f} 115V350" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="4 5"/>')
    parts.append(f'<text x="{x(2020) - 8:.2f}" y="99" text-anchor="end">2020 baseline</text>')
    if indexed:
        parts.append(f'<text x="88" y="99" fill="{TEXT}">2020 = 100</text>')
    else:
        parts.append(f'<text x="88" y="99" fill="{TEXT}">{esc("Nominal USD" if unit == "USD" else unit.capitalize())}</text>')
    path, previous, previous_definition = [], None, None
    for year, value in sorted(values.items()):
        definition = next(r["comparability"] for r in present if r["year"] == year)
        connected = previous == year - 1 and previous_definition == definition
        path.append(f"{'L' if connected else 'M'}{x(year):.2f},{y(value):.2f}")
        previous = year
        previous_definition = definition
    parts.append(f'<path class="data-line" d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2.8" stroke-linejoin="round"/>')
    for row in present:
        year = row["year"]
        label = row["period"] + ": " + number(row["value"], unit)
        parts.append(f'<circle cx="{x(year):.2f}" cy="{y(values[year]):.2f}" r="3.5" fill="{color}">'
                     f'<title>{esc(label)}</title></circle>')
    source = SOURCE_NAMES.get(sample["source_id"], sample["source_id"])
    note = f"Source: {source}. Annual observations; missing years and definition changes are not connected."
    if sample["period_basis"] == "academic":
        note += " Academic years use ending years."
    if sample["period_basis"] == "reporting":
        note += " Reporting years, not physical-presence counts."
    for line, text in enumerate(textwrap.wrap(note, width=100)):
        parts.append(f'<text class="figure-source" x="88" y="{414 + line * 18}" font-size="12" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def annual_table(rows):
    annual = sorted((r for r in rows if r["frequency"] == "annual"), key=lambda r: r["year"])
    body = "".join(
        f'<tr><th scope="row">{esc(r["period"])}</th><td>{esc(number(r["value"], r["unit"]))}</td>'
        f'<td>{esc(r["status"])}</td></tr>' for r in annual)
    return ('<div class="table-scroll"><table><caption>Exact annual observations</caption>'
            '<thead><tr><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Status</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def initial_panel(rows):
    annual = [r for r in rows if r["frequency"] == "annual"]
    current = max((r for r in annual if r["value"] is not None), key=lambda r: r["year"])
    ref = baseline(annual)
    prior = baseline(annual, current["year"] - 1)
    return (
        '<div class="headline-grid">'
        f'<div><p class="label">Latest complete annual observation</p><p class="metric" id="latest-value">{number(current["value"], current["unit"])}</p>'
        f'<p id="latest-period">{esc(current["period"])} \u00b7 {esc(MEASURES[current["measure"]])}</p></div>'
        f'<div><p class="label" id="baseline-label">Change since {esc(ref["period"] if ref else "2020")}</p>'
        f'<p class="delta" id="baseline-change">{comparison(change(current, ref), current["unit"])}</p>'
        f'<p id="yoy-change">Prior year: {comparison(change(current, prior), current["unit"])}</p></div></div>'
    )


def build(root):
    root = Path(root)
    rows = validate(load(root / "data/site/observations.json", []))
    if not rows:
        raise ValueError("No canonical observations; run update.py first")
    sources = load(root / "data/site/sources.json", {})
    matrix = coverage(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row["series_id"]].append(row)
    charts, all_tables = {}, []
    site = root / "site"
    figures = root / "outputs/figures"
    for series_id, series_rows in sorted(groups.items()):
        sample = series_rows[0]
        slug = series_id.replace(":", "-")
        levels = svg_chart(series_rows)
        indexed = svg_chart(series_rows, True)
        charts[series_id] = {"levels": levels, "index": indexed}
        if levels.startswith("<svg"):
            write_atomic(figures / (slug + ".svg"), levels + "\n")
            write_atomic(site / "figures" / (slug + ".svg"), levels + "\n")
            for theme in CHART_THEMES:
                themed = svg_chart(series_rows, theme=theme)
                write_atomic(figures / theme / (slug + ".svg"), themed + "\n")
                write_atomic(site / "figures" / theme / (slug + ".svg"), themed + "\n")
        heading = (GEOGRAPHIES[sample["origin"]] + " \u2192 " + GEOGRAPHIES[sample["destination"]] +
                   " \u00b7 " + MEASURES[sample["measure"]])
        all_tables.append(f'<details><summary>{esc(heading)} <span class="muted">({esc(SOURCE_NAMES[sample["source_id"]])})</span></summary>'
                          f'<p>{esc(sample["definition"])}</p>{annual_table(series_rows)}</details>')
    payload = {"observations": rows, "sources": sources, "coverage": matrix,
               "geographies": GEOGRAPHIES, "measures": MEASURES,
               "source_names": SOURCE_NAMES, "charts": charts, "chart_themes": CHART_THEMES}
    download = {k: v for k, v in payload.items() if k not in {"charts", "chart_themes"}}
    write_atomic(site / "downloads/exchange.json", json_text(download))
    write_atomic(site / "downloads/observations.json", json_text(rows))
    write_atomic(site / "downloads/coverage.json", json_text(matrix))
    write_atomic(site / "downloads/sources.json", json_text(sources))
    csv_file = io.StringIO(newline="")
    writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_atomic(site / "downloads/observations.csv", csv_file.getvalue())
    package = Path(__file__).parent
    for name in ["style.css", "app.js"]:
        write_atomic(site / "assets" / name, (package / "static" / name).read_text())
    candidates = {sid: series for sid, series in groups.items()
                  if any(r["frequency"] == "annual" and r["value"] is not None for r in series)}
    if not candidates:
        raise ValueError("No verified annual observations to render")
    selected_id = "iie:CHN:USA:international_students"
    if selected_id not in candidates:
        selected_id = min(candidates, key=lambda sid: (
            candidates[sid][0]["origin"] != "CHN" or candidates[sid][0]["destination"] != "USA", sid))
    selected = candidates[selected_id]
    current = max((r for r in selected if r["frequency"] == "annual" and r["value"] is not None),
                  key=lambda r: r["year"])
    selected_geo = current["destination"] if current["origin"] == "USA" else current["origin"]
    selected_direction = "from_us" if current["origin"] == "USA" else "to_us"
    selected_slug = selected_id.replace(":", "-")
    selected_source = sources.get(current["source_id"], {})
    cov_rows = "".join(
        f'<tr><td>{esc(GEOGRAPHIES[c["origin"]])} \u2192 {esc(GEOGRAPHIES[c["destination"]])}</td>'
        f'<td>{esc(MEASURES[c["measure"]])}</td><td>{esc(", ".join(map(str, c["available_years"]))) if c["available_years"] else esc(c["reason"])}</td>'
        f'<td>{"Available" if c["baseline_2020"] else "Not available"}</td></tr>' for c in matrix)
    source_rows = "".join(
        f'<tr><th scope="row">{esc(SOURCE_NAMES[s])}</th><td>{esc(m["status"])}</td>'
        f'<td>{esc(m.get("vintage", "No verified release"))}</td>'
        f'<td>{esc(m.get("last_successful_retrieval", "Never"))}</td>'
        f'<td>{esc(m["last_recorded_check"])}</td><td>{esc(m.get("notes", m.get("error", "")))}</td></tr>'
        for s, m in sorted(sources.items()))
    options = "".join(f'<option value="{k}"{" selected" if k == selected_geo else ""}>{esc(v)}</option>'
                      for k, v in GEOGRAPHIES.items() if k != "USA")
    direction_options = "".join(f'<option value="{k}"{" selected" if k == selected_direction else ""}>{v}</option>'
                                for k, v in [("to_us", "To U.S."), ("from_us", "From U.S.")])
    measure_options = "".join(f'<option value="{k}"{" selected" if k == current["measure"] else ""}>{esc(v)}</option>'
                              for k, v in MEASURES.items())
    theme_options = "".join(f'<option value="{k}">{esc(v["label"])}</option>' for k, v in CHART_THEMES.items())
    embedded = json_text(payload).replace("<", "\\u003c")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Evidence-backed students, visitor trips, goods and services exchanged between the U.S. and mainland China, Hong Kong, Macau and Taiwan.">
<title>U.S. bilateral exchange | Students, visitors and trade</title><link rel="stylesheet" href="assets/style.css">
<script src="assets/app.js" defer></script></head>
<body><a class="skip" href="#main">Skip to content</a><div class="page">
<header><p class="eyebrow">A bilateral exchange monitor</p><h1>Students, visitors<br>and trade.</h1>
<p class="lead">The United States and mainland China, Hong Kong, Macau, and Taiwan.
Four separate geographies. Both directions. History since {START_YEAR}; change since 2020.</p>
<p class="scope">History from {START_YEAR} where available \u00b7 Latest verified period varies by series \u00b7 Nominal USD for trade</p></header>
<main id="main">
<form class="controls" aria-label="Explore bilateral series" onsubmit="return false">
<label for="geography">Geography<select id="geography">{options}</select></label>
<label for="direction">Direction<select id="direction">{direction_options}</select></label>
<label for="measure">Measure<select id="measure">{measure_options}</select></label></form>
<noscript><p class="notice">Interactive controls need JavaScript. The initial chart and all annual tables, coverage, sources and complete downloads below work without it.</p></noscript>
<section class="series-panel" aria-labelledby="series-title">
<p class="eyebrow" id="series-category">{esc(MEASURES[current["measure"]])}</p>
<h2 id="series-title">{esc(GEOGRAPHIES[current["origin"]])} \u2192 {esc(GEOGRAPHIES[current["destination"]])}</h2>
<div id="annual-headlines" aria-live="polite">{initial_panel(selected)}</div>
<p class="definition" id="definition">{esc(current["definition"])}</p>
<div class="chart-heading"><h3>Annual history</h3><div class="chart-control"><label for="chart-mode">Display</label>
<select id="chart-mode"><option value="levels">Reported values</option><option value="index">2020 = 100</option></select></div>
<div class="chart-control"><label for="chart-theme">Background</label><select id="chart-theme">{theme_options}</select></div></div>
<div id="chart">{charts[selected_id]["levels"]}</div>
<p class="chart-note">Gaps stay gaps. Academic-year labels use their ending year on the axis; the 2020 baseline is 2019/20, not calendar 2020. Reporting-year UIS data are not physical-presence counts.</p>
<details id="selected-table"><summary>Exact values for this series</summary><div id="series-table">{annual_table(selected)}</div></details>
<div id="partial-panel" class="partial" hidden></div>
<div class="source-note" id="series-source">Source: <a href="{esc(current["source_url"])}">{esc(SOURCE_NAMES[current["source_id"]])}</a> \u00b7 {esc(current["source_vintage"])}. {esc(selected_source.get("notes", ""))}</div>
<p id="series-notes" class="chart-note">{esc(current["notes"])}</p>
</section>
<section class="reading-note"><h2>What the numbers mean</h2><div class="notes-grid">
<p><strong>Students are not departures.</strong> Enrolled-only counts, enrollment including OPT, degree mobility, and credit study abroad are separate populations. None is a border-crossing count.</p>
<p><strong>Trips are not unique tourists.</strong> NTTO covers overnight visits and all purposes. Destination arrival series can include same-day visits. Leisure-only data are shown only when explicitly reported.</p>
<p><strong>Trade follows exports.</strong> U.S. imports are partner \u2192 U.S. BEA uses balance-of-payments accounting. Macau goods use Comtrade customs data: exports FOB, imports CIF. Services exclude affiliate sales.</p>
<p><strong>2020 is an unusual baseline.</strong> Pandemic restrictions can make percentage rebounds very large. Full annual history and prior-year changes provide context; no causal effect is claimed.</p></div></section>
<section id="downloads"><h2>The complete data, not just the chart.</h2>
<p>All observations, including monthly history and matched YTD sums, definitions, missingness, source vintages, request URLs, retrieval timestamps and raw-response checksums.</p>
<div class="downloads"><a href="downloads/observations.csv" download>All observations \u00b7 CSV</a><a href="downloads/exchange.json" download>Complete dataset + coverage \u00b7 JSON</a></div>
<div id="figure-link"><p><a href="figures/{esc(selected_slug)}.svg" download>Download this chart \u00b7 SVG (reported values)</a></p>
<p class="figure-variants">Publication backgrounds (same reported values):
{" · ".join(f'<a href="figures/{theme}/{esc(selected_slug)}.svg" download>{esc(spec["label"])} SVG</a>' for theme, spec in CHART_THEMES.items())}</p></div></section>
<section id="coverage"><h2>Coverage, including the gaps.</h2>
<p>Missing does not mean zero. No interpolation, regional allocation, or passenger/visa proxy fills an unavailable bilateral series.</p>
<details><summary>View all four geographies, both directions and every measure</summary>
<div class="table-scroll"><table><caption>Verified annual coverage by geography and measure</caption>
<thead><tr><th>Direction</th><th>Measure</th><th>Available ending years / specific gap</th><th>2020 baseline</th></tr></thead>
<tbody>{cov_rows}</tbody></table></div></details></section>
<section id="sources"><h2>Sources and recorded checks.</h2>
<p>Dates below belong to the published snapshot. An unchanged daily check does not rewrite them. The daily workflow's check artifact records every actual attempt; a successful check is not a new data release.</p>
<div class="table-scroll"><table class="sources-table"><caption>Source release, health and publication provenance</caption>
<thead><tr><th>Source</th><th>Health</th><th>Source vintage</th><th>Published successful retrieval</th><th>Last recorded publication check</th><th>Notes</th></tr></thead>
<tbody>{source_rows}</tbody></table></div></section>
<section id="all-values"><h2>All annual tables.</h2><p>Accessible without JavaScript. Monthly values and derived YTD rows are included in the complete downloads.</p>
{"".join(all_tables)}</section>
</main><footer>Public aggregate statistics. Separate definitions, honest gaps, no composite exchange score. Hosting integration is not configured.</footer>
</div><script type="application/json" id="exchange-data">{embedded}</script></body></html>
"""
    write_atomic(site / "index.html", document)
    return {"observations": len(rows), "series": len(groups), "coverage_cells": len(matrix)}
