"""Dependency-light, deterministic static publication, including complete downloads."""

import csv
import html
import io
import json
import math
import textwrap
from collections import defaultdict
from pathlib import Path

import resvg_py

from .model import START_YEAR, GEOGRAPHIES, MEASURES, change, coverage, gap_reason, json_text, validate
from .pipeline import load, write_atomic
from .sources import SOURCE_POLICIES
from .weibo_analysis import WEIBO_CHARTS, svg_weibo, validate_summary
from .theme import (CHART_HEIGHT, CHART_THEMES, CHART_WIDTH, COMPARISON_GEOGRAPHIES, FIGURE_CATEGORIES, FONT,
                    FONT_FILES, GRID, MUTED, PARTNER_COLORS, PNG_HEIGHT, PNG_WIDTH,
                    TEXT, figure_category)


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


def source_notices(source_ids):
    notices = [f'<li><strong>{esc(SOURCE_NAMES[sid])}:</strong> {esc(SOURCE_POLICIES[sid]["notice"])} '
               f'<a href="{esc(SOURCE_POLICIES[sid]["terms_url"])}">Source terms</a></li>'
               for sid in sorted(set(source_ids) & SOURCE_POLICIES.keys())]
    return ('<details class="source-restrictions"><summary>Source access and reuse restrictions</summary><ul>' +
            "".join(notices) + '</ul></details>') if notices else ""


