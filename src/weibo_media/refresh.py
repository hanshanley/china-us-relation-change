"""Incremental, privately staged collection and source-audited publication."""

import csv
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import assessment, export, registry, report
from .collect import AccessBlocked, PublicClient, SHANGHAI, collect_account, parse_detail, parse_feed, window
from .storage import connect, now


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(db):
    return {r["id"]: dict(r) for r in db.execute(
        "SELECT id,account_id,uid,published_utc,text_status,text FROM posts ORDER BY id")}


def fingerprint(post):
    return {k: post[k] for k in ("id", "account_id", "uid", "published_utc", "text_status")} | {
        "text_sha256": sha(post["text"].encode())}


def load_proofs(root, db):
    from us_china_exchange.model import digest, json_text

    audit = json.loads((root / "data/discovery/weibo_primary_audit.json").read_text())
    raw = (root / "data/discovery/weibo_post_source_audit.csv").read_bytes()
    posts = canonical(db)
    if (sha(raw) != audit["post_manifest_sha256"]
            or digest(json_text([fingerprint(p) for p in posts.values()]).encode()) != audit["canonical_posts_sha256"]
            or sha((root / "data/registry/outlets.json").read_bytes()) != audit["registry_sha256"]):
        raise ValueError("Existing source audit is stale; automatic collection cannot waive re-audit")
    proofs = {r["post_id"]: r for r in csv.DictReader(io.StringIO(raw.decode()))}
    if set(proofs) != set(posts):
        raise ValueError("Existing source-proof manifest is incomplete")
    for post_id, post in posts.items():
        proof = proofs[post_id]
        if any(proof[k] != post[k] for k in ("account_id", "uid", "published_utc", "text_status")) or (
                proof["canonical_text_sha256"] != sha(post["text"].encode())):
            raise ValueError("Existing canonical post disagrees with its source proof")
    return audit, posts, proofs


class CaptureClient(PublicClient):
    def __init__(self, raw_dir, delay=2):
        super().__init__(delay=delay)
        self.capture_dir = Path(raw_dir)
        self.captures = []
        self.blocked_urls = set()

    def get(self, url):
        if url in self.blocked_urls:
            raise AccessBlocked("Recorded source-URL access restriction; not retried")
        body = super().get(url)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        path = self.capture_dir / (urlsplit(url).path.strip("/").replace("/", "_") + f"_{time.time_ns()}.html")
        path.write_text(body, encoding="utf-8")
        self.captures.append({"url": url, "path": path, "body": body, "observed_at": now()})
        return body


