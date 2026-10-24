#!/usr/bin/env python3
"""Manually backfill reviewed education/tourism aggregates without accessing IIE."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.contact_backfill import (
    government_credit_history, government_enrollment_history, government_eric_history,
    government_mobility_history, government_student_history,
    hong_kong_visitors, mainland_students,
)
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import coverage, json_text
from us_china_exchange.pipeline import refresh, write_atomic
from us_china_exchange.sources import SOURCE_POLICIES


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch reviewed public republications; never access IIE")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--education-only", action="store_true", help="Review education histories without rechecking tourism")
    selection.add_argument("--enrollment-only", action="store_true", help="Review government-hosted academic-level tables; preserve other sources")
    selection.add_argument("--historical-only", action="store_true", help="Review pinned federal-deposit enrollment and credit histories; preserve other sources")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/contact-audit/raw", args.refresh)
    client.now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output = ROOT / "data/site"
    prior = json.loads((output / "observations.json").read_text())
    rows = prior
    if args.historical_only:
        rows = government_eric_history(client, rows)
    elif not args.enrollment_only:
        rows = government_student_history(client, rows)
        rows = government_credit_history(client, rows)
        rows = government_mobility_history(client, rows)
    if not args.historical_only:
        rows = government_enrollment_history(client, rows)
    sources = json.loads((output / "sources.json").read_text())
    sources["iie"]["observations"] = sum(r["source_id"] == "iie" for r in rows)
    sources["iie"]["notes"] = SOURCE_POLICIES["iie"]["notice"]
    files = {"observations.json": rows, "sources.json": sources, "coverage.json": coverage(rows)}
    texts = {name: json_text(value) for name, value in files.items()}
    with TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(output, staging / "data/site")
        for name, content in texts.items():
            write_atomic(staging / "data/site" / name, content)
        adapters = {} if args.enrollment_only or args.historical_only else {"moe": mainland_students}
        if not args.education_only and not args.enrollment_only and not args.historical_only:
            adapters["hktb"] = hong_kong_visitors
        report = refresh(staging, adapters=adapters, client=client)
        for name in texts:
            write_atomic(output / name, (staging / "data/site" / name).read_text())
    print(f"Government republications added {len(rows) - len(prior)} historical observations; direct IIE retrieval remains paused.")
    print(report)
