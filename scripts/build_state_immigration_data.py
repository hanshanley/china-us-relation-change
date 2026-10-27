#!/usr/bin/env python3
"""Refresh the complete state map from the latest actually released ACS five-year file."""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic
from us_china_exchange.state_immigration_sources import collect, fetch_released_directory, geometry_text


def stable(data):
    result = copy.deepcopy(data)
    result.pop("sources", None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int)
    parser.add_argument("--cached", action="store_true", help="Reuse checked local source downloads")
    args = parser.parse_args()
    client = ReviewClient(ROOT / "data/local/state-immigration/raw", refresh=not args.cached)
    target = ROOT / "data/site/state_immigration.json"
    prior = json.loads(target.read_text()) if target.exists() else None
    check = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "warnings": []}
    try:
        year = args.year
        if year is None:
            current = datetime.now(timezone.utc).year
            first = prior["end_year"] if prior else current - 3
            for candidate in range(current - 1, first - 1, -1):
                try:
                    directory, _ = fetch_released_directory(client, candidate)
                except Exception as exc:
                    check["warnings"].append(f"{candidate} release page: {type(exc).__name__}")
                    continue
                if directory:
                    year = candidate
                    break
            if year is None:
                raise ValueError("No released ACS five-year summary file could be verified")
        if prior and year < prior["end_year"]:
            raise ValueError("Refusing to replace the map with an older Census vintage")
        data, geometry = collect(client, year)
        changed = not prior or stable(data) != stable(prior)
        if changed:
            write_atomic(ROOT / "data/site/us_states.geojson", geometry_text(geometry))
            write_atomic(target, json_text(data))
        check.update(status="degraded" if check["warnings"] else "ok", end_year=year,
                     states=len(data["states"]), changed=changed)
    except Exception as exc:
        check.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        write_atomic(ROOT / "data/local/state-immigration/check.json", json_text(check))
        raise
    write_atomic(ROOT / "data/local/state-immigration/check.json", json_text(check))
    print(json_text(check), end="")


if __name__ == "__main__":
    main()
