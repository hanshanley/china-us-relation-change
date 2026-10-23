#!/usr/bin/env python3
"""Refresh permitted Weibo feeds privately; publish only source-audited aggregates."""

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weibo_media.refresh import refresh


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", action="append")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or (args.push and not args.publish):
        parser.error("Positive limit required; --push requires --publish")
    work = ROOT / "data/local/automation"
    work.mkdir(parents=True, exist_ok=True)
    with (work / "refresh.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another private refresh is already running")
        if args.publish and not subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
            subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, check=True)
            subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=ROOT, check=True)
        print(json.dumps(refresh(ROOT, account_ids=args.account, limit=args.limit,
                                 publish=args.publish, push=args.push), indent=2))
