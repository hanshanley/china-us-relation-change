"""House-style charts for separate, explicitly defined aggregate indicators."""

import html
import math
import textwrap

from .theme import CHART_THEMES, FONT, GRID, MUTED, TEXT, axis_label


def svg_indicator_chart(config, groups, theme, description, point_class):
    points = [r for group in groups for r in group["points"]]
    if not points:
        return None
    esc = lambda value: html.escape(str(value), quote=True)
    maximum = max(r["plotted_value"] for r in points) * 1.15 or 1
    magnitude = 10 ** math.floor(math.log10(maximum))
    maximum = math.ceil(maximum / magnitude) * magnitude
    minimum, maximum = config.get("y_min", 0), config.get("y_max", maximum)
    if maximum <= minimum or any(not minimum <= r["plotted_value"] <= maximum for r in points):
        raise ValueError("Indicator axis limits cannot clip observations")
    bars = config["mode"] == "bars"
    first = config.get("first_year", min(r["year"] for r in points))
    last = max(first + 1, max(r["year"] for r in points), config.get("last_year", 0))
    x = lambda year: 115 + (year - first) / (last - first) * 835
    y = lambda value: 420 - (value - minimum) / (maximum - minimum) * 250

    def metadata(group, row):
        year, basis = row["year"], group.get("period_basis", "")
        period = (f"1 July {year}" if "July" in basis else
                  f"FY{year}" if "fiscal" in basis and point_class == "immigration-point" else
                  f"Fiscal year ending {year}" if "fiscal" in basis else
                  f"{year - 1}/{str(year)[-2:]}" if "academic" in basis else
                  f"Class of {year}" if basis == "graduating class" else str(year))
        return (f'data-period="{esc(period)}" data-reported-value="{row["value"]}" '
                f'data-reported-unit="{esc(row.get("reported_unit", config["unit"]))}" '
                f'data-status="{esc(row.get("status", ""))}"')
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" role="img" '
        f'aria-label="{esc(config["title"])}"><title>{esc(config["title"])}</title>',
        f'<desc>{esc(description)}</desc>',
        f'<rect class="chart-background" width="1000" height="600" fill="{CHART_THEMES[theme]["background"]}"/>',
        f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
        f'<text x="115" y="40" font-size="27" font-weight="bold" fill="{TEXT}">{esc(config["title"])}</text>',
        f'<text x="115" y="77" font-size="18">{esc(config["subtitle"])}</text>',
        f'<text class="axis-unit" x="115" y="145" font-size="18">{esc(config["unit"])}</text>',
    ]
    if not bars:
        for i, group in enumerate(groups):
            pos = ([115, 550] if len(groups) <= 2 else [115, 345, 550, 760])[i]
            parts.append(f'<path d="M{pos} 108h25" stroke="{group["color"]}" stroke-width="3"/>'
                         f'<text class="legend-label" x="{pos + 33}" y="114" font-size="17" fill="{TEXT}">{esc(group["label"])}</text>')
    for fraction in (0, .5, 1):
        value = minimum + (maximum - minimum) * fraction
        label = axis_label(value) + ("%" if config["mode"] == "share" else "")
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity=".6" stroke-width=".5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(label)}</text>')
    parts.append(f'<path d="M115 170V420H950" stroke="{GRID}" stroke-width=".8" fill="none"/>')
    if bars:
        for i, group in enumerate(groups):
            pos = 115 + (i + .5) / len(groups) * 835
            if not group["points"]:
                label = group.get("unavailable_label", "Unavailable")
                parts.append(f'<g class="unavailable-bar" data-series-id="{esc(group["id"])}" '
                             f'data-label="{esc(group["label"])}" data-reason="{esc(label)}">'
                             f'<text x="{pos:.2f}" y="450" text-anchor="middle">{esc(label)}</text>'
                             f'<text x="{pos:.2f}" y="478" text-anchor="middle" font-size="18">{esc(group["label"])}</text></g>')
                continue
            if len(group["points"]) != 1:
                raise ValueError("Program inventory bars require separate single-snapshot series")
            r = group["points"][0]
            height = 420 - y(r["plotted_value"])
            parts.append(
                f'<rect class="{point_class}" data-series-id="{esc(group["id"])}" data-year="{r["year"]}" '
                f'data-value="{r["plotted_value"]}" {metadata(group, r)} x="{pos - 65:.2f}" y="{y(r["plotted_value"]):.2f}" '
                f'width="130" height="{height:.2f}" fill="{group["color"]}"/>'
                f'<text x="{pos:.2f}" y="{y(r["plotted_value"]) - 12:.2f}" text-anchor="middle" fill="{TEXT}">{r["value"]:,}</text>'
                f'<text x="{pos:.2f}" y="450" text-anchor="middle">{r["year"]}</text>'
                f'<text x="{pos:.2f}" y="478" text-anchor="middle" font-size="18">{esc(group["label"])}</text>')
    else:
        ticks = [first] + [year for year in range((first // 5 + 1) * 5, last, 5)
                           if last - year >= 2 and year - first >= 2] + [last]
        observed_years = sorted({r["year"] for r in points})
        if len(observed_years) <= 8 and all(group["cadence"] != "annual" for group in groups):
            ticks = observed_years
        for year in ticks:
            parts.append(f'<text class="year-tick" x="{x(year):.2f}" y="457" text-anchor="middle" font-size="18">{year}</text>')
        for group in groups:
            path, previous = [], None
            for r in group["points"]:
                same_definition = previous is not None and previous["comparability"] == r["comparability"]
                contiguous = previous is not None and (r["year"] == previous["year"] + 1
                    if group["cadence"] == "annual" else
                    group["scheduled_years"].index(r["year"]) == group["scheduled_years"].index(previous["year"]) + 1)
                connected = same_definition and contiguous
                path.append(f'{"L" if connected else "M"}{x(r["year"]):.2f},{y(r["plotted_value"]):.2f}')
                previous = r
            parts.append(f'<path class="data-line" data-series-id="{esc(group["id"])}" d="{" ".join(path)}" '
                         f'stroke="{group["color"]}" stroke-width="3" fill="none"/>')
            for r in group["points"]:
                parts.append(f'<circle class="{point_class}" data-series-id="{esc(group["id"])}" '
                             f'data-year="{r["year"]}" data-value="{r["plotted_value"]}" '
                             f'{metadata(group, r)} '
                             f'cx="{x(r["year"]):.2f}" cy="{y(r["plotted_value"]):.2f}" r="4" fill="{group["color"]}">'
                             f'<title>{esc(group["label"])} {r["year"]}: {r["plotted_value"]:,.4f} {esc(config["unit"])}</title></circle>')
    for i, text in enumerate(textwrap.wrap(config["note"], width=106)):
        parts.append(f'<text class="figure-source" x="115" y="{520 + i * 20}" font-size="14" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)
