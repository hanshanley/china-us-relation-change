"""An offline, accessible choropleth with separate count and share exports."""

import bisect
import csv
import html
import io
import json
import math
from pathlib import Path

from .model import json_text
from .pipeline import write_atomic
from .state_immigration_sources import POPULATION, geometry_text, validate
from .theme import CHART_THEMES, FONT, GRID, MUTED, TEXT


COLORS = ("#F0E5E2", "#E1C7C1", "#CCA099", "#B4776E", "#98534A", "#7B2D26")
METRICS = {
    "share": {"field": "share_percent", "label": "Share of immigrant residents", "unit": "%",
              "bounds": (0, 2, 4, 6, 8, 10),
              "labels": ("Under 2%", "2-4%", "4-6%", "6-8%", "8-10%", "10%+")},
    "count": {"field": "china_born", "label": "Number of China-born residents", "unit": "people",
              "bounds": (0, 5000, 20000, 50000, 100000, 250000),
              "labels": ("Under 5k", "5-20k", "20-50k", "50-100k", "100-250k", "250k+")},
}


def esc(value):
    return html.escape(str(value), quote=True)


def fill(value, metric):
    if value is None:
        return "#D6D3CC"
    return COLORS[bisect.bisect_right(METRICS[metric]["bounds"], value) - 1]


def project(lon, lat, region):
    center, origin, p1, p2 = {"main": (-96, 38, 29.5, 45.5), "AK": (-154, 60, 55, 65),
                              "HI": (-157, 20, 8, 18)}[region]
    phi, phi0, phi1, phi2 = map(math.radians, (lat, origin, p1, p2))
    n = (math.sin(phi1) + math.sin(phi2)) / 2
    c = math.cos(phi1) ** 2 + 2 * n * math.sin(phi1)
    rho = math.sqrt(c - 2 * n * math.sin(phi)) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(phi0)) / n
    theta = n * math.radians((lon - center + 180) % 360 - 180)
    return rho * math.sin(theta), rho * math.cos(theta) - rho0


