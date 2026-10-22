import gzip
import io
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

from .registry import valid_url
from .storage import json_text, now, put_post


SHANGHAI = ZoneInfo("Asia/Shanghai")
USER_AGENT = "weibo-media-research/0.1"
LIMITATIONS = (
    "Public Sina syndication feed only; no historical pagination is exposed. "
    "Feed exhaustion is not historical completeness. Detail text is source_full, "
    "not independently verified against Weibo. Repost classification may be unknown. "
    "Engagement counts are source snapshots and may be stale."
)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def window(start, end):
    first = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=SHANGHAI)
    last = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=SHANGHAI) + timedelta(days=1)
    if last <= first:
        raise ValueError("End date must not precede start date")
    return timestamp(first.isoformat()), timestamp(last.isoformat())


class Node:
    def __init__(self, tag="", attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []

    def find(self, class_name):
        return [node for node in self.walk()
                if class_name in node.attrs.get("class", "").split()]

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        if self.tag in {"script", "style", "svg"}:
            return ""
        if self.attrs.get("action-type") == "fl_unfold":
            return ""
        if self.tag == "img":
            return self.attrs.get("alt") or ""
        parts = []
        for child in self.children:
            parts.append(child.text() if isinstance(child, Node) else child)
            if isinstance(child, Node) and child.tag in {"p", "div", "br"}:
                parts.append("\n")
        return "".join(parts).strip()


class HTMLTree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def numeric(value):
    value = value.strip()
    return int(value) if re.fullmatch(r"[0-9]+", value) else None


def parse_feed(html, expected_name=None):
    tree = HTMLTree(html).root
    if expected_name:
        titles = [node.text() for node in tree.walk() if node.tag == "title"]
        if titles != [expected_name + "的微博_新浪新闻"]:
            raise ValueError("Sina feed account identity does not match the registry")
    posts = []
    for link in tree.find("post-link"):
        match = re.fullmatch(r"/news/detail/([0-9]+)\.html", link.attrs.get("href", ""))
        text = link.find("post-text")
        times = link.find("time")
        if not match or not text or not times:
            raise ValueError("Unrecognized Sina feed post markup")
        date = re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d", times[0].text())
        if not date:
            raise ValueError("Sina feed has no absolute publication time")
        counts = [numeric(node.text()) for node in link.find("action")]
        posts.append({
            "id": match.group(1), "text": text[0].text(),
            "published_original": date.group(),
            "source_url": "https://www.sina.cn" + link.attrs["href"],
            "reposts": counts[0] if len(counts) == 3 else None,
            "comments": counts[1] if len(counts) == 3 else None,
            "likes": counts[2] if len(counts) == 3 else None,
        })
    if not posts:
        raise ValueError("No recognized posts; empty response is not evidence of no activity")
    return posts


def parse_detail(html, expected_id, expected_uid):
    tree = HTMLTree(html).root
    root = next((node for node in tree.walk() if node.tag == "html"), None)
    if root is None or not root.attrs.get("data-id"):
        raise ValueError("Missing detail post identity")
    if root.attrs["data-id"] != expected_id:
        raise SourceConflict("Detail post ID mismatch")
    documents = []
    for node in tree.walk():
        if node.tag == "script" and node.attrs.get("type") == "application/ld+json":
            documents.append(json.loads("".join(c for c in node.children if isinstance(c, str))))
    articles = []
    for document in documents:
        graphs = document.get("@graph", [document])
        articles.extend(item for item in graphs if item.get("@type") == "NewsArticle")
    if len(articles) != 1:
        raise ValueError("Missing unambiguous post provenance in detail page")
    article = articles[0]
    author = article.get("author", {})
    author_url = author.get("url") if isinstance(author, dict) else None
    author_path = urlsplit(author_url).path if isinstance(author_url, str) else ""
    if not re.fullmatch(r"/u/[0-9]+", author_path):
        raise ValueError("Missing unambiguous detail author identity")
    if author_path != f"/u/{expected_uid}":
        raise SourceConflict("Detail author UID mismatch")
    body = tree.find("article-content")
    if len(body) != 1 or not body[0].text():
        raise ValueError("Missing detail text")
    return {
        "text": body[0].text(), "published_original": article["datePublished"],
        "text_status": "source_full",
    }


class AccessBlocked(Exception):
    pass


class SourceConflict(ValueError):
    pass


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if (urlsplit(newurl).scheme != "https" or
                urlsplit(newurl).hostname != urlsplit(request.full_url).hostname):
            raise AccessBlocked("Cross-host or non-HTTPS redirect; access not followed")
        if urlsplit(request.full_url).hostname == "web.archive.org":
            old_capture = re.search(r"/web/([0-9]{14})id_/", request.full_url)
            new_capture = re.search(r"/web/([0-9]{14})id_/", newurl)
            if old_capture and (not new_capture or old_capture[1] != new_capture[1]):
                raise AccessBlocked("Archive redirected to a different capture; timestamp not assumed")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class PublicClient:
    def __init__(self, delay=2.0, raw_dir=None):
        self.delay = max(1.0, delay)
        self.last_request = 0.0
        self.robots = None
        self.blocked = None
        self.raw_dir = Path(raw_dir) if raw_dir else None
        self.opener = build_opener(SameHostRedirect())

    def request(self, url):
        if self.blocked:
            raise AccessBlocked(self.blocked)
        for attempt in range(3):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with self.opener.open(Request(url, headers={"User-Agent": USER_AGENT}),
                                      timeout=30) as response:
                    content = response.read(5_000_001)
                    if len(content) > 5_000_000:
                        raise ValueError("Source exceeds response size limit")
                    if content[:2] == b"\x1f\x8b":
                        with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                            content = compressed.read(5_000_001)
                        if len(content) > 5_000_000:
                            raise ValueError("Decompressed source exceeds response size limit")
                    headers = getattr(response, "headers", None)
                    encoding = headers.get_content_charset() if headers is not None else None
                    if not encoding:
                        declared = re.search(
                            rb"<meta\b[^>]*\bcharset\s*=\s*[\"']?\s*([A-Za-z0-9._-]+)",
                            content[:4096], re.IGNORECASE,
                        )
                        encoding = declared[1].decode("ascii") if declared else "utf-8"
                    if encoding.strip().lower() in {
                        "chinese", "csgb2312", "csiso58gb231280", "gb2312", "gb_2312",
                        "gb_2312-80", "gbk", "iso-ir-58", "x-gbk",
                    }:
                        # HTML's GBK-family labels use the gb18030 decoder.
                        encoding = "gb18030"
                    try:
                        return content.decode(encoding)
                    except LookupError:
                        raise ValueError("Unsupported declared source encoding") from None
            except HTTPError as error:
                if error.code in {401, 403, 406, 418, 429, 432}:
                    self.blocked = f"HTTP {error.code}; no access-control bypass attempted"
                    raise AccessBlocked(self.blocked)
                if error.code < 500 or attempt == 2:
                    raise ValueError(f"HTTP {error.code} fetching public source") from None
                time.sleep(self.delay * (2 ** (attempt + 1)))
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise ValueError("Public source network failure") from None
                time.sleep(self.delay * (2 ** (attempt + 1)))

    def get(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "www.sina.cn" or
                not re.fullmatch(r"/(?:media/[0-9]+|news/detail/[0-9]+\.html)", parsed.path) or
                parsed.query or parsed.fragment):
            raise ValueError("Only pilot-verified public Sina feed/detail routes are supported")
        if self.robots is None:
            self.robots = RobotFileParser()
            self.robots.parse(self.request("https://www.sina.cn/robots.txt").splitlines())
            crawl_delay = self.robots.crawl_delay(USER_AGENT)
            if crawl_delay:
                self.delay = max(self.delay, crawl_delay)
        if not self.robots.can_fetch(USER_AGENT, url):
            raise AccessBlocked("Source robots policy does not permit retrieval")
        html = self.request(url)
        if any(marker in html.lower() for marker in
               ("sina visitor system", "<title>captcha", "passport.weibo.com/visitor")):
            raise AccessBlocked("Visitor or challenge page; no bypass attempted")
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            name = parsed.path.strip("/").replace("/", "_") + "_" + str(time.time_ns()) + ".html"
            (self.raw_dir / name).write_text(html, encoding="utf-8")
        return html


def normalize(record, account, start, end):
    if account["officialness"] != "confirmed":
        raise ValueError("Only confirmed official accounts may contribute posts")
    if not isinstance(record.get("id"), str) or not re.fullmatch(r"[0-9]+", record["id"]):
        raise ValueError("Post ID must be a numeric string")
    if not account["uid"] or record.get("uid", account["uid"]) != account["uid"]:
        raise ValueError("Missing or mismatched author UID")
    original = record["published_original"]
    dt = datetime.fromisoformat(original.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI)
    utc = timestamp(dt.isoformat())
    cutoff = account["attribution_end"] if "attribution_end" in account.keys() else None
    if cutoff:
        end = min(end, window(cutoff, cutoff)[0])
    if not start <= utc < end:
        return None
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Post must contain accessible text; metadata-only imports are not a corpus")
    if record.get("text_status") not in {"full", "source_full", "truncated", "unknown"}:
        raise ValueError("Explicit text completeness is required")
    if record.get("kind", "unknown") not in {"original", "repost", "unknown"}:
        raise ValueError("Unsupported post kind")
    if record.get("source_type") not in {"sina_syndication", "archive", "authorized_import"}:
        raise ValueError("Unsupported post source")
    valid_url(record["source_url"])
    record = dict(record)
    record["retrieved_at"] = timestamp(record["retrieved_at"])
    if record.get("captured_at"):
        record["captured_at"] = timestamp(record["captured_at"])
    if record["source_type"] == "archive" and not record.get("captured_at"):
        raise ValueError("Archived posts require their capture timestamp")
    if record.get("captured_at") and utc > record["captured_at"]:
        raise ValueError("Post publication cannot follow source capture")
    if record.get("captured_at") and record["captured_at"] > record["retrieved_at"]:
        raise ValueError("Source capture cannot follow retrieval")
    reference = record.get("referenced_id")
    if reference is not None and (not isinstance(reference, str) or
                                  not re.fullmatch(r"[0-9]+", reference)):
        raise ValueError("Referenced post ID must be a numeric string or null")
    commentary = record.get("repost_commentary")
    if commentary is not None and not isinstance(commentary, str):
        raise ValueError("Repost commentary must be a string or null")
    if record.get("redistribution", "unknown") not in {"unknown", "permitted", "restricted"}:
        raise ValueError("Unsupported redistribution status")
    for key in ("likes", "comments", "reposts"):
        value = record.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Engagement counts must be nonnegative integers or null")
    record.update(
        account_id=account["id"], uid=account["uid"], published_utc=utc,
        canonical_url=f"https://m.weibo.cn/detail/{record['id']}",
        kind=record.get("kind", "unknown"),
        redistribution=record.get("redistribution", "unknown"),
    )
    return record


def collect_account(db, account_id, start, end, client, limit=50):
    if limit < 1:
        raise ValueError("Post limit must be positive")
    account = db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not account or account["officialness"] != "confirmed":
        raise ValueError("Collection requires a confirmed registry account")
    run = db.execute(
        "SELECT * FROM runs WHERE account_id=? AND source_type='sina_syndication' "
        "AND window_start=? AND window_end=? ORDER BY id DESC LIMIT 1",
        (account_id, start, end),
    ).fetchone()
    checkpoint = json.loads(run["checkpoint"]) if run and run["checkpoint"] else None
    resume = checkpoint and checkpoint["next"] < len(checkpoint["items"])
    if resume:
        run_id = run["id"]
        with db:
            db.execute("UPDATE runs SET status='running', error=NULL, finished_at=NULL WHERE id=?",
                       (run_id,))
    else:
        with db:
            run_id = db.execute(
                "INSERT INTO runs (account_id,source_type,started_at,window_start,window_end,"
                "status,limitations) VALUES (?,?,?,?,?,'running',?)",
                (account_id, "sina_syndication", now(), start, end, LIMITATIONS),
            ).lastrowid
    try:
        if not account["uid"]:
            raise AccessBlocked("Official account confirmed, but stable UID not yet resolved")
        if not resume:
            with db:
                db.execute("UPDATE runs SET pages_attempted=pages_attempted+1 WHERE id=?", (run_id,))
            html = client.get(f"https://www.sina.cn/media/{account['uid']}")
            checkpoint = {"items": parse_feed(html, account["display_name"]), "next": 0,
                          "retrieved_at": now(), "recovered_ids": []}
            with db:
                db.execute("UPDATE runs SET checkpoint=? WHERE id=?", (json_text(checkpoint), run_id))
        for _ in range(limit):
            if checkpoint["next"] >= len(checkpoint["items"]):
                break
            item = dict(checkpoint["items"][checkpoint["next"]])
            preliminary = dict(item, source_type="sina_syndication", text_status="truncated",
                               retrieved_at=checkpoint["retrieved_at"])
            post = None
            detail_error = None
            if normalize(preliminary, account, start, end) is not None:
                with db:
                    db.execute("UPDATE runs SET pages_attempted=pages_attempted+1 WHERE id=?", (run_id,))
                try:
                    html = client.get(item["source_url"])
                    item.update(parse_detail(html, item["id"], account["uid"]))
                    item.update(source_type="sina_syndication", retrieved_at=now())
                    post = normalize(item, account, start, end)
                    if not post:
                        raise SourceConflict("Detail publication time disagrees with the in-window feed")
                    # Counts were observed on the feed, not the detail page.
                    for key in ("likes", "comments", "reposts"):
                        post[key] = None
                except (AccessBlocked, ValueError, KeyError) as error:
                    detail_error = error
            recovered_ids = checkpoint.setdefault("recovered_ids", [])
            new_id = preliminary["id"] not in recovered_ids
            conflicts = checkpoint.setdefault("source_conflicts", {})
            if isinstance(detail_error, SourceConflict):
                conflicts[preliminary["id"]] = str(detail_error)
                in_window = None
            else:
                conflicts.pop(preliminary["id"], None)
                in_window = normalize(preliminary, account, start, end)
            if in_window and new_id:
                recovered_ids.append(preliminary["id"])
            detail_errors = checkpoint.setdefault("detail_errors", {})
            if detail_error:
                detail_errors[preliminary["id"]] = str(detail_error)
            else:
                detail_errors.pop(preliminary["id"], None)
            checkpoint["next"] += 1
            with db:
                if in_window:
                    if post:
                        put_post(db, post)
                    in_window["source_url"] = f"https://www.sina.cn/media/{account['uid']}"
                    put_post(db, in_window)
                    if new_id:
                        db.execute("UPDATE runs SET posts_recovered=posts_recovered+1 WHERE id=?", (run_id,))
                db.execute("UPDATE runs SET checkpoint=? WHERE id=?", (json_text(checkpoint), run_id))
        with db:
            errors = checkpoint.get("detail_errors", {})
            conflicts = checkpoint.get("source_conflicts", {})
            summary = (f"{len(errors) - len(conflicts)} detail pages unavailable; previews retained. "
                       f"{len(conflicts)} source conflicts skipped. {json_text(errors)}" if errors else None)
            db.execute("UPDATE runs SET status=?,finished_at=?,error=? WHERE id=?",
                       ("blocked" if getattr(client, "blocked", None) else "partial",
                        now(), summary, run_id))
    except (AccessBlocked, ValueError, KeyError) as error:
        with db:
            db.execute("UPDATE runs SET status=?,error=?,finished_at=? WHERE id=?",
                       ("blocked" if isinstance(error, AccessBlocked) else "partial",
                        str(error), now(), run_id))
    return dict(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())


def import_posts(db, path, start, end):
    accepted = skipped = 0
    per_account = {}
    with open(path, encoding="utf-8") as stream, db:
        for number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                account = db.execute("SELECT * FROM accounts WHERE id=?",
                                     (record["account_id"],)).fetchone()
                if not account:
                    raise ValueError("Unknown account")
                events = record.get("provenance")
                if events is not None:
                    if not isinstance(events, list) or not events:
                        raise ValueError("Canonical export requires nonempty provenance")
                    matching = [event for event in events
                                if event["text"] == record["text"] and
                                event["text_status"] == record["text_status"]]
                    if not matching:
                        raise ValueError("Canonical text does not match any provenance record")
                    events = events + [matching[-1]]
                else:
                    events = [record]
                kept = False
                for event in events:
                    if event.get("post_id", record["id"]) != record["id"]:
                        raise ValueError("Provenance post ID mismatch")
                    post = normalize(dict(record, **{key: event[key] for key in (
                        "source_url", "source_type", "retrieved_at", "captured_at",
                        "text", "text_status") if key in event}), account, start, end)
                    if post:
                        put_post(db, post)
                        kept = True
                if kept:
                    for observation in record.get("engagement_observations", []):
                        if observation["post_id"] != record["id"]:
                            raise ValueError("Engagement post ID mismatch")
                        valid_url(observation["source_url"])
                        if observation["source_type"] not in {"sina_syndication", "archive", "authorized_import"}:
                            raise ValueError("Unsupported engagement source")
                        counts = [observation.get(key) for key in ("likes", "comments", "reposts")]
                        if any(value is not None and (type(value) is not int or value < 0) for value in counts):
                            raise ValueError("Invalid engagement count")
                        db.execute("INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?)", (
                            record["id"], timestamp(observation["observed_at"]),
                            observation["source_type"], observation["source_url"], *counts,
                        ))
                    accepted += 1
                    per_account[account["id"]] = per_account.get(account["id"], 0) + 1
                else:
                    skipped += 1
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f"Import line {number}: {error}") from None
        for account_id, count in per_account.items():
            db.execute(
                "INSERT INTO runs (account_id,source_type,started_at,finished_at,window_start,"
                "window_end,status,posts_recovered,limitations) VALUES (?,?,?,?,?,?,'partial',?,?)",
                (account_id, "import", now(), now(), start, end, count,
                 "Imported records only; no claim of historical completeness."),
            )
    return {"accepted": accepted, "outside_window": skipped}
