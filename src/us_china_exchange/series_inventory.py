"""Audit measured coverage without turning research targets into release dates."""

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup


DATASETS = (
    "exchange", "immigration", "opinions", "language-learning", "business-presence",
    "business-current", "confucius-programs", "student-estimates",
)


def _reported(row):
    value = row.get("value")
    if value is None:
        value = row.get("bound")
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _year(row):
    value = row.get("year")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    for field in ("reference", "field_end", "period_end"):
        value = row.get(field, "")
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    raise ValueError("Observation has no explicit measurement year")


def _period(row):
    return str(row.get("period") or row.get("reference") or _year(row))


def _latest(values):
    values = sorted({str(v) for v in values if v})
    if not values:
        return None
    parsed = [(datetime.fromisoformat(v.replace("Z", "+00:00")), v) for v in values]
    if all(date.tzinfo for date, value in parsed):
        return max(parsed)[1]
    if any(date.tzinfo for date, value in parsed):
        raise ValueError("Source check mixes timezone-aware and unzoned timestamps")
    return max(parsed)[1]


def _relationship(definition, rows):
    sample = rows[0]
    origin = sample.get("origin", definition.get("origin"))
    destination = sample.get("destination", definition.get("destination"))
    if origin and destination:
        return f"{origin} -> {destination}"
    if definition.get("respondent_country") and definition.get("target_country"):
        return f'{definition["respondent_country"]} respondents about {definition["target_country"]}'
    return " | ".join(str(definition[k]) for k in ("label", "scope") if definition.get(k))


def _gaps(rows, cadence):
    reported = [r for r in rows if _reported(r)]
    if not reported or cadence not in {"annual", "monthly", "ytd"}:
        return None
    if cadence == "monthly":
        periods = {_period(r) for r in reported}
        if any(len(p) != 7 or p[4] != "-" or not p[:4].isdigit()
               or not p[5:].isdigit() or not 1 <= int(p[5:]) <= 12 for p in periods):
            raise ValueError("Monthly observation needs an explicit YYYY-MM period")
        ordinals = {int(p[:4]) * 12 + int(p[5:]) - 1 for p in periods}
        return [f"{n // 12:04d}-{n % 12 + 1:02d}"
                for n in range(min(ordinals), max(ordinals) + 1) if n not in ordinals]
    years = {_year(r) for r in reported}
    return [str(y) for y in range(min(years), max(years) + 1) if y not in years]


def _source_details(rows, sources):
    urls, retrievals, checks, vintages = set(), [], [], set()
    for row in rows:
        source = sources.get(row.get("source_id"), {})
        assets = source.get("assets", []) + ([source["asset"]] if source.get("asset") else [])
        urls.update(a["url"] for a in assets if a.get("url"))
        if row.get("source_url"):
            urls.add(row["source_url"])
        retrievals.extend([row.get("retrieved_at"), source.get("last_successful_retrieval")])
        retrievals.extend(a.get("retrieved_at") for a in assets)
        checks.extend([source.get("last_recorded_check"), source.get("checked_at")])
        if row.get("source_vintage"):
            vintages.add(row["source_vintage"])
    return {
        "source_urls": sorted(urls), "source_vintages": sorted(vintages),
        "latest_successful_retrieval": _latest(retrievals),
        "latest_recorded_source_check": _latest(checks),
    }


def _matching_model_points(rows, cadence, points):
    result = []
    for point in points:
        candidates = [r for r in rows if _reported(r)] if _reported(point) else rows
        periods = {_period(r) for r in candidates}
        years = {_year(r) for r in candidates}
        period = _period(point)
        monthly = len(period) == 7 and period[4:5] == "-" and period[5:].isdigit()
        if period in periods or (cadence not in {"monthly", "ytd"} and not monthly and _year(point) in years):
            result.append(point)
    return result


def inventory_series(dataset, data, uses, target_year, model_points=None):
    grouped = defaultdict(list)
    for row in data.get("observations", []):
        sid = row.get("series_id")
        if not sid:
            raise ValueError(f"{dataset}: observation lacks a series identity")
        definition = data.get("series", {}).get(sid, {})
        cadence = row.get("frequency") or definition.get("cadence") or "dated_observations"
        basis = row.get("period_basis") or definition.get("period_basis", "")
        month = ""
        if cadence == "ytd":
            end = row.get("period_end", "")
            if not end or len(end) != 10:
                raise ValueError("YTD observation lacks an explicit ending month")
            month = end[5:7]
        grouped[sid, cadence, basis, month].append(row)
    result = []
    for (sid, cadence, basis, month), rows in sorted(grouped.items()):
        definition = data.get("series", {}).get(sid, {})
        measured = sorted((r for r in rows if _reported(r)), key=lambda r: (_year(r), _period(r)))
        years = sorted({_year(r) for r in measured})
        matching = (_matching_model_points(rows, cadence, model_points.get(sid, []))
                    if model_points is not None else None)
        blocks = defaultdict(list)
        for row in measured:
            blocks[row.get("comparability", ""), row.get("unit", definition.get("unit", ""))].append(row)
        result.append({
            "dataset": dataset, "series_id": sid, "cadence": cadence, "period_basis": basis,
            "matching_ytd_end_month": month, "label": definition.get("label", sid),
            "relationship": _relationship(definition, rows),
            "definitions": sorted({r["definition"] for r in rows if r.get("definition")}),
            "series_definition": definition, "observation_rows": len(rows),
            "reported_or_bounded_rows": len(measured),
            "first_period": _period(measured[0]) if measured else None,
            "latest_period": _period(measured[-1]) if measured else None,
            "first_year": years[0] if years else None,
            "latest_year": years[-1] if years else None,
            "reported_years": years, "internal_missing_periods": _gaps(rows, cadence),
            "unreported_records": [
                {"period": _period(r), "status": r.get("status", r.get("qualifier", ""))}
                for r in rows if not _reported(r)],
            "value_qualifiers": sorted({r["qualifier"] for r in rows if r.get("qualifier")}),
            "fieldwork_periods": [
                {"survey_id": survey_id, **data.get("surveys", {}).get(survey_id, {})}
                for survey_id in sorted({r["survey_id"] for r in rows if r.get("survey_id")})],
            "target_start_year": 2000, "target_end_year": target_year,
            "target_start_covered": bool(years and years[0] <= 2000),
            "uncovered_target_tail_years": list(range(years[-1] + 1, target_year + 1)) if years else [],
            "comparison_blocks": [
                {"comparability": c, "unit": unit, "first_year": min(_year(r) for r in points),
                 "latest_year": max(_year(r) for r in points), "reported_rows": len(points)}
                for (c, unit), points in sorted(blocks.items())],
            "rendered_on_pages": sorted({p["page"] for p in matching}) if matching is not None else sorted(uses.get(sid, [])),
            "embedded_model_periods": sorted({_period(p) for p in matching}) if matching is not None else None,
            **_source_details(rows, data.get("sources", {})),
        })
    return result


