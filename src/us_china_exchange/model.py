import calendar
import hashlib
import json
import math
from datetime import date


GEOGRAPHIES = {"CHN": "Mainland China", "HKG": "Hong Kong",
               "MAC": "Macau", "TWN": "Taiwan", "USA": "United States"}
MEASURES = {
    "degree_students": "Degree enrollment",
    "international_students": "International students, including OPT",
    "study_abroad": "Academic-credit study abroad",
    "visitors": "Visitor trips",
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
        "period_start": f"{year}-{start_month:02d}-01",
        "period_end": f"{year}-{end_month:02d}-{calendar.monthrange(year, end_month)[1]}",
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
        if row["measure"] not in MEASURES or row["year"] < 2010:
            raise ValueError("Unsupported measure or year")
        if row["status"] not in {"observed", "estimated", "provisional", "missing", "suppressed"}:
            raise ValueError("Unknown observation status")
        value = row["value"]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0
        ):
            raise ValueError("Invalid observation value")
        if (value is None) != (row["status"] in {"missing", "suppressed"}):
            raise ValueError("Missingness and observation status disagree")
        start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
        if start > end or end.year != row["year"]:
            raise ValueError("Invalid period boundaries")
        if row["period_basis"] not in {"calendar", "academic", "reporting"}:
            raise ValueError("Unknown period basis")
        if row["frequency"] not in {"annual", "monthly", "ytd"}:
            raise ValueError("Unknown frequency")
        if not row["source_id"] or not row["definition"]:
            raise ValueError("Missing provenance or definition")
    return sorted(rows, key=key)


def change(current, baseline):
    if baseline is None or baseline["value"] is None:
        return {"absolute": None, "percent": None, "reason": "Baseline unavailable"}
    fields = ("series_id", "frequency", "period_basis", "comparability", "unit")
    if any(current[f] != baseline[f] for f in fields) or (
        current["period_start"][5:] != baseline["period_start"][5:]
        or current["period_end"][5:] != baseline["period_end"][5:]
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
                    "reason": "" if available else (
                        "No separately reported Taiwan series in UNESCO UIS; alternative official education data required"
                        if measure == "degree_students" and geo == "TWN" else
                        "No verified observations retrieved; see source attempts and limitations"),
                })
    return result
