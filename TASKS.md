# U.S.-China analysis: requested work and completion checklist

Updated: October 24, 2026. This is the durable checklist for the user's requests.
Read this before starting or resuming work, and update it as each item is resolved.
Repeated requests are consolidated below, not silently discarded.

**An unchecked item is not finished.** Work in an isolated candidate, a passing
unit test, or a successful deployment alone does not establish completion.
Previously verified milestones are recorded separately from the remaining work.
This is the **single authoritative request ledger**. `PUBLICATION-TODO.md`
contains archived planning context, not a second set of completion statuses.

## 1. Finish the current graph corrections

Work through these in order; complete and verify a coherent release before
claiming that the website is fixed.

- [ ] **UI-01: Fix repeated toggling.** Switching geography, direction, measure
  and display mode must never leave the previous plot, wrong data, wrong title,
  missing marks, stale tooltip, invalid index or a blank/broken chart.
  Reproduce the October 24 enrolled-student screenshot and toggle back and forth,
  not just reload the initial page.
- [ ] **UI-02: Use bars for a single measured count.** Single-series annual
  reported-value charts must use vertical annual bars, including enrolled
  students, students + OPT, study abroad, visits and trade. Apply consistently
  to the website, regional single-series panels and PNG/SVG exports.
  Baseline indexes and genuine multi-series comparisons need deliberate,
  clearly identified treatment, not accidental style changes.
- [ ] **UI-03: Provide the reverse graphs.** Make China-to-U.S. and U.S.-to-China
  views easy to reach. Where a genuinely compatible reverse series is unavailable,
  state that rather than substitute a stock, a regional total or another measure.
- [ ] **UI-04: Distinguish direction by colour.** China-to-U.S. and U.S.-to-China
  must use different, consistent colours across the interactive and downloaded
  versions. Keep geography/language comparisons distinguishable as well.
- [ ] **UI-05: Preserve every reported value.** The enrolled-only inbound series
  already contains all seven academic ending years 2019-2025. Do not make
  definition changes look like lost observations. Keep true missing years blank;
  hovering a blank year must not display a neighbouring year's value as its own.
- [ ] **UI-06: Label the COVID travel-restriction period throughout time charts.**
  Use a restrained shaded band and readable period label in native charts and
  both export themes. Verify official dates, exemptions and staged reopenings.
  Do not imply one universal ban, that all travel stopped, or that goods trade
  was prohibited. Do not put a time-period band on maps or categorical snapshots.
- [ ] **UI-07: Enforce the user's latest public-chart freshness rule.**
  Histories need a reported observation in 2023 or later; standalone snapshots
  must be from 2024-2026. Hide ineligible public plots and their controls/links,
  without deleting historical observations from complete downloads. A newer,
  differently defined statistic does not refresh an old series.
- [ ] **UI-08: Recheck size and appearance.** Compact, legible desktop and phone
  charts; no overflowing labels, empty-looking line fragments, oversized panels,
  clipped annotations, random points, overlapping legends or illegible axes.
- [ ] **UI-09: Replace the rejected Business view with current evidence.**
  Reconcile the existing `data/local/business-refresh-work/` candidate with the
  shared source. Keep AmCham Shanghai and German Chamber survey populations,
  fieldwork/performance years and investment positions separate. A survey
  percentage is not an enterprise count or a combined European sample.
- [ ] **UI-10: Recheck the reported faint header line.** Inspect the actual
  desktop/phone result and distinguish the unwanted line from intentional
  masthead and axis rules. Do not claim this fixed from source inspection alone.

**Current evidence, not completion:** the live enrolled-student screenshot was
reproduced. Its 2019-2025 values are present; the old line renderer splits at
population-definition changes. A repair candidate is under
`data/local/bilateral-repair/`; it is not the published fix.

## 2. Resolve data gaps one by one

Use `data/site/gap_review.csv` as the detailed source-attempt ledger. Update its
dates, recoveries and limitations when evidence changes. A failed download is not
proof that data do not exist: try alternative original reports, official archives,
government republications and compatible source tables.

- [ ] **DATA-01: Audit every displayed series.** Record its definition, direction,
  first/last reported period, missing internal periods and latest source checked.
  Prioritize genuinely missing observations over further cosmetic changes.
