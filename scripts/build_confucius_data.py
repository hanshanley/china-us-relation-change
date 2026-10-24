#!/usr/bin/env python3
"""Collect reviewed Confucius-program facts, or check the public directory for changes."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.confucius_sources import DIRECTORY, collect, parse_directory, stable_directory, validate
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--check-only", action="store_true",
                        help="Detect changes without automatically reclassifying programs or replacing reviewed observations")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/confucius/raw", refresh=not args.cached)
    target = ROOT / "data/site/confucius_programs.json"
    prior = json.loads(target.read_text()) if target.exists() else None
    check = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        if args.check_only:
            if prior is None:
                raise ValueError("No reviewed program dataset exists")
            validate(prior)
            body, asset = client.get(DIRECTORY)
            current = parse_directory(body)
            previous = [r for r in prior["records"] if r["source_id"] == "cief_directory"]
            changed = stable_directory(previous) != stable_directory(current)
            check.update(status="review_required" if changed else "unchanged", directory_changed=changed,
                         records=len(current), asset=asset,
                         latest_verified_successor_report="2023-06-22",
                         note="Directory retrieval verifies listings only. Historical reports, replacements and current operating totals still require reviewed evidence.")
        else:
            data = collect(ROOT, client)
            write_atomic(target, json_text(data))
            check.update(status="reviewed", observations=len(data["observations"]), records=len(data["records"]))
    except Exception as exc:
        check.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        write_atomic(ROOT / "data/local/confucius/check.json", json_text(check))
        raise
    write_atomic(ROOT / "data/local/confucius/check.json", json_text(check))
    print(json_text(check), end="")


if __name__ == "__main__":
    main()
