import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from us_china_exchange.theme import png_dimensions
from bs4 import BeautifulSoup

from us_china_exchange.state_immigration_map import build_state_map, fill, map_paths
from us_china_exchange.state_immigration_sources import (
    FIELDS, STATE_FIPS, geometry_text, parse_states, released_directory, validate,
)


ROOT = Path(__file__).resolve().parents[1]


def published():
    return (json.loads((ROOT / "data/site/state_immigration.json").read_text()),
            json.loads((ROOT / "data/site/us_states.geojson").read_text()))


def table_prefix(omit=None, missing=None):
    columns = ["GEO_ID"] + [f"B05006_{kind}{code}" for code in FIELDS.values() for kind in ("E", "M")]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, delimiter="|", lineterminator="\n")
    writer.writeheader()
    for fips in ["US"] + sorted(STATE_FIPS):
        if fips == omit:
            continue
        scale = 51 if fips == "US" else 1
        values = {"foreign_born": 1000, "china_parent": 120, "china_born": 100,
                  "hong_kong_born": 10, "taiwan_born": 10}
        row = {"GEO_ID": "0100000US" if fips == "US" else "0400000US" + fips}
        for field, code in FIELDS.items():
            row[f"B05006_E{code}"] = values[field] * scale
            row[f"B05006_M{code}"] = 5
        if fips == missing:
            row["B05006_E050"] = "N"
        writer.writerow(row)
    return stream.getvalue().encode()


def test_summary_file_selection_excludes_nested_hong_kong_and_taiwan():
    _, geometry = published()
    states, national = parse_states(table_prefix(), geometry)
    assert len(states) == 51
    assert states[0]["china_born"] == 100
    assert states[0]["china_parent"] == 120
    assert states[0]["share_percent"] == 10
    assert national["china_born"] == 5100
    assert sum(row["china_born"] for row in states) == national["china_born"]
    with pytest.raises(ValueError, match="every state"):
        parse_states(table_prefix(omit="56"), geometry)
    with pytest.raises(ValueError, match="every state"):
        parse_states(table_prefix().rstrip(b"\n"), geometry)


def test_suppressed_estimate_is_not_zero_or_recovered_by_subtraction():
    _, geometry = published()
    states, _ = parse_states(table_prefix(missing="56"), geometry)
    row = next(s for s in states if s["fips"] == "56")
    assert row["china_born"] is None
    assert row["share_percent"] is None
    assert row["china_parent"] == 120 and row["hong_kong_born"] == row["taiwan_born"] == 10
    assert fill(None, "count") != fill(0, "count")
    assert fill(None, "share") != fill(0, "share")


def test_unreleased_year_or_metadata_link_does_not_select_a_new_vintage():
    url = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/"
    assert released_directory(f'<a href="{url}">5-Year Summary File</a>', 2024) == url
    assert released_directory(f'<a href="{url}">5-Year Summary File</a>', 2025) is None
    assert released_directory('<a href="https://api.census.gov/data/2025/acs/acs5/groups.json">Metadata</a>', 2025) is None
    assert released_directory(f'<a href="{url}">1-Year Summary File</a>', 2024) is None


def test_frozen_states_reconcile_with_national_control_and_source_cells():
    data, geometry = published()
    assert validate(data, geometry) is data
    assert len(data["states"]) == 51
    assert all(row["china_born"] is not None for row in data["states"])
    assert sum(s["china_born"] for s in data["states"]) == data["national"]["china_born"]
    assert sum(s["foreign_born"] for s in data["states"]) == data["national"]["foreign_born"]
    assert data["start_year"] == data["end_year"] - 4
    assert len(data["sources"]["table"]["sha256"]) == 64
    assert data["sources"]["table"]["sha256_scope"].startswith("Retrieved file prefix")


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d["states"].pop(), "50 states"),
    (lambda d: d.update(population="Chinese nationality"), "birthplace"),
    (lambda d: d.update(survey="ACS one-year estimates"), "period"),
    (lambda d: d.update(start_year=d["start_year"] + 1, end_year=d["end_year"] + 1), "vintage"),
    (lambda d: d["states"][0].update(share_percent=100), "denominator"),
    (lambda d: d["states"][0].update(china_born=0), "reported cell"),
    (lambda d: d["states"][0].update(geo_id="0400000US72"), "geography"),
])
def test_invalid_state_scope_period_denominator_or_join_is_rejected(mutation, match):
    data, geometry = published()
    mutation(data)
    with pytest.raises(ValueError, match=match):
        validate(data, geometry)


