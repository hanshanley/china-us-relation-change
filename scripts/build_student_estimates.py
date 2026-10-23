#!/usr/bin/env python3
"""Review dated primary estimates without pretending they form an annual census."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic
from us_china_exchange.student_estimates import collect

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    data = collect(ReviewClient(ROOT / "data/local/itemized-gaps/raw", args.refresh))
    write_atomic(ROOT / "data/site/student_estimates.json", json_text(data))
    print(f"Reviewed {len(data['observations'])} dated estimates/bounds; annual enrollment observations unchanged.")
