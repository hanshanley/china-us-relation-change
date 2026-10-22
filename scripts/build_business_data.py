#!/usr/bin/env python3
"""Explicitly collect reviewed business-presence aggregates; never a daily scrape."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_sources import collect_business
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refetch reviewed public assets instead of the local checksummed cache")
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    data = collect_business(ReviewClient(ROOT / "data/local/business-presence/raw", args.refresh))
    from us_china_exchange.business_analysis import validate_business_data
    validate_business_data(data)
    write_atomic(ROOT / "data/site/business_presence.json", json_text(data))
    print(f"Frozen {len(data['observations'])} business-presence observations.", flush=True)
    if not args.data_only:
        from us_china_exchange.render import build
        print(json_text(build(ROOT)), end="")
