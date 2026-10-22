import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image

from us_china_exchange.render import build
from us_china_exchange.weibo_analysis import create_summary, svg_weibo, validate_summary
from weibo_media.registry import load
from weibo_media.storage import connect


ROOT = Path(__file__).resolve().parents[1]


def snapshot_inputs(tmp_path):
    registry = {"outlets": [], "accounts": [], "evidence": []}
    for i in range(1, 4):
        registry["outlets"].append(dict(
            id=f"outlet{i}", name=f"Publisher {i}", category="news", aliases=[], us_basis="U.S. test publisher",
            source_url=f"https://example.org/{i}", research_status="reviewed", notes="Fixture"))
        registry["accounts"].append(dict(
            id=f"account{i}", outlet_id=f"outlet{i}", uid=str(i), handle=None, display_name=f"Publisher {i}",
            profile_url=f"https://example.org/account{i}", language="en", operator="Test publisher",
            relationship="Institutional fixture", officialness="confirmed" if i < 3 else "unresolved",
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
    for metric, total, unit in (("recovery-coverage", 2, "Accounts"), ("text-completeness", 3, "Recovered posts")):
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
