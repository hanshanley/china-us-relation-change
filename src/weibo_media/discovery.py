"""Reproducible U.S. publisher roster and bounded, robots-aware link screening."""

import argparse
import csv
import hashlib
import io
import json
import re
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from .collect import AccessBlocked, USER_AGENT
from .export import write_csv
from .storage import now


SOURCE = "https://www.scimagomedia.com/rankings.php?country=United+States"
DOWNLOAD = SOURCE + "&download=1"
NAMESPACE = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
HEADERS = ["Media", "Domain", "Country", "Region", "Language", "Typology",
           "Global_rank", "Overall"]
RESULT_FIELDS = ["domain", "checked_at", "status", "page_url", "weibo_links",
                 "bytes_read", "body_truncated", "error"]


def ranking_rows(content, limit=1000):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ElementTree.fromstring(archive.read("xl/sharedStrings.xml")).findall(
                    "m:si", NAMESPACE):
                strings.append("".join(node.text or "" for node in item.findall(".//m:t", NAMESPACE)))
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    matrix = []
    for row in sheet.findall(".//m:row", NAMESPACE):
        values = [""] * len(HEADERS)
        for cell in row.findall("m:c", NAMESPACE):
            column = re.match(r"([A-Z]+)", cell.attrib["r"])[1]
            index = 0
            for char in column:
                index = index * 26 + ord(char) - ord("A") + 1
            value = cell.find("m:v", NAMESPACE)
            text = value.text if value is not None else "".join(
                node.text or "" for node in cell.findall(".//m:t", NAMESPACE))
            if cell.get("t") == "s":
                text = strings[int(text)]
            if index <= len(values):
                values[index - 1] = text or ""
        matrix.append(values)
    if not matrix or matrix[0] != HEADERS:
        raise ValueError("Unexpected SCImago download columns")
    records = []
    seen = set()
    previous = -1
    for values in matrix[1:]:
        name, domain, country, region, language, typology, rank, score = values
        domain = domain.strip().lower()
        if country != "United States":
            raise ValueError("Download includes a non-U.S. country label")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", domain):
            raise ValueError("Unexpected publisher domain")
        rank = int(rank)
        if rank < previous or domain in seen:
            raise ValueError("Ranking must be ordered with distinct domains")
        previous = rank
        seen.add(domain)
        records.append({
            "us_position": len(records) + 1, "global_rank": rank, "name": name.strip(),
            "domain": domain, "country": country, "region": region,
            "language": language, "typology": typology, "overall": float(score),
            "ranking_source": SOURCE,
        })
    if len(records) < limit:
        raise ValueError(f"Only {len(records)} distinct U.S. publishers; need {limit}")
    return records[:limit], len(records)


def account_link(value, page_url):
    if not isinstance(value, str):
        return None
    url = urlsplit(urljoin(page_url, value.strip()))
    if url.scheme not in {"https", "http"} or url.username or url.password:
        return None
    host = url.hostname or ""
    path = url.path.rstrip("/")
    if (host, path) in {
            ("widget.weibo.com", "/relationship/followbutton.php"),
            ("widget.weibo.com", "/weiboshow/index.php"),
            ("service.t.sina.com.cn", "/widget/WeiboShow.php")}:
        try:
            if url.port not in (None, 443 if url.scheme == "https" else 80):
                return None
        except ValueError:
            return None
        uids = parse_qs(url.query, keep_blank_values=True).get("uid", [])
        if len(uids) == 1 and re.fullmatch(r"[1-9][0-9]*", uids[0]):
            return "https://weibo.com/u/" + uids[0]
        return None
    if host in {"weibo.com", "www.weibo.com", "weibo.cn", "www.weibo.cn", "e.weibo.com"}:
        legacy = re.fullmatch(r"/p/(?:100505|100606)([0-9]+)(?:/home)?", path)
        if legacy:
            return "https://weibo.com/u/" + legacy[1]
        match = re.fullmatch(r"/(u/[0-9]+|[A-Za-z0-9_]+)(?:/profile)?", path)
        reserved = {"login", "signup", "register", "share", "home", "search", "about",
                    "p", "tv", "n", "u", "international", "overseas", "newlogin"}
        if match and match[1].lower() not in reserved:
            return "https://" + ("weibo.com" if host == "e.weibo.com" else host) + "/" + match[1]
    if host == "m.weibo.cn" and re.fullmatch(r"/(?:u|profile)/[0-9]+", path):
        return "https://" + host + path
    return None


