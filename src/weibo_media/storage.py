import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS outlets (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            aliases TEXT NOT NULL, us_basis TEXT NOT NULL, source_url TEXT NOT NULL,
            research_status TEXT NOT NULL, notes TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY, outlet_id TEXT NOT NULL REFERENCES outlets(id),
            uid TEXT UNIQUE, handle TEXT, display_name TEXT NOT NULL,
            profile_url TEXT NOT NULL, language TEXT NOT NULL,
            operator TEXT NOT NULL, relationship TEXT NOT NULL,
            officialness TEXT NOT NULL, existence TEXT NOT NULL,
            accessibility TEXT NOT NULL, notes TEXT NOT NULL, attribution_end TEXT
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
            source_url TEXT NOT NULL, source_type TEXT NOT NULL,
            observed_at TEXT NOT NULL, claim_date TEXT, supports TEXT NOT NULL,
            justification TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
            source_type TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            window_start TEXT NOT NULL, window_end TEXT NOT NULL,
            status TEXT NOT NULL, pages_attempted INTEGER NOT NULL DEFAULT 0,
            posts_recovered INTEGER NOT NULL DEFAULT 0, checkpoint TEXT,
            error TEXT, limitations TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
            uid TEXT NOT NULL, canonical_url TEXT NOT NULL,
            published_original TEXT NOT NULL, published_utc TEXT NOT NULL,
            text TEXT NOT NULL, text_status TEXT NOT NULL, kind TEXT NOT NULL,
            referenced_id TEXT, repost_commentary TEXT,
            redistribution TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provenance (
            post_id TEXT NOT NULL REFERENCES posts(id),
            source_url TEXT NOT NULL, source_type TEXT NOT NULL,
            retrieved_at TEXT NOT NULL, captured_at TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL, text_status TEXT NOT NULL,
            PRIMARY KEY (post_id, source_url, retrieved_at)
        );
        CREATE TABLE IF NOT EXISTS observations (
            post_id TEXT NOT NULL REFERENCES posts(id),
            observed_at TEXT NOT NULL, source_type TEXT NOT NULL,
            source_url TEXT NOT NULL, likes INTEGER, comments INTEGER, reposts INTEGER,
            PRIMARY KEY (post_id, observed_at, source_url)
        );
    """)
    if "attribution_end" not in {row["name"] for row in db.execute("PRAGMA table_info(accounts)")}:
        with db:
            db.execute("ALTER TABLE accounts ADD COLUMN attribution_end TEXT")
    return db


def rows(db, table):
    allowed = {
        "outlets", "accounts", "evidence", "posts", "provenance",
        "observations", "runs",
    }
    if table not in allowed:
        raise ValueError("Unknown table")
    order = "id" if table not in {"provenance", "observations"} else "post_id"
    return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def put_post(db, post):
    existing = db.execute("SELECT * FROM posts WHERE id=?", (post["id"],)).fetchone()
    if existing and (existing["uid"] != post["uid"] or
                     existing["account_id"] != post["account_id"]):
        raise ValueError("Post ID belongs to a different account")
    columns = (
        "id", "account_id", "uid", "canonical_url", "published_original",
        "published_utc", "text", "text_status", "kind", "referenced_id",
        "repost_commentary", "redistribution",
    )
    quality = {"truncated": 0, "unknown": 1, "source_full": 2, "full": 3}
    if not existing:
        db.execute(
            f"INSERT INTO posts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            [post.get(column) for column in columns],
        )
    elif (quality[post["text_status"]] > quality[existing["text_status"]] or
          (quality[post["text_status"]] == quality[existing["text_status"]] and
           len(post["text"]) >= len(existing["text"]))):
        updates = {column: post.get(column) for column in columns[3:]}
        for column in ("kind", "referenced_id", "repost_commentary", "redistribution"):
            if updates[column] in (None, "unknown"):
                updates[column] = existing[column]
        db.execute(
            "UPDATE posts SET " + ",".join(f"{column}=?" for column in columns[3:]) +
            " WHERE id=?",
            [updates[column] for column in columns[3:]] + [post["id"]],
        )
    db.execute(
        "INSERT OR IGNORE INTO provenance VALUES (?,?,?,?,?,?,?)",
        (post["id"], post["source_url"], post["source_type"], post["retrieved_at"],
         post.get("captured_at") or "", post["text"], post["text_status"]),
    )
    if any(post.get(key) is not None for key in ("likes", "comments", "reposts")):
        db.execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?)",
            (post["id"], post.get("captured_at") or post["retrieved_at"],
             post["source_type"], post["source_url"],
             post.get("likes"), post.get("comments"), post.get("reposts")),
        )


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
