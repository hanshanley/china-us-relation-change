"""Audit publisher information pages and export an explicit account-status ledger."""

import argparse
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import build_opener
from urllib.robotparser import RobotFileParser

from .collect import AccessBlocked, USER_AGENT
from .discovery import PublisherRedirect, SocialLinks, fetch
from .export import write_csv
from .storage import connect, now


class InformationLinks(SocialLinks):
    def __init__(self, page_url):
        super().__init__(page_url)
        self.information_pages = set()

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        value = dict(attrs).get("href") if tag == "a" else None
        if not isinstance(value, str):
            return
        url = urlsplit(urljoin(self.page_url, value))
        if (url.scheme != "https" or url.netloc != urlsplit(self.page_url).netloc
                or url.query or url.fragment or url.username or url.password):
            return
        if re.fullmatch(
                r"/(?:(?:about(?:[-_]us)?|contact(?:[-_]us)?|social(?:-media)?|connect|follow(?:-us)?|"
                r"company|help|info|support|page-weibo)(?:\.(?:html?|php|aspx))?/?){1,3}"
                r"(?:index\.(?:html?|php|aspx))?",
                url.path, re.IGNORECASE):
            self.information_pages.add(url.geturl())


def deep_check(row, timeout=12):
    result = {
        "domain": row["domain"], "checked_at": now(), "pages": [], "candidate_links": [],
        "status": "not_attempted", "error": None,
    }
    if row["status"] != "screened_no_link":
        result.update(status="prior_check_inconclusive", error=row["error"] or row["status"])
        return result
    home = row["page_url"]
    redirects = PublisherRedirect()
    opener = build_opener(redirects)
    try:
        try:
            text, policy_url, _, truncated = fetch(
                opener, urljoin(home, "/robots.txt"), 500_000, timeout)
            if truncated or "<html" in text.lower() or "<!doctype html" in text.lower():
                raise ValueError("Unusable robots response")
            if urlsplit(policy_url).netloc != urlsplit(home).netloc:
                raise AccessBlocked("Robots origin changed; secondary pages not requested")
        except HTTPError as error:
            if error.code not in {404, 410}:
                raise
            if urlsplit(error.geturl()).netloc != urlsplit(home).netloc:
                raise AccessBlocked("Robots origin changed")
            text = "User-agent: *\nAllow: /"
        policy = RobotFileParser()
        policy.parse(text.splitlines())
        redirects.policy, redirects.origin = policy, urlsplit(home).netloc
        delay = max(2, policy.crawl_delay(USER_AGENT) or 0)
        rate = policy.request_rate(USER_AGENT)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 60:
            result.update(status="robots_deferred", error="Requested spacing exceeds 60 seconds")
            return result
        pending, seen = [home], set()
        while pending and len(seen) < 3:
            url = pending.pop(0)
            if url in seen:
                continue
            seen.add(url)
            if not policy.can_fetch(USER_AGENT, url):
                result["pages"].append({"url": url, "status": "robots_disallowed"})
                continue
            time.sleep(delay)
            try:
                body, final, size, truncated = fetch(opener, url, 1_500_000, timeout)
                if "<html" not in body.lower() and "<!doctype html" not in body.lower():
                    raise ValueError("Non-HTML response")
                if any(marker in body.lower() for marker in (
                        "<title>just a moment", "<title>access denied", "verify you are human",
                        "enable javascript and cookies to continue")):
                    raise AccessBlocked("Challenge page")
                parser = InformationLinks(final)
                parser.feed(body)
                links = [{"profile_url": link, "publisher_url": final}
                         for link in sorted(parser.links)]
                result["candidate_links"].extend(links)
                result["pages"].append({
                    "url": final, "status": "readable", "bytes_read": size,
                    "body_truncated": truncated, "weibo_links": sorted(parser.links),
                })
                if url == home:
                    pending.extend(sorted(parser.information_pages))
            except HTTPError as error:
                result["pages"].append({"url": url, "status": "http_error", "error": f"HTTP {error.code}"})
                if error.code in {401, 403, 406, 418, 429, 432}:
                    break
            except (AccessBlocked, OSError, URLError, ValueError, LookupError) as error:
                result["pages"].append({"url": url, "status": "error", "error": str(error)[:300]})
                if isinstance(error, AccessBlocked):
                    break
        readable = sum(page["status"] == "readable" for page in result["pages"])
        result["status"] = ("candidate_found" if result["candidate_links"] else
                            "no_candidate_in_checked_pages" if readable else "no_readable_pages")
    except (HTTPError, AccessBlocked, OSError, URLError, ValueError, LookupError) as error:
        result.update(status="access_error", error=str(error)[:300])
    return result


