#!/usr/bin/env python3
"""Write a research coverage inventory from complete publication downloads."""

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_china_exchange.model import json_text
from us_china_exchange.pipeline import write_atomic
from us_china_exchange.series_inventory import inventory_publication


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Research audit directory, not the public website")
    parser.add_argument("--target-year", type=int, default=date.today().year)
    args = parser.parse_args()
    if args.output.resolve() == args.site.resolve() or args.site.resolve() in args.output.resolve().parents:
        parser.error("Keep operational inventory outputs outside the public publication")
    report = inventory_publication(args.site, args.target_year)
    write_atomic(args.output / "series-inventory.json", json_text(report))
    stream = io.StringIO(newline="")
    fields = list(report["series"][0])
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                     for key, value in row.items()} for row in report["series"])
    write_atomic(args.output / "series-inventory.csv", stream.getvalue())
    print(json_text({
        "datasets": len(report["datasets"]), "inventory_rows": len(report["series"]),
        "rendered_series": report["rendered_series"],
        "json": str(args.output / "series-inventory.json"),
        "csv": str(args.output / "series-inventory.csv"),
    }), end="")
