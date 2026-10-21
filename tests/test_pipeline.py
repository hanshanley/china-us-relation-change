import csv
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

from weibo_media.archive import archive_time, collect_archive, parse_archive
from weibo_media.cli import main
from weibo_media.collect import (
    AccessBlocked, PublicClient, SameHostRedirect, collect_account, import_posts, normalize,
    parse_detail, parse_feed, window,
)
from weibo_media.export import export
from weibo_media.registry import load, validate
from weibo_media.report import report
from weibo_media.storage import connect, put_post


UID = "12345678901234567890"
POST_ID = "90071992547409931"
OBSERVED = "2026-10-21T14:00:00+00:00"
FULL_TEXT = '中文，带"引号"\n第二行：完整研究样本。' * 20


def registry():
    return {
        "outlets": [{
            "id": "test", "name": "Test News", "category": "newspaper", "aliases": ["测试"],
            "us_basis": "Synthetic U.S. outlet fixture", "source_url": "https://example.org/",
            "research_status": "reviewed", "notes": "",
        }],
        "accounts": [{
            "id": "test-account", "outlet_id": "test", "uid": UID, "handle": None,
            "display_name": "测试媒体", "profile_url": "https://weibo.com/u/" + UID,
            "language": "zh-Hans", "operator": "Fixture publisher",
            "relationship": "Fixture newsroom", "officialness": "confirmed",
            "existence": "current_evidence", "accessibility": "unknown", "notes": "",
        }],
        "evidence": [{
            "id": "test-link", "account_id": "test-account", "source_url": "https://example.org/",
            "source_type": "publisher_link", "observed_at": OBSERVED, "claim_date": None,
            "supports": "identity", "justification": "Synthetic publisher outbound link",
        }],
    }


def record(post_id=POST_ID, date="2020-01-01 00:00", text=FULL_TEXT):
    return {
        "id": post_id, "account_id": "test-account", "uid": UID,
        "published_original": date, "text": text, "text_status": "source_full",
        "source_url": "https://www.sina.cn/news/detail/" + post_id + ".html",
        "source_type": "sina_syndication", "retrieved_at": OBSERVED,
        "kind": "unknown", "likes": None, "comments": 0, "reposts": None,
    }


def feed(items):
    html = "<html><head><title>测试媒体的微博_新浪新闻</title></head><body>"
    for item in items:
        html += (
            f'<a class="post-link" href="/news/detail/{item["id"]}.html"><article class="post">'
            f'<div class="time">{item["published_original"]}<span class="src">来自网页</span></div>'
            '<div class="post-text">中文预览</div><div class="post-actions">'
            '<div class="action">转发</div><div class="action">0</div>'
            '<div class="action">2</div></div></article></a>'
        )
    return html + "</body></html>"


def detail(post_id=POST_ID, uid=UID, text=FULL_TEXT):
    article = {"@type": "NewsArticle", "author": {"url": "https://weibo.com/u/" + uid},
               "datePublished": "2020-01-01 00:00", "headline": "NOT POST TEXT"}
    return (
        f'<html data-id="{post_id}"><head><script type="application/ld+json">'
        + json.dumps({"@graph": [article]})
        + '</script></head><body><article class="article-content"><p>'
        + text + '</p></article><aside><article>UNRELATED RECOMMENDATION</article>'
        + '</aside><div class="comments">COMMENT TEXT</div></body></html>'
    )


