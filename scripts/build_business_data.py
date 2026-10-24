#!/usr/bin/env python3
"""Explicitly collect reviewed business-presence aggregates; never a daily scrape."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_sources import collect_business, norwegian_affiliates
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refetch reviewed public assets instead of the local checksummed cache")
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--norway-only", action="store_true", help="Review Statistics Norway; preserve all other observations")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/business-presence/raw", args.refresh)
    data = (collect_norway(client, json.loads((ROOT / "data/site/business_presence.json").read_text()))
            if args.norway_only else collect_business(client))
    from us_china_exchange.business_analysis import validate_business_data
    validate_business_data(data)
    write_atomic(ROOT / "data/site/business_presence.json", json_text(data))
    print(f"Frozen {len(data['observations'])} business-presence observations.", flush=True)
    if not args.data_only:
        from us_china_exchange.render import build
        print(json_text(build(ROOT)), end="")
