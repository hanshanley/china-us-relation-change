"""A non-temporal view of documented publisher/account associations."""

import html
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from .model import json_text
from .weibo_analysis import AUDIT_LABELS


EVIDENCE_LABELS = {
    "current_evidence": "Profile evidence",
    "historical": "Historical evidence only",
    "unknown": "Evidence period unknown",
}
PREFERRED_PUBLISHERS = ("nyt", "wsj", "bloomberg", "forbes", "npr", "vogue")
LOGO_FILES = tuple(identity + ".svg" for identity in PREFERRED_PUBLISHERS) + ("credits.json",)
PUBLISHER_LABELS = {
    "profile": "Profile evidence only",
    "historical": "Historical evidence only",
    "mixed": "Mixed evidence",
    "unknown": "Evidence period incomplete",
}
EDITORIAL_LABELS = {
    "news_business": "News & business",
    "culture_lifestyle": "Culture & lifestyle",
    "broadcast": "Broadcasting",
    "specialist_trade": "Specialist & trade media",
    "chinese_language": "U.S.-based Chinese-language media",
    "release_services": "News-release services",
    "other": "Other / unclassified",
}
RELATIONSHIP_LABELS = {
    "publisher_linked": "Publisher-linked channels",
    "edition_partner": "Chinese editions & local partners",
    "us_chinese": "U.S.-based Chinese-language outlets",
    "unclassified": "Relationship not classified",
}


def editorial_category(account):
    category = account.get("category", "")
    if category in {"us_chinese_language", "us_chinese_community_media", "us_based_international_broadcaster"}:
        return "chinese_language"
    if category in {"press_release_service", "science_news_release_service"}:
        return "release_services"
    if category in {"newspaper", "business", "digital_news"}:
        return "news_business"
    if category in {"factual_broadcaster", "broadcaster"}:
        return "broadcast"
    if category in {"design_media", "art_media", "travel_media", "lifestyle", "health_lifestyle_media",
                    "music_culture_media", "travel_lifestyle_media", "art_fashion_media"}:
        return "culture_lifestyle"
    if category in {"music_trade_news", "automotive_news", "trade_news", "sports_news", "design_trade_media",
                    "academic_business_media", "specialist", "science_media", "entertainment_trade_news"}:
        return "specialist_trade"
    return "other"


def relationship_category(account):
    if editorial_category(account) == "chinese_language":
        return "us_chinese"
    relationship = account.get("relationship", "").casefold().split(";")[0].split(", not")[0]
    if not relationship:
        return "unclassified"
    if relationship.startswith(("publisher-operated", "publisher-owned")):
        return "publisher_linked"
    if any(word in relationship for word in ("edition", "partner", "distributor", "local branded")):
        return "edition_partner"
    return "publisher_linked"


def publisher_state(accounts):
    states = {a["existence"] for a in accounts}
    if {"current_evidence", "historical"} <= states:
        return "mixed"
    if "unknown" in states:
        return "unknown"
    return "profile" if "current_evidence" in states else "historical"


def category_label(category):
    return {
        "us_chinese_language": "U.S. Chinese-language media",
        "us_chinese_community_media": "U.S. Chinese community media",
        "us_based_international_broadcaster": "U.S.-based international broadcasting",
        "press_release_service": "Press-release services",
    }.get(category, category.replace("_", " ").title())


