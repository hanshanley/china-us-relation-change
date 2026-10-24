"""State-level birthplace estimates from the public Census summary files."""

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime
from urllib.parse import urlencode, urlsplit

import requests
from bs4 import BeautifulSoup


STATE_FIPS = set(
    "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 "
    "27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 "
    "50 51 53 54 55 56".split()
)
POPULATION = "China, excluding Hong Kong and Taiwan"
UNIVERSE = "Foreign-born population excluding population born at sea"
FIELDS = {
    "foreign_born": "001", "china_parent": "049", "china_born": "050",
    "hong_kong_born": "051", "taiwan_born": "052",
}
PREFIX_BYTES = 1048576
GEOMETRY_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "Generalized_ACS2024/State_County/MapServer/8/query?"
    + urlencode({"where": "GEOID NOT IN ('60','66','69','72','78')",
                 "outFields": "GEOID,STUSAB,NAME", "outSR": "4326",
                 "returnGeometry": "true", "f": "geojson", "geometryPrecision": 3})
)
MISSING = {"", ".", "-", "**", "***", "N", "(X)", "-222222222", "-333333333",
           "-555555555", "-666666666", "-888888888", "-999999999"}


def geometry_text(geometry):
    return json.dumps(geometry, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def released_directory(content, year):
    soup = BeautifulSoup(content, "html.parser")
    expected = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/"
    return next((a["href"] for a in soup.select("a[href]")
                 if a.get_text(" ", strip=True) == "5-Year Summary File" and a["href"] == expected), None)


def validate_variables(metadata):
    variables = metadata["variables"]
    expected = {"001": "Estimate!!Total:", "050": "!!" + POPULATION,
                "049": "!!China:", "051": "!!Hong Kong", "052": "!!Taiwan"}
    for code, ending in expected.items():
        entry = variables[f"B05006_{code}E"]
        if (not entry["label"].endswith(ending) or
                entry["concept"] != "Place of Birth for the Foreign-Born Population in the United States"):
            raise ValueError("Census birthplace category or table universe changed")


def public_table_prefix(client, url):
    byte_range = f"bytes=0-{PREFIX_BYTES - 1}"
    cache_key = f"GET {url} Range {byte_range}"
    prior = client.assets.get(cache_key)
    path = client.cache / prior["sha256"] if prior else None
    if prior and not client.refresh and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == prior["sha256"]:
        content, asset = path.read_bytes(), prior
    else:
        with requests.get(url, headers={"Range": byte_range}, stream=True, timeout=90) as response:
            response.raise_for_status()
            if response.status_code == 206 and not re.fullmatch(
                    rf"bytes 0-{PREFIX_BYTES - 1}/\d+", response.headers.get("Content-Range", "")):
                raise ValueError("Unexpected Census table byte range")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                chunks.append(chunk[:PREFIX_BYTES - size])
                size += len(chunks[-1])
                if size == PREFIX_BYTES:
                    break
            content, asset = client.remember(url, b"".join(chunks), response.url, cache_key)
    return content, dict(asset, byte_range=byte_range,
                        sha256_scope="Retrieved file prefix, not the complete nationwide table file")


def census_count(value):
    if value in MISSING:
        return None
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"Unexpected Census count: {value!r}")
    return int(value)


