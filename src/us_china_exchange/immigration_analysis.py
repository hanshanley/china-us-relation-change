"""Fiscal-year immigration indicators, separate from travel and visa issuances."""

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .indicator_charts import svg_indicator_chart
from .model import json_text
from .pipeline import write_atomic
from .theme import CHART_THEMES, PARTNER_COLORS
from .immigration_sources import MACAU_ABODE_YEARS, STOCK_PAIRS, STOCK_YEARS


CHARTS = {
    "migrant-stock-to-us": {
        "title": "China- and Hong Kong-born residents in the U.S.", "subtitle": "UN estimates | actual 1 July benchmarks, 2000–2024",
        "series": ["un_stock:CHN:USA", "un_stock:HKG:USA"], "unit": "Estimated residents", "mode": "levels",
        "note": "UN DESA, International Migrant Stock 2024, Table 1 (CC BY 3.0 IGO). Foreign-born resident stocks, not annual arrivals, green-card grants or net migration. Only published benchmark years are shown; no invented annual counts."},
    "migrant-stock-from-us": {
        "title": "U.S. citizens in China; U.S.-born in Hong Kong", "subtitle": "UN estimates | distinct citizenship and birthplace populations",
        "series": ["un_stock:USA:CHN", "un_stock:USA:HKG"], "unit": "Estimated residents", "mode": "levels",
        "note": "UN DESA, International Migrant Stock 2024 (CC BY 3.0 IGO). Mainland China uses U.S. citizenship (C R); Hong Kong uses U.S. birthplace (B R). Stocks on 1 July, not new immigrants, permanent-residency grants or U.S. departures. Do not add the two populations."},
    "green-card-grants": {
        "title": "U.S. green-card grants by birthplace", "subtitle": "Fiscal years 2000–2024 | includes arrivals and adjustments",
        "series": ["ohss_birth:CHN", "ohss_birth:HKG", "ohss_birth:MAC"], "unit": "Status grants", "mode": "levels",
        "note": "DHS/OHSS, country of birth, not nationality. Includes people already in the U.S. adjusting status. Fiscal years end September 30. FY2015–2024 rounded to nearest ten; earlier source vintages use exact counts."},
    "hong-kong-green-cards": {
        "title": "Green-card grants to Hong Kong-born people", "subtitle": "Fiscal years 2000–2024 | U.S. permanent residency",
        "series": ["ohss_birth:HKG"], "unit": "Status grants", "mode": "levels",
        "note": "DHS/OHSS birthplace category. Includes arrivals and adjustments, not just new departures from Hong Kong. FY2015–2024 rounded to nearest ten. No visa or visitor counts substituted."},
    "macau-green-cards": {
        "title": "Green-card grants to Macau-born people", "subtitle": "Fiscal years 2000–2024 | U.S. permanent residency",
        "series": ["ohss_birth:MAC"], "unit": "Status grants", "mode": "levels",
        "note": "DHS/OHSS birthplace category. Includes arrivals and adjustments. FY2015–2024 rounded to nearest ten; confidential/missing values are not zero."},
    "macau-residence-approvals": {
        "title": "Macau residence approvals: U.S. category", "subtitle": "Calendar years 2010-2025 | people newly approved",
        "series": ["dsec_abode:USA:MAC"], "unit": "People approved", "mode": "levels",
        "note": "DSEC annual yearbooks, table 2.10. People in the U.S. country category newly approved for residence "
        "in Macau. Calendar-year approvals, not resident stocks, U.S. departures or U.S. green-card grants. "
        "The source category does not establish citizenship or a permanent-resident legal status."},
    "latest-admissions": {
        "title": "FY2025: arrivals and status adjustments", "subtitle": "DHS China-nationality category | NOT the birthplace series",
        "series": ["ohss_nationality:new_arrivals", "ohss_nationality:adjustments"], "unit": "Status grants", "mode": "bars",
        "note": "DHS/OHSS reports 65,670 total FY2025 China-nationality grants: 27,020 new arrivals and 38,650 adjustments within the U.S. Rounded to nearest ten. Nationality differs from birthplace: do not splice this into the historical line."},
}


