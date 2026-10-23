# Scheduled discovery: separating publisher identity, coverage and source rights

Review date: October 23, 2026 UTC. The post window remains January 1, 2020
through October 21, 2026 inclusive, Asia/Shanghai.

This pass reviewed the next five genuinely unreviewed domains in the original
SCImago U.S.-classified digital-reputation cohort. The cohort is not a traffic
ranking, and its country classification is not an independently audited
current ownership or headquarters determination.

## Actual source outcomes

| Position | Selected publication/domain | Primary-source outcome | Account finding |
|---|---|---|---|
| 161 | Newsday / `newsday.com` | Complete root, canonical Contact and actually linked About read; earlier homepage truncation resolved. | Unknown |
| 162 | Willoughby News-Herald / `news-herald.com` | Root/Contact factual metadata only after conservative removal of fresh copies under explicit AI/text-mining reservation. | Unknown |
| 163 | Pasadena Star-News / `pasadenastarnews.com` | Root/Contact factual metadata only under the same explicit reservation; no further host requests. | Unknown |
| 164 | RTVI / `rtvi.com` | Actual root and first-party Weibo-coverage article read; no publisher account designation or independently established current U.S. operator. | Unknown |
| 165 | Berkshire Eagle / `berkshireeagle.com` | Root and Contact read; actually linked About returned HTTP404, not a company-description proof. | Unknown |

Seven primary HTML captures remain available privately: Newsday's three,
RTVI's two and Berkshire Eagle's two. Four additional publisher responses
retain factual metadata only; the failed Berkshire About is separately
recorded. No discarded body is described as an available source capture.

## Repairing a source-completeness gap

Newsday's earlier automated root stopped at a 1.5MB cap. A bounded 4MB
request recovered **2,374,614 bytes**, with the actual truncation flag
**false**. The complete received HTML, not an entire website or account
census, was inspected.

The actual root links to
[Contact Newsday](https://www.newsday.com/services/contact-newsday-lz16sefb)
and a separate publisher-owned
[About page](https://projects.newsday.com/long-island/about-us/).
The latter host's robots policy was checked independently. These sources
identify Long Island reporting and describe a Melville media operation;
they do not independently certify current legal control.

## Source-rights disposition

The Ohio News-Herald and Pasadena Star-News notices explicitly reserve AI
training, text/data-mining and similar uses without written consent.
After reading those notices, this pass conservatively removed **only the
four fresh transient HTML copies**, retained basic identity/link audit
metadata, and made no further requests to either host. Older captures
were not modified.

The metadata records expose `raw_file: null` and `sha256: null`. Separately
labeled discarded-capture fingerprints document disposal, not a retained
primary source. These are rights/retention limitations, not HTTP access
failures and not verified account negatives.

## A mention of Weibo is not a publisher channel

RTVI's
[actual article about Chinese internet services](https://rtvi.com/news/oni-voobshhe-ne-paryatsya-kak-rabotaet-kitajskij-internet/)
describes Weibo as a platform. That is coverage, not an institutional
account designation. Likewise, another Sina profile quoting an RTVI
report, a book promotion quoting Newsday, municipal/police Weibo coverage,
and market pages about Weibo's stock are not publisher-account bindings.

No RT/Russia Today account was silently assigned to RTVI. The actual
RTVI root's contact phone and U.S.-news focus are not headquarters proof;
its static address fields are unpopulated. The selected U.S. classification
is preserved, with that operator uncertainty explicit. Static JSON data
was inspected without executing scripts or requesting controlled APIs.

The Weibo search provider also reported a robots restriction for
`weibo.com`. No result on that host was followed, retried or bypassed.
There were no new archive requests.

## Reconciled publication

The registry contains **247 reviewed outlet/candidate records**.
The selected-domain ledger now records **165 manual reviews and 835
domains without recorded manual review**, with the original source rows,
names, domains, classifications and ordering preserved.

No account was promoted and no posts were added or changed. Totals remain
**87 documented channels across 62 publisher/brand groups**, with 289
account-evidence records and **6,521 partially recovered posts from 68
channels**. There are 5,760 available source bodies and 761 truncated
previews. All 21 canonical text corrections and all provenance remain intact.
The complete private JSONL SHA-256 is unchanged:
`05207b115469159ea36b4c16648e77dbc5cce44ed3e0bee4552eed5ec1bfc47a`.

The account audit retains **85 rechecked numeric bindings**, one pending
NYT Chinese numeric recheck and VOA's unresolved historical vanity UID.
Selected-domain outcomes remain **five current-profile positives, seven
historical-only positives, 988 unknowns and zero verified negatives**.
The combined ledger still contains 1,082 distinct domains.

The complete ledgers, private full-content exports, inventory, registry-bound
audit and Weibo-only publication surfaces are refreshed together. No new
live numeric-profile sweep is implied. Scheduled discovery stays active
every 30 minutes while useful permitted leads remain.