def parse_states(content, geometry):
    records = {}
    # A range may end mid-record. Only complete lines participate in the selection.
    text = content[:content.rfind(b"\n") + 1].decode("utf-8-sig")
    for row in csv.DictReader(io.StringIO(text), delimiter="|"):
        geo_id = row["GEO_ID"]
        if geo_id == "0100000US" or re.fullmatch(r"0400000US\d{2}", geo_id):
            if geo_id in records:
                raise ValueError("Duplicate Census state/national record")
            records[geo_id] = row
    features = {f["properties"]["GEOID"]: f for f in geometry["features"]}
    if set(features) != STATE_FIPS or len(geometry["features"]) != 51:
        raise ValueError("Map geometry must cover exactly 50 states and DC")
    needed = {"0100000US"} | {"0400000US" + fips for fips in STATE_FIPS}
    if not needed <= records.keys():
        raise ValueError("Census table prefix does not contain every state and the national control")

    def point(geo_id, fips, name, postal):
        row = records[geo_id]
        result = {"fips": fips, "name": name, "postal": postal, "geo_id": geo_id, "reported_cells": {}}
        for field, code in FIELDS.items():
            for suffix, kind in (("", "E"), ("_moe", "M")):
                variable = f"B05006_{kind}{code}"
                result["reported_cells"][variable] = row[variable]
                result[field + suffix] = census_count(row[variable])
        numerator, denominator = result["china_born"], result["foreign_born"]
        result["share_percent"] = 100 * numerator / denominator if numerator is not None and denominator else None
        return result

    states = [point("0400000US" + fips, fips, features[fips]["properties"]["NAME"],
                    features[fips]["properties"]["STUSAB"]) for fips in sorted(STATE_FIPS)]
    national = point("0100000US", "US", "United States", "US")
    return states, national


def collect(client, year):
    release_url = f"https://www.census.gov/programs-surveys/acs/data/summary-file.{year}.html"
    page, release_asset = client.get(release_url)
    directory = released_directory(page, year)
    if directory is None:
        raise ValueError(f"The {year} ACS five-year summary file is not yet released")
    metadata, variable_asset = client.get(f"https://api.census.gov/data/{year}/acs/acs5/groups/B05006.json")
    validate_variables(json.loads(metadata))
    content, table_asset = public_table_prefix(client, directory + f"acsdt5y{year}-b05006.dat")
    raw_geometry, geometry_asset = client.get(GEOMETRY_URL)
    geometry = json.loads(raw_geometry)
    geometry["features"].sort(key=lambda f: f["properties"]["GEOID"])
    states, national = parse_states(content, geometry)
    data = {
        "version": 1, "survey": "ACS five-year estimates", "table": "B05006",
        "start_year": year - 4, "end_year": year,
        "population": POPULATION, "universe": UNIVERSE, "moe_confidence_percent": 90,
        "variables": dict(FIELDS), "states": states, "national": national,
        "geometry_file": "us-states.geojson", "geometry_vintage": 2024,
        "geometry_sha256": hashlib.sha256(geometry_text(geometry).encode()).hexdigest(),
        "sources": {"release": release_asset, "variables": variable_asset,
                    "table": table_asset, "geometry": geometry_asset},
        "notes": "Five-year period estimates, not counts for the final year, new arrivals, ancestry or citizenship. "
                 "Share is China-born residents divided by all foreign-born residents, excluding those born at sea. "
                 "Hong Kong and Taiwan are excluded from the numerator; Macau is not separately identified. "
                 "All 51 state/DC rows use the same period and table. Source margins of error are 90% confidence; "
                 "the derived percentage is a point estimate with no calculated percentage margin of error.",
    }
    return validate(data, geometry), geometry