def simplify(points, tolerance=.22):
    if len(points) <= 2:
        return points
    ax, ay = points[0]
    bx, by = points[-1]
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    largest, index = -1, 0
    for i, (x, y) in enumerate(points[1:-1], 1):
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length)) if length else 0
        distance = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
        if distance > largest:
            largest, index = distance, i
    if largest <= tolerance * tolerance:
        return [points[0], points[-1]]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def map_paths(geometry):
    projected, regions = {}, {"main": [], "AK": [], "HI": []}
    for feature in geometry["features"]:
        postal = feature["properties"]["STUSAB"]
        region = postal if postal in {"AK", "HI"} else "main"
        shape = feature["geometry"]
        polygons = [shape["coordinates"]] if shape["type"] == "Polygon" else shape["coordinates"]
        rings = [[project(lon, lat, region) for lon, lat in ring] for polygon in polygons for ring in polygon]
        projected[feature["properties"]["GEOID"]] = (region, rings)
        regions[region].extend(point for ring in rings for point in ring)
    transforms = {}
    for region, points in regions.items():
        x, y, width, height = {"main": (207, 96, 747, 388), "AK": (38, 330, 180, 130),
                               "HI": (55, 480, 155, 48)}[region]
        left, right = min(p[0] for p in points), max(p[0] for p in points)
        top, bottom = min(p[1] for p in points), max(p[1] for p in points)
        scale = min(width / (right - left), height / (bottom - top))
        transforms[region] = (scale, x + (width - (right - left) * scale) / 2 - left * scale,
                               y + (height - (bottom - top) * scale) / 2 - top * scale)
    paths = {}
    for fips, (region, rings) in projected.items():
        scale, tx, ty = transforms[region]
        commands = []
        for ring in rings:
            points = simplify([(x * scale + tx, y * scale + ty) for x, y in ring])
            if len(points) >= 4:
                commands.append("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in points[:-1]) + "Z")
        if not commands:
            raise ValueError(f"Map simplification removed state {fips}")
        paths[fips] = "".join(commands)
    scale, tx, ty = transforms["main"]
    x, y = project(-77.0369, 38.9072, "main")
    return paths, (x * scale + tx, y * scale + ty)


def point_label(row, data):
    count = f'{row["china_born"]:,}' if row["china_born"] is not None else "Unavailable"
    share = f'{row["share_percent"]:.2f}%' if row["share_percent"] is not None else "Unavailable"
    total = f'{row["foreign_born"]:,}' if row["foreign_born"] is not None else "unavailable"
    return (f'{row["name"]}, {data["start_year"]}-{data["end_year"]}: {count} China-born residents; '
            f'{share} of {total} foreign-born residents. China excludes Hong Kong and Taiwan.')


def svg_map(data, paths, metric, theme="themarginoferror", interactive=False):
    config, background = METRICS[metric], CHART_THEMES[theme]["background"]
    outlines, dc_point = paths
    period = f'{data["start_year"]}-{data["end_year"]}'
    marks = []
    for row in data["states"]:
        value = row[config["field"]]
        tab = "-1" if row["fips"] == "11" else "0"
        interaction = f' role="button" tabindex="{tab}" aria-label="{esc(point_label(row, data))}"' if interactive else ""
        marks.append(f'<path class="state-shape" data-state-fips="{row["fips"]}" '
                     f'data-china-born="{row["china_born"] if row["china_born"] is not None else ""}" '
                     f'data-foreign-born="{row["foreign_born"] if row["foreign_born"] is not None else ""}" '
                     f'data-share-percent="{row["share_percent"] if row["share_percent"] is not None else ""}" '
                     f'fill="{fill(value, metric)}" stroke="{background}" stroke-width=".85" fill-rule="evenodd"'
                     f'{interaction} d="{outlines[row["fips"]]}"><title>{esc(point_label(row, data))}</title></path>')
    dc = next(r for r in data["states"] if r["fips"] == "11")
    x, y = dc_point
    dc_interaction = f' role="button" tabindex="0" aria-label="{esc(point_label(dc, data))}"' if interactive else ""
    marks.append(f'<g class="state-callout" data-state-fips="11"{dc_interaction}>'
                 f'<path d="M{x:.2f},{y:.2f}L958,{y + 30:.2f}" fill="none" stroke="{MUTED}" stroke-width=".8"/>'
                 f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{TEXT}"/>'
                 f'<rect class="state-callout-fill" x="946" y="{y + 25:.2f}" width="36" height="25" rx="2" '
                 f'fill="{fill(dc[config["field"]], metric)}" stroke="{background}"/>'
                 f'<text x="964" y="{y + 42:.2f}" text-anchor="middle" font-size="12" fill="{TEXT}">DC</text>'
                 f'<title>{esc(point_label(dc, data))}</title></g>')
    legend = []
    for i, (color, label) in enumerate(zip(COLORS, config["labels"])):
        x0 = 45 + i * 152
        legend.append(f'<rect x="{x0}" y="537" width="22" height="12" fill="{color}"/>'
                      f'<text x="{x0 + 29}" y="548" font-size="13" fill="{MUTED}">{esc(label)}</text>')
    viewbox = "0 90 1000 440" if interactive else "0 0 1000 600"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
            f'role="{"group" if interactive else "img"}" aria-label="China-born immigrant residents by U.S. state, {period}" '
            f'data-state-map="{metric}" data-period="{period}" style="font-family:{esc(FONT)}">'
            '<title>China-born residents, by U.S. state</title>'
            f'<desc>{esc(config["label"])}. {period} ACS five-year estimates. China excludes Hong Kong and Taiwan. '
            'Shares use all foreign-born residents, not all residents. Alaska and Hawaii are insets at separate scales.</desc>'
            f'<rect width="1000" height="600" fill="{"transparent" if interactive else background}"/>'
            + ("" if interactive else
               f'<text x="42" y="39" font-size="26" font-weight="700" fill="{TEXT}">China-born residents, by U.S. state</text>'
               f'<text x="42" y="68" font-size="16" fill="{MUTED}">{esc(config["label"])} | {period} ACS five-year estimates</text>')
            + "".join(marks)
            + f'<text class="state-inset-label" x="44" y="320" font-size="13" fill="{MUTED}">Alaska</text>'
            f'<text class="state-inset-label" x="57" y="476" font-size="13" fill="{MUTED}">Hawaii</text>'
            + ("" if interactive else "".join(legend) +
               f'<text x="42" y="577" font-size="11" fill="{MUTED}">Census ACS B05006. China excludes Hong Kong and Taiwan. Insets use separate scales; not annual arrivals.</text>')
            + '</svg>')