def archived(post_id=POST_ID, uid=UID, truncated=False):
    expand = '<a action-type="fl_unfold">展开全文</a>' if truncated else ""
    return (
        "<html><head><title>测试媒体的微博_微博</title></head>"
        "<script>$CONFIG['oid']='" + uid + "';</script>"
        f'<div class="WB_feed_type" mid="{post_id}" tbinfo="ouid={uid}">'
        '<div node-type="feed_list_content" class="WB_text">归档正文'
        '<img alt="[微笑]">' + expand + '</div>'
        '<a node-type="feed_list_item_date" title="2020-01-01 00:00">今天</a>'
        '<a action-type="fl_like">赞 3</a><a action-type="fl_comment">评论</a>'
        '</div><div class="comments">DO NOT INGEST</div></html>'
    )


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        result = self.pages[url]
        if isinstance(result, Exception):
            raise result
        return result


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = connect(self.root / "test.sqlite")
        self.path = self.root / "registry.json"
        self.path.write_text(json.dumps(registry()), encoding="utf-8")
        load(self.db, self.path)
        self.account = self.db.execute("SELECT * FROM accounts").fetchone()
        self.bounds = window("2020-01-01", "2026-10-21")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_evidence_gate_and_exact_schema(self):
        data = registry()
        data["evidence"][0]["source_type"] = "matching_logo"
        with self.assertRaisesRegex(ValueError, "lacks direct identity"):
            validate(data)
        data = registry()
        data["accounts"][0]["unexpected_sql_column"] = "x"
        with self.assertRaisesRegex(ValueError, "fields must be exactly"):
            validate(data)
        data = registry()
        data["evidence"][0]["observed_at"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate(data)
        for cutoff in ("2023-02-30", "2023-11-01T00:00:00+08:00", True):
            data = registry()
            data["accounts"][0]["attribution_end"] = cutoff
            with self.assertRaises(ValueError):
                validate(data)
        self.assertEqual(validate(registry())["accounts"][0]["uid"], UID)

    def test_legacy_account_migration_preserves_identity_and_persists_cutoff(self):
        path = self.root / "legacy.sqlite"
        account = registry()["accounts"][0]
        columns = list(account)
        with sqlite3.connect(path) as legacy:
            legacy.execute("CREATE TABLE accounts (" + ",".join(
                column + (" TEXT PRIMARY KEY" if column == "id" else " TEXT")
                for column in columns) + ")")
            legacy.execute("INSERT INTO accounts VALUES (" + ",".join("?" for _ in columns) + ")",
                           [account[column] for column in columns])
        migrated = connect(path)
        try:
            row = migrated.execute("SELECT * FROM accounts").fetchone()
            self.assertEqual(row["uid"], UID)
            self.assertIsNone(row["attribution_end"])
            data = registry()
            data["accounts"][0]["attribution_end"] = "2023-11-01"
            self.path.write_text(json.dumps(data), encoding="utf-8")
            load(migrated, self.path)
        finally:
            migrated.close()
        reopened = connect(path)
        try:
            row = reopened.execute("SELECT * FROM accounts").fetchone()
            self.assertEqual(row["uid"], UID)
            self.assertEqual(row["attribution_end"], "2023-11-01")
        finally:
            reopened.close()

    def test_shanghai_boundaries_and_author_restrictions(self):
        for date, included in [
            ("2019-12-31 23:59:59", False), ("2020-01-01 00:00:00", True),
            ("2026-10-21 23:59:59", True), ("2026-10-22 00:00:00", False),
            ("2019-12-31T16:00:00Z", True),
        ]:
            self.assertEqual(normalize(record(date=date), self.account, *self.bounds) is not None, included)
        self.assertEqual(normalize(record(), self.account, *self.bounds)["published_utc"],
                         "2019-12-31T16:00:00+00:00")
        for change in ({"uid": "999"}, {"id": 90071992547409931},
                       {"text": ""}, {"likes": -1}, {"likes": True},
                       {"source_type": "archive", "captured_at": "2019-01-01T00:00:00Z"}):
            with self.assertRaises(ValueError):
                normalize(dict(record(), **change), self.account, *self.bounds)
        with self.assertRaisesRegex(ValueError, "confirmed"):
            normalize(record(), dict(self.account, officialness="unresolved"), *self.bounds)

    def test_long_detail_text_excludes_metadata_asides_and_comments(self):
        parsed = parse_detail(detail(), POST_ID, UID)
        self.assertEqual(parsed["text"], FULL_TEXT)
        self.assertEqual(parsed["text_status"], "source_full")
        with self.assertRaisesRegex(ValueError, "author UID mismatch"):
            parse_detail(detail(uid="999"), POST_ID, UID)
        with self.assertRaisesRegex(ValueError, "ID mismatch"):
            parse_detail(detail(), "123", UID)
        with self.assertRaisesRegex(ValueError, "identity"):
            parse_feed(feed([record()]), "Another outlet")

    def test_rebranded_uid_does_not_import_another_publisher_as_historical_account(self):
        url = "https://www.sina.cn/media/" + UID
        client = FakeClient({url: feed([record()]).replace(
            "测试媒体的微博_新浪新闻", "Unrelated Brand的微博_新浪新闻")})
        run = collect_account(self.db, "test-account", *self.bounds, client, limit=10)
        self.assertIn("identity", run["error"])
        self.assertEqual(run["posts_recovered"], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
        self.assertEqual(client.calls, [url])

    def test_resume_skips_old_pinned_post_without_stopping_and_deduplicates(self):
        pinned = record("90071992547409930", "2019-01-01 00:00")
        client = FakeClient({
            "https://www.sina.cn/media/" + UID: feed([pinned, record()]),
            record()["source_url"]: detail(),
        })
        first = collect_account(self.db, "test-account", *self.bounds, client, limit=1)
        self.assertEqual(first["posts_recovered"], 0)
        second = collect_account(self.db, "test-account", *self.bounds, client, limit=1)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["posts_recovered"], 1)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM provenance").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT text FROM posts").fetchone()[0], FULL_TEXT)
        collect_account(self.db, "test-account", *self.bounds, client, limit=2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)

    def test_attribution_end_filters_same_named_feed_archive_and_import(self):
        with self.db:
            self.db.execute("UPDATE accounts SET attribution_end='2023-11-01'")
        account = self.db.execute("SELECT * FROM accounts").fetchone()
        before = record(date="2023-10-31 23:59:59")
        after = record("90071992547409932", "2023-11-01 00:00")
        self.assertIsNotNone(normalize(before, account, *self.bounds))
        self.assertIsNone(normalize(after, account, *self.bounds))
        self.assertIsNone(normalize(
            dict(after, published_original="2023-10-31T16:00:00Z"), account, *self.bounds))
        url = "https://www.sina.cn/media/" + UID
        client = FakeClient({
            url: feed([after, before]),
            before["source_url"]: detail().replace("2020-01-01 00:00", before["published_original"]),
        })
        run = collect_account(self.db, "test-account", *self.bounds, client, limit=2)
        self.assertEqual(run["posts_recovered"], 1)
        self.assertEqual(client.calls, [url, before["source_url"]])
        archive_url = "https://web.archive.org/web/20240101000000id_/https://weibo.com/fixture"
        html = archived(post_id=after["id"]).replace("2020-01-01 00:00", after["published_original"])
        run = collect_archive(self.db, "test-account", archive_url, *self.bounds,
                              FakeClient({archive_url: html}))
        self.assertIsNone(run["error"])
        self.assertEqual(run["posts_recovered"], 0)
        importing = self.root / "after_cutoff.jsonl"
        importing.write_text(json.dumps(after) + "\n", encoding="utf-8")
        self.assertEqual(import_posts(self.db, importing, *self.bounds),
                         {"accepted": 0, "outside_window": 1})
        self.assertEqual(self.db.execute("SELECT id FROM posts").fetchall()[0]["id"], before["id"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)

    def test_unavailable_pinned_detail_retains_preview_and_continues(self):
        pinned = record("90071992547409930")
        client = FakeClient({
            "https://www.sina.cn/media/" + UID: feed([pinned, record()]),
            pinned["source_url"]: AccessBlocked("Visitor gate"),
            record()["source_url"]: detail(),
        })
        run = collect_account(self.db, "test-account", *self.bounds, client, limit=2)
        self.assertEqual(run["posts_recovered"], 2)
        self.assertIn("1 detail pages unavailable", run["error"])
        statuses = {row["id"]: row["text_status"] for row in self.db.execute("SELECT * FROM posts")}
        self.assertEqual(statuses[pinned["id"]], "truncated")
        self.assertEqual(statuses[POST_ID], "source_full")

    def test_text_quality_and_nullable_engagement_preserve_provenance(self):
        post = normalize(record(), self.account, *self.bounds)
        with self.db:
            put_post(self.db, post)
            put_post(self.db, dict(post, text="短预览", text_status="truncated",
                                   retrieved_at="2026-10-21T14:01:00+00:00"))
            put_post(self.db, dict(post, text="更短正文", retrieved_at="2026-10-21T14:02:00+00:00"))
        self.assertEqual(self.db.execute("SELECT text FROM posts").fetchone()[0], FULL_TEXT)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM provenance").fetchone()[0], 3)
        observation = self.db.execute("SELECT * FROM observations LIMIT 1").fetchone()
        self.assertIsNone(observation["likes"])
        self.assertEqual(observation["comments"], 0)
        self.assertIsNone(observation["reposts"])

    def test_archive_capture_identity_truncation_and_idempotence(self):
        url = "https://web.archive.org/web/20200315170409id_/https://weibo.com/fixture"
        self.assertEqual(archive_time(url), "2020-03-15T17:04:09+00:00")
        self.assertEqual(archive_time(
            "https://web.archive.org/web/20140317074207id_/http://weibo.com:80/cnetnews"),
            "2014-03-17T07:42:07+00:00")
        with self.assertRaises(ValueError):
            archive_time(url.replace("https://weibo.com/", "https://weibo.com:80/"))
        with self.assertRaises(ValueError):
            archive_time("https://web.archive.org/web/latest/https://weibo.com/fixture")
        with self.assertRaisesRegex(AccessBlocked, "different capture"):
            SameHostRedirect().redirect_request(
                Request(url), None, 302, "Found", {},
                url.replace("20200315170409", "20200316170409"))
        with self.assertRaisesRegex(ValueError, "owner UID"):
            parse_archive(archived(uid="999"), UID)
        self.assertEqual(parse_archive(archived(truncated=True), UID)[0]["text_status"], "truncated")
        client = FakeClient({url: archived()})
        for _ in range(2):
            run = collect_archive(self.db, "test-account", url, *self.bounds, client)
            self.assertIsNone(run["error"])
        post = self.db.execute("SELECT * FROM posts").fetchone()
        self.assertEqual(post["text"], "归档正文[微笑]")
        observation = self.db.execute("SELECT * FROM observations").fetchone()
        self.assertEqual(observation["observed_at"], "2020-03-15T17:04:09+00:00")
        self.assertEqual(observation["likes"], 3)
        self.assertIsNone(observation["comments"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)

    def test_archive_json_embedded_feed_is_decoded_without_executing_scripts(self):
        fragment = archived().split("</script>", 1)[1].removesuffix("</html>")
        html = ("<script>$CONFIG['oid']='" + UID + "';</script>"
                "<script>FM.view(" + json.dumps({"html": fragment}) + ");</script>")
        records = parse_archive(html, UID)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], POST_ID)
        self.assertEqual(records[0]["text"], "归档正文[微笑]")

    def test_archive_rebranded_uid_is_rejected_but_reviewed_alias_is_allowed(self):
        url = "https://web.archive.org/web/20200315170409id_/https://weibo.com/fixture"
        changed = archived().replace("测试媒体的微博", "Unrelated Brand的微博")
        run = collect_archive(self.db, "test-account", url, *self.bounds, FakeClient({url: changed}))
        self.assertEqual(run["posts_recovered"], 0)
        self.assertIn("publisher name", run["error"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
        historical_alias = archived().replace("测试媒体的微博", "测试的微博")
        run = collect_archive(
            self.db, "test-account", url, *self.bounds, FakeClient({url: historical_alias}))
        self.assertEqual(run["posts_recovered"], 1)

    def test_archive_logged_out_like_count_remains_observable(self):
        html = archived().replace(
            '<a action-type="fl_like">赞 3</a>',
            '<div class="WB_feed_handle"><a action-type="login">'
            '<span node-type="like_status">&#241;2034</span></a></div>'
            '<span node-type="like_status">99</span>',
        )
        self.assertEqual(parse_archive(html, UID)[0]["likes"], 2034)

    def test_full_text_csv_jsonl_roundtrip_public_omissions_and_import_rollback(self):
        post = normalize(record(), self.account, *self.bounds)
        with self.db:
            put_post(self.db, post)
        output = self.root / "export"
        export(self.db, output)
        with open(output / "posts.csv", encoding="utf-8", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["id"], POST_ID)
        self.assertEqual(row["uid"], UID)
        self.assertEqual(row["text"], FULL_TEXT)
        other = connect(self.root / "other.sqlite")
        try:
            load(other, self.path)
            result = import_posts(other, output / "posts.jsonl", *self.bounds)
            self.assertEqual(result["accepted"], 1)
            for table in ("posts", "provenance", "observations"):
                left = [tuple(row) for row in self.db.execute(f"SELECT * FROM {table}")]
                right = [tuple(row) for row in other.execute(f"SELECT * FROM {table}")]
                self.assertEqual(left, right)
            imported = self.root / "invalid.jsonl"
            imported.write_text(json.dumps(record("90071992547409932")) + '\n{"bad":true}\n')
            with self.assertRaisesRegex(ValueError, "Import line 2"):
                import_posts(other, imported, *self.bounds)
            self.assertEqual(other.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)
        finally:
            other.close()
        manifest = export(self.db, self.root / "public", public=True)
        self.assertEqual(manifest["omitted_posts"], 1)
        self.assertEqual((self.root / "public/posts.jsonl").read_text(), "")
        self.assertIn(POST_ID, (self.root / "public/omissions.csv").read_text())

    def test_offline_cli_export_and_report_include_honest_coverage(self):
        importing = self.root / "import.jsonl"
        importing.write_text(json.dumps(record()) + "\n", encoding="utf-8")
        args = ["--db", str(self.root / "test.sqlite")]
        main(args + ["import", str(importing)])
        main(args + ["export", "--output", str(self.root / "cli-export")])
        target = self.root / "report.md"
        main(args + ["report", "--output", str(target)])
        text = target.read_text()
        self.assertIn("2020-01", text)
        self.assertNotIn("| 2019-12 |", text)
        self.assertIn("unknown (0)", text)
        self.assertIn("0.00 (1)", text)
        self.assertNotIn(FULL_TEXT, text)

    def test_network_safety_and_gzip_replay_decoding(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, limit):
                return gzip.compress("归档页面".encode())

        client = PublicClient()
        with patch.object(client.opener, "open", return_value=Response()):
            self.assertEqual(client.request("https://web.archive.org/example"), "归档页面")
        with self.assertRaisesRegex(ValueError, "pilot-verified"):
            client.get("https://weibo.com/u/" + UID)
        client.blocked = "HTTP 429"
        with self.assertRaises(AccessBlocked), patch.object(client.opener, "open") as request:
            client.request("https://www.sina.cn/media/" + UID)
        request.assert_not_called()

    def test_declared_archive_encoding_preserves_chinese_publisher_evidence(self):
        from email.message import Message

        class Response:
            def __init__(self, encoding="gbk", headers=None):
                self.body = '<meta charset="gb2312"><title>科技资讯网喆</title>'.encode(encoding)
                self.headers = headers

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, limit):
                return self.body

        client = PublicClient()
        with patch.object(client.opener, "open", return_value=Response()), patch("time.sleep"):
            self.assertIn("科技资讯网喆", client.request("https://web.archive.org/example"))
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        with patch.object(client.opener, "open", return_value=Response("utf-8", headers)), patch("time.sleep"):
            self.assertIn("科技资讯网喆", client.request("https://web.archive.org/example"))


if __name__ == "__main__":
    unittest.main()