def validate_immigration_data(data):
    if set(data) != {"version", "series", "observations", "sources", "coverage", "context"} or data["version"] != 1:
        raise ValueError("Invalid immigration schema")
    expected = {f"ohss_birth:{g}" for g in ("CHN", "HKG", "MAC")} | {
        "ohss_nationality:total", "ohss_nationality:new_arrivals", "ohss_nationality:adjustments"}
    expected |= {f"un_stock:{origin}:{destination}" for origin, destination in STOCK_PAIRS}
    expected.add("dsec_abode:USA:MAC")
    if set(data["series"]) != expected:
        raise ValueError("Immigration populations must remain explicit")
    for sid, definition in data["series"].items():
        if sid == "dsec_abode:USA:MAC":
            if (definition["measure"], definition["unit"], definition["period_basis"], definition["cadence"]) != (
                    "residence_authorizations", "people approved", "calendar", "annual"):
                raise ValueError("Macau approvals must retain their source category and calendar-year basis")
            continue
        if sid.startswith("un_stock:"):
            pair = tuple(sid.split(":")[1:])
            if (definition["measure"], definition["unit"], definition["period_basis"], definition.get("data_type")) != (
                    "migrant_stock", "estimated residents", "mid-year July 1", STOCK_PAIRS[pair]):
                raise ValueError("UN stocks must retain their citizenship/birthplace type and mid-year basis")
            continue
        if definition["measure"] != "permanent_resident_grants" or definition["unit"] != "status grants" or definition["period_basis"] != "fiscal ending year":
            raise ValueError("Immigration must not be relabelled visits, visas or calendar years")
        required = "country of birth" if sid.startswith("ohss_birth") else "nationality"
        if required not in definition["scope"].lower():
            raise ValueError("Birthplace and nationality populations must not be spliced")
    for source_id, source in data["sources"].items():
        if not source["assets"] or not source["locator"] or not source["vintage"]:
            raise ValueError("Immigration source provenance incomplete")
        for asset in source["assets"]:
            if not re.fullmatch("[0-9a-f]{64}", asset["sha256"]) or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
                raise ValueError("Immigration source checksum or retrieval timestamp invalid")
            for field in ("url", "request_url"):
                url = urlsplit(asset[field])
                host = ("www.un.org" if source_id == "un_stock_2024" else
                        "www.dsec.gov.mo" if source_id.startswith("dsec_abode_") else "ohss.dhs.gov")
                if url.scheme != "https" or url.netloc != host:
                    raise ValueError("Immigration values require the reviewed official source")
    seen = set()
    for r in data["observations"]:
        if isinstance(r["year"], bool) or not isinstance(r["year"], int):
            raise ValueError("Invalid fiscal ending year")
        key = r["series_id"], r["year"]
        if key in seen or r["series_id"] not in expected or r["source_id"] not in data["sources"]:
            raise ValueError("Invalid or duplicate immigration observation")
        seen.add(key)
        expected_source = ("un_stock_2024" if r["series_id"].startswith("un_stock:") else
                           f"ohss_birth_{2004 if r['year'] <= 2004 else 2014 if r['year'] <= 2014 else 2024}"
                           if r["series_id"].startswith("ohss_birth") else "ohss_nationality_2025")
        if ((r["series_id"].startswith("dsec_abode:") and not r["source_id"].startswith("dsec_abode_"))
                or (not r["series_id"].startswith("dsec_abode:") and r["source_id"] != expected_source)):
            raise ValueError("Immigration observation population/source mismatch")
        if r["status"] not in {"observed", "rounded", "estimated", "suppressed", "missing"} or (r["value"] is None) != (r["status"] in {"suppressed", "missing"}):
            raise ValueError("Immigration missingness cannot become zero")
        if r["value"] is not None and (isinstance(r["value"], bool) or not isinstance(r["value"], int) or r["value"] < 0):
            raise ValueError("Invalid immigration count")
        if r["status"] == "rounded" and r["value"] % 10:
            raise ValueError("Rounded immigration counts must be multiples of ten")
    for sid in expected:
        years = {year for identity, year in seen if identity == sid}
        if years != (set(MACAU_ABODE_YEARS) if sid.startswith("dsec_abode:") else
                     set(STOCK_YEARS) if sid.startswith("un_stock:") else
                     set(range(2000, 2025)) if sid.startswith("ohss_birth") else {2025}):
            raise ValueError("Reviewed immigration coverage is incomplete or has invented years")
    if not all(data["context"].get(k) for k in ("definition", "periods", "rounding", "rights")):
        raise ValueError("Immigration definitions and limitations required")
    return data


