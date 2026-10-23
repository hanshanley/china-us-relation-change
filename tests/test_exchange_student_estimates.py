import copy
import csv
import json
from pathlib import Path

import pytest

from us_china_exchange.student_estimates import export, panel, reported, validate


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/student_estimates.json").read_text())


def test_dated_estimates_preserve_bounds_and_distinguish_annual_participation_from_presence():
    data = validate(published())
    assert [reported(row) for row in data["observations"]] == ["About 350", "700", "880", ">1,100", "<2,000 per year"]
    upper = data["observations"][-1]
    assert upper["value"] is None and upper["bound"] == 2000
    assert upper["measurement"] == "annual_participation_estimate"
    bad = copy.deepcopy(data)
    bad["observations"][-1]["value"] = 2000
    with pytest.raises(ValueError, match="exact count"):
        validate(bad)


def test_estimate_exports_contain_actual_values_bounds_dates_and_source_evidence(tmp_path):
    data = published()
    export(tmp_path, data)
    assert json.loads((tmp_path / "site/downloads/student-estimates.json").read_text()) == data
    rows = list(csv.DictReader((tmp_path / "site/downloads/student-estimates.csv").open()))
    assert len(rows) == len(data["observations"]) == 5
    assert rows[-1]["value"] == "" and rows[-1]["bound"] == "2000"
    assert all(len(row["sha256"]) == 64 and row["statement_date"] for row in rows)
    html = panel(data)
    assert "&lt;2,000 per year" in html and "&gt;1,100" in html
    assert "not an extension" in html
