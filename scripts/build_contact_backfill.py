#!/usr/bin/env python3
"""Manually backfill verified government republications without accessing IIE."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.contact_backfill import government_student_history, hong_kong_visitors, mainland_students
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import coverage, json_text
from us_china_exchange.pipeline import refresh, write_atomic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch public government republications; never access IIE")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/contact-audit/raw", args.refresh)
    client.now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output = ROOT / "data/site"
    prior = json.loads((output / "observations.json").read_text())
    rows = government_student_history(client, prior)
    sources = json.loads((output / "sources.json").read_text())
    sources["iie"]["observations"] = sum(r["source_id"] == "iie" for r in rows)
    files = {"observations.json": rows, "sources.json": sources, "coverage.json": coverage(rows)}
    texts = {name: json_text(value) for name, value in files.items()}
    with TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(output, staging / "data/site")
        for name, content in texts.items():
            write_atomic(staging / "data/site" / name, content)
        report = refresh(staging, adapters={"moe": mainland_students, "hktb": hong_kong_visitors}, client=client)
        for name in texts:
            write_atomic(output / name, (staging / "data/site" / name).read_text())
    print(f"Government republications added {len(rows) - len(prior)} historical observations; direct IIE retrieval remains paused.")
    print(report)
