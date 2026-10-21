import json

import pytest

from us_china_exchange.model import observation
from us_china_exchange.pipeline import SourceUnavailable, refresh


class FakeClient:
    now = "2026-10-21T00:00:00+00:00"


def adapter(value=100, vintage="Release 1", source="sample"):
    def fetch(client):
        row = observation(source, "CHN", "USA", "visitors", 2020, value, "Test scope")
        row.update(source_url="https://example.org/official.csv", raw_sha256="a" * 64,
                   retrieved_at=client.now, source_vintage=vintage)
        return [row], vintage, "Source notes"
    return fetch


def test_unchanged_refresh_is_byte_identical_and_revision_replaces(tmp_path):
    first = refresh(tmp_path, {"sample": adapter()}, FakeClient())
    path = tmp_path / "data/site/observations.json"
    before = path.read_bytes()
    client = FakeClient()
    client.now = "2026-10-22T00:00:00+00:00"
    assert first["publication_changed"]
    assert not refresh(tmp_path, {"sample": adapter()}, client)["publication_changed"]
    assert path.read_bytes() == before
    refresh(tmp_path, {"sample": adapter(125, "Release 2")}, client)
    assert len(json.loads(path.read_text())) == 1
    assert json.loads(path.read_text())[0]["value"] == 125


def test_outage_retains_data_and_recovery_updates_health(tmp_path):
    refresh(tmp_path, {"sample": adapter()}, FakeClient())
    path = tmp_path / "data/site/observations.json"
    before = path.read_bytes()

    def outage(client):
        raise SourceUnavailable("HTTP 503")

    refresh(tmp_path, {"sample": outage}, FakeClient())
    assert path.read_bytes() == before
    assert json.loads((tmp_path / "data/site/sources.json").read_text())["sample"]["status"] == "degraded"
    refresh(tmp_path, {"sample": adapter()}, FakeClient())
    assert json.loads((tmp_path / "data/site/sources.json").read_text())["sample"]["status"] == "available"


def test_malformed_candidate_does_not_publish(tmp_path):
    refresh(tmp_path, {"sample": adapter()}, FakeClient())
    before = {p.name: p.read_bytes() for p in (tmp_path / "data/site").iterdir()}
    with pytest.raises(ValueError):
        refresh(tmp_path, {"sample": adapter(-1)}, FakeClient())
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "data/site").iterdir()}
    assert json.loads((tmp_path / "data/local/exchange/check.json").read_text())["publication_blocked"]


def test_volatile_raw_checksum_does_not_create_publication_change(tmp_path):
    refresh(tmp_path, {"sample": adapter()}, FakeClient())

    def different_container(client):
        rows, vintage, notes = adapter()(client)
        rows[0]["raw_sha256"] = "b" * 64
        return rows, vintage, notes

    assert not refresh(tmp_path, {"sample": different_container}, FakeClient())["publication_changed"]


def test_partial_refresh_preserves_omitted_rows_manifests_and_noop(tmp_path):
    refresh(tmp_path, {"sample": adapter(), "other": adapter(200, source="other")}, FakeClient())

    def outage(client):
        raise SourceUnavailable("HTTP 503")

    refresh(tmp_path, {"other": outage}, FakeClient())
    output = tmp_path / "data/site"
    old_rows = json.loads((output / "observations.json").read_text())
    old_manifest = json.loads((output / "sources.json").read_text())["other"]
    assert old_manifest["status"] == "degraded"
    report = refresh(tmp_path, {"sample": adapter(125, "Release 2")}, FakeClient())
    rows = json.loads((output / "observations.json").read_text())
    assert {r["source_id"] for r in rows} == {"sample", "other"}
    assert next(r for r in rows if r["source_id"] == "other") == next(
        r for r in old_rows if r["source_id"] == "other")
    assert next(r for r in rows if r["source_id"] == "sample")["value"] == 125
    assert json.loads((output / "sources.json").read_text())["other"] == old_manifest
    assert set(report["sources"]) == {"sample"}
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert not refresh(tmp_path, {"sample": adapter(125, "Release 2")}, FakeClient())["publication_changed"]
    assert not refresh(tmp_path, {}, FakeClient())["publication_changed"]
    with pytest.raises(ValueError):
        refresh(tmp_path, {"sample": adapter(-1)}, FakeClient())
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_refresh_repairs_legacy_reporting_dates_with_validated_candidate(tmp_path):
    refresh(tmp_path, {"sample": adapter()}, FakeClient())
    path = tmp_path / "data/site/observations.json"
    old_rows = json.loads(path.read_text())
    old_rows[0]["period_basis"] = "reporting"
    path.write_text(json.dumps(old_rows))

    def corrected(client):
        rows, vintage, notes = adapter()(client)
        rows[0].update(period_basis="reporting", period_start=None, period_end=None)
        return rows, vintage, notes

    assert refresh(tmp_path, {"sample": corrected}, FakeClient())["publication_changed"]
    row = json.loads(path.read_text())[0]
    assert row["period_start"] is None and row["period_end"] is None


@pytest.mark.parametrize("previous_log", [False, True])
@pytest.mark.parametrize("failure", ["provenance", "serialization"])
def test_final_failures_record_current_attempt_before_any_publication_write(tmp_path, previous_log, failure):
    refresh(tmp_path, {"sample": adapter()}, FakeClient())
    output = tmp_path / "data/site"
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    log = tmp_path / "data/local/exchange/check.json"
    if not previous_log:
        log.unlink()
    client = FakeClient()
    client.now = "2026-10-22T00:00:00+00:00"

    def invalid(client):
        rows, vintage, notes = adapter(125)(client)
        if failure == "provenance":
            rows[0]["raw_sha256"] = ""
        else:
            vintage = {"not JSON serializable"}
        return rows, vintage, notes

    message = "provenance incomplete" if failure == "provenance" else "JSON serializable"
    with pytest.raises((ValueError, TypeError), match=message):
        refresh(tmp_path, {"sample": invalid}, client)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    report = json.loads(log.read_text())
    assert report["checked_at"] == client.now
    assert report["publication_blocked"] is True
    assert report["publication_changed"] is False
    assert message in report["error"]
    assert report["sources"]["sample"]["checked_at"] == client.now
    refresh(tmp_path, {"sample": adapter(125, "Release 2")}, client)
    assert "publication_blocked" not in json.loads(log.read_text())
    assert json.loads((output / "observations.json").read_text())[0]["value"] == 125


def test_final_validation_logs_invalid_retained_source_without_publishing_selected_update(tmp_path):
    refresh(tmp_path, {"sample": adapter(), "other": adapter(200, source="other")}, FakeClient())
    output = tmp_path / "data/site"
    path = output / "observations.json"
    stored = json.loads(path.read_text())
    next(r for r in stored if r["source_id"] == "other")["period"] = "2025"
    path.write_text(json.dumps(stored))
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    client = FakeClient()
    client.now = "2026-10-22T00:00:00+00:00"
    with pytest.raises(ValueError, match="calendar period label"):
        refresh(tmp_path, {"sample": adapter(125)}, client)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    report = json.loads((tmp_path / "data/local/exchange/check.json").read_text())
    assert report["checked_at"] == client.now
    assert report["publication_blocked"] is True
    assert "calendar period label" in report["error"]
    assert set(report["sources"]) == {"sample"}
