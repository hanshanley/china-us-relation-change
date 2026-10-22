"""Domestic language-learning indicators, kept separate from bilateral flows."""

import html
import math
import re
import textwrap
from datetime import datetime
from urllib.parse import urlsplit

from .theme import CHART_THEMES, FONT, GRID, MUTED, PARTNER_COLORS, TEXT


LANGUAGE_COLORS = {"chinese": PARTNER_COLORS["CHN"], "japanese": "#3D6F8C",
                   "korean": "#4A7C59", "all_languages": "#6B6B6B", "spanish": "#C2993E"}
CHARTS = {
    "college-enrollments": {
        "title": "Chinese/Mandarin course enrollments",
        "subtitle": "U.S. colleges and universities | fall census rounds",
        "series": ["mla:chinese"], "unit": "Course registrations", "mode": "levels",
        "note": "MLA 2021-report vintage. Registrations, not unique learners. Lines join census rounds, not annual estimates. Commercial reuse permission unverified."},
    "college-share": {
        "title": "Chinese/Mandarin's share of language study",
        "subtitle": "Share of all non-English language course registrations",
        "series": ["mla:chinese"], "denominator": "mla:all_languages", "unit": "Percent", "mode": "share",
        "note": "Calculated from the same MLA report vintage and census rounds; denominator includes ASL and classical languages. Not a share of all college students."},
    "college-benchmarks": {
        "title": "Language study in context",
        "subtitle": "U.S. college course enrollments | 2013 = 100",
        "series": ["mla:chinese", "mla:japanese", "mla:korean", "mla:all_languages"],
        "unit": "2013 = 100", "mode": "index", "baseline": 2013,
        "note": "Each language uses its own 2013 baseline. MLA 2021-report vintage, not annual estimates. Population totals vary across census rounds; this is not a causal estimate."},
    "matched-college-benchmarks": {
        "title": "The same responding institutions",
        "subtitle": "Matched 2013/2021 respondents | 2013 = 100",
        "series": ["mla_matched:chinese", "mla_matched:japanese", "mla_matched:korean",
                   "mla_matched:all_languages"], "unit": "2013 = 100", "mode": "index", "baseline": 2013,
        "note": "Same institution IDs with complete reported language-count rows in both rounds; nonresponse excluded, explicit zero-language respondents retained. Selected cohort, not a national total or a causal estimate."},
    "ap-chinese-global": {
        "title": "AP Chinese exam participation",
        "subtitle": "Global reports, including international participation - NOT U.S.-only",
        "series": ["ap:global_total", "ap:standard_group"], "unit": "Exam participants", "mode": "levels",
        "note": "College Board global reports. Standard group is a subset based on language exposure/training, not U.S. location or ancestry. Never add the two series; neither measures all learners."},
    "ap-chinese-us-cohorts": {
        "title": "AP Chinese in U.S. public-school cohorts",
        "subtitle": "Graduating classes 2007-2013 | exams taken during high school",
        "series": ["ap_cohort:us_public"], "unit": "Exams", "mode": "levels",
        "note": "College Board Report to the Nation. Year is graduating class, not exam administration. Public schools only; not all U.S. schools or unique learners. Historical cohorts are not spliced into global annual totals."},
    "chinese-bachelors": {
        "title": "Chinese-language bachelor's awards",
        "subtitle": "IPEDS | first major CIP 16.0301 | academic year ending",
        "series": ["ipeds:bachelors"], "unit": "Awards", "mode": "levels",
        "note": "NCES IPEDS; 50 states and DC, Title IV degree-granting institutions. From 2001, first-major only; 2000 lacks a separate major-number field. Awards are not unique people or all China specialists."},
    "chinese-graduate-awards": {
        "title": "Chinese-language graduate awards",
        "subtitle": "IPEDS | first major CIP 16.0301 | academic year ending",
        "series": ["ipeds:masters", "ipeds:doctorates"], "unit": "Awards", "mode": "levels",
        "note": "NCES IPEDS; reported/imputed awards, not unique people. Major coding changes in 2001; doctoral definition changes in 2010 from old category to research/scholarship doctorates. Lines break at those boundaries."},
    "school-program-inventories": {
        "title": "Mandarin immersion program inventories",
        "subtitle": "Different coverage definitions - not a comparable growth series",
        "series": ["schools:cal_directory", "schools:arc_public", "schools:nexus_all"], "unit": "Programs", "mode": "bars",
        "note": "CAL: immersion directory. ARC: public-school DLI canvass. Nexus: compiled inventory including private schools. Different universes and methods; no growth rate or connecting trend is calculated."},
}