def coverage_model(summary):
    cohort = summary.get("cohort")
    if not cohort:
        return None
    total = cohort["selected_domains"]
    percentage = lambda count: round(count / total * 100, 1) if total else None
    unresolved = cohort["unknown_domains"] + cohort["candidate_domains"]
    evidence = [
        dict(id="current_evidence", label="Current profile evidence", count=cohort["current_identity_domains"],
             note="A documented publisher/account association. This does not establish current posting."),
        dict(id="historical", label="Historical evidence only", count=cohort["historical_only_domains"],
             note="A documented historical association, not proof of a current account or continuing licence."),
        dict(id="unknown", label="No confirmed account decision", count=cohort["unknown_domains"],
             note="Unknown is not absent: an account may exist or have existed without evidence recovered here."),
        dict(id="candidate", label="Candidate still unresolved", count=cohort["candidate_domains"],
             note="A lead is not yet a confirmed institutional account."),
        dict(id="verified_negative", label="Verified negative in reviewed scope", count=cohort["verified_negative_domains"],
             note="A sourced negative decision within the reviewed scope, not proof that an account never existed."),
    ]
    reviewed = cohort["manually_reviewed_domains"]
    review = [
        dict(id="reviewed", label="Manually reviewed", count=reviewed,
             note="A manual review can still end unresolved. Review progress is not account-adoption prevalence."),
        dict(id="unreviewed", label="Not yet manually reviewed", count=total - reviewed,
             note="Homepage screening is not a completed account-identity investigation."),
    ]
    for group in evidence + review:
        group["percent"] = percentage(group["count"])
    return {
        "total": total,
        "modes": {
            "evidence": dict(percent=percentage(unresolved), count=unresolved,
                             documented=cohort["current_identity_domains"] + cohort["historical_only_domains"],
                             headline="remain unresolved", groups=[g for g in evidence if g["count"]],
                             explanation="Missing evidence is not evidence that an outlet has no Weibo account."),
            "review": dict(percent=percentage(total - reviewed), count=total - reviewed,
                           documented=reviewed,
                           headline="have not had a manual review", groups=[g for g in review if g["count"]],
                           explanation="This shows the investigation's coverage—not the percentage using Weibo."),
        },
    }


def coverage_markup(summary):
    esc = lambda value: html.escape(str(value), quote=True)
    model = coverage_model(summary)
    primary = ""
    if model and model["total"]:
        mode, total = model["modes"]["evidence"], model["total"]
        segments = "".join(
            f'<span class="coverage-segment {g["id"]}" data-state="{g["id"]}" data-count="{g["count"]}" '
            f'style="width:{g["count"] / total * 100:.8f}%" '
            f'title="{esc(g["label"])}: {g["count"]:,} of {total:,} ({g["percent"]:.1f}%)"></span>'
            for g in mode["groups"])
        legend = "".join(
            f'<button type="button" class="coverage-category" data-state="{g["id"]}" '
            f'aria-pressed="false" disabled><span class="coverage-swatch {g["id"]}" aria-hidden="true"></span>'
            f'<span class="coverage-category-name">{esc(g["label"])}'
            f'<small>{g["count"]:,} of {total:,} domains</small></span>'
            f'<strong>{g["percent"]:.1f}%</strong></button>' for g in mode["groups"]
        )
        primary = (
            '<details class="weibo-coverage" id="weibo-coverage"><summary>Selection &amp; research coverage</summary>'
            f'<p id="coverage-tally"><strong>{mode["documented"]:,} of {total:,} selected domains</strong> '
            'have a documented account association.</p>'
            '<div class="coverage-modes" role="group" aria-label="Coverage perspective" hidden>'
            '<button type="button" data-coverage-mode="evidence" aria-pressed="true">Account evidence</button>'
            '<button type="button" data-coverage-mode="review" aria-pressed="false">Review progress</button></div>'
            f'<div id="coverage-bar" class="coverage-bar" role="img" '
            f'aria-label="{total:,} selected domains: {mode["count"]:,} unresolved">'
            + segments + '</div><div class="coverage-key" id="coverage-key">' + legend + '</div>'
            f'<p id="coverage-explanation" class="coverage-explanation" role="status">{esc(mode["explanation"])}</p>'
            '<p class="coverage-source">The cohort is SCImago’s U.S.-classified digital-reputation selection, '
            'not a traffic ranking or an independently audited census of current U.S. ownership. '
            '<a href="https://github.com/hanshanley/china-us-relation-change/blob/main/data/discovery/us_top1000_accounts.csv">'
            'Inspect all domain decisions ↗</a></p></details>'
        )
    accounts = summary["accounts"]
    represented = sum(a["recovered_posts"] > 0 for a in accounts)
    channel_total = len(accounts)
    text_counts = {r["status"]: r["recovered_posts"] for r in summary["text_completeness"]}
    post_total = sum(text_counts.values())

    def recovery_row(title, total, amount, label, segments, note):
        if not total:
            return f'<div class="recovery-row"><h3>{title}</h3><p>No records in this snapshot; no percentage is inferred.</p></div>'
        bars = "".join(
            f'<span class="recovery-segment {state}" style="width:{count / total * 100:.8f}%" '
            f'data-count="{count}" title="{esc(name)}: {count:,} / {total:,} ({count / total * 100:.1f}%)"></span>'
            for state, count, name in segments if count
        )
        labels = " · ".join(f'{name}: {count:,} ({count / total * 100:.1f}%)' for _, count, name in segments if count)
        return (
            f'<div class="recovery-row"><div class="recovery-row-heading"><h3>{title}</h3>'
            f'<p>{amount:,} of {total:,} {label}</p></div>'
            f'<div class="recovery-bar" role="img" aria-label="{esc(labels)}">{bars}</div>'
            f'<p class="recovery-count">{esc(note)}</p>'
            f'<p class="recovery-segment-labels">{esc(labels)}</p></div>'
        )

    channels = recovery_row(
        "Channels with recovered posts", channel_total, represented,
        "documented channels",
        [("represented", represented, "With recovered posts"),
         ("unrepresented", channel_total - represented, "No recovered posts")],
        "This is not an inactivity rate; some historical channels ended before the requested window.",
    )
    texts = recovery_row(
        "Text in the recovered sample", post_total, text_counts.get("source_full", 0) + text_counts.get("full", 0),
        "recovered posts have source text",
        [("source-body", text_counts.get("source_full", 0), "Available source body"),
         ("explicit-full", text_counts.get("full", 0), "Explicitly full original"),
         ("truncated", text_counts.get("truncated", 0), "Truncated preview"),
         ("unknown-text", text_counts.get("unknown", 0), "Unknown completeness")],
        "An available source body is not an independently verified complete original; images and video are not recovered.",
    )
    return primary, (
        '<details class="weibo-recovery" id="weibo-recovery"><summary>Data completeness</summary>'
        '<p class="recovery-intro">These counts describe the recovered sample, not all Weibo posts or the selected-domain cohort.</p>'
        + channels + texts
        + '<div class="coverage-unmeasured">'
        '<p><strong>The share of historical posts missing cannot be estimated.</strong></p>'
        '<p>We do not know the total number published. There is no defensible denominator for a “percent of all posts recovered.” '
        'Uneven recovery is why no posting-history or popularity trend is shown.</p></div></details>'
    )


