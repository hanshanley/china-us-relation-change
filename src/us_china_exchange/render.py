"""Dependency-light, deterministic static publication, including complete downloads."""

import csv
import html
import io
import json
import math
import textwrap
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import resvg_py

from .model import START_YEAR, GEOGRAPHIES, MEASURES, change, coverage, gap_reason, json_text, primary_observations, primary_series, validate
from .business_analysis import CHARTS as BUSINESS_CHARTS, RETIRED_CHARTS as BUSINESS_RETIRED_CHARTS, build_business, validate_business_data
from .immigration_analysis import CHARTS as IMMIGRATION_CHARTS, build_immigration, validate_immigration_data
from .language_analysis import CHARTS as LANGUAGE_CHARTS, RETIRED_CHARTS as LANGUAGE_RETIRED_CHARTS, chart_points, svg_language_chart, validate_language_data
from .pipeline import load, write_atomic
from . import student_estimates
from .opinion_analysis import CHARTS as OPINION_CHARTS, build_opinions
from .opinion_sources import validate_opinion_data
from .confucius_analysis import CHARTS as CONFUCIUS_CHARTS, build_confucius
from .confucius_sources import validate as validate_confucius
from .state_immigration_sources import validate as validate_state_immigration
from .sources import SOURCE_PAGES, SOURCE_POLICIES
from .weibo_analysis import WEIBO_CHARTS, svg_weibo, validate_summary
from .weibo_explorer import explorer_page
from .weibo_activity import DAILY_FIELDS, ROLLING_FIELDS
from .theme import (CHART_HEIGHT, CHART_THEMES, CHART_WIDTH, COMPARISON_GEOGRAPHIES, FIGURE_CATEGORIES, FONT,
                    FONT_FILES, GRID, MUTED, PARTNER_COLORS, PNG_HEIGHT, PNG_WIDTH,
                    TEXT, axis_label, figure_category, linear_axis)


SOURCE_NAMES = {
    "bea": "U.S. Bureau of Economic Analysis",
    "bea_expanded": "U.S. Bureau of Economic Analysis",
    "ntto": "U.S. National Travel and Tourism Office",
    "nbs_tourism": "China National Bureau of Statistics / Ministry of Culture and Tourism",
    "ntto_siat": "U.S. National Travel and Tourism Office / SIAT",
    "hktb": "Hong Kong Tourism Board",
    "moe": "China Ministry of Education / official report republications",
    "uis": "UNESCO Institute for Statistics",
    "iie": "IIE Open Doors",
    "taiwan_tourism": "Taiwan Tourism Administration",
    "macau_tourism": "Macao Government Tourism Office / DSEC",
    "comtrade": "UN Comtrade (U.S. reporter)",
    "ustr": "Office of the U.S. Trade Representative",
}
SPLIT_REGIONAL_MEASURES = set(MEASURES)


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


