"""UBO-classified U.S. affiliate counts, with historical population breaks."""

import copy
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import xlrd
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from pypdf import PdfReader

from .model import json_text
from .pipeline import write_atomic


GEOGRAPHIES = {"CHN": "China", "HKG": "Hong Kong"}


def parse_counts(content, source):
    notes = ""
    member = source["table_member"]
    if member:
        archive = zipfile.ZipFile(io.BytesIO(content))
        notes = " ".join(" ".join(page.extract_text() or "" for page in
                         PdfReader(io.BytesIO(archive.read(source["definition_member"]))).pages).split())
        content = archive.read(member)
    if content.startswith(b"PK"):
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        rows = list(book[source["worksheet"]].values)
        book.close()
    else:
        book = xlrd.open_workbook(file_contents=content)
        sheet = book.sheet_by_name(source["worksheet"])
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        book.release_resources()
    header = " ".join(str(v) for row in rows[:8] for v in row)
    if "Country of UBO" not in header or not re.search("Number of (?:Affiliates|affiliates)", header):
        raise ValueError("Expected affiliate counts by country of UBO, not another population")
    if not any(re.search(r"^(?:Total|Number of affiliates\b.*)$", str(row[1]).strip(), re.I) for row in rows[:8]):
        raise ValueError("The count column must be affiliates, not consolidated companies or money")
    match = re.search(r"Greater Than\s*\$\s*(\d+)\s*Million", header, re.I)
    if not match and notes:
        pattern = (r"Tables\s+J[\s-]*2\s+and\s+J[\s-]*3" if source["year"] <= 2001 else
                   r"Tables\s+III[ .-]*A[ .-]*4\s+and\s+III[ .-]*A[ .-]*5")
        start = re.search(pattern, notes, re.I)
        if start:
            match = re.search(r"greater than\s*\$\s*(\d+)\s*million",
                              notes[start.start():start.start() + 1800], re.I)
    if not match or int(match[1]) * 1_000_000 != source["size_threshold_usd"]:
        raise ValueError("Published count threshold differs or requires review")
    result = {}
    for i, row in enumerate(rows, 1):
        for geo, label in GEOGRAPHIES.items():
            if str(row[0]).strip() != label:
                continue
            if geo in result or source["cells"][geo] != f"B{i}":
                raise ValueError("Duplicate or moved affiliate country cell")
            value = row[1]
            if isinstance(value, str):
                value = value.strip()
                if value in {"D", "(D)"}:
                    result[geo] = (None, "suppressed")
                    continue
                if re.fullmatch(r"\d+|\d{1,3}(?:,\d{3})+", value):
                    value = int(value.replace(",", ""))
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0 or value != int(value)):
                raise ValueError("Invalid count or unreviewed range; never fill with zero")
            result[geo] = (int(value), source["status"])
    if set(result) != set(GEOGRAPHIES):
        raise ValueError("Both separately reported China and Hong Kong counts are required")
    return result