def update_proofs(db, old_posts, old_proofs, captures):
    posts, proofs, native = canonical(db), {}, 0
    accounts = {r["uid"]: dict(r) for r in db.execute("SELECT * FROM accounts WHERE uid IS NOT NULL")}
    changed = {key for key, post in posts.items()
               if key not in old_posts or fingerprint(post) != fingerprint(old_posts[key])}
    for key in set(posts) - changed:
        proofs[key] = old_proofs[key]
    for capture in captures:
        url = capture["url"]
        if "/news/detail/" in url:
            post_id = url.rsplit("/", 1)[1].removesuffix(".html")
            if post_id not in changed:
                continue
            post = posts[post_id]
            try:
                parsed = [dict(parse_detail(capture["body"], post_id, post["uid"]), id=post_id)]
            except (ValueError, KeyError):
                continue
            method = "native_detail_id_author_date_and_text"
        else:
            uid = url.rsplit("/", 1)[1]
            account = accounts.get(uid)
            if account is None:
                continue
            parsed = parse_feed(capture["body"], account["display_name"])
            method = "scoped_publisher_feed_id_date_and_preview"
        for item in parsed:
            post_id = item["id"]
            if post_id not in changed:
                continue
            post = posts[post_id]
            published = datetime.fromisoformat(item["published_original"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=SHANGHAI)
            status = item.get("text_status", "truncated")
            if (post["text"] != item["text"] or post["text_status"] != status
                    or published.astimezone(timezone.utc) != datetime.fromisoformat(post["published_utc"])
                    or ("/media/" in url and post["uid"] != url.rsplit("/", 1)[1])):
                continue
            proofs[post_id] = {
                "post_id": post_id, "account_id": post["account_id"], "uid": post["uid"],
                "published_utc": post["published_utc"], "text_status": post["text_status"],
                "canonical_text_sha256": sha(post["text"].encode()), "source_url": url,
                "source_sha256": sha(capture["path"].read_bytes()), "verification_method": method,
            }
    if set(proofs) != set(posts):
        raise ValueError("New/changed canonical posts lack matching primary-source text/date/identity proof")
    native = sum(proofs[key]["verification_method"] == "native_detail_id_author_date_and_text" for key in changed)
    return posts, proofs, native


def write_audit(stage, audit, posts, proofs, native):
    from us_china_exchange.model import digest, json_text

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(next(iter(proofs.values()))), lineterminator="\n")
    writer.writeheader()
    writer.writerows(proofs[k] for k in sorted(proofs))
    raw = stream.getvalue().encode()
    (stage / "data/discovery/weibo_post_source_audit.csv").write_bytes(raw)
    audit = json.loads(json.dumps(audit))
    audit.update(audited_at=now(), canonical_posts_sha256=digest(json_text(
        [fingerprint(p) for p in posts.values()]).encode()), post_manifest_sha256=sha(raw),
        scope="Incremental primary-source consistency audit: unchanged bound proofs carried forward; "
              "new/changed canonical texts, author IDs and dates checked against fresh saved sources. "
              "Identity decisions retain their prior sources; not a new identity sweep or complete timelines.")
    audit["corpus"]["posts_checked"] = audit["corpus"]["primary_text_matches"] = len(posts)
    audit["corpus"]["native_detail_sources_checked"] += native
    (stage / "data/discovery/weibo_primary_audit.json").write_text(json_text(audit))
    return audit


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def relevant_dirty(root):
    paths = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).splitlines()
    prefixes = ("data/registry/", "data/discovery/", "data/site/weibo", "site/weibo.html",
                "site/downloads/weibo", "site/figures/weibo/", "outputs/figures/weibo/",
                "src/weibo_media/", "src/us_china_exchange/weibo", "src/us_china_exchange/render.py",
                "src/us_china_exchange/theme.py", "scripts/refresh_weibo.py")
    return any(row[3:].startswith(prefixes) for row in paths)


