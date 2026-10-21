import csv
import json
from pathlib import Path

from .storage import json_text, rows


def write_csv(path, records, columns):
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({
                key: json_text(value) if isinstance(value, (list, dict)) else value
                for key, value in record.items()
            })


def coverage(db):
    return [dict(row) for row in db.execute("""
        SELECT a.id AS account_id, a.officialness, a.uid,
               COUNT(p.id) AS recovered_posts,
               MIN(p.published_utc) AS earliest_observed_post,
               MAX(p.published_utc) AS latest_observed_post,
               r.status AS latest_run_status, r.error AS latest_error,
               r.window_start, r.window_end, r.limitations
        FROM accounts a LEFT JOIN posts p ON p.account_id=a.id
        LEFT JOIN runs r ON r.id=(
            SELECT MAX(id) FROM runs WHERE account_id=a.id
        ) GROUP BY a.id ORDER BY a.id
    """)]


def export(db, directory, public=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    omitted = []
    included_ids = set()
    for table in ("outlets", "accounts", "evidence", "posts", "provenance", "observations", "runs"):
        records = rows(db, table)
        if table == "posts":
            if public:
                omitted = [{"post_id": row["id"], "reason": "Redistribution not explicitly permitted"}
                           for row in records if row["redistribution"] != "permitted"]
                records = [row for row in records if row["redistribution"] == "permitted"]
            included_ids = {row["id"] for row in records}
            enriched = []
            for record in records:
                record["provenance"] = [dict(row) for row in db.execute(
                    "SELECT * FROM provenance WHERE post_id=? ORDER BY retrieved_at,source_url",
                    (record["id"],))]
                record["engagement_observations"] = [dict(row) for row in db.execute(
                    "SELECT * FROM observations WHERE post_id=? ORDER BY observed_at,source_url",
                    (record["id"],))]
                enriched.append(record)
            records = enriched
            columns = [row[1] for row in db.execute("PRAGMA table_info(posts)")] + [
                "provenance", "engagement_observations"]
        else:
            columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            if table in {"provenance", "observations"}:
                records = [row for row in records if row["post_id"] in included_ids]
            if public and table == "runs":
                # Checkpoints contain private feed previews.
                records = [dict(row, checkpoint=None) for row in records]
        write_csv(directory / f"{table}.csv", records, columns)
        with open(directory / f"{table}.jsonl", "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json_text(record) + "\n")
    account_coverage = coverage(db)
    if account_coverage:
        write_csv(directory / "coverage.csv", account_coverage, list(account_coverage[0]))
    else:
        write_csv(directory / "coverage.csv", [], ["account_id", "recovered_posts"])
    write_csv(directory / "omissions.csv", omitted, ["post_id", "reason"])
    manifest = {
        "mode": "public" if public else "local_private",
        "included_posts": len(included_ids), "omitted_posts": len(omitted),
        "contains_full_text": True,
        "completeness": "Recoverable text only; inspect text_status, provenance and coverage.",
        "warning": "Source terms and redistribution rights must be checked before sharing. "
                   "CSV values are unescaped research data; import IDs/text as text in spreadsheets.",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
