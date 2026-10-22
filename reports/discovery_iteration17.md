# Las Vegas newspaper account and a corrected domain-alias lookup

Research observed October 22, 2026 UTC/EDT, continuing checkpoint
`98125bf`. The fixed publication interval remains January 1, 2020
through October 21, 2026 inclusive, Asia/Shanghai.

**One additional historical account was verified: Las Vegas Chinese
News Network / 拉斯维加斯新闻报, UID `5079316821`, handle `lvcnn`.**
No new eligible posts were recovered. This pass also fixes an actual
cohort-lookup bug without changing the selected 1,000 domains.

## Publisher designation and independent historical owner binding

The [current publisher homepage](https://www.lvcnn.com/) directly
links **`weibo.com/lvcnn`** through its own Wei Bo logo. Its actual
[Contact](https://www.lvcnn.com/contact.php) and expressly linked
[company introduction](https://www.lvcnn.com/guest.php?id=1200)
independently identify the newspaper's Las Vegas, Nevada operation,
matching publication name and website.

The company-introduction page is this newspaper's own listing, not
one of its separate travel-agent or other advertiser entries. No CNN
account or organizational relationship was inferred from the site's
English abbreviation.

An [exact January 28, 2015 publisher homepage](https://web.archive.org/web/20150128072550id_/http://www.lvcnn.com:80/)
already carries the same `lvcnn` link. The
[exact February 16, 2015 platform profile](https://web.archive.org/web/20150216123507id_/http://www.weibo.com/lvcnn)
has matching title and owner-scoped **`oid=5079316821`** /
**`onick=拉斯维加斯新闻报`**. This binds the publisher's actual handle
without using viewer IDs, avatars or an unrelated similarly named
creator.

The contemporaneous 2015 publisher link matters: today's footer was
not simply backdated as proof of 2015 officialness. The earlier
[January 2012 publisher root](https://web.archive.org/web/20120127082006id_/http://lvcnn.com:80/)
had no qualifying profile link, which did not prove account absence
and did not prevent checking a genuinely later source.

Officialness rests on publisher designation and independent owner
binding, **not an assumed current blue badge**. The current legal
account owner and current platform identity/activity remain
unverified, so the account is classified **historical**, not as a
currently active feed.

## Zero recovered eligible posts is a documented gap

The permitted current numeric Sina route redirects outside the
supported same-host HTTPS route. It was refused, and the official
collection attempt, run **147**, records one attempted page and
**zero recovered posts**, with the exact access limitation. No
redirect to a desktop/mobile Weibo gate or other host was followed.

The already preserved 2015 profile was parsed **offline**, without an
unnecessary replay download. It has **15 author-validated records
dated March 21 through December 11, 2014**. These are not 2015
publications merely because the source was captured in 2015, and
none is within the fixed 2020-2026 window. They were not imported
into the post corpus.

Two genuinely different numeric-profile archive indexes, `u/UID`
and the bare UID path, were checked for 2020-2026. Both were empty.
Additional bounded native-source searches supplied no independently
author-bound eligible record; other publishers' stories about Las
Vegas were not imported as the newspaper's output.

These findings do not establish deletion, inactivity, no later posts,
a transfer of account control or any license/attribution cutoff.
The current publisher's retained link is not proof of current
platform availability. Historical recovery remains explicitly
incomplete.

## DI.fm: fix the lookup, preserve the cohort

The selected source row at position **84** literally uses
**`www.di.fm`**. Registry publication matching already canonicalized
`https://www.di.fm/` to **`di.fm`**, but compared that with the raw
cohort string. This could hide a real manual review or known account
and create a second, unnecessary **`di.fm`** supplemental row.

The fix canonicalizes **lookup keys only** for account matching,
manual-review matching and supplemental-membership checks. It
preserves all **1,000 original source-domain strings and their
order**, including `www.di.fm`. It does not replace a source row,
rerank websites or silently change the sample.

The real cohort contains **one** such noncanonical row and **zero
canonical-host collisions**. Two focused regression cases first
reproduced the missing account decision and duplicate supplement,
then passed after the correction. The full-ledger case verifies
the original membership/order, matching review and no duplicate
bare-host supplement. Existing missing-link/unknown semantics are
unchanged; this is not a new DI.fm account claim.

## Five additional ranked publisher/platform reviews

Positions refer to SCImago's U.S.-classified **digital-reputation**
cohort, not a traffic ranking or independent corporate-nationality
audit.

| Position | Publication/platform | Actual primary follow-up | Weibo result |
|---|---|---|---|
| 80 | St. Louis Post-Dispatch | Complete root and actual Contact | Unknown |
| 81 | Anchorage Daily News | Complete root and actual Contact | Unknown |
| 82 | Bicycling | Complete root, actual About and Community Guidelines | Unknown |
| 83 | Toledo Blade | Complete root; guarded Contact redirect; independently permitted HTTPS media-kit Contact | Unknown |
| 84 | DI.fm / Digitally Imported | Live root 403 respected; independently permitted exact 2012 publisher root | Unknown |

[St. Louis Contact](https://www.stltoday.com/contact/) was read without
treating its unexpanded template placeholders or individual staff
paths as publisher-account proof.
[Anchorage's actual Contact](https://www.adn.com/contact/) is one page
despite its slash redirect. Other Daily News papers, businesses
using the ADN acronym and local sports teams were not substituted.

[Bicycling's own About](https://www.bicycling.com/about/a19436368/about-bicycling/)
identifies the actual magazine, not the generic cycling activity.
A self-described **单车志Bicycling官方** Sohu byline was encountered,
but supplies neither a publication-specific Sina UID nor a retrieved
primary U.S.-brand edition/license binding. It was not promoted or
added as a U.S. Bicycling alias. This is not a fraud, unlicensed-
operation or permanent non-affiliation finding.

Toledo's actual Contact redirect points to an **HTTP** media-kit
URL. That downgrade/cross-publisher redirect was not followed.
Header-only metadata identified the target; the corresponding
[HTTPS media-kit Contact](https://www.blademediakit.com/the-blade-contacts/)
was independently robots checked and readable, identifying the
actual Blade contacts without a qualifying Weibo link. Shared
parent/company social accounts were not borrowed.

DI.fm's live **403** was respected without a live alias or path
bypass. The independently permitted
[exact January 3, 2012 publisher root](https://web.archive.org/web/20120103055334id_/http://www.di.fm:80/)
identifies Digitally Imported's electronic-music radio service. Its
hosted channels, DJs and similarly abbreviated businesses were not
substituted for the platform's own account. It is labeled a radio
platform, not an independent newspaper.

### Reject the wrong community entities

The initial generic **Bicycling** item described a mode of transport,
and generic **The Blade** was a disambiguation page. Both failed
publication/website matching and were rejected, not used as
negative account evidence.

The actual **Bicycling magazine** and **Toledo newspaper** articles
were then resolved, with their own items and matching expected
websites. Together with the three already correct items, all five
publication/platform-specific main Sina-identifier checks supplied
no locator. Only ordinary Wikipedia/Wikidata HTML was used; no
API, EntityData or SPARQL fallback. Missing community identifiers
do not establish account absence.

## Reconciled checkpoint and continuing frontier

The registry now contains **161 reviewed outlet/candidate rows**,
**82 confirmed current/historical account identities across 57
publisher/brand groups**, and **267 structured account-evidence
records**. Six new reviewed rows comprise the five ranked
publications/platforms and the Las Vegas newspaper. The new
historical identity does not imply current activity.

The corpus remains **6,059 distinct posts from 64 accounts:
5,322 source-full and 737 truncated**. Complete private CSV/JSONL
retain all available in-window post text and provenance/observations,
without omitted records. No 2014 post, unrelated publisher output or
invented full text was imported. Raw sources and post bodies remain
private; public downloads are complete aggregate/account tables.

The canonical private JSONL remains **byte-identical** to the prior
6,059-record export, SHA-256:
`6bf6bbd41a4c84010cd231839df81f3d268ef633e57102fb145eaab8121503a2`.
Exact real-corpus reimport preserves posts, provenance and observations.
The original 1,000-domain roster CSV is also byte-identical; only its
assessment matching and newly recorded reviews changed.

The combined ledger has **1,076 domains**, with no separate
`di.fm` supplement duplicating ranked `www.di.fm`. The selected
1,000 still contain **five current-identity positive domains, six
historical-only positives and 989 unknowns**, with **zero verified
negatives**. All five newly reviewed ranked rows attach to their
actual original domains; no source row or ordering changed.

The next actual unreviewed ranked rows begin with **Houston
Chronicle / chron.com (85), The Balance (86), Baton Rouge Advocate
(87), Portland Press Herald (88) and Billings Gazette (89)**.
Publication-specific cycling-brand relationships, legitimate U.S.
community publishers and older permitted post sources remain
actionable leads. The recurring research prompt remains active:
this checkpoint is not global completion.