class SocialLinks(HTMLParser):
    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "area", "iframe"}:
            value = dict(attrs).get("src" if tag == "iframe" else "href", "")
            link = account_link(value, self.page_url)
            if link:
                self.links.add(link)


class AliasPolicyRequired(AccessBlocked):
    def __init__(self, url):
        self.url = url
        super().__init__("Homepage www alias needs its own robots check")


class PublisherRedirect(HTTPRedirectHandler):
    policy = None
    origin = None
    http_error_308 = HTTPRedirectHandler.http_error_302

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        old, new = urlsplit(request.full_url), urlsplit(newurl)
        if (new.scheme != "https" or new.username or new.password or new.port not in (None, 443)
                or (new.hostname or "").removeprefix("www.") !=
                (old.hostname or "").removeprefix("www.")):
            raise AccessBlocked("Cross-publisher or non-HTTPS redirect not followed")
        if self.policy is not None:
            if new.netloc != self.origin:
                raise AliasPolicyRequired(newurl)
            if not self.policy.can_fetch(USER_AGENT, newurl):
                raise AccessBlocked("Homepage redirect lacks robots permission")
        return super().redirect_request(request, fp, 307 if code == 308 else code, msg, headers, newurl)


def fetch(opener, url, cap, timeout):
    with opener.open(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        body = response.read(cap + 1)
        charset = response.headers.get_content_charset() or "utf-8"
        return body[:cap].decode(charset, errors="replace"), response.geturl(), len(body), len(body) > cap


def screen_publisher(domain, timeout=12, allow_alias_retry=True):
    result = dict.fromkeys(RESULT_FIELDS)
    result.update(domain=domain, checked_at=now(), status="error", weibo_links=[],
                  bytes_read=0, body_truncated=False, error=None)
    redirects = PublisherRedirect()
    opener = build_opener(redirects)
    home = "https://" + domain + "/"
    try:
        try:
            robots, robots_url, _, truncated = fetch(opener, home + "robots.txt", 500_000, timeout)
            if truncated:
                raise ValueError("Robots response exceeds limit")
            if "<html" in robots.lower() or "<!doctype html" in robots.lower():
                raise ValueError("Robots endpoint returned HTML, not a usable policy")
            home = urljoin(robots_url, "/")
        except HTTPError as error:
            if error.code not in {404, 410}:
                raise
            home = urljoin(error.geturl(), "/")
            robots = "User-agent: *\nAllow: /"
        policy = RobotFileParser()
        policy.parse(robots.splitlines())
        if not policy.can_fetch(USER_AGENT, home):
            result["status"] = "robots_disallowed"
            return result
        delay = max(2, policy.crawl_delay(USER_AGENT) or 0)
        rate = policy.request_rate(USER_AGENT)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 60:
            result.update(status="robots_deferred", error="Publisher requests spacing above 60 seconds")
            return result
        time.sleep(delay)
        redirects.policy, redirects.origin = policy, urlsplit(home).netloc
        body, page_url, size, truncated = fetch(opener, home, 1_500_000, timeout)
        result.update(page_url=page_url, bytes_read=size, body_truncated=truncated)
        if urlsplit(home).netloc != urlsplit(page_url).netloc:
            # A www alias may have its own robots rules; do not assume permission.
            result.update(status="redirect_policy_unchecked", error="Homepage changed host after robots check")
            return result
        if not policy.can_fetch(USER_AGENT, page_url):
            result.update(status="redirect_policy_unchecked", error="Homepage redirected to a disallowed path")
            return result
        if any(marker in body.lower() for marker in (
                "<title>just a moment", "<title>access denied", "<title>captcha",
                "verify you are human", "enable javascript and cookies to continue")):
            result["status"] = "challenge"
            return result
        if "<html" not in body.lower() and "<!doctype html" not in body.lower():
            result["status"] = "inconclusive_non_html"
            return result
        parser = SocialLinks(page_url)
        parser.feed(body)
        result["weibo_links"] = sorted(parser.links)
        result["status"] = ("candidate_links" if parser.links else
                            "inconclusive_short_page" if size < 2000 else
                            "screened_no_link")
    except AliasPolicyRequired as error:
        if allow_alias_retry:
            time.sleep(2)
            result = screen_publisher(urlsplit(error.url).hostname, timeout, False)
            result["domain"] = domain
        else:
            result.update(status="access_error", error="Repeated www alias change; not followed")
    except HTTPError as error:
        result.update(status="http_error", error=f"HTTP {error.code}")
    except (AccessBlocked, URLError, OSError, ValueError, LookupError) as error:
        result.update(status="access_error", error=str(error)[:300])
    return result


def run(roster_path, output, workers=8, retry_redirects=False):
    roster_path, output = Path(roster_path), Path(output)
    with roster_path.open(encoding="utf-8", newline="") as stream:
        roster = list(csv.DictReader(stream))
    domains = [row["domain"] for row in roster]
    if len(set(domains)) != len(domains):
        raise ValueError("Duplicate roster domains")
    output.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(roster_path.read_bytes()).hexdigest()
    state_path = output / "screening_source.sha256"
    if state_path.exists() and state_path.read_text().strip() != identity:
        raise ValueError("Roster changed; use a fresh output directory")
    state_path.write_text(identity + "\n")
    journal = output / "screening.jsonl"
    completed = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            completed[record["domain"]] = record
    if retry_redirects:
        completed = {domain: record for domain, record in completed.items()
                     if record["error"] not in {
                         "Homepage redirect lacks robots permission", "HTTP 308",
                         "Homepage www alias needs its own robots check"}}
    with journal.open("a", encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(screen_publisher, domain): domain for domain in domains
                   if domain not in completed}
        for future in as_completed(futures):
            record = future.result()
            completed[record["domain"]] = record
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if len(completed) % 100 == 0:
                print(f"Screened {len(completed)}/{len(domains)} publishers", flush=True)
    results = [dict(row, **{key: completed[row["domain"]][key] for key in RESULT_FIELDS
                           if key != "domain"}) for row in roster]
    write_csv(output / "screening.csv", results, list(results[0]))
    return results


def publish(roster_path, screening_directory, directory, report_path):
    roster_path, screening_directory = Path(roster_path), Path(screening_directory)
    expected = hashlib.sha256(roster_path.read_bytes()).hexdigest()
    if (screening_directory / "screening_source.sha256").read_text().strip() != expected:
        raise ValueError("Screening does not match the roster")
    with (screening_directory / "screening.csv").open(encoding="utf-8", newline="") as stream:
        results = list(csv.DictReader(stream))
    with roster_path.open(encoding="utf-8", newline="") as stream:
        domains = [row["domain"] for row in csv.DictReader(stream)]
    if len(set(domains)) != 1000 or [row["domain"] for row in results] != domains:
        raise ValueError("Publication requires all 1000 distinct roster domains in source order")
    counts = Counter(row["status"] for row in results)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Restore the structured link arrays before writing the machine-readable exports.
    for row in results:
        row["weibo_links"] = json.loads(row["weibo_links"])
        for key in ("us_position", "global_rank", "bytes_read"):
            row[key] = int(row[key])
        row["overall"] = float(row["overall"])
        row["body_truncated"] = row["body_truncated"] == "True"
        row["error"] = row["error"] or None
    write_csv(directory / "us_top1000_screening.csv", results, list(results[0]))
    (directory / "us_top1000_screening.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    lines = [
        "# Top 1,000 U.S. news websites: Weibo screening", "",
        f"Published: {now()}. All 1,000 selected domains have an attempted-check record.", "",
        "## U.S.-only ranking and selection", "",
        f"Source: [SCImago U.S. media ranking]({SOURCE}), retrieved October 21, 2026; "
        "[methodology](https://www.scimagomedia.com/methodology.php). "
        "The source download contains 1,139 U.S.-classified media domains. We selected the first "
        "1,000 in published order, retaining tie order and recording both global rank and U.S. "
        "selection position. This is not the global top 1,000 and not an all-industry website list.", "",
        "**Ranking is digital reputation, not audience/traffic.** SCImago combines four equally "
        "weighted SEO/link indicators. Country is its place-of-publication/media-reference "
        "classification, not independently verified ownership. The download has no edition date; "
        "the retrieval date must not be presented as a ranking vintage. Some specialist/Chinese "
        "editions in our manual inventory are absent from this source.", "",
        "SCImago (n.d.), *SCImago Media Rankings* [Portal], retrieved October 21, 2026. "
        "Source data permits non-commercial reuse with attribution; the derived ranking retains "
        "that restriction. The manifest records the download SHA-256 and selection rule.", "",
        "## Actual screening outcomes", "",
        "| Outcome | Websites |", "|---|---:|",
    ]
    lines.extend(f"| {status} | {count} |" for status, count in sorted(counts.items()))
    lines += [
        "", "Each check requests the publisher robots policy and, only if allowed, at most 1.5 MB "
        "of the homepage. Explicit robots 404/410 means no rules at that path; policy errors, "
        "HTML challenge pages posing as robots files, login/rate limits, unsupported redirects "
        "and inaccessible hosts are not bypassed. Requests are paced per domain with bounded "
        "cross-domain concurrency. A recovery pass checks www aliases' robots independently "
        "and supports HTTPS 308 redirects; old events remain in the local journal while exports "
        "use the latest result per domain. The earlier interrupted exploratory pass is excluded.", "",
        "**This is 1,000 attempted publisher checks, not 1,000 verified account decisions.** "
        "`screened_no_link` means no recognized account link in the returned snapshot; it is "
        "not a negative Weibo-account finding. Tiny/non-HTML pages, blocked pages and robots "
        "restrictions are inconclusive. JavaScript-rendered links, Chinese editions, historical "
        "pages, contact pages and alternate domains are outside this bounded homepage pass. "
        "These are capture-time outcomes: later support for explicit profile tabs and known "
        "UID-bearing follow/timeline widgets does not retroactively reprocess saved checks.", "",
        "## Publisher-link candidates", "",
        "Links below require manual identity/edition review; homepage links can be partners rather "
        "than the publisher's own account. Known follow/timeline widgets expose candidate UIDs, "
        "not automatic officialness. Share buttons, post URLs, ambiguous widget UIDs and "
        "incidental script text are not classified as account links.", "",
        "| U.S. position | Publisher | Homepage | Profile links |", "|---:|---|---|---|",
    ]
    for row in results:
        if row["weibo_links"]:
            links = ", ".join(f"[profile]({url})" for url in row["weibo_links"])
            lines.append(f"| {row['us_position']} | {row['name'].replace('|', '/')} | "
                         f"[checked page]({row['page_url']}) | {links} |")
    if not counts["candidate_links"]:
        lines.append("| - | No recognized profile links in this bounded pass | - | - |")
    lines += [
        "", "## Manually verified identities remain separate", "",
        "See the [evidence-backed account inventory](weibo_media_inventory.md). Expanded targeted "
        "verification resolved WSJ Chinese as historically official (`chinesewsj`, UID `1649159940`) "
        "using an archived publisher link and archived platform UID. It also confirmed "
        "National Geographic's Chinese-language account (`1644225642`) and Scientific American's "
        "Chinese-edition magazine account (`1235572171`), plus MIT Technology Review's "
        "Chinese-language account (`1738690784`). These three additional specialist brands "
        "do not appear in the selected SCImago 1,000; they are supplementary discoveries, not results "
        "manufactured from the ranking scan. Subsequent [collection follow-up](collection_followup.md) "
        "also verified Bloomberg China, China Press and two regional World Journal accounts, "
        "collected the newly verified public feeds, and investigated historical archive failures. "
        "The next [discovery round](discovery_round2.md) adds the historical Fast Company "
        "publisher at U.S. source position33 and further supplementary accounts, while auditing "
        "UID rebranding and same-name false leads. The [continuing iteration](discovery_iteration3.md) "
        "adds further business, technology, U.S. Chinese-language and licensed specialist-media "
        "identities, including the separate NYT-licensed T China style edition. It also records "
        "publisher-announced license termination: unchanged profile names do not establish a "
        "continuing U.S. license. [Further publisher traces](discovery_iteration4.md) verify "
        "additional ranked publishers and reconstruct historical channel/UID changes without "
        "relabeling independent successor posts. [Continued newsroom discovery](discovery_iteration5.md) "
        "adds the historical NPR identity at source position5 and recovers archive-bound native "
        "details without relaxing live profile-name checks. [Publisher account clusters]"
        "(discovery_iteration6.md) adds the historical Popular Science Chinese edition and "
        "explicitly labeled release-distribution channels; multiple sector feeds are not "
        "independent newsrooms. [Publication identity follow-up](discovery_iteration7.md) resolves "
        "Knowledge at Wharton's locator and reassesses Popular Science's current identity and "
        "distribution-based cutoff. [Ranked-publisher follow-up](discovery_iteration8.md) checks "
        "five further selected-cohort publishers without converting missing evidence into account "
        "negatives, and verifies the supplementary Men's Health Chinese edition. "
        "[Local-publisher follow-up](discovery_iteration9.md) adds the archive-bound Chinese Radio "
        "Seattle identity and five more ranked reviews, while keeping newly located Chicago/New York "
        "candidates separate from resolved accounts. Current status and legal operator "
        "uncertainty remain explicit.", "",
        "## Complete machine-readable deliverables", "",
        "- [All 1,000 ranked U.S. domains](../data/discovery/us_top1000.csv)",
        "- [Ranking source manifest](../data/discovery/us_top1000.manifest.json)",
        "- [All 1,000 checks, CSV](../data/discovery/us_top1000_screening.csv)",
        "- [All 1,000 checks, JSONL](../data/discovery/us_top1000_screening.jsonl)", "",
        "- [All 1,000 account decisions and post counts, CSV](../data/discovery/us_top1000_accounts.csv)",
        "- [All 1,000 account decisions and evidence, JSONL](../data/discovery/us_top1000_accounts.jsonl)",
        "- [Ranked plus supplemental outlet assessments, CSV](../data/discovery/outlet_account_assessments.csv)",
        "- [Ranked plus supplemental outlet assessments, JSONL](../data/discovery/outlet_account_assessments.jsonl)", "",
        "Every roster row is retained, including blocked and inconclusive checks. No post text "
        "or publisher article bodies are included in these screening exports. The account "
        "assessment fields distinguish confirmed identities, historical-only evidence and unknowns; "
        "there are no verified-negative account findings. Collected-post booleans refer only to "
        "our recovered corpus, not true account output.", "",
        "## Reproduce or resume", "",
        "Requires Python 3.9+ and no additional packages. From the repository root:", "",
        "```sh", "export PYTHONPATH=src", "mkdir -p data/local/discovery",
        f"curl --fail --location '{DOWNLOAD}' --output data/local/discovery/scimago-us.xlsx",
        "python3 -m weibo_media.discovery roster data/local/discovery/scimago-us.xlsx",
        "python3 -m weibo_media.discovery screen --workers 12",
        "python3 -m weibo_media.discovery publish", "```", "",
        "The roster command validates U.S. labels, ordering and distinct domains before selecting "
        "exactly 1,000 rows. `us_position` is a selection index, not an untied published rank. "
        "Screening checkpoints are local at `data/local/discovery/us1000-validated/screening.jsonl`. "
        "Reruns resume without repeating completed domains; use a fresh `screen --output` directory "
        "for a new observation. `screen --retry-redirects` revisits prior unsupported redirects "
        "without removing the original journal events. To publish a nondefault checkpoint, supply "
        "`publish --screening PATH`. Publication rejects incomplete or mismatched rosters.", "",
    ]
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("roster")
    build.add_argument("xlsx")
    build.add_argument("--output", default="data/discovery/us_top1000.csv")
    build.add_argument("--limit", type=int, default=1000)
    screen = commands.add_parser("screen")
    screen.add_argument("--roster", default="data/discovery/us_top1000.csv")
    screen.add_argument("--output", default="data/local/discovery/us1000-validated")
    screen.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    screen.add_argument("--retry-redirects", action="store_true",
                        help="Retry prior unsupported redirect failures; preserve old journal events")
    publishing = commands.add_parser("publish")
    publishing.add_argument("--roster", default="data/discovery/us_top1000.csv")
    publishing.add_argument("--screening", default="data/local/discovery/us1000-validated")
    publishing.add_argument("--output", default="data/discovery")
    publishing.add_argument("--report", default="reports/top1000_us_screening.md")
    args = parser.parse_args()
    if args.command == "roster":
        if args.limit < 1:
            raise ValueError("Roster limit must be positive")
        content = Path(args.xlsx).read_bytes()
        records, total = ranking_rows(content, args.limit)
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(path, records, list(records[0]))
        manifest = {
            "source_url": SOURCE, "download_url": DOWNLOAD, "processed_at": now(),
            "source_sha256": hashlib.sha256(content).hexdigest(),
            "source_rows": total, "selected_rows": len(records),
            "selection": "First N distinct U.S.-labeled domains in downloaded source order; ties retain source order.",
            "metric": "SCImago digital reputation, not audience/traffic or editorial quality.",
            "ranking_vintage": "Not specified in download; processed_at is not an edition date.",
            "country": "Source classification; not independently verified U.S. ownership.",
            "reuse": "Non-commercial use with citation, per source website.",
        }
        path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))
    elif args.command == "screen":
        results = run(args.roster, args.output, args.workers, args.retry_redirects)
        print(json.dumps({"screened": len(results)}, indent=2))
    else:
        print(json.dumps(publish(args.roster, args.screening, args.output, args.report), indent=2))


if __name__ == "__main__":
    main()
