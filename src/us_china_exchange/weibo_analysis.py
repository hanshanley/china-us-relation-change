"""Text-free, frozen Weibo research aggregates and their publication figures."""

import html
import json
import math
import re
import sqlite3
import textwrap
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .model import digest, json_text
from .weibo_activity import ROLLING_CHARTS, daily_activity, rolling_activity, validate_activity
from .theme import BLUE, CHART_HEIGHT, CHART_THEMES, CHART_WIDTH, FONT, GOLD, GREEN, GRID, MUTED, TEXT


WEIBO_CHARTS = {
    **{key: config[0] for key, config in ROLLING_CHARTS.items()},
    "monthly-posts": "Recovered posts over time",
    "monthly-accounts": "Channels represented over time",
    "identity-evidence": "Account identity evidence",
    "recovery-coverage": "Recovered corpus coverage",
    "publication-years": "Recovered posts by publication year",
    "text-completeness": "Text completeness of recovered posts",
}
SHANGHAI = ZoneInfo("Asia/Shanghai")
TEXT_LABELS = {
    "source_full": "Available source body",
    "truncated": "Truncated preview",
    "full": "Explicitly full original",
    "unknown": "Unknown completeness",
}
AUDIT_LABELS = {
    "numeric_binding_rechecked": "Numeric identity rechecked",
    "numeric_binding_recheck_pending": "Historical UID recheck pending",
    "vanity_rechecked_uid_unresolved": "Vanity rechecked; UID unresolved",
}
AUDIT_ACCOUNT_FIELDS = {"account_id", "uid", "status", "method", "source_url", "source_sha256",
                        "observed_name", "observed_certification", "note"}
AUDIT_CORPUS_FIELDS = {"posts_checked", "primary_text_matches", "native_detail_sources_checked",
                       "archived_sources_checked", "live_registered_profiles_attempted",
                       "live_registered_profiles_readable", "current_profile_name_matches",
                       "explicit_prior_detail_conflicts_found", "canonical_text_corrections"}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Weibo timestamps require a timezone")
    return parsed


def publication_months(source, accounts):
    intervals = sorted((timestamp(w["start"]).astimezone(SHANGHAI),
                        timestamp(w["end"]).astimezone(SHANGHAI))
                       for w in source["requested_windows"])
    if not intervals:
        dates = [timestamp(a[key]).astimezone(SHANGHAI) for a in accounts
                 for key in ("earliest_publication_utc", "latest_publication_utc") if a[key]]
        if not dates:
            return []
        intervals = [(min(dates), max(dates) + timedelta(microseconds=1))]
    merged = []
    for start, end in intervals:
        if start >= end:
            raise ValueError("Invalid Weibo collection window")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    months = {}
    for start, end in merged:
        current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while current < end:
            following = current.replace(year=current.year + current.month // 12,
                                        month=current.month % 12 + 1)
            month = current.strftime("%Y-%m")
            partial = start > current or end < following
            months[month] = months.get(month, True) and partial
            current = following
    return [{"month": month, "partial_window": months[month]} for month in sorted(months)]


def cohort_summary(path, accounts):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not rows or len({r["domain"] for r in rows}) != len(rows):
        raise ValueError("Invalid or duplicate Weibo cohort domains")
    by_id = {a["account_id"]: a for a in accounts}
    statuses = Counter()
    for row in rows:
        ids = row["account_ids"]
        if len(set(ids)) != len(ids) or any(i not in by_id for i in ids):
            raise ValueError("Weibo cohort contains an unresolved account reference")
        matched = [by_id[i] for i in ids]
        expected = ("confirmed_current_evidence" if any(a["existence"] == "current_evidence" for a in matched)
                    else "confirmed_historical_only" if matched else None)
        if (row["account_status"] not in {"confirmed_current_evidence", "confirmed_historical_only",
                                         "unknown", "candidate_requires_verification"}
                or (expected is not None and row["account_status"] != expected)
                or (expected is None and row["account_status"].startswith("confirmed_"))
                or row["account_uids"] != [a["uid"] for a in matched]
                or row["recovered_posts"] != sum(a["recovered_posts"] for a in matched)
                or row["verified_no_account"] is not False):
            raise ValueError("Weibo cohort and account snapshot do not reconcile")
        statuses[row["account_status"]] += 1
    sources = {r["ranking_source"] for r in rows}
    if len(sources) != 1 or path.read_bytes() != raw:
        raise ValueError("Weibo cohort source changed or has mixed ranking sources")
    return {
        "assessment_sha256": digest(raw), "ranking_source": sources.pop(),
        "ranking_basis": "SCImago U.S.-classified digital reputation, not website traffic",
        "selected_domains": len(rows),
        "manually_reviewed_domains": sum(bool(r["manual_review"]) for r in rows),
        "current_identity_domains": statuses["confirmed_current_evidence"],
        "historical_only_domains": statuses["confirmed_historical_only"],
        "unknown_domains": statuses["unknown"],
        "candidate_domains": statuses["candidate_requires_verification"],
        "verified_negative_domains": 0,
    }