- [ ] **DATA-02: U.S. students in mainland China.** Seek a compatible annual
  U.S.-specific enrollment history after 2018 and the missing 2017 observation.
  Keep dated statements, degree students, credit participation and bounds separate.
- [ ] **DATA-03: Longer U.S.-host enrollment histories.** Extend enrolled-only
  counts before 2019 and Macau students + OPT before 2015 where verified.
  Do not replace enrolled-only counts with totals that include OPT.
- [ ] **DATA-04: Credit study-abroad histories.** Seek remaining early annual
  observations, especially before 2014. The China 2007/08 checkpoint is not
  a complete early history. Do not invent an unreleased 2024/25 annual total.
- [ ] **DATA-05: Degree mobility and other host enrollment.** Investigate missing
  UIS periods and U.S.-specific mainland/Hong Kong/Macau host figures.
  Empty responses and grouped "rest of world" categories are not country counts.
- [ ] **DATA-06: Recent U.S. visits to mainland China.** Continue seeking
  compatible all-mode annual counts after 2018. Keep the newer U.S.-resident
  air-travel survey separate; do not splice it into all-mode arrivals.
- [ ] **DATA-07: Remaining visitor-history gaps.** Check Macau 2000, the
  unreportable 2021 resident-air estimate, and genuinely leisure-only route counts.
  An apparent zero with positive survey responses must not become zero travel.
- [ ] **DATA-08: Keep current monthly/YTD travel data current.** Check Hong Kong
  and Macau against the actual latest published release. Match the same months
  across years; never annualize YTD or relabel an old response as a new month.
- [ ] **DATA-09: Trade history.** Seek compatible Macau services before 2018.
  Maintain separate goods/services and accounting definitions; never allocate a
  regional remainder or splice incompatible release vintages.
- [ ] **DATA-10: Annual immigration to the U.S.** Present annual China-to-U.S.
  immigration, keeping birthplace, nationality, new arrivals and adjustments
  distinct. Newly committed annual-admissions work still needs public-release
  and live-chart verification.
- [ ] **DATA-11: Annual immigration in the reverse direction.** Seek original
  U.S.-specific annual mainland admission/residence grants. Keep Hong Kong and
  Macau separate; do not substitute resident-stock benchmarks, visas or trips.
  Extend Macau approvals before 2010 if original evidence permits.
- [ ] **DATA-12: Bilateral immigrant resident stocks.** Continue investigating
  the unverified U.S.-Macau pairs without allocating grouped birthplace totals.
  Stock counts are not annual immigration flows.
- [ ] **DATA-13: Nationwide language-course enrollments.** Look for an actual
  post-2021 MLA release and newer national K-12 Chinese/Japanese/Korean learner
  counts. California alone is not nationwide coverage. A school offering a
  language is not a count of its students.
- [ ] **DATA-14: Trace the language-article evidence.** Check the original
  MLA/HESA tables and dates behind the cited material; integrate only genuinely
  new compatible observations. Keep U.K. evidence separate from U.S. evidence.
- [ ] **DATA-15: Business histories toward the present.** Check newer BEA
  U.S.-affiliate and European-country enterprise releases. Keep European
  countries and EU aggregates separate; do not fill confidential EU cells or
  substitute deal/project counts for operating enterprise counts.
- [ ] **DATA-16: Current Confucius program evidence.** Continue looking for a
  verified operating census or dated compatible observations. Operator directory
  listings, historical rosters, classrooms and cumulative successors remain
  separate; a 2026 retrieval date does not make an old operating count current.
- [ ] **DATA-17: Close the loop on each unresolved item.** Record the actual
  alternative sources tried, what they contain, and the remaining precise gap.
  Do not mark a data gap recovered merely because a substitute chart exists.

### Article source work: DATA-14