def refresh(root, *, account_ids=None, limit=50, publish=False, push=False, client=None):
    from us_china_exchange.model import json_text
    from us_china_exchange.pipeline import write_atomic
    from us_china_exchange.render import build_weibo
    from us_china_exchange.weibo_analysis import create_summary

    root = Path(root).resolve()
    work = root / "data/local/automation"
    work.mkdir(parents=True, exist_ok=True)
    attempted = now()
    prior_status_path = root / "data/site/weibo_refresh.json"
    previous = json.loads(prior_status_path.read_text()) if prior_status_path.exists() else {}
    status = {
        "mode": "daily_local", "status": "failed", "attempted_at": attempted,
        "successful_collection_at": previous.get("successful_collection_at"),
        "through_date": previous.get("through_date"), "accounts_attempted": 0,
        "readable_feeds": 0, "new_posts": 0, "errors": [], "note": "",
    }
    state_path = work / "access-holds.json"
    holds = json.loads(state_path.read_text()) if state_path.exists() else {"host": None, "accounts": {}}
    holds.setdefault("urls", {})
    database = root / "data/local/weibo.sqlite"
    before_db = sha(database.read_bytes())
    head = git(root, "rev-parse", "HEAD")
    if publish and relevant_dirty(root):
        status.update(status="deferred", note="Working tree is dirty; automatic publication deferred without touching it")
        (work / "last-check.json").write_text(json.dumps(status, indent=2) + "\n")
        raise ValueError(status["note"])
    end_date = datetime.now(SHANGHAI).date() - timedelta(days=1)
    start, end = window("2020-01-01", end_date.isoformat())
    base_validated = False
    with tempfile.TemporaryDirectory(prefix="refresh-", dir=work) as temporary:
        stage = Path(temporary)
        for relative in ("data/registry", "data/discovery", "data/site"):
            shutil.copytree(root / relative, stage / relative)
        staged_db = stage / "weibo.sqlite"
        original = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        copied = sqlite3.connect(staged_db)
        original.backup(copied)
        original.close()
        copied.close()
        db = connect(staged_db)
        try:
            registry.load(db, stage / "data/registry/outlets.json")
            audit, old_posts, old_proofs = load_proofs(root, db)
            base_validated = True
            baseline_dir = work / "baseline_2026-10-21"
            if publish and not baseline_dir.exists():
                saved = stage / "baseline"
                saved.mkdir()
                backup = sqlite3.connect(saved / "weibo.sqlite")
                db.backup(backup)
                backup.close()
                shutil.copy2(root / "data/site/weibo_summary.json", saved / "weibo_summary.json")
                for name in ("weibo_primary_audit.json", "weibo_post_source_audit.csv"):
                    shutil.copy2(root / "data/discovery" / name, saved / name)
                os.replace(saved, baseline_dir)
            eligible = [dict(r) for r in db.execute(
                "SELECT * FROM accounts WHERE officialness='confirmed' AND existence='current_evidence' "
                "AND uid IS NOT NULL AND (attribution_end IS NULL OR attribution_end>?) ORDER BY id",
                (end_date.isoformat(),))]
            if account_ids:
                if set(account_ids) - {a["id"] for a in eligible}:
                    raise ValueError("Refresh accepts only currently attributed, confirmed numeric channels")
                eligible = [a for a in eligible if a["id"] in account_ids]
            for old_run in db.execute("SELECT account_id,status,error,checkpoint FROM runs WHERE source_type='sina_syndication'"):
                checkpoint = json.loads(old_run["checkpoint"] or "{}")
                for post_id, reason in checkpoint.get("detail_errors", {}).items():
                    if re.search(r"HTTP\s*(?:401|403|406|418|429|432)|robots|captcha|visitor|challenge|redirect", reason, re.I):
                        holds["urls"][f"https://www.sina.cn/news/detail/{post_id}.html"] = reason[:300]
            latest = {r["account_id"]: r for r in db.execute(
                "SELECT account_id,status,error FROM runs WHERE source_type='sina_syndication' ORDER BY id")}
            for account in eligible:
                old_run = latest.get(account["id"])
                if old_run and old_run["status"] == "blocked":
                    holds["accounts"][account["id"]] = account["uid"] + ":" + account["display_name"]
            client = client or CaptureClient(root / "data/local/raw/refresh" / attempted.replace(":", "_"))
            if isinstance(client, CaptureClient):
                client.blocked_urls = set(holds["urls"])
            runs = []
            for account in eligible:
                identity = account["uid"] + ":" + account["display_name"]
                if holds["host"] or holds["accounts"].get(account["id"]) == identity:
                    status["errors"].append({"account_id": account["id"], "reason": "Recorded access/identity hold; not retried"})
                    continue
                status["accounts_attempted"] += 1
                def reusable(preview):
                    old = old_posts.get(preview["id"])
                    return (old is not None and old["text_status"] in {"source_full", "full"}
                            and all(old[k] == preview[k] for k in ("uid", "account_id", "published_utc")))
                run = collect_account(db, account["id"], start, end, client, limit, reuse_verified=reusable)
                runs.append(run)
                checkpoint = json.loads(run["checkpoint"]) if run["checkpoint"] else {}
                for post_id, reason in checkpoint.get("detail_errors", {}).items():
                    if re.search(r"HTTP\s*(?:401|403|406|418|429|432)|robots|captcha|visitor|challenge|redirect", reason, re.I):
                        url = f"https://www.sina.cn/news/detail/{post_id}.html"
                        holds["urls"][url] = reason[:300]
                        if isinstance(client, CaptureClient):
                            client.blocked_urls.add(url)
                if checkpoint.get("items"):
                    status["readable_feeds"] += 1
                if run["error"]:
                    status["errors"].append({"account_id": account["id"], "reason": run["error"][:300]})
                if getattr(client, "blocked", None):
                    holds["host"] = client.blocked
                elif (run["status"] == "blocked" or checkpoint.get("source_conflicts")
                      or "identity does not match" in (run["error"] or "")):
                    holds["accounts"][account["id"]] = identity
            if not status["readable_feeds"]:
                status["status"] = "blocked" if holds["host"] or holds["accounts"] else "failed"
                raise ValueError("No readable feeds; publication date and corpus not advanced")
            for run in runs:
                conflicts = json.loads(run["checkpoint"] or "{}").get("source_conflicts", {})
                if set(conflicts) & set(old_posts):
                    raise ValueError("New source conflict affects an audited canonical post; manual review required")
            posts, proofs, native = update_proofs(db, old_posts, old_proofs, client.captures)
            write_audit(stage, audit, posts, proofs, native)
            status.update(status="partial" if status["errors"] or account_ids else "current",
                          successful_collection_at=now(), through_date=end_date.isoformat(),
                          new_posts=len(posts) - len(old_posts),
                          note=f"{len(eligible)} eligible channels in this pass; access holds are not retried. "
                               "Bounded public feeds only; recovered-sample lower bounds, not full timelines or verified inactivity.")
            (stage / "data/site/weibo_refresh.json").write_text(json_text(status))
            assessment.publish(db, root / "data/discovery/us_top1000.csv",
                               root / "data/discovery/us_top1000_screening.csv",
                               root / "data/local/discovery/secondary-pages/publisher_pages.jsonl",
                               stage / "data/discovery")
            export.export(db, stage / "exports", False)
            report.report(db, stage / "reports/weibo_media_inventory.md")
            summary = create_summary(staged_db, stage / "data/registry/outlets.json")
            write_atomic(stage / "data/site/weibo_summary.json", json_text(summary))
            build_weibo(stage, summary, {"weibo": []})
            if publish:
                if (git(root, "rev-parse", "HEAD") != head or relevant_dirty(root)
                        or sha(database.read_bytes()) != before_db):
                    raise ValueError("Concurrent work changed; staged refresh not promoted")
                publication = ["data/discovery/" + p for p in (
                    "us_top1000_accounts.csv", "us_top1000_accounts.jsonl", "outlet_account_assessments.csv",
                    "outlet_account_assessments.jsonl", "weibo_post_source_audit.csv", "weibo_primary_audit.json")]
                publication += ["data/site/weibo_summary.json", "data/site/weibo_refresh.json",
                                "reports/weibo_media_inventory.md", "site/weibo.html"]
                publication += [str(p.relative_to(stage)) for folder in ("outputs/figures/weibo", "site/figures/weibo", "site/downloads")
                                for p in (stage / folder).rglob("*") if p.is_file()]
                for relative in publication:
                    write_atomic(root / relative, (stage / relative).read_bytes())
                db.close()
                db = None
                write_atomic(database, staged_db.read_bytes())
                export_dir = root / "data/local/exports"
                for path in (stage / "exports").iterdir():
                    if path.is_file():
                        write_atomic(export_dir / path.name, path.read_bytes())
                create_summary(database, root / "data/registry/outlets.json")
                if push:
                    env = dict(os.environ, GIT_AUTHOR_NAME="Hans Hanley", GIT_AUTHOR_EMAIL="hwahhanley@gmail.com",
                               GIT_COMMITTER_NAME="Hans Hanley", GIT_COMMITTER_EMAIL="hwahhanley@gmail.com")
                    subprocess.run(["git", "add", "--", *publication], cwd=root, check=True)
                    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode:
                        subprocess.run(["git", "commit", "--only", "-m", "Refresh source-audited Weibo activity",
                                        "--", *publication], cwd=root, env=env, check=True)
                        subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=root, check=True)
            return status
        except Exception as error:
            status["note"] = str(error)[:300]
            if status["status"] not in {"blocked", "failed"}:
                status["status"] = "failed"
            if (publish and base_validated and git(root, "rev-parse", "HEAD") == head
                    and not relevant_dirty(root) and sha(database.read_bytes()) == before_db):
                unchanged = create_summary(database, root / "data/registry/outlets.json")
                unchanged["refresh"] = status
                write_atomic(prior_status_path, json_text(status))
                write_atomic(root / "data/site/weibo_summary.json", json_text(unchanged))
                build_weibo(root, unchanged, {"weibo": []})
                if push:
                    env = dict(os.environ, GIT_AUTHOR_NAME="Hans Hanley", GIT_AUTHOR_EMAIL="hwahhanley@gmail.com",
                               GIT_COMMITTER_NAME="Hans Hanley", GIT_COMMITTER_EMAIL="hwahhanley@gmail.com")
                    paths = ["data/site/weibo_refresh.json", "data/site/weibo_summary.json",
                             "site/downloads/weibo-summary.json", "site/weibo.html"]
                    subprocess.run(["git", "add", "--", *paths], cwd=root, check=True)
                    subprocess.run(["git", "commit", "--only", "-m", "Record blocked Weibo refresh without advancing data",
                                    "--", *paths], cwd=root, env=env, check=True)
                    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=root, check=True)
            raise
        finally:
            if db is not None:
                db.close()
            state_path.write_text(json.dumps(holds, indent=2) + "\n")
            (work / "last-check.json").write_text(json.dumps(status, indent=2) + "\n")