def test_duplicate_or_mismatched_geometry_is_not_silently_joined():
    data, geometry = published()
    geometry["features"][0]["properties"]["NAME"] = "Wrong state"
    data["geometry_sha256"] = hashlib.sha256(geometry_text(geometry).encode()).hexdigest()
    with pytest.raises(ValueError, match="join"):
        validate(data, geometry)


def test_map_exports_and_downloads_preserve_every_state_and_both_measures(tmp_path):
    data, geometry = published()
    gallery = {"immigration": []}
    markup = build_state_map(tmp_path, data, geometry, gallery)
    soup = BeautifulSoup(markup, "html.parser")
    assert len(soup.select(".state-shape")) == 51
    assert len(soup.select("[data-state-row]")) == 51
    assert len(soup.select("#state-map-select option")) == 52
    assert soup.select_one(".state-map-controls").has_attr("hidden")
    assert soup.select_one(".state-callout")["data-state-fips"] == "11"
    assert json.loads(soup.select_one(".state-map-data").string)["states"] == data["states"]
    assert json.loads((tmp_path / "site/downloads/state-immigration.json").read_text()) == data
    rows = list(csv.DictReader(io.StringIO((tmp_path / "site/downloads/state-immigration.csv").read_text())))
    assert len(rows) == 51
    expected = {r["fips"]: r for r in data["states"]}
    for row in rows:
        point = expected[row["fips"]]
        assert int(row["china_born"]) == point["china_born"]
        assert float(row["share_percent"]) == point["share_percent"]
        assert row["B05006_E050"] == point["reported_cells"]["B05006_E050"]
    assert len(gallery["immigration"]) == 2
    for theme, background in (("substack", "#F5F5F5"), ("themarginoferror", "#F7F5F0")):
        for metric in ("share", "count"):
            path = tmp_path / f"outputs/figures/immigration/{theme}/state-china-{metric}.svg"
            svg = BeautifulSoup(path.read_text(), "html.parser")
            assert svg.svg["data-state-map"] == metric
            assert svg.rect["fill"] == background
            assert len(svg.select(".state-shape")) == 51
            for mark in svg.select(".state-shape"):
                row = expected[mark["data-state-fips"]]
                assert float(mark["data-china-born"]) == row["china_born"]
                value = row["share_percent"] if metric == "share" else row["china_born"]
                assert mark["fill"] == fill(value, metric)
            png = path.with_suffix(".png").read_bytes()
            assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == png_dimensions(path.read_text())


def test_simplified_map_retains_all_states_and_the_dateline_inset():
    _, geometry = published()
    paths, dc = map_paths(geometry)
    assert paths.keys() == STATE_FIPS
    assert all(path.startswith("M") and path.endswith("Z") for path in paths.values())
    assert all("nan" not in path and "inf" not in path for path in paths.values())
    assert 700 < dc[0] < 950 and 100 < dc[1] < 480


def test_new_fetch_timestamps_and_page_markup_do_not_create_daily_data_revisions():
    import importlib.util

    spec = importlib.util.spec_from_file_location("state_collector", ROOT / "scripts/build_state_immigration_data.py")
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    data, _ = published()
    checked = copy.deepcopy(data)
    checked["sources"]["release"]["sha256"] = "0" * 64
    checked["sources"]["table"]["retrieved_at"] = "2030-01-01T00:00:00+00:00"
    assert collector.stable(data) == collector.stable(checked)
    checked["states"][0]["china_born"] += 1
    assert collector.stable(data) != collector.stable(checked)
