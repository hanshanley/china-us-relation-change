#!/usr/bin/env python3
"""Manually review official immigration aggregates and freeze a validated snapshot."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.immigration_analysis import validate_immigration_data
from us_china_exchange.immigration_sources import collect
from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    data = validate_immigration_data(collect(ReviewClient(ROOT / "data/local/immigration/raw", args.refresh)))
    write_atomic(ROOT / "data/site/immigration.json", json_text(data))
    print(f"Reviewed {len(data['observations'])} immigration observations from {len(data['sources'])} official source assets.")
