"""Reviewed source-table checkpoints, not generated expected values."""
import json
from pathlib import Path

import pytest

from us_china_exchange.model import validate


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/observations.json").read_text())


def reviewed_snapshot():
    # Freeze the independently reviewed vintage, not future legitimate revisions.
    return json.loads((ROOT / "tests/fixtures/exchange_reviewed_2026-10-21.json").read_text())


@pytest.mark.parametrize("origin,destination,measure,baseline,latest", [
    ("CHN", "USA", "goods", 432582, 309039),
    ("USA", "CHN", "goods", 125145, 107002),
    ("CHN", "USA", "services", 16275, 22768),
    ("USA", "CHN", "services", 40931, 57196),
    ("HKG", "USA", "goods", 8249, 5436),
    ("USA", "HKG", "goods", 24170, 34384),
    ("HKG", "USA", "services", 9759, 15541),
    ("USA", "HKG", "services", 12568, 16857),
    ("TWN", "USA", "goods", 60442, 201456),
    ("USA", "TWN", "goods", 30522, 55080),
    ("TWN", "USA", "services", 6422, 12599),
    ("USA", "TWN", "services", 9322, 14864),
])
def test_reviewed_bea_million_dollar_checkpoints(origin, destination, measure, baseline, latest):
    index = {(r["origin"], r["destination"], r["measure"], r["year"]): r["value"]
             for r in reviewed_snapshot() if r["source_id"] == "bea" and r["frequency"] == "annual"}
    assert index[(origin, destination, measure, 2020)] == baseline * 1_000_000
    assert index[(origin, destination, measure, 2025)] == latest * 1_000_000


@pytest.mark.parametrize("source,origin,destination,measure,year,value", [
    ("ntto", "CHN", "USA", "visitors", 2020, 378080),
    ("ntto", "CHN", "USA", "visitors", 2025, 1562458),
    ("ntto", "HKG", "USA", "visitors", 2025, 86692),
    ("ntto", "MAC", "USA", "visitors", 2025, 3409),
    ("ntto", "TWN", "USA", "visitors", 2025, 427470),
    ("taiwan_tourism", "USA", "TWN", "visitors", 2020, 82872),
    ("taiwan_tourism", "USA", "TWN", "visitors", 2025, 715481),
    ("iie", "CHN", "USA", "international_students", 2020, 372532),
    ("iie", "CHN", "USA", "international_students", 2025, 265919),
    ("iie", "HKG", "USA", "international_students", 2025, 5492),
    ("iie", "MAC", "USA", "international_students", 2025, 397),
    ("iie", "TWN", "USA", "international_students", 2025, 23263),
    ("iie", "USA", "CHN", "study_abroad", 2024, 1749),
    ("macau_tourism", "USA", "MAC", "visitors", 2020, 13489),
    ("macau_tourism", "USA", "MAC", "visitors", 2025, 162460),
])
def test_reviewed_people_checkpoints(source, origin, destination, measure, year, value):
    row = next(r for r in reviewed_snapshot() if
               (r["source_id"], r["origin"], r["destination"], r["measure"], r["year"], r["frequency"])
               == (source, origin, destination, measure, year, "annual"))
    assert row["value"] == value


def test_publication_has_no_duplicate_keys_and_complete_provenance():
    rows = published()
    assert validate(rows)
    assert all(len(r["raw_sha256"]) == 64 and r["source_url"].startswith("https://") for r in rows)
    assert not any(r["period_start"] is not None for r in rows if r["period_basis"] == "academic")
