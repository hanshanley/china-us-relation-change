#!/usr/bin/env python3
"""Explicitly review public language data, freeze aggregates, and build offline figures."""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_analysis import validate_language_data
from us_china_exchange.language_sources import AP_GROUP_CONTEXT, ReviewClient, ap_global, ap_us_cohorts, hesa_bacs, ipeds, mla, mla_snapshot, schools, school_comparisons, school_pulse
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


def collect(client, last_degree_year=2025):
    if not 2000 <= last_degree_year <= datetime.now(timezone.utc).year:
        raise ValueError("The final degree year must be between 2000 and the current year")
    result = {"version": 1, "series": {}, "observations": [], "sources": {}, "coverage": [], "context": {}}
    for name, fetch in [("MLA", mla), ("MLA pandemic snapshot", mla_snapshot), ("HESA/BACS", hesa_bacs),
                        ("AP", ap_global), ("AP U.S. cohorts", ap_us_cohorts),
                        ("IPEDS", lambda c: ipeds(c, range(2000, last_degree_year + 1))),
                        ("Schools", schools), ("School language comparisons", school_comparisons),
                        ("National School Pulse Panel", school_pulse)]:
        print("Reviewing " + name + " sources...", flush=True)
        definitions, observations, sources = fetch(client)
        if set(definitions) & result["series"].keys() or set(sources) & result["sources"].keys():
            raise ValueError("Duplicate language-source or series identity")
        result["series"].update(definitions)
        result["observations"].extend(observations)
        result["sources"].update(sources)
    result["coverage"] = [
        {"id": "college_census", "status": "available",
         "description": "Fall census rounds 2002, 2006, 2009, 2013, 2016 and 2021; one report vintage, no annual interpolation."},
        {"id": "matched_colleges", "status": "available",
         "description": "Matched 2013/2021 institution IDs with complete reported language-count rows; nonresponse and partial-count responses excluded, explicit zero-language institutions retained."},
        {"id": "ap_global", "status": "available",
         "description": "Global AP Chinese and Japanese annual participation and standard-group subsets, 2007-2025. Not U.S.-only; no verified 2026 counts."},
        {"id": "ap_korean", "status": "not_offered",
         "description": "No AP Korean exam appears in the College Board catalogue. Korean college enrollment is a separate MLA benchmark, not an AP series."},
        {"id": "ap_us_cohorts", "status": "historical_only",
         "description": "U.S. public-school graduating classes 2007-2013, counting exams taken during high school. Not the year of exam administration or all U.S. schools."},
        {"id": "ap_us_annual", "status": "not_verified",
         "description": "A current U.S.-only annual administration series remains unverified. Global reports, their standard group and historical graduating cohorts cannot substitute for that population."},
        {"id": "degree_awards", "status": "available",
         "description": f"Annual IPEDS awards from academic year ending 2000 through {last_degree_year}; first major from 2001, 50 states/DC and Title IV degree-granting institutions."},
        {"id": "immersion_programs", "status": "snapshots_only",
         "description": "CAL 2011 directory, ARC 2021 public-school canvass and Nexus 2025 mixed-school inventory have different universes; no comparable growth rate."},
        {"id": "k12_learners", "status": "estimate_only",
         "description": "2014-15-era Chinese enrollment estimate, published 2017. No continuous national learner census verified; do not combine with immersion-program counts."},
    ]
    result["context"] = {
        "question": "Is the United States losing its capacity to develop Chinese-language expertise, or is learning shifting between educational settings?",
        "economist": {
            "title": "Why fewer university students are studying Mandarin",
            "date": "2023-08-24",
            "url": "https://www.economist.com/china/2023/08/24/why-fewer-university-students-are-studying-mandarin",
            "role": "Context, not the numeric source for the census series.",
            "interpretation": "Employment incentives, geopolitical tensions, competing cultural attractions and translation technology are proposed explanations, not a demonstrated causal decomposition.",
            "reported_snapshot_change_percent": -21,
            "snapshot_comparison_years": [2016, 2020],
            "snapshot_source_id": "mla_snapshot_2020",
        },
        "nexus_response_scope": {
            "year": 2025, "program_responses": 103, "us_program_responses": 102,
            "hong_kong_program_responses": 1, "response_associated_enrollments": 34341,
            "note": "Mixed-geography respondent total, not a U.S. national learner count; excluded from U.S. enrollment observations.",
        },
        "rights": "Only selected numerical aggregates and our original figures are published, not source reports, artwork, institution-level workbooks or exam questions. Source terms still apply; commercial reuse permission is not established by these exports.",
    }
    result["context"]["ap_groups"] = AP_GROUP_CONTEXT
    result["observations"].sort(key=lambda r: (r["series_id"], r["year"]))
    return update_school_context(update_article_context(result))


