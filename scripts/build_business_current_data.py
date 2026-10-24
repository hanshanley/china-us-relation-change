#!/usr/bin/env python3
"""Rebuild the reviewed October 2026 business snapshot from permitted cached sources."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.business_current import reviewed_snapshot
from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic


class ReviewedCache:
    def __init__(self, directory):
        self.directory = directory
        self.assets = json.loads((directory / "assets.json").read_text())

    def get(self, url):
        asset = self.assets[url]
        content = (self.directory / asset["sha256"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Reviewed primary-source checksum mismatch")
        return content, asset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bea-cache", type=Path, required=True)
    parser.add_argument("--survey-cache", type=Path, required=True)
    args = parser.parse_args()
    data = reviewed_snapshot(ReviewedCache(args.bea_cache), ReviewedCache(args.survey_cache))
    write_atomic(ROOT / "data/site/business_current.json", json_text(data))
    print(f"Frozen {len(data['observations'])} current business observations; no network requests.")
