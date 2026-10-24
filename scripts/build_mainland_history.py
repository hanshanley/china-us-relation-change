#!/usr/bin/env python3
"""Review older mainland student counts without refreshing unrelated sources."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.mainland_history import mainland_history
from us_china_exchange.model import coverage, json_text
from us_china_exchange.pipeline import write_atomic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write reviewed canonical data; otherwise retain a private candidate")
    args = parser.parse_args()
    site = ROOT / "data/site"
    names = ("observations.json", "coverage.json", "sources.json")
    baseline = {name: (site / name).read_bytes() for name in names}
    prior = json.loads(baseline["observations.json"])
    client = ReviewClient(ROOT / "data/local/mainland-student-recovery/raw")
    rows = mainland_history(client, prior)
    sources = json.loads(baseline["sources.json"])
    sources["moe"]["observations"] = sum(r["source_id"] == "moe" for r in rows)
    files = {"observations.json": rows, "coverage.json": coverage(rows), "sources.json": sources}
    if any((site / name).read_bytes() != baseline[name] for name in names):
        raise RuntimeError("Shared source data advanced during review; rerun against the new baseline")
    output = site if args.apply else ROOT / "data/local/mainland-student-recovery/candidate"
    for name, value in files.items():
        write_atomic(output / name, json_text(value))
    receipt = {
        "added": len(rows) - len(prior), "observations": len(rows), "applied": args.apply,
        "baseline_sha256": {name: hashlib.sha256(body).hexdigest() for name, body in baseline.items()},
        "output_sha256": {name: hashlib.sha256(json_text(value).encode()).hexdigest()
                          for name, value in files.items()},
    }
    write_atomic(ROOT / "data/local/mainland-student-recovery/review.json", json_text(receipt))
    print(json_text(receipt), end="")