def validate(data):
    if data.get("version") != 1 or not data.get("context"):
        raise ValueError("Invalid inward-affiliate dataset")
    cutoff = date.fromisoformat(data["as_of"])
    if set(data["series"]) != {"bea_mousa:" + geo for geo in GEOGRAPHIES}:
        raise ValueError("Mainland and Hong Kong must remain separately identified")
    for sid, definition in data["series"].items():
        if (definition["unit"] != "affiliates" or definition["country_basis"] != "UBO"
                or definition["origin"] != sid.split(":")[1] or definition["destination"] != "USA"
                or definition["measure"] != "majority_owned_us_affiliates"
                or definition["period_basis"] != "fiscal ending year"):
            raise ValueError("Affiliate ownership, direction, period or counting unit changed")
    for source in data["sources"].values():
        if ("majority-owned" not in source["scope"].lower()
                or source["bank_coverage"] not in {"nonbank_only", "including_banks"}
                or ("nonbank" in source["scope"].lower()) != (source["bank_coverage"] == "nonbank_only")
                or source["size_threshold_usd"] not in {3_000_000, 10_000_000, 15_000_000, 20_000_000}
                or source["status"] not in {"observed", "provisional"}
                or set(source["cells"]) != set(GEOGRAPHIES)):
            raise ValueError("Unreviewed affiliate population or threshold")
        for asset in [source["asset"]] + ([source["page_asset"]] if source.get("page_asset") else []):
            if (not re.fullmatch("[0-9a-f]{64}", asset["sha256"]) or not asset["url"].startswith("https://")
                    or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None):
                raise ValueError("Invalid original affiliate source provenance")
    seen = set()
    for row in data["observations"]:
        source = data["sources"][row["source_id"]]
        key = row["series_id"], row["year"]
        if key in seen or row["series_id"] not in data["series"]:
            raise ValueError("Duplicate or unknown affiliate observation")
        seen.add(key)
        if (type(row["year"]) is not int or not 2000 <= row["year"] <= cutoff.year
                or row["year"] != source["year"]
                or row["bank_coverage"] != source["bank_coverage"]
                or row["size_threshold_usd"] != source["size_threshold_usd"]
                or row["comparability"] != f'{source["bank_coverage"]}:USD{source["size_threshold_usd"]}'):
            raise ValueError("Affiliate year or comparability block changed")
        if row["status"] not in {"observed", "provisional", "suppressed"}:
            raise ValueError("Unreviewed affiliate status")
        if row["value"] is not None and row["status"] != source["status"]:
            raise ValueError("Affiliate release status differs from its source")
        if ((row["value"] is None) != (row["status"] == "suppressed")
                or row["value"] is not None and (type(row["value"]) is not int or row["value"] < 0)):
            raise ValueError("Affiliate missingness or count changed")
    if not seen:
        raise ValueError("No reported affiliate evidence")
    return data


def rebuild(data, cache):
    result = copy.deepcopy(validate(data))
    observations = []
    for source_id, source in sorted(data["sources"].items(), key=lambda item: item[1]["year"]):
        asset = source["asset"]
        content = (Path(cache) / asset["sha256"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Original affiliate workbook checksum mismatch")
        if source.get("page_asset"):
            page_asset = source["page_asset"]
            page = (Path(cache) / page_asset["sha256"]).read_bytes()
            if hashlib.sha256(page).hexdigest() != page_asset["sha256"]:
                raise ValueError("Original affiliate index checksum mismatch")
            text = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
            if source["scope"] not in text or str(source["year"]) not in text:
                raise ValueError("Affiliate table's primary scope or year differs")
        for geo, (value, status) in parse_counts(content, source).items():
            observations.append({
                "series_id": "bea_mousa:" + geo, "year": source["year"], "value": value,
                "source_id": source_id, "status": status, "period": str(source["year"]),
                "bank_coverage": source["bank_coverage"], "size_threshold_usd": source["size_threshold_usd"],
                "comparability": f'{source["bank_coverage"]}:USD{source["size_threshold_usd"]}',
            })
    result["observations"] = sorted(observations, key=lambda row: (row["year"], row["series_id"]))
    return validate(result)


def export(data, directory):
    validate(data)
    rows = []
    for row in data["observations"]:
        source = data["sources"][row["source_id"]]
        geo = row["series_id"].split(":")[1]
        rows.append(dict(row, **data["series"][row["series_id"]],
                         source_url=source["asset"]["url"], raw_sha256=source["asset"]["sha256"],
                         retrieved_at=source["asset"]["retrieved_at"], source_vintage=source["vintage"],
                         table_member=source["table_member"], worksheet=source["worksheet"],
                         cell=source["cells"][geo], source_scope=source["scope"],
                         definition_member=source["definition_member"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    directory = Path(directory)
    write_atomic(directory / "business-inward.json", json_text(data))
    write_atomic(directory / "business-inward-observations.csv", stream.getvalue())
