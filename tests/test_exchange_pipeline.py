import json

import pytest

from us_china_exchange.model import observation
from us_china_exchange.pipeline import SourceUnavailable, refresh


class FakeClient:
    now = "2026-10-21T00:00:00+00:00"


def adapter(value=100, vintage="Release 1"):
    def fetch(client):
        row = observation("sample", "CHN", "USA", "visitors", 2020, value, "Test scope")
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
