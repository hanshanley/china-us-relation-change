import csv
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image

from us_china_exchange.render import build, build_weibo
from us_china_exchange.weibo_analysis import create_summary, svg_weibo, validate_summary
from weibo_media.registry import load
from weibo_media.storage import connect


ROOT = Path(__file__).resolve().parents[1]


def snapshot_inputs(tmp_path, unresolved_uid_channels=0):
    registry = {"outlets": [], "accounts": [], "evidence": []}
    for i in range(1, 4 + unresolved_uid_channels):
        registry["outlets"].append(dict(
            id=f"outlet{i}", name=f"Publisher {i}", category="news", aliases=[], us_basis="U.S. test publisher",
            source_url=f"https://example.org/{i}", research_status="reviewed", notes="Fixture"))
        registry["accounts"].append(dict(
            id=f"account{i}", outlet_id=f"outlet{i}", uid=str(i) if i < 4 else None,
            handle=f"historical{i}" if i >= 4 else None, display_name=f"Publisher {i}",
            profile_url=f"https://example.org/account{i}", language="en", operator="Test publisher",
            relationship="Institutional fixture", officialness="unresolved" if i == 3 else "confirmed",
            existence="current_evidence" if i == 1 else "historical", accessibility="unknown", notes="Fixture",
            attribution_end="2021-01-01" if i == 2 else None))
        registry["evidence"].append(dict(
            id=f"evidence{i}", account_id=f"account{i}", source_url=f"https://example.org/{i}",
            source_type="publisher_link", observed_at="2026-10-21T00:00:00+00:00", claim_date=None,
            supports="identity", justification="Synthetic institutional account evidence"))
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry))
    database = tmp_path / "weibo.sqlite"
    db = connect(database)
    load(db, path)
    records = [
        ("p1", "account1", "1", "2021-12-31T16:30:00+00:00", "source_full"),
        ("p2", "account2", "2", "2020-12-31T15:59:00+00:00", "truncated"),
        ("p3", "account2", "2", "2020-12-31T16:00:00+00:00", "source_full"),
        ("p4", "account3", "3", "2021-01-01T00:00:00+00:00", "source_full"),
        ("p5", "account1", "1", "2022-01-01T00:00:00+00:00", "source_full"),
    ]
    with db:
        for post_id, account, uid, published, status in records:
            db.execute("""INSERT INTO posts
                (id,account_id,uid,canonical_url,published_original,published_utc,text,text_status,kind,redistribution)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (post_id, account, uid, "https://example.org/post", published, published,
                        "PRIVATE_BODY_MUST_NOT_BE_PUBLISHED", status, "unknown", "unknown"))
        for i in (1, 2):
            db.execute("""INSERT INTO runs
                (account_id,source_type,started_at,finished_at,window_start,window_end,status,limitations)
                VALUES (?,?,?,?,?,?,?,?)""",
                       (f"account{i}", "fixture", "2026-10-21T00:00:00+00:00", "2026-10-21T01:00:00+00:00",
                        "2019-12-31T16:00:00+00:00", "2026-10-21T16:00:00+00:00", "partial", "Partial fixture"))
    db.close()
    return database, path


def test_summary_respects_timezone_attribution_and_private_corpus(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    before = database.read_bytes()
    summary = create_summary(database, registry)
    assert database.read_bytes() == before
    assert summary["yearly"] == [{"year": 2020, "recovered_posts": 1}, {"year": 2022, "recovered_posts": 2}]
    assert summary["source"]["excluded_attribution_posts"] == 1
    assert summary["source"]["excluded_unconfirmed_posts"] == 1
    assert summary["roster"]["confirmed_accounts"] == 2
    assert sum(a["recovered_posts"] for a in summary["accounts"]) == 3
    assert "PRIVATE_BODY" not in json.dumps(summary)
    doc = ElementTree.fromstring(svg_weibo(summary, "publication-years"))
    bars = [x for x in doc.iter() if x.get("class") == "data-bar"]
    assert {x.get("data-label") for x in bars} == {"2020", "2022"}
    assert "n/a" in "".join(doc.itertext())
    for metric, total, unit in (("recovery-coverage", 2, "Documented channels"), ("text-completeness", 3, "Recovered posts")):
        figure = ElementTree.fromstring(svg_weibo(summary, metric))
        assert sum(int(x.get("data-value")) for x in figure.iter() if x.get("class") == "data-bar") == total
        assert next(x.text for x in figure.iter() if x.get("class") == "axis-unit") == unit


def test_summary_rejects_unreconciled_counts_and_extra_private_fields(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    summary["accounts"][0]["recovered_posts"] += 1
    with pytest.raises(ValueError, match="do not reconcile"):
        validate_summary(summary)
    summary = create_summary(database, registry)
    summary["accounts"][0]["text"] = "PRIVATE_BODY"
    with pytest.raises(ValueError, match="Unexpected Weibo account"):
        validate_summary(summary)
    summary = create_summary(database, registry)
    summary["accounts"][0]["evidence"][0]["text"] = "PRIVATE_BODY"
    with pytest.raises(ValueError, match="Unexpected or missing Weibo account evidence"):
        validate_summary(summary)


def test_weibo_csv_bytes_are_stable_after_json_roundtrip(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    names = ("accounts", "years", "text-completeness")
    before = {name: (tmp_path / f"site/downloads/weibo-{name}.csv").read_bytes() for name in names}
    build_weibo(tmp_path, json.loads(json.dumps(summary, sort_keys=True)), {"weibo": []})
    assert before == {name: (tmp_path / f"site/downloads/weibo-{name}.csv").read_bytes() for name in names}


def test_unresolved_historical_urls_are_not_counted_as_numeric_accounts(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path, unresolved_uid_channels=2)
    summary = create_summary(database, registry)
    assert summary["roster"]["confirmed_accounts"] == 4
    assert summary["roster"]["resolved_numeric_accounts"] == 2
    assert summary["roster"]["unresolved_numeric_accounts"] == 2
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    page = (tmp_path / "site/weibo.html").read_text()
    assert "2 channels have resolved numeric UIDs; 2 do not" in page
    assert page.count("UID unresolved") == 2
    assert "No ranked-cohort assessment is included" in page
    with (tmp_path / "site/downloads/weibo-accounts.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    for row, account in zip(rows, summary["accounts"]):
        assert row["uid"] == (account["uid"] or "")
        assert row["handle"] == (account["handle"] or "")
        assert row["uid_resolution"] == account["uid_resolution"]
        assert json.loads(row["evidence"]) == account["evidence"]
    assert [r["recovered_posts"] for r in rows if not r["uid"]] == ["0", "0"]
    summary["accounts"][-1]["uid_resolution"] = "resolved_numeric_uid"
    with pytest.raises(ValueError, match="numeric identity"):
        validate_summary(summary)


def test_cohort_unknowns_are_not_negatives_and_stale_account_bindings_fail(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path)
    rows = [
        dict(domain=f"publisher{i}.example", ranking_source="https://example.org/ranking",
             account_status=status, account_ids=ids, account_uids=uids, recovered_posts=posts,
             verified_no_account=False, manual_review=[{"notes": "Synthetic review"}] if ids else [])
        for i, status, ids, uids, posts in (
            (1, "confirmed_current_evidence", ["account1"], ["1"], 2),
            (2, "confirmed_historical_only", ["account2"], ["2"], 1),
            (3, "unknown", [], [], 0),
            (4, "candidate_requires_verification", [], [], 0))
    ]
    path = tmp_path / "cohort.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    summary = create_summary(database, registry, path)
    cohort = summary["cohort"]
    assert cohort["selected_domains"] == 4
    assert cohort["manually_reviewed_domains"] == 2
    assert cohort["current_identity_domains"] == cohort["historical_only_domains"] == 1
    assert cohort["unknown_domains"] == cohort["candidate_domains"] == 1
    assert cohort["verified_negative_domains"] == 0
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    page = (tmp_path / "site/weibo.html").read_text()
    assert "1 unknown, 1 unresolved candidates, 0 verified negatives" in page
    assert "digital reputation, not website traffic" in page
    cohort["unknown_domains"] += 1
    with pytest.raises(ValueError, match="cohort totals"):
        validate_summary(summary)
    rows[0]["account_uids"] = ["unverified"]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError, match="cohort and account snapshot"):
        create_summary(database, registry, path)
    with pytest.raises(FileNotFoundError):
        create_summary(database, registry, tmp_path / "missing-assessment.jsonl")


def test_legacy_snapshot_does_not_invent_uid_resolution(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    summary["version"] = 1
    del summary["cohort"]
    for key in ("resolved_numeric_accounts", "unresolved_numeric_accounts"):
        del summary["roster"][key]
    for account in summary["accounts"]:
        for key in ("uid", "handle", "display_name", "uid_resolution", "category", "us_basis",
                    "operator", "notes", "evidence"):
            del account[key]
    validate_summary(summary)
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    page = (tmp_path / "site/weibo.html").read_text()
    assert "Numeric UID resolution was not recorded in this legacy snapshot" in page
    assert "channels have resolved numeric UIDs" not in page
    assert "UID resolution, evidence" not in page


def test_weibo_outputs_publish_only_complete_aggregates_and_both_backgrounds(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    (tmp_path / "data/site/weibo_summary.json").write_text(json.dumps(summary))
    build(tmp_path)
    published = json.loads((tmp_path / "site/downloads/weibo-summary.json").read_text())
    assert published == summary
    assert "PRIVATE_BODY" not in (tmp_path / "site/weibo.html").read_text()
    assert len(list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))) == 8
    for path in (tmp_path / "outputs/figures/weibo").glob("*/*.png"):
        assert path.read_bytes() == (tmp_path / "site/figures/weibo" /
                                    path.relative_to(tmp_path / "outputs/figures/weibo")).read_bytes()
        with Image.open(path) as image:
            assert image.size == (3000, 1800)
    summary["yearly"] = []
    for account in summary["accounts"]:
        account.update(recovered_posts=0, earliest_publication_utc=None, latest_publication_utc=None)
    for status in summary["text_completeness"]:
        status["recovered_posts"] = 0
    (tmp_path / "data/site/weibo_summary.json").write_text(json.dumps(summary))
    build(tmp_path)
    assert len(list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))) == 6
    assert not list((tmp_path / "site/figures/weibo").glob("*/publication-years.*"))
    (tmp_path / "data/site/weibo_summary.json").unlink()
    build(tmp_path)
    assert not list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))
    assert not list((tmp_path / "site/figures/weibo").glob("*/*.svg"))
    assert not (tmp_path / "site/weibo.html").exists()
    assert not list((tmp_path / "site/downloads").glob("weibo-*"))