def channel_composition(summary):
    counts = Counter(account["existence"] for account in summary["accounts"])
    total = sum(counts.values())
    if not total:
        return ""
    segments, labels = [], []
    for state, label in EVIDENCE_LABELS.items():
        count = counts[state]
        if not count:
            continue
        percentage = count / total * 100
        segments.append(
            f'<span class="coverage-segment {state}" data-state="{state}" data-count="{count}" '
            f'style="width:{percentage:.8f}%"></span>')
        labels.append(
            f'<span><i class="coverage-swatch {state}" aria-hidden="true"></i>'
            f'{label}: <strong>{count:,} of {total:,}</strong> ({percentage:.1f}%)</span>')
    return (
        '<section class="weibo-composition" id="weibo-channel-composition">'
        '<h2>Evidence across documented channels</h2>'
        '<p>Channel-level evidence, not publisher counts or a measure of posting activity.</p>'
        f'<div class="coverage-bar" role="img" aria-label="{total} documented channels: '
        + html.escape("; ".join(f"{EVIDENCE_LABELS[state]} {counts[state]}" for state in EVIDENCE_LABELS if counts[state]),
                      quote=True) + '">' + "".join(segments) + '</div>'
        '<div class="weibo-composition-key">' + "".join(labels) + '</div>'
        '<p class="weibo-composition-note">A found profile does not establish current posting, '
        'a continuing licence or U.S. editorial control. Publisher groups above can contain more than one channel.</p></section>'
    )