def validate_language_data(data):
    if set(data) != {"version", "series", "observations", "sources", "coverage", "context"} or data["version"] != 1:
        raise ValueError("Unexpected language-learning dataset schema")
    definitions, sources = data["series"], data["sources"]
    if not isinstance(definitions, dict) or not isinstance(sources, dict) or not definitions or not sources:
        raise ValueError("Language-learning definitions and provenance are required")
    if not isinstance(data["observations"], list) or not isinstance(data["coverage"], list) or not isinstance(data["context"], dict):
        raise ValueError("Language-learning observations, coverage and context have invalid types")
    series_fields = {"label", "measure", "unit", "scope", "cadence", "period_basis", "notes"}
    for sid, definition in definitions.items():
        if not re.fullmatch(r"[a-z0-9_:]+", sid) or set(definition) != series_fields:
            raise ValueError("Invalid language-learning series definition")
        if not all(isinstance(v, str) for v in definition.values()) or not all(
                definition[k] for k in series_fields - {"notes"}):
            raise ValueError("Language-learning populations and units must be explicit")
    for item in sources.values():
        if set(item) != {"name", "vintage", "assets", "locator", "notes"} or not item["assets"]:
            raise ValueError("Invalid language-source provenance")
        if not all(isinstance(item[k], str) and item[k] for k in ("name", "vintage", "locator")):
            raise ValueError("Language-source identity and table locator are required")
        for asset in item["assets"]:
            if set(asset) != {"url", "request_url", "sha256", "retrieved_at"}:
                raise ValueError("Invalid language-source asset fields")
            if not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
                raise ValueError("Invalid language-source checksum")
            for field in ("url", "request_url"):
                parsed = urlsplit(asset[field])
                if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username:
                    raise ValueError("Invalid public language-source URL")
            if datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
                raise ValueError("Language-source dates need timezones")
    seen = set()
    fields = {"series_id", "year", "value", "source_id", "status", "notes", "comparability"}
    for r in data["observations"]:
        if set(r) != fields or r["series_id"] not in definitions or r["source_id"] not in sources:
            raise ValueError("Language observation has incomplete definitions or provenance")
        if isinstance(r["year"], bool) or not isinstance(r["year"], int) or not 2000 <= r["year"] <= 9999:
            raise ValueError("Invalid language observation year")
        key = r["series_id"], r["year"]
        if key in seen:
            raise ValueError("Duplicate language observation")
        seen.add(key)
        if r["status"] not in {"observed", "estimated", "reported_or_imputed", "missing"}:
            raise ValueError("Invalid language observation status")
        if (r["value"] is None) != (r["status"] == "missing"):
            raise ValueError("Language observation missingness disagrees with status")
        if r["value"] is not None and (isinstance(r["value"], bool) or not isinstance(r["value"], int)
                                       or r["value"] < 0):
            raise ValueError("Language indicators require nonnegative integer counts")
        if not isinstance(r["comparability"], str) or not r["comparability"]:
            raise ValueError("Missing language comparability definition")
        if not isinstance(r["notes"], str):
            raise ValueError("Language observation notes must be text")
        if r["series_id"].startswith("ap:") and "global" not in definitions[r["series_id"]]["scope"].lower():
            raise ValueError("Global AP data must not be relabelled U.S.-only")
        if r["series_id"].startswith("ap_cohort:") and (
                "U.S. public-school graduating" not in definitions[r["series_id"]]["scope"]
                or definitions[r["series_id"]]["period_basis"] != "graduating class"):
            raise ValueError("AP U.S. public-school cohorts must retain their graduating-class population")
    by_key = {(r["series_id"], r["year"]): r for r in data["observations"]}
    for r in data["observations"]:
        if r["series_id"] == "ap:standard_group" and r["value"] is not None:
            total = by_key.get(("ap:global_total", r["year"]))
            if total is None or total["value"] is None or r["value"] > total["value"]:
                raise ValueError("AP standard-group subset does not reconcile")
        if r["series_id"] == "mla:chinese" and r["value"] is not None:
            total = by_key.get(("mla:all_languages", r["year"]))
            if total is None or total["value"] is None or r["value"] > total["value"]:
                raise ValueError("MLA language share does not reconcile")
    coverage_ids = set()
    for item in data["coverage"]:
        if set(item) != {"id", "status", "description"} or not all(isinstance(v, str) and v for v in item.values()):
            raise ValueError("Invalid language coverage record")
        if item["id"] in coverage_ids:
            raise ValueError("Duplicate language coverage identity")
        coverage_ids.add(item["id"])
    context = data["context"]
    if not all(context.get(k) for k in ("question", "rights", "economist", "nexus_response_scope")):
        raise ValueError("Language context and interpretation caveats are required")
    economist, nexus = context["economist"], context["nexus_response_scope"]
    if economist.get("snapshot_source_id") not in sources:
        raise ValueError("MLA snapshot context lacks primary-source provenance")
    for key in ("program_responses", "us_program_responses", "hong_kong_program_responses",
                "response_associated_enrollments"):
        if isinstance(nexus.get(key), bool) or not isinstance(nexus.get(key), int) or nexus[key] < 0:
            raise ValueError("Invalid Nexus respondent count")
    if nexus["us_program_responses"] + nexus["hong_kong_program_responses"] != nexus["program_responses"]:
        raise ValueError("Nexus response geographies do not reconcile")
    for chart_id in CHARTS:
        chart_points(data, chart_id)
    return data


