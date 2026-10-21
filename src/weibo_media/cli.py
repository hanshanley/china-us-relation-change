import argparse
import json
import sqlite3
import sys

from .collect import PublicClient, collect_account, import_posts, window
from .archive import ArchiveClient, collect_archive
from .export import export
from .registry import load
from .report import report
from .storage import connect


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sourced U.S. media Weibo inventory and post recovery")
    parser.add_argument("--db", default="data/local/weibo.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    registry = commands.add_parser("registry", help="Validate and upsert an evidence-backed registry")
    registry.add_argument("path", nargs="?", default="data/registry/outlets.json")
    collect = commands.add_parser("collect", help="Recover public syndicated posts; resume unfinished feed")
    collect.add_argument("--account", action="append", help="Registry account ID; repeatable; default all confirmed")
    collect.add_argument("--limit", type=int, default=50, help="Maximum feed entries per account per invocation")
    collect.add_argument("--delay", type=float, default=2.0, help="Request spacing; minimum one second")
    collect.add_argument("--raw-dir", default="data/local/raw")
    importing = commands.add_parser("import", help="Import permitted full-text normalized JSONL")
    importing.add_argument("path")
    archive = commands.add_parser("archive", help="Recover a verified account's archived profile snapshot")
    archive.add_argument("--account", required=True)
    archive.add_argument("--url", required=True, action="append", help="Wayback id_ replay URL; repeatable")
    archive.add_argument("--delay", type=float, default=2.0)
    archive.add_argument("--raw-dir", default="data/local/raw")
    for command in (collect, importing, archive):
        command.add_argument("--start", default="2020-01-01")
        command.add_argument("--end", default="2026-10-21", help="Inclusive Asia/Shanghai publication date")
    exporting = commands.add_parser("export", help="Export full-content tables and canonical posts.jsonl")
    exporting.add_argument("--output", default="data/local/exports")
    exporting.add_argument("--public", action="store_true", help="Omit text without explicit redistribution permission")
    reporting = commands.add_parser("report", help="Generate sourced inventory and observed activity report")
    reporting.add_argument("--output", default="reports/weibo_media_inventory.md")
    args = parser.parse_args(argv)
    db = None
    exit_code = 0
    try:
        db = connect(args.db)
        if args.command == "registry":
            result = load(db, args.path)
        elif args.command == "collect":
            if args.limit < 1:
                raise ValueError("--limit must be positive")
            start, end = window(args.start, args.end)
            ids = args.account or [row[0] for row in db.execute(
                "SELECT id FROM accounts WHERE officialness='confirmed' ORDER BY id")]
            if not ids:
                raise ValueError("No confirmed accounts; load the registry first")
            client = PublicClient(args.delay, args.raw_dir)
            runs = [collect_account(db, account_id, start, end, client, args.limit) for account_id in ids]
            result = [{key: run[key] for key in (
                "id", "account_id", "status", "pages_attempted", "posts_recovered", "error", "limitations"
            )} for run in runs]
            exit_code = 2 if any(run["error"] for run in runs) else 0
        elif args.command == "archive":
            start, end = window(args.start, args.end)
            client = ArchiveClient(args.delay, args.raw_dir)
            runs = [collect_archive(db, args.account, url, start, end, client) for url in args.url]
            result = [{key: run[key] for key in (
                "id", "account_id", "status", "pages_attempted", "posts_recovered", "error", "limitations"
            )} for run in runs]
            exit_code = 2 if any(run["error"] for run in runs) else 0
        elif args.command == "import":
            result = import_posts(db, args.path, *window(args.start, args.end))
        elif args.command == "export":
            result = export(db, args.output, args.public)
        else:
            result = report(db, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        exit_code = 1
    finally:
        if db:
            db.close()
    if exit_code:
        raise SystemExit(exit_code)
