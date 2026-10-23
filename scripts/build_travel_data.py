#!/usr/bin/env python3
"""Review destination visitor histories without replacing other exchange observations."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.pipeline import refresh
from us_china_exchange.sources import nbs_tourism
from us_china_exchange.travel_sources import siat


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--history-only", action="store_true")
    group.add_argument("--air-only", action="store_true")
    args = parser.parse_args()
    review = ReviewClient(ROOT / "data/local/contact-gaps/raw", args.refresh)
    adapters = {}
    if not args.air_only:
        adapters["nbs_tourism"] = nbs_tourism
    if not args.history_only:
        adapters["ntto_siat"] = lambda client: siat(review, args.refresh)
    result = refresh(ROOT, adapters=adapters, client=SimpleNamespace(
        get=review.get, now=datetime.now(timezone.utc).isoformat(timespec="seconds")))
    print(result)