def update_article_context(result):
    result["context"]["economist"]["republication"] = {
        "publisher": "Mint", "date": "2023-10-27",
        "url": "https://www.livemint.com/specials/why-fewer-university-students-are-studying-mandarin-11698412205247.html"}
    result["context"]["economist"]["snapshot_series"] = [
        "mla_snapshot:chinese", "mla_snapshot:japanese", "mla_snapshot:korean"]
    result["context"]["uk_chinese_studies"] = {
        "series_id": "hesa_chinese_studies:total", "source_id": "hesa_bacs_2021_22",
        "reference_periods": ["2012/13", "2021/22"],
        "note": "Subject-apportioned enrollments, not admissions or all Mandarin learners. "
        "Historical source data are kept in complete downloads; they do not qualify as a current public plot. "
        "JACS and HECoS observations are separate comparison groups; no U.S./UK learner total is calculated."}
    return result


def collect_article_sources(client, prior):
    result = copy.deepcopy(prior)
    for fetch in (mla_snapshot, hesa_bacs):
        definitions, observations, sources = fetch(client)
        result["series"].update(definitions)
        result["sources"].update(sources)
        result["observations"] = [
            r for r in result["observations"] if r["series_id"] not in definitions] + observations
    result["observations"].sort(key=lambda r: (r["series_id"], r["year"]))
    return validate_language_data(update_article_context(result))


def update_school_context(result):
    for item in result["coverage"]:
        if item["id"] == "k12_learners":
            item["description"] = ("2014-15-era Chinese/Japanese national enrollment estimates, published 2017. "
                                   "No comparable national Korean total or continuous K-12 census is verified.")
    result["coverage"] = [r for r in result["coverage"] if r["id"] not in {
        "hs_language_availability", "school_pulse_availability", "language_demand"}] + [
        {"id": "hs_language_availability", "status": "snapshot_only",
         "description": "2014-15 reported high-school programs: Chinese 1,144, Japanese 433 and Korean 43. Not unique schools or a national availability census."},
        {"id": "language_demand", "status": "not_measured",
         "description": "Enrollments, program availability and exam participation do not directly measure unmet demand. No composite national learner total is calculated."}]
    if "spp_availability:chinese" in result["series"]:
        result["coverage"].append({
            "id": "school_pulse_availability", "status": "survey_snapshot",
            "description": "January 2024 national public-school availability estimates: Chinese 3%, Japanese 1%; "
            "Korean below reporting standards. Not student enrollments or a continuation of 2014-15 program counts."})
    return validate_language_data(result)