def chart_points(data, chart_id):
    config = CHARTS[chart_id]
    rows = data["observations"]
    grouped = []
    for index, sid in enumerate(config["series"]):
        if sid not in data["series"]:
            continue
        selected = sorted((r for r in rows if r["series_id"] == sid), key=lambda r: r["year"])
        present = [r for r in selected if r["value"] is not None]
        expected_unit = "course registrations" if config["mode"] in {"index", "share"} else config["unit"].lower()
        if data["series"][sid]["unit"].lower() != expected_unit:
            raise ValueError("Language chart units do not match the observation population")
        population_fields = ("scope", "period_basis", "cadence")
        if config["mode"] == "index" and len({
                tuple(data["series"][s][k] for k in population_fields)
                for s in config["series"] if s in data["series"]}) > 1:
            raise ValueError("Language benchmark populations do not match")
        if config["mode"] == "share" and config["denominator"] in data["series"] and any(
                data["series"][sid][k] != data["series"][config["denominator"]][k]
                for k in ("unit",) + population_fields):
            raise ValueError("Language share populations do not match")
        ref = next((r for r in present if r["year"] == config.get("baseline")), None)
        denominators = {r["year"]: r for r in rows if r["series_id"] == config.get("denominator")}
        points = []
        for r in present:
            value = r["value"]
            denominator = None
            if config["mode"] == "index":
                if ref is None or not ref["value"] or ref["comparability"] != r["comparability"]:
                    continue
                denominator = ref["value"]
                value = value / denominator * 100
            elif config["mode"] == "share":
                other = denominators.get(r["year"])
                if other is None or not other["value"] or other["source_id"] != r["source_id"]:
                    continue
                denominator = other["value"]
                value = value / denominator * 100
            if not math.isfinite(value):
                raise ValueError("Nonfinite plotted language value")
            points.append(dict(r, plotted_value=value, denominator=denominator,
                               reported_unit=data["series"][sid]["unit"], plotted_unit=config["unit"]))
        language = sid.split(":")[-1]
        color = LANGUAGE_COLORS.get(language, ["#7B2D26", "#3D6F8C", "#C2993E"][index % 3])
        grouped.append({"id": sid, "label": data["series"][sid]["label"], "color": color,
                        "points": points, "scheduled_years": [r["year"] for r in selected],
                        "cadence": data["series"][sid]["cadence"]})
    return grouped


