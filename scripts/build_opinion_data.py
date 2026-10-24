#!/usr/bin/env python3
"""Recheck reviewed opinion sources without overwriting the last good snapshot on error."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.language_sources import ReviewClient
from us_china_exchange.model import json_text
from us_china_exchange.opinion_sources import REVIEWED_PATH, collect
from us_china_exchange.pipeline import write_atomic


def stable(data):
    return {k: v for k, v in data.items() if k != "sources"} | {
        "sources": {sid: {k: v for k, v in source.items() if k != "assets"}
                    for sid, source in data["sources"].items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true")
    args = parser.parse_args()
    path = ROOT / "data/site/opinions.json"
    check = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        data = collect(ReviewClient(ROOT / "data/local/opinions/cache", refresh=not args.cached),
                       (ROOT / REVIEWED_PATH).read_bytes())
        old = json.loads(path.read_text()) if path.exists() else None
        changed = old is None or stable(old) != stable(data)
        if changed:
            write_atomic(path, json_text(data))
        check.update(status="ok", changed=changed, observations=len(data["observations"]),
                     scope="Reviewed released tables and revisions; a new question or release URL requires source review.")
    except Exception as exc:
        check.update(status="error", changed=False, error=str(exc))
        raise
    finally:
        write_atomic(ROOT / "data/local/opinions/check.json", json_text(check))
        print(json_text(check))


if __name__ == "__main__":
    main()
