import calendar
import hashlib
import json
import math
from datetime import date


START_YEAR = 2000
GEOGRAPHIES = {"CHN": "Mainland China", "HKG": "Hong Kong",
               "MAC": "Macau", "TWN": "Taiwan", "USA": "United States"}
MEASURES = {
    "enrolled_students": "Enrolled international students (excluding OPT)",
    "degree_students": "Degree enrollment",
    "international_students": "International students, including OPT",
    "study_abroad": "Academic-credit study abroad",
    "visitors": "Visitor trips",
    "air_visitors": "U.S.-resident air-travel destination estimates",
    "leisure_visitors": "Leisure visitor trips",
    "goods": "Goods trade",
    "services": "Services trade",
}


def json_text(value):
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True,
                      allow_nan=False) + "\n"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def observation(source, origin, destination, measure, year, value,
                definition, unit=None, frequency="annual", month=None,
                period_basis="calendar", status="observed", notes="",
                comparability=""):
    year_only = period_basis in {"academic", "reporting"}
    if year_only and (frequency != "annual" or month is not None):
        raise ValueError("Academic and reporting years require annual observations without a month")
    if frequency in {"monthly", "ytd"} and month is None:
        raise ValueError("Monthly and YTD observations require an ending month")
    if month is not None and (isinstance(month, bool) or not 1 <= month <= 12):
        raise ValueError("Invalid month")
    end_month = month or 12
    start_month = month if frequency == "monthly" else 1
    label = str(year) if month is None else f"{year}-{month:02d}"
    if period_basis == "academic":
        label = f"{year - 1}/{str(year)[-2:]}"
    series_id = f"{source}:{origin}:{destination}:{measure}"
    return {
        "series_id": series_id, "source_id": source,
        "origin": origin, "destination": destination, "measure": measure,
        "year": year, "period": label, "period_basis": period_basis,
        "period_start": None if year_only else f"{year}-{start_month:02d}-01",
        "period_end": None if year_only else (
            f"{year}-{end_month:02d}-{calendar.monthrange(year, end_month)[1]}"),
        "frequency": frequency, "unit": unit or (
            "USD" if measure in {"goods", "services"} else
            "trips" if "visitors" in measure else "students"),
        "value": value, "status": status, "definition": definition,
        "comparability": comparability or definition, "notes": notes,
    }


def key(row):
    return row["series_id"], row["period"], row["frequency"]


def validate(rows):
    seen = set()
    for row in rows:
        if key(row) in seen:
            raise ValueError(f"Duplicate observation: {key(row)}")
        seen.add(key(row))
        if row["origin"] not in GEOGRAPHIES or row["destination"] not in GEOGRAPHIES:
            raise ValueError("Unknown geography")
        if (row["origin"] == "USA") == (row["destination"] == "USA"):
            raise ValueError("Observation must have exactly one U.S. endpoint")
        if (row["measure"] not in MEASURES or isinstance(row["year"], bool)
                or not isinstance(row["year"], int) or row["year"] < START_YEAR):
            raise ValueError("Unsupported measure or year")
        expected_series = f"{row['source_id']}:{row['origin']}:{row['destination']}:{row['measure']}"
        if row["series_id"] != expected_series:
            raise ValueError("Series identity does not match its source, geography and measure")
        null_statuses = {"missing", "suppressed", "not_applicable", "included_elsewhere"}
        if row["status"] not in null_statuses | {"observed", "estimated", "provisional", "low_reliability"}:
            raise ValueError("Unknown observation status")
        value = row["value"]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0
        ):
            raise ValueError("Invalid observation value")
        if (value is None) != (row["status"] in null_statuses):
            raise ValueError("Missingness and observation status disagree")
        if row["period_basis"] not in {"calendar", "academic", "reporting"}:
            raise ValueError("Unknown period basis")
        if row["frequency"] not in {"annual", "monthly", "ytd"}:
            raise ValueError("Unknown frequency")
        if row["period_basis"] in {"academic", "reporting"}:
            if row["period_start"] is not None or row["period_end"] is not None:
                raise ValueError("Academic and reporting periods must not invent exact dates")
            if row["frequency"] != "annual":
                raise ValueError("Academic and reporting years require annual observations")
            label = (f"{row['year'] - 1}/{str(row['year'])[-2:]}"
                     if row["period_basis"] == "academic" else str(row["year"]))
            if row["period"] != label:
                raise ValueError("Invalid academic or reporting period label")
        else:
            start = date.fromisoformat(row["period_start"])
            end = date.fromisoformat(row["period_end"])
            if start > end or start.year != row["year"] or end.year != row["year"]:
                raise ValueError("Invalid period boundaries")
            if start.day != 1 or end.day != calendar.monthrange(end.year, end.month)[1]:
                raise ValueError("Periods must cover complete months")
            if row["frequency"] == "annual" and (start.month, end.month) != (1, 12):
                raise ValueError("Annual periods must cover a full year")
            if row["frequency"] == "monthly" and start.month != end.month:
                raise ValueError("Monthly periods must cover one month")
            if row["frequency"] == "ytd" and start.month != 1:
                raise ValueError("YTD periods must begin in January")
            label = str(row["year"]) if row["frequency"] == "annual" else f"{row['year']}-{end.month:02d}"
            if row["period"] != label:
                raise ValueError("Invalid calendar period label")
        if not row["source_id"] or not row["definition"]:
            raise ValueError("Missing provenance or definition")
    return sorted(rows, key=key)


