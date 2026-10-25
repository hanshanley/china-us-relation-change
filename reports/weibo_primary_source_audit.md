# Weibo primary-source recheck and corpus corrections

Audit date: October 22, 2026. Publication window remains January 1, 2020
through October 21, 2026, inclusive in Asia/Shanghai.

This document describes the original audit baseline. Subsequent automatic live
refreshes carry unchanged bound source proofs forward and verify new or changed
canonical records against newly saved primary captures. Their complete current
proof manifest and aggregate JSON expose the updated corpus counts. These
incremental checks do not imply another live account-identity sweep, and do not
replace the archived October 21 baseline.

The registry-bound manifest was refreshed October 25 UTC after 256 additional
ranked-domain reviews. Account/post source captures and all identity decisions
are retained. The latest factual-only Gwinnett review adds no account or
post and implies no new live numeric-profile sweep; see discovery_iteration85.md.

This is a source-level recheck, not just a reconciliation of registry flags.
It establishes documented institutional/profile associations and consistency
of the recovered text with saved primary sources. It does **not** independently
certify current corporate control, continuing U.S. licensing, exhaustive
account discovery or complete historical timelines.

## Identity decisions

| Decision | Channels | Meaning |
|---|---:|---|
| Numeric binding rechecked | 85 | Live institutional profiles, saved historical owner-UID headers or an explicit original-author card re-read; publisher/edition relationships remain explicitly qualified. |
| Historical numeric binding recheck pending | 1 | NYT Chinese retains its previously documented mapping, but that numeric binding was not independently revalidated in this audit. |
| Publisher-designated historical vanity rechecked; UID unresolved | 1 | VOA's `legalwindow` programme designation is established; its numeric candidate remains unassigned. |

There are still **87 documented current/historical channel records**, not
87 independent U.S. newspapers or 87 uniformly U.S.-operated newsrooms.
The 86 previously recorded numeric UIDs must not be confused with the
85 numeric bindings rechecked here.

All 86 registered numeric profile routes were attempted through permitted,
paced Sina syndication pages. **81 were readable; five redirected and were not
followed across hosts. All 62 current-profile entries matched their registered
names.** Redirects were not interpreted as deletion or suspension. Historical
renames, including former SELF, TechCrunch, VICE and WSJ Magazine channels,
were not relabeled as current U.S.-brand operations.

The live requests were repeated with a guard rejecting same-host redirects
that change the requested profile/post identity or source route. Historical
owner assertions were read from previously saved primary HTML, including
legacy owner configuration and institution-specific headers. No new archive
requests were made after the recorded archive access restriction.

For uncertified profiles, officialness was not inferred from a generic bio or
matching name alone. The actual Artforum publisher-to-Chinese-site-to-numeric
account chain and EE Times' saved publisher navigation were inspected.
PR Newswire's publisher-owned account directory was fetched again:
its additional UID `1660674903` still displays an unbranded placeholder.
Without a resolved institutional identity it remains outside the confirmed
account corpus; that is not a finding that it was deleted.

The original NYT ownership-confirmation report was reread; it establishes the
historical `nytchinese` designation, not the numeric UID. A separately identified
2017 WSJ native post redirected and was not treated as numeric confirmation.
Subsequent cache inspection resolved WSJ's numeric recheck independently:
the [saved June 8, 2017 Weibo capture](https://web.archive.org/web/20170608194454id_/http://weibo.com/chinabloomberg)
contains a scoped original-author card explicitly connecting
`华尔街日报中文网`, `/chinesewsj` and `usercard` UID `1649159940`.
The containing feed distinguishes Bloomberg's owner UID `5076455752` from
the reposted original author's UID `1649159940`. This is first-party platform
identity markup, not an inference from a quoted name or a third-party repost
site. The full saved source hash and method are in the account-audit manifest.
The June 2, 2017 original post is outside the collection window and was not
imported. Historical identity does not certify current operation or licensing.

VOA's candidate profile still has a matching programme name/books/bio, but
that does not establish the missing vanity-to-UID binding. No candidate
posts were imported.

## Actual corpus defects corrected

The audit found extraction/selection defects, not evidence that these posts
belonged to different account UIDs:

- **Seven canonical text selections** preferred longer archived renderings
  over already validated native bodies. Differences included invisible
  characters, rendered link captions and, in one case, a pin label.
  The cleaner native body is now selected for these original-kind records.
- **Fourteen additional archived previews** contained an ignored `置顶`
  interface control and its layout whitespace. These controls were removed
  by re-parsing the actual saved source, without new archive retrieval.
- **All 21 changes affected only canonical text.** No posts or engagement
  observations were deleted. Every prior source variant was preserved;
  fourteen cleaned, cache-derived provenance observations were added.

Canonical selection still gives explicit completeness precedence over source
preference. Equally `source_full` original/unknown-kind records prefer
validated native detail bodies over longer archive UI renderings. Known
reposts retain longer quoted context. Canonical imports restore the
provenance-matched canonical choice among equal-quality variants, so replaying
retained legacy variants cannot silently undo these corrections.

The per-record correction ledger contains IDs, correction methods and
before/after text hashes, not copyrighted post bodies:
[complete correction ledger](../data/discovery/weibo_canonical_corrections.csv).

## Source-level validation

All **6,521 canonical stored texts**, with their timestamps and scoped account
identities, were checked against primary-source captures. This included:

- **5,500 native detail sources**, validating post ID, unique author UID,
  publication time and the extracted body;
- **46 archived sources**, validating owner UID, own-author post markup,
  publication time and extracted text;
- publisher-scoped feed captures for remaining explicitly truncated previews.

The corpus still contains **5,760 available source bodies and 761 truncated
previews**. Matching an available source body does not establish a complete
original Weibo post, images, video or transcript recovery. Preserved legacy
UI-bearing variants are provenance, not the corrected canonical text.

The complete
[6,521-row source-audit manifest](../data/discovery/weibo_post_source_audit.csv)
provides post/account IDs, publication UTC, text status, canonical text hash,
selected primary-source URL, saved-source hash and verification method.
It is explicitly **audit metadata, not a substitute for the private full-text
corpus**. Full canonical text and every source variant remain in
`data/local/exports/posts.{jsonl,csv}`.

## Collector and publication safeguards

Regression cases reproduced a real collector bug: a detail page contradicting
the expected post ID, author UID or publication/attribution bounds was being
treated like an unavailable detail page, retaining an attributed preview.
Such contradictions now reject that source and persist in `source_conflicts`;
ordinary unavailable details still retain clearly labeled, scoped previews.
No such explicit contradictions were found in the saved native metadata and
recorded detail-error checkpoints examined for this corpus.

New snapshots bind the audit to the registry and hashes of every canonical
database text, without publishing those texts. Publication fails if the
registry/text snapshot changes or a new unresolved source conflict affects
an existing corpus record. Reconciliation of counts alone can no longer
silently carry a stale source-audit claim.

The frozen aggregate JSON and complete account CSV expose each account's
primary recheck status, method, source URL, source hash and limitations.
The complete machine-readable decisions are in
[the primary-audit manifest](../data/discovery/weibo_primary_audit.json).

## Remaining gaps

NYT Chinese's historical numeric recheck and VOA's numeric binding remain unresolved.
Current legal operation and continuing license terms are not uniformly audited.
The ranked cohort still has **12 positive domains, 988 unknown domains and zero
verified negatives**; 367 have recorded manual review, including the 247
additional reviews above. It is a SCImago
U.S.-classified digital-reputation cohort, not a traffic ranking or an
independently audited ownership list. This work improves the reliability of
the documented positives and recovered corpus; it does not complete that census.