def create_summary(database, registry_path, assessment_path=None, audit_path=None):
    from weibo_media.registry import validate as validate_registry

    registry_path = Path(registry_path)
    registry_bytes = registry_path.read_bytes()
    registry = validate_registry(json.loads(registry_bytes))
    explicit_audit = audit_path is not None
    audit_path = (Path(audit_path) if explicit_audit else
                  registry_path.parent.parent / "discovery/weibo_primary_audit.json")
    if explicit_audit and not audit_path.is_file():
        raise FileNotFoundError(audit_path)
    audit_bytes = audit_path.read_bytes() if audit_path.is_file() else None
    db = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN")
        stored_accounts = {r["id"]: dict(r) for r in db.execute(
            "SELECT id,outlet_id,uid,profile_url,officialness,existence,attribution_end FROM accounts")}
        fields = ("outlet_id", "uid", "profile_url", "officialness", "existence", "attribution_end")
        if set(stored_accounts) != {a["id"] for a in registry["accounts"]} or any(
                any(stored_accounts[a["id"]][key] != a[key] for key in fields)
                for a in registry["accounts"]):
            raise ValueError("Weibo registry and database differ; load the registry before taking a snapshot")
        posts = [dict(r) for r in db.execute(
            "SELECT id,account_id,uid,published_utc,text_status FROM posts ORDER BY id")]
        if audit_bytes is not None:
            db.create_function("audit_text_sha256", 1, lambda value: digest(value.encode()))
            text_hashes = dict(db.execute("SELECT id,audit_text_sha256(text) FROM posts"))
        runs = [dict(r) for r in db.execute(
            "SELECT account_id,status,source_type,started_at,finished_at,window_start,window_end,checkpoint "
            "FROM runs ORDER BY id")]
    finally:
        db.close()
    if registry_path.read_bytes() != registry_bytes:
        raise ValueError("Weibo registry changed during the snapshot; retry")
    confirmed = {a["id"]: a for a in registry["accounts"] if a["officialness"] == "confirmed"}
    outlets = {o["id"]: o for o in registry["outlets"]}
    counts, years, months, statuses, dates = Counter(), Counter(), Counter(), Counter(), {}
    month_accounts = defaultdict(set)
    windows = {(timestamp(r["window_start"]), timestamp(r["window_end"])) for r in runs}
    excluded_unconfirmed = excluded_attribution = 0
    included = []
    for post in posts:
        account = confirmed.get(post["account_id"])
        if account is None:
            excluded_unconfirmed += 1
            continue
        if account["uid"] is None or post["uid"] != account["uid"]:
            raise ValueError("Weibo post UID does not match its registered account")
        published = timestamp(post["published_utc"])
        local = published.astimezone(SHANGHAI)
        if account["attribution_end"] and local.date() >= date.fromisoformat(account["attribution_end"]):
            excluded_attribution += 1
            continue
        if post["text_status"] not in TEXT_LABELS:
            raise ValueError("Unknown Weibo text-completeness status")
        if windows and not any(start <= published < end for start, end in windows):
            raise ValueError("Weibo post publication falls outside requested collection windows")
        counts[account["id"]] += 1
        years[local.year] += 1
        month = local.strftime("%Y-%m")
        months[month] += 1
        month_accounts[month].add(account["id"])
        statuses[post["text_status"]] += 1
        dates.setdefault(account["id"], []).append(published.astimezone(timezone.utc).isoformat())
        included.append(post)
    latest_runs = {r["account_id"]: r for r in runs}
    accounts = []
    for account_id, account in sorted(confirmed.items()):
        observed = dates.get(account_id, [])
        run = latest_runs.get(account_id, {})
        accounts.append({
            "account_id": account_id, "outlet_id": account["outlet_id"],
            "outlet_name": outlets[account["outlet_id"]]["name"],
            "uid": account["uid"], "handle": account["handle"], "display_name": account["display_name"],
            "uid_resolution": "resolved_numeric_uid" if account["uid"] is not None else "unresolved_numeric_uid",
            "category": outlets[account["outlet_id"]]["category"],
            "us_basis": outlets[account["outlet_id"]]["us_basis"],
            "operator": account["operator"], "notes": account["notes"],
            "evidence": [{key: e[key] for key in (
                "source_url", "source_type", "supports", "observed_at", "claim_date", "justification")}
                for e in registry["evidence"] if e["account_id"] == account_id],
            "profile_url": account["profile_url"], "relationship": account["relationship"],
            "existence": account["existence"], "attribution_end": account["attribution_end"],
            "recovered_posts": counts[account_id],
            "earliest_publication_utc": min(observed) if observed else None,
            "latest_publication_utc": max(observed) if observed else None,
            "latest_run_status": run.get("status"), "latest_run_source": run.get("source_type"),
        })
    summary = {
        "version": 5,
        "source": {
            "registry_sha256": digest(registry_bytes),
            "corpus_metadata_sha256": digest(json_text(posts).encode()),
            "latest_collection_at": max(
                (timestamp(r["finished_at"] or r["started_at"]).astimezone(timezone.utc) for r in runs),
                default=None),
            "publication_timezone": "Asia/Shanghai",
            "requested_windows": [dict(start=start, end=end) for start, end in sorted({
                (r["window_start"], r["window_end"]) for r in runs})],
            "excluded_unconfirmed_posts": excluded_unconfirmed,
            "excluded_attribution_posts": excluded_attribution,
        },
        "roster": {
            "outlets": len(registry["outlets"]),
            "reviewed_outlets": sum(o["research_status"] == "reviewed" for o in registry["outlets"]),
            "confirmed_accounts": len(accounts),
            "confirmed_outlets": len({a["outlet_id"] for a in accounts}),
            "resolved_numeric_accounts": sum(a["uid"] is not None for a in accounts),
            "unresolved_numeric_accounts": sum(a["uid"] is None for a in accounts),
        },
        "cohort": None,
        "accounts": accounts,
        "yearly": [{"year": year, "recovered_posts": count} for year, count in sorted(years.items())],
        "text_completeness": [{"status": status, "recovered_posts": statuses[status]} for status in TEXT_LABELS],
    }
    summary["monthly"] = [
        dict(period, recovered_posts=months[period["month"]],
             observed_accounts=len(month_accounts[period["month"]]))
        for period in publication_months(summary["source"], accounts)
    ]
    summary["daily"] = daily_activity(included, accounts, summary["source"]["requested_windows"])
    summary["rolling_30d"] = rolling_activity(summary["daily"], accounts)
    refresh_path = registry_path.parent.parent / "site/weibo_refresh.json"
    summary["refresh"] = json.loads(refresh_path.read_text()) if refresh_path.is_file() else None
    latest = summary["source"]["latest_collection_at"]
    summary["source"]["latest_collection_at"] = latest.isoformat() if latest else None
    explicit_assessment = assessment_path is not None
    assessment_path = (Path(assessment_path) if explicit_assessment else
                       registry_path.parent.parent / "discovery/us_top1000_accounts.jsonl")
    if explicit_assessment and not assessment_path.is_file():
        raise FileNotFoundError(assessment_path)
    if assessment_path.is_file():
        summary["cohort"] = cohort_summary(assessment_path, accounts)
    if audit_bytes is not None:
        audit = json.loads(audit_bytes)
        unreviewed = {post_id for run in runs
                      if run["checkpoint"] and timestamp(run["finished_at"] or run["started_at"]) > timestamp(audit["audited_at"])
                      for post_id in json.loads(run["checkpoint"]).get("source_conflicts", {})}
        if unreviewed.intersection(p["id"] for p in posts):
            raise ValueError("New source conflicts in the existing corpus require re-audit before publication")
        canonical = [dict(p, text_sha256=text_hashes[p["id"]]) for p in posts]
        if (audit_path.read_bytes() != audit_bytes
                or audit.get("registry_sha256") != digest(registry_bytes)
                or audit.get("canonical_posts_sha256") != digest(json_text(canonical).encode())):
            raise ValueError("Primary source audit is stale; re-audit changed registry or post contents before publication")
        summary["primary_source_audit"] = audit
        summary["source"]["primary_audit_sha256"] = digest(json_text(audit).encode())
        by_id = {row["account_id"]: row for row in audit["accounts"]}
        if set(by_id) != set(confirmed):
            raise ValueError("Primary source audit and confirmed account roster differ")
        for account in accounts:
            row = by_id[account["account_id"]]
            for key in ("status", "method", "note", "source_url", "source_sha256"):
                account["primary_audit_" + key] = row[key]
    return validate_summary(summary)


