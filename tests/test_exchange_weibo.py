import csv
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image

from us_china_exchange.render import build, build_weibo
from us_china_exchange.model import digest, json_text
from us_china_exchange.weibo_analysis import create_summary, svg_weibo, validate_summary
from us_china_exchange.weibo_activity import rolling_activity
from us_china_exchange.weibo_explorer import explorer_page
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


def primary_audit_input(database, registry, summary, path):
    db = connect(database)
    try:
        canonical = [dict(r, text_sha256=digest(r["text"].encode())) for r in db.execute(
            "SELECT id,account_id,uid,published_utc,text_status,text FROM posts ORDER BY id")]
        for row in canonical:
            del row["text"]
    finally:
        db.close()
    audit = {
        "version": 1, "audited_at": "2026-10-22T18:00:00+00:00",
        "registry_sha256": digest(registry.read_bytes()),
        "canonical_posts_sha256": digest(json_text(canonical).encode()),
        "post_manifest_sha256": "b" * 64,
        "scope": "Synthetic primary identity and source-text consistency fixture, not completeness.",
        "accounts": [
            dict(account_id=a["account_id"], uid=a["uid"],
                 status="numeric_binding_rechecked", method="fixture_primary_source",
                 source_url=a["profile_url"], source_sha256="a" * 64,
                 observed_name=a["display_name"], observed_certification=None, note="Synthetic review")
            for a in summary["accounts"]
        ],
        "corpus": dict(posts_checked=sum(a["recovered_posts"] for a in summary["accounts"]),
                       primary_text_matches=sum(a["recovered_posts"] for a in summary["accounts"]),
                       native_detail_sources_checked=2, archived_sources_checked=0,
                       live_registered_profiles_attempted=2, live_registered_profiles_readable=1,
                       current_profile_name_matches=1, explicit_prior_detail_conflicts_found=0,
                       canonical_text_corrections=0),
    }
    path.write_text(json_text(audit))
    return audit


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
    monthly = {r["month"]: r for r in summary["monthly"]}
    assert len(monthly) == 82
    assert monthly["2020-12"] == dict(month="2020-12", recovered_posts=1, observed_accounts=1, partial_window=False)
    assert monthly["2022-01"] == dict(month="2022-01", recovered_posts=2, observed_accounts=1, partial_window=False)
    assert monthly["2021-01"] == dict(month="2021-01", recovered_posts=0, observed_accounts=0, partial_window=False)
    assert monthly["2026-10"]["partial_window"] is True
    assert "PRIVATE_BODY" not in json.dumps(summary)
    rolling_doc = ElementTree.fromstring(svg_weibo(summary, "rolling30-posts"))
    description = next(x.text for x in rolling_doc.iter() if x.tag.endswith("desc"))
    assert "30-day" in description and "Monthly" not in description
    date_labels = [x for x in rolling_doc.iter() if x.get("class") == "date-tick"]
    complete = [r for r in summary["rolling_30d"] if not r["partial_window"]]
    assert [date_labels[0].get("data-period"), date_labels[-1].get("data-period")] == [
        complete[0]["date"], complete[-1]["date"]]
    assert len(date_labels[0].text.split()) == len(date_labels[-1].text.split()) == 3
    doc = ElementTree.fromstring(svg_weibo(summary, "publication-years"))
    bars = [x for x in doc.iter() if x.get("class") == "data-bar"]
    assert {x.get("data-label") for x in bars} == {"2020", "2022"}
    assert "n/a" in "".join(doc.itertext())
    for metric, total, unit in (("recovery-coverage", 2, "Documented channels"), ("text-completeness", 3, "Recovered posts")):
        figure = ElementTree.fromstring(svg_weibo(summary, metric))
        assert sum(int(x.get("data-value")) for x in figure.iter() if x.get("class") == "data-bar") == total
        assert next(x.text for x in figure.iter() if x.get("class") == "axis-unit") == unit