def inventory_publication(site, target_year):
    site = Path(site)
    uses = defaultdict(set)
    model_points = defaultdict(list)
    for path in sorted(site.glob("*.html")):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        for node in soup.select('script[type="application/json"]'):
            model = json.loads(node.string or node.get_text())
            if not isinstance(model, dict):
                continue
            if model.get("kind"):
                for group in model.get("groups", []):
                    uses[group["id"]].add(path.name)
                    model_points[group["id"]].extend(dict(p, page=path.name) for p in group.get("points", []))
                for point in model.get("bars", []) + model.get("unavailable_bars", []):
                    uses[point["id"]].add(path.name)
                    model_points[point["id"]].append(dict(point, page=path.name))
            if model.get("layout"):
                for row in model.get("rows", []):
                    if row.get("series_id"):
                        uses[row["series_id"]].add(path.name)
                        model_points[row["series_id"]].append(dict(row, page=path.name))
    series, datasets, non_series = [], [], []
    for name in DATASETS:
        path = site / "downloads" / (name + ".json")
        if not path.is_file():
            continue
        data = json.loads(path.read_text())
        if name == "student-estimates":
            non_series.append({
                "dataset": name, "component": "dated mainland student statements",
                "definition": data["comparability"], "scope": data["scope"],
                "statement_records": data["observations"],
                "source_provenance": _source_details(data["observations"], data["sources"]),
                "note": "Statement dates are not invented measurement periods or annual enrollment observations."})
            continue
        if isinstance(data, dict) and data.get("observations"):
            series.extend(inventory_series(name, data, uses, target_year, model_points))
            datasets.append(name)
    if not series:
        raise ValueError("No complete observation datasets found in publication")
    unmapped = sorted(set(uses) - {r["series_id"] for r in series})
    if unmapped:
        raise ValueError("Rendered series missing from complete downloads: " + ", ".join(unmapped))
    covered = defaultdict(set)
    for row in series:
        covered[row["series_id"]].update(row["embedded_model_periods"] or [])
    unmatched = {sid: sorted({_period(p) for p in points} - covered[sid])
                 for sid, points in model_points.items()
                 if {_period(p) for p in points} - covered[sid]}
    if unmatched:
        raise ValueError("Rendered measurement periods missing from reported data: " + json.dumps(unmatched, sort_keys=True))
    map_path = site / "downloads/state-immigration.json"
    if (site / "immigration.html").is_file() and map_path.is_file():
        data = json.loads(map_path.read_text())
        non_series.append({
            "page": "immigration.html", "component": "state resident map",
            "cadence": "multi-year period estimate", "metrics": ["china_born", "share_percent"],
            "measurement_period": f'{data["start_year"]}-{data["end_year"]}',
            "geography_records": len(data["states"]), "population": data["population"],
            "universe": data["universe"], "definition": data["notes"],
            "source_provenance": data["sources"],
        })
    weibo_path = site / "downloads/weibo-summary.json"
    if (site / "weibo.html").is_file() and weibo_path.is_file():
        data = json.loads(weibo_path.read_text())
        non_series.append({
            "page": "weibo.html", "component": "account evidence inventory", "cadence": "research inventory",
            "definition": "Dated account/recovery evidence; not historical total output or an annual bilateral flow.",
            "cohort": data["cohort"], "roster": data["roster"], "collection": data["refresh"],
            "requested_collection_windows": data["source"].get("requested_windows", []),
            "latest_recorded_collection": data["source"].get("latest_collection_at"),
        })
    manifest = site / "publication-manifest.json"
    return {
        "version": 1,
        "source_revision": json.loads(manifest.read_text()).get("source_revision") if manifest.exists() else None,
        "target_start_year": 2000, "target_end_year": target_year,
        "interpretation": (
            "Target-window years are research goals, not a release calendar. An uncovered tail does not "
            "establish that those observations have been released. Internal gaps are calculated only "
            "for explicitly annual/monthly/YTD cadences, within the first and last reported periods. "
            "Null gaps for census/survey/snapshot/benchmark series mean annual gaps are not applicable. "
            "Bounds are retained as bounds, not exact counts. Source checks and successful retrievals "
            "remain separate. Public page references identify embedded chart models, not every dynamic "
            "selector route. State maps and Weibo account inventories are not annual series."),
        "datasets": datasets, "rendered_series": len(uses),
        "non_series_components": non_series,
        "series": series,
    }
