#!/usr/bin/env python3
"""Reparse every reviewed inward-affiliate count from checksum-bound local originals."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_inward import export, rebuild
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/site/business_inward.json")
    parser.add_argument("--exports", type=Path)
    args = parser.parse_args()
    data = rebuild(json.loads((ROOT / "data/site/business_inward.json").read_text()), args.cache)
    write_atomic(args.output, json_text(data))
    if args.exports:
        export(data, args.exports)
    print(f"Rebuilt {len(data['observations'])} actual affiliate counts with explicit population breaks; no network.")