User-supplied lead: [The Economist article republished by Mint on October 27,
2023](https://www.livemint.com/specials/why-fewer-university-students-are-studying-mandarin-11698412205247.html).
It is a research lead, not a new 2026 data release or permission to reproduce
the article or its artwork.

- [x] **LANG-01: Identify the source article.** The supplied excerpt matches
  Mint's licensed Economist republication. Retain the exact title, publication
  date and clean source URL; do not copy the article into the project.
- [ ] **LANG-02: Integrate the actual MLA pandemic snapshot.** Verified Figure 1
  of the [fall-2022 newsletter snapshot](https://www.mla.org/content/download/191129/file/Fall-2022-NL-snapshot.pdf)
  gives 2016/2020 course registrations at the same 1,308 institutions:
  Chinese 33,561/26,528; Japanese 46,936/43,268; Korean 9,033/11,323.
  The roughly 21% Chinese decline is real, but this is not the national census.
  The source is already retained; its six selected count observations still
  need reproducible integration, validation and full-data exports.
- [ ] **LANG-03: Preserve the distinct national MLA history and seek a newer
  actual release.** Existing 2021-report-vintage Chinese counts are 54,248 in
  2016 and 46,492 in 2021, a different comparison. A 2024 collection announcement
  does not supply 2024 observations. Keep Chinese, Japanese and Korean separate.
- [ ] **LANG-04: Recover the HESA evidence with its real units and periods.**
  [BACS's primary 2021-22 report](https://bacsuk.org.uk/wp-content/uploads/2015/05/BACS-State-of-the-Field-2021-22-Report.pdf),
  Table 7, supplies the HESA-derived Chinese-studies history and quotes 1,535
  in 2012/13 versus 1,055 in 2021/22. These are subject-apportioned enrollments,
  not admissions, unique learners, or all people taking Mandarin. Preserve the
  JACS/HECoS classification boundary and do not join them to U.S. course counts.
- [ ] **LANG-05: Pursue newer, comparable U.K. data.** HESA publishes through
  2024/25, but direct Table 52 and its CSV returned 403 on October 24, 2026.
  The official data.gov.uk catalogue points to that same CSV, not a recovered
  alternate file. Check legitimate publisher reports and open data alternatives.
  Do not bypass restrictions, silently substitute broad Asian studies, or claim
  Japanese/Korean comparisons without those actual subject observations.
- [ ] **LANG-06: Respect the newer public freshness rule.** Retain useful older
  evidence in the complete data/research exports. A 2016/2020 snapshot or
  2021/22 U.K. endpoint does not by itself qualify as a current public chart.
- [ ] **LANG-07: Verify integration, not just source discovery.** Reconcile
  selected facts, source checksums and locators, definitions, CSV/JSON records,
  public eligibility and any plotted comparisons. Update DATA-14 only after
  the integration is actually verified; otherwise record the precise remainder.

## 3. Preserve the requested analysis and presentation

These are continuing requirements and final regression checks, not new scope.

- [ ] **SCOPE-01:** Students, tourists/visitor trips, goods and services in both
  directions, with history from 2000 where verified and current 2025/2026
  observations where actually released.
- [ ] **SCOPE-02:** Public regional comparisons cover mainland China, Hong Kong
  and Macau, not Taiwan; retain historical source data in full downloads.
- [ ] **SCOPE-03:** Mainland China left, Hong Kong/Macau right, with a shared
  year range and clearly separate vertical scales; stack on phones.
- [ ] **SCOPE-04:** Compare Chinese, Japanese and Korean separately, not a
  combined language total. Keep course enrollments, awards, program counts,
  school availability and AP participation distinct.
- [ ] **SCOPE-05:** Keep the confusing AP "standard group" presentation removed;
  label global versus U.S.-only exam populations accurately. Japanese is a
  benchmark; no AP Korean exam or zero Korean participation is invented.
- [ ] **SCOPE-06:** Preserve the 50-state/DC China-born resident map, count/share
  controls, denominators, margins of error and complete data. It is not an
  annual-arrivals map.
- [ ] **SCOPE-07:** Preserve U.S. opinions of China and Chinese opinions of the
  U.S., with historical and age comparisons. Keep original age bands and
  survey questions; do not present a social-media explanation as established
  causality.
- [ ] **SCOPE-08:** Preserve the dedicated Confucius Institutes/Classrooms page
  and chronological layout, subject to the newer public freshness rule.
- [ ] **SCOPE-09:** Keep Weibo correct and publicly readable: the full evidence
  directory, usable filters and source details, distinct denominators, and
  complete downloads. Unknown accounts are not absent accounts, and recovered
  posts are not all historical output.
- [ ] **STYLE-01:** Follow the `uk_decline` house style, with both Substack and
  The Margin of Error backgrounds, high-resolution PNG plus editable SVG,
  and category-organized output folders.
- [ ] **STYLE-02:** Keep the website outward-facing. No internal gap inventories,
  operational audit dumps or redundant introductory copy. Link to GitHub for
  the research detail; retain essential definitions and source attribution.
- [ ] **STYLE-03:** Verify the collective analysis remains on the website's
  Interactive Analysis page, uses the latest user-selected cover image, and
  appears before older analyses.

## 4. Previously published and verified milestones

These checks describe the named releases, not a claim that the new queue is done.

- [x] Built the bilateral dashboard, full-data downloads and categorized,
  two-background PNG/SVG exports.
- [x] Published split regional visitor panels and annual trade bars (`e2627bd`).
- [x] Published nationwide Chinese/Japanese/Korean degree comparisons through
  academic ending year 2025 (`7255f5a`).
- [x] Recovered multiple missing histories and newer alternative-source
  observations; the detailed source attempts are retained in the gap ledger.
- [x] Published the 50-state/DC count/share map using consistent 2020-2024 ACS
  five-year estimates (`8f11bac`).
- [x] Published the dedicated Confucius program page and complete supporting
  data (`9715c95`).
- [x] Redesigned and live-verified the Weibo page (`6966b45`): all 87 documented
  channels, pagination, deep links, filters and complete downloads.
- [x] Published Confucius counts on a real year axis (`190f72f`); verified
  desktop/phone/touch/keyboard/no-JS, both export themes and 611 served asset hashes.

## 5. Release gate: required before checking off the current fixes

- [ ] **VERIFY-01:** Run focused regressions for the new behavior, then the
  relevant integrated suite; resolve introduced failures.
- [ ] **VERIFY-02:** Independently reconcile all plotted years/values/units,
  bar and COVID-band geometry, direction colours and chart download links.
- [ ] **VERIFY-03:** Exercise repeated direction/geography/measure/index toggles,
  hover, touch, keyboard, resizing and no-JavaScript fallback at desktop, 390px
  and 320px widths. Inspect actual screenshots.
- [ ] **VERIFY-04:** Confirm complete CSV/JSON downloads, including historical
  and non-plotted records; no metadata-only or filtered-page-only downloads.
- [ ] **VERIFY-05:** Commit and push as **Hans Hanley**, with no Copilot
  authorship/co-author trailers. Preserve unrelated concurrent edits.
- [ ] **VERIFY-06:** Deploy the intended revision; verify the website's actual
  served manifest, relevant asset hashes and live toggle sequences. A local
  success or green deployment alone is insufficient.
- [ ] **VERIFY-07:** Update this file with the completion evidence and remaining
  gaps. Report only verified results; leave unfinished work unchecked.

## 6. Weibo research and unattended updates

These remain part of the project, even though the public directory redesign is
already verified. Preserve the separate population and access restrictions.

- [ ] **WEIBO-01: Finish permitted discovery or document source exhaustion.**
  The published cohort has 373/1,000 manually reviewed domains, not 373 confirmed
  accounts. Track the remaining frontier, do not repeat exhausted routes, and
  keep unknowns distinct from verified negatives.
- [ ] **WEIBO-02: Integrate the already captured pass 78 once.** Review the
  retained Lewiston Sun Journal evidence before adding it; do not repeat the
  blocked newspaper request or count the same pass twice. Verify the actual
  published review count afterward.
- [ ] **WEIBO-03: Resolve recoverable account/post bindings.** The historical
  NYT Chinese numeric recheck and VOA `legalwindow` binding remain unresolved.
  Candidate posts are not confirmed evidence and recovery is not total output.
- [ ] **AUTO-01: Make private daily collection operational.** The recorded
  scheduled-process access failure remains a blocker until authorization and
  a genuinely unattended collection run are verified. Do not change filesystem
  permissions, relocate the project or bypass the block without approval.
- [ ] **AUTO-02: Verify the entire unattended chain.** Confirm collection,
  cutoff advancement, deduplication, aggregates, complete exports, commit/push
  and actual website deployment. A successful aggregate build is not proof
  that private collection worked.
- [ ] **AUTO-03: Preserve truthful freshness after failures.** Keep the last
  successful data; distinguish build dates, source periods, successful retrievals
  and failed attempts. Do not convert collection failures to zero posting.
