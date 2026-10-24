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
    return (
        primary + '<details class="weibo-recovery" id="weibo-recovery"><summary>Recovered posts &amp; limitations</summary>'
        '<p class="recovery-intro">These counts describe the recovered sample, not all Weibo posts or the selected-domain cohort.</p>'
        + channels + texts
        + '<div class="coverage-unmeasured">'
        '<p><strong>The share of historical posts missing cannot be estimated.</strong></p>'
        '<p>We do not know the total number published. There is no defensible denominator for a “percent of all posts recovered.” '
        'Uneven recovery is why no posting-history or popularity trend is shown.</p></div></details>'
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
            details.append(
                f'<article class="weibo-channel-detail" id="weibo-account-{esc(identifier)}" '
                f'data-account-id="{esc(identifier)}">'
                f'<p class="weibo-category">{esc(category_label(account.get("category", "not_recorded")))}</p>'
                f'<h3 tabindex="-1">{esc(account["outlet_name"])}</h3>'
                f'<p class="weibo-channel-name">{esc(title)}</p>'
                f'<p class="weibo-evidence-label {esc(state)}">{esc(label)}</p>'
                f'<p class="weibo-profile">{link(account["profile_url"], "Weibo profile ↗")} '
                f'<span class="weibo-uid">{esc(uid)}</span></p>'
                f'<p class="weibo-relationship">{esc(account["relationship"])}</p>'
                + (f'<p class="weibo-period">Publisher association recorded only before '
                   f'{esc(account["attribution_end"])}. Later posts are not attributed to this publisher.</p>'
                   if account.get("attribution_end") else "")
                + '<details><summary>Operator & publication scope</summary>'
                f'<p><strong>Operator:</strong> {esc(account.get("operator", "Not recorded"))}</p>'
                f'<p>{esc(account.get("us_basis", "U.S.-inclusion basis not recorded in this legacy snapshot."))}</p>'
                f'<p>{esc(account.get("notes", ""))}</p>'
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
    payload = json_text({"accounts": model, "coverage": coverage_model(summary)}).replace("<", "\\u003c")
    observed = max((e["observed_at"][:10] for a in accounts for e in a.get("evidence", [])), default=None)
    dated = f'Evidence recorded through {observed}. ' if observed else ""
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
        '</div><p class="weibo-intro">Includes publisher-linked editions and U.S.-based Chinese-language media. '
        'Select a channel to inspect its identity and sources.</p>'
        f'<p class="weibo-snapshot">{esc(dated)}Profile evidence does not establish current posting or U.S. editorial control.</p>'
        '<form class="weibo-filters" id="weibo-filters" hidden>'
        '<label>Find an outlet or channel<input id="weibo-search" name="q" type="search" '
        'placeholder="Name or Weibo ID" autocomplete="off"></label>'
        '<button type="button" id="weibo-filter-toggle" class="weibo-filter-toggle" '
        'aria-expanded="false" aria-controls="weibo-filter-options" hidden>Filters</button>'
        '<div id="weibo-filter-options" class="weibo-filter-options">'
        f'<label>Media type<select id="weibo-category" name="category"><option value="">All media types</option>{options}</select></label>'
        '<label>Identity evidence<select id="weibo-evidence" name="evidence"><option value="">All evidence periods</option>'
        '<option value="current_evidence">Current profile evidence</option>'
        '<option value="historical">Historical evidence only</option>'
        '<option value="unknown">Evidence period unknown</option></select></label>'
        '<div class="weibo-filter-actions"><label><input type="checkbox" id="weibo-followup" name="followup">'
        'Evidence checks pending</label><button type="reset">Reset filters</button></div></div></form>'
        f'<div class="weibo-legend">{legend}</div>'
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
        '<aside class="weibo-inspector" aria-label="Selected channel">'
        '<p class="weibo-inspector-label">Channel details</p>'
        '<button type="button" id="weibo-back" class="weibo-back" hidden>Back to accounts</button>'
        '<div id="weibo-detail-list">'
        + "".join(details) + '</div><p id="weibo-empty-detail" hidden>No channel matches these filters.</p></aside></div>'
        '<details class="weibo-cohort"><summary>What these accounts represent</summary>'
        + cohort_text
        + '<p>These are documented associations, not a complete inventory or a current ownership/licensing audit. '
        'Unknown outlets are not verified absences. Accounts are listed alphabetically; recovered-post '
        'counts and collection volumes do not determine their order.</p>'
        '<p>Current profile evidence does not mean currently posting; historical-only does not mean deleted. '
        'Licensed Chinese editions, regional distributors and U.S.-based Chinese-language media are distinguished '
        'in each channel’s publication scope. Publisher/brand groups are not independent U.S. newsrooms.</p></details>'
        '<details class="weibo-methods"><summary>Identity checks, complete data & recovery limits</summary>'
        + resolution + audit_text
        + '<p><a href="downloads/weibo-accounts.csv" download>Complete account metadata and evidence · CSV</a> · '
        '<a href="downloads/weibo-summary.json" download>Complete snapshot and provenance · JSON</a></p>'
        '<p>The private post corpus is unevenly recovered and strongly weighted toward recent collection. '
        'It cannot establish comparable historical posting rates. This is not a census of active accounts. '
        'Recovery data remain available for audit, but are not plotted as an activity trend here.</p>'
        f'<p>{archive_links}</p>'
        + '</details></div></section>' + coverage_markup(summary) + '</main></div>'
        f'<script id="weibo-explorer-data" type="application/json">{payload}</script>'
        '<script src="assets/weibo-explorer.js" defer></script></body></html>'
    )