def validate(data, geometry):
    if (data["version"] != 1 or data["survey"] != "ACS five-year estimates" or
            data["table"] != "B05006" or data["start_year"] != data["end_year"] - 4 or
            data["population"] != POPULATION or data["universe"] != UNIVERSE or
            data["variables"] != FIELDS or data["moe_confidence_percent"] != 90):
        raise ValueError("State map must retain its birthplace, period, universe and uncertainty definitions")
    states = data["states"]
    if len(states) != 51 or {s["fips"] for s in states} != STATE_FIPS:
        raise ValueError("State map requires exactly 50 states and DC")
    if len({s["postal"] for s in states}) != 51 or any(not re.fullmatch("[A-Z]{2}", s["postal"]) for s in states):
        raise ValueError("State postal codes must be unique")
    national = data["national"]
    if (national["fips"], national["name"], national["geo_id"]) != ("US", "United States", "0100000US"):
        raise ValueError("Incorrect national control")
    for row in states + [national]:
        if row["fips"] != "US" and row["geo_id"] != "0400000US" + row["fips"]:
            raise ValueError("State FIPS and Census geography do not match")
        if not row["name"]:
            raise ValueError("Missing state name")
        for field, code in FIELDS.items():
            for suffix, kind in (("", "E"), ("_moe", "M")):
                value = row[field + suffix]
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("Estimates and margins of error must be nonnegative integers or unavailable")
                if value != census_count(row["reported_cells"][f"B05006_{kind}{code}"]):
                    raise ValueError("Decoded Census value differs from the reported cell")
        n, d = row["china_born"], row["foreign_born"]
        expected = 100 * n / d if n is not None and d else None
        actual = row["share_percent"]
        if (expected is None and actual is not None) or (expected is not None and (
                not isinstance(actual, (int, float)) or not math.isfinite(actual) or abs(actual - expected) > 1e-10)):
            raise ValueError("State share uses the wrong denominator or value")
        if n is not None and d is not None and n > d:
            raise ValueError("China-born residents exceed the foreign-born universe")
        parts = [row[k] for k in ("china_parent", "china_born", "hong_kong_born", "taiwan_born")]
        if all(v is not None for v in parts) and parts[0] != sum(parts[1:]):
            raise ValueError("China parent category does not reconcile with China, Hong Kong and Taiwan")
    for field in FIELDS:
        if all(s[field] is not None for s in states) and national[field] is not None:
            if sum(s[field] for s in states) != national[field]:
                raise ValueError("State estimates do not reconcile with the national control")
    if not any(s["china_born"] is not None for s in states):
        raise ValueError("Map has no reported China-born estimates")
    if hashlib.sha256(geometry_text(geometry).encode()).hexdigest() != data["geometry_sha256"]:
        raise ValueError("Frozen geometry checksum does not match")
    features = geometry["features"]
    if geometry["type"] != "FeatureCollection" or len(features) != 51 or {
            f["properties"]["GEOID"] for f in features} != STATE_FIPS:
        raise ValueError("Geometry must have exactly 51 distinct state/DC features")
    index = {s["fips"]: s for s in states}
    for feature in features:
        props, shape = feature["properties"], feature["geometry"]
        row = index[props["GEOID"]]
        if props["STUSAB"] != row["postal"] or props["NAME"] != row["name"]:
            raise ValueError("State geometry/name join is inconsistent")
        if shape["type"] not in {"Polygon", "MultiPolygon"} or not shape["coordinates"]:
            raise ValueError("State polygon geometry is missing")
        polygons = [shape["coordinates"]] if shape["type"] == "Polygon" else shape["coordinates"]
        for polygon in polygons:
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1] or any(
                        len(p) != 2 or not all(math.isfinite(v) for v in p) or
                        not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90 for p in ring):
                    raise ValueError("Invalid geographic ring")
    for key, host in (("release", "www.census.gov"), ("variables", "api.census.gov"),
                      ("table", "www2.census.gov"), ("geometry", "tigerweb.geo.census.gov")):
        asset = data["sources"][key]
        if not re.fullmatch("[0-9a-f]{64}", asset["sha256"]) or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None:
            raise ValueError("State map provenance is incomplete")
        for field in ("url", "request_url"):
            parsed = urlsplit(asset[field])
            if parsed.scheme != "https" or parsed.netloc != host:
                raise ValueError("State map requires official Census sources")
    table = data["sources"]["table"]
    if table.get("byte_range") != f"bytes=0-{PREFIX_BYTES - 1}" or not table.get("sha256_scope"):
        raise ValueError("Partial-file checksum scope must be explicit")
    year = data["end_year"]
    expected = {
        "release": f"https://www.census.gov/programs-surveys/acs/data/summary-file.{year}.html",
        "variables": f"https://api.census.gov/data/{year}/acs/acs5/groups/B05006.json",
        "table": f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-b05006.dat",
        "geometry": GEOMETRY_URL,
    }
    if any(data["sources"][key]["request_url"] != url for key, url in expected.items()):
        raise ValueError("Source vintage or Census table does not match the map period")
    if data["geometry_file"] != "us-states.geojson" or data["geometry_vintage"] != 2024:
        raise ValueError("State geometry vintage and filename must remain explicit")
    return data
