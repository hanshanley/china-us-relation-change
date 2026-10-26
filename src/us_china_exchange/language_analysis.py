"""Domestic language-learning indicators, kept separate from bilateral flows."""

import math
import re
from datetime import datetime
from urllib.parse import urlsplit

from .indicator_charts import svg_indicator_chart
from .public_freshness import current_groups
from .theme import PARTNER_COLORS


LANGUAGE_COLORS = {"chinese": PARTNER_COLORS["CHN"], "japanese": "#3D6F8C",
                   "korean": "#4A7C59", "all_languages": "#6B6B6B", "spanish": "#C2993E"}
RETIRED_CHARTS = {"ap-language-standard-group", "school-language-availability",
                  "language-doctorates", "school-program-inventories"}
CHARTS = {
    "college-enrollments": {
        "title": "College language-course enrollments",
        "subtitle": "U.S. colleges and universities | fall census rounds",
        "series": ["mla:chinese", "mla:japanese", "mla:korean"], "unit": "Course registrations", "mode": "levels",
        "note": "MLA 2021-report vintage, U.S. institutions. Course registrations, not unique learners or U.S. citizenship counts. Commercial reuse permission unverified."},
    "school-language-enrollments": {
        "title": "K-12 language-enrollment estimates", "subtitle": "2014–15-era reference period | published in 2017",
        "series": ["schools:k12_estimate", "schools:k12_japanese_estimate"], "unit": "Enrollments", "mode": "bars",
        "note": "American Councils Table 2. Chinese/Japanese state reports plus modeled estimates for missing data; not unique people. No comparable national Korean total is supplied. Its 936 respondent enrollments are not mixed into these national estimates."},
    "college-share": {
        "title": "Each language's share of college language study",
        "subtitle": "Share of all non-English language course registrations",
        "series": ["mla:chinese", "mla:japanese", "mla:korean"], "denominator": "mla:all_languages", "unit": "Percent", "mode": "share",
        "note": "Calculated from the same MLA report vintage and census rounds; denominator includes ASL and classical languages. Not a share of all college students."},
    "college-benchmarks": {
        "title": "Language study in context",
        "subtitle": "U.S. college course enrollments | 2013 = 100",
        "series": ["mla:chinese", "mla:japanese", "mla:korean"],
        "unit": "2013 = 100", "mode": "index", "baseline": 2013,
        "note": "MLA 2021-report vintage. Each language is indexed to its 2013 course registrations."},
    "matched-college-benchmarks": {
        "title": "The same responding institutions",
        "subtitle": "Matched 2013/2021 respondents | 2013 = 100",
        "series": ["mla_matched:chinese", "mla_matched:japanese", "mla_matched:korean"],
        "unit": "2013 = 100", "mode": "index", "baseline": 2013,
        "note": "MLA. Institutions reporting complete language counts in both 2013 and 2021; a selected cohort, not a national total."},
    "ap-chinese-global": {
        "title": "AP Chinese and Japanese test takers",
        "subtitle": "All participants | global administrations, not U.S.-only",
        "series": ["ap:global_total", "ap:japanese_total"], "unit": "Exam participants", "mode": "levels",
        "note": "College Board global exam totals, not U.S.-only counts or all language learners. No AP Korean exam is listed; Korean college enrollments are a separate comparison. No verified 2026 participant counts."},
    "ap-chinese-us-cohorts": {
        "title": "AP Chinese in U.S. public-school cohorts",
        "subtitle": "Graduating classes 2007-2013 | exams taken during high school",
        "series": ["ap_cohort:us_public"], "unit": "Exams", "mode": "levels",
        "note": "College Board Report to the Nation. Year is graduating class, not exam administration. U.S. public-school cohorts, distinct from global annual exam totals."},
    "chinese-bachelors": {
        "title": "Bachelor's degrees by language",
        "subtitle": "Nationwide IPEDS | Chinese, Japanese and Korean | academic year ending",
        "series": ["ipeds:bachelors", "ipeds_japanese:bachelors", "ipeds_korean:bachelors"],
        "unit": "Awards", "mode": "levels", "point_markers": False,
        "note": "NCES IPEDS, U.S. degree-granting institutions. First-major language and literature degrees. "
        "Reporting definitions changed in 2001; 2025 is provisional."},
    "chinese-graduate-awards": {
        "title": "Master's degrees by language",
        "subtitle": "Nationwide IPEDS | Chinese, Japanese and Korean | academic year ending",
        "series": ["ipeds:masters", "ipeds_japanese:masters", "ipeds_korean:masters"],
        "unit": "Awards", "mode": "levels", "point_markers": False,
        "note": "NCES IPEDS, U.S. degree-granting institutions. First-major language and literature degrees. "
        "Reporting definitions changed in 2001; 2025 is provisional."},
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
        if r["status"] not in {"observed", "estimated", "reported_or_imputed", "missing", "suppressed"}:
            raise ValueError("Invalid language observation status")
        if (r["value"] is None) != (r["status"] in {"missing", "suppressed"}):
            raise ValueError("Language observation missingness disagrees with status")
        percentage = definitions[r["series_id"]]["measure"] == "school_offering_share"
        if percentage and (not r["series_id"].startswith("spp_availability:")
                           or r["source_id"] != "nces_spp_languages_2024" or r["year"] != 2024
                           or definitions[r["series_id"]]["unit"] != "percent"
                           or definitions[r["series_id"]]["period_basis"] != "January 2024 survey"
                           or definitions[r["series_id"]]["cadence"] != "survey snapshot"
                           or "all schools" not in definitions[r["series_id"]]["scope"]):
            raise ValueError("School availability must retain its survey period, percentage unit and source")
        if r["value"] is not None and (isinstance(r["value"], bool)
                or not isinstance(r["value"], (int, float) if percentage else int)
                or not math.isfinite(r["value"]) or r["value"] < 0 or (percentage and r["value"] > 100)):
            raise ValueError("Language counts must be nonnegative integers; school percentages must be finite and within 0-100")
        if not isinstance(r["comparability"], str) or not r["comparability"]:
            raise ValueError("Missing language comparability definition")
        if not isinstance(r["notes"], str):
            raise ValueError("Language observation notes must be text")
        if r["series_id"].startswith("mla_snapshot:") and (
                r["source_id"] != "mla_snapshot_2020" or r["year"] not in {2016, 2020}
                or definitions[r["series_id"]]["cadence"] != "paired census"
                or "1,308" not in definitions[r["series_id"]]["scope"]
                or "not the national census" not in definitions[r["series_id"]]["scope"]):
            raise ValueError("MLA snapshot must retain its matched population and 2016/2020 endpoints")
        if r["series_id"].startswith("hesa_chinese_studies:") and (
                r["source_id"] != "hesa_bacs_2021_22"
                or definitions[r["series_id"]]["period_basis"] != "academic ending year"
                or definitions[r["series_id"]]["unit"] != "subject-apportioned enrollments"
                or "UK higher education" not in definitions[r["series_id"]]["scope"]
                or r["comparability"] != ("hesa_chinese_studies:quoted_legacy_population"
                    if r["series_id"] == "hesa_chinese_studies:quoted_2012"
                    else "hesa_chinese_studies:" + ("jacs" if r["year"] < 2020 else "hecos"))
                or (r["series_id"] == "hesa_chinese_studies:total" and r["year"] < 2015)
                or (r["series_id"] == "hesa_chinese_studies:quoted_2012" and r["year"] != 2013)):
            raise ValueError("HESA must retain UK subject allocations, academic years and the coding boundary")
        if r["series_id"].startswith("ap:") and "global" not in definitions[r["series_id"]]["scope"].lower():
            raise ValueError("Global AP data must not be relabelled U.S.-only")
        if r["series_id"].startswith("ap_cohort:") and (
                "U.S. public-school graduating" not in definitions[r["series_id"]]["scope"]
                or definitions[r["series_id"]]["period_basis"] != "graduating class"):
            raise ValueError("AP U.S. public-school cohorts must retain their graduating-class population")
        if r["series_id"].startswith("ap_us_annual:") and (
                r["series_id"] not in {"ap_us_annual:chinese", "ap_us_annual:japanese"}
                or r["source_id"] != f"tea_ap_us_{r['year']}" or r["year"] < 2007
                or definitions[r["series_id"]]["period_basis"] != "academic ending year"
                or definitions[r["series_id"]]["measure"] != "annual_exam_administrations"
                or definitions[r["series_id"]]["unit"] != "exams"
                or definitions[r["series_id"]]["cadence"] != "annual"
                or definitions[r["series_id"]]["scope"] !=
                "U.S. public and nonpublic school examinees, all grades; national annual AP language exams"):
            raise ValueError("AP U.S. annual exams must retain their national all-school administration population")
    by_key = {(r["series_id"], r["year"]): r for r in data["observations"]}
    for r in data["observations"]:
        if r["series_id"].startswith("ap_us_annual:") and r["value"] is not None:
            global_id = "ap:global_total" if r["series_id"].endswith(":chinese") else "ap:japanese_total"
            total = by_key.get((global_id, r["year"]))
            if total is not None and total["value"] is not None and r["value"] > total["value"]:
                raise ValueError("AP U.S. annual count exceeds the separately retained global total")
        if r["series_id"] in {"ap:standard_group", "ap:japanese_standard_group"} and r["value"] is not None:
            total_id = "ap:global_total" if r["series_id"] == "ap:standard_group" else "ap:japanese_total"
            total = by_key.get((total_id, r["year"]))
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
        language = ("japanese" if "japanese" in sid else "chinese") if (
            sid.startswith("ap:") or chart_id == "school-language-enrollments") else sid.split(":")[-1]
        degrees = chart_id in {"chinese-bachelors", "chinese-graduate-awards"}
        if degrees:
            language = "japanese" if sid.startswith("ipeds_japanese:") else "korean" if sid.startswith("ipeds_korean:") else "chinese"
        color = LANGUAGE_COLORS.get(language, ["#7B2D26", "#3D6F8C", "#C2993E"][index % 3])
        label = language.capitalize() if degrees or chart_id == "school-language-enrollments" else data["series"][sid]["label"]
        grouped.append({"id": sid, "label": label, "color": color,
                        "points": points, "scheduled_years": [r["year"] for r in selected],
                        "cadence": data["series"][sid]["cadence"],
                        "period_basis": data["series"][sid]["period_basis"],
                        "unavailable_label": "Not reportable" if selected and all(
                            r["status"] == "suppressed" for r in selected) else "Unavailable"})
    return current_groups(grouped)


def svg_language_chart(data, chart_id, theme="themarginoferror"):
    config = dict(CHARTS[chart_id])
    groups = chart_points(data, chart_id)
    points = [r for group in groups for r in group["points"]]
    if any(r["source_id"].startswith("mla") for r in points) and "permission" not in config["note"]:
        config["note"] += " MLA commercial reuse permission unverified."
    return svg_indicator_chart(
        config, groups, theme,
        "U.S. language-learning indicators, with source-specific units and populations.",
        "language-point")
