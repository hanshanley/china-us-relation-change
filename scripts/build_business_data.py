#!/usr/bin/env python3
"""Explicitly collect reviewed business-presence aggregates; never a daily scrape."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_sources import collect_business, finnish_eurostat_affiliates, french_affiliates, german_affiliates, netherlands_affiliates, norwegian_affiliates, nordic_affiliates, spanish_affiliates
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


def collect_norway(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = norwegian_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    data["coverage"] = [r for r in data["coverage"] if r["id"] not in definitions] + [{
        "id": "ssb_norway:china", "status": "annual",
        "description": "Statistics Norway all-industry country history; the narrower Eurostat history remains separate."}]
    return data


def collect_germany(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = german_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    data["coverage"] = [r for r in data["coverage"] if r["id"] not in definitions] + [
        {"id": sid, "status": "annual",
         "description": "German-controlled China enterprises; Eurostat and Bundesbank source histories stay "
         "separate because overlapping counts differ. Not added to EU27 or relabelled parent companies."}
        for sid in definitions]
    data["context"]["geography"] = (
        "China is the host in every chart. Germany is shown separately from the overlapping EU27 aggregate. "
        "Historical EU membership, UK and Norwegian populations remain distinct; no all-Europe total is calculated.")
    return data


def update_country_coverage(data, definitions):
    updated = {sid: {"id": sid, "status": "partial_history", "description": definition["notes"]}
               for sid, definition in definitions.items()}
    data["coverage"] = [updated.pop(row["id"], row) for row in data["coverage"]]
    data["coverage"].extend(updated.values())


def collect_nordic(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = nordic_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if not all(country in data["context"]["geography"] for country in ("Swedish", "Finnish")):
        data["context"]["geography"] += (
            " Swedish and Finnish series retain their own control, sector and source definitions; "
            "national and overlapping EU27 membership aggregates are not summed.")
    return data


def collect_france(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = french_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    return data


def collect_netherlands(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = netherlands_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Netherlands" not in data["context"]["geography"]:
        data["context"]["geography"] += " Netherlands is shown separately from the overlapping EU27 aggregate."
    return data


def collect_finland_history(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = finnish_eurostat_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    return data


def collect_spain(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = spanish_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Spain" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Spain's Eurostat financial/nonfinancial history is separate from INE's national "
            "nonfinancial population; Spain overlaps EU aggregates and is not added to them.")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refetch reviewed public assets instead of the local checksummed cache")
    parser.add_argument("--data-only", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--norway-only", action="store_true", help="Review Statistics Norway; preserve all other observations")
    selection.add_argument("--germany-only", action="store_true", help="Review Bundesbank; preserve all other observations")
    selection.add_argument("--netherlands-only", action="store_true", help="Review Dutch-controlled China affiliates; preserve all other observations")
    selection.add_argument("--nordic-only", action="store_true",
                           help="Review Swedish and Finnish China affiliates; preserve other countries")
    selection.add_argument("--france-only", action="store_true",
                           help="Review French Eurostat affiliate counts; preserve other countries")
    selection.add_argument("--finland-history-only", action="store_true",
                           help="Review the separate longer Finnish-UCI Eurostat history; preserve national counts")
    selection.add_argument("--spain-only", action="store_true",
                           help="Review Spanish-controlled Eurostat enterprises; preserve all other countries")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/business-presence/raw", args.refresh)
    collector = (collect_spain if args.spain_only else collect_netherlands if args.netherlands_only else
                 collect_finland_history if args.finland_history_only else
                 collect_france if args.france_only else collect_nordic if args.nordic_only else
                 collect_norway if args.norway_only else collect_germany if args.germany_only else None)
    data = (collector(client, json.loads((ROOT / "data/site/business_presence.json").read_text()))
            if collector else collect_business(client))
    from us_china_exchange.business_analysis import validate_business_data
    validate_business_data(data)
    write_atomic(ROOT / "data/site/business_presence.json", json_text(data))
    print(f"Frozen {len(data['observations'])} business-presence observations.", flush=True)
    if not args.data_only:
        from us_china_exchange.render import build
        print(json_text(build(ROOT)), end="")
