import json
import re
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser

from .collect import AccessBlocked, HTMLTree, PublicClient, USER_AGENT, normalize, numeric
from .storage import now, put_post


ARCHIVE_LIMITATIONS = (
    "Single archived profile snapshot; no full timeline backfill. Unexpanded posts are "
    "truncated. Engagement belongs to capture time, not retrieval/publication time. "
    "Snapshots can contain cached data and omit deleted posts."
)


def archive_time(url):
    match = re.fullmatch(
        r"https://web\.archive\.org/web/([0-9]{14})id_/https?://(?:www\.)?weibo\.com/"
        r"(?:u/[0-9]+|[A-Za-z0-9_]+)", url)
    if not match:
        raise ValueError("Expected a Wayback id_ profile replay URL with a 14-digit capture timestamp")
    return datetime.strptime(match[1], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()


class ArchiveClient(PublicClient):
    def get(self, url):
        archive_time(url)
        if self.robots is None:
            self.robots = RobotFileParser()
            try:
                text = self.request("https://web.archive.org/robots.txt")
            except ValueError as error:
                if "HTTP 404 " not in str(error):
                    raise
                text = "User-agent: *\nAllow: /"
            self.robots.parse(text.splitlines())
            delay = self.robots.crawl_delay(USER_AGENT)
            if delay:
                self.delay = max(self.delay, delay)
        if not self.robots.can_fetch(USER_AGENT, url):
            raise AccessBlocked("Archive robots policy does not permit retrieval")
        html = self.request(url)
        if "sina visitor system" in html.lower():
            raise AccessBlocked("Archive contains a visitor gate, not a usable feed")
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            name = "archive_" + url.split("/web/")[1].replace("/", "_").replace(":", "_") + ".html"
            (self.raw_dir / name).write_text(html, encoding="utf-8")
        return html


def parse_archive(html, expected_uid):
    owner = re.search(r"\$CONFIG\[['\"]oid['\"]\]\s*=\s*['\"]([0-9]+)['\"]", html)
    if not owner or owner[1] != expected_uid:
        raise ValueError("Archived profile owner UID mismatch or missing")
    root = HTMLTree(html).root
    items = root.find("WB_feed_type")
    if not items:
        fragments = []
        for match in re.finditer(r"FM\.view\(\s*", html):
            try:
                document, _ = json.JSONDecoder().raw_decode(html[match.end():])
            except ValueError:
                continue
            if isinstance(document, dict) and isinstance(document.get("html"), str):
                fragments.append(document["html"])
        items = HTMLTree("".join(fragments)).root.find("WB_feed_type")
    records = []
    for item in items:
        authors = dict(re.findall(r"([a-z]+)=([0-9]+)", item.attrs.get("tbinfo", "")))
        if authors.get("ouid") != expected_uid:
            continue
        text_nodes = [node for node in item.walk()
                      if node.attrs.get("node-type") == "feed_list_content"]
        dates = [node for node in item.walk()
                 if node.attrs.get("node-type") == "feed_list_item_date"]
        if len(text_nodes) != 1 or not dates or not item.attrs.get("mid"):
            raise ValueError("Unrecognized archived feed post markup")
        published = dates[0].attrs.get("title", "")
        datetime.strptime(published, "%Y-%m-%d %H:%M")
        own_text = text_nodes[0].text()
        quoted = [node for node in item.walk()
                  if node.attrs.get("node-type") == "feed_list_reason"]
        is_repost = bool(quoted or item.attrs.get("isforward") or item.attrs.get("omid"))
        record = {
            "id": item.attrs["mid"], "uid": expected_uid,
            "published_original": published,
            "text": own_text + ("\n\n" + "\n".join(node.text() for node in quoted) if quoted else ""),
            "text_status": "truncated" if any(
                node.attrs.get("action-type") == "fl_unfold" for node in item.walk()
            ) else "source_full",
            "kind": "repost" if is_repost else "original",
            "referenced_id": item.attrs.get("omid"),
            "repost_commentary": own_text if is_repost else None,
            "likes": None, "comments": None, "reposts": None,
        }
        handles = item.find("WB_feed_handle")
        metric_root = handles[0] if handles else item
        for node in metric_root.walk():
            action = node.attrs.get("action-type")
            metric = {"fl_forward": "reposts", "fl_comment": "comments", "fl_like": "likes"}.get(action)
            if node.attrs.get("node-type") == "like_status":
                metric = "likes"
            if metric:
                values = re.findall(r"(?<![0-9])[0-9]+(?![0-9])", node.text())
                if len(values) == 1 and not any(unit in node.text() for unit in ("万", "亿", ".")):
                    record[metric] = numeric(values[0])
        records.append(record)
    if not records:
        raise ValueError("Archive replay has no recognized posts; not evidence of no activity")
    return records


def collect_archive(db, account_id, url, start, end, client):
    captured_at = archive_time(url)
    account = db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not account or account["officialness"] != "confirmed":
        raise ValueError("Archive collection requires a confirmed account")
    with db:
        run_id = db.execute(
            "INSERT INTO runs (account_id,source_type,started_at,window_start,window_end,"
            "status,pages_attempted,limitations) VALUES (?,?,?,?,?,'running',1,?)",
            (account_id, "archive", now(), start, end, ARCHIVE_LIMITATIONS),
        ).lastrowid
    try:
        if not account["uid"]:
            raise AccessBlocked("Stable UID unresolved; cannot verify archived author")
        html = client.get(url)
        recovered = 0
        retrieved_at = now()
        with db:
            for record in parse_archive(html, account["uid"]):
                record.update(source_url=url, source_type="archive",
                              retrieved_at=retrieved_at, captured_at=captured_at)
                post = normalize(record, account, start, end)
                if post:
                    if post["published_utc"] > captured_at:
                        raise ValueError("Post publication cannot follow archive capture")
                    put_post(db, post)
                    recovered += 1
            db.execute("UPDATE runs SET status='partial',finished_at=?,posts_recovered=? WHERE id=?",
                       (now(), recovered, run_id))
    except (AccessBlocked, ValueError, KeyError) as error:
        with db:
            db.execute("UPDATE runs SET status=?,finished_at=?,error=? WHERE id=?",
                       ("blocked" if isinstance(error, AccessBlocked) else "partial",
                        now(), str(error), run_id))
    return dict(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())
