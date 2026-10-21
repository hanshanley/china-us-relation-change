import io
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request
from urllib.robotparser import RobotFileParser
from xml.sax.saxutils import escape

from weibo_media.collect import AccessBlocked
from weibo_media.discovery import (
    AliasPolicyRequired, HEADERS, PublisherRedirect, SocialLinks, account_link, publish,
    ranking_rows, run, screen_publisher,
)
from weibo_media.export import write_csv


def spreadsheet(rows):
    xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for number, values in enumerate([HEADERS] + rows, 1):
        xml += f'<row r="{number}">'
        for column, value in enumerate(values):
            xml += (f'<c r="{chr(65 + column)}{number}" t="inlineStr"><is><t>'
                    + escape(str(value)) + '</t></is></c>')
        xml += '</row>'
    xml += '</sheetData></worksheet>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", xml)
    return output.getvalue()


class DiscoveryTest(unittest.TestCase):
    def test_exact_ranked_us_selection_and_source_order_ties(self):
        rows = [
            ["Test A", "a.test", "United States", "Northern America", "English", "General", 1, 90],
            ["Test B", "b.test", "United States", "Northern America", "English", "General", 1, 90],
            ["Test C", "c.test", "United States", "Northern America", "English", "General", 3, 80],
        ]
        selected, total = ranking_rows(spreadsheet(rows), 2)
        self.assertEqual(total, 3)
        self.assertEqual([row["domain"] for row in selected], ["a.test", "b.test"])
        self.assertEqual([row["us_position"] for row in selected], [1, 2])
        with self.assertRaisesRegex(ValueError, "need 4"):
            ranking_rows(spreadsheet(rows), 4)
        rows[2][2] = "Canada"
        with self.assertRaisesRegex(ValueError, "non-U.S."):
            ranking_rows(spreadsheet(rows), 2)
        rows[2][2], rows[2][1] = "United States", "a.test"
        with self.assertRaisesRegex(ValueError, "distinct"):
            ranking_rows(spreadsheet(rows), 2)

    def test_only_profile_links_not_share_buttons_or_incidental_text(self):
        parser = SocialLinks("https://publisher.test/")
        parser.feed(
            '<a href="//weibo.com/u/1765373140?from=publisher">Social</a>'
            '<a href="https://service.weibo.com/share/share.php">Share</a>'
            '<a href="https://weibo.com/123/456">Linked post</a>'
            '<script>var incidental="https://weibo.com/fake";</script>'
            '<a href="https://weibo.com/login">Login</a>'
            '<a href="https://weibo.com.evil.test/fake">Not Weibo</a>'
            '<a href>Empty attribute</a>'
        )
        self.assertEqual(parser.links, {"https://weibo.com/u/1765373140"})
        parser.feed('<map><area href="https://weibo.com/testpublisher" shape="rect"></map>')
        self.assertIn("https://weibo.com/testpublisher", parser.links)
        self.assertEqual(account_link("http://weibo.com/testhandle/", ""),
                         "https://weibo.com/testhandle")
        parser.feed('<a href="http://weibo.com/LA18Chinese/profile?s=6cm7D0">Weibo</a>')
        self.assertIn("https://weibo.com/LA18Chinese", parser.links)
        self.assertEqual(account_link("https://weibo.com/u/123456/profile/", ""),
                         "https://weibo.com/u/123456")
        for path in ("share/profile", "login/profile", "123/456/profile",
                     "testhandle/profile/123"):
            self.assertIsNone(account_link("https://weibo.com/" + path, ""))
        self.assertIsNone(account_link("https://user:pass@weibo.com/fake", ""))

    def test_publisher_widgets_resolve_explicit_ids_but_not_shares(self):
        parser = SocialLinks("https://publisher.test/")
        parser.feed(
            '<iframe src="http://widget.weibo.com/relationship/followbutton.php'
            '?width=63&amp;uid=1734995435"></iframe>'
            '<iframe src="//service.t.sina.com.cn/widget/WeiboShow.php'
            '?height=460&amp;uid=1671481074"></iframe>'
            '<iframe src="https://service.weibo.com/share/share.php?uid=123"></iframe>'
            '<iframe src="https://widget.weibo.com.evil.test/relationship/followbutton.php'
            '?uid=123"></iframe>'
            '<iframe src="https://widget.weibo.com/relationship/followbutton.php'
            '?uid=123&amp;uid=456"></iframe>'
            '<iframe src="https://widget.weibo.com/relationship/followbutton.php'
            '?uid=&amp;uid=123"></iframe>'
            '<iframe src="https://widget.weibo.com:8443/relationship/followbutton.php'
            '?uid=123"></iframe>'
            '<script src="https://widget.weibo.com/relationship/followbutton.php'
            '?uid=123"></script>'
        )
        self.assertEqual(parser.links, {
            "https://weibo.com/u/1734995435", "https://weibo.com/u/1671481074",
        })
        for uid in ("", "0", "-1", "not_an_id"):
            self.assertIsNone(account_link(
                "https://widget.weibo.com/relationship/followbutton.php?uid=" + uid, ""))

    @patch("weibo_media.discovery.time.sleep")
    @patch("weibo_media.discovery.fetch")
    def test_robots_fail_closed_and_no_links_is_not_account_absence(self, fetch, sleep):
        fetch.return_value = ("User-agent: *\nDisallow: /", "https://example.test/robots.txt", 30, False)
        self.assertEqual(screen_publisher("example.test")["status"], "robots_disallowed")
        self.assertEqual(fetch.call_count, 1)
        fetch.reset_mock()
        fetch.return_value = ("<html>Challenge</html>", "https://example.test/robots.txt", 22, False)
        self.assertEqual(screen_publisher("example.test")["status"], "access_error")
        self.assertEqual(fetch.call_count, 1)
        fetch.reset_mock()
        fetch.side_effect = HTTPError("https://example.test/robots.txt", 403, "Forbidden", {}, None)
        self.assertEqual(screen_publisher("example.test")["status"], "http_error")
        self.assertEqual(fetch.call_count, 1)
        fetch.reset_mock()
        fetch.side_effect = [
            ("User-agent: *\nAllow: /", "https://example.test/robots.txt", 25, False),
            ("<html>" + "x" * 2100 + "</html>", "https://example.test/", 2113, False),
        ]
        result = screen_publisher("example.test")
        self.assertEqual(result["status"], "screened_no_link")
        self.assertEqual(result["weibo_links"], [])
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called()

    def test_homepage_redirect_permission_checked_before_following(self):
        redirect = PublisherRedirect()
        policy = RobotFileParser()
        policy.parse(["User-agent: *", "Disallow: /private"])
        redirect.policy, redirect.origin = policy, "example.test"
        request = Request("https://example.test/")
        for url in ("https://example.test/private", "https://other.test/",
                    "https://www.example.test/", "http://example.test/"):
            with self.assertRaises(AccessBlocked):
                redirect.redirect_request(request, None, 302, "Found", {}, url)
        self.assertEqual(redirect.redirect_request(
            request, None, 302, "Found", {}, "https://example.test/news").full_url,
            "https://example.test/news")
        self.assertEqual(redirect.redirect_request(
            request, None, 308, "Permanent Redirect", {}, "https://example.test/news").full_url,
            "https://example.test/news")

    @patch("weibo_media.discovery.time.sleep")
    @patch("weibo_media.discovery.fetch")
    def test_www_alias_gets_independent_policy_before_homepage(self, fetch, sleep):
        fetch.side_effect = [
            ("User-agent: *\nAllow: /", "https://example.test/robots.txt", 25, False),
            AliasPolicyRequired("https://www.example.test/"),
            ("User-agent: *\nDisallow: /", "https://www.example.test/robots.txt", 30, False),
        ]
        result = screen_publisher("example.test")
        self.assertEqual(result["domain"], "example.test")
        self.assertEqual(result["status"], "robots_disallowed")
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(fetch.call_args.args[1], "https://www.example.test/robots.txt")

    @patch("weibo_media.discovery.screen_publisher")
    def test_resume_does_not_rescan_and_changed_roster_is_rejected(self, screen):
        screen.side_effect = lambda domain: {
            "domain": domain, "checked_at": "2026-10-21T14:00:00+00:00",
            "status": "screened_no_link", "page_url": "https://" + domain + "/",
            "weibo_links": [], "bytes_read": 3000, "body_truncated": False, "error": None,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            roster = root / "roster.csv"
            write_csv(roster, [{"domain": "a.test"}, {"domain": "b.test"}], ["domain"])
            first = run(roster, root / "output", 2)
            second = run(roster, root / "output", 2)
            self.assertEqual(first, second)
            self.assertEqual(screen.call_count, 2)
            events = (root / "output/screening.jsonl").read_text().splitlines()
            self.assertEqual({json.loads(line)["domain"] for line in events}, {"a.test", "b.test"})
            roster.write_text("domain\nc.test\n")
            with self.assertRaisesRegex(ValueError, "Roster changed"):
                run(roster, root / "output")

    def test_published_screen_requires_all_1000_rows_and_preserves_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            roster, checks = root / "roster.csv", root / "screening.csv"
            records = [{
                "domain": f"publisher-{n}.test", "us_position": n, "global_rank": n + 2,
                "name": f"Publisher {n}", "overall": 50.5, "status": "screened_no_link",
                "weibo_links": [], "bytes_read": 3000, "body_truncated": False,
                "error": None, "page_url": f"https://publisher-{n}.test/",
            } for n in range(1, 1001)]
            records[0].update(status="candidate_links",
                              weibo_links=["https://weibo.com/testpublisher"])
            write_csv(roster, [{"domain": row["domain"]} for row in records], ["domain"])
            (root / "screening_source.sha256").write_text(hashlib.sha256(roster.read_bytes()).hexdigest())
            write_csv(checks, records[:-1], list(records[0]))
            with self.assertRaisesRegex(ValueError, "all 1000"):
                publish(roster, root, root / "public", root / "report.md")
            write_csv(checks, records, list(records[0]))
            counts = publish(roster, root, root / "public", root / "report.md")
            self.assertEqual(counts, {"candidate_links": 1, "screened_no_link": 999})
            exported = [json.loads(line) for line in
                        (root / "public/us_top1000_screening.jsonl").read_text().splitlines()]
            self.assertEqual(exported, records)
            self.assertIn("not 1,000 verified account decisions", (root / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