def verify(screening_path, directory, workers=12):
    with open(screening_path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    journal = directory / "publisher_pages.jsonl"
    completed = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            completed[record["domain"]] = record
    with journal.open("a", encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(deep_check, row) for row in rows if row["domain"] not in completed]
        for job in as_completed(jobs):
            record = job.result()
            completed[record["domain"]] = record
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if len(completed) % 100 == 0:
                print(f"Assessed {len(completed)}/{len(rows)} publishers", flush=True)
    return [completed[row["domain"]] for row in rows]


def domain_key(url):
    return (urlsplit(url).hostname or "").removeprefix("www.")


def outlet_domain(outlet):
    return {"forbes": "forbes.com", "fortune": "fortune.com", "hbr": "hbr.org",
            "nyt": "nytimes.com", "wsj": "wsj.com", "bloomberg": "bloomberg.com",
            "scientific-american": "scientificamerican.com", "cnn": "edition.cnn.com"}.get(
                outlet["id"], domain_key(outlet["source_url"]))


def account_assessments(db, roster, screening, checks):
    outlets = {row["id"]: dict(row) for row in db.execute("SELECT * FROM outlets")}
    accounts = [dict(row) for row in db.execute("SELECT * FROM accounts")]
    mapping = {}
    for account in accounts:
        outlet = outlets[account["outlet_id"]]
        main = outlet_domain(outlet)
        mapping.setdefault(main, []).append(account)
    results = []
    for row in roster:
        matched = mapping.get(row["domain"], [])
        manual = [{
            "outlet_id": outlet["id"], "research_status": outlet["research_status"],
            "notes": outlet["notes"], "us_basis": outlet["us_basis"],
        } for outlet in outlets.values() if outlet_domain(outlet) == row["domain"]]
        confirmed = [a for a in matched if a["officialness"] == "confirmed"]
        candidates = checks[row["domain"]]["candidate_links"]
        existence = {a["existence"] for a in confirmed}
        status = ("confirmed_current_evidence" if "current_evidence" in existence else
                  "confirmed_historical_only" if confirmed else
                  "candidate_requires_verification" if candidates else "unknown")
        counts = {a["id"]: db.execute("SELECT COUNT(*) FROM posts WHERE account_id=?",
                                     (a["id"],)).fetchone()[0] for a in confirmed}
        collection = {}
        for account in confirmed:
            run = db.execute("SELECT * FROM runs WHERE account_id=? ORDER BY id DESC LIMIT 1",
                             (account["id"],)).fetchone()
            collection[account["id"]] = {
                "recovered_posts": counts[account["id"]],
                "status": ("posts_recovered_partial" if counts[account["id"]] else
                           "attempted_no_posts" if run else "not_attempted"),
                "latest_run_status": run["status"] if run else None,
                "error": run["error"] if run else None,
                "limitations": run["limitations"] if run else None,
            }
        evidence = [dict(e) for a in confirmed for e in db.execute(
            "SELECT * FROM evidence WHERE account_id=? ORDER BY id", (a["id"],))]
        results.append(dict(
            row, account_status=status,
            account_ids=[a["id"] for a in confirmed], account_uids=[a["uid"] for a in confirmed],
            account_profiles=[a["profile_url"] for a in confirmed],
            relationships=[a["relationship"] for a in confirmed],
            has_ever_official_weibo=True if confirmed else None,
            has_current_profile_evidence=True if "current_evidence" in existence else None,
            verified_no_account=False,
            assessment_reason=("Primary identity evidence; see evidence records and edition relationship."
                               if confirmed else "No verified account decision; missing links are not proof of absence."),
            post_counts=counts, recovered_posts=sum(counts.values()),
            has_collected_posts=bool(sum(counts.values())),
            post_collection=collection,
            homepage_check=screening[row["domain"]]["status"],
            publisher_page_check=checks[row["domain"]], evidence=evidence,
            manual_review=manual,
        ))
    return results


def publish(db, roster_path, screening_path, journal_path, output):
    with open(roster_path, newline="", encoding="utf-8") as stream:
        roster = list(csv.DictReader(stream))
    with open(screening_path, newline="", encoding="utf-8") as stream:
        screening = {row["domain"]: row for row in csv.DictReader(stream)}
    checks = {}
    for line in Path(journal_path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        checks[row["domain"]] = row
    domains = {row["domain"] for row in roster}
    if len(roster) != 1000 or len(domains) != 1000 or domains != set(screening) or domains != set(checks):
        raise ValueError("Assessment requires exactly the same 1000 distinct domains at every stage")
    results = account_assessments(db, roster, screening, checks)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "us_top1000_accounts.csv", results, list(results[0]))
    (output / "us_top1000_accounts.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    ranked = [dict(row, roster_scope="ranked_us_1000") for row in results]
    supplemental_roster = []
    for outlet in db.execute("SELECT * FROM outlets ORDER BY id"):
        domain = outlet_domain(outlet)
        if domain in domains:
            continue
        record = dict.fromkeys(roster[0])
        record.update(name=outlet["name"], domain=domain)
        supplemental_roster.append(record)
        screening[domain] = {"status": "outside_ranked_screening"}
        checks[domain] = {"status": "targeted_registry_review", "candidate_links": [], "pages": []}
    supplemental = [dict(row, roster_scope="supplementary_manual")
                    for row in account_assessments(db, supplemental_roster, screening, checks)]
    combined = ranked + supplemental
    write_csv(output / "outlet_account_assessments.csv", combined, list(combined[0]))
    (output / "outlet_account_assessments.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in combined), encoding="utf-8")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening", default="data/discovery/us_top1000_screening.csv")
    parser.add_argument("--work", default="data/local/discovery/secondary-pages")
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=12)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--db", default="data/local/weibo.sqlite")
    args = parser.parse_args()
    if args.publish:
        db = connect(args.db)
        try:
            db.execute("BEGIN")
            results = publish(db, "data/discovery/us_top1000.csv", args.screening,
                              Path(args.work) / "publisher_pages.jsonl", "data/discovery")
            print(json.dumps({"assessed": len(results)}, indent=2))
        finally:
            db.close()
    else:
        verify(args.screening, args.work, args.workers)


if __name__ == "__main__":
    main()
