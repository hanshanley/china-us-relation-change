# U.S. news media on Weibo

**Project checklist:** [`PUBLICATION-TODO.md`](PUBLICATION-TODO.md) tracks the
requested work, verified completions, remaining data gaps and blocked automation.
Read it before resuming work; a local implementation is not a verified deployment.

This repository also contains an independent **U.S. bilateral exchange
dashboard** for students, visitor trips, and trade with mainland China,
Hong Kong, Macau, and Taiwan. Open [`site/index.html`](site/index.html) locally;
see [exchange setup, definitions and operations](docs/EXCHANGE.md) and
[source contracts](docs/SOURCES.md). Hosting is not configured.

The [combined exchange charts](site/comparisons.html) compare mainland China,
Hong Kong and Macau only. The [Weibo research charts](site/weibo.html) separately
show timestamped aggregate snapshots, not total activity or popularity.
The private collector is configured to rebuild the graphs and complete
downloads, then commit and push them four times daily. Unattended attempts
are currently blocked by macOS file-access permissions; a successful
manual run does not establish that the scheduled job can run unattended.
See [automatic refresh](docs/EXCHANGE.md#automatic-private-weibo-refresh)
for the schedule and safeguards, and
[graph generation and limits](docs/EXCHANGE.md#weibo-research-graphs)
for the trailing-30-day measures and PNG/SVG exports. This updates the published
files; it does not add hosting or live-refresh an already-open browser tab.

The [Chinese-language learning section](site/language-learning.html) adds college
registrations and their language-study share, matched-institution comparisons,
AP exam indicators, immersion inventories and annual Chinese-language degree
awards. These are separate educational indicators, not a combined learner total.
AP global administration counts and historical U.S. public-school graduating
cohorts are explicitly separate. See [definitions and manual refresh](docs/EXCHANGE.md#chinese-language-learning).

The [business-presence section](site/business-presence.html) tracks **U.S. and
European businesses in China over time**, not U.S. businesses in Europe.
Annual U.S. affiliate history starts in 2000; European coverage includes
separately labelled EU memberships, the UK and Norway. Full yearly tables,
complete downloads and both chart backgrounds accompany the graphs. Sparse
U.S. parent-company benchmarks are secondary, not annual substitutes.
See [business definitions and refresh](docs/EXCHANGE.md#business-presence).

An evidence-backed account inventory and small, resumable post-recovery CLI.
The scope includes U.S. news brands, their explicitly labeled Chinese editions,
and U.S.-based Chinese-language outlets. It is **not an exhaustive census**.

Start with [the inventory](reports/weibo_media_inventory.md) and
[the access pilot](reports/access_pilot.md). Confirmed officialness is separate
from current account accessibility or observed posting activity. The reviewed
roster also retains unresolved candidates and outlets where usable evidence was
not found; neither means that an account does not exist.

## Run

Requires Python 3.9+ and the system timezone database. There are no third-party
runtime dependencies. From the repository root:

```sh
export PYTHONPATH=src
python3 -m weibo_media registry
python3 -m weibo_media collect --limit 110
python3 -m weibo_media export
python3 -m weibo_media report
```

Alternatively, install with `python3 -m pip install -e .` and use `weibo-media`.
`python3 -m weibo_media --help` lists commands. The global `--db PATH` option goes
before the command; default: `data/local/weibo.sqlite`.

The manual CLI's default publication interval is **January 1, 2020 through October 21, 2026**,
inclusive in Asia/Shanghai. Internally it is half-open, ending at October 22,
2026 00:00 Shanghai time. `collect`, `archive`, and `import` accept `--start` and
`--end` overrides. Original timestamps and normalized UTC timestamps are stored
separately. Sina's unzoned Chinese publication timestamps are interpreted in
Asia/Shanghai; imports with explicit offsets retain their own interpretation.
The automatic refresh advances the live collection window separately and
recomputes rolling graphs through the last completed Shanghai day; it does not
reset the live corpus to this original baseline.

```sh
python3 -m weibo_media collect --account forbes-china --limit 25 --delay 2
python3 -m weibo_media archive --account fortune-china \
  --url https://web.archive.org/web/20260310032620id_/https://weibo.com/fortunechina
```

`--account` is repeatable for `collect`; it defaults to confirmed accounts only.
`--url` is repeatable for `archive`. Only pilot-verified source routes are
supported. Requests use an identifiable user agent, robots checks, conservative
spacing, bounded network/5xx retries, and no login/CAPTCHA bypass. HTTP access or
rate-limit failures stop further network requests by that client. Archive
redirects to different capture timestamps are refused.
Sina redirects that change the requested profile/post identity or source route
are also refused, even when the hostname stays the same.

A `collect` rerun resumes an unfinished persisted feed snapshot. Once its cursor
is exhausted, another invocation starts a fresh snapshot. Post IDs deduplicate
across runs while retaining source text and engagement snapshots. An old pinned
post never stops the date scan. Unavailable detail pages retain labeled previews;
their errors are saved in the run checkpoint and do not prevent other feed
entries from being processed. A new feed pass retries details. `archive` reruns
deduplicate post IDs and retain snapshot provenance.

An explicit detail-page contradiction in post ID, author UID, or the requested
date/attribution bounds is different from an unavailable detail page: that source
is skipped, not imported as a fallback preview. Such conflicts are retained in
the run checkpoint's `source_conflicts` for review.

Canonical text selection compares completeness before length. Equally
`source_full` original/unknown-kind records prefer a validated native detail body
over longer archived UI renderings; known reposts retain longer quoted context.
Ignored archival pin controls are excluded from post text. Canonical imports
restore the supplied, provenance-matched choice among equal-quality variants.
Every prior source variant remains in provenance rather than being discarded.

Accounts may specify an optional `attribution_end` date (`YYYY-MM-DD`, exclusive,
Asia/Shanghai). Live collection, archives and imports all exclude publications
on or after that cutoff, even if the UID and displayed brand name are unchanged.
Evidence and account notes explain conservative cutoffs; they are not necessarily
exact contract-termination dates. Existing registries and databases without the
field remain compatible. An absent cutoff is not evidence of a continuing license.

Collection runs are deliberately **partial**, even when the visible feed is
exhausted: no complete historical pagination has been demonstrated. Blocked
accounts are recorded rather than silently skipped. Exit code `2` means that
some source retrievals were blocked/failed, but usable records may have been
saved; code `1` indicates a command/input failure. Inspect `runs.csv` and
`coverage.csv`, not just process success.

## Data and exports

| Location | Contents |
|---|---|
| `data/registry/outlets.json` | Reviewed roster, candidate accounts, identity/operator evidence |
| `data/local/weibo.sqlite` | Local posts, provenance, observations, runs/checkpoints |
| `data/local/raw/` | Local raw responses for reproducibility |
| `data/local/exports/` | Full-text CSV and JSONL exports plus coverage and manifest |
| `reports/weibo_media_inventory.md` | Shareable sourced inventory and descriptive activity |

Local databases, raw responses, and corpus exports are ignored by Git. Do not
publish third-party text without checking source terms and redistribution rights.
The default export is a **local/private research corpus**, not a license to
redistribute. `export --public --output data/local/public` omits posts without
explicit `redistribution: "permitted"` and lists every omission in
`omissions.csv`; it does not silently substitute metadata-only post rows.
Review all metadata/rights assertions yourself before sharing any output.

`posts.jsonl` is the canonical lossless post export. Each row includes full
recoverable text, string IDs, publication timestamps, completeness, original/
repost classification, all text provenance, and engagement observations.
`posts.csv` includes the same text with proper CSV quoting; nested provenance
and observations are JSON cells. Import IDs and text as **text** in spreadsheets
to avoid precision loss or formula execution. Other tables have CSV and JSONL
exports; SQL nulls are JSON `null` and empty CSV cells.

Text-completeness labels:

- `source_full`: entire accessible syndicated/captured body, not independently
  verified against an inaccessible original.
- `truncated`: a feed preview or unexpanded archived post.
- `full`: an import explicitly establishes complete original text.
- `unknown`: completeness cannot be established.

Sina headline/description summaries, recommendations, and comments are not
treated as original post text. Source-feed engagement is recorded at the feed
retrieval time, not the later detail-fetch time. Archive observations use
capture time, separate from retrieval and publication times. Missing counts
remain null, never zero. Counts may be cached. Monthly activity is recovered
output, not true total output; missing months are not reported as zero activity.
Syndicated posts with unknown repost status are not assumed original.

## Extend coverage with authorized or archival records

`import` accepts either the canonical exported `posts.jsonl` (including all
provenance and observations), or normalized JSONL like this synthetic example:

```json
{"id":"90071992547409931","account_id":"forbes-china","uid":"1765373140","published_original":"2020-01-01T12:00:00+08:00","text":"Example authorized text.\nSecond line.","text_status":"full","kind":"original","source_url":"https://example.org/permitted-export/record","source_type":"authorized_import","retrieved_at":"2026-10-21T12:00:00+00:00","likes":null,"comments":0,"reposts":null,"redistribution":"unknown"}
```

```sh
python3 -m weibo_media import data/local/authorized.jsonl
python3 -m weibo_media export
python3 -m weibo_media report
```

Allowed sources are `sina_syndication`, `archive`, and `authorized_import`.
Archived records additionally require timezone-aware `captured_at`; publication
cannot follow capture. `retrieved_at` must be timezone-aware. Post/account IDs
must be numeric **strings** and bind to a confirmed registry account with a
known UID. `kind` is `original`, `repost`, or `unknown`; optional
`referenced_id` and `repost_commentary` preserve repost context.
Missing `redistribution` defaults to `unknown`. Metadata-only input is rejected.
Each import is transactional: a malformed line rolls back that whole file.

Registry loading validates exact fields and evidence gates, then upserts; it
does not delete older registry records from an existing database. Use a fresh
database when an exact independent registry snapshot is needed.

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use synthetic, offline data, not real post text. They cover evidence
gating, author/ID checks, Shanghai boundaries, pinned posts, resume/deduplication,
detail isolation, archive capture times, preview retention, nullable engagement,
transactional imports, and full Chinese multiline CSV/JSONL round trips.
Live results are documented separately in the access pilot.

No topics, LLM labels, sentiment, comments, follower lists, media files, or
article-body crawling are collected.