def test_monthly_figures_and_download_keep_all_bins_and_partial_months(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    for metric, field in (("monthly-posts", "recovered_posts"), ("monthly-accounts", "observed_accounts")):
        doc = ElementTree.fromstring(svg_weibo(summary, metric))
        points = [x for x in doc.iter() if x.get("class") == "data-point"]
        assert [(p.get("data-month"), int(p.get("data-value"))) for p in points] == [
            (row["month"], row[field]) for row in summary["monthly"]]
        assert "partial requested month" in "".join(points[-1].itertext())
        assert any(x.get("stroke-dasharray") for x in doc.iter() if x.get("class") == "data-line")
        assert "not a posting-activity trend" in "".join(doc.itertext())
        assert "21 Oct 2026" in "".join(doc.itertext())
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    with (tmp_path / "site/downloads/weibo-months.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 82
    assert rows[0] == dict(month="2020-01", recovered_posts="0", observed_accounts="0", partial_window="False")
    assert rows[-1]["partial_window"] == "True"
    assert sum(int(row["recovered_posts"]) for row in rows) == 3
    page = (tmp_path / "site/weibo.html").read_text()
    assert "downloads/weibo-months.csv" in page and "not a census of active accounts" in page
    summary["version"] = 2
    del summary["monthly"]
    for key in ("daily", "rolling_30d", "refresh"):
        del summary[key]
    build_weibo(tmp_path, summary, {"weibo": []})
    assert not (tmp_path / "site/downloads/weibo-months.csv").exists()
    assert not list((tmp_path / "site/figures/weibo").glob("*/monthly-*.*"))


def test_monthly_windows_merge_adjacent_intervals_and_break_unrequested_gaps(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    db = connect(database)
    with db:
        db.execute("UPDATE runs SET window_start=?,window_end=? WHERE account_id='account1'",
                   ("2020-11-30T16:00:00+00:00", "2020-12-31T16:00:00+00:00"))
        db.execute("UPDATE runs SET window_start=?,window_end=? WHERE account_id='account2'",
                   ("2021-12-31T16:00:00+00:00", "2022-01-31T16:00:00+00:00"))
    summary = create_summary(database, registry)
    assert summary["monthly"] == [
        dict(month="2020-12", recovered_posts=1, observed_accounts=1, partial_window=False),
        dict(month="2022-01", recovered_posts=2, observed_accounts=1, partial_window=False)]
    doc = ElementTree.fromstring(svg_weibo(summary, "monthly-posts"))
    assert not any(x.get("class") == "data-line" for x in doc.iter())
    with db:
        db.execute("DELETE FROM posts WHERE id IN ('p1','p5')")
        db.execute("UPDATE runs SET window_start=?,window_end=? WHERE account_id='account1'",
                   ("2020-11-30T16:00:00+00:00", "2020-12-15T16:00:00+00:00"))
        db.execute("UPDATE runs SET window_start=?,window_end=? WHERE account_id='account2'",
                   ("2020-12-15T16:00:00+00:00", "2020-12-31T16:00:00+00:00"))
    db.close()
    summary = create_summary(database, registry)
    assert summary["monthly"] == [
        dict(month="2020-12", recovered_posts=1, observed_accounts=1, partial_window=False)]


def test_monthly_windows_keep_exact_half_open_boundaries(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    db = connect(database)
    with db:
        db.execute("UPDATE runs SET window_start=?,window_end=?",
                   ("2020-12-31T15:59:00+00:00", "2022-01-01T00:00:00+00:00"))
    with pytest.raises(ValueError, match="outside requested collection windows"):
        create_summary(database, registry)
    with db:
        db.execute("UPDATE runs SET window_end=?", ("2022-01-01T00:00:00.000001+00:00",))
    db.close()
    summary = create_summary(database, registry)
    assert len(summary["monthly"]) == 14
    assert summary["monthly"][0] == dict(
        month="2020-12", recovered_posts=1, observed_accounts=1, partial_window=True)
    assert summary["monthly"][-1] == dict(
        month="2022-01", recovered_posts=2, observed_accounts=1, partial_window=True)


@pytest.mark.parametrize("mutation", ["missing_month", "duplicate_month", "post_count", "channel_count",
                                     "partial_month", "private_field"])
def test_monthly_snapshot_rejects_incomplete_or_unreconciled_aggregates(tmp_path, mutation):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    monthly = summary["monthly"]
    if mutation == "missing_month":
        monthly.pop(0)
    elif mutation == "duplicate_month":
        monthly[1] = monthly[0].copy()
    elif mutation == "post_count":
        monthly[24]["recovered_posts"] += 1
    elif mutation == "channel_count":
        monthly[24]["observed_accounts"] = 2
    elif mutation == "partial_month":
        monthly[-1]["partial_window"] = False
    else:
        monthly[0]["text"] = "PRIVATE_BODY"
    with pytest.raises(ValueError, match="[Mm]onthly"):
        validate_summary(summary)


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
    names = ("accounts", "months", "days", "rolling30", "years", "text-completeness")
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
    del summary["monthly"]
    for key in ("daily", "rolling_30d", "refresh"):
        del summary[key]
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
    assert 'id="weibo-explorer"' in page
    assert 'id="monthly-posts"' not in page
    assert not (tmp_path / "site/downloads/weibo-months.csv").exists()


def test_primary_audit_exposes_pending_bindings_and_rejects_stale_text(tmp_path, monkeypatch):
    database, registry = snapshot_inputs(tmp_path)
    db = connect(database)
    with db:
        db.execute("DELETE FROM posts WHERE account_id='account2'")
    db.close()
    base = create_summary(database, registry)
    path = tmp_path / "audit.json"
    audit = primary_audit_input(database, registry, base, path)
    audit["accounts"][1].update(status="numeric_binding_recheck_pending",
                                method="prior_archive_not_reread", source_sha256=None)
    path.write_text(json.dumps(audit))
    summary = create_summary(database, registry, audit_path=path)
    assert summary["version"] == 5
    assert summary["roster"]["resolved_numeric_accounts"] == 2
    assert summary["accounts"][1]["uid"] == "2"
    assert summary["accounts"][1]["primary_audit_status"] == "numeric_binding_recheck_pending"
    assert "PRIVATE_BODY" not in json.dumps(summary)
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    build_weibo(tmp_path, summary, {"weibo": []})
    page = (tmp_path / "site/weibo.html").read_text()
    assert "1 numeric binding rechecked; 1 historical numeric binding still pending" in page
    assert "Publisher 2" in page and "Historical UID recheck pending" in page
    with (tmp_path / "site/downloads/weibo-accounts.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[1]["uid"] == "2" and rows[1]["primary_audit_status"] == "numeric_binding_recheck_pending"
    assert rows[1]["primary_audit_source_sha256"] == ""
    before = (tmp_path / "site/downloads/weibo-accounts.csv").read_bytes()
    build_weibo(tmp_path, json.loads(json.dumps(summary, sort_keys=True)), {"weibo": []})
    assert before == (tmp_path / "site/downloads/weibo-accounts.csv").read_bytes()
    legacy = json.loads(json.dumps(summary))
    legacy["version"] = 3
    del legacy["monthly"]
    for key in ("daily", "rolling_30d", "refresh"):
        del legacy[key]
    build_weibo(tmp_path, legacy, {"weibo": []})
    assert "Primary-source recheck" in (tmp_path / "site/weibo.html").read_text()
    assert not (tmp_path / "site/downloads/weibo-months.csv").exists()
    db = connect(database)
    with db:
        db.execute("UPDATE posts SET text='CHANGED_PRIVATE_BODY' WHERE id='p1'")
    db.close()
    with pytest.raises(ValueError, match="audit is stale"):
        create_summary(database, registry, audit_path=path)


def test_primary_audit_does_not_publish_extra_raw_source_fields(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    base = create_summary(database, registry)
    path = tmp_path / "audit.json"
    audit = primary_audit_input(database, registry, base, path)
    audit["accounts"][0]["raw_html"] = "PRIVATE_SOURCE_BODY"
    path.write_text(json_text(audit))
    with pytest.raises(ValueError, match="Unexpected primary source audit fields"):
        create_summary(database, registry, audit_path=path)
    audit = primary_audit_input(database, registry, base, path)
    audit["accounts"][0]["source_url"] = "javascript:alert(1)"
    path.write_text(json_text(audit))
    with pytest.raises(ValueError, match="Invalid primary source audit URL"):
        create_summary(database, registry, audit_path=path)


def test_new_source_conflict_requires_reaudit_even_when_canonical_text_did_not_change(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    base = create_summary(database, registry)
    path = tmp_path / "audit.json"
    primary_audit_input(database, registry, base, path)
    db = connect(database)
    with db:
        db.execute("UPDATE runs SET finished_at=?,checkpoint=? WHERE account_id='account1'",
                   ("2026-10-22T19:00:00+00:00",
                    json.dumps({"source_conflicts": {"p1": "Detail author UID mismatch"}})))
    db.close()
    with pytest.raises(ValueError, match="source conflicts.*require re-audit"):
        create_summary(database, registry, audit_path=path)


def test_weibo_outputs_publish_only_complete_aggregates_and_both_backgrounds(tmp_path):
    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    (tmp_path / "data/site/weibo_summary.json").write_text(json.dumps(summary))
    build(tmp_path)
    published = json.loads((tmp_path / "site/downloads/weibo-summary.json").read_text())
    assert published == summary
    assert "PRIVATE_BODY" not in (tmp_path / "site/weibo.html").read_text()
    assert len(list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))) == 20
    catalog = (tmp_path / "site/figures/index.html").read_text()
    assert "monthly-posts.png" in catalog and "monthly-accounts.png" in catalog
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
    for month in summary["monthly"]:
        month.update(recovered_posts=0, observed_accounts=0)
    for day in summary["daily"]:
        day.update(recovered_posts=0, account_ids=[])
    summary["rolling_30d"] = rolling_activity(summary["daily"], summary["accounts"])
    (tmp_path / "data/site/weibo_summary.json").write_text(json.dumps(summary))
    build(tmp_path)
    assert len(list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))) == 6
    assert not list((tmp_path / "site/figures/weibo").glob("*/publication-years.*"))
    assert not list((tmp_path / "site/figures/weibo").glob("*/monthly-*.*"))
    (tmp_path / "data/site/weibo_summary.json").unlink()
    build(tmp_path)
    assert not list((tmp_path / "outputs/figures/weibo").glob("*/*.png"))
    assert not list((tmp_path / "site/figures/weibo").glob("*/*.svg"))
    assert not (tmp_path / "site/weibo.html").exists()
    assert not list((tmp_path / "site/downloads").glob("weibo-*"))
    assert not (tmp_path / "site/assets/weibo-explorer.js").exists()


def test_account_map_keeps_distinct_channels_grouped_without_recovery_weights(tmp_path):
    from bs4 import BeautifulSoup

    database, registry = snapshot_inputs(tmp_path, unresolved_uid_channels=1)
    summary = create_summary(database, registry)
    summary["accounts"][1].update(outlet_id="outlet1", outlet_name="Publisher 1", recovered_posts=0)
    before = BeautifulSoup(explorer_page(summary), "html.parser")
    dots = before.select(".weibo-dot")
    assert len(dots) == 3
    assert len(before.select(".weibo-brand")) == 2
    assert {dot["data-account-id"] for dot in dots} == {a["account_id"] for a in summary["accounts"]}
    assert before.select_one("#weibo-account-account4 .weibo-uid").text == "UID unresolved"
    assert not before.select(".comparison-chart, .plot-data, #publication-years, #monthly-posts, #rolling30-posts")
    payload = json.loads(before.select_one("#weibo-explorer-data").string)
    assert {a["id"] for a in payload["accounts"]} == {a["account_id"] for a in summary["accounts"]}
    assert all("recovered_posts" not in a and "latest_publication_utc" not in a for a in payload["accounts"])
    for account in summary["accounts"]:
        account.update(recovered_posts=999999, earliest_publication_utc=None, latest_publication_utc=None)
    after = BeautifulSoup(explorer_page(summary), "html.parser")
    assert str(before.select_one("#weibo-map")) == str(after.select_one("#weibo-map"))
    assert before.select_one("#weibo-explorer-data").string == after.select_one("#weibo-explorer-data").string


def test_account_explorer_preserves_scope_and_escapes_serialized_evidence(tmp_path):
    from bs4 import BeautifulSoup

    database, registry = snapshot_inputs(tmp_path)
    summary = create_summary(database, registry)
    account = summary["accounts"][0]
    account.update(display_name="<script>not executable</script>", relationship="Licensed edition, not the U.S. newsroom")
    page = BeautifulSoup(explorer_page(summary), "html.parser")
    detail = page.select_one("#weibo-account-account1")
    assert detail.select_one(".weibo-channel-name").text == account["display_name"]
    assert not detail.select("script")
    assert account["relationship"] in detail.text
    assert account["operator"] in detail.text and account["us_basis"] in detail.text
    assert detail.select_one(".weibo-sources a")["href"] == account["evidence"][0]["source_url"]
    assert account["evidence"][0]["justification"] in detail.text
