import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

import pytest

from test_pipeline import UID, POST_ID, detail, feed, record, registry
from us_china_exchange.model import json_text
from us_china_exchange.weibo_analysis import create_summary
from weibo_media.collect import AccessBlocked, normalize, window
from weibo_media.refresh import canonical, fingerprint, refresh
from weibo_media.registry import load
from weibo_media.storage import connect, put_post


class CapturedFixture:
    def __init__(self, root, pages):
        self.root = root / "data/local/fixture-captures"
        self.root.mkdir(parents=True, exist_ok=True)
        self.pages, self.captures, self.calls = pages, [], []
        self.blocked = None

    def get(self, url):
        self.calls.append(url)
        body = self.pages[url]
        if isinstance(body, Exception):
            self.blocked = str(body)
            raise body
        path = self.root / f"capture-{len(self.calls)}.html"
        path.write_text(body)
        self.captures.append({"url": url, "path": path, "body": body})
        return body


def inputs(root, monkeypatch):
    for folder in ("data/registry", "data/discovery", "data/site"):
        (root / folder).mkdir(parents=True)
    path = root / "data/registry/outlets.json"
    data = registry()
    data["accounts"][0]["existence"] = "current_evidence"
    path.write_text(json.dumps(data))
    database = root / "data/local/weibo.sqlite"
    db = connect(database)
    load(db, path)
    post = normalize(record(), db.execute("SELECT * FROM accounts").fetchone(), *window("2020-01-01", "2026-10-21"))
    with db:
        put_post(db, post)
    posts = canonical(db)
    db.close()
    proof = dict(post_id=POST_ID, account_id="test-account", uid=UID, published_utc=post["published_utc"],
                 text_status=post["text_status"], canonical_text_sha256=hashlib.sha256(post["text"].encode()).hexdigest(),
                 source_url=post["source_url"], source_sha256="a" * 64, verification_method="fixture_prior_native_audit")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(proof), lineterminator="\n")
    writer.writeheader()
    writer.writerow(proof)
    raw = stream.getvalue().encode()
    (root / "data/discovery/weibo_post_source_audit.csv").write_bytes(raw)
    audit = {
        "version": 1, "audited_at": "2026-10-22T00:00:00+00:00",
        "registry_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "canonical_posts_sha256": hashlib.sha256(json_text([fingerprint(p) for p in posts.values()]).encode()).hexdigest(),
        "post_manifest_sha256": hashlib.sha256(raw).hexdigest(), "scope": "Synthetic prior source audit",
        "accounts": [dict(account_id="test-account", uid=UID, status="numeric_binding_rechecked",
                          method="fixture", source_url=post["source_url"], source_sha256="a" * 64,
                          observed_name="测试媒体", observed_certification=None, note="Synthetic source")],
        "corpus": dict(posts_checked=1, primary_text_matches=1, native_detail_sources_checked=1,
                       archived_sources_checked=0, live_registered_profiles_attempted=1,
                       live_registered_profiles_readable=1, current_profile_name_matches=1,
                       explicit_prior_detail_conflicts_found=0, canonical_text_corrections=0),
    }
    (root / "data/discovery/weibo_primary_audit.json").write_text(json_text(audit))
    (root / "data/site/weibo_summary.json").write_text(json_text(create_summary(database, path)))
    def assessment(db, roster, screening, journal, directory):
        row = dict(domain="example.org", account_ids=["test-account"], account_uids=[UID],
                   account_status="confirmed_current_evidence", recovered_posts=db.execute(
                       "SELECT count(*) FROM posts").fetchone()[0], manual_review=[{}],
                   ranking_source="https://example.org/ranking", verified_no_account=False)
        for filename in ("us_top1000_accounts.jsonl", "outlet_account_assessments.jsonl"):
            (directory / filename).write_text(json.dumps(row) + "\n")
        for filename in ("us_top1000_accounts.csv", "outlet_account_assessments.csv"):
            (directory / filename).write_text("fixture\n")
    monkeypatch.setattr("weibo_media.assessment.publish", assessment)
    monkeypatch.setattr("us_china_exchange.render.png_chart", lambda svg: b"fixture")
    (root / ".gitignore").write_text("data/local/\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org",
                    "commit", "-qm", "Synthetic public metadata fixture"], cwd=root, check=True)
    return database


def test_incremental_refresh_verifies_new_primary_text_and_preserves_private_original(tmp_path, monkeypatch):
    database = inputs(tmp_path, monkeypatch)
    before = database.read_bytes()
    new_id = "90071992547409932"
    client = CapturedFixture(tmp_path, {
        f"https://www.sina.cn/media/{UID}": feed([record(POST_ID), record(new_id)]),
        f"https://www.sina.cn/news/detail/{new_id}.html": detail(post_id=new_id),
    })
    result = refresh(tmp_path, account_ids=["test-account"], publish=True, client=client)
    assert result["new_posts"] == 1 and result["readable_feeds"] == 1 and result["status"] == "partial"
    assert f"https://www.sina.cn/news/detail/{POST_ID}.html" not in client.calls
    assert database.read_bytes() != before
    summary = json.loads((tmp_path / "data/site/weibo_summary.json").read_text())
    assert summary["version"] == 5 and summary["refresh"] == result
    assert sum(row["recovered_posts"] for row in summary["daily"]) == 2
    assert "PRIVATE" not in (tmp_path / "site/downloads/weibo-summary.json").read_text()
    with (tmp_path / "data/discovery/weibo_post_source_audit.csv").open() as stream:
        proof = {r["post_id"]: r for r in csv.DictReader(stream)}
    assert proof[POST_ID]["verification_method"] == "fixture_prior_native_audit"
    assert proof[new_id]["verification_method"] == "native_detail_id_author_date_and_text"
    assert (tmp_path / "data/local/exports/posts.jsonl").is_file()


def test_blocked_refresh_preserves_corpus_and_does_not_retry_access_hold(tmp_path, monkeypatch):
    database = inputs(tmp_path, monkeypatch)
    before = database.read_bytes()
    client = CapturedFixture(tmp_path, {f"https://www.sina.cn/media/{UID}": AccessBlocked("HTTP403; no bypass")})
    for _ in range(2):
        with pytest.raises(ValueError, match="No readable feeds"):
            refresh(tmp_path, client=client)
    assert len(client.calls) == 1
    assert database.read_bytes() == before
    assert json.loads((tmp_path / "data/local/automation/last-check.json").read_text())["status"] == "blocked"


def test_stale_audit_prevents_network_collection(tmp_path, monkeypatch):
    database = inputs(tmp_path, monkeypatch)
    db = connect(database)
    with db:
        db.execute("UPDATE posts SET text='CHANGED'")
    db.close()
    client = CapturedFixture(tmp_path, {})
    with pytest.raises(ValueError, match="stale"):
        refresh(tmp_path, client=client)
    assert client.calls == []


def test_automatic_commit_never_includes_unrelated_staged_work(tmp_path, monkeypatch):
    root = tmp_path / "project"
    inputs(root, monkeypatch)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=root, check=True)
    unrelated = root / "unrelated.txt"
    unrelated.write_text("Preserve the other contributor's staged work.")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=root, check=True)
    client = CapturedFixture(root, {f"https://www.sina.cn/media/{UID}": feed([record(POST_ID)])})
    refresh(root, account_ids=["test-account"], publish=True, push=True, client=client)
    committed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
                                        cwd=root, text=True).splitlines()
    assert "unrelated.txt" not in committed
    assert subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=root, text=True).strip() == "unrelated.txt"
    assert unrelated.read_text() == "Preserve the other contributor's staged work."