def number(value, unit="", compact=False):
    if value is None:
        return "Not available"
    if compact and abs(value) >= 1_000_000_000_000:
        return ("$" if unit == "USD" else "") + f"{value / 1_000_000_000_000:,.1f}T"
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
    x = lambda year: 115 + (year - START_YEAR) / (end - START_YEAR) * 835
    y = lambda value: 435 - value / maximum * 285
    sample = present[0]
    partner = sample["destination"] if sample["origin"] == "USA" else sample["origin"]
    color = PARTNER_COLORS[partner]
    heading = MEASURES[sample["measure"]]
    direction = f"{GEOGRAPHIES[sample['origin']]} to {GEOGRAPHIES[sample['destination']]}"
    title = f"{heading}: {direction}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="{esc(title)}">',
             f"<title>{esc(title)}</title>",
             f"<desc>Annual history from {START_YEAR} where available. Missing years and definition changes break the line. Exact values are in the complete data download.</desc>",
             f'<rect class="chart-background" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{background}"/>',
             f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
             f'<text x="115" y="45" font-size="28" font-weight="bold" fill="{TEXT}">{esc(heading)}</text>',
             f'<text x="115" y="80" font-size="22">{esc(direction)}</text>']
    for fraction in [0, 0.5, 1]:
        value = maximum * fraction
        label = f"{value:.0f}" if indexed else number(value, unit, compact=True)
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity="0.6" stroke-width="0.5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(label)}</text>')
    for year in sorted(set(range(START_YEAR, end - 1, 5)) | {end}):
        parts.append(f'<text x="{x(year):.2f}" y="472" text-anchor="middle">{year}</text>')
    parts.append(f'<path d="M115 150V435H950" stroke="{GRID}" stroke-width="0.8" fill="none"/>')
    parts.append(f'<path d="M{x(2020):.2f} 150V435" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="4 5"/>')
    parts.append(f'<text x="{x(2020) - 8:.2f}" y="125" text-anchor="end">2020 baseline</text>')
    if indexed:
        parts.append(f'<text x="115" y="125" fill="{TEXT}">2020 = 100</text>')
    else:
        parts.append(f'<text x="115" y="125" fill="{TEXT}">{esc("Nominal USD" if unit == "USD" else unit.capitalize())}</text>')
    path, previous, previous_definition = [], None, None
    for year, value in sorted(values.items()):
        definition = next(r["comparability"] for r in present if r["year"] == year)
        connected = previous == year - 1 and previous_definition == definition
        path.append(f"{'L' if connected else 'M'}{x(year):.2f},{y(value):.2f}")
        previous = year
        previous_definition = definition
    parts.append(f'<path class="data-line" d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="3.2" stroke-linejoin="round"/>')
    for row in present:
        year = row["year"]
        label = row["period"] + ": " + number(row["value"], unit)
        parts.append(f'<circle cx="{x(year):.2f}" cy="{y(values[year]):.2f}" r="4" fill="{color}">'
                     f'<title>{esc(label)}</title></circle>')
    source = SOURCE_NAMES.get(sample["source_id"], sample["source_id"])
    breaks = [current["period"] for previous, current in zip(annual, annual[1:])
              if current["comparability"] != previous["comparability"]]
    note = f"Source: {source}. Annual observations; missing years and definition changes are not connected."
    if breaks:
        note = (f"Source: {source}. Population-definition breaks: " + ", ".join(breaks) +
                ". Missing years and definition changes are not connected.")
    if sample["period_basis"] == "academic":
        note += " Academic years use ending years."
    if sample["period_basis"] == "reporting":
        note += " Reporting years, not physical-presence counts."
    if sample["source_id"] in SOURCE_POLICIES:
        note += " " + SOURCE_POLICIES[sample["source_id"]]["figure_notice"]
    for line, text in enumerate(textwrap.wrap(note, width=90)):
        parts.append(f'<text class="figure-source" x="115" y="{520 + line * 23}" font-size="16" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def regional_series(rows, measure, direction):
    if direction not in {"to_us", "from_us"}:
        raise ValueError("Unknown comparison direction")
    groups = {}
    for geo in COMPARISON_GEOGRAPHIES:
        origin, destination = (geo, "USA") if direction == "to_us" else ("USA", geo)
        annual = sorted((r for r in rows if r["measure"] == measure and r["frequency"] == "annual"
                         and r["origin"] == origin and r["destination"] == destination),
                        key=lambda r: r["year"])
        if len({r["series_id"] for r in annual}) > 1:
            raise ValueError("Comparison requires one source series per geography and measure")
        groups[geo] = annual
    return groups


def svg_comparison(rows, measure, direction, theme="themarginoferror", logarithmic=False):
    groups = regional_series(rows, measure, direction)
    present = [r for annual in groups.values() for r in annual if r["value"] is not None]
    if not present:
        return '<p class="gap">No verified annual observations for this measure and direction.</p>'
    if len({(r["unit"], r["period_basis"]) for r in present}) != 1:
        raise ValueError("Comparison units and period bases must match")
    plotted = [r for r in present if not logarithmic or r["value"] > 0]
    if not plotted:
        return '<p class="gap">No positive observations are available for a logarithmic view.</p>'
    end = max(2021, max(r["year"] for annual in groups.values() for r in annual))
    x = lambda year: 115 + (year - START_YEAR) / (end - START_YEAR) * 835
    if logarithmic:
        low = math.floor(math.log10(min(r["value"] for r in plotted)))
        high = max(low + 1, math.ceil(math.log10(max(r["value"] for r in plotted))))
        ticks = [10 ** power for power in range(low, high + 1)]
        y = lambda value: 420 - (math.log10(value) - low) / (high - low) * 240
    else:
        maximum = max(r["value"] for r in plotted) * 1.13 or 1
        magnitude = 10 ** math.floor(math.log10(maximum))
        maximum = math.ceil(maximum / magnitude) * magnitude
        ticks = [0, maximum / 2, maximum]
        y = lambda value: 420 - value / maximum * 240
    direction_label = "To the United States" if direction == "to_us" else "From the United States"
    title = MEASURES[measure] + ": " + direction_label
    unit = "Nominal USD" if present[0]["unit"] == "USD" else present[0]["unit"].capitalize()
    if logarithmic:
        unit += " (log scale)"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="{esc(title)}">',
        f'<title>{esc(title)}</title><desc>Three separate geographies, not a regional total. Missing observations and definition changes are not connected.</desc>',
        f'<rect class="chart-background" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{CHART_THEMES[theme]["background"]}"/>',
        f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
        f'<text x="115" y="40" font-size="28" font-weight="bold" fill="{TEXT}">{esc(MEASURES[measure])}</text>',
        f'<text x="115" y="75" font-size="22">{esc(direction_label)}</text>',
    ]
    missing = []
    for i, geo in enumerate(COMPARISON_GEOGRAPHIES):
        color = PARTNER_COLORS[geo]
        available = any(r["value"] is not None for r in groups[geo])
        if not available:
            missing.append(GEOGRAPHIES[geo])
        pos = 115 + i * 270
        dash = ' stroke-dasharray="7 4"' if any(r["source_id"] == "comtrade" for r in groups[geo]) else ""
        parts.append(f'<path class="legend-swatch" data-geography="{geo}" d="M{pos} 108h28" stroke="{color}" stroke-width="3.2"{dash}/>'
                     f'<text x="{pos + 36}" y="114" fill="{TEXT}">{esc(GEOGRAPHIES[geo])}{"*" if not available else ""}</text>')
    parts.append(f'<text x="115" y="153">{esc(unit)}</text>')
    for value in ticks:
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity="0.6" stroke-width="0.5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(number(value, present[0]["unit"], compact=True))}</text>')
    for year in sorted(set(range(START_YEAR, end - 1, 5)) | {end}):
        parts.append(f'<text x="{x(year):.2f}" y="455" font-size="18" text-anchor="middle">{year}</text>')
    parts.append(f'<path d="M115 180V420H950" stroke="{GRID}" stroke-width="0.8" fill="none"/>'
                 f'<path d="M{x(2020):.2f} 180V420" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="4 5"/>'
                 f'<text x="{x(2020) - 8:.2f}" y="153" text-anchor="end">2020 baseline</text>')
    for geo, annual in groups.items():
        data = [r for r in annual if r["value"] is not None and (not logarithmic or r["value"] > 0)]
        if not data:
            continue
        path, previous = [], None
        for row in data:
            connected = (previous is not None and row["year"] == previous["year"] + 1
                         and row["comparability"] == previous["comparability"])
            path.append(f'{"L" if connected else "M"}{x(row["year"]):.2f},{y(row["value"]):.2f}')
            previous = row
        dash = ' stroke-dasharray="7 4"' if data[0]["source_id"] == "comtrade" else ""
        parts.append(f'<path class="data-line" data-geography="{geo}" data-series-id="{esc(data[0]["series_id"])}" '
                     f'd="{" ".join(path)}" fill="none" stroke="{PARTNER_COLORS[geo]}" stroke-width="3.2" stroke-linejoin="round"{dash}/>')
        for row in data:
            label = GEOGRAPHIES[geo] + " · " + row["period"] + ": " + number(row["value"], row["unit"])
            parts.append(f'<circle data-geography="{geo}" data-period="{esc(row["period"])}" cx="{x(row["year"]):.2f}" '
                         f'cy="{y(row["value"]):.2f}" r="3" fill="{PARTNER_COLORS[geo]}"><title>{esc(label)}</title></circle>')
    note = "Sources: " + "; ".join(SOURCE_NAMES.get(s, s) for s in sorted({r["source_id"] for r in present})) + ". "
    if measure == "goods" and any(r["source_id"] == "comtrade" for r in present):
        note += "Macau dashed: customs exports FOB/imports CIF; others: BEA balance-of-payments. Accounting differs. "
    if measure == "visitors" and direction == "from_us":
        note += "Macau: travel-document issuing place (residence before April 2015). Trips, not people. "
    if measure == "international_students":
        note += "IIE population expands in 2020/21–2022/23. "
    if present[0]["period_basis"] == "academic":
        note += "Academic years use ending years. "
    if present[0]["period_basis"] == "reporting":
        note += "Reporting years; not physical-presence counts. "
    if missing:
        note += "*No verified series: " + ", ".join(missing) + ". "
    note += "Missing years and definition changes stay unconnected."
    if logarithmic:
        note += " Log scale: zeros are omitted, never replaced."
    for sid in sorted({r["source_id"] for r in present} & SOURCE_POLICIES.keys()):
        note += " " + SOURCE_POLICIES[sid]["figure_notice"]
    for line, text in enumerate(textwrap.wrap(note, width=108)):
        parts.append(f'<text class="figure-source" x="115" y="{500 + line * 20}" font-size="14" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def png_chart(svg):
    fonts = Path(__file__).parent / "static/fonts"
    # This renderer release sizes the PNG from intrinsic SVG dimensions, not width/height options.
    svg = svg.replace("<svg ", f'<svg width="{PNG_WIDTH}" height="{PNG_HEIGHT}" ', 1)
    png = resvg_py.svg_to_bytes(
        svg_string=svg, skip_system_fonts=True,
        font_files=[str(fonts / name) for name in FONT_FILES],
        font_family="DejaVu Serif", serif_family="DejaVu Serif")
    if (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) != (PNG_WIDTH, PNG_HEIGHT):
        raise ValueError("PNG renderer did not preserve the required export dimensions")
    return png


def figure_links(paths):
    return ('<p>Download reported values as a high-resolution PNG or editable SVG:</p><ul>' +
            "".join(f'<li>{esc(CHART_THEMES[theme]["label"])}: '
                    f'<a href="{esc(files["png"])}" download>PNG (3000 \u00d7 1800)</a> \u00b7 '
                    f'<a href="{esc(files["svg"])}" download>SVG</a></li>'
                    for theme, files in paths.items()) + '</ul>')


def export_figure(root, relative, svg):
    png = png_chart(svg)
    files = {}
    for suffix, content in (("svg", svg + "\n"), ("png", png)):
        path = Path(str(relative) + "." + suffix)
        write_atomic(root / "outputs/figures" / path, content)
        write_atomic(root / "site/figures" / path, content)
        files[suffix] = "figures/" + path.as_posix()
    return files


def remove_figure(root, relative):
    for suffix in ("png", "svg"):
        for directory in (root / "outputs/figures", root / "site/figures"):
            path = directory / (str(relative) + "." + suffix)
            if path.is_file():
                path.unlink()


def build_weibo(root, summary, gallery):
    validate_summary(summary)
    cards = []
    for metric, title in WEIBO_CHARTS.items():
        paths = {}
        for theme in CHART_THEMES:
            svg = svg_weibo(summary, metric, theme)
            if svg.startswith("<svg"):
                paths[theme] = export_figure(root, Path("weibo") / theme / metric, svg)
        if paths:
            image = paths["themarginoferror"]["png"]
            body = (f'<div class="comparison-chart"><img src="{esc(image)}" alt="{esc(title)}" '
                    'width="1000" height="600" loading="lazy"></div>' + figure_links(paths))
            relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                        for theme, files in paths.items()}
            gallery["weibo"].append(f'<article><h3>{esc(title)}</h3>{figure_links(relative)}</article>')
        else:
            for theme in CHART_THEMES:
                remove_figure(root, Path("weibo") / theme / metric)
            body = '<p class="gap">No recovered publication dates in this frozen snapshot.</p>'
        cards.append(f'<section class="series-panel"><h2>{esc(title)}</h2>{body}</section>')
    write_atomic(root / "site/downloads/weibo-summary.json", json_text(summary))
    for name, records in (("accounts", summary["accounts"]), ("years", summary["yearly"]),
                          ("text-completeness", summary["text_completeness"])):
        stream = io.StringIO(newline="")
        columns = list(records[0]) if records else (["year", "recovered_posts"] if name == "years" else ["account_id"])
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
        write_atomic(root / f"site/downloads/weibo-{name}.csv", stream.getvalue())
    roster = summary["roster"]
    total = sum(a["recovered_posts"] for a in summary["accounts"])
    recovered = sum(a["recovered_posts"] > 0 for a in summary["accounts"])
    table = "".join(f'<tr><th scope="row">{esc(a["outlet_name"])}</th><td>{esc(a["existence"])}</td>'
                    f'<td>{a["recovered_posts"]:,}</td><td>{esc(a["latest_run_status"] or "not attempted")}</td>'
                    f'<td>{esc(a["attribution_end"] or "not established")}</td>'
                    f'<td><a href="{esc(a["profile_url"])}">Registered profile</a></td></tr>' for a in summary["accounts"])
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Weibo research coverage</title><link rel="stylesheet" href="assets/style.css"></head>'
                '<body><div class="page"><header><p><a href="index.html">Exchange dashboard</a> · '
                '<a href="comparisons.html">Three-geography comparisons</a></p><h1>Weibo research.</h1>'
                '<p class="lead">Account evidence and recovered-corpus coverage—not a census of posting activity.</p>'
                f'<p>{roster["outlets"]:,} outlets in the research roster; {roster["confirmed_accounts"]:,} confirmed accounts '
                f'across {roster["confirmed_outlets"]:,} outlet/brand groups. {total:,} posts recovered from {recovered:,} accounts.</p>'
                '<p>This is a frozen aggregate snapshot, not a live Weibo feed. Current identity evidence does not prove '
                'current activity. Zero recovery does not mean zero posting; unknown accounts are not verified absences. '
                'Historical licensing cutoffs are respected. Counts are not audience size, popularity or evidence of a causal link to trade or travel.</p>'
                '<p>The sample includes explicitly labelled Chinese editions, U.S.-based Chinese-language media, '
                'press-release services and independent regional distributors. Multiple channels of one publisher '
                'are not separate outlets; account totals are not independent editorial-newsroom totals. '
                'Institutional identity is not proof of direct U.S.-newsroom operation or a continuing license; '
                'per-account relationships and attribution exclusions are retained in the aggregate JSON.</p>'
                '<p>Only aggregate counts and public institutional account metadata are published. No post text, '
                'private corpus records or engagement rankings are included. Sources and requested collection windows '
                'are identified in the complete aggregate JSON.</p>'
                '<p><a href="downloads/weibo-summary.json" download>Complete aggregate snapshot and provenance · JSON</a> · '
                '<a href="downloads/weibo-accounts.csv" download>All account aggregates · CSV</a> · '
                '<a href="downloads/weibo-years.csv" download>All publication-year aggregates · CSV</a> · '
                '<a href="downloads/weibo-text-completeness.csv" download>All text-completeness aggregates · CSV</a></p>'
                '</header><main>' + "".join(cards) +
                '<section class="series-panel"><h2>Account coverage details</h2><div class="table-scroll"><table>'
                '<thead><tr><th>Outlet / edition</th><th>Identity evidence</th><th>Recovered posts</th>'
                '<th>Latest run</th><th>Exclusive attribution end</th><th>Source</th></tr></thead>'
                f'<tbody>{table}</tbody></table></div></section></main></div></body></html>')
    write_atomic(root / "site/weibo.html", document)