def collect_school_pulse(client, prior):
    result = copy.deepcopy(prior)
    definitions, observations, sources = school_pulse(client)
    result["series"].update(definitions)
    result["sources"].update(sources)
    result["observations"] = sorted(
        [r for r in result["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    return update_school_context(result)


def collect_school_comparisons(client, prior):
    result = copy.deepcopy(prior)
    definitions, observations, sources = school_comparisons(client)
    result["series"].update(definitions)
    result["sources"].update(sources)
    result["observations"] = [r for r in result["observations"] if r["series_id"] not in definitions] + observations
    result["observations"].sort(key=lambda r: (r["series_id"], r["year"]))
    return update_school_context(result)


def collect_ap(client, prior):
    result = copy.deepcopy(prior)
    definitions, observations, sources = ap_global(client)
    result["series"].update(definitions)
    result["sources"].update(sources)
    result["observations"] = [r for r in result["observations"] if not r["series_id"].startswith("ap:")] + observations
    for item in result["coverage"]:
        if item["id"] == "ap_global":
            item["description"] = "Global AP Chinese and Japanese counts and standard-group subsets, 2007-2025; not U.S.-only. No verified 2026 participant counts."
    result["coverage"] = [r for r in result["coverage"] if r["id"] != "ap_korean"] + [{
        "id": "ap_korean", "status": "not_offered", "description": AP_GROUP_CONTEXT["korean"]}]
    result["context"]["ap_groups"] = AP_GROUP_CONTEXT
    result["observations"].sort(key=lambda r: (r["series_id"], r["year"]))
    return validate_language_data(result)


def collect_ipeds(client, prior, year, full_history=False):
    if not 2000 <= year <= datetime.now(timezone.utc).year:
        raise ValueError("The degree year must be between 2000 and the current year")
    result = copy.deepcopy(prior)
    definitions, observations, sources = ipeds(client, range(2000, year + 1) if full_history else [year])
    result["series"].update(definitions)
    result["sources"].update(sources)
    records = {(r["series_id"], r["year"]): r for r in result["observations"]}
    records.update({(r["series_id"], r["year"]): r for r in observations})
    result["observations"] = sorted(records.values(), key=lambda r: (r["series_id"], r["year"]))
    last = max(r["year"] for r in result["observations"] if r["series_id"].startswith("ipeds:"))
    for item in result["coverage"]:
        if item["id"] == "degree_awards":
            item["description"] = (
                f"Annual Chinese, Japanese and Korean IPEDS awards from academic year ending 2000 through {last}; "
                "first major from 2001, 50 states/DC and Title IV degree-granting institutions.")
    return validate_language_data(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Explicitly re-fetch reviewed public source files instead of their checksummed local cache")
    parser.add_argument("--last-degree-year", type=int, default=2025)
    parser.add_argument("--data-only", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--ap-only", action="store_true", help="Review only AP sources; preserve all non-AP observations and definitions")
    selection.add_argument("--schools-only", action="store_true", help="Add reviewed school language comparisons; preserve all other observations")
    selection.add_argument("--school-pulse-only", action="store_true", help="Review national January 2024 availability estimates; preserve historical observations")
    selection.add_argument("--article-sources-only", action="store_true", help="Review the distinct MLA pandemic snapshot and HESA/BACS history; preserve all other data")
    selection.add_argument("--ipeds-only", action="store_true", help="Review the selected final IPEDS year; preserve every other year and non-degree observation")
    selection.add_argument("--ipeds-history", action="store_true", help="Review Chinese, Japanese and Korean degree histories from 2000; preserve non-degree observations")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/language-learning/raw", args.refresh)
    if args.ipeds_only or args.ipeds_history:
        prior = json.loads((ROOT / "data/site/language_learning.json").read_text())
        data = collect_ipeds(client, prior, args.last_degree_year, args.ipeds_history)
    elif args.article_sources_only:
        prior = json.loads((ROOT / "data/site/language_learning.json").read_text())
        data = collect_article_sources(client, prior)
    elif args.ap_only or args.schools_only or args.school_pulse_only:
        prior = json.loads((ROOT / "data/site/language_learning.json").read_text())
        fetch = collect_ap if args.ap_only else collect_school_pulse if args.school_pulse_only else collect_school_comparisons
        data = fetch(client, prior)
    else:
        data = collect(client, args.last_degree_year)
    write_atomic(ROOT / "data/site/language_learning.json", json_text(data))
    if not args.data_only:
        from us_china_exchange.render import build
        print(json_text(build(ROOT)), end="")