def baseline(rows, year=None):
    if year is None:
        year = 2019 if rows and rows[0]["measure"] == "air_visitors" else 2020
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
        return '<p class="gap">A comparable, nonzero baseline is not available.</p>'
    if indexed and any(change(r, ref)["absolute"] is None for r in present):
        return '<p class="gap">Definitions differ from the baseline; an index would not be comparable.</p>'
    unit = present[0]["unit"]
    first = min(r["year"] for r in present)
    end = max(r["year"] for r in annual)
    values = {r["year"]: (r["value"] / ref["value"] * 100 if indexed else r["value"])
              for r in present}
    maximum, ticks = linear_axis(max(values.values()))
    snapshot = ((len(present) == 1 and first == end) or
                (len(present) == 2 and present[0]["source_id"] == "ustr"
                 and len({r["comparability"] for r in present}) == 2))
    columns = not indexed and not snapshot and (
        present[0]["measure"] in {"goods", "services"}
        or present[0]["series_id"] == "iie:CHN:USA:international_students")
    x = lambda year: 115 + ((year - first + .5) / (end - first + 1) if snapshot or columns
                            else (year - first) / max(1, end - first)) * 835
    y = lambda value: 435 - value / maximum * 285
    sample = present[0]
    partner = sample["destination"] if sample["origin"] == "USA" else sample["origin"]
    color = PARTNER_COLORS[partner]
    heading = MEASURES[sample["measure"]]
    direction = f"{GEOGRAPHIES[sample['origin']]} to {GEOGRAPHIES[sample['destination']]}"
    title = f"{heading}: {direction}"
    description = (f"Single verified annual snapshot for {first}; no historical trend inferred."
                   if snapshot and len(present) == 1 else
                   f"Separate annual snapshots for {first} and {end}; release vintages are not connected or used for growth."
                   if snapshot else
                   "Annual reported totals shown as columns. Missing years are left blank. Exact values are in the complete data download."
                   if columns else f"Annual history from {first} where available. Missing years and definition changes break the line. Exact values are in the complete data download.")
    if columns and sample["source_id"] == "iie":
        description = ("Reported student counts shown as columns, with academic years labeled by ending year. "
                       "Population definitions vary; exact periods, values and definitions accompany the chart.")
    style_attribute = ' data-plot-style="columns"' if columns else ""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="{esc(title)}"{style_attribute}>',
             f"<title>{esc(title)}</title>",
             f"<desc>{esc(description)}</desc>",
             f'<rect class="chart-background" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{background}"/>',
             f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
             f'<text x="115" y="45" font-size="28" font-weight="bold" fill="{TEXT}">{esc(heading)}</text>',
             f'<text x="115" y="80" font-size="22">{esc(direction)}</text>']
    for value in ticks:
        label = axis_label(value, "" if indexed else unit)
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity="0.6" stroke-width="0.5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(label)}</text>')
    years = (sorted(values) if snapshot else
             sorted({first, end} | {year for year in range((first // 5 + 1) * 5, end, 5)
                                   if year - first >= 2 and end - year >= 2}))
    for year in years:
        parts.append(f'<text x="{x(year):.2f}" y="472" text-anchor="middle">{year}</text>')
    parts.append(f'<path d="M115 150V435H950" stroke="{GRID}" stroke-width="0.8" fill="none"/>')
    if ref is not None:
        reference_x = x(ref["year"])
        anchor = "start" if reference_x < 400 else "end"
        label_x = max(260, reference_x + 8) if anchor == "start" else reference_x - 8
        parts.append(f'<path d="M{reference_x:.2f} 150V435" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="4 5"/>')
        parts.append(f'<text x="{label_x:.2f}" y="125" text-anchor="{anchor}">{ref["year"]} baseline</text>')
    if indexed:
        parts.append(f'<text x="115" y="125" fill="{TEXT}">{ref["year"]} = 100</text>')
    else:
        parts.append(f'<text x="115" y="125" fill="{TEXT}">{esc("Nominal USD" if unit == "USD" else unit.capitalize())}</text>')
    if not columns:
        path, previous, previous_definition = [], None, None
        for year, value in sorted(values.items()):
            definition = next(r["comparability"] for r in present if r["year"] == year)
            connected = previous == year - 1 and previous_definition == definition
            path.append(f"{'L' if connected else 'M'}{x(year):.2f},{y(value):.2f}")
            previous = year
            previous_definition = definition
        parts.append(f'<path class="data-line" data-series-id="{esc(sample["series_id"])}" d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="3.2" stroke-linejoin="round"/>')
    for row in present:
        year = row["year"]
        label = row["period"] + ": " + number(row["value"], unit)
        if indexed:
            label = (f'{row["period"]}: index {values[year]:.2f} ({ref["year"]} = 100); '
                     f'reported {number(row["value"], unit)} {unit}')
        if snapshot:
            value_label = f"{values[year]:.0f}" if indexed else number(values[year], unit, compact=True)
            parts.append(f'<rect class="snapshot-bar" x="{x(year) - 32:.2f}" y="{y(values[year]):.2f}" '
                         f'width="64" height="{435 - y(values[year]):.2f}" fill="{color}" aria-hidden="true"/>'
                         f'<text x="{x(year):.2f}" y="{y(values[year]) - 10:.2f}" text-anchor="middle" '
                         f'font-size="20" fill="{TEXT}">{esc(value_label)}</text>')
        if columns:
            width = min(64, 835 / (end - first + 1) * .72)
            parts.append(f'<rect class="annual-column" data-series-id="{esc(row["series_id"])}" '
                         f'data-year="{year}" data-value="{values[year]}" x="{x(year) - width / 2:.2f}" '
                         f'y="{y(values[year]):.2f}" width="{width:.2f}" height="{435 - y(values[year]):.2f}" '
                         f'fill="{color}"><title>{esc(label)}</title></rect>')
        radius = 0 if columns else 4.5 if row is present[-1] else 2.8
        parts.append(f'<circle data-series-id="{esc(row["series_id"])}" data-year="{year}" data-value="{values[year]}" '
                     f'data-period="{esc(row["period"])}" data-reported-value="{row["value"]}" '
                     f'data-reported-unit="{esc(unit)}" data-status="{esc(row["status"])}" '
                     f'cx="{x(year):.2f}" cy="{y(values[year]):.2f}" r="{radius}" fill="{color}">'
                     f'<title>{esc(label)}</title></circle>')
    if not snapshot and not columns:
        latest = present[-1]
        latest_value = values[latest["year"]]
        label = f"{latest_value:.0f}" if indexed else number(latest_value, unit, compact=True)
        parts.append(f'<text class="end-label" x="{x(latest["year"]) - 10:.2f}" '
                     f'y="{y(latest_value) - 12:.2f}" text-anchor="end" font-size="20" '
                     f'font-weight="bold" fill="{color}" stroke="#FFFFFF" stroke-width="4" '
                     f'paint-order="stroke">{esc(label)}</text>')
    source = SOURCE_NAMES.get(sample["source_id"], sample["source_id"])
    breaks = [current["period"] for previous, current in zip(annual, annual[1:])
              if current["comparability"] != previous["comparability"]]
    note = f"Source: {source}. Annual observations; missing years and definition changes are not connected."
    if snapshot and len(present) == 1:
        kind = "estimate" if sample["status"] == "estimated" else "observation"
        note = f"Source: {source}. Single verified annual {kind}; no historical trend inferred."
    if breaks:
        kind = "Release-vintage" if sample["source_id"] == "ustr" else "Population-definition"
        note = (f"Source: {source}. {kind} breaks: " + ", ".join(breaks) +
                ". Missing years and definition changes are not connected.")
        if sample["source_id"] == "ustr":
            note += " Archival 2024 estimates are not used for growth against the newer 2025 vintage."
    if sample["period_basis"] == "academic":
        note += " Academic years use ending years."
    if sample["period_basis"] == "reporting":
        note += " Reporting years, not physical-presence counts."
    if sample["source_id"] in SOURCE_POLICIES:
        note += " " + SOURCE_POLICIES[sample["source_id"]]["figure_notice"]
    for line, text in enumerate(textwrap.wrap(note, width=110)):
        parts.append(f'<text class="figure-source" x="115" y="{510 + line * 18}" font-size="13" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def regional_series(rows, measure, direction):
    rows = primary_observations(rows)
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


def svg_comparison(rows, measure, direction, theme="themarginoferror", logarithmic=False,
                   geographies=COMPARISON_GEOGRAPHIES, year_range=None):
    if not geographies or len(set(geographies)) != len(geographies) or any(
            geo not in COMPARISON_GEOGRAPHIES for geo in geographies):
        raise ValueError("Comparison geographies must be distinct mainland China, Hong Kong or Macau")
    groups = {geo: annual for geo, annual in regional_series(rows, measure, direction).items()
              if geo in geographies}
    present = [r for annual in groups.values() for r in annual if r["value"] is not None]
    if not present:
        return '<p class="gap">No verified annual observations for this measure and direction.</p>'
    if len({(r["unit"], r["period_basis"]) for r in present}) != 1:
        raise ValueError("Comparison units and period bases must match")
    plotted = [r for r in present if not logarithmic or r["value"] > 0]
    if not plotted:
        return '<p class="gap">No positive observations are available for a logarithmic view.</p>'
    first, end = min(r["year"] for r in present), max(r["year"] for annual in groups.values() for r in annual)
    if year_range is not None:
        if year_range[0] > first or year_range[1] < end:
            raise ValueError("Shared comparison year range cannot clip observations")
        first, end = year_range
    x = lambda year: 115 + (year - first) / max(1, end - first) * 835
    if logarithmic:
        low = math.floor(math.log10(min(r["value"] for r in plotted)))
        high = max(low + 1, math.ceil(math.log10(max(r["value"] for r in plotted))))
        ticks = [10 ** power for power in range(low, high + 1)]
        y = lambda value: 420 - (math.log10(value) - low) / (high - low) * 240
    else:
        maximum, ticks = linear_axis(max(r["value"] for r in plotted))
        y = lambda value: 420 - value / maximum * 240
    direction_label = "To the United States" if direction == "to_us" else "From the United States"
    title = MEASURES[measure] + ": " + direction_label
    split_panel = tuple(geographies) != tuple(COMPARISON_GEOGRAPHIES)
    metadata = ""
    if split_panel:
        title += " · " + " and ".join(GEOGRAPHIES[geo] for geo in groups)
        metadata = f' data-geographies="{" ".join(groups)}" data-first-year="{first}" data-last-year="{end}"'
    description = ("Separately reported geographies" if split_panel else "Three separate geographies")
    unit = "Nominal USD" if present[0]["unit"] == "USD" else present[0]["unit"].capitalize()
    if logarithmic:
        unit += " (log scale)"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="{esc(title)}"{metadata}>',
        f'<title>{esc(title)}</title><desc>{description}, not a regional total. Missing observations and definition changes are not connected.</desc>',
        f'<rect class="chart-background" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{CHART_THEMES[theme]["background"]}"/>',
        f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
        f'<text x="115" y="40" font-size="28" font-weight="bold" fill="{TEXT}">{esc(MEASURES[measure])}</text>',
        f'<text x="115" y="75" font-size="22">{esc(direction_label)}</text>',
    ]
    missing = []
    for i, geo in enumerate(groups):
        color = PARTNER_COLORS[geo]
        available = any(r["value"] is not None for r in groups[geo])
        if not available:
            missing.append(GEOGRAPHIES[geo])
        pos = 115 + i * 270
        dash = ' stroke-dasharray="7 4"' if any(r["source_id"] == "comtrade" for r in groups[geo]) else ""
        parts.append(f'<path class="legend-swatch" data-geography="{geo}" d="M{pos} 108h28" stroke="{color}" stroke-width="3.2"{dash}/>'
                     f'<text x="{pos + 36}" y="114" fill="{TEXT}">{esc(GEOGRAPHIES[geo])}{"*" if not available else ""}</text>')
    parts.append(f'<text class="axis-unit" x="115" y="153">{esc(unit)}</text>')
    for value in ticks:
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity="0.6" stroke-width="0.5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(axis_label(value, present[0]["unit"]))}</text>')
    for year in sorted({first, end} | {year for year in range((first // 5 + 1) * 5, end, 5) if year - first >= 2 and end - year >= 2}):
        parts.append(f'<text x="{x(year):.2f}" y="455" font-size="18" text-anchor="middle">{year}</text>')
    parts.append(f'<path d="M115 180V420H950" stroke="{GRID}" stroke-width="0.8" fill="none"/>')
    if any(r["year"] == 2020 for r in present):
        reference_x = x(2020)
        anchor = "start" if reference_x < 550 else "end"
        label_x = max(400, reference_x + 8) if anchor == "start" else reference_x - 8
        parts.append(f'<path d="M{reference_x:.2f} 180V420" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="4 5"/>'
                     f'<text x="{label_x:.2f}" y="153" text-anchor="{anchor}">2020 baseline</text>')
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
            parts.append(f'<circle data-geography="{geo}" data-series-id="{esc(row["series_id"])}" data-year="{row["year"]}" '
                         f'data-value="{row["value"]}" data-period="{esc(row["period"])}" '
                         f'data-status="{esc(row["status"])}" cx="{x(row["year"]):.2f}" '
                         f'cy="{y(row["value"]):.2f}" r="3" fill="{PARTNER_COLORS[geo]}"><title>{esc(label)}</title></circle>')
    note = "Sources: " + "; ".join(SOURCE_NAMES.get(s, s) for s in sorted({r["source_id"] for r in present})) + ". "
    if measure == "goods" and any(r["source_id"] == "comtrade" for r in present):
        note += "Macau dashed: customs exports FOB/imports CIF; others: BEA balance-of-payments. Accounting differs. "
    if measure == "services" and any(r["source_id"] == "ustr" and r["year"] == 2024 for r in present):
        note += "Macau 2024 archival vintage is not compared with 2025. "
    if measure == "visitors" and direction == "from_us":
        if "HKG" in groups:
            note += "Hong Kong: residence through 2022, nationality from 2023. "
        if "MAC" in groups:
            note += "Macau: travel-document issuing place (residence before April 2015). "
        note += "Trips, not people. "
    if measure in {"international_students", "enrolled_students"} and any(
            r["source_id"] == "iie" and 2021 <= r["year"] <= 2023 for r in present):
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
    # Keep archival figure exports reproducible without presenting recovery as an activity trend.
    for metric, title in WEIBO_CHARTS.items():
        paths = {}
        for theme in CHART_THEMES:
            svg = svg_weibo(summary, metric, theme)
            if svg.startswith("<svg"):
                paths[theme] = export_figure(root, Path("weibo") / theme / metric, svg)
        if paths:
            relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                        for theme, files in paths.items()}
            gallery["weibo"].append(f'<article><h3>{esc(title)}</h3>{figure_links(relative)}</article>')
        else:
            for theme in CHART_THEMES:
                remove_figure(root, Path("weibo") / theme / metric)
    write_atomic(root / "site/downloads/weibo-summary.json", json_text(summary))
    downloads = [("accounts", summary["accounts"]), ("years", summary["yearly"]),
                 ("text-completeness", summary["text_completeness"])]
    monthly_path = root / "site/downloads/weibo-months.csv"
    if "monthly" in summary:
        downloads.append(("months", summary["monthly"]))
    elif monthly_path.is_file():
        monthly_path.unlink()
    for name, key in (("days", "daily"), ("rolling30", "rolling_30d")):
        path = root / f"site/downloads/weibo-{name}.csv"
        if key in summary:
            downloads.append((name, summary[key]))
        elif path.is_file():
            path.unlink()
    for name, records in downloads:
        stream = io.StringIO(newline="")
        columns = sorted(records[0]) if records else (["year", "recovered_posts"] if name == "years" else ["account_id"])
        if name == "months":
            columns = ["month", "observed_accounts", "partial_window", "recovered_posts"]
        elif name == "days":
            columns = sorted(DAILY_FIELDS)
        elif name == "rolling30":
            columns = sorted(ROLLING_FIELDS)
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list))
                          else value for key, value in row.items()} for row in records)
        write_atomic(root / f"site/downloads/weibo-{name}.csv", stream.getvalue())
    write_atomic(root / "site/weibo.html", explorer_page(summary))
    for name in ("weibo-explorer.css", "weibo-explorer.js"):
        write_atomic(root / "site/assets" / name, (Path(__file__).parent / "static" / name).read_text())


def build_languages(root, data, gallery):
    validate_language_data(data)
    for chart_id in LANGUAGE_RETIRED_CHARTS:
        for theme in CHART_THEMES:
            remove_figure(root, Path("language_learning") / theme / chart_id)
    cards, plotted_rows, count = [], [], 0
    for chart_id, config in LANGUAGE_CHARTS.items():
        paths = {}
        for theme in CHART_THEMES:
            svg = svg_language_chart(data, chart_id, theme)
            relative = Path("language_learning") / theme / chart_id
            if svg is None:
                remove_figure(root, relative)
            else:
                paths[theme] = export_figure(root, relative, svg)
        body = '<p class="gap">No verified observations for this indicator in the frozen snapshot.</p>'
        if paths:
            count += 1
            image = paths["themarginoferror"]["png"]
            body = (f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(config["title"])}">'
                    f'<img src="{esc(image)}" alt="{esc(config["title"])} - {esc(config["subtitle"])}" '
                    'width="1000" height="600" loading="lazy"></div>' +
                    f'<p class="chart-note">{esc(config["note"])}</p>' + figure_links(paths))
            relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                        for theme, files in paths.items()}
            gallery["language_learning"].append(
                f'<article><h3>{esc(config["title"])}</h3><p>{esc(config["subtitle"])}</p>' +
                figure_links(relative) + '</article>')
            exact = []
            for group in chart_points(data, chart_id):
                for point in group["points"]:
                    definition = data["series"][group["id"]]
                    provenance = data["sources"][point["source_id"]]
                    plotted_rows.append(dict(point, chart_id=chart_id, label=group["label"],
                                             scope=definition["scope"], definition=definition["notes"],
                                             period_basis=definition["period_basis"],
                                             source_name=provenance["name"],
                                             source_vintage=provenance["vintage"]))
                    exact.append(f'<tr><th scope="row">{esc(group["label"])}</th><td>{point["year"]}</td>'
                                 f'<td>{point["value"]:,}</td><td>{point["plotted_value"]:,.4f}</td>'
                                 f'<td>{esc(point["status"])}</td><td>{esc(provenance["vintage"])}</td></tr>')
            body += ('<details><summary>Exact reported and plotted values</summary><div class="table-scroll"><table>'
                     '<thead><tr><th>Series</th><th>Year / ending year</th><th>Reported count</th>'
                     f'<th>{esc(config["unit"])}</th><th>Status</th><th>Source vintage</th></tr></thead>'
                     '<tbody>' + "".join(exact) + '</tbody></table></div></details>')
        cards.append(f'<section class="series-panel" id="{chart_id}"><h2>{esc(config["title"])}</h2>{body}</section>')
    write_atomic(root / "site/downloads/language-learning.json", json_text(data))
    raw_rows = []
    for observation in data["observations"]:
        definition = data["series"][observation["series_id"]]
        provenance = data["sources"][observation["source_id"]]
        raw_rows.append(dict(observation, **{k: v for k, v in definition.items() if k != "notes"},
                             definition_notes=definition["notes"], source_name=provenance["name"],
                             source_vintage=provenance["vintage"], source_locator=provenance["locator"],
                             source_assets=json.dumps(provenance["assets"], sort_keys=True)))
    for name, rows in [("language-observations", raw_rows), ("language-chart-values", plotted_rows)]:
        stream = io.StringIO(newline="")
        columns = sorted({key for r in rows for key in r})
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        write_atomic(root / "site/downloads" / (name + ".csv"), stream.getvalue())
    sources = "".join(
        f'<li><strong>{esc(item["name"])} - {esc(item["vintage"])}</strong>. {esc(item["locator"])}. '
        f'{esc(item["notes"])}<ul>' +
        "".join(f'<li><a href="{esc(a["url"])}">Primary source</a>; retrieved {esc(a["retrieved_at"])}; '
                f'SHA-256 <code>{a["sha256"]}</code></li>' for a in item["assets"]) + '</ul></li>'
        for item in data["sources"].values())
    coverage_html = "".join(f'<tr><th scope="row">{esc(c["id"].replace("_", " "))}</th>'
                            f'<td>{esc(c["status"])}</td><td>{esc(c["description"])}</td></tr>'
                            for c in data["coverage"])
    context = data["context"]
    economist = context["economist"]
    census = {(r["series_id"], r["year"]): r for r in data["observations"]}
    latest = max((r for r in data["observations"] if r["series_id"] == "mla:chinese" and r["value"] is not None),
                 key=lambda r: r["year"], default=None)
    reference = census.get(("mla:chinese", 2013))
    census_note = ""
    if latest and reference and reference["value"] is not None:
        census_note = (f'<p>The national census shows Chinese/Mandarin moving from {reference["value"]:,} registrations '
                       f'in 2013 to {latest["value"]:,} in {latest["year"]}. The benchmark compares Chinese, Japanese '
                       'and Korean; the share panel uses all-language totals as its denominator. '
                       'Neither establishes what caused the changes.</p>')
        earlier_total = census.get(("mla:all_languages", 2013))
        latest_total = census.get(("mla:all_languages", latest["year"]))
        if reference["value"] and earlier_total and earlier_total["value"] and latest_total and latest_total["value"]:
            chinese_change = (latest["value"] / reference["value"] - 1) * 100
            all_change = (latest_total["value"] / earlier_total["value"] - 1) * 100
            earlier_share = reference["value"] / earlier_total["value"] * 100
            latest_share = latest["value"] / latest_total["value"] * 100
            census_note += (f'<p>Over those same years, Chinese/Mandarin registrations changed {chinese_change:+.1f}%, '
                            f'compared with {all_change:+.1f}% for all languages. Its share of language registrations '
                            f'was {earlier_share:.2f}% in 2013 and {latest_share:.2f}% in {latest["year"]}. '
                            'An absolute decline alone does not establish a China-specific retreat.</p>')
    estimate = next((r for r in data["observations"] if r["series_id"] == "schools:k12_estimate"), None)
    school_note = (f'<p>The separate 2014-15-era K-12 survey estimated <strong>{estimate["value"]:,} Chinese '
                   'enrollments</strong>, combining reported and modeled state data. It is not a current census '
                   'and excludes substantial community/heritage and summer-school coverage.</p>') if estimate and estimate["value"] is not None else ""
    japanese = census.get(("schools:k12_japanese_estimate", 2015))
    korean = census.get(("schools:korean_respondent_enrollment", 2015))
    if japanese and japanese["value"] is not None:
        school_note += (f'<p>The same national-estimate table reports {japanese["value"]:,} Japanese enrollments '
                        'but no comparable Korean total. Its separate reported high-school program counts measure '
                        'availability, not the number of learners or unmet demand.</p>')
    if korean and korean["value"] is not None:
        school_note += (f'<p>The report identifies {korean["value"]:,} Korean-class enrollments among 43 reporting '
                        'schools across 22 states. This respondent-only count is retained in the complete download, '
                        'not plotted as a national estimate alongside Chinese and Japanese.</p>')
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Language learning | U.S. language-learning indicators</title>'
                '<link rel="stylesheet" href="assets/style.css"></head><body><div class="page">'
                '<header><p><a href="index.html">Exchange dashboard</a> · '
                '<a href="comparisons.html">Three-geography comparisons</a></p>'
                '<h1>Language learning.</h1>'
                f'<p class="lead">{esc(context["question"])}</p>'
                '<p>College registrations, exam participation, immersion programs and degree awards are different '
                'populations. They are never added into a learner total or interpreted as border crossings.</p>'
                '<p>MLA figures concern U.S. institutions. <strong>The annual AP panel is global, not U.S.-only</strong>; '
                'a separate historical AP panel covers '
                'U.S. public-school graduating classes 2007-2013 and exams taken during high school, not annual '
                'exam administrations. A current U.S.-only annual AP series remains unverified.</p>'
                '<p>Each panel keeps its actual reference years, source vintage and population. '
                'College census rounds are not annual observations; academic-year awards use ending years.</p>'
                '<p><a href="downloads/language-learning.json" download>Complete dataset, definitions and provenance · JSON</a> · '
                '<a href="downloads/language-observations.csv" download>Every source observation · CSV</a> · '
                '<a href="downloads/language-chart-values.csv" download>Every reported and plotted chart value · CSV</a></p>'
                '</header><main><section class="series-panel"><h2>Reading the Economist claim</h2>'
                f'<p><a href="{esc(economist["url"])}">{esc(economist["title"])}</a>, '
                f'{esc(economist["date"])}. {esc(economist["interpretation"])}</p>'
                '<p>The article cites a rounded 21% decline from 2016 to 2020. That comparison comes from '
                'the separate MLA pandemic snapshot of 1,308 matched institutions, not the full 2021 census. '
                'It is retained as context, never spliced into the national census series.</p>'
                + census_note + '</section>' +
                "".join(cards) +
                '<section class="series-panel"><h2>School-age evidence and its limits</h2>' + school_note +
                '<p>Nexus reports 335 programs in its 2025 U.S. inventory. Its survey received 102 U.S. responses '
                'plus one from Hong Kong. The 34,341 respondent-associated enrollments therefore do not become '
                'a U.S. national learner estimate here. Program counts and survey-response counts remain distinct.</p>'
                '<p>The 2011, 2021 and 2025 inventories use different coverage definitions. Their bars are separate '
                'snapshots, not evidence of a calculated growth rate. Establishment-year responses among surviving '
                'survey respondents are not reconstructed counts of programs active in earlier years.</p></section>'
                '<section class="series-panel"><h2>Coverage and unresolved comparisons</h2><div class="table-scroll"><table>'
                '<thead><tr><th>Indicator</th><th>Coverage</th><th>Definition and limitation</th></tr></thead>'
                '<tbody>' + coverage_html + '</tbody></table></div></section>'
                '<section class="series-panel"><h2>Sources, vintages and reuse</h2>'
                f'<p>{esc(context["rights"])}</p>'
                '<p>MLA network terms limit ordinary use to personal noncommercial use; separate commercial reuse '
                'permission is unverified. These publication backgrounds do not grant source-content rights.</p>'
                '<details><summary>Primary sources and retained checksums</summary><ul>' +
                sources + '</ul></details></section></main></div></body></html>')
    write_atomic(root / "site/language-learning.html", document)
    return count


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
    language_data = load(root / "data/site/language_learning.json", None)
    if language_data is not None:
        validate_language_data(language_data)
    confucius_data = load(root / "data/site/confucius_programs.json", None)
    if confucius_data is not None:
        validate_confucius(confucius_data)
    business_data = load(root / "data/site/business_presence.json", None)
    if business_data is not None:
        validate_business_data(business_data)
    immigration_data = load(root / "data/site/immigration.json", None)
    if immigration_data is not None:
        validate_immigration_data(immigration_data)
    state_data = load(root / "data/site/state_immigration.json", None)
    state_geometry = load(root / "data/site/us_states.geojson", None) if state_data is not None else None
    if state_data is not None:
        validate_state_immigration(state_data, state_geometry)
        if immigration_data is None:
            raise ValueError("The state immigration map requires the immigration page")
    student_estimate_data = load(root / "data/site/student_estimates.json", None)
    if student_estimate_data is not None:
        student_estimates.validate(student_estimate_data)
    opinion_data = load(root / "data/site/opinions.json", None)
    if opinion_data is not None:
        validate_opinion_data(opinion_data)
    review_path = root / "data/site/gap_review.csv"
    review_text = review_path.read_text(encoding="utf-8") if review_path.is_file() else None
    review_rows = list(csv.DictReader(io.StringIO(review_text))) if review_text is not None else []
    if review_text is not None:
        required = {"gap_id", "checked_at", "area", "route", "measure", "period", "disposition",
                    "verified_recovery", "unresolved_or_scope_limit", "primary_sources"}
        if (not review_rows or len({r.get("gap_id") for r in review_rows}) != len(review_rows)
                or any(set(r) != required or any(not value for value in r.values()) for r in review_rows)):
            raise ValueError("Itemized gap review must contain complete uniquely identified cases")
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
            split_regions = measure in SPLIT_REGIONAL_MEASURES
            panels = (("CHN",), ("HKG", "MAC")) if split_regions else (COMPARISON_GEOGRAPHIES,)
            panel_labels = {"-".join(geo.lower() for geo in geographies):
                            " and ".join(GEOGRAPHIES[geo] for geo in geographies)
                            for geographies in panels}
            available = [r for annual in regional.values() for r in annual if r["value"] is not None]
            if len({(r["unit"], r["period_basis"]) for r in available}) > 1:
                raise ValueError("Comparison units and period bases must match")
            year_range = ((min(r["year"] for r in available),
                           max(r["year"] for annual in regional.values() for r in annual))
                          if available else None)
            versions = {}
            for scale in ("levels", "log"):
                versions[scale] = {}
                if split_regions:
                    for theme in CHART_THEMES:
                        remove_figure(root, Path(figure_category(measure)) / "comparisons" / theme /
                                      f"chn-hkg-mac-{direction}-{measure}-{scale}")
                for geographies in panels:
                    prefix = "-".join(geo.lower() for geo in geographies)
                    svg = svg_comparison(rows, measure, direction, logarithmic=scale == "log",
                                         geographies=geographies, year_range=year_range)
                    if not svg.startswith("<svg"):
                        for theme in CHART_THEMES:
                            remove_figure(root, Path(figure_category(measure)) / "comparisons" / theme /
                                          f"{prefix}-{direction}-{measure}-{scale}")
                        continue
                    versions[scale][prefix] = {}
                    for theme in CHART_THEMES:
                        themed = svg_comparison(rows, measure, direction, theme, logarithmic=scale == "log",
                                                geographies=geographies, year_range=year_range)
                        relative = (Path(figure_category(measure)) / "comparisons" / theme /
                                    f"{prefix}-{direction}-{measure}-{scale}")
                        versions[scale][prefix][theme] = export_figure(root, relative, themed)
                if not versions[scale]:
                    del versions[scale]

            def comparison_markup(scale):
                result = []
                for geographies in panels:
                    prefix = "-".join(geo.lower() for geo in geographies)
                    panel_label = panel_labels[prefix]
                    paths = versions[scale].get(prefix)
                    content = f'<p class="gap">No verified annual observations for {esc(panel_label)}.</p>'
                    if paths:
                        image = paths["themarginoferror"]["png"]
                        content = (
                            f'<div class="comparison-chart" tabindex="0" role="region" '
                            f'aria-label="{esc(heading)}: {esc(panel_label)}">'
                            f'<img src="{esc(image)}" alt="{esc(heading)}: {esc(panel_label)}'
                            f'{" on a log scale" if scale == "log" else ""}" '
                            'width="1000" height="600" loading="lazy"></div>' + figure_links(paths))
                    if split_regions:
                        content = (f'<div class="comparison-pane" data-geographies="{" ".join(geographies)}" '
                                   f'role="group" aria-label="{esc(panel_label)}">'
                                   f'<h3 class="comparison-region-title">{esc(panel_label)}</h3>{content}</div>')
                    result.append(content)
                markup = "".join(result)
                return f'<div class="comparison-panels">{markup}</div>' if split_regions else markup

            body = ""
            if "levels" in versions:
                comparison_count += 1
                if split_regions:
                    body += '<p class="chart-context">Same year range; separate vertical scales.</p>'
                body += comparison_markup("levels")
                if measure == "goods" and any(r["source_id"] == "comtrade" for r in available):
                    body += ('<p class="chart-note">Macau (dashed) uses customs accounting: exports FOB, imports CIF. '
                             'Mainland China and Hong Kong use balance-of-payments data; the accounting bases differ.</p>')
                if measure == "services" and any(r["source_id"] == "ustr" for r in available):
                    body += ('<p class="chart-note">Macau releases are separate annual snapshots. '
                             'Different release vintages are not connected or used to calculate growth.</p>')
                if "log" in versions:
                    body += ('<details><summary>Logarithmic view — useful when series differ greatly in size</summary>'
                             + comparison_markup("log") + '</details>')
                catalog_label = "Regional comparison"
                catalog = f'<article class="combined-chart"><h3>{catalog_label}: {esc(heading)}</h3>'
                for scale, panel_versions in versions.items():
                    for prefix, paths in panel_versions.items():
                        relative_paths = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                                          for theme, files in paths.items()}
                        pane_caption = f' · {esc(panel_labels[prefix])}' if split_regions else ""
                        catalog += (f'<h4>{"Reported values" if scale == "levels" else "Logarithmic view"}'
                                    f'{pane_caption}</h4>' + figure_links(relative_paths))
                gallery[figure_category(measure)].insert(0, catalog + '</article>')
            else:
                body += '<p class="gap">No verified annual series for these geographies in this direction. Missing is not zero.</p>'
            body += '<details><summary>Exact values, definitions and unavailable series</summary>'
            for geo, annual in regional.items():
                present = [r for r in annual if r["value"] is not None]
                body += f'<h3>{esc(GEOGRAPHIES[geo])}</h3>'
                if present:
                    latest = max(present, key=lambda r: r["year"])
                    body += (f'<p>Source: <a href="{esc(SOURCE_PAGES.get(latest["source_id"], latest["source_url"]))}">{esc(SOURCE_NAMES[latest["source_id"]])}</a>'
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
                           '<h1>Mainland China,<br>Hong Kong and Macau.</h1>'
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
                         "downloads/weibo-years.csv", "downloads/weibo-text-completeness.csv",
                         "downloads/weibo-months.csv", "downloads/weibo-days.csv", "downloads/weibo-rolling30.csv",
                         "assets/weibo-explorer.css", "assets/weibo-explorer.js"]:
            path = site / relative
            if path.is_file():
                path.unlink()
    language_count = build_languages(root, language_data, gallery) if language_data is not None else 0
    confucius_count = build_confucius(root, confucius_data, gallery) if confucius_data is not None else 0
    if confucius_data is None:
        for chart_id in CONFUCIUS_CHARTS:
            for theme in CHART_THEMES:
                remove_figure(root, Path("language_learning") / theme / chart_id)
        for relative in ("confucius.html", "downloads/confucius-programs.json",
                         "downloads/confucius-observations.csv", "downloads/confucius-records.csv",
                         "assets/confucius.js", "assets/confucius.css"):
            (site / relative).unlink(missing_ok=True)
    if language_data is None:
        for chart_id in set(LANGUAGE_CHARTS) | LANGUAGE_RETIRED_CHARTS:
            for theme in CHART_THEMES:
                remove_figure(root, Path("language_learning") / theme / chart_id)
        for relative in ["language-learning.html", "downloads/language-learning.json",
                         "downloads/language-observations.csv", "downloads/language-chart-values.csv"]:
            path = site / relative
            if path.is_file():
                path.unlink()
    business_count = build_business(root, business_data, gallery) if business_data is not None else 0
    opinion_count = build_opinions(root, opinion_data, gallery) if opinion_data is not None else 0
    if opinion_data is None:
        for chart_id in OPINION_CHARTS:
            for theme in CHART_THEMES:
                remove_figure(root, Path("opinions") / theme / chart_id)
        for relative in ("opinions.html", "downloads/opinions.json", "downloads/opinion-observations.csv",
                         "downloads/opinion-chart-values.csv"):
            (site / relative).unlink(missing_ok=True)
    immigration_count = build_immigration(root, immigration_data, gallery, state_data, state_geometry) if immigration_data is not None else 0
    if state_data is None:
        for theme in CHART_THEMES:
            for metric in ("share", "count"):
                remove_figure(root, Path("immigration") / theme / ("state-china-" + metric))
        for relative in ("downloads/state-immigration.json", "downloads/state-immigration.csv",
                         "downloads/us-states.geojson", "assets/state-map.js", "assets/state-map.css"):
            (site / relative).unlink(missing_ok=True)
    if immigration_data is None:
        for chart_id in IMMIGRATION_CHARTS:
            for theme in CHART_THEMES:
                remove_figure(root, Path("immigration") / theme / chart_id)
        for name in ["immigration.html", "downloads/immigration.json", "downloads/immigration-observations.csv", "downloads/immigration-chart-values.csv"]:
            (site / name).unlink(missing_ok=True)
    if business_data is None:
        for chart_id in set(BUSINESS_CHARTS) | BUSINESS_RETIRED_CHARTS:
            for theme in CHART_THEMES:
                remove_figure(root, Path("business_presence") / theme / chart_id)
        for relative in ["business-presence.html", "downloads/business-presence.json",
                         "downloads/business-observations.csv", "downloads/business-chart-values.csv"]:
            path = site / relative
            if path.is_file():
                path.unlink()
    payload = {"observations": rows, "sources": sources, "coverage": matrix,
               "primary_series": primary_series(rows),
               "geographies": GEOGRAPHIES, "measures": MEASURES,
               "prefer_current_travel": True,
               "source_policies": SOURCE_POLICIES,
               "source_pages": SOURCE_PAGES,
               "source_names": SOURCE_NAMES, "charts": charts, "chart_themes": CHART_THEMES,
               "figures": figure_paths}
    if student_estimate_data is not None:
        student_estimates.export(root, student_estimate_data)
        payload["student_estimates"] = student_estimate_data
    else:
        for name in ["student-estimates.json", "student-estimates.csv"]:
            (site / "downloads" / name).unlink(missing_ok=True)
    if review_text is not None:
        write_atomic(site / "downloads/gap-review.csv", review_text)
        payload["gap_review"] = review_rows
    else:
        (site / "downloads/gap-review.csv").unlink(missing_ok=True)
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
    category_sections = []
    for category, label in FIGURE_CATEGORIES.items():
        if category == "services_trade":
            continue
        if category == "goods_trade":
            content = "".join(
                f'<section id="{key}"><h3>{title}</h3>{"".join(gallery[key])}</section>'
                for key, title in (("goods_trade", "Goods"), ("services_trade", "Services")))
            category_sections.append(f'<section id="trade"><h2>Trade</h2>{content}</section>')
        else:
            category_sections.append(f'<section id="{category}"><h2>{label}</h2>{"".join(gallery[category])}</section>')
    figure_index = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>Exchange charts by category</title>'
                    '<style>body{max-width:1000px;margin:auto;padding:24px;font:18px/1.6 Georgia,serif;'
                    'color:#1A1A1A;background:#F7F5F0}article{padding:12px 0;border-bottom:1px solid #D6D3CC}'
                    'a{color:#3D6F8C}h2{margin-top:48px}h3{font-size:21px}li{margin:8px 0}</style>'
                    '<h1>Exchange charts by category</h1>'
                    '<p>PNG images are 3000 \u00d7 1800 pixels. Both backgrounds contain the same reported values.</p>' +
                    "".join(category_sections) + '</html>')
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
{"<p><a href='language-learning.html'>Chinese-language learning: college, AP, school programs and degree awards</a> — separate educational indicators, not bilateral flows.</p>" if language_data is not None else ""}
{"<p><a href='confucius.html'>Confucius Institutes, Classrooms and documented successor programs in the United States</a>.</p>" if confucius_data is not None else ""}
{"<p><a href='business-presence.html'>U.S. and European businesses in China over time: annual affiliate and enterprise histories</a>.</p>" if business_data is not None else ""}
{"<p><a href='immigration.html'>Immigration: permanent-resident grants, not visitor trips or visas</a>.</p>" if immigration_data is not None else ""}
{"<p><a href='opinions.html'>Public opinion in both directions, including age differences</a>.</p>" if opinion_data is not None else ""}
{"<p><a href='weibo.html'>Explore U.S. media accounts on Weibo</a> — documented identities and publisher relationships, not posting trends.</p>" if weibo_summary is not None else ""}
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
<select id="chart-mode"><option value="levels">Reported values</option><option value="index">Baseline = 100</option></select></div>
<div class="chart-control"><label for="chart-theme">Background</label><select id="chart-theme">{theme_options}</select></div></div>
<div id="chart" tabindex="0" role="region" aria-label="Annual chart; scroll horizontally on narrow screens">{charts[selected_id]["levels"]}</div>
<p class="chart-note chart-scroll-hint">On a narrow screen, scroll the chart sideways to keep its labels readable.</p>
<p class="chart-note">Gaps stay gaps. Academic-year labels use their ending year on the axis; the 2020 baseline is 2019/20, not calendar 2020. Reporting-year UIS data are not physical-presence counts.</p>
<details id="selected-table"><summary>Exact values for this series</summary><div id="series-table">{annual_table(selected)}</div></details>
<div id="partial-panel" class="partial" hidden></div>
<div class="source-note" id="series-source">Source: <a href="{esc(SOURCE_PAGES.get(current["source_id"], current["source_url"]))}">{esc(SOURCE_NAMES[current["source_id"]])}</a> \u00b7 {esc(current["source_vintage"])}. {esc(selected_source.get("notes", ""))}</div>
<p id="series-notes" class="chart-note">{esc(current["notes"])}</p>
</section>
{student_estimates.panel(student_estimate_data) if student_estimate_data is not None else ""}
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
{('<p><a href="downloads/gap-review.csv" download>Itemized source-recovery review &#183; CSV</a> '
  '&#8212; dated case-by-case findings; recovered values, outstanding years, confidentiality and source-population limits. '
  'This review accompanies rather than replaces the complete observation downloads.</p>') if review_text is not None else ""}
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
            "comparisons": comparison_count, "language_charts": language_count, "confucius_charts": confucius_count, "business_charts": business_count,
            "immigration_charts": immigration_count, "opinion_charts": opinion_count}
