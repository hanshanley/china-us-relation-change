"""Text-free, frozen Weibo research aggregates and their publication figures."""

import html
import json
import math
import sqlite3
import textwrap
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .model import digest, json_text
from .theme import BLUE, CHART_HEIGHT, CHART_THEMES, CHART_WIDTH, FONT, GOLD, GREEN, GRID, MUTED, TEXT


WEIBO_CHARTS = {
    "identity-evidence": "Account identity evidence",
    "recovery-coverage": "Recovered corpus coverage",
    "publication-years": "Recovered posts by publication year",
    "text-completeness": "Text completeness of recovered posts",
}
TEXT_LABELS = {
    "source_full": "Available source body",
    "truncated": "Truncated preview",
    "full": "Explicitly full original",
    "unknown": "Unknown completeness",
}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Weibo timestamps require a timezone")
    return parsed


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


def create_summary(database, registry_path, assessment_path=None):
    from weibo_media.registry import validate as validate_registry

    registry_path = Path(registry_path)
    registry_bytes = registry_path.read_bytes()
    registry = validate_registry(json.loads(registry_bytes))
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
        runs = [dict(r) for r in db.execute(
            "SELECT account_id,status,source_type,started_at,finished_at,window_start,window_end FROM runs ORDER BY id")]
    finally:
        db.close()
    if registry_path.read_bytes() != registry_bytes:
        raise ValueError("Weibo registry changed during the snapshot; retry")
    confirmed = {a["id"]: a for a in registry["accounts"] if a["officialness"] == "confirmed"}
    outlets = {o["id"]: o for o in registry["outlets"]}
    counts, years, statuses, dates = Counter(), Counter(), Counter(), {}
    excluded_unconfirmed = excluded_attribution = 0
    for post in posts:
        account = confirmed.get(post["account_id"])
        if account is None:
            excluded_unconfirmed += 1
            continue
        if account["uid"] is None or post["uid"] != account["uid"]:
            raise ValueError("Weibo post UID does not match its registered account")
        published = timestamp(post["published_utc"])
        local = published.astimezone(ZoneInfo("Asia/Shanghai"))
        if account["attribution_end"] and local.date() >= date.fromisoformat(account["attribution_end"]):
            excluded_attribution += 1
            continue
        if post["text_status"] not in TEXT_LABELS:
            raise ValueError("Unknown Weibo text-completeness status")
        counts[account["id"]] += 1
        years[local.year] += 1
        statuses[post["text_status"]] += 1
        dates.setdefault(account["id"], []).append(published.astimezone(timezone.utc).isoformat())
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
        "version": 2,
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
    latest = summary["source"]["latest_collection_at"]
    summary["source"]["latest_collection_at"] = latest.isoformat() if latest else None
    explicit_assessment = assessment_path is not None
    assessment_path = (Path(assessment_path) if explicit_assessment else
                       registry_path.parent.parent / "discovery/us_top1000_accounts.jsonl")
    if explicit_assessment and not assessment_path.is_file():
        raise FileNotFoundError(assessment_path)
    if assessment_path.is_file():
        summary["cohort"] = cohort_summary(assessment_path, accounts)
    return validate_summary(summary)


def validate_summary(summary):
    version = summary.get("version")
    fields = {"version", "source", "roster", "accounts", "yearly", "text_completeness"}
    if version == 2:
        fields.add("cohort")
    if set(summary) != fields:
        raise ValueError("Unexpected Weibo aggregate fields; post text must not be published")
    if version not in (1, 2) or summary["source"]["publication_timezone"] != "Asia/Shanghai":
        raise ValueError("Unsupported Weibo aggregate snapshot")
    if set(summary["source"]) != {"registry_sha256", "corpus_metadata_sha256", "latest_collection_at",
                                 "publication_timezone", "requested_windows",
                                 "excluded_unconfirmed_posts", "excluded_attribution_posts"}:
        raise ValueError("Unexpected Weibo source fields")
    roster_fields = {"outlets", "reviewed_outlets", "confirmed_accounts", "confirmed_outlets"}
    if version == 2:
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
    if version == 2:
        account_fields |= {"uid", "handle", "display_name", "uid_resolution", "category", "us_basis",
                           "operator", "notes", "evidence"}
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
    if version == 2:
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
    return summary


def svg_weibo(summary, metric, theme="themarginoferror"):
    validate_summary(summary)
    accounts = summary["accounts"]
    if metric == "identity-evidence":
        counts = Counter(a["existence"] for a in accounts)
        values = [("Current profile evidence", counts["current_evidence"], BLUE),
                  ("Historical evidence", counts["historical"], GOLD),
                  ("Existence unknown", counts["unknown"], MUTED)]
        unresolved = summary["roster"].get("unresolved_numeric_accounts")
        identity = (f"Numeric UID unresolved for {unresolved} channel(s). " if unresolved is not None else
                    "Numeric UID resolution is not recorded in this legacy snapshot. ")
        note = ("Only documented channels; unknown outlet domains are excluded. " + identity
                + "Profile evidence does not prove current activity, U.S. operation or continuing licensing.")
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
