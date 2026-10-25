import json
from pathlib import Path
import subprocess
import sys

import pytest

from us_china_exchange.series_inventory import inventory_publication, inventory_series


def dataset(rows, cadence="annual"):
    return {
        "series": {"count": {"label": "Count", "cadence": cadence, "scope": "Test population", "unit": "people"}},
        "observations": [dict(series_id="count", source_id="source", **row) for row in rows],
        "sources": {"source": {
            "last_recorded_check": "2026-10-24T11:00:00+00:00",
            "last_successful_retrieval": "2026-10-21T11:00:00+00:00",
            "assets": [{"url": "https://example.org/table", "retrieved_at": "2026-10-21T19:00:00+08:00"}]}},
    }


def test_exact_zero_and_nulls_do_not_refresh_the_measurement_or_invent_release_gaps():
    data = dataset([
        {"year": 2000, "value": 5, "comparability": "old"},
        {"year": 2001, "value": 0, "comparability": "old"},
        {"year": 2002, "value": None, "status": "suppressed"},
        {"year": 2003, "value": 7, "comparability": "new"},
        {"year": 2026, "value": None, "status": "missing"}])
    row, = inventory_series("test", data, {"count": {"index.html"}}, 2026)
    assert row["first_year"] == 2000 and row["latest_year"] == 2003
    assert row["reported_or_bounded_rows"] == 3
    assert row["internal_missing_periods"] == ["2002"]
    assert row["unreported_records"][-1] == {"period": "2026", "status": "missing"}
    assert row["uncovered_target_tail_years"] == list(range(2004, 2027))
    assert row["latest_recorded_source_check"] == "2026-10-24T11:00:00+00:00"
    assert row["latest_successful_retrieval"] in {
        "2026-10-21T11:00:00+00:00", "2026-10-21T19:00:00+08:00"}
    assert {b["comparability"] for b in row["comparison_blocks"]} == {"old", "new"}


@pytest.mark.parametrize("cadence", ["survey_rounds", "census_rounds", "snapshot", "benchmark"])
def test_irregular_periods_are_not_labelled_as_missing_annual_reports(cadence):
    data = dataset([{"year": 2000, "value": 5}, {"year": 2024, "value": 7}], cadence)
    row, = inventory_series("test", data, {}, 2026)
    assert row["internal_missing_periods"] is None
    assert row["reported_years"] == [2000, 2024]


def test_monthly_holes_and_matching_ytd_periods_are_kept_separate():
    data = dataset([
        {"year": 2025, "period": "2025-01", "frequency": "monthly", "value": 1},
        {"year": 2025, "period": "2025-03", "frequency": "monthly", "value": 2},
        {"year": 2025, "period_end": "2025-06-30", "frequency": "ytd", "value": 3},
        {"year": 2026, "period_end": "2026-06-30", "frequency": "ytd", "value": 4},
        {"year": 2026, "period_end": "2026-09-30", "frequency": "ytd", "value": 6}])
    rows = inventory_series("test", data, {}, 2026)
    assert len(rows) == 3
    monthly = next(r for r in rows if r["cadence"] == "monthly")
    assert monthly["internal_missing_periods"] == ["2025-02"]
    assert {r["matching_ytd_end_month"] for r in rows if r["cadence"] == "ytd"} == {"06", "09"}


def test_reference_dates_and_bounds_are_not_replaced_by_retrieval_years():
    data = dataset([{"reference": "2023-07", "value": None, "bound": 5, "qualifier": "less_than"}], "dated_observations")
    row, = inventory_series("test", data, {}, 2026)
    assert row["first_period"] == "2023-07" and row["latest_year"] == 2023
    assert row["reported_or_bounded_rows"] == 1
    assert row["internal_missing_periods"] is None


def test_rendered_series_must_have_complete_downloaded_observations(tmp_path):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads/exchange.json").write_text(json.dumps(dataset([{"year": 2024, "value": 1}])))
    model = {"kind": "series", "groups": [{"id": "count", "points": [{"year": 2024, "value": 1}]}]}
    page = tmp_path / "index.html"
    page.write_text('<script type="application/json">' + json.dumps(model) + "</script>")
    report = inventory_publication(tmp_path, 2026)
    assert report["rendered_series"] == 1
    assert report["series"][0]["rendered_on_pages"] == ["index.html"]
    model["groups"][0]["id"] = "metadata-only"
    page.write_text('<script type="application/json">' + json.dumps(model) + "</script>")
    with pytest.raises(ValueError, match="missing from complete downloads"):
        inventory_publication(tmp_path, 2026)