def annual_table(rows):
    annual = sorted((r for r in rows if r["frequency"] == "annual"), key=lambda r: r["year"])
    varied = len({r["comparability"] for r in annual}) > 1
    body = "".join(
        f'<tr><th scope="row">{esc(r["period"])}</th><td>{esc(number(r["value"], r["unit"]))}</td>'
        f'<td>{esc(r["status"])}</td>' +
        (f'<td>{esc(r["definition"])}</td>' if varied else "") + '</tr>' for r in annual)
    return ('<div class="table-scroll"><table><caption>Exact annual observations</caption>'
            '<thead><tr><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Status</th>' +
            ('<th scope="col">Population definition</th>' if varied else "") + '</tr></thead>' +
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
    charts, all_tables, figure_paths = {}, [], {}
    gallery = defaultdict(list)
    site = root / "site"
    figures = root / "outputs/figures"
    previous_ids = {r["series_id"] for r in load(site / "downloads/observations.json", [])}
    for sid in previous_ids - groups.keys():
        parts = sid.split(":")
        if (len(parts) != 4 or parts[0] not in SOURCE_NAMES or parts[1] not in GEOGRAPHIES
                or parts[2] not in GEOGRAPHIES or parts[3] not in MEASURES):
            continue
        for theme in CHART_THEMES:
            remove_figure(root, Path(figure_category(parts[3])) / theme / sid.replace(":", "-"))
    for series_id, series_rows in sorted(groups.items()):
        sample = series_rows[0]
        slug = series_id.replace(":", "-")
        levels = svg_chart(series_rows)
        indexed = svg_chart(series_rows, True)
        charts[series_id] = {"levels": levels, "index": indexed}
        if levels.startswith("<svg"):
            category = figure_category(sample["measure"])
            figure_paths[series_id] = {}
            for theme in CHART_THEMES:
                themed = svg_chart(series_rows, theme=theme)
                figure_paths[series_id][theme] = export_figure(root, Path(category) / theme / slug, themed)
        else:
            for theme in CHART_THEMES:
                remove_figure(root, Path(figure_category(sample["measure"])) / theme / slug)
        heading = (GEOGRAPHIES[sample["origin"]] + " \u2192 " + GEOGRAPHIES[sample["destination"]] +
                   " \u00b7 " + MEASURES[sample["measure"]])
        if series_id in figure_paths:
            relative_links = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                              for theme, files in figure_paths[series_id].items()}
            gallery[category].append(f'<article><h3>{esc(heading)}</h3><p>{esc(SOURCE_NAMES[sample["source_id"]])}</p>'
                                     + figure_links(relative_links) + '</article>')
        definition = ("Population definitions vary by year; each row includes its definition."
                      if len({r["comparability"] for r in series_rows if r["frequency"] == "annual"}) > 1
                      else sample["definition"])
        all_tables.append(f'<details><summary>{esc(heading)} <span class="muted">({esc(SOURCE_NAMES[sample["source_id"]])})</span></summary>'
                          f'<p>{esc(definition)}</p>{annual_table(series_rows)}</details>')
    comparison_cards, comparison_count = [], 0
    for measure in MEASURES:
        for direction in ("to_us", "from_us"):
            regional = regional_series(rows, measure, direction)
            label = "To the United States" if direction == "to_us" else "From the United States"
            heading = MEASURES[measure] + " · " + label
            versions = {}
            for scale in ("levels", "log"):
                svg = svg_comparison(rows, measure, direction, logarithmic=scale == "log")
                if not svg.startswith("<svg"):
                    for theme in CHART_THEMES:
                        relative = (Path(figure_category(measure)) / "comparisons" / theme /
                                    f"chn-hkg-mac-{direction}-{measure}-{scale}")
                        remove_figure(root, relative)
                    continue
                versions[scale] = {}
                for theme in CHART_THEMES:
                    themed = svg_comparison(rows, measure, direction, theme, logarithmic=scale == "log")
                    relative = (Path(figure_category(measure)) / "comparisons" / theme /
                                f"chn-hkg-mac-{direction}-{measure}-{scale}")
                    versions[scale][theme] = export_figure(root, relative, themed)
            body = ""
            if "levels" in versions:
                comparison_count += 1
                image = versions["levels"]["themarginoferror"]["png"]
                body += (f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(heading)}">'
                         f'<img src="{esc(image)}" alt="{esc(heading)}: mainland China, Hong Kong and Macau" '
                         'width="1000" height="600" loading="lazy"></div>' +
                         figure_links(versions["levels"]))
                if "log" in versions:
                    image = versions["log"]["themarginoferror"]["png"]
                    body += ('<details><summary>Logarithmic view — useful when series differ greatly in size</summary>'
                             f'<div class="comparison-chart"><img src="{esc(image)}" alt="{esc(heading)} on a log scale" '
                             'width="1000" height="600" loading="lazy"></div>' +
                             figure_links(versions["log"]) + '</details>')
                catalog = f'<article class="combined-chart"><h3>Three-geography comparison: {esc(heading)}</h3>'
                for scale, paths in versions.items():
                    relative_paths = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                                      for theme, files in paths.items()}
                    catalog += f'<h4>{"Reported values" if scale == "levels" else "Logarithmic view"}</h4>' + figure_links(relative_paths)
                gallery[figure_category(measure)].insert(0, catalog + '</article>')
            else:
                body += '<p class="gap">No verified annual series for these geographies in this direction. Missing is not zero.</p>'
            body += '<details><summary>Exact values, definitions and unavailable series</summary>'
            for geo, annual in regional.items():
                present = [r for r in annual if r["value"] is not None]
                body += f'<h3>{esc(GEOGRAPHIES[geo])}</h3>'
                if present:
                    latest = max(present, key=lambda r: r["year"])
                    body += (f'<p>Source: <a href="{esc(latest["source_url"])}">{esc(SOURCE_NAMES[latest["source_id"]])}</a>'
                             f' · {esc(latest["source_vintage"])}. Latest: {esc(latest["period"])}.</p>' + annual_table(annual))
                else:
                    body += f'<p>{esc(gap_reason(geo, geo if direction == "to_us" else "USA", measure))}</p>'
            body += '</details>'
            comparison_cards.append(f'<section class="series-panel" id="{measure}-{direction}"><h2>{esc(heading)}</h2>{body}</section>')
    comparison_document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                           '<meta name="viewport" content="width=device-width,initial-scale=1">'
                           '<title>China, Hong Kong and Macau | U.S. exchange comparisons</title>'
                           '<link rel="stylesheet" href="assets/style.css"></head><body><div class="page">'
                           '<header><p><a href="index.html">Individual series and complete data</a></p>'
                           '<h1>Three geographies.<br>One chart.</h1>'
                           '<p class="lead">Mainland China, Hong Kong and Macau, with a fixed colour for each geography. '
                           'Taiwan is excluded from these comparisons. No regional totals are constructed.</p>'
                           '<p>Annual history from 2000 where verified. Series can end in different years. '
                           'An asterisk identifies an unavailable series, not zero. Log views omit true zeros and never replace them.</p>'
                           '<p>Macau goods use customs accounting; the other goods lines use BEA balance-of-payments accounting. '
                           'The dashed Macau line is not an identical accounting measure. Population-definition breaks remain gaps.</p>'
                           '<p>All figures are available as 3000 × 1800 PNGs and SVGs, with both publication backgrounds.</p>'
                           + source_notices(r["source_id"] for r in rows
                                            if r["origin"] in COMPARISON_GEOGRAPHIES
                                            or r["destination"] in COMPARISON_GEOGRAPHIES) +
                           '<p><a href="downloads/observations.csv" download>Complete observations CSV</a> · '
                           '<a href="downloads/exchange.json" download>Complete dataset and provenance JSON</a></p></header><main>' +
                           "".join(comparison_cards) + '</main></div></body></html>')
    write_atomic(site / "comparisons.html", comparison_document)
    weibo_summary = load(root / "data/site/weibo_summary.json", None)
    if weibo_summary is not None:
        build_weibo(root, weibo_summary, gallery)
    else:
        for theme in CHART_THEMES:
            for metric in WEIBO_CHARTS:
                remove_figure(root, Path("weibo") / theme / metric)
        for relative in ["weibo.html", "downloads/weibo-summary.json", "downloads/weibo-accounts.csv",
                         "downloads/weibo-years.csv", "downloads/weibo-text-completeness.csv"]:
            path = site / relative
            if path.is_file():
                path.unlink()
    payload = {"observations": rows, "sources": sources, "coverage": matrix,
               "geographies": GEOGRAPHIES, "measures": MEASURES,
               "source_policies": SOURCE_POLICIES,
               "source_names": SOURCE_NAMES, "charts": charts, "chart_themes": CHART_THEMES,
               "figures": figure_paths}
    download = {k: v for k, v in payload.items() if k not in {"charts", "chart_themes", "figures"}}
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
    for name in FONT_FILES + ("LICENSE",):
        write_atomic(site / "assets/fonts" / name, (package / "static/fonts" / name).read_bytes())
    figure_index = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>Exchange charts by category</title>'
                    '<style>body{max-width:1000px;margin:auto;padding:24px;font:18px/1.6 Georgia,serif;'
                    'color:#1A1A1A;background:#F7F5F0}article{padding:12px 0;border-bottom:1px solid #D6D3CC}'
                    'a{color:#3D6F8C}h2{margin-top:48px}h3{font-size:21px}li{margin:8px 0}</style>'
                    '<h1>Exchange charts by category</h1>'
                    '<p>PNG images are 3000 \u00d7 1800 pixels. Both backgrounds contain the same reported values.</p>' +
                    "".join(f'<section><h2>{label}</h2>{"".join(gallery[category])}</section>'
                            for category, label in FIGURE_CATEGORIES.items()) + '</html>')
    write_atomic(figures / "index.html", figure_index)
    write_atomic(site / "figures/index.html", figure_index)
    # Retire only known generated paths from the previous flat export layout.
    for directory in (figures, site / "figures"):
        for sid in groups:
            slug = sid.replace(":", "-") + ".svg"
            for relative in [Path(slug)] + [Path(theme) / slug for theme in CHART_THEMES]:
                legacy = directory / relative
                if legacy.is_file():
                    legacy.unlink()
        for theme in CHART_THEMES:
            legacy_directory = directory / theme
            if legacy_directory.is_dir() and not any(legacy_directory.iterdir()):
                legacy_directory.rmdir()
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
<p><a href="comparisons.html">Compare mainland China, Hong Kong and Macau on the same charts</a></p>
{"<p><a href='weibo.html'>Weibo account evidence and recovered-corpus graphs</a> — separate research coverage, not an exchange-flow measure.</p>" if weibo_summary is not None else ""}
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
<div id="chart" tabindex="0" role="region" aria-label="Annual chart; scroll horizontally on narrow screens">{charts[selected_id]["levels"]}</div>
<p class="chart-note chart-scroll-hint">On a narrow screen, scroll the chart sideways to keep its labels readable.</p>
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
<div id="figure-link">{figure_links(figure_paths[selected_id])}</div>
<p><a href="figures/index.html">Browse all charts by category</a>: students, visitors, goods trade and services trade.</p></section>
<section id="coverage"><h2>Coverage, including the gaps.</h2>
<p>Missing does not mean zero. No interpolation, regional allocation, or passenger/visa proxy fills an unavailable bilateral series.</p>
<details><summary>View all four geographies, both directions and every measure</summary>
<div class="table-scroll"><table><caption>Verified annual coverage by geography and measure</caption>
<thead><tr><th>Direction</th><th>Measure</th><th>Available ending years / specific gap</th><th>2020 baseline</th></tr></thead>
<tbody>{cov_rows}</tbody></table></div></details></section>
<section id="sources"><h2>Sources and recorded checks.</h2>
<p>Dates below belong to the published snapshot. An unchanged daily check does not rewrite them. The daily workflow's check artifact records every actual attempt; a successful check is not a new data release.</p>
{source_notices(sources)}
<div class="table-scroll"><table class="sources-table"><caption>Source release, health and publication provenance</caption>
<thead><tr><th>Source</th><th>Health</th><th>Source vintage</th><th>Published successful retrieval</th><th>Last recorded publication check</th><th>Notes</th></tr></thead>
<tbody>{source_rows}</tbody></table></div></section>
<section id="all-values"><h2>All annual tables.</h2><p>Accessible without JavaScript. Monthly values and derived YTD rows are included in the complete downloads.</p>
{"".join(all_tables)}</section>
</main><footer>Public aggregate statistics. Separate definitions, honest gaps, no composite exchange score. Hosting integration is not configured.</footer>
</div><script type="application/json" id="exchange-data">{embedded}</script></body></html>
"""
    write_atomic(site / "index.html", document)
    return {"observations": len(rows), "series": len(groups), "coverage_cells": len(matrix),
            "comparisons": comparison_count}
