from pathlib import Path

from .export import coverage
from .storage import now


def cell(value):
    return str(value if value is not None else "unknown").replace("|", "\\|").replace("\n", " ")


def report(db, path):
    outlets = db.execute("SELECT * FROM outlets ORDER BY name").fetchall()
    accounts = db.execute("""
        SELECT a.*,o.name AS outlet FROM accounts a
        JOIN outlets o ON o.id=a.outlet_id ORDER BY o.name,a.id
    """).fetchall()
    reviewed = sum(row["research_status"] == "reviewed" for row in outlets)
    account_coverage = {row["account_id"]: row for row in coverage(db)}
    confirmed = [a for a in accounts if a["officialness"] == "confirmed"]
    recovered_accounts = sum(account_coverage[a["id"]]["recovered_posts"] > 0 for a in confirmed)
    unattempted = sum(account_coverage[a["id"]]["latest_run_status"] is None for a in confirmed)
    lines = [
        "# U.S. news-media accounts on Sina Weibo",
        "",
        f"Generated: {now()}. Registry claims retain their own observation dates.",
        "",
        f"Candidate roster: **{len(outlets)} outlets; {reviewed} reviewed; "
        f"{len(outlets) - reviewed} pending**. This is an expandable research roster, not a census.",
        "Officialness, historical existence, operator relationship, and current access are distinct.",
        "Account totals are not independent outlet totals: one publisher can operate multiple "
        "channels. Press-release services and independent regional distributors are explicitly "
        "labeled; they are not presented as independent U.S. editorial newsrooms.",
        "A visitor/login gate does not establish that an account was suspended or deleted.",
        "",
        f"**Posts recovered for {recovered_accounts} of {len(confirmed)} confirmed accounts.** "
        f"{unattempted} confirmed accounts have no recorded collection attempt. "
        "Zero recovered posts after an attempt can reflect access, attribution or coverage limits, "
        "not zero account output.",
        "There is no verified-negative outlet list: missing publisher links and access failures "
        "remain unknowns. The complete ranked and supplemental account-status ledger is linked "
        "in the [collection follow-up](collection_followup.md).",
        "",
        "## Confirmed official accounts",
        "",
        "| Outlet / edition | Account | UID | Relationship | Existence evidence | Direct access | Attribution end | Recovered posts | Collection |",
        "|---|---|---|---|---|---|---|---:|---|",
    ]
    for account in accounts:
        if account["officialness"] == "confirmed":
            lines.append("| " + " | ".join(cell(value) for value in (
                account["outlet"], f"[{account['display_name']}]({account['profile_url']})",
                account["uid"], account["relationship"], account["existence"],
                account["accessibility"], account["attribution_end"] or "not established",
                account_coverage[account["id"]]["recovered_posts"],
                account_coverage[account["id"]]["latest_run_status"] or "not attempted",
            )) + " |")
    lines += ["", "### Evidence and operator notes", ""]
    for account in accounts:
        lines += [f"**{cell(account['outlet'])} / {cell(account['display_name'])}** "
                  f"({account['officialness']}). Operator: {cell(account['operator'])}. "
                  f"{cell(account['notes'])}", ""]
        evidence = db.execute("SELECT * FROM evidence WHERE account_id=? ORDER BY id",
                              (account["id"],)).fetchall()
        for item in evidence:
            lines.append(f"- [{item['id']}]({item['source_url']}) [{item['source_type']}; "
                         f"supports {item['supports']}; observed {item['observed_at']}; "
                         f"claim date {cell(item['claim_date'])}]: {cell(item['justification'])}")
        lines.append("")
    lines += ["## Reviewed and pending outlets", "",
              "| Outlet | Research status | Account result / limits |",
              "|---|---|---|"]
    for outlet in outlets:
        found = [a for a in accounts if a["outlet_id"] == outlet["id"]]
        result = "; ".join(f"{a['display_name']}: {a['officialness']}" for a in found)
        if not result:
            result = ("No resolved account identity in registry; see source notes, not a negative finding"
                      if outlet["research_status"] == "reviewed" else "Not yet reviewed")
        lines.append(f"| [{cell(outlet['name'])}]({outlet['source_url']}) | "
                     f"{outlet['research_status']} | {cell(result)}. {cell(outlet['notes'])} |")
    lines += ["", "## Recovered corpus and coverage", "",
              "Requested publication interval: January 1, 2020 through October 21, 2026 "
              "(Asia/Shanghai). Per-run bounds in coverage.csv are authoritative for custom runs.",
              "All counts below are recovered/observed posts, not total output. No zero-activity "
              "claim is made for missing months. Historical recovery remains partial.",
              "",
              "| Account | Recovered posts | Earliest observed UTC | Latest observed UTC | Latest run | Gap / limitation |",
              "|---|---|---|---|---|---|"]
    for row in account_coverage.values():
        lines.append("| " + " | ".join(cell(value) for value in (
            row["account_id"], row["recovered_posts"], row["earliest_observed_post"],
            row["latest_observed_post"],
            f"{row['latest_run_source']}: {row['latest_run_status']}" if row["latest_run_status"] else "not attempted",
            row["latest_error"] or row["limitations"] or "Not collected",
        )) + " |")
    lines += ["", "### Text completeness", "",
              "| Account | Text status | Recovered posts |",
              "|---|---|---|"]
    for row in db.execute("""
        SELECT account_id,text_status,COUNT(*) AS count FROM posts
        GROUP BY account_id,text_status ORDER BY account_id,text_status
    """):
        lines.append(f"| {row['account_id']} | {row['text_status']} | {row['count']} |")
    lines += ["", "## Observed monthly activity", "",
              "Counts use publication months in Asia/Shanghai. Unknown post kinds are retained, "
              "not silently classified as original posts.", "",
              "| Account | Month | Kind | Recovered posts |",
              "|---|---|---|---|"]
    for row in db.execute("""
        SELECT account_id, strftime('%Y-%m',published_utc,'+8 hours') AS month,
               kind, COUNT(*) AS count FROM posts GROUP BY account_id,month,kind
        ORDER BY account_id,month,kind
    """):
        lines.append(f"| {row['account_id']} | {row['month']} | {row['kind']} | {row['count']} |")
    lines += ["", "## Engagement observations", "",
              "Grouped by source and observation day, not by publication date. "
              "Each group uses the latest snapshot per post on that day. Counts may be cached; "
              "these are not historic engagement trajectories or cross-account performance rankings. "
              "Missing values are excluded, not converted to zero.", "",
              "| Account | Source | Observation day UTC | Posts | Mean likes (n) | Mean comments (n) | Mean reposts (n) |",
              "|---|---|---|---|---|---|---|"]
    for row in db.execute("""
        WITH ranked AS (
          SELECT o.*,p.account_id,
            ROW_NUMBER() OVER (
              PARTITION BY o.post_id,o.source_type,substr(o.observed_at,1,10)
              ORDER BY o.observed_at DESC,o.source_url
            ) AS rank
          FROM observations o JOIN posts p ON p.id=o.post_id
        )
        SELECT account_id,source_type,substr(observed_at,1,10) AS day,COUNT(*) AS count,
          AVG(likes) AS likes,COUNT(likes) AS likes_n,
          AVG(comments) AS comments,COUNT(comments) AS comments_n,
          AVG(reposts) AS reposts,COUNT(reposts) AS reposts_n
        FROM ranked WHERE rank=1 GROUP BY account_id,source_type,day
        ORDER BY account_id,source_type,day
    """):
        metrics = []
        for name in ("likes", "comments", "reposts"):
            metrics.append(f"{row[name]:.2f} ({row[name + '_n']})" if row[name] is not None else "unknown (0)")
        lines.append("| " + " | ".join([cell(row[key]) for key in (
            "account_id", "source_type", "day", "count")] + metrics) + " |")
    lines += ["", "## Method and remaining gaps", "",
              "Discovery prioritizes publisher-owned outbound links, explicit platform certification "
              "naming the outlet, and first-hand publisher confirmation. Search results and matching "
              "logos alone do not confirm officialness.",
              "",
              "Collection uses the pilot-verified public Sina syndication feed, linked detail pages, "
              "and selected public Wayback profile snapshots, respecting robots rules and access failures. "
              "No Weibo gates are bypassed. "
              "Detail text is labeled source_full: the complete accessible syndicated body, not a "
              "guarantee of fidelity to an inaccessible original. Feed previews remain truncated "
              "in provenance. Reposts cannot reliably be identified on this source.",
              "",
              "An attribution end excludes posts on or after that Asia/Shanghai date across live, "
              "archive and import routes, even when a UID retains the same name. These are "
              "evidence-backed collection cutoffs, not necessarily exact contract-termination dates; "
              "see each account's evidence and notes. An unestablished cutoff does not prove "
              "a continuing U.S. license.",
              "",
              "No feed-history pagination has been demonstrated. Archive index hits alone are not "
              "recovered posts. Authorized/manual/archive JSONL imports can extend coverage, retaining "
              "publication versus capture dates. Resolve unknown UIDs before attempting account-specific "
              "syndication retrieval. No claim is made that any outlet lacking evidence never used Weibo.",
              "",
              "Corpus text and raw responses are local-only by default. Public exports omit posts "
              "without explicit redistribution permission and list omissions. No third-party post "
              "text is reproduced in this report. See [top-1,000 U.S. website screening](top1000_us_screening.md) "
              "for the separate ranked discovery roster, [collection follow-up](collection_followup.md) "
              "for explicit account/post assessments and the scraper evaluation, "
              "[further discovery](discovery_round2.md) for subsequent publisher-link research, "
              "[continued discovery](discovery_iteration3.md) for additional identities and licensing "
              "cutoffs, [further publisher traces](discovery_iteration4.md) for subsequent ranked, "
              "technology and historical-account checks, [continued newsroom discovery](discovery_iteration5.md) "
              "for NPR and archive-bound detail recovery, [publisher account clusters](discovery_iteration6.md) "
              "for release-distribution channels and unresolved historical locators, "
              "[publication identity follow-up](discovery_iteration7.md) for Knowledge at Wharton's "
              "resolved account and Popular Science's current identity/cutoff reassessment, "
              "[ranked-publisher follow-up](discovery_iteration8.md) for five further source-cohort "
              "reviews and the Men's Health Chinese edition, "
              "[local-publisher follow-up](discovery_iteration9.md) for Chinese Radio Seattle's "
              "historical account and five further ranked reviews, "
              "[music-publication follow-up](discovery_iteration10.md) for Rolling Stone's "
              "Chinese edition, its independently documented license and subsequent ranked reviews, "
              "[trade-edition and archive follow-up](discovery_iteration11.md) for Variety's "
              "Chinese-edition identity and independently dated publisher-root checks, "
              "[identity-screening follow-up](discovery_iteration12.md) for nine further reviews "
              "and explicitly excluded founder/unbound blogger and long-form author candidates, "
              "[historical SELF follow-up](discovery_iteration13.md) for two newly resolved "
              "publisher-designated channels and the renamed-magazine attribution boundary, "
              "[Travel + Leisure follow-up](discovery_iteration14.md) for its publisher-linked "
              "Chinese edition, fixed-window recovery and a separately held copyright partner, "
              "[China Press Bay Area follow-up](discovery_iteration15.md) for a second U.S. "
              "newspaper channel without inferring Seattle identity from a shared widget, "
              "[Phoenix Americas follow-up](discovery_iteration16.md) for a specifically labeled "
              "U.S.-based regional broadcaster, independently recovered posts and further publisher reviews, "
              "[Las Vegas newspaper follow-up](discovery_iteration17.md) for a historically verified "
              "account, explicit recovery limits and canonical-domain matching without changing cohort membership, "
              "[Chron and cycling-identity follow-up](discovery_iteration18.md) for five further reviews "
              "and a real Chinese account held outside U.S. totals without a verified brand relationship, "
              "[Radio-programme and publisher follow-up](discovery_iteration19.md) for five more ranked reviews "
              "and a station programme distinguished from an organizational Sina account, "
              "[VISIONAIRE and regional-publisher follow-up](discovery_iteration20.md) for a publisher-documented "
              "Chinese-edition identity, fixed-window recovery and five further ranked reviews, "
              "[Artforum and ARTnews follow-up](discovery_iteration21.md) for separately verified art-media "
              "identities, printed-license evidence and early-window archive recovery, "
              "and [access pilot](access_pilot.md) for source-level "
              "access checks and archive gaps.", ""]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return {"report": str(target), "outlets": len(outlets), "accounts": len(accounts)}