def test_dated_statements_do_not_become_a_fabricated_annual_series(tmp_path):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads/exchange.json").write_text(json.dumps(dataset([{"year": 2024, "value": 1}])))
    statements = {
        "comparability": "Dated statements, not an annual census", "scope": "Americans studying in China",
        "observations": [{"id": "statement", "source_id": "source", "statement_date": "2026-03-23",
                          "measurement": "annual_participation_estimate", "value": None,
                          "bound": 2000, "qualifier": "less_than"}],
        "sources": {"source": {"asset": {"url": "https://example.org/report",
                                        "retrieved_at": "2026-10-24T11:00:00+00:00"}}}}
    (tmp_path / "downloads/student-estimates.json").write_text(json.dumps(statements))
    report = inventory_publication(tmp_path, 2026)
    assert len(report["series"]) == 1
    record, = report["non_series_components"]
    assert record["statement_records"] == statements["observations"]
    assert record["source_provenance"]["source_urls"] == ["https://example.org/report"]
    assert "first_year" not in record


def test_custom_program_models_are_mapped_to_original_series(tmp_path):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads/confucius-programs.json").write_text(
        json.dumps(dataset([{"reference": "2023-07", "bound": 5, "value": None}], "dated_observations")))
    model = {"layout": "timeline", "rows": [
        {"id": "observation-id", "series_id": "count", "reference": "2023-07", "value": None, "bound": 5}]}
    (tmp_path / "confucius.html").write_text(
        '<script type="application/json">' + json.dumps(model) + "</script>")
    report = inventory_publication(tmp_path, 2026)
    assert report["rendered_series"] == 1
    assert report["series"][0]["rendered_on_pages"] == ["confucius.html"]


def test_categorical_bars_are_not_missed_when_the_model_has_no_line_groups(tmp_path):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads/opinions.json").write_text(json.dumps(dataset([{"year": 2026, "value": 5}], "survey_rounds")))
    model = {"kind": "bars", "groups": [], "bars": [{"id": "count", "year": 2026, "value": 5}]}
    (tmp_path / "opinions.html").write_text(
        '<script type="application/json">' + json.dumps(model) + "</script>")
    report = inventory_publication(tmp_path, 2026)
    assert report["rendered_series"] == 1
    assert report["series"][0]["rendered_on_pages"] == ["opinions.html"]


def test_annual_chart_does_not_claim_to_render_monthly_or_ytd_records():
    data = dataset([
        {"year": 2025, "period": "2025", "frequency": "annual", "value": 5},
        {"year": 2025, "period": "2025-06", "frequency": "monthly", "value": 1},
        {"year": 2025, "period": "2025-06", "period_end": "2025-06-30", "frequency": "ytd", "value": 3}])
    points = {"count": [{"year": 2025, "period": "2025", "value": 5, "page": "index.html"}]}
    rows = inventory_series("test", data, {"count": {"index.html"}}, 2026, points)
    assert next(r for r in rows if r["cadence"] == "annual")["rendered_on_pages"] == ["index.html"]
    assert all(not r["rendered_on_pages"] for r in rows if r["cadence"] != "annual")


def test_cli_keeps_operational_reports_out_of_the_public_website(tmp_path):
    site = tmp_path / "publication"
    (site / "downloads").mkdir(parents=True)
    (site / "downloads/exchange.json").write_text(json.dumps(dataset([{"year": 2024, "value": 1}])))
    script = Path(__file__).resolve().parents[1] / "scripts/audit_series_coverage.py"
    blocked = subprocess.run(
        [sys.executable, str(script), "--site", str(site), "--output", str(site / "audit")],
        capture_output=True, text=True)
    assert blocked.returncode == 2 and "outside the public publication" in blocked.stderr
    assert not (site / "audit").exists()
    output = tmp_path / "research-audit"
    subprocess.run(
        [sys.executable, str(script), "--site", str(site), "--output", str(output), "--target-year", "2026"],
        capture_output=True, check=True)
    report = json.loads((output / "series-inventory.json").read_text())
    assert len(report["series"]) == 1 and (output / "series-inventory.csv").is_file()


@pytest.mark.parametrize("placeholder", [False, True])
def test_unreported_or_invented_rendered_years_cannot_disappear_from_the_audit(tmp_path, placeholder):
    (tmp_path / "downloads").mkdir()
    rows = [{"year": 2024, "value": 1}]
    if placeholder:
        rows.append({"year": 2026, "value": None, "status": "missing"})
    (tmp_path / "downloads/exchange.json").write_text(json.dumps(dataset(rows)))
    model = {"kind": "series", "groups": [{"id": "count", "points": [{"year": 2026, "value": 1}]}]}
    (tmp_path / "index.html").write_text('<script type="application/json">' + json.dumps(model) + "</script>")
    with pytest.raises(ValueError, match="measurement periods missing"):
        inventory_publication(tmp_path, 2026)