def explorer_page(summary):
    esc = lambda value: html.escape(str(value), quote=True)

    def link(url, label):
        parsed = urlsplit(url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return esc(label)
        return (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
                f'{esc(label)}</a>')

    accounts = summary["accounts"]
    groups = defaultdict(list)
    for account in accounts:
        groups[account["outlet_id"]].append(account)
    priority = {identity: i for i, identity in enumerate(PREFERRED_PUBLISHERS)}
    ordered = sorted(groups.values(), key=lambda rows: (
        priority.get(rows[0]["outlet_id"], len(priority)),
        rows[0]["outlet_name"].casefold(), rows[0]["outlet_id"]))
    states = Counter(publisher_state(group) for group in ordered)
    categories = sorted({editorial_category(a) for a in accounts}, key=EDITORIAL_LABELS.get)
    relationships = sorted({relationship_category(a) for a in accounts}, key=RELATIONSHIP_LABELS.get)
    cards, details, model, publishers = [], [], [], []
    for group in ordered:
        first = group[0]
        identity, name = first["outlet_id"], first["outlet_name"]
        state = publisher_state(group)
        dots, group_details = [], []
        for account in sorted(group, key=lambda a: (a.get("display_name", a["account_id"]).casefold(), a["account_id"])):
            identifier = account["account_id"]
            state = account["existence"]
            title = account.get("display_name") or account["outlet_name"]
            label = EVIDENCE_LABELS[state]
            audit = account.get("primary_audit_status")
            needs_review = audit != "numeric_binding_rechecked"
            model.append({
                "id": identifier, "outlet": account["outlet_id"],
                "category": account.get("category", "not_recorded"), "state": state,
                "editorial_category": editorial_category(account), "relationship": relationship_category(account),
                "needs_review": needs_review,
                "search": " ".join(str(account.get(k) or "") for k in
                                   ("outlet_name", "display_name", "handle", "uid", "account_id")),
            })
            dots.append(
                f'<a class="weibo-dot weibo-channel-link {esc(state)}" href="#weibo-account-{esc(identifier)}" '
                f'data-account-id="{esc(identifier)}" aria-label="{esc(first["outlet_name"])}: '
                f'{esc(title)} — {esc(label)}" title="{esc(title)} — {esc(label)}">'
                f'<span class="weibo-state-dot" aria-hidden="true"></span>'
                f'<span class="weibo-link-name">{esc(title)}</span>'
                f'<span class="weibo-link-state">{esc("Profile evidence" if state == "current_evidence" else label)}</span></a>'
            )
            sources = "".join(
                f'<li>{link(e["source_url"], e["source_type"].replace("_", " ").capitalize())}'
                f'<p>{esc(e["justification"])}</p>'
                f'<small>Observed {esc(e["observed_at"][:10])}'
                + (f' · Claim date {esc(e["claim_date"][:10])}' if e.get("claim_date") else "")
                + '</small></li>' for e in account.get("evidence", [])
            )
            uid = account.get("uid") or ("UID unresolved" if summary["version"] >= 2 else "UID not recorded")
            audit_label = AUDIT_LABELS.get(audit, "Not assessed in this snapshot")
            audit_note = account.get("primary_audit_note", "No primary-source recheck is recorded in this snapshot.")
            audit_source = account.get("primary_audit_source_url")
            evidence_rows = account.get("evidence", [])
            dated = max((e["observed_at"][:10] for e in evidence_rows), default=None)
            leading_sources = "".join(
                '<li>' + link(e["source_url"], e["source_type"].replace("_", " ").capitalize())
                + f'<small>Observed {esc(e["observed_at"][:10])}'
                + (f' · Claim dated {esc(e["claim_date"][:10])}' if e.get("claim_date") else "")
                + '</small></li>' for e in evidence_rows[:2])
            group_details.append(
                f'<article class="weibo-channel-detail" id="weibo-account-{esc(identifier)}" '
                f'data-account-id="{esc(identifier)}">'
                f'<p class="weibo-category">{esc(RELATIONSHIP_LABELS[relationship_category(account)])}</p>'
                f'<h4 tabindex="-1" class="weibo-channel-name">{esc(title)}</h4>'
                f'<p class="weibo-evidence-label {esc(state)}">{esc(label)}</p>'
                + (f'<p class="weibo-evidence-date">Latest serialized evidence: {esc(dated)}</p>' if dated else "")
                + f'<p class="weibo-profile">{link(account["profile_url"], "Weibo profile ↗")}</p>'
                f'<p class="weibo-relationship">{esc(account["relationship"])}</p>'
                + (f'<p class="weibo-period">Publisher association recorded only before '
                   f'{esc(account["attribution_end"])}. Later posts are not attributed to this publisher.</p>'
                   if account.get("attribution_end") else "")
                + ('<ul class="weibo-leading-sources">' + leading_sources + '</ul>' if leading_sources else "")
                + '<details><summary>Operator, original notes & publication scope</summary>'
                f'<p><strong>Operator:</strong> {esc(account.get("operator", "Not recorded"))}</p>'
                f'<p>Registry category: {esc(category_label(account.get("category", "not_recorded")))}</p>'
                f'<p>{esc(account.get("us_basis", "U.S.-inclusion basis not recorded in this legacy snapshot."))}</p>'
                f'<p>{esc(account.get("notes", ""))}</p>'
                + '</details>'
                f'<details><summary>Primary source evidence ({len(account.get("evidence", []))})</summary>'
                f'<ol class="weibo-sources">{sources}</ol>'
                + ('' if sources else '<p>No serialized source evidence is available in this legacy snapshot.</p>')
                + '</details>'
                f'<details class="weibo-identity-check"><summary>{esc(audit_label)}</summary>'
                f'<p class="weibo-uid">{esc(uid)}</p>'
                f'<p>{esc(audit_note)}</p>'
                + (f'<p>{link(audit_source, "Recheck source ↗")}</p>' if audit_source else "")
                + '</details></article>'
            )
        state = publisher_state(group)
        publishers.append({
            "id": identity, "name": name, "state": state,
            "categories": sorted({editorial_category(a) for a in group}),
            "research_categories": sorted({a.get("category", "not_recorded") for a in group}),
            "relationships": sorted({relationship_category(a) for a in group}),
            "accounts": [a["account_id"] for a in group],
            "needs_review": any(a.get("primary_audit_status") != "numeric_binding_rechecked" for a in group),
            "search": " ".join(str(a.get(key) or "") for a in group
                               for key in ("outlet_name", "display_name", "handle", "uid", "account_id")),
        })
        logo = Path(__file__).parent / "static/weibo-logos" / f"{identity}.svg"
        mark = (
            f'<span class="weibo-publisher-mark"><img src="assets/weibo-logos/{identity}.svg" '
            f'alt="" width="180" height="52" loading="{"eager" if identity in priority else "lazy"}"></span>'
            f'<h3 class="weibo-publisher-name">{esc(name)}</h3>'
            if identity in PREFERRED_PUBLISHERS and logo.is_file() else
            f'<span class="weibo-publisher-mark"><span class="weibo-wordmark">{esc(name.split(" / ")[0])}</span></span>'
            f'<h3 class="weibo-publisher-name">{esc(name)}</h3>'
        )
        cards.append(
            f'<article class="weibo-brand" data-outlet-id="{esc(identity)}" data-evidence-state="{state}">'
            f'<a class="weibo-publisher-link" href="#weibo-publisher-{esc(identity)}" data-outlet-id="{esc(identity)}" '
            f'aria-controls="weibo-publisher-{esc(identity)}" '
            f'aria-label="{esc(name)} — {PUBLISHER_LABELS[state]}; {len(group)} documented channels">'
            + mark + f'<span class="weibo-publisher-state {state}"><i aria-hidden="true"></i>{PUBLISHER_LABELS[state]}</span>'
            f'<span class="weibo-publisher-count">{len(group)} channel{"s" if len(group) != 1 else ""}</span>'
            '</a></article>'
        )
        profile_count = sum(a["existence"] == "current_evidence" for a in group)
        historical_count = sum(a["existence"] == "historical" for a in group)
        details.append(
            f'<section class="weibo-publisher-detail" id="weibo-publisher-{esc(identity)}" data-outlet-id="{esc(identity)}">'
            '<button type="button" class="weibo-close-publisher">Close details</button>'
            f'<h3 tabindex="-1">{esc(name)}</h3>'
            f'<p class="weibo-publisher-summary">{profile_count} with profile evidence · '
            f'{historical_count} historical-only</p>'
            f'<nav class="weibo-dots" aria-label="{esc(name)} accounts">' + "".join(dots) + '</nav>'
            + "".join(group_details) + '</section>'
        )
    options = "".join(f'<option value="{c}">{esc(EDITORIAL_LABELS[c])}</option>' for c in categories)
    relationship_options = "".join(
        f'<option value="{r}">{esc(RELATIONSHIP_LABELS[r])}</option>' for r in relationships)
    status_controls = (
        '<button type="button" data-publisher-filter="" aria-pressed="true">All publishers</button>'
        + "".join(
            f'<button type="button" data-publisher-filter="{state}" aria-pressed="false">'
            f'<i class="{state}" aria-hidden="true"></i>{esc(label)} <span>{states[state]}</span></button>'
            for state, label in PUBLISHER_LABELS.items() if state != "unknown" or states[state])
    )
    cohort = summary.get("cohort")
    cohort_text = (
        f'<p><strong>{cohort["current_identity_domains"] + cohort["historical_only_domains"]:,} of '
        f'{cohort["selected_domains"]:,} selected domains have documented accounts.</strong> '
        f'{cohort["current_identity_domains"]:,} have current profile evidence; '
        f'{cohort["historical_only_domains"]:,} have historical evidence only. '
        f'{cohort["unknown_domains"]:,} unknown, {cohort["candidate_domains"]:,} unresolved candidates, '
        f'{cohort["verified_negative_domains"]:,} verified negatives. '
        f'{cohort["manually_reviewed_domains"]:,} have recorded manual review.</p>'
        + (f'<p>The documented share is '
           f'{(cohort["current_identity_domains"] + cohort["historical_only_domains"]) / cohort["selected_domains"] * 100:.1f}% '
           'of these selected domains, not of all U.S. publishers. Unresolved domains are not verified absences.</p>'
           if cohort["selected_domains"] else "")
        + f'<p>The selected cohort uses {esc(cohort["ranking_basis"])}. '
        'The atlas also includes separately documented supplemental media. Neither population is a representative '
        'sample for estimating media adoption or market penetration. That would require a bounded sample, an explicit '
        'audience/size measure, deduplicated publishers and systematic investigation of every sampled organization.</p>'
        if cohort else '<p>No ranked-cohort assessment is included in this snapshot; no absence rate is inferred.</p>'
    )
    roster = summary["roster"]
    resolution = (
        f'<p>{roster["resolved_numeric_accounts"]:,} channels have resolved numeric UIDs; '
        f'{roster["unresolved_numeric_accounts"]:,} do not. A historical vanity URL is not a resolved UID.</p>'
        if summary["version"] >= 2 else
        '<p>Numeric UID resolution was not recorded in this legacy snapshot.</p>'
    )
    audit_text = ""
    if "primary_source_audit" in summary:
        checks = Counter(a["status"] for a in summary["primary_source_audit"]["accounts"])
        audit_text = (f'<p>Primary-source recheck: {checks["numeric_binding_rechecked"]} numeric binding'
                      f'{"s" if checks["numeric_binding_rechecked"] != 1 else ""} rechecked; '
                      f'{checks["numeric_binding_recheck_pending"]} historical numeric binding'
                      f'{"s" if checks["numeric_binding_recheck_pending"] != 1 else ""} still pending. '
                      'Resolved identifiers and independently rechecked bindings are different measures.</p>'
                      f'<p>{summary["primary_source_audit"]["corpus"]["canonical_text_corrections"]} canonical text selections were corrected. '
                      'That audit checks source consistency, not complete historical recovery.</p>')
    archive = [("years", "Publication-year aggregates"), ("text-completeness", "Text-completeness aggregates")]
    archive += [(name, label) for name, key, label in (
        ("months", "monthly", "Monthly recovery data"), ("days", "daily", "Daily recovery data"),
        ("rolling30", "rolling_30d", "Trailing-30-day recovery data"),
    ) if key in summary]
    archive_links = " · ".join(
        f'<a href="downloads/weibo-{name}.csv" download>{label} · CSV</a>' for name, label in archive
    )
    payload = json_text({"accounts": model, "publishers": publishers, "coverage": coverage_model(summary)}).replace("<", "\\u003c")
    observed = max((e["observed_at"][:10] for a in accounts for e in a.get("evidence", [])), default=None)
    dated = f'Evidence recorded through {observed}. ' if observed else ""
    cohort_coverage, recovery = coverage_markup(summary)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>U.S. media on Weibo</title><link rel="stylesheet" href="assets/style.css">'
        '<link rel="stylesheet" href="assets/weibo-explorer.css"></head>'
        '<body><div class="page"><header><p><a href="index.html">Exchange dashboard</a></p>'
        '<h1>U.S. media on Weibo</h1><p class="lead">Documented accounts and Chinese-language editions, '
        'with sources for each association.</p></header><main>'
        '<section class="weibo-directory" id="weibo-directory" aria-label="Documented account directory">'
        '<div class="weibo-explorer" id="weibo-explorer">'
        '<div class="weibo-overview">'
        f'<p><strong>{len(accounts):,}</strong><span>documented channels</span></p>'
        f'<p><strong>{len(groups):,}</strong><span>publisher / brand groups</span></p>'
        '</div><p class="weibo-intro">Choose a publisher to inspect its Chinese-language channels and evidence.</p>'
        f'<p class="weibo-snapshot">{esc(dated)}A found profile is not proof of current posting or U.S. editorial control.</p>'
        '<form class="weibo-filters" id="weibo-filters" hidden>'
        '<label>Find an outlet or channel<input id="weibo-search" name="q" type="search" '
        'placeholder="Name or Weibo ID" autocomplete="off"></label>'
        '<button type="button" id="weibo-filter-toggle" class="weibo-filter-toggle" '
        'aria-expanded="false" aria-controls="weibo-filter-options" hidden>Filters</button>'
        '<select id="weibo-evidence" name="evidence" aria-label="Publisher evidence" hidden>'
        '<option value="">All evidence states</option>'
        '<option value="profile">Profile evidence only</option>'
        '<option value="historical">Historical evidence only</option>'
        '<option value="mixed">Mixed evidence</option>'
        '<option value="unknown">Evidence period incomplete</option></select>'
        f'<div class="weibo-state-filters" role="group" aria-label="Publisher evidence">{status_controls}</div>'
        '<div id="weibo-filter-options" class="weibo-filter-options">'
        f'<label>Editorial grouping<select id="weibo-category" name="category"><option value="">All groups</option>{options}</select></label>'
        '<label>Publisher relationship<select id="weibo-relationship" name="relationship">'
        f'<option value="">All relationships</option>{relationship_options}</select></label>'
        '<div class="weibo-filter-actions"><label><input type="checkbox" id="weibo-followup" name="followup">'
        'Evidence checks pending</label><button type="reset">Reset filters</button></div></div></form>'
        f'<div class="weibo-result-line"><p id="weibo-result-count" class="weibo-result-count" role="status" aria-live="polite">'
        f'{len(accounts)} channels across {len(groups)} publisher / brand groups</p>'
        '<a href="downloads/weibo-accounts.csv" download>Download all accounts</a></div>'
        '<div class="weibo-layout">'
        '<div class="weibo-results"><div class="weibo-map" id="weibo-map">' + "".join(cards)
        + '<p id="weibo-empty" hidden>No matching channels. Try another name or reset the filters.</p></div>'
        '<nav class="weibo-pagination" id="weibo-pagination" aria-label="Publisher result pages" hidden>'
        '<button type="button" id="weibo-previous">Previous</button>'
        '<span id="weibo-page-label" role="status" aria-live="polite"></span>'
        '<button type="button" id="weibo-next">Next</button></nav></div>'
        '<div class="weibo-inspector" aria-label="Publisher and account evidence"><div id="weibo-detail-list">'
        + "".join(details) + '</div></div></div></div></section>'
        + channel_composition(summary)
        + '<details class="weibo-cohort"><summary>Research limitations &amp; selected-domain context</summary>'
        + cohort_text
        + '<p>These are documented associations, not a complete inventory or a current ownership/licensing audit. '
        'Unknown outlets are not verified absences. The named publishers lead this editorial selection; '
        'the remaining groups are alphabetical. Placement is not an activity or popularity ranking.</p>'
        '<p>Mixed evidence means a publisher has both profile-evidence and historical-only channels. '
        'Profile evidence does not mean currently posting; historical-only does not mean deleted. '
        'Licensed Chinese editions, regional distributors and U.S.-based Chinese-language media are distinguished '
        'in each channel’s publication scope. Publisher/brand groups are not independent U.S. newsrooms.</p>'
        + cohort_coverage + '</details>'
        '<details class="weibo-methods"><summary>Methodology &amp; complete downloads</summary>'
        + resolution + audit_text
        + '<p><a href="downloads/weibo-accounts.csv" download>Complete account metadata and evidence · CSV</a> · '
        '<a href="downloads/weibo-summary.json" download>Complete snapshot and provenance · JSON</a></p>'
        '<p>The private post corpus is unevenly recovered and strongly weighted toward recent collection. '
        'It cannot establish comparable historical posting rates. This is not a census of active accounts. '
        'Recovery data remain available for audit, but are not plotted as an activity trend here.</p>'
        f'<p>{archive_links}</p>'
        '<p><a href="assets/weibo-logos/credits.json">Publisher-mark sources and credits</a>. '
        'Marks identify publishers; they do not imply endorsement or current account activity.</p>'
        + '</details>' + recovery + '</main></div>'
        f'<script id="weibo-explorer-data" type="application/json">{payload}</script>'
        '<script src="assets/weibo-explorer.js" defer></script></body></html>'
    )
