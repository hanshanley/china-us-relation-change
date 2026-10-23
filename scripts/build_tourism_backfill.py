#!/usr/bin/env python3
"""Recover reviewed visitor histories and current monthly government releases."""

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.contact_backfill import hong_kong_visitors
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.pipeline import refresh, write_atomic
from us_china_exchange.tourism_backfill import macau_recent


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch the reviewed public source documents")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/itemized-gaps/raw", args.refresh)
    client.now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(ROOT / "data/site", staging / "data/site")
        report = refresh(staging, adapters={"hktb": hong_kong_visitors,
                                           "macau_tourism": macau_recent}, client=client)
        for name in ("observations.json", "sources.json", "coverage.json"):
            write_atomic(ROOT / "data/site" / name, (staging / "data/site" / name).read_text())
    print(report)
