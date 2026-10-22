#!/usr/bin/env python3
"""Freeze text-free local Weibo research aggregates, then build publication figures."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic
from us_china_exchange.render import build
from us_china_exchange.weibo_analysis import create_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data/local/weibo.sqlite")
    args = parser.parse_args()
    summary = create_summary(args.db, ROOT / "data/registry/outlets.json")
    write_atomic(ROOT / "data/site/weibo_summary.json", json_text(summary))
    print(json_text(build(ROOT)), end="")
