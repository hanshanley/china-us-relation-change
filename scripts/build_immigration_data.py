#!/usr/bin/env python3
"""Manually review official immigration aggregates and freeze a validated snapshot."""

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.immigration_analysis import validate_immigration_data
from us_china_exchange.immigration_sources import (
    ADMISSION_YEARS, BIRTH_YEARS, MACAU_ABODE_YEARS, admissions, birthplace, collect, macau_abode,
)
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


def collect_macau(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = macau_abode(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    data["coverage"] = [r for r in data["coverage"] if r["id"] != "macau_residence_approvals"] + [{
        "id": "macau_residence_approvals", "status": "available",
        "description": f"DSEC U.S.-category residence approvals for every calendar year "
        f"{MACAU_ABODE_YEARS[0]}-{MACAU_ABODE_YEARS[-1]}; "
        "not resident stocks, physical U.S. departures or a permanent-resident classification."}]
    data["context"]["macau_approvals"] = (
        "DSEC's Macau series counts newly approved people in its U.S. country category, not verified U.S. citizens, "
        "U.S. departures or permanent-resident grants.")
    data["context"]["periods"] = (
        "U.S. grant series use fiscal years ending September 30. Macau approvals use January-December calendar years. "
        "UN resident stocks use 1 July benchmarks. Birthplace, citizenship and source-country categories remain separate.")
    return validate_immigration_data(data)


def collect_admissions(client, prior):
    data = copy.deepcopy(prior)
    observations, sources = admissions(client)
    old = {(r["series_id"], r["year"]): r for r in data["observations"]}
    for row in observations:
        key = row["series_id"], row["year"]
        if key in old and old[key]["value"] != row["value"]:
            raise ValueError("Annual admissions backfill conflicts with a retained count")
        old.setdefault(key, row)
    data["observations"] = sorted(old.values(), key=lambda r: (r["series_id"], r["year"]))
    data["sources"].update({sid: source for sid, source in sources.items() if sid not in data["sources"]})
    data["context"]["rounding"] = (
        "FY2015-2024 birthplace counts and FY2023-2025 nationality counts are rounded to the nearest ten. "
        "Earlier source vintages retain their published exact counts.")
    data["context"]["admissions_vintages"] = (
        "Nationality counts retain each fiscal year's published Q4 preliminary administrative-report vintage, "
        "not a harmonized final-yearbook revision.")
    for coverage in data["coverage"]:
        if coverage["id"] == "to_us_nationality":
            coverage["description"] = (
                f"China nationality category, FY{ADMISSION_YEARS[0]}-FY{ADMISSION_YEARS[-1]} "
                "annual permanent-residency grants. "
                "New arrivals and adjustments within the U.S. are distinct; not a count by previous residence.")
    return validate_immigration_data(data)


def collect_birthplace(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = birthplace(client)
    old = {(r["series_id"], r["year"]): r for r in data["observations"]}
    for row in observations:
        key = row["series_id"], row["year"]
        if key in old and old[key]["value"] != row["value"]:
            raise ValueError("Birthplace backfill conflicts with a retained count")
        old.setdefault(key, row)
    data["observations"] = sorted(old.values(), key=lambda r: (r["series_id"], r["year"]))
    data["series"].update(definitions)
    data["sources"].update(sources)
    for coverage in data["coverage"]:
        if coverage["id"] == "to_us_birthplace":
            coverage["description"] = (
                f"China, Hong Kong and Macau birthplace series, FY{BIRTH_YEARS[0]}-FY{BIRTH_YEARS[-1]}; "
                "all permanent-resident status grants, including new arrivals and adjustments.")
    return validate_immigration_data(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--macau-only", action="store_true", help="Add Macau annual residence approvals; preserve all other observations")
    selection.add_argument("--admissions-only", action="store_true", help="Add annual new arrivals and status adjustments; preserve other observations")
    selection.add_argument("--birthplace-only", action="store_true", help="Extend birthplace-based status grants; preserve other observations")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/immigration/raw", args.refresh)
    if args.admissions_only or args.macau_only or args.birthplace_only:
        collector = collect_admissions if args.admissions_only else collect_macau if args.macau_only else collect_birthplace
        data = collector(client, json.loads((ROOT / "data/site/immigration.json").read_text()))
    else:
        data = validate_immigration_data(collect(client))
    write_atomic(ROOT / "data/site/immigration.json", json_text(data))
    print(f"Reviewed {len(data['observations'])} immigration observations from {len(data['sources'])} official source assets.")