def svg_language_chart(data, chart_id, theme="themarginoferror"):
    config = CHARTS[chart_id]
    groups = chart_points(data, chart_id)
    points = [r for group in groups for r in group["points"]]
    if not points:
        return None
    esc = lambda value: html.escape(str(value), quote=True)
    maximum = max(r["plotted_value"] for r in points) * 1.15 or 1
    magnitude = 10 ** math.floor(math.log10(maximum))
    maximum = math.ceil(maximum / magnitude) * magnitude
    bars = config["mode"] == "bars"
    first = 2000 if not bars else min(r["year"] for r in points)
    last = max(first + 1, max(r["year"] for r in points))
    x = lambda year: 115 + (year - first) / (last - first) * 835
    y = lambda value: 420 - value / maximum * 250
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" role="img" '
        f'aria-label="{esc(config["title"])}"><title>{esc(config["title"])}</title>',
        '<desc>Distinct educational indicators, not border crossings or a count of all learners. Exact observations and provenance accompany this figure.</desc>',
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
        value = maximum * fraction
        label = f"{value:.1f}%" if config["mode"] == "share" else f"{value:,.0f}"
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity=".6" stroke-width=".5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{esc(label)}</text>')
    parts.append(f'<path d="M115 170V420H950" stroke="{GRID}" stroke-width=".8" fill="none"/>')
    if bars:
        for i, group in enumerate(groups):
            if len(group["points"]) != 1:
                raise ValueError("Program inventory bars require separate single-snapshot series")
            r = group["points"][0]
            pos = 115 + (i + .5) / len(groups) * 835
            height = 420 - y(r["plotted_value"])
            parts.append(
                f'<rect class="language-point" data-series-id="{esc(group["id"])}" data-year="{r["year"]}" '
                f'data-value="{r["plotted_value"]}" x="{pos - 65:.2f}" y="{y(r["plotted_value"]):.2f}" '
                f'width="130" height="{height:.2f}" fill="{group["color"]}"/>'
                f'<text x="{pos:.2f}" y="{y(r["plotted_value"]) - 12:.2f}" text-anchor="middle" fill="{TEXT}">{r["value"]:,}</text>'
                f'<text x="{pos:.2f}" y="450" text-anchor="middle">{r["year"]}</text>'
                f'<text x="{pos:.2f}" y="478" text-anchor="middle" font-size="18">{esc(group["label"])}</text>')
    else:
        for year in [year for year in range(first, last, 5) if last - year >= 2] + [last]:
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
                parts.append(f'<circle class="language-point" data-series-id="{esc(group["id"])}" '
                             f'data-year="{r["year"]}" data-value="{r["plotted_value"]}" '
                             f'cx="{x(r["year"]):.2f}" cy="{y(r["plotted_value"]):.2f}" r="4" fill="{group["color"]}">'
                             f'<title>{esc(group["label"])} {r["year"]}: {r["plotted_value"]:,.4f} {esc(config["unit"])}</title></circle>')
    note = config["note"]
    if any(r["source_id"].startswith("mla") for r in points) and "permission" not in note:
        note += " MLA commercial reuse permission unverified."
    for i, text in enumerate(textwrap.wrap(note, width=106)):
        parts.append(f'<text class="figure-source" x="115" y="{520 + i * 20}" font-size="14" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)
