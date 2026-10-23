# Account verification and post-collection follow-up

Snapshot updated October 23, 2026. The [generated inventory](weibo_media_inventory.md)
contains the authoritative per-account post totals. A verified identity is not
a guarantee of current ownership, current posting, or complete historical recovery.

**Live-update distinction:** the October 21, 2026 collection cutoff below is
the preserved historical baseline, not a permanent live-data cutoff. Automatic
private refreshes advance the activity dataset through the last completed
Asia/Shanghai day. The generated inventory, frozen aggregate JSON and refresh
status report the latest live totals; historical checkpoint counts below are
not rewritten as though they were the latest collection.

## Published snapshot: October 23, 2026

The [primary-source recheck](weibo_primary_source_audit.md) now reports
**85 numeric bindings rechecked, one historical numeric recheck pending,
and one historical vanity-only channel with UID unresolved**. All 6,521
canonical texts were checked against primary-source captures; 21 canonical
texts were corrected for selection/extraction defects while preserving all
prior source variants. This is source-level validation, not just matching totals.
WSJ Chinese's numeric binding was independently rechecked in a saved 2017
first-party Weibo original-author card; NYT Chinese's numeric recheck remains
pending. The historical WSJ evidence did not add out-of-window posts.

There are **87 documented current/historical channels across 62 publisher/brand
groups: 86 resolved numeric UIDs and one historical vanity-only URL**. VOA's
publisher-designated `legalwindow` channel remains UID-unresolved; the numeric
candidate has not been assigned and its posts have not been imported.
These are not 87 independent U.S. newspapers or uniformly U.S.-operated newsrooms.
Current-profile evidence for 62 channels and historical-only evidence for 25
do not establish current activity or continuing licensing.

The selected **1,000 SCImago U.S.-classified domains** are ranked by digital
reputation, not traffic; their present ownership/nationality was not independently
audited. **Five have current-profile evidence, seven historical-only evidence,
988 remain unknown, and zero are verified negatives.** All underwent homepage
screening, but only 221 have recorded manual review.

The [latest scheduled pass](discovery_iteration45.md) adds five reviews with
eight complete primary HTML responses and one genuine cached publisher PDF.
Actual named Contact bodies distinguish Auburn, New York's Citizen from
Alabama's Opelika-Auburn News and identify Dothan and Butte publication context.
Asbury Park Press's recorded newspaper HTTP403 was not retried; the cached
directory supplies New Jersey publication-name scope, not current app.com
control or a Sina identity. Dothan's machine-learning article coverage was not
misread as a publisher-wide source-use reservation. All nine existing
no-further-publisher-body restrictions remain unchanged.
The live 6,570-post corpus, original archived baseline and all rolling data
remain unchanged by discovery.
Discovery is not exhausted: 779 selected domains still lack a recorded
manual review. A bounded recurring prompt is active every 30 minutes; later
passes must advance the frontier rather than repeatedly probing exhausted leads.

