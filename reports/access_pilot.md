# Public-source access pilot

Observed on **October 21, 2026**. These are actual network checks, not fixture
results. Access can differ by time, region, and client. Registry evidence uses
date-granularity observation labels at midnight UTC; exact post-source retrieval
and capture timestamps are retained separately in the local database.

## Account identity

| Outlet / edition | Evidence | Result |
|---|---|---|
| Forbes China | [Publisher homepage](https://www.forbeschina.com/) outbound link; [Sina profile](https://www.sina.cn/media/1765373140) organization-naming certification | Confirmed; UID `1765373140` |
| Fortune China | [Publisher homepage](https://www.fortunechina.com/) outbound link; [archived profile](https://web.archive.org/web/20260310032620id_/https://weibo.com/fortunechina); [current Sina profile](https://www.sina.cn/media/1657987915) | Confirmed; UID `1657987915` |
| Harvard Business Review, Chinese edition | [Sina profile](https://www.sina.cn/media/2793358674) explicitly identifies the edition's official account; [HBR global editions](https://hbr.org/global-editions) establishes the licensing relationship | Confirmed; UID `2793358674`; exact legal account operator unresolved |
| The New York Times, Chinese edition | [First-hand publisher confirmation to TechCrunch](https://techcrunch.com/2012/07/03/one-week-on-new-york-times-social-media-accounts-shut-down-in-china-site-still-up/); [2012 archived profile](https://web.archive.org/web/20120628101255id_/http://www.weibo.com/nytchinese) binds handle to UID | Historically confirmed; UID `2782194035`; no current-survival claim |
| The Wall Street Journal, Chinese edition | [Archived publisher homepage, 2018](https://web.archive.org/web/20181009043938/https://cn.wsj.com/) links to `chinesewsj`; [archived platform profile, 2019](https://web.archive.org/web/20190724092335/https://www.weibo.com/chinesewsj) binds it to UID `1649159940` | Historically confirmed after expanded verification; present account availability/activity unresolved. No in-window corpus recovered. |
| National Geographic, Chinese-language account | [Sina profile](https://www.sina.cn/media/1644225642) explicitly names 美国国家地理官方微博 | Newly confirmed; UID `1644225642`; exact legal operator unresolved; no backfill attempted |
| Scientific American / 环球科学 | [Sina profile](https://www.sina.cn/media/1235572171) names the official magazine account and Chinese edition; [publisher homepage](https://www.huanqiukexue.com/) independently identifies the edition and company | Newly confirmed Chinese-edition account; UID `1235572171`; no backfill attempted |
| MIT Technology Review, Chinese-language account | [Sina profile](https://www.sina.cn/media/1738690784) explicitly names 《麻省理工科技评论》杂志官方微博 | Newly confirmed; UID `1738690784`; current legal operator/licensing terms unresolved; no backfill attempted |

The roster includes U.S.-based Chinese-language outlets, but no account for
those outlets was confirmed in this bounded pass. In particular, SinoVision /
美国中文网 and The China Press / 侨报 are separate outlets, not aliases.
Publisher access failures and limited searches are recorded in the registry;
they are not negative proof that accounts do not exist.

## Direct platform access versus public syndication

| Surface | Actual result | Decision |
|---|---|---|
| [Weibo robots policy](https://weibo.com/robots.txt) | Default crawler group disallows `/`; other named crawler groups differ | Do not implement direct Weibo scraping or impersonate a privileged crawler |
| Forbes, Fortune and NYT desktop profile requests | Redirected to Sina Visitor System | Do not bypass the visitor gate; distinguish this from account deletion |
| Mobile timeline/status probes | HTTP 432 | No further gate-evasion attempts |
| [Sina mobile robots policy](https://www.sina.cn/robots.txt) | Default group allows `/` | Use only the verified public syndication routes, with pacing and policy checks |
| `/media/1765373140` | 101 visible feed entries, including an older pinned September 8 post ahead of October 21 posts | Do not infer chronological order or stop at the pinned date |
| `/media/1657987915` | 100 visible feed entries; explicit Fortune China certification | Collect linked accessible details; mark historical coverage partial |
| `/media/2793358674` | 100 visible feed entries; explicit Chinese-edition HBR certification | Collect linked accessible details; unknown repost status remains unknown |
| `/media/2782194035` and `/media/1649159940` | Redirected off the supported host/route toward a generic Sina homepage | Do not follow as an account feed or infer inactivity |
| Linked Sina detail pages | Some expose a main `article-content` body and structured author URL; others redirect away from supported routes | Verify author UID and post ID; retain a labeled feed preview if detail is unavailable |

For example, the Forbes post with ID `5356507123421092` has 153 characters in
the feed preview and 209 in the accessible detail body. The detail's
headline/description are separate editorial metadata and are not imported as
post text. Related-user recommendations, comments, and linked article bodies
are excluded. Main detail text is `source_full`, not a guarantee that an
inaccessible Weibo original has no additional content.

Feed engagement action order was checked against the SVG markup:
reposts, comments, likes. Only plain integer values are parsed; abbreviated
counts are not guessed. Counts are timestamped source snapshots, not
publication-time historical measurements.

No historical feed pagination was exposed. The visible end marker means only
that the returned snapshot is exhausted. It does not establish complete
history, complete recent output, or recovery of deleted posts.

## Archive recovery

Annual CDX queries were bounded to 2020-2026, HTTP 200, HTML responses,
one capture per year. CDX hits were treated as discovery leads, not posts.
`web.archive.org/robots.txt` returned HTTP 404 (no robots rules at that path);
other policy/network errors are not treated as permission to proceed.
Archive requests use the same conservative pacing and do not follow redirects
to a different capture timestamp.

Several replay bodies are gzip-encoded. Decoding gzip, rather than treating the
body as empty/unreadable HTML, recovered Fortune's stable UID. A 2020 template
stores feed fragments in JSON passed to `FM.view`; the adapter decodes those
JSON strings without executing JavaScript.

| Account | Requested archive capture UTC | Recovered posts | Outcome |
|---|---|---|---|
| Fortune China | 2020-03-15 17:04:09 | 15 | Supported JSON-embedded feed; publication dates March 6-13, 2020 |
| Fortune China | 2021-08-15 10:31:15 | 16 | Usable static profile snapshot |
| Fortune China | 2022-01-19 04:49:06 | 15 | Usable static profile snapshot |
| Fortune China | 2023-05-08 17:30:33 | 0 | Replay has no verifiable profile owner/feed markup |
| Fortune China | 2024-01-14 06:26:09 | 15 | Usable static profile snapshot |
| Fortune China | 2025-01-19 07:45:34 | 0 | Replay has no verifiable profile owner/feed markup |
| Fortune China | 2026-03-10 03:26:20 | 16 | Usable static profile snapshot |
| Forbes China | 2023-04-26 00:18:46 | 0 | Replay has no verifiable profile owner/feed markup |
| Forbes China | 2025-04-05 03:41:12 | 0 | Replay has no verifiable profile owner/feed markup |

These are recovered rows per snapshot, not guaranteed net-new unique posts.
The failed first 2020 parser attempt remains in the run log; the corrected
adapter recovered that snapshot successfully on retry.

The specified `nytchinese` URL and HBR numeric-profile URL returned no matching
2020-2026 captures in the bounded CDX queries. Additional all-year queries found
one NYT capture in 2012, which resolved UID `2782194035` but lies outside the
requested corpus window. The tested WSJ handle/numeric URL variants returned
no index rows. These results do not prove that other aliases, snapshots, or
archives lack material.

Archived expandable previews remain `truncated`; visible unexpanded bodies
are `source_full`. Archive capture time, retrieval time, and publication time
remain separate. Archived engagement is attributed to the capture snapshot.
Logged-out archive templates put visible like counts inside `like_status`
nodes on login links, rather than `fl_like` actions. Both representations are
parsed; the four usable 2021-2026 snapshots were refreshed after this correction.

## Executed collection

The completed bounded run recovered **378 distinct posts**: 101 for Forbes
China, 177 for Fortune China (100 public-feed posts and 77 archived posts),
and 100 for HBR's Chinese edition. No in-window NYT posts were recovered.
Thirty public-feed detail pages were unavailable (10 Forbes, 18 Fortune,
2 HBR); their previews were retained rather than discarded or called complete.

The canonical corpus contains **296 `source_full` bodies and 82 `truncated`
previews**, with 711 provenance records and 375 engagement observations.
These are recovery and source-quality counts, not a claim that all original
Weibo text or all activity was retrieved. The local `posts.jsonl` and
`posts.csv` contain every recoverable canonical text, including explicitly
labeled previews, and reconcile with the database.

## Remaining gaps

The inventory is usable independently of corpus coverage. The public feed and
selected archives provide real recoverable posts, but **not a complete
January 2020-October 2026 backfill**. Large gaps remain between snapshots, and
the 2023/2025 replays above did not supply verified text.

Extending coverage requires additional permitted archives, publisher-supplied
exports, or properly authorized platform/licensed access. The
[account-monitor documentation](https://open.weibo.com/cli/skills/account-monitor)
and [data interface](https://data.weibo.com/datacenter/interface) are discovery
leads only; this pilot did not establish free unauthenticated historical
entitlements. The normalized JSONL importer supports provenance-bearing
authorized records without rerunning or relabeling existing data.

The generated [inventory and activity report](weibo_media_inventory.md) and
local `coverage.csv`, `runs.csv`, and full-text corpus are the authoritative
outputs of the actual collection. No third-party post text is committed here.
