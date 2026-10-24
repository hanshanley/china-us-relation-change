#!/usr/bin/env python3
"""Recover reviewed visitor histories and current monthly government releases."""

import argparse
import json
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
from us_china_exchange.sources import bea_expanded
from us_china_exchange.tourism_backfill import dsec_recent_visitors, macau_recent, macau_services_history, reviewed_hktb_months


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch the reviewed public source documents")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--services-only", action="store_true", help="Review current and archived services without rechecking tourism")
    selection.add_argument("--dsec-only", action="store_true", help="Review the latest DSEC country workbook without rechecking older sources")
    selection.add_argument("--hktb-reviewed-only", action="store_true", help="Validate versioned HKTB monthly facts against retained cumulative totals")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/itemized-gaps/raw", args.refresh)
    client.now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(ROOT / "data/site", staging / "data/site")
        prior = json.loads((staging / "data/site/observations.json").read_text())
        adapters = ({"hktb": lambda c: reviewed_hktb_months(
            (ROOT / "data/reviewed/hktb-monthly-2026-08.json").read_bytes(), prior, c.now)}
                    if args.hktb_reviewed_only else
                    {"macau_tourism": dsec_recent_visitors} if args.dsec_only else
                    {"ustr": macau_services_history, "bea_expanded": bea_expanded})
        if not args.services_only and not args.dsec_only and not args.hktb_reviewed_only:
            adapters.update(hktb=hong_kong_visitors, macau_tourism=macau_recent)
        report = refresh(staging, adapters=adapters, client=client)
        for name in ("observations.json", "sources.json", "coverage.json"):
            write_atomic(ROOT / "data/site" / name, (staging / "data/site" / name).read_text())
    print(report)
