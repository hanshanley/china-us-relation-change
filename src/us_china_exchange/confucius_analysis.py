"""Dated program-count graphics with bounds and incompatible populations explicit."""

import csv
import html
import io
import json
import textwrap
from datetime import date
from pathlib import Path

from .confucius_sources import SERIES, reference_date, reported, validate
from .model import json_text
from .pipeline import write_atomic
from .theme import CHART_THEMES, FONT, GRID, MUTED, PARTNER_COLORS, TEXT, linear_axis


CHARTS = {
    "confucius-institutes": {
        "title": "Confucius Institutes: reported U.S. counts",
        "subtitle": "Dated national snapshots | host coverage differs",
        "series": ["institutes_reported"],
        "note": "Different sources, not a harmonized annual census. The June 2023 roster includes non-university hosts and one paused institute. Announced closures are not effective closure dates."},
    "confucius-campus": {
        "title": "Institutes at U.S. colleges and universities",
        "subtitle": "Campus-only counts | bounds remain bounds",
        "series": ["institutes_campus"],
        "note": "Campus-only reports, not the all-host roster. GAO reports fewer than five as of July 2023, not exactly five. The December 2022 figure is approximate. No current total is inferred."},
    "confucius-classrooms": {
        "title": "Confucius Classrooms: historical U.S. reports",
        "subtitle": "Reported programs or school sites | not physical rooms",
        "series": ["classrooms_reported"],
        "note": "National reports use different program/site counting rules. The 2024 inventory and today's directory listings are not appended as active-classroom totals. No decline rate is calculated."},
    "confucius-successors": {
        "title": "Documented replacements after institute closures",
        "subtitle": "Institutions identified by NAS | not a census of programs open now",
        "series": ["successors_documented"],
        "note": "Cumulative source documentation, not an operating stock. Proposed replacements, retained partnerships and transferred institutes are separate, potentially overlapping categories; they are not added to these counts."},
    "confucius-directory": {
        "title": "The operator's U.S. directory",
        "subtitle": "Listed institutes and classroom programs | operation not verified",
        "series": ["institutes_listed", "classrooms_listed"],
        "note": "Complete U.S.-filtered CIEF directory response. Program names identify the categories; the API's website enable field is not operating status. The classroom list is not a national K-12 school census."},
}
SHORT_SOURCES = {
    "mfa_2014": "Foreign Ministry", "nas_2017": "NAS", "nas_2022": "NAS",
    "crs_2022": "CRS", "crs_2023": "CRS", "usc_2021": "USC",
    "nas_roster_2023": "NAS roster", "gao_2019": "GAO", "gao_2023": "GAO",
    "nas_tracker_2023": "NAS", "cief_directory": "CIEF directory",
    "senate_2019": "U.S. Senate",
}


def esc(value):
    return html.escape(str(value), quote=True)


def period_label(reference):
    parsed = reference_date(reference)
    if len(reference) == 4:
        return reference
    if len(reference) == 7:
        return parsed.strftime("%b %Y")
    return f'{parsed.strftime("%b")} {parsed.day}, {parsed.year}'


def chart_rows(data, chart_id):
    rows = [r for r in data["observations"] if r["series_id"] in CHARTS[chart_id]["series"]]
    rows.sort(key=lambda r: (reference_date(r["reference"]), r["id"]))
    output = []
    for row in rows:
        definition, provenance = SERIES[row["series_id"]], data["sources"][row["source_id"]]
        prefix = {"as_of": "", "reported_by": "Reported by ", "retrieved": "Retrieved "}[row["reference_basis"]]
        label = prefix + period_label(row["reference"])
        if chart_id == "confucius-directory":
            label = "Institutes" if definition["category"] == "institutes" else "Classroom programs"
        output.append(dict(row, label=label, reported=reported(row), scope=definition["scope"],
                           measurement=definition["measurement"], unit=definition["unit"],
                           source_name=provenance["name"], source_short=SHORT_SOURCES[row["source_id"]],
                           publisher_url=provenance["publisher_url"], color=PARTNER_COLORS["CHN"]))
    return output