def chart_groups(data, chart_id):
    groups = []
    for sid in CHARTS[chart_id]["series"]:
        rows = sorted((r for r in data["observations"] if r["series_id"] == sid), key=lambda r: r["year"])
        definition = data["series"][sid]
        geo = (definition["origin"] if definition.get("destination") == "USA" else definition.get("destination")) if sid.startswith("un_stock:") else sid.split(":")[-1]
        groups.append({"id": sid, "label": data["series"][sid]["label"],
                       "color": PARTNER_COLORS.get(geo, PARTNER_COLORS["CHN"]),
                       "cadence": definition["cadence"], "scheduled_years": [r["year"] for r in rows],
                       "period_basis": definition["period_basis"],
                       "points": [dict(r, plotted_value=r["value"], reported_unit=definition["unit"], plotted_unit=CHARTS[chart_id]["unit"])
                                  for r in rows if r["value"] is not None]})
    return groups


def build_immigration(root, data, gallery, state_data=None, state_geometry=None):
    from .render import esc, export_figure, figure_links

    validate_immigration_data(data)
    cards, plotted = [], []
    if state_data is not None:
        from .state_immigration_map import build_state_map

        cards.append(build_state_map(root, state_data, state_geometry, gallery))
    for chart_id, config in CHARTS.items():
        groups = chart_groups(data, chart_id)
        stock_chart = chart_id.startswith("migrant-stock")
        basis = groups[0]["period_basis"]
        paths = {theme: export_figure(root, Path("immigration") / theme / chart_id, svg_indicator_chart(
            config, groups, theme, "Resident stocks and status grants have distinct periods and populations; not all physical arrivals.", "immigration-point"))
                 for theme in CHART_THEMES}
        exact = []
        for group in groups:
            for point in group["points"]:
                plotted.append(dict(point, chart_id=chart_id, label=group["label"],
                                    scope=data["series"][group["id"]]["scope"], period_basis=basis,
                                    source_name=data["sources"][point["source_id"]]["name"],
                                    source_vintage=data["sources"][point["source_id"]]["vintage"]))
                period = (f'1 July {point["year"]}' if stock_chart else
                          f'FY{point["year"]}' if basis == "fiscal ending year" else str(point["year"]))
                exact.append(f'<tr><td>{esc(group["label"])}</td><th scope="row">{period}</th>'
                             f'<td>{point["value"]:,}</td><td>{point["status"]}</td></tr>')
        cards.append(f'<section class="series-panel" id="{chart_id}"><h2>{esc(config["title"])}</h2>'
                     f'<div class="comparison-chart"><img src="{paths["themarginoferror"]["png"]}" width="1000" height="600" '
                     f'alt="{esc(config["title"])}" loading="lazy"></div>'
                     f'<p class="chart-note">{esc(config["note"])}</p>{figure_links(paths)}'
                     '<details><summary>Exact reported values</summary><div class="table-scroll"><table>'
                     f'<thead><tr><th>Population</th><th>Period</th><th>{esc(config["unit"])}</th><th>Precision</th></tr></thead>'
                     '<tbody>' + "".join(exact) + '</tbody></table></div></details></section>')
        relative = {theme: {kind: path.removeprefix("figures/") for kind, path in files.items()}
                    for theme, files in paths.items()}
        gallery["immigration"].append(f'<article><h3>{esc(config["title"])}</h3>{figure_links(relative)}</article>')
    write_atomic(root / "site/downloads/immigration.json", json_text(data))
    for name, rows in [("immigration-observations", [dict(r, **{k: v for k, v in data["series"][r["series_id"]].items() if k != "notes"},
                                                      definition_notes=data["series"][r["series_id"]]["notes"],
                                                      fiscal_period_start=f'{r["year"]-1}-10-01' if data["series"][r["series_id"]]["period_basis"] == "fiscal ending year" else "",
                                                      fiscal_period_end=f'{r["year"]}-09-30' if data["series"][r["series_id"]]["period_basis"] == "fiscal ending year" else "",
                                                      calendar_period_start=f'{r["year"]}-01-01' if data["series"][r["series_id"]]["period_basis"] == "calendar" else "",
                                                      calendar_period_end=f'{r["year"]}-12-31' if data["series"][r["series_id"]]["period_basis"] == "calendar" else "",
                                                      observation_date=f'{r["year"]}-07-01' if r["series_id"].startswith("un_stock:") else "",
                                                      source_name=data["sources"][r["source_id"]]["name"],
                                                      source_vintage=data["sources"][r["source_id"]]["vintage"],
                                                      source_locator=data["sources"][r["source_id"]]["locator"],
                                                      source_assets=json_text(data["sources"][r["source_id"]]["assets"]))
                                                   for r in data["observations"]]),
                       ("immigration-chart-values", plotted)]:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=sorted({k for r in rows for k in r}), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        write_atomic(root / "site/downloads" / (name + ".csv"), stream.getvalue())
    coverage = "".join(f'<tr><th>{esc(c["id"])}</th><td>{esc(c["status"])}</td><td>{esc(c["description"])}</td></tr>' for c in data["coverage"])
    sources = "".join(f'<li>{esc(s["name"])} · {esc(s["vintage"])}. {esc(s["locator"])}. {esc(s["notes"])}'
                      + "".join(f'<p><a href="{esc(a["url"])}">Official source</a> · SHA-256 <code>{a["sha256"]}</code> · '
                                f'retrieved {esc(a["retrieved_at"])}</p>' for a in s["assets"]) + '</li>' for s in data["sources"].values())
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Immigration | U.S.–China connections</title><link rel="stylesheet" href="assets/style.css">'
            + ('<link rel="stylesheet" href="assets/state-map.css">' if state_data is not None else '') +
            '</head><body><div class="page">'
            '<header><h1>Immigration</h1><p>Resident stocks, U.S. permanent-resident grants and Macau residence approvals, shown separately.</p>'
            '<p><a href="downloads/immigration.json" download>Complete data and provenance · JSON</a> · '
            '<a href="downloads/immigration-observations.csv" download>All observations · CSV</a> · '
            '<a href="downloads/immigration-chart-values.csv" download>All plotted values · CSV</a></p></header><main>' +
            "".join(cards) + '<section class="series-panel"><h2>Definitions, direction and coverage</h2>' +
            "".join(f'<p>{esc(v)}</p>' for v in data["context"].values()) +
            '<div class="table-scroll"><table><thead><tr><th>Series</th><th>Status</th><th>Scope or gap</th></tr></thead><tbody>' + coverage +
            '</tbody></table></div></section><section class="series-panel"><h2>Primary sources</h2><ul>' + sources +
            '</ul></section></main></div>' +
            ('<script src="assets/state-map.js" defer></script>' if state_data is not None else '') +
            '</body></html>')
    write_atomic(root / "site/immigration.html", html)
    return len(cards)
