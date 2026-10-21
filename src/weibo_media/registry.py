import json
from datetime import datetime
from urllib.parse import urlsplit

from .storage import json_text


OFFICIALNESS = {"confirmed", "unresolved", "rejected"}
STRONG_EVIDENCE = {"publisher_link", "publisher_statement", "platform_certification",
                   "direct_confirmation"}
FIELDS = {
    "outlets": {"id", "name", "category", "aliases", "us_basis", "source_url",
                "research_status", "notes"},
    "accounts": {"id", "outlet_id", "uid", "handle", "display_name", "profile_url",
                 "language", "operator", "relationship", "officialness", "existence",
                 "accessibility", "notes"},
    "evidence": {"id", "account_id", "source_url", "source_type", "observed_at",
                 "claim_date", "supports", "justification"},
}


def valid_url(value):
    if not isinstance(value, str):
        raise ValueError("URL must be a string")
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("Evidence and profile URLs must be absolute HTTP(S) URLs")


def validate(data):
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise ValueError("Registry must contain exactly outlets, accounts, and evidence")
    for table, fields in FIELDS.items():
        if not isinstance(data.get(table), list):
            raise ValueError(f"Registry requires a {table} list")
        for row in data[table]:
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError(f"{table} row fields must be exactly: {', '.join(sorted(fields))}")
            nullable = {"uid", "handle", "claim_date"}
            for key, value in row.items():
                if key == "aliases":
                    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                        raise ValueError("Outlet aliases must be a list of strings")
                elif not isinstance(value, str) and not (key in nullable and value is None):
                    raise ValueError(f"{table}.{key} must be a string")
        ids = [row["id"] for row in data[table]]
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError(f"{table} IDs must be nonempty strings")
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate {table} ID")
    outlets = {row["id"] for row in data["outlets"]}
    accounts = {row["id"] for row in data["accounts"]}
    for evidence in data["evidence"]:
        if evidence["account_id"] not in accounts:
            raise ValueError("Evidence references unknown account")
        valid_url(evidence["source_url"])
        if datetime.fromisoformat(evidence["observed_at"]).tzinfo is None:
            raise ValueError("Evidence observation timestamp requires a timezone")
        if evidence["claim_date"]:
            datetime.fromisoformat(evidence["claim_date"])
        if evidence["supports"] not in {"identity", "relationship", "historical", "access"}:
            raise ValueError("Unsupported evidence purpose")
        if not evidence["justification"].strip():
            raise ValueError("Evidence requires a justification")
    seen_uids = set()
    for account in data["accounts"]:
        if account["outlet_id"] not in outlets:
            raise ValueError("Account references unknown outlet")
        if account["officialness"] not in OFFICIALNESS:
            raise ValueError("Unsupported officialness")
        if account["existence"] not in {"current_evidence", "historical", "unknown"}:
            raise ValueError("Unsupported existence status")
        if account["accessibility"] not in {"observable", "login_required", "unavailable", "unknown"}:
            raise ValueError("Unsupported accessibility")
        valid_url(account["profile_url"])
        uid = account.get("uid")
        if uid is not None:
            if not isinstance(uid, str) or not uid.isascii() or not uid.isdigit():
                raise ValueError("UID must be a numeric string or null")
            if uid in seen_uids:
                raise ValueError("Duplicate UID")
            seen_uids.add(uid)
        evidence = [row for row in data["evidence"] if row["account_id"] == account["id"]]
        if account["officialness"] == "confirmed" and not any(
            row["source_type"] in STRONG_EVIDENCE and
            row["supports"] in {"identity", "historical"} for row in evidence
        ):
            raise ValueError(f"Confirmed account {account['id']} lacks direct identity evidence")
        if not account["relationship"] or not account["operator"]:
            raise ValueError("Operator and relationship must be explicit (unknown is allowed)")
    for outlet in data["outlets"]:
        valid_url(outlet["source_url"])
        if outlet["research_status"] not in {"reviewed", "pending"}:
            raise ValueError("Unsupported outlet research status")
        if not outlet["us_basis"]:
            raise ValueError("Outlet requires a U.S.-inclusion basis")
    return data


def load(db, path):
    with open(path, encoding="utf-8") as stream:
        data = validate(json.load(stream))
    with db:
        for table in ("outlets", "accounts", "evidence"):
            for original in data[table]:
                row = dict(original)
                if table == "outlets":
                    row["aliases"] = json_text(row["aliases"])
                columns = list(row)
                db.execute(
                    f"INSERT INTO {table} ({','.join(columns)}) VALUES "
                    f"({','.join('?' for _ in columns)}) ON CONFLICT(id) DO UPDATE SET " +
                    ",".join(f"{column}=excluded.{column}" for column in columns if column != "id"),
                    list(row.values()),
                )
    return {table: len(data[table]) for table in ("outlets", "accounts", "evidence")}