def svg_counts(data, chart_id, theme="themarginoferror"):
    rows, config = chart_rows(data, chart_id), CHARTS[chart_id]
    top, ticks = linear_axis(max((r["value"] if r["value"] is not None else r["bound"] or 0) for r in rows))
    left, right, first, step, bottom = 58, 928, 122, min(67, 352 / max(1, len(rows))), 492
    background = CHART_THEMES[theme]["background"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" role="img" '
        f'data-confucius-chart="{chart_id}" data-axis-max="{top}" aria-label="{esc(config["title"])}" '
        f'style="font-family:{esc(FONT)}">',
        f'<title>{esc(config["title"])}</title><desc>{esc(config["note"])}</desc>',
        f'<rect class="chart-background" width="1000" height="600" fill="{background}"/>',
        f'<text x="42" y="40" font-size="25" font-weight="700" fill="{TEXT}">{esc(config["title"])}</text>',
        f'<text x="42" y="76" font-size="16" fill="{MUTED}">{esc(config["subtitle"])}</text>',
    ]
    for tick in ticks:
        x = left + tick / top * (right - left)
        parts.append(f'<path d="M{x:.2f},107V{bottom}" stroke="{GRID}" stroke-width=".7"/>'
                     f'<text x="{x:.2f}" y="{bottom + 20}" text-anchor="middle" font-size="13" fill="{MUTED}">{tick:g}</text>')
    for i, row in enumerate(rows):
        y = first + i * step
        amount = row["value"] if row["value"] is not None else row["bound"]
        x = left + (amount or 0) / top * (right - left)
        title = f'{row["label"]}: {row["reported"]} {row["unit"]}. {row["source_name"]}. {row["notes"]}'
        parts.append(f'<g class="confucius-mark" data-observation-id="{row["id"]}" '
                     f'data-value="{row["value"] if row["value"] is not None else ""}" '
                     f'data-bound="{row["bound"] if row["bound"] is not None else ""}" '
                     f'data-qualifier="{row["qualifier"]}" data-reference="{row["reference"]}">'
                     f'<title>{esc(title)}</title>'
                     f'<text x="{left}" y="{y:.2f}" font-size="14" fill="{TEXT}">{esc(row["label"])}'
                     f' &#183; {esc(row["source_short"])}</text>'
                     f'<text class="confucius-reported" x="{right}" y="{y:.2f}" text-anchor="end" '
                     f'font-size="16" font-weight="700" fill="{TEXT}">{esc(row["reported"])}</text>')
        if row["qualifier"] in {"exact", "approximate"}:
            parts.append(f'<rect class="confucius-bar" x="{left}" y="{y + 10:.2f}" width="{x - left:.2f}" '
                         f'height="11" fill="{row["color"]}" opacity="{.6 if row["qualifier"] == "approximate" else 1}"/>')
        elif row["qualifier"] in {"less_than", "at_least"}:
            start, stop = (left, x) if row["qualifier"] == "less_than" else (x, right)
            parts.append(f'<path class="confucius-bound" d="M{start:.2f},{y + 15:.2f}H{stop:.2f}" '
                         f'stroke="{row["color"]}" fill="none" stroke-width="2" stroke-dasharray="4 4"/>'
                         f'<circle class="confucius-boundary" cx="{x:.2f}" cy="{y + 15:.2f}" r="4" '
                         f'fill="{background}" stroke="{row["color"]}" stroke-width="2"/>')
        parts.append('</g>')
    note = "Sources: " + ", ".join(sorted({r["source_short"] for r in rows})) + ". " + config["note"]
    for i, line in enumerate(textwrap.wrap(note, width=117)):
        parts.append(f'<text class="confucius-source" x="42" y="{542 + 17 * i}" font-size="12" fill="{MUTED}">{esc(line)}</text>')
    return "".join(parts) + "</svg>"


def table(data, rows):
    body = []
    for row in rows:
        definition, source = SERIES[row["series_id"]], data["sources"][row["source_id"]]
        body.append(f'<tr data-confucius-row="{esc(row["id"])}"><th scope="row">{esc(row["reference"])}</th>'
                    f'<td>{esc(reported(row))}</td><td>{esc(definition["measurement"].replace("_", " "))}</td>'
                    f'<td>{esc(definition["unit"])}</td><td><a href="{esc(source["publisher_url"])}">'
                    f'{esc(source["name"])}</a></td><td>{esc(row["notes"])}</td></tr>')
    return ('<div class="table-scroll"><table><thead><tr><th>Reference</th><th>Reported count</th>'
            '<th>What is counted</th><th>Unit</th><th>Source</th><th>Scope</th></tr></thead><tbody>' +
            "".join(body) + '</tbody></table></div>')


