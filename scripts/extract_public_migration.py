#!/usr/bin/env python3
"""Extract a separate, explicitly modelled U.S.-China migration dataset."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
REVISION = "b9709be5a89f02d2969a78c128995bd23ce81636"
SOURCE_URL = (
    "https://huggingface.co/datasets/ThGaskin/Migration_flows/resolve/"
    + REVISION + "/Estimates/mig_bilateral.csv")
SOURCE_SHA256 = "13f43848e3ec5effa03c5cfa643e220e86600db873d2ae5bdf6b6e921676d9b1"
LICENSE_NAME = "modelled-migration-us-china.LICENSE.txt"
LICENSE_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"
PAIRS = {("USA", "CHN"), ("CHN", "USA")}
FIELDS = ["", "Origin ISO", "Destination ISO", "Year", "stock_mean", "stock_std",
          "mig_prev", "mig_prev_std", "mig_brth", "mig_brth_std"]
NUMERIC = FIELDS[4:]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract(rows):
    chosen, seen = [], set()
    for r in rows:
        if (r["Origin ISO"], r["Destination ISO"]) not in PAIRS:
            continue
        key = r["Origin ISO"], r["Destination ISO"], int(r["Year"])
        if key in seen:
            raise ValueError("Duplicate bilateral model observation")
        seen.add(key)
        for field in NUMERIC:
            value = r[field]
            terminal_flow = key[2] == 2024 and field.startswith("mig_")
            if terminal_flow:
                if value != "":
                    raise ValueError("Terminal stock year must not become an invented flow")
            elif value == "" or not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError("Missing or invalid model value/uncertainty")
        chosen.append(r)
    expected = {(o, d, y) for o, d in PAIRS for y in range(1990, 2025)}
    if seen != expected:
        raise ValueError("Incomplete bilateral query; retain every source year")
    chosen.sort(key=lambda r: (r["Origin ISO"], r["Destination ISO"], int(r["Year"])))
    flows = [{
        "year": r["Year"], "origin": r["Origin ISO"], "destination": r["Destination ISO"],
        "mean": r["mig_prev"], "standard_deviation": r["mig_prev_std"],
        "status": "modelled_estimate", "unit": "estimated moves",
        "period_basis": "annual model year",
        "population": "previous residence; all birthplaces; not status- or citizenship-specific",
        "source_row_index": r[""],
    } for r in chosen if r["mig_prev"] != ""]
    return chosen, flows


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=ROOT / "data/local/migration-model/mig_bilateral.csv")
    parser.add_argument("--license-file", type=Path, default=ROOT / "data/reviewed" / LICENSE_NAME)
    parser.add_argument("--output", type=Path, default=ROOT / "data/reviewed")
    args = parser.parse_args()
    license_bytes = args.license_file.read_bytes()
    if hashlib.sha256(license_bytes).hexdigest() != LICENSE_SHA256:
        raise ValueError("Upstream licence checksum mismatch")
    if not args.source_csv.exists():
        args.source_csv.parent.mkdir(parents=True, exist_ok=True)
        partial = args.source_csv.with_suffix(".csv.part")
        try:
            with urlopen(SOURCE_URL, timeout=120) as response, partial.open("wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
            if sha256(partial) != SOURCE_SHA256:
                raise ValueError("Downloaded source checksum mismatch")
            partial.replace(args.source_csv)
        finally:
            partial.unlink(missing_ok=True)
    digest = sha256(args.source_csv)
    if digest != SOURCE_SHA256:
        raise ValueError("Source does not match the pinned publisher checksum")
    with args.source_csv.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError("Published model fields changed")
        chosen, flows = extract(reader)
    args.output.mkdir(parents=True, exist_ok=True)
    full_path = args.output / "modelled-migration-us-china-full-query.csv"
    flow_path = args.output / "modelled-migration-us-china.csv"
    write_csv(full_path, FIELDS, chosen)
    write_csv(flow_path, list(flows[0]), flows)
    (args.output / LICENSE_NAME).write_bytes(license_bytes)
    metadata = {
        "title": "Public modelled U.S.-China migration flows; NOT permanent-resident counts",
        "authors": ["Thomas Gaskin", "Guy J. Abel"],
        "paper_doi": "10.1038/s41586-026-10611-7",
        "dataset": "ThGaskin/Migration_flows",
        "source_url": SOURCE_URL, "source_revision": REVISION,
        "source_sha256": digest, "source_bytes": args.source_csv.stat().st_size,
        "license": "GPL-3.0", "license_file": LICENSE_NAME,
        "license_sha256": LICENSE_SHA256,
        "license_source_git_blob": "f288702d2fa16d3cdf0035b15a9fcbc552cd88e7",
        "license_source_url": "https://api.github.com/repos/ThGaskin/Migration_flows/git/blobs/"
                              "f288702d2fa16d3cdf0035b15a9fcbc552cd88e7",
        "reviewed_on": "2026-10-25",
        "changes": "Selected both USA/CHN directions and sorted source rows. "
                   "Normalized previous-residence flow fields separately; numerical strings unchanged.",
        "complete_query_rows": len(chosen), "annual_flow_rows": len(flows),
        "flow_years": [1990, 2023], "stock_years": [1990, 2024],
        "period_basis": "annual model year",
        "source_missingness": "2024 contains stocks only; flow cells are blank, not zero.",
        "geography": {"CHN": "China (156)", "USA": "United States of America (840)",
                      "HKG": "separate Hong Kong code (344)", "MAC": "separate Macao code (446)",
                      "TWN": "separate Taiwan code (158)"},
        "field_definitions": {
            "Year": "Annual model time coordinate; 2024 is a terminal stock year only.",
            "Origin ISO": "Previous residence for mig_prev; birthplace for stock_mean and mig_brth.",
            "Destination ISO": "Destination/residence country; CHN is separate from HKG, MAC and TWN.",
            "mig_prev": "Modelled origin-destination moves by previous residence; use this for geographic direction.",
            "mig_prev_std": "Publisher's standard deviation; not a 95% confidence bound.",
            "mig_brth": "Modelled birthplace-destination moves; origin field here means birthplace, not departure.",
            "mig_brth_std": "Publisher's standard deviation of the birthplace-destination flow estimate.",
            "stock_mean": "Modelled resident stock by birthplace, NOT annual immigration.",
            "stock_std": "Publisher's standard deviation of the resident-stock estimate.",
            "": "Original source-row index, preserved in the complete query.",
        },
        "limitations": [
            "Estimates, not observed administrative counts or permanent-residence grants.",
            "Not restricted to U.S. citizens or mainland-China-born migrants.",
            "Do not fill the missing FY2003-2005 official LPR arrivals with these values.",
            "Do not append these estimates to the official fiscal-year LPR series.",
        ],
        "observations": flows,
        "source_rows": chosen,
        "derived_files_sha256": {
            p.name: sha256(p) for p in (full_path, flow_path)},
    }
    (args.output / "modelled-migration-us-china.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(f"Saved {len(flows)} modelled annual flows and {len(chosen)} complete-query rows; official LPR data untouched.")


if __name__ == "__main__":
    main()