def build_state_map(root, data, geometry, gallery):
    from .render import export_figure, figure_links

    validate(data, geometry)
    root = Path(root)
    paths, exports = map_paths(geometry), {}
    for metric in METRICS:
        exports[metric] = {theme: export_figure(root, Path("immigration") / theme / ("state-china-" + metric),
                                               svg_map(data, paths, metric, theme)) for theme in CHART_THEMES}
        relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                    for theme, files in exports[metric].items()}
        gallery["immigration"].append(f'<article><h3>U.S. states: {esc(METRICS[metric]["label"])}</h3>'
                                     f'{figure_links(relative)}</article>')
    write_atomic(root / "site/downloads/state-immigration.json", json_text(data))
    write_atomic(root / "site/downloads/us-states.geojson", geometry_text(geometry))
    stream = io.StringIO(newline="")
    rows = []
    for row in data["states"]:
        flat = {k: v for k, v in row.items() if k != "reported_cells"}
        flat.update(start_year=data["start_year"], end_year=data["end_year"], population=POPULATION,
                    universe=data["universe"], moe_confidence_percent=90, source_table="B05006",
                    source_url=data["sources"]["table"]["url"], **row["reported_cells"])
        rows.append(flat)
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_atomic(root / "site/downloads/state-immigration.csv", stream.getvalue())
    for name in ("state-map.js", "state-map.css"):
        write_atomic(root / "site/assets" / name, (Path(__file__).parent / "static" / name).read_text())
    options = "".join(f'<option value="{s["fips"]}">{esc(s["name"])}</option>'
                      for s in sorted(data["states"], key=lambda s: s["name"]))
    exact = []
    for row in sorted(data["states"], key=lambda s: s["name"]):
        number = lambda value: f"{value:,}" if value is not None else "Unavailable"
        percentage = f'{row["share_percent"]:.2f}%' if row["share_percent"] is not None else "Unavailable"
        exact.append(f'<tr data-state-row="{row["fips"]}"><th scope="row">{esc(row["name"])}</th>'
                     f'<td>{number(row["china_born"])}</td><td>{percentage}</td><td>{number(row["foreign_born"])}</td>'
                     f'<td>{number(row["china_born_moe"])}</td><td>{number(row["foreign_born_moe"])}</td></tr>')
    model = {"start_year": data["start_year"], "end_year": data["end_year"], "states": data["states"],
             "national": data["national"], "metrics": METRICS, "colors": COLORS}
    graphic_links = "".join(f'<div><h3>{esc(config["label"])}</h3>{figure_links(exports[metric])}</div>'
                            for metric, config in METRICS.items())
    legend = "".join(f'<span><i style="background:{color}"></i>{esc(label)}</span>'
                     for color, label in zip(COLORS, METRICS["share"]["labels"]))
    return (
        '<section class="series-panel state-map-panel" id="state-china-map"><h2>China-born residents, by U.S. state</h2>'
        f'<p class="chart-context">{data["start_year"]}-{data["end_year"]} ACS five-year estimates</p>'
        '<div class="state-map-controls" hidden><div class="state-map-metrics" role="group" aria-label="Map measure">'
        '<button type="button" data-map-metric="share" aria-pressed="true">Share of immigrants</button>'
        '<button type="button" data-map-metric="count" aria-pressed="false">Number of residents</button></div>'
        f'<label for="state-map-select">State<select id="state-map-select"><option value="">Choose a state</option>{options}</select></label></div>'
        '<div class="comparison-chart state-map-chart">' + svg_map(data, paths, "share", interactive=True) +
        '</div><div class="state-map-legend" aria-label="Share of immigrants colour key">' + legend +
        '</div><div class="state-map-readout" aria-live="polite" aria-atomic="true"></div>'
        '<p class="chart-note">China excludes Hong Kong and Taiwan. Percentages are of each state&#8217;s '
        'foreign-born residents, not its total population. Alaska and Hawaii use separate inset scales.</p>'
        '<details class="chart-method"><summary>About these estimates</summary>'
        '<p>These are resident population estimates, not annual arrivals or green-card grants. '
        'Foreign-born means not a U.S. citizen at birth, including naturalized citizens. '
        'The same five-year period is used across all 50 states and D.C.; the estimates do not describe a single year. '
        'Census does not separately identify Macau in this category. Reported count margins of error use 90% confidence; '
        'the derived percentage has no calculated percentage margin of error.</p>'
        f'<p>Source: <a href="{esc(data["sources"]["release"]["url"])}">U.S. Census Bureau, American Community Survey</a>, '
        'table B05006.</p></details>'
        '<details class="state-map-table"><summary>All state estimates</summary><div class="table-scroll"><table>'
        f'<caption>{data["start_year"]}-{data["end_year"]} ACS five-year estimates. China excludes Hong Kong and Taiwan. '
        'Margins of error are plus/minus people at 90% confidence.</caption>'
        '<thead><tr><th>State</th><th>China-born residents</th><th>Share of immigrants</th>'
        '<th>All foreign-born residents</th><th>China-born MOE</th><th>Foreign-born MOE</th></tr></thead>'
        '<tbody>' + "".join(exact) + '</tbody></table></div></details>'
        '<details class="chart-downloads"><summary>Download data &amp; graphics</summary>'
        '<p><a href="downloads/state-immigration.csv" download>All 51 state/DC estimates &middot; CSV</a> &middot; '
        '<a href="downloads/state-immigration.json" download>Complete data &amp; sources &middot; JSON</a> &middot; '
        '<a href="downloads/us-states.geojson" download>State outlines &middot; GeoJSON</a></p>'
        + graphic_links + '</details>'
        '<script type="application/json" class="state-map-data">' + json_text(model).replace("<", "\\u003c") +
        '</script></section>')