**Unattended collection is currently blocked:** the first OS-scheduled
invocation on October 23 failed before Python initialized because the
Documents-hosted virtual environment was not accessible to that process.
No new scheduled collection occurred. The earlier bounded manual success and
successful GitHub aggregate rebuild do not establish unattended collection.
The [operations note](../docs/EXCHANGE.md#automatic-private-weibo-refresh)
records the actual failure and user-approved-access requirement. Published
refresh health now records the startup block and zero attempted feeds, retaining
the last successful collection time, cutoff, corpus and all rolling data.

**6,521 posts were partially recovered from 68 channels**: 5,760 available source
bodies and 761 truncated previews. These are not complete timelines or independently
verified complete original posts; images, video and transcripts were not recovered.
The public page and complete account downloads expose UIDs, resolution status,
operator relationships, U.S.-inclusion bases and all curated identity evidence.
The earlier checkpoints below are retained as historical progress notes, not
current totals.

## Earlier collection checkpoint

At the preceding checkpoint, the registry had **12 confirmed account identities across 11 outlets**.
All 12 have a recorded collection attempt. **1,135 distinct in-window posts
were recovered from 10 accounts**, comprising 822 accessible source bodies
and 313 explicitly truncated previews. NYT Chinese and WSJ Chinese remain
the two confirmed historical accounts with no recovered in-window posts.
No confirmed account is left unattempted.
See [further account discovery](discovery_round2.md) and the generated inventory
for subsequent additions and current totals; the numbers in this section
describe the earlier published checkpoint.

Of the ranked 1,000 U.S. websites, five have a confirmed account identity in
this research: Forbes, Fortune and Bloomberg have current-profile evidence;
NYT and WSJ have historical-only evidence. **The other 995 remain unknown,
not verified negatives.** Other confirmed specialist and U.S. Chinese-language
outlets are explicitly supplemental to this particular ranking.

## Explicit account decisions, not missing-link guesses

The complete assessments are:

- `data/discovery/us_top1000_accounts.csv` and `.jsonl`: exactly the 1,000
  U.S.-classified ranked websites, in source order.
- `data/discovery/outlet_account_assessments.csv` and `.jsonl`: the same 1,000
  plus separately labeled manual-roster outlets outside that ranking.

Each row exposes `account_status`, `has_ever_official_weibo`,
`has_current_profile_evidence`, account identifiers, identity evidence, operator
relationships, `has_collected_posts`, post counts, and account-specific
collection status/errors. JSONL preserves nested source checks and evidence.
There are **no verified-negative account findings**. An unknown is JSON `null`
in the yes/no fields, not `false`; historical officialness is `true` for
`has_ever_official_weibo` but does not establish a current account.
Current-profile evidence means a currently observable publisher/platform
identity surface; it does not independently establish direct Weibo availability,
recent posting, or present-day legal operation.
`has_collected_posts=false` means our corpus has no posts for that row, not
that its publisher never posted.

Known verified accounts override a missing homepage link. For example, WSJ
and NYT retain their historical account evidence even though their current
publisher homepages do not supply usable account links. Supplemental Chinese
editions are not silently assigned a place in the ranking.

## Checks beyond publisher homepages

All 1,000 ranked domains have a second-stage assessment record. The 323
blocked/inconclusive first-stage checks were retained, not bypassed. For the
other domains, the second stage checked publisher robots policies, refreshed
the homepage, and followed up to two actually linked institutional about,
contact, help, or social-information pages on the same origin.

The pass attempted 1,167 pages, of which 1,155 returned readable HTML.
It produced no additional institutional Weibo profile-link candidates.
This remains a bounded discovery pass, **not proof that all other websites
lack Weibo accounts**. Publisher information pages can omit accounts, and
historical/Chinese-edition accounts often require separate archival research.

The local per-domain page audit is
`data/local/discovery/secondary-pages/publisher_pages.jsonl`; its structured
outcomes are included in the complete public assessment exports.
Share buttons, article links, and incidental mentions are not account evidence.
Clickable HTML image-map areas and legacy enterprise profile links are
recognized by the updated parser.

## Additional publisher and account discoveries

| Outlet / account | Direct identity chain | Collection route |
|---|---|---|
| Bloomberg China, `chinabloomberg`, UID `5076455752` | [Publisher about page](https://www.bloombergchina.com/about-us/) links to the handle; [2022 archived profile](https://web.archive.org/web/20220629133800id_/https://www.weibo.com/chinabloomberg) binds UID; [current public profile](https://www.sina.cn/media/5076455752) explicitly names the official account | Public syndicated feed plus 14 archived June 2022 records |
| The China Press, `uschinapress`, UID `1823184085` | [2020 publisher homepage](https://web.archive.org/web/20200101140938id_/http://www.uschinapress.com/) links to the handle; [2020 profile](https://web.archive.org/web/20200215021312id_/https://www.weibo.com/uschinapress) binds UID | Public feed, now named 侨报美西, plus 15 records each from 2020, 2021, 2022 captures |
| World Journal North America, `worldjournalnews`, UID `3229879502` | [Publisher's dedicated social page](https://web.archive.org/web/20200114054006id_/https://www.worldjournal.com/page-weibo/) links through an image map; [2024 archived profile](https://web.archive.org/web/20240711045444id_/https://www.weibo.com/worldjournalnews) binds UID; [current profile](https://www.sina.cn/media/3229879502) explicitly certifies the account | Public feed plus 2024/2025 archive snapshots |
| World Journal Los Angeles, `laworldjournal`, UID `2514536744` | Same [publisher social page](https://web.archive.org/web/20200114054006id_/https://www.worldjournal.com/page-weibo/) separately links the regional account; [2021 archived profile](https://web.archive.org/web/20211209084124id_/https://www.weibo.com/laworldjournal) binds UID; [current profile](https://www.sina.cn/media/2514536744) explicitly certifies the regional account | Public feed plus archived May 2020 posts |

World Journal's two accounts are distinct regional accounts of one outlet,
not two additional publishers. China Press's historical publisher binding is
confirmed; the current profile's regional rename is recorded without inventing
a verified current legal operator. Bloomberg's account is not conflated with
separately licensed Bloomberg Businessweek editions.

Both World Journal North America snapshots expose the same 15 posts published
January-June 2024. Their distinct capture timestamps are retained, but posts
deduplicate by ID; a 2025 capture is not evidence of a 2025 publication.
The Los Angeles snapshot captured in December 2021 exposes May 2020 posts.

The three previously uncollected specialist accounts were also processed:
National Geographic, Scientific American / 环球科学, and MIT Technology Review
each yielded 100 public-feed entries. Unavailable detail pages retain explicitly
truncated previews; none is silently counted as complete original text.

## NYT and WSJ: actual archive investigation

Exact Wayback/CDX handle, enterprise-handle, and numeric-UID queries were run
with and without a successful-status filter. In-window index rows exist, but
the observed captures are redirects, redirect revisits, or an archived denial,
not usable account feeds.

| Account | In-window archive observations | Post outcome |
|---|---|---|
| WSJ Chinese | Exact handle rows in 2021, 2023, 2024, 2025, 2026 are redirects/revisits. Enterprise rows in 2021/2025 are redirects; numeric UID form returned no rows. The March 16, 2023 replay first exposed a visitor redirect in research; a later collector attempt returned HTTP 404. | No in-window feed text recovered |
| NYT Chinese | Exact handle rows in 2020-2026 are redirects/revisits, plus an archived 403 in November 2025. Enterprise/numeric forms returned no rows. The September 4, 2020 replay redirects to a different capture; collection refuses to misattribute its timestamp. | No in-window feed text recovered |

An alternative [Arquivo.pt version-history API](https://arquivo.pt/textsearch)
returned four WSJ rows, all original HTTP 302 responses, and no NYT rows for
the tested HTTP/HTTPS forms. A wrapper-level HTTP 200 is not an archived-origin
HTTP 200. Its [robots policy](https://arquivo.pt/robots.txt), checked before a
body follow-up, disallows `/wayback`, so no replay-body inspection or import
was attempted. These outcomes do not establish that either outlet had no
in-window posts or that every possible alias/archive has been exhausted.

## Evaluation of the suggested Xarrow scraper

Inspected [Xarrow/weibo-scraper](https://github.com/Xarrow/weibo-scraper),
pinned at commit `0a8cce7edfd797b106236186d64922732a5007db`
(commit date November 26, 2022). Its README describes unauthenticated
mobile-site scraping; its
[API implementation](https://github.com/Xarrow/weibo-scraper/blob/0a8cce7edfd797b106236186d64922732a5007db/weibo_base/weibo_api.py)
uses `https://m.weibo.cn/api/container/getIndex` for name/profile lookup and
paged timelines.

On October 21, 2026, [the mobile host's robots policy](https://m.weibo.cn/robots.txt)
returned HTTP 200. Its default `User-agent: *` group disallows `/`; the named
search-crawler exceptions do not apply to this research client. Consequently,
the identified API route was **not requested after this policy check** and
the package was not installed or executed. Earlier mobile probes had returned
HTTP 432. No identity spoofing, cookie borrowing, proxy rotation, or login-gate
bypass was used. The precise probe is saved locally as
`data/local/discovery/xarrow_api_probe.json`.

The repository demonstrates a possible historical interface, not working
present-day access or an entitlement to historical data. Its pagination loop
also repeats the same page indefinitely if the request returns `None`, and
its request helper supplies no default timeout. Those behaviors were not
adopted. Existing normalized JSONL imports remain available for properly
authorized external exports, including complete text and provenance.

## Reproduce the assessment

```sh
export PYTHONPATH=src
python3 -m weibo_media.assessment
python3 -m weibo_media.assessment --publish
python3 -m weibo_media export
python3 -m weibo_media report
```

The page pass resumes its local journal. Run final assessment/export/report
after collection stops so that per-account corpus counts agree. Full
recoverable post text remains local in `data/local/exports/posts.jsonl` and
`posts.csv`; no third-party post text is published to GitHub.
