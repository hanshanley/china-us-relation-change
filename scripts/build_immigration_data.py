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
from us_china_exchange.immigration_sources import admissions, collect, macau_abode
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
        "description": "DSEC U.S.-category residence approvals for every calendar year 2010-2025; "
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
    for coverage in data["coverage"]:
        if coverage["id"] == "to_us_nationality":
            coverage["description"] = (
                "China nationality category, FY2020-FY2025 annual permanent-residency grants. "
                "New arrivals and adjustments within the U.S. are distinct; not a count by previous residence.")
    return validate_immigration_data(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--macau-only", action="store_true", help="Add Macau annual residence approvals; preserve all other observations")
    parser.add_argument("--admissions-only", action="store_true", help="Add annual new arrivals and status adjustments; preserve other observations")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/immigration/raw", args.refresh)
    data = (collect_admissions(client, json.loads((ROOT / "data/site/immigration.json").read_text()))
            if args.admissions_only else collect_macau(client, json.loads((ROOT / "data/site/immigration.json").read_text()))
            if args.macau_only else validate_immigration_data(collect(client)))
    write_atomic(ROOT / "data/site/immigration.json", json_text(data))
    print(f"Reviewed {len(data['observations'])} immigration observations from {len(data['sources'])} official source assets.")
