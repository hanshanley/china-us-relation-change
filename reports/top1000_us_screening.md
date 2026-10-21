# Top 1,000 U.S. news websites: Weibo screening

Published: 2026-10-21T18:46:07.966742+00:00. All 1,000 selected domains have an attempted-check record.

## U.S.-only ranking and selection

Source: [SCImago U.S. media ranking](https://www.scimagomedia.com/rankings.php?country=United+States), retrieved October 21, 2026; [methodology](https://www.scimagomedia.com/methodology.php). The source download contains 1,139 U.S.-classified media domains. We selected the first 1,000 in published order, retaining tie order and recording both global rank and U.S. selection position. This is not the global top 1,000 and not an all-industry website list.

**Ranking is digital reputation, not audience/traffic.** SCImago combines four equally weighted SEO/link indicators. Country is its place-of-publication/media-reference classification, not independently verified ownership. The download has no edition date; the retrieval date must not be presented as a ranking vintage. Some specialist/Chinese editions in our manual inventory are absent from this source.

SCImago (n.d.), *SCImago Media Rankings* [Portal], retrieved October 21, 2026. Source data permits non-commercial reuse with attribution; the derived ranking retains that restriction. The manifest records the download SHA-256 and selection rule.

## Actual screening outcomes

| Outcome | Websites |
|---|---:|
| access_error | 73 |
| http_error | 226 |
| inconclusive_non_html | 1 |
| robots_disallowed | 23 |
| screened_no_link | 677 |

Each check requests the publisher robots policy and, only if allowed, at most 1.5 MB of the homepage. Explicit robots 404/410 means no rules at that path; policy errors, HTML challenge pages posing as robots files, login/rate limits, unsupported redirects and inaccessible hosts are not bypassed. Requests are paced per domain with bounded cross-domain concurrency. A recovery pass checks www aliases' robots independently and supports HTTPS 308 redirects; old events remain in the local journal while exports use the latest result per domain. The earlier interrupted exploratory pass is excluded.

**This is 1,000 attempted publisher checks, not 1,000 verified account decisions.** `screened_no_link` means no recognized profile anchor in the returned snapshot; it is not a negative Weibo-account finding. Tiny/non-HTML pages, blocked pages and robots restrictions are inconclusive. JavaScript-rendered links, Chinese editions, historical pages, contact pages and alternate domains are outside this bounded homepage pass.

## Publisher-link candidates

Links below require manual identity/edition review; homepage links can be partners rather than the publisher's own account. Share buttons, post URLs and incidental script text are not classified as profile links.

| U.S. position | Publisher | Homepage | Profile links |
|---:|---|---|---|
| - | No recognized profile links in this bounded pass | - | - |

## Manually verified identities remain separate

See the [evidence-backed account inventory](weibo_media_inventory.md). Expanded targeted verification resolved WSJ Chinese as historically official (`chinesewsj`, UID `1649159940`) using an archived publisher link and archived platform UID. It also confirmed National Geographic's Chinese-language account (`1644225642`) and Scientific American's Chinese-edition magazine account (`1235572171`), plus MIT Technology Review's Chinese-language account (`1738690784`). These three additional specialist brands do not appear in the selected SCImago 1,000; they are supplementary discoveries, not results manufactured from the ranking scan. Subsequent [collection follow-up](collection_followup.md) also verified Bloomberg China, China Press and two regional World Journal accounts, collected the newly verified public feeds, and investigated historical archive failures. The next [discovery round](discovery_round2.md) adds the historical Fast Company publisher at U.S. source position33 and further supplementary accounts, while auditing UID rebranding and same-name false leads. The [continuing iteration](discovery_iteration3.md) adds further business, technology, U.S. Chinese-language and licensed specialist-media identities, including the separate NYT-licensed T China style edition. It also records publisher-announced license termination: unchanged profile names do not establish a continuing U.S. license. Current status and legal operator uncertainty remain explicit.

## Complete machine-readable deliverables

- [All 1,000 ranked U.S. domains](../data/discovery/us_top1000.csv)
- [Ranking source manifest](../data/discovery/us_top1000.manifest.json)
- [All 1,000 checks, CSV](../data/discovery/us_top1000_screening.csv)
- [All 1,000 checks, JSONL](../data/discovery/us_top1000_screening.jsonl)

- [All 1,000 account decisions and post counts, CSV](../data/discovery/us_top1000_accounts.csv)
- [All 1,000 account decisions and evidence, JSONL](../data/discovery/us_top1000_accounts.jsonl)
- [Ranked plus supplemental outlet assessments, CSV](../data/discovery/outlet_account_assessments.csv)
- [Ranked plus supplemental outlet assessments, JSONL](../data/discovery/outlet_account_assessments.jsonl)

Every roster row is retained, including blocked and inconclusive checks. No post text or publisher article bodies are included in these screening exports. The account assessment fields distinguish confirmed identities, historical-only evidence and unknowns; there are no verified-negative account findings. Collected-post booleans refer only to our recovered corpus, not true account output.

## Reproduce or resume

Requires Python 3.9+ and no additional packages. From the repository root:

```sh
export PYTHONPATH=src
mkdir -p data/local/discovery
curl --fail --location 'https://www.scimagomedia.com/rankings.php?country=United+States&download=1' --output data/local/discovery/scimago-us.xlsx
python3 -m weibo_media.discovery roster data/local/discovery/scimago-us.xlsx
python3 -m weibo_media.discovery screen --workers 12
python3 -m weibo_media.discovery publish
```

The roster command validates U.S. labels, ordering and distinct domains before selecting exactly 1,000 rows. `us_position` is a selection index, not an untied published rank. Screening checkpoints are local at `data/local/discovery/us1000-validated/screening.jsonl`. Reruns resume without repeating completed domains; use a fresh `screen --output` directory for a new observation. `screen --retry-redirects` revisits prior unsupported redirects without removing the original journal events. To publish a nondefault checkpoint, supply `publish --screening PATH`. Publication rejects incomplete or mismatched rosters.