def export_data(root, data):
    write_atomic(root / "site/downloads/confucius-programs.json", json_text(data))
    observations = []
    for row in data["observations"]:
        definition, source = SERIES[row["series_id"]], data["sources"][row["source_id"]]
        observations.append(dict(row, **definition, reported=reported(row), source_name=source["name"],
                                 source_published_on=source["published_on"], source_url=source["publisher_url"],
                                 evidence_kind=source["evidence_kind"], source_assets=json_text(source["assets"])))
    for name, records in (("confucius-observations", observations), ("confucius-records", data["records"])):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=sorted({k for r in records for k in r}), lineterminator="\n")
        writer.writeheader()
        for row in records:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})
        write_atomic(root / "site/downloads" / (name + ".csv"), stream.getvalue())


def build_confucius(root, data, gallery):
    from .render import export_figure, figure_links

    validate(data)
    root = Path(root)
    export_data(root, data)
    figures = {}
    for chart_id, config in CHARTS.items():
        paths = {theme: export_figure(root, Path("language_learning") / theme / chart_id,
                                     svg_counts(data, chart_id, theme)) for theme in CHART_THEMES}
        figures[chart_id] = paths
        relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                    for theme, files in paths.items()}
        gallery["language_learning"].append(f'<article><h3>{esc(config["title"])}</h3>{figure_links(relative)}</article>')

    def graphic(chart_id):
        points = chart_rows(data, chart_id)
        maximum, ticks = linear_axis(max((r["value"] if r["value"] is not None else r["bound"] or 0) for r in points))
        model = {"id": chart_id, "rows": points, "maximum": maximum, "ticks": ticks, "note": CHARTS[chart_id]["note"],
                 "title": CHARTS[chart_id]["title"]}
        return (f'<div class="comparison-chart confucius-chart" data-confucius-chart="{chart_id}">' +
                svg_counts(data, chart_id) +
                '<script type="application/json" class="confucius-plot-data">' +
                json_text(model).replace("<", "\\u003c") + '</script></div>'
                '<details class="chart-downloads"><summary>Download PNG / SVG</summary>' +
                figure_links(figures[chart_id]) + '</details>')

    index = {r["id"]: r for r in data["observations"]}
    directory_date = period_label(index["cief_institutes"]["reference"])
    def summary(category):
        definitions = {
            "institutes": [
                ("cief_institutes", "Latest operator listing", "Directory entries; operation not verified"),
                ("gao_campus_2023", "Latest verified campus report", "Operating university institutes, GAO")],
            "classrooms": [
                ("cief_classrooms", "Latest operator listing", "Program listings; not a national K-12 census"),
                ("senate_classrooms_2019", "Last national school-site report", "Reported classroom sites, U.S. Senate")],
            "successors": [
                ("nas_successors_2023", "Latest documented replacement count", "Institutions reported by NAS; not programs verified open now")],
        }
        cards = []
        for identity, label, detail in definitions[category]:
            row = index[identity]
            cards.append(f'<div><p class="label">{label}</p><p class="metric">{esc(reported(row))}</p>'
                         f'<p class="confucius-summary-date">{esc(period_label(row["reference"]))}</p>'
                         f'<p class="confucius-summary-note">{esc(detail)}</p></div>')
        return '<div class="confucius-summary">' + "".join(cards) + '</div>'
    panels = []
    for category, title, chart_id, note in (
            ("institutes", "Confucius Institutes", "confucius-institutes",
             "Reports counted different kinds of hosts. The campus-only figures are shown separately below; a paused institute is not silently treated as operating."),
            ("classrooms", "K-12 Confucius Classrooms", "confucius-classrooms",
             "Historical national reports are shown here. NAS documented 164 school or school-system cases in July 2024, including former programs; that is not 164 active classrooms. The current operating total is unknown."),
            ("successors", "Successor & rebranded programs", "confucius-successors",
             "NAS reported 28 institutions with replacement programs in June 2022 and at least 28 in June 2023. These are cumulative documented cases, not a count still operating now. Twelve proposed replacements and 58 retained partnerships in the 2022 report are different, overlapping categories.")):
        category_rows = [r for r in data["observations"] if SERIES[r["series_id"]]["category"] == category]
        extra = ('<details class="confucius-campus"><summary>College and university campuses only</summary>' +
                 graphic("confucius-campus") + '</details>') if category == "institutes" else ""
        panels.append(f'<section class="series-panel" id="confucius-{category}"><h2>{title}</h2>'
                      f'<p class="chart-context">{esc(CHARTS[chart_id]["subtitle"])}</p>'
                      + summary(category) + graphic(chart_id) + f'<p class="chart-note">{esc(note)}</p>' + extra +
                      '<details><summary>All reported values &amp; definitions</summary>' +
                      table(data, category_rows) + '</details></section>')
    listing_rows = [r for r in data["records"] if r["source_id"] == "cief_directory"]
    listing_table = "".join(
        f'<tr data-directory-id="{r["id"]}"><th scope="row"><a href="{esc(r["url"])}">{esc(r["institution"])}</a>'
        f'</th><td>{"Institute" if r["category"] == "institutes" else "Classroom program"}</td>'
        '<td>Not verified</td></tr>' for r in listing_rows)
    source_list = "".join(f'<li><a href="{esc(s["publisher_url"])}">{esc(s["name"])}</a>'
                          f' ({esc(s["published_on"] or directory_date)}). {esc(s["locator"])}</li>'
                          for s in data["sources"].values())
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Confucius Institutes &amp; Classrooms</title><link rel="stylesheet" href="assets/style.css">'
        '<link rel="stylesheet" href="assets/confucius.css"></head><body><div class="page">'
        '<header><h1>Confucius Institutes &amp; Classrooms</h1><p>U.S. institutes, school programs and documented replacements, counted separately.</p></header><main>'
        + "".join(panels) +
        '<details class="confucius-directory"><summary>Explore the operator&#8217;s directory</summary>'
        f'<p>U.S. directory retrieved {esc(directory_date)}. Every returned entry is included below and in the download. '
        'Listing is not proof that a program remains open. The source includes a university-named classroom entry; '
        'these seven names cannot be read as a K-12 school census.</p>' + graphic("confucius-directory") +
        '<div class="table-scroll"><table><thead><tr><th>Listed program</th><th>Source label</th>'
        '<th>Operating status</th></tr></thead><tbody>' + listing_table + '</tbody></table></div></details>'
        '<details class="confucius-method"><summary>Definitions &amp; sources</summary>'
        '<p>Snapshots retain their original reference dates, including year-only and month-only observations. '
        'A report upload, webpage modification or retrieval in a later year does not make an old count current. '
        'No annual observations or national operating totals are inferred from partial inventories.</p>'
        '<p>Successor counts retain NAS attribution and its broader definition of replacement. A proposal, a continuing '
        'partner relationship and a host transfer are not automatically completed rebrands. The supporting workbook '
        'has 29 R-coded rows, including prospective or ambiguous descriptions; these flags are retained, not substituted '
        'for a current operating total. Schools and districts are not interchangeable counting units.</p>'
        '<p>GAO selected facts use an explicitly identified, versioned transcription; its checksum is not a checksum of '
        'the publisher PDF. Other numerical inputs retain publisher-response checksums. Only factual aggregates and '
        'selected factual record fields are redistributed, not report text or artwork.</p><ul>' + source_list + '</ul></details>'
        '<details class="confucius-downloads"><summary>Download all data</summary>'
        '<p><a href="downloads/confucius-programs.json" download>Complete observations, records &amp; sources · JSON</a></p>'
        '<p><a href="downloads/confucius-observations.csv" download>All observations &amp; definitions · CSV</a> · '
        '<a href="downloads/confucius-records.csv" download>All selected institution &amp; directory records · CSV</a></p>'
        '</details></main></div><script src="assets/confucius.js" defer></script></body></html>')
    write_atomic(root / "site/confucius.html", document)
    for name in ("confucius.js", "confucius.css"):
        write_atomic(root / "site/assets" / name, (Path(__file__).parent / "static" / name).read_text())
    return len(figures)