def validate_summary(summary):
    version = summary.get("version")
    has_audit = version == 3 or (version in (4, 5) and "primary_source_audit" in summary)
    fields = {"version", "source", "roster", "accounts", "yearly", "text_completeness"}
    if version in (2, 3, 4, 5):
        fields.add("cohort")
    if version in (4, 5):
        fields.add("monthly")
    if version == 5:
        fields |= {"daily", "rolling_30d", "refresh"}
    if has_audit:
        fields.add("primary_source_audit")
    if set(summary) != fields:
        raise ValueError("Unexpected Weibo aggregate fields; post text must not be published")
    if version not in (1, 2, 3, 4, 5) or summary["source"]["publication_timezone"] != "Asia/Shanghai":
        raise ValueError("Unsupported Weibo aggregate snapshot")
    source_fields = {"registry_sha256", "corpus_metadata_sha256", "latest_collection_at",
                     "publication_timezone", "requested_windows",
                     "excluded_unconfirmed_posts", "excluded_attribution_posts"}
    if has_audit:
        source_fields.add("primary_audit_sha256")
    if set(summary["source"]) != source_fields:
        raise ValueError("Unexpected Weibo source fields")
    roster_fields = {"outlets", "reviewed_outlets", "confirmed_accounts", "confirmed_outlets"}
    if version in (2, 3, 4, 5):
        roster_fields |= {"resolved_numeric_accounts", "unresolved_numeric_accounts"}
    if set(summary["roster"]) != roster_fields:
        raise ValueError("Unexpected Weibo roster fields")
    if any(set(window) != {"start", "end"} or timestamp(window["start"]) >= timestamp(window["end"])
           for window in summary["source"]["requested_windows"]):
        raise ValueError("Invalid Weibo collection window")
    if summary["source"]["latest_collection_at"] is not None:
        timestamp(summary["source"]["latest_collection_at"])
    for value in list(summary["roster"].values()) + [
            summary["source"]["excluded_unconfirmed_posts"], summary["source"]["excluded_attribution_posts"]]:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Invalid Weibo roster or exclusion count")
    if (summary["roster"]["reviewed_outlets"] > summary["roster"]["outlets"]
            or summary["roster"]["confirmed_outlets"] > summary["roster"]["outlets"]):
        raise ValueError("Weibo roster totals do not reconcile")
    accounts, yearly, text = summary["accounts"], summary["yearly"], summary["text_completeness"]
    account_fields = {"account_id", "outlet_id", "outlet_name", "profile_url", "relationship", "existence",
                      "attribution_end", "recovered_posts", "earliest_publication_utc",
                      "latest_publication_utc", "latest_run_status", "latest_run_source"}
    if version in (2, 3, 4, 5):
        account_fields |= {"uid", "handle", "display_name", "uid_resolution", "category", "us_basis",
                           "operator", "notes", "evidence"}
    if has_audit:
        account_fields |= {"primary_audit_" + k for k in ("status", "method", "note", "source_url", "source_sha256")}
    if any(set(a) != account_fields for a in accounts):
        raise ValueError("Unexpected Weibo account aggregate fields")
    if any(set(r) != {"year", "recovered_posts"} for r in yearly) or any(
            set(r) != {"status", "recovered_posts"} for r in text):
        raise ValueError("Unexpected Weibo count fields")
    if len({a["account_id"] for a in accounts}) != len(accounts):
        raise ValueError("Duplicate Weibo account aggregate")
    if len({r["year"] for r in yearly}) != len(yearly):
        raise ValueError("Duplicate Weibo publication-year aggregate")
    if {r["status"] for r in text} != set(TEXT_LABELS) or len(text) != len(TEXT_LABELS):
        raise ValueError("Invalid Weibo text-completeness aggregates")
    if any(a["existence"] not in {"current_evidence", "historical", "unknown"} for a in accounts):
        raise ValueError("Invalid Weibo account evidence status")
    for row in accounts + yearly + text:
        if (isinstance(row["recovered_posts"], bool) or not isinstance(row["recovered_posts"], int)
                or row["recovered_posts"] < 0):
            raise ValueError("Invalid Weibo recovered-post count")
    if any(isinstance(r["year"], bool) or not isinstance(r["year"], int)
           or not 1 <= r["year"] <= 9999 or r["recovered_posts"] == 0 for r in yearly):
        raise ValueError("Publication-year aggregates require observed years and positive counts")
    totals = [sum(r["recovered_posts"] for r in group) for group in (accounts, yearly, text)]
    if len(set(totals)) != 1 or summary["roster"]["confirmed_accounts"] != len(accounts):
        raise ValueError("Weibo aggregate totals do not reconcile")
    if summary["roster"]["confirmed_outlets"] != len({a["outlet_id"] for a in accounts}):
        raise ValueError("Weibo confirmed-outlet count does not reconcile")
    if version in (4, 5):
        monthly = summary["monthly"]
        month_fields = {"month", "recovered_posts", "observed_accounts", "partial_window"}
        if any(set(row) != month_fields for row in monthly):
            raise ValueError("Unexpected Weibo monthly fields")
        if ([{"month": r["month"], "partial_window": r["partial_window"]} for r in monthly]
                != publication_months(summary["source"], accounts)
                or any(type(r["partial_window"]) is not bool for r in monthly)):
            raise ValueError("Weibo monthly periods do not match collection windows")
        represented = [
            (timestamp(a["earliest_publication_utc"]).astimezone(SHANGHAI).strftime("%Y-%m"),
             timestamp(a["latest_publication_utc"]).astimezone(SHANGHAI).strftime("%Y-%m"))
            for a in accounts if a["recovered_posts"] > 0]
        if any(type(r["recovered_posts"]) is not int or r["recovered_posts"] < 0
               or type(r["observed_accounts"]) is not int
               or not 0 <= r["observed_accounts"] <= min(
                   sum(start <= r["month"] <= end for start, end in represented), r["recovered_posts"])
               or (r["observed_accounts"] == 0) != (r["recovered_posts"] == 0) for r in monthly):
            raise ValueError("Invalid Weibo monthly recovered-post or channel counts")
        monthly_years = Counter()
        for row in monthly:
            if row["recovered_posts"]:
                monthly_years[int(row["month"][:4])] += row["recovered_posts"]
        if dict(monthly_years) != {r["year"]: r["recovered_posts"] for r in yearly}:
            raise ValueError("Weibo monthly and annual totals do not reconcile")
    if version == 5:
        validate_activity(summary)
        refresh = summary["refresh"]
        if refresh is not None:
            refresh_fields = {"mode", "status", "attempted_at", "successful_collection_at", "through_date",
                              "accounts_attempted", "readable_feeds", "new_posts", "errors", "note"}
            if (set(refresh) != refresh_fields or refresh["mode"] != "daily_local"
                    or refresh["status"] not in {"current", "partial", "blocked", "failed", "deferred"}
                    or any(type(refresh[k]) is not int or refresh[k] < 0 for k in (
                        "accounts_attempted", "readable_feeds", "new_posts"))
                    or refresh["readable_feeds"] > refresh["accounts_attempted"]
                    or not isinstance(refresh["errors"], list)
                    or any(set(e) != {"account_id", "reason"} for e in refresh["errors"])):
                raise ValueError("Invalid Weibo automatic-refresh status")
            timestamp(refresh["attempted_at"])
            if refresh["successful_collection_at"]:
                timestamp(refresh["successful_collection_at"])
            if refresh["through_date"]:
                date.fromisoformat(refresh["through_date"])
    if version in (2, 3, 4, 5):
        uids = [a["uid"] for a in accounts if a["uid"] is not None]
        if (any(not isinstance(uid, str) or not uid.isascii() or not uid.isdigit() for uid in uids)
                or len(set(uids)) != len(uids)
                or summary["roster"]["resolved_numeric_accounts"] != len(uids)
                or summary["roster"]["unresolved_numeric_accounts"] != len(accounts) - len(uids)
                or any(a["uid_resolution"] != ("resolved_numeric_uid" if a["uid"] is not None
                                               else "unresolved_numeric_uid")
                       or (a["uid"] is None and a["recovered_posts"]) for a in accounts)):
            raise ValueError("Weibo numeric identity counts do not reconcile")
        evidence_fields = {"source_url", "source_type", "supports", "observed_at", "claim_date", "justification"}
        if any(not a["evidence"] or any(set(e) != evidence_fields for e in a["evidence"]) for a in accounts):
            raise ValueError("Unexpected or missing Weibo account evidence")
        cohort = summary["cohort"]
        if cohort is not None:
            count_fields = {"selected_domains", "manually_reviewed_domains", "current_identity_domains",
                            "historical_only_domains", "unknown_domains", "candidate_domains",
                            "verified_negative_domains"}
            if set(cohort) != count_fields | {"assessment_sha256", "ranking_source", "ranking_basis"}:
                raise ValueError("Unexpected Weibo cohort fields")
            if (any(isinstance(cohort[k], bool) or not isinstance(cohort[k], int) or cohort[k] < 0
                    for k in count_fields)
                    or cohort["manually_reviewed_domains"] > cohort["selected_domains"]
                    or sum(cohort[k] for k in ("current_identity_domains", "historical_only_domains",
                                               "unknown_domains", "candidate_domains",
                                               "verified_negative_domains")) != cohort["selected_domains"]):
                raise ValueError("Weibo cohort totals do not reconcile")
    if has_audit:
        audit = summary["primary_source_audit"]
        audit_fields = {"version", "audited_at", "registry_sha256", "canonical_posts_sha256",
                        "post_manifest_sha256", "scope", "accounts", "corpus"}
        if (set(audit) != audit_fields or audit["version"] != 1
                or set(audit["corpus"]) != AUDIT_CORPUS_FIELDS
                or any(set(a) != AUDIT_ACCOUNT_FIELDS for a in audit["accounts"])):
            raise ValueError("Unexpected primary source audit fields; raw source text must not be published")
        timestamp(audit["audited_at"])
        if summary["source"]["primary_audit_sha256"] != digest(json_text(audit).encode()):
            raise ValueError("Primary source audit checksum does not reconcile")
        if (audit["registry_sha256"] != summary["source"]["registry_sha256"]
                or any(not isinstance(audit[k], str) or not re.fullmatch(r"[0-9a-f]{64}", audit[k])
                       for k in ("registry_sha256", "canonical_posts_sha256", "post_manifest_sha256"))
                or any(type(v) is not int or v < 0 for v in audit["corpus"].values())):
            raise ValueError("Invalid primary source audit hashes or counts")
        by_id = {a["account_id"]: a for a in audit["accounts"]}
        if len(by_id) != len(audit["accounts"]) or set(by_id) != {a["account_id"] for a in accounts}:
            raise ValueError("Primary source audit account decisions do not reconcile")
        for account in accounts:
            row = by_id[account["account_id"]]
            url = urlsplit(row["source_url"]) if isinstance(row["source_url"], str) else None
            if not url or url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password:
                raise ValueError("Invalid primary source audit URL")
            if (row["uid"] != account["uid"] or row["status"] not in AUDIT_LABELS
                    or any(account["primary_audit_" + k] != row[k] for k in (
                        "status", "method", "note", "source_url", "source_sha256"))
                    or (row["status"] == "vanity_rechecked_uid_unresolved") != (row["uid"] is None)
                    or (row["status"] == "numeric_binding_recheck_pending" and account["recovered_posts"])
                    or (row["source_sha256"] is not None
                        and (not isinstance(row["source_sha256"], str)
                             or not re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"])))
                    or (row["status"] != "numeric_binding_recheck_pending" and row["source_sha256"] is None)):
                raise ValueError("Primary source audit identity decision does not reconcile")
        corpus = audit["corpus"]
        if (corpus["posts_checked"] != totals[0] or corpus["primary_text_matches"] != totals[0]
                or corpus["live_registered_profiles_readable"] > corpus["live_registered_profiles_attempted"]
                or corpus["live_registered_profiles_attempted"] > summary["roster"]["resolved_numeric_accounts"]
                or corpus["current_profile_name_matches"] > sum(a["existence"] == "current_evidence" for a in accounts)):
            raise ValueError("Primary source audit coverage does not reconcile")
    return summary


def svg_monthly(summary, metric, theme):
    rolling = metric in ROLLING_CHARTS
    rows = [r for r in summary.get("rolling_30d", []) if not r["partial_window"]] if rolling else summary.get("monthly", [])
    if not rows or not any(row["recovered_posts"] for row in rows):
        return '<p class="gap">Publication-date aggregates are not available in this snapshot.</p>'
    field = ROLLING_CHARTS[metric][1] if rolling else "recovered_posts" if metric == "monthly-posts" else "observed_accounts"
    unit = ROLLING_CHARTS[metric][2] if rolling else "Recovered posts per month" if metric == "monthly-posts" else "Channels with recovered posts per month"
    period = "date" if rolling else "month"
    maximum = max(row[field] for row in rows) * 1.12
    magnitude = 10 ** math.floor(math.log10(maximum))
    maximum = math.ceil(maximum / magnitude) * magnitude
    month_number = (lambda day: date.fromisoformat(day).toordinal()) if rolling else (
        lambda month: int(month[:4]) * 12 + int(month[5:]) - 1)
    first, last = month_number(rows[0][period]), month_number(rows[-1][period])
    x = lambda month: 115 + ((month_number(month) - first) / (last - first) if last != first else .5) * 835
    y = lambda value: 420 - value / maximum * 270
    esc = lambda value: html.escape(str(value), quote=True)
    subtitle = f'{"Trailing 30 days" if rolling else "Monthly publication dates"}, Asia/Shanghai | {rows[0][period]} to {rows[-1][period]}'
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" data-metric="{metric}" aria-label="{esc(WEIBO_CHARTS[metric])}">',
        f'<title>{esc(WEIBO_CHARTS[metric])}</title>',
        '<desc>Monthly counts in the recovered sample only, not total posting activity. '
        'Unrequested months break the line. Hollow markers identify partial requested months.</desc>',
        f'<rect class="chart-background" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{CHART_THEMES[theme]["background"]}"/>',
        f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
        f'<text x="80" y="45" font-size="28" font-weight="bold" fill="{TEXT}">{esc(WEIBO_CHARTS[metric])}</text>',
        f'<text x="80" y="82" font-size="18">{esc(subtitle)}</text>',
        f'<text class="axis-unit" x="115" y="125" font-size="18" fill="{TEXT}">{unit}</text>',
    ]
    for fraction in (0, .5, 1):
        value = maximum * fraction
        label = f"{value:,.1f}" if metric == "rolling30-average" else f"{value:,.0f}"
        parts.append(f'<path d="M115 {y(value):.2f}H950" stroke="{GRID}" stroke-opacity=".6" stroke-width=".5"/>'
                     f'<text x="100" y="{y(value) + 6:.2f}" text-anchor="end">{label}</text>')
    ticks = [0]
    for i, row in enumerate(rows[1:-1], 1):
        distance = month_number(row[period]) - first
        remaining = last - month_number(row[period])
        if ((not rolling and last - first <= 18 and distance % 4 == 0 and remaining >= 4)
                or (row[period].endswith("-01-01" if rolling else "-01")
                    and distance >= (180 if rolling else 6) and remaining >= (365 if rolling else 12))):
            if len(ticks) == 1 or x(row[period]) - x(rows[ticks[-1]][period]) >= 85:
                ticks.append(i)
    if len(rows) > 1:
        ticks.append(len(rows) - 1)
    for i in ticks:
        row = rows[i]
        label = datetime.strptime(row[period], "%Y-%m-%d" if rolling else "%Y-%m").strftime(
            "%b %Y" if (not rolling and last - first <= 18) or not row[period].endswith("-01-01" if rolling else "-01") else "%Y")
        label += "*" if row["partial_window"] else ""
        anchor = "start" if i == 0 else "end" if i == len(rows) - 1 else "middle"
        parts.append(f'<text x="{x(row[period]):.2f}" y="457" text-anchor="{anchor}" font-size="18">{esc(label)}</text>')
    previous = None
    line = []
    for row in rows:
        if rolling:
            connected = previous and month_number(row[period]) == month_number(previous[period]) + 1
            line.append(f'{"L" if connected else "M"}{x(row[period]):.2f},{y(row[field]):.2f}')
        elif previous and month_number(row["month"]) == month_number(previous["month"]) + 1:
            partial = row["partial_window"] or previous["partial_window"]
            dash = ' stroke-dasharray="5 4"' if partial else ""
            parts.append(f'<path class="data-line" d="M{x(previous["month"]):.2f},{y(previous[field]):.2f} '
                         f'L{x(row["month"]):.2f},{y(row[field]):.2f}" fill="none" stroke="{BLUE}" '
                         f'stroke-width="2.5"{dash}/>')
        previous = row
    if rolling:
        parts.append(f'<path class="data-line" d="{" ".join(line)}" fill="none" stroke="{BLUE}" stroke-width="2.5"/>')
    for row in rows:
        fill = CHART_THEMES[theme]["background"] if row["partial_window"] else BLUE
        detail = f'{row[period]}: {row[field]:,}' + ("; partial requested month" if row["partial_window"] else "")
        radius = 3 if not rolling or row is rows[-1] else 0
        parts.append(f'<circle class="data-point" data-{period}="{row[period]}" data-value="{row[field]}" '
                     f'data-partial-window="{str(row["partial_window"]).lower()}" '
                     f'cx="{x(row[period]):.2f}" cy="{y(row[field]):.2f}" r="{radius}" '
                     f'fill="{fill}" stroke="{BLUE}" stroke-width="1.3"><title>{esc(detail)}</title></circle>')
    note = ("Source: recovered-corpus metadata. Uneven recovery is not a posting-activity trend. "
            "Zero means no recovered posts, not inactivity. Channels are distinct accounts, not publishers. "
            "* Hollow markers and dashed segments: partial requested months; no extrapolation.")
    if rolling:
        note = ("Source: recovered-corpus metadata; lower bounds, not total activity. Each window includes "
                "the shown date and previous 29 Shanghai days. Daily mean = recovered posts / 30. "
                "First 29 days and windows crossing unrequested/partial days are unavailable, not zero. "
                "Distinct publisher/brand groups are not necessarily independent U.S. newsrooms.")
    if summary["source"]["requested_windows"]:
        end = max(timestamp(w["end"]) for w in summary["source"]["requested_windows"])
        note += f' Requested window ends {(end.astimezone(SHANGHAI) - timedelta(microseconds=1)):%d %b %Y}.'
    else:
        note += " No requested window recorded; range spans recovered publication dates only."
    for line, text in enumerate(textwrap.wrap(note, width=103)):
        parts.append(f'<text class="figure-source" x="80" y="{505 + line * 21}" font-size="15" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def svg_weibo(summary, metric, theme="themarginoferror"):
    validate_summary(summary)
    if metric in {"monthly-posts", "monthly-accounts"} or metric in ROLLING_CHARTS:
        return svg_monthly(summary, metric, theme)
    accounts = summary["accounts"]
    if metric == "identity-evidence":
        counts = Counter(a["existence"] for a in accounts)
        values = [("Current profile evidence", counts["current_evidence"], BLUE),
                  ("Historical evidence", counts["historical"], GOLD),
                  ("Existence unknown", counts["unknown"], MUTED)]
        unresolved = summary["roster"].get("unresolved_numeric_accounts")
        identity = (f"Numeric UID unresolved for {unresolved} channel(s). " if unresolved is not None else
                    "Numeric UID resolution is not recorded in this legacy snapshot. ")
        if "primary_source_audit" in summary:
            decisions = summary["primary_source_audit"]["accounts"]
            rechecked = sum(a["status"] == "numeric_binding_rechecked" for a in decisions)
            pending = sum(a["status"] == "numeric_binding_recheck_pending" for a in decisions)
            identity = f"UID recheck: {rechecked} done, {pending} pending, {unresolved} unresolved. "
        note = ("Only documented channels; unknown outlet domains are excluded. " + identity
                + "Profile identity does not prove activity, U.S. operation or ongoing licensing.")
    elif metric == "recovery-coverage":
        recovered = sum(a["recovered_posts"] > 0 for a in accounts)
        unattempted = sum(a["recovered_posts"] == 0 and a["latest_run_status"] is None for a in accounts)
        values = [("With recovered posts", recovered, BLUE),
                  ("Attempted, no recovery", len(accounts) - recovered - unattempted, GOLD),
                  ("Not attempted", unattempted, MUTED)]
        note = "Zero recovered posts can reflect access or coverage limits; it never establishes zero account output."
    elif metric == "text-completeness":
        counts = {r["status"]: r["recovered_posts"] for r in summary["text_completeness"]}
        colors = {"source_full": BLUE, "truncated": GOLD, "full": GREEN, "unknown": MUTED}
        values = [(TEXT_LABELS[status], counts[status], colors[status]) for status in TEXT_LABELS]
        note = "Source-full means the available source body, not verified original completeness or recovered images/video."
    elif metric == "publication-years":
        counts = {r["year"]: r["recovered_posts"] for r in summary["yearly"]}
        if not counts:
            return '<p class="gap">No recovered publication dates in this snapshot.</p>'
        values = [(str(year), counts.get(year), BLUE) for year in range(min(counts), max(counts) + 1)]
        note = ("Publication years use Asia/Shanghai. Coverage and collection effort vary; this is not a posting-activity "
                "trend or a causal measure. Unobserved years are not zero activity.")
    else:
        raise ValueError("Unknown Weibo figure")
    maximum = max((v for _, v, _ in values if v is not None), default=0) * 1.12 or 1
    magnitude = 10 ** math.floor(math.log10(maximum))
    maximum = math.ceil(maximum / magnitude) * magnitude
    esc = lambda value: html.escape(str(value), quote=True)
    snapshot = summary["source"]["latest_collection_at"]
    subtitle = f"Latest recorded collection: {snapshot[:10] if snapshot else 'no collection attempts'}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="{esc(WEIBO_CHARTS[metric])}">',
        f'<title>{esc(WEIBO_CHARTS[metric])}</title><desc>Aggregate research coverage only. Partial recovery is not total output or popularity.</desc>',
        f'<rect class="chart-background" width="1000" height="600" fill="{CHART_THEMES[theme]["background"]}"/>',
        f'<g font-family="{esc(FONT)}" font-size="20" fill="{MUTED}">',
        f'<text x="80" y="45" font-size="28" font-weight="bold" fill="{TEXT}">{esc(WEIBO_CHARTS[metric])}</text>',
        f'<text x="80" y="82">{esc(subtitle)}</text>',
    ]
    annual = metric == "publication-years"
    unit = "Documented channels" if metric in {"identity-evidence", "recovery-coverage"} else "Recovered posts"
    parts.append(f'<text class="axis-unit" x="{115 if annual else 380}" y="{130 if annual else 116}" '
                 f'font-size="18" fill="{TEXT}">{unit}</text>')
    for fraction in (0, .5, 1):
        value = maximum * fraction
        if annual:
            y = 420 - fraction * 260
            parts.append(f'<path d="M115 {y:.2f}H950" stroke="{GRID}" stroke-opacity=".6" stroke-width=".5"/>'
                         f'<text x="100" y="{y + 6:.2f}" text-anchor="end">{value:,.0f}</text>')
        else:
            x = 380 + fraction * 540
            parts.append(f'<path d="M{x:.2f} 125V440" stroke="{GRID}" stroke-opacity=".6" stroke-width=".5"/>'
                         f'<text x="{x:.2f}" y="470" text-anchor="middle">{value:,.0f}</text>')
    for i, (label, value, color) in enumerate(values):
        if annual:
            x = 115 + (i + .5) / len(values) * 835
            width = 835 / len(values) * .6
            if value is not None:
                height = value / maximum * 260
                parts.append(f'<rect class="data-bar" data-label="{esc(label)}" data-value="{value}" x="{x - width / 2:.2f}" '
                             f'y="{420 - height:.2f}" width="{width:.2f}" height="{height:.2f}" fill="{color}"/>'
                             f'<text x="{x:.2f}" y="{410 - height:.2f}" text-anchor="middle" fill="{TEXT}">{value:,}</text>')
            else:
                parts.append(f'<text x="{x:.2f}" y="410" text-anchor="middle">n/a</text>')
            parts.append(f'<text x="{x:.2f}" y="455" text-anchor="middle">{esc(label)}</text>')
        else:
            y = 145 + i * 82
            width = value / maximum * 540
            parts.append(f'<text x="80" y="{y + 25}" font-size="18" fill="{TEXT}">{esc(label)}</text>'
                         f'<rect class="data-bar" data-label="{esc(label)}" data-value="{value}" x="380" y="{y}" '
                         f'width="{width:.2f}" height="36" fill="{color}"/>'
                         f'<text x="{392 + width:.2f}" y="{y + 25}" fill="{TEXT}">{value:,}</text>')
    footnote = ("Source: local Weibo identity registry and recovered-corpus metadata; public aggregates only. "
                "Recovery is partial, not total posting or popularity. " + note)
    for line, text in enumerate(textwrap.wrap(footnote, width=100)):
        parts.append(f'<text class="figure-source" x="80" y="{510 + line * 21}" font-size="15" font-style="italic">{esc(text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)
