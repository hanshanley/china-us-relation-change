"""A non-temporal view of documented publisher/account associations."""

import html
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from .model import json_text
from .weibo_analysis import AUDIT_LABELS


EVIDENCE_LABELS = {
    "current_evidence": "Current profile evidence",
    "historical": "Historical evidence only",
    "unknown": "Evidence period unknown",
}


def category_label(category):
    return {
        "us_chinese_language": "U.S. Chinese-language media",
        "us_chinese_community_media": "U.S. Chinese community media",
        "us_based_international_broadcaster": "U.S.-based international broadcasting",
        "press_release_service": "Press-release services",
    }.get(category, category.replace("_", " ").title())


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
    ordered = sorted(groups.values(), key=lambda rows: (rows[0]["outlet_name"].casefold(), rows[0]["outlet_id"]))
    states = Counter(a["existence"] for a in accounts)
    categories = sorted({a.get("category", "not_recorded") for a in accounts}, key=category_label)
    cards, details, model = [], [], []
    for group in ordered:
        first = group[0]
        dots = []
        for account in sorted(group, key=lambda a: (a.get("display_name", a["account_id"]).casefold(), a["account_id"])):
            identifier = account["account_id"]
            state = account["existence"]
            title = account.get("display_name", account["outlet_name"])
            label = EVIDENCE_LABELS[state]
            audit = account.get("primary_audit_status")
            needs_review = audit != "numeric_binding_rechecked"
            model.append({
                "id": identifier, "outlet": account["outlet_id"],
                "category": account.get("category", "not_recorded"), "state": state,
                "needs_review": needs_review,
                "search": " ".join(str(account.get(k) or "") for k in
                                   ("outlet_name", "display_name", "handle", "uid", "account_id")),
            })
            dots.append(
                f'<a class="weibo-dot {esc(state)}" href="#weibo-account-{esc(identifier)}" '
                f'data-account-id="{esc(identifier)}" aria-label="{esc(first["outlet_name"])}: '
                f'{esc(title)} — {esc(label)}" title="{esc(title)} — {esc(label)}">'
                '<span aria-hidden="true"></span></a>'
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
            details.append(
                f'<article class="weibo-channel-detail" id="weibo-account-{esc(identifier)}" '
                f'data-account-id="{esc(identifier)}">'
                f'<p class="weibo-category">{esc(category_label(account.get("category", "not_recorded")))}</p>'
                f'<h3 tabindex="-1">{esc(account["outlet_name"])}</h3>'
                f'<p class="weibo-channel-name">{esc(title)}</p>'
                f'<p class="weibo-evidence-label {esc(state)}">{esc(label)}</p>'
                f'<p class="weibo-uid">{esc(uid)}</p>'
                f'<p>{link(account["profile_url"], "Registered profile ↗")}</p>'
                f'<p class="weibo-relationship">{esc(account["relationship"])}</p>'
                '<details><summary>Operator & publication scope</summary>'
                f'<p><strong>Operator:</strong> {esc(account.get("operator", "Not recorded"))}</p>'
                f'<p>{esc(account.get("us_basis", "U.S.-inclusion basis not recorded in this legacy snapshot."))}</p>'
                f'<p>{esc(account.get("notes", ""))}</p>'
                + (f'<p>Exclusive attribution end: {esc(account["attribution_end"])}. Later posts are not '
                   'assigned to this publisher identity.</p>' if account.get("attribution_end") else "")
                + '</details>'
                f'<details><summary>Primary source evidence ({len(account.get("evidence", []))})</summary>'
                f'<ol class="weibo-sources">{sources}</ol>'
                + ('' if sources else '<p>No serialized source evidence is available in this legacy snapshot.</p>')
                + '</details>'
                f'<details class="weibo-identity-check"><summary>{esc(audit_label)}</summary>'
                f'<p>{esc(audit_note)}</p>'
                + (f'<p>{link(audit_source, "Recheck source ↗")}</p>' if audit_source else "")
                + '</details></article>'
            )
        cards.append(
            f'<article class="weibo-brand" data-outlet-id="{esc(first["outlet_id"])}">'
            f'<h3>{esc(first["outlet_name"])}</h3>'
            f'<p>{esc(category_label(first.get("category", "not_recorded")))}</p>'
            f'<div class="weibo-dots" role="group" aria-label="{esc(first["outlet_name"])} channels">'
            + "".join(dots) + '</div></article>'
        )
    options = "".join(f'<option value="{esc(c)}">{esc(category_label(c))}</option>' for c in categories)
    legend = "".join(
        f'<span><i class="{esc(state)}" aria-hidden="true"></i>{esc(label)} '
        f'<b data-state-count="{esc(state)}">{states[state]}</b></span>'
        for state, label in EVIDENCE_LABELS.items() if states[state]
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
        f'<p>The selected cohort uses {esc(cohort["ranking_basis"])}. '
        'The account map also includes separately documented supplemental media; it is not a census of U.S. outlets.</p>'
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
    payload = json_text({"accounts": model}).replace("<", "\\u003c")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>U.S. media on Weibo</title><link rel="stylesheet" href="assets/style.css">'
        '<link rel="stylesheet" href="assets/weibo-explorer.css"></head>'
        '<body><div class="page"><header><p><a href="index.html">Exchange dashboard</a></p>'
        '<h1>U.S. media on Weibo</h1><p class="lead">Explore documented outlets and channels, '
        'not a recovery-biased posting history.</p></header><main>'
        '<section class="weibo-explorer" id="weibo-explorer" aria-label="Publisher and account evidence explorer">'
        '<div class="weibo-overview">'
        f'<p><strong>{len(accounts):,}</strong><span>documented channels</span></p>'
        f'<p><strong>{len(groups):,}</strong><span>publisher / brand groups</span></p>'
        '</div><p class="weibo-intro">Equal-sized dots are channels, grouped by publisher. '
        'Select one for its identity and sources. Alphabetical—not an activity ranking.</p>'
        '<form class="weibo-filters" id="weibo-filters" hidden>'
        '<label>Find an outlet or channel<input id="weibo-search" name="q" type="search" '
        'placeholder="Name, Chinese name, handle or UID" autocomplete="off"></label>'
        f'<label>Media type<select id="weibo-category" name="category"><option value="">All media types</option>{options}</select></label>'
        '<label>Identity evidence<select id="weibo-evidence" name="evidence"><option value="">All evidence periods</option>'
        '<option value="current_evidence">Current profile evidence</option>'
        '<option value="historical">Historical evidence only</option>'
        '<option value="unknown">Evidence period unknown</option></select></label>'
        '<div class="weibo-filter-actions"><label><input type="checkbox" id="weibo-followup" name="followup">'
        'UID checks needing follow-up</label><button type="reset">Reset filters</button></div></form>'
        f'<div class="weibo-legend">{legend}</div>'
        f'<p id="weibo-result-count" class="weibo-result-count" role="status" aria-live="polite">'
        f'{len(accounts)} channels across {len(groups)} publisher / brand groups</p>'
        '<div class="weibo-layout"><aside class="weibo-inspector" aria-label="Selected channel">'
        '<p class="weibo-inspector-label">Channel details</p>'
        '<button type="button" id="weibo-back" class="weibo-back" hidden>Back to account map</button>'
        '<div id="weibo-detail-list">'
        + "".join(details) + '</div><p id="weibo-empty-detail" hidden>No channel matches these filters.</p></aside>'
        '<div class="weibo-map" id="weibo-map">' + "".join(cards)
        + '<p id="weibo-empty" hidden>No matching channels. Try another name or reset the filters.</p></div></div>'
        '<section class="weibo-cohort"><h2>What this inventory can—and cannot—show</h2>'
        + cohort_text
        + '<p>These are documented associations, not a complete inventory or a current ownership/licensing audit. '
        'Unknown outlets are not verified absences. No recovered-post counts, dates or collection volumes '
        'determine the dots, their size or their order.</p>'
        '<p>Current profile evidence does not mean currently posting; historical-only does not mean deleted. '
        'Licensed Chinese editions, regional distributors and U.S.-based Chinese-language media are distinguished '
        'in each channel’s publication scope. Publisher/brand groups are not independent U.S. newsrooms.</p></section>'
        '<details class="weibo-methods"><summary>Identity checks, complete data & recovery limits</summary>'
        + resolution + audit_text
        + '<p><a href="downloads/weibo-accounts.csv" download>Complete account metadata and evidence · CSV</a> · '
        '<a href="downloads/weibo-summary.json" download>Complete snapshot and provenance · JSON</a></p>'
        '<p>The private post corpus is unevenly recovered and strongly weighted toward recent collection. '
        'It cannot establish comparable historical posting rates. This is not a census of active accounts. '
        'Recovery data remain available for audit, but are not plotted as an activity trend here.</p>'
        f'<p>{archive_links}</p>'
        + '</details></section></main></div>'
        f'<script id="weibo-explorer-data" type="application/json">{payload}</script>'
        '<script src="assets/weibo-explorer.js" defer></script></body></html>'
    )