def change(current, baseline):
    if baseline is None or baseline["value"] is None:
        return {"absolute": None, "percent": None, "reason": "Baseline unavailable"}
    fields = ("series_id", "frequency", "period_basis", "comparability", "unit")
    if any(current[f] != baseline[f] for f in fields) or (
        (current["period_start"] or "")[5:7] != (baseline["period_start"] or "")[5:7]
        or (current["period_end"] or "")[5:7] != (baseline["period_end"] or "")[5:7]
    ):
        return {"absolute": None, "percent": None, "reason": "Definitions or periods differ"}
    if current["value"] is None:
        return {"absolute": None, "percent": None, "reason": "Current value unavailable"}
    absolute = current["value"] - baseline["value"]
    return {"absolute": absolute,
            "percent": absolute / baseline["value"] * 100 if baseline["value"] else None,
            "reason": "" if baseline["value"] else "Zero baseline; percentage undefined"}


def coverage(rows):
    result = []
    for geo in GEOGRAPHIES:
        if geo == "USA":
            continue
        for origin, destination in [(geo, "USA"), ("USA", geo)]:
            for measure in MEASURES:
                subset = [r for r in rows if (r["origin"], r["destination"], r["measure"])
                          == (origin, destination, measure)]
                available = [r for r in subset if r["value"] is not None]
                years = sorted({r["year"] for r in available if r["frequency"] == "annual"})
                result.append({
                    "origin": origin, "destination": destination, "measure": measure,
                    "observations": len(available), "first_year": min(years) if years else None,
                    "last_year": max(years) if years else None, "available_years": years,
                    "baseline_2020": 2020 in years,
                    "source_ids": sorted({r["source_id"] for r in subset}),
                    "reason": "" if available else gap_reason(geo, origin, measure),
                })
    return result


def gap_reason(geo, origin, measure):
    if measure == "air_visitors":
        return "Reviewed SIAT estimates cover U.S.-resident air travel to mainland China and Hong Kong only. Other directions are unverified; missing estimates are not zero or all-mode arrivals."
    if measure == "degree_students":
        if geo == "TWN":
            return "Taiwan is not separately listed in UIS bilateral tertiary-mobility indicators; IIE counts have a different scope."
        return "UIS bilateral origin/destination request returned no records; no compatible destination degree-enrollment series verified."
    if measure == "enrolled_students":
        return "IIE enrolled-only counts cover U.S. hosts. MOE historical degree/non-degree reporting snapshots cover the mainland destination only; equivalent enrollment counts for this route remain unverified."
    if measure == "international_students":
        return "OPT-inclusive IIE totals describe students hosted in the U.S.; not an outbound U.S. enrollment measure."
    if measure == "study_abroad":
        return "IIE credit-study-abroad statistics cover U.S.-origin participants only; reverse-direction participation is not reported here."
    if measure == "leisure_visitors":
        return "Available arrival sources are all-purpose trips; no separately verified leisure-purpose series for this direction."
    if measure == "services":
        return "Macau services are directly reported in the USTR country summary for 2025; older years remain unverified. A missing value is not zero or a regional allocation."
    if measure == "visitors" and origin == "USA":
        if geo == "HKG":
            return "HKTB all-mode history uses residence for 2000-2022 and nationality for 2023-2025, with a visible definition break; matched first-half 2025/2026 counts are separate. No cross-definition 2020 index is calculated."
        if geo == "CHN":
            return "No current U.S.-origin all-mode visitor table verified in mainland official releases; historic arrivals are not spliced to air-passenger proxies."
    return "No verified compatible primary-source observations; missing values are never inferred as zero."
