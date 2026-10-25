#!/usr/bin/env python3
"""Explicitly collect reviewed business-presence aggregates; never a daily scrape."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_sources import austrian_affiliates, belgian_affiliates, collect_business, danish_affiliates, finnish_eurostat_affiliates, french_affiliates, german_affiliates, italian_affiliates, netherlands_affiliates, norwegian_affiliates, nordic_affiliates, polish_affiliates, spanish_affiliates, swedish_eurostat_affiliates, uk_early_affiliates
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


def collect_uk_history(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = uk_early_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    replaced = {(row["series_id"], row["year"]) for row in observations}
    data["observations"] = sorted(
        [row for row in data["observations"] if (row["series_id"], row["year"]) not in replaced]
        + observations, key=lambda row: (row["series_id"], row["year"]))
    update_country_coverage(data, definitions)
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


def collect_italy(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = italian_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Italian" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Italian historical legal units and current enterprises remain separate, not a compatible splice.")
    data["context"]["geography"] = data["context"]["geography"].replace(
        "Italian historical legal units and current enterprises remain separate, not a compatible splice.",
        "Italian legal-unit history reaches 2023; grouped Eurostat enterprises remain a separate population.")
    return data


def collect_austria(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = austrian_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [row for row in data["observations"] if row["series_id"] not in definitions] + observations,
        key=lambda row: (row["series_id"], row["year"]))
    update_country_coverage(data, definitions)
    if "Austria" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Austria is separate from overlapping EU27 membership and broader national counts; "
            "its older legal units are not spliced into current enterprise counts.")
    return data


def collect_sweden_history(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = swedish_eurostat_affiliates(client)
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


def collect_denmark(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = danish_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Denmark" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Denmark's national resident-parent coverage includes foreign ultimate owners and excludes "
            "branches; it is not spliced with Danish-UCI Eurostat counts or summed into EU aggregates.")
    return data


def collect_poland(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = polish_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Poland" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Poland's ultimate-control population remains separate from the broader national "
            "foreign-equity survey and is not added to overlapping EU aggregates.")
    return data


def collect_belgium(client, prior):
    data = copy.deepcopy(prior)
    definitions, observations, sources = belgian_affiliates(client)
    data["series"].update(definitions)
    data["sources"].update(sources)
    data["observations"] = sorted(
        [r for r in data["observations"] if r["series_id"] not in definitions] + observations,
        key=lambda r: (r["series_id"], r["year"]))
    update_country_coverage(data, definitions)
    if "Belgium" not in data["context"]["geography"]:
        data["context"]["geography"] += (
            " Belgium's pre-UCI legal units, UCI legal units and2022+enterprises remain separate; "
            "its current FDI reporting-frame cutoffs are not backdated or treated as all Belgian firms.")
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
    selection.add_argument("--uk-history-only", action="store_true",
                           help="Review UK 2007-2009 counts; preserve later UK and other-country observations")
    selection.add_argument("--finland-history-only", action="store_true",
                           help="Review the separate longer Finnish-UCI Eurostat history; preserve national counts")
    selection.add_argument("--italy-only", action="store_true",
                           help="Review Italian legal units and enterprises separately; preserve other countries")
    selection.add_argument("--sweden-history-only", action="store_true",
                           help="Review the separate older Swedish-UCI Eurostat history; preserve national counts")
    selection.add_argument("--spain-only", action="store_true",
                           help="Review Spanish-controlled Eurostat enterprises; preserve all other countries")
    selection.add_argument("--denmark-only", action="store_true",
                           help="Review subsidiaries controlled from Denmark; preserve other countries")
    selection.add_argument("--austria-only", action="store_true",
                           help="Review separate Austrian legal-unit/enterprise cohorts; preserve other countries")
    selection.add_argument("--poland-only", action="store_true",
                           help="Review Polish-resident-UCI China enterprises; preserve other countries")
    selection.add_argument("--belgium-only", action="store_true",
                           help="Review Belgian pre-UCI/legal/enterprise populations separately; preserve other countries")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/business-presence/raw", args.refresh)
    collector = (collect_austria if args.austria_only else collect_italy if args.italy_only else
                 collect_uk_history if args.uk_history_only else
                 collect_sweden_history if args.sweden_history_only else
                 collect_belgium if args.belgium_only else
                 collect_poland if args.poland_only else
                 collect_denmark if args.denmark_only else collect_spain if args.spain_only else
                 collect_netherlands if args.netherlands_only else
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
