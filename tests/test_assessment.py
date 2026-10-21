import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weibo_media.assessment import InformationLinks, account_assessments, deep_check, publish
from weibo_media.discovery import account_link
from weibo_media.export import write_csv
from weibo_media.registry import load
from weibo_media.storage import connect
from test_pipeline import registry


class AssessmentTest(unittest.TestCase):
    def test_information_page_selection_does_not_crawl_articles_or_external_sites(self):
        parser = InformationLinks("https://publisher.test/")
        parser.feed(
            '<a href="/about-us.html">About</a><a href="/help/contact-us">Contact</a>'
            '<a href="/news/about-the-election">Article</a>'
            '<a href="https://other.test/about/">Other site</a>'
            '<a href="/contact?tracking=yes">Query</a><a href>Missing</a>'
            '<a href="https://e.weibo.com/testpublisher">Weibo</a>'
        )
        self.assertEqual(parser.information_pages, {
            "https://publisher.test/about-us.html", "https://publisher.test/help/contact-us",
        })
        self.assertEqual(parser.links, {"https://weibo.com/testpublisher"})
        self.assertEqual(account_link("https://weibo.com/p/1006061234567890/home", ""),
                         "https://weibo.com/u/1234567890")

    @patch("weibo_media.assessment.time.sleep")
    @patch("weibo_media.assessment.fetch")
    def test_secondary_page_finds_candidate_with_publisher_provenance(self, fetch, sleep):
        fetch.side_effect = [
            ("User-agent: *\nAllow: /", "https://publisher.test/robots.txt", 30, False),
            ('<html><a href="/about">About</a><a href="/contact">Contact</a></html>',
             "https://publisher.test/", 80, False),
            ('<html><a href="https://weibo.com/testpublisher">Weibo</a></html>',
             "https://publisher.test/about", 80, False),
            ("<html>No links</html>", "https://publisher.test/contact", 30, False),
        ]
        result = deep_check({"domain": "publisher.test", "status": "screened_no_link",
                             "page_url": "https://publisher.test/", "error": ""})
        self.assertEqual(result["status"], "candidate_found")
        self.assertEqual(len(result["pages"]), 3)
        self.assertEqual(result["candidate_links"], [{
            "profile_url": "https://weibo.com/testpublisher",
            "publisher_url": "https://publisher.test/about",
        }])
        self.assertEqual(fetch.call_count, 4)

    @patch("weibo_media.assessment.fetch")
    def test_previous_access_block_is_retained_not_bypassed(self, fetch):
        result = deep_check({"domain": "publisher.test", "status": "http_error",
                             "page_url": "", "error": "HTTP 403"})
        self.assertEqual(result["status"], "prior_check_inconclusive")
        self.assertEqual(result["pages"], [])
        fetch.assert_not_called()

    def test_known_account_overrides_missing_links_but_unknown_is_not_no(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = registry()
            data["outlets"][0]["source_url"] = "https://publisher.test/"
            source = root / "registry.json"
            source.write_text(json.dumps(data))
            db = connect(root / "database.sqlite")
            load(db, source)
            roster = [{"domain": "publisher.test"}, {"domain": "unknown.test"}]
            screening = {row["domain"]: {"status": "screened_no_link"} for row in roster}
            checks = {row["domain"]: {"candidate_links": []} for row in roster}
            results = account_assessments(db, roster, screening, checks)
            self.assertEqual(results[0]["account_status"], "confirmed_current_evidence")
            self.assertEqual(results[0]["account_ids"], ["test-account"])
            self.assertEqual(results[1]["account_status"], "unknown")
            self.assertIsNone(results[1]["has_ever_official_weibo"])
            self.assertTrue(results[0]["has_ever_official_weibo"])
            self.assertTrue(all(row["verified_no_account"] is False for row in results))
            self.assertEqual(results[0]["recovered_posts"], 0)
            self.assertEqual(len(results[0]["evidence"]), 1)
            db.execute("UPDATE accounts SET existence='historical'")
            self.assertEqual(account_assessments(db, roster, screening, checks)[0]["account_status"],
                             "confirmed_historical_only")
            self.assertIsNone(account_assessments(
                db, roster, screening, checks)[0]["has_current_profile_evidence"])
            db.close()

    def test_publication_refuses_an_incomplete_domain_assessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            roster, screening, journal = root / "roster.csv", root / "screen.csv", root / "checks.jsonl"
            write_csv(roster, [{"domain": "only.test"}], ["domain"])
            write_csv(screening, [{"domain": "only.test"}], ["domain"])
            journal.write_text(json.dumps({"domain": "only.test"}))
            db = connect(root / "database.sqlite")
            with self.assertRaisesRegex(ValueError, "1000 distinct domains"):
                publish(db, roster, screening, journal, root / "public")
            db.close()

    def test_complete_ranked_ledger_keeps_supplemental_verified_outlet_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "registry.json"
            data = registry()
            data["outlets"].append(dict(data["outlets"][0], id="cnn", name="CNN",
                                        source_url="https://www.cnn.com/"))
            source.write_text(json.dumps(data))
            db = connect(root / "database.sqlite")
            load(db, source)
            rows = [{"domain": f"ranked-{n}.test", "name": f"Publisher {n}", "us_position": n}
                    for n in range(1, 1001)]
            rows[0].update(domain="edition.cnn.com", name="CNN")
            roster, screening, journal = root / "roster.csv", root / "screen.csv", root / "checks.jsonl"
            write_csv(roster, rows, list(rows[0]))
            write_csv(screening, [{"domain": r["domain"], "status": "screened_no_link"}
                                  for r in rows], ["domain", "status"])
            journal.write_text("".join(json.dumps({
                "domain": r["domain"], "candidate_links": [], "pages": [],
                "status": "no_candidate_in_checked_pages",
            }) + "\n" for r in rows))
            results = publish(db, roster, screening, journal, root / "public")
            self.assertEqual(len(results), 1000)
            combined = [json.loads(line) for line in
                        (root / "public/outlet_account_assessments.jsonl").read_text().splitlines()]
            self.assertEqual(len(combined), 1001)
            self.assertTrue(all(r["roster_scope"] == "ranked_us_1000" for r in combined[:1000]))
            self.assertEqual(combined[-1]["roster_scope"], "supplementary_manual")
            self.assertIsNone(combined[-1]["us_position"])
            self.assertTrue(combined[-1]["has_ever_official_weibo"])
            self.assertEqual(combined[-1]["account_ids"], ["test-account"])
            self.assertEqual(combined[0]["manual_review"][0]["outlet_id"], "cnn")
            self.assertEqual(combined[-1]["post_collection"]["test-account"]["status"], "not_attempted")
            self.assertTrue(all(r["has_ever_official_weibo"] is None for r in combined[:1000]))
            db.close()


if __name__ == "__main__":
    unittest.main()
