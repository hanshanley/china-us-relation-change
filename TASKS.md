# U.S.-China analysis: requested work and completion checklist

Updated: October 24, 2026. This is the durable checklist for the user's requests.
Read this before starting or resuming work, and update it as each item is resolved.
Repeated requests are consolidated below, not silently discarded.

**An unchecked item is not finished.** Work in an isolated candidate, a passing
unit test, or a successful deployment alone does not establish completion.
Previously verified milestones are recorded separately from the remaining work.
This is the **single authoritative request ledger**. `PUBLICATION-TODO.md`
contains archived planning context, not a second set of completion statuses.
Agents coordinate file claims, active changes and handoffs in `AGENT-COMMS.md`;
read and update it before overlapping work.

**Verified release:** `2a4c646` is deployed and live-checked. The public freshness
gate, single-series annual bars, reverse controls, COVID shading and annual
immigration default are published. Official annual-admissions source recovery is
in `0c8cf49`. DATA-11 remains open: a verified forward series is not a recovered
reverse-flow series. Direction-specific colours, the Business replacement, the
reported header line and the remaining source gaps below are not declared done.

## 1. Finish the current graph corrections

Work through these in order; complete and verify a coherent release before
claiming that the website is fixed.

- [x] **UI-01: Fix repeated toggling.** Switching geography, direction, measure
  and display mode must never leave the previous plot, wrong data, wrong title,
  missing marks, stale tooltip, invalid index or a blank/broken chart.
  Reproduce the October 24 enrolled-student screenshot and toggle back and forth,
  not just reload the initial page.
- [x] **UI-02: Use bars for a single measured count.** Single-series annual
  reported-value charts must use vertical annual bars, including enrolled
  students, students + OPT, study abroad, visits and trade. Apply consistently
  to the website, regional single-series panels and PNG/SVG exports.
  Baseline indexes and genuine multi-series comparisons need deliberate,
  clearly identified treatment, not accidental style changes.
- [x] **UI-03: Provide the reverse graphs.** Make China-to-U.S. and U.S.-to-China
  views easy to reach. Where a genuinely compatible reverse series is unavailable,
  state that rather than substitute a stock, a regional total or another measure.
  Retain both directions in the existing dropdown; UI-11 removes the redundant
  reverse-direction button, not access to either graph.
- [ ] **UI-04: Distinguish direction by colour.** China-to-U.S. and U.S.-to-China
  must use different, consistent colours across the interactive and downloaded
  versions. Keep geography/language comparisons distinguishable as well.
- [x] **UI-05: Preserve every reported value.** The enrolled-only inbound series
  already contains all seven academic ending years 2019-2025. Do not make
  definition changes look like lost observations. Keep true missing years blank;
  hovering a blank year must not display a neighbouring year's value as its own.
- [x] **UI-06: Label the COVID travel-restriction period throughout time charts.**
  Use a restrained shaded band and readable period label in native charts and
  both export themes. Verify official dates, exemptions and staged reopenings.
  Do not imply one universal ban, that all travel stopped, or that goods trade
  was prohibited. Do not put a time-period band on maps or categorical snapshots.
- [x] **UI-07: Enforce the user's latest public-chart freshness rule.**
  Histories need a reported observation in 2023 or later; standalone snapshots
  must be from 2024-2026. Hide ineligible public plots and their controls/links,
  without deleting historical observations from complete downloads. A newer,
  differently defined statistic does not refresh an old series.
  Use measurement dates, not publication/retrieval dates, and check each series
  or snapshot separately. Preserve earlier points in qualifying histories.
  Explicitly test the U.S.-to-mainland enrolled series ending in 2018 through
  route controls, old deep links, cached selections and downloadable graphics;
  newer credit study abroad must not be relabeled as current enrollment.
- [x] **UI-08: Recheck size and appearance.** Compact, legible desktop and phone
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
- [ ] **UI-11: Remove the redundant reverse-direction button.** The October 24,
  6:44 p.m. screenshot identifies the large "View United States -> Mainland
  China" button as unnecessary and unattractive because the direction dropdown
  already provides this choice. Remove this button throughout the public topic
  pages; keep the existing dropdown and both available directions working.
  Remove obsolete button-specific styling, event handlers and test expectations.
  Verify the dropdown on desktop and phone and confirm the button is absent
  from the deployed site before checking this off.

**Completion evidence for the checked graph items:** the live site was verified
against the exact `2a4c646` source. It has 72 public plot models, 224 SVG exports,
66 enabled route choices and zero stale public plots. The obsolete mainland
enrollment and visitor graphic URLs return 404; forcing the retired enrolled
selection falls back to separately labelled credit study abroad, not invented
current enrollment. Both travel directions use annual bars and work through the
reverse button. Local validation passed 318 tests, the offline browser suite and
620 chart renderings / 1,143 hover checks with zero audit issues.

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
  Historical recovery: the exact 2017 count (23,911) is now independently
  sourced to Liu Xianjun's explicitly dated scholarly account. Six additional
  2000-2005 facts from Tian/Liu Table 3 reconcile with all ten retained
  2006-2015 overlaps. The full MOE-population history is continuous 2000-2018;
  the source's conflicting 2016 and mislabelled later rows are excluded.
  Component `354a39b` and `scripts/build_mainland_history.py` preserve every
  prior observation. This item remains open for a compatible post-2018 annual
  series; historical recovery does not restore a stale public chart.
- [ ] **DATA-03: Longer U.S.-host enrollment histories.** Extend enrolled-only
  counts before 2019 and Macau students + OPT before 2015 where verified.
  Do not replace enrolled-only counts with totals that include OPT.
- [ ] **DATA-04: Credit study-abroad histories.** Seek remaining early annual
  observations, especially before 2014. The China 2007/08 checkpoint is not
  a complete early history. Do not invent an unreleased 2024/25 annual total.

  Source checkpoint **`80a2e06`**, pushed October 24: 118 additional observations
  preserve all 2,638 prior records exactly. Enrolled-only histories now cover
  2007-2025 for every geography; Macau OPT-inclusive totals cover 2000-2025;
  credit-study-abroad counts cover every academic ending year 2000-2024.
  Pre-2007 enrolled-only counts remain unverified because the earlier reviewed
  tables combine non-degree and OPT. The original 2013 Taiwan total (21,867)
  differs from the retained NCES republication (21,897); that difference is
  disclosed without overwriting the retained source. All 342 frozen-source
  tests passed, the public build succeeded, complete 2,756-row CSV/JSON exports
  reconciled, and repeated recovery changed no data hashes. **Combined website
  deployment and live verification remain with the release owner.**
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
- [x] **DATA-10: Annual immigration to the U.S.** Present annual China-to-U.S.
  immigration, keeping birthplace, nationality, new arrivals and adjustments
  distinct. FY2020-FY2025 new permanent-resident arrivals are published as the
  default, with adjustments for people already in the U.S. on a separate chart.
  Open the page on the annual view, not the resident map; keep the map and stocks
  as separate measures. Preserve published exact/rounded precision and totals
  rather than forcing independently rounded components to sum exactly.
- [ ] **DATA-11: Annual immigration in the reverse direction.** Seek original
  U.S.-specific annual mainland admission/residence grants. Keep Hong Kong and
  Macau separate; do not substitute resident-stock benchmarks, visas or trips.
  Extend Macau approvals before 2010 if original evidence permits.
  Check U.S.-specific Hong Kong permanent admissions separately. NIA/OECD
  alternatives have not yet supplied a verified comparable mainland series;
  this remains an open gap, not zero immigration or proof that none exists.
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
- [ ] **DATA-18: Current AP counts and the U.S.-only population.** Seek actual
  newer Chinese/Japanese participant counts and a nationwide U.S.-only series.
  Global annual administrations, graduating cohorts and the standard group
  are different populations. Preserve the documented absence of an AP Korean
  exam without inventing zero Korean learners or an equivalent exam series.
- [ ] **DATA-19: School availability and immersion inventories.** Preserve the
  national January 2024 school-availability estimates, including the unreportable
  Korean result, and review newer evidence. Keep the 2025 immersion inventory
  separate from older incompatible directories and respondent enrollment
  totals. Neither indicator resolves the national learner-count gap.
- [ ] **DATA-20: Current opinion histories and age comparisons.** Maintain
  both directions using actual fieldwork periods and original age groups.
  Keep favorable percentages, warmth means, survey modes and sample populations
  distinct. Remove stale-only historical alternatives under UI-07; do not
  treat the year of a new article as the year of its underlying survey.

### Article source work: DATA-14

User-supplied lead: [The Economist article republished by Mint on October 27,
2023](https://www.livemint.com/specials/why-fewer-university-students-are-studying-mandarin-11698412205247.html).
It is a research lead, not a new 2026 data release or permission to reproduce
the article or its artwork.

- [x] **LANG-01: Identify the source article.** The supplied excerpt matches
  Mint's licensed Economist republication. Retain the exact title, publication
  date and clean source URL; do not copy the article into the project.
- [x] **LANG-02: Integrate the actual MLA pandemic snapshot.** Verified Figure 1
  of the [fall-2022 newsletter snapshot](https://www.mla.org/content/download/191129/file/Fall-2022-NL-snapshot.pdf)
  gives 2016/2020 course registrations at the same 1,308 institutions:
  Chinese 33,561/26,528; Japanese 46,936/43,268; Korean 9,033/11,323.
  The roughly 21% Chinese decline is real, but this is not the national census.
  The six observations are committed in `1cad87d`; deterministic collection,
  validation and full JSON/CSV exports passed 25 focused tests. Live release
  `b168790`, deployment `40139669213`, retained all 384 language rows, including
  these six counts; all 496 served asset hashes matched.
- [x] **LANG-03: Preserve the distinct national MLA history and seek a newer
  actual release.** Existing 2021-report-vintage Chinese counts are 54,248 in
  2016 and 46,492 in 2021, a different comparison. A 2024 collection announcement
  does not supply 2024 observations. Keep Chinese, Japanese and Korean separate.
  Live source check on October 24, 2026 confirmed that the report catalogue and
  actual fall workbook still end in 2021. Receipt:
  `data/local/language-article-recovery/national-release-check.json`.
- [ ] **LANG-04: Recover the HESA evidence with its real units and periods.**
  [BACS's primary 2021-22 report](https://bacsuk.org.uk/wp-content/uploads/2015/05/BACS-State-of-the-Field-2021-22-Report.pdf),
  Table 7, supplies the HESA-derived Chinese-studies history and quotes 1,535
  in 2012/13 versus 1,055 in 2021/22. These are subject-apportioned enrollments,
  not admissions, unique learners, or all people taking Mandarin. Preserve the
  JACS/HECoS classification boundary and do not join them to U.S. course counts.
  **Correction ready, not yet verified live:** `74ba244` retains eight Table 7
  totals and gives the early quote its own series/comparability group. The
  original 2016 BACS report labels the matching 1,535 as full-time and gives
  part-time separately. Equivalence with the later total is unverified; do not
  import the article's 31% as a like-for-like decline. Corrected full exports
  contain 384 rows, preserve all 369 original observations, and pass 25 tests.
  Handoff to the combined release owner is recorded locally; keep this item
  open until the corrected dataset is served and checked.
- [ ] **LANG-05: Pursue newer, comparable U.K. data.** HESA publishes through
  2024/25, but direct Table 52 and its CSV returned 403 on October 24, 2026.
  The official data.gov.uk catalogue points to that same CSV, not a recovered
  alternate file. Check legitimate publisher reports and open data alternatives.
  Do not bypass restrictions, silently substitute broad Asian studies, or claim
  Japanese/Korean comparisons without those actual subject observations.
  Additional source review: the BACS archive's nominal 2022-23 report link
  opens a funding report, not newer enrollments. The earlier 2016 report
  identifies a study-mode mismatch; it is not a harmonized newer history.
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
- [x] **DOC-01: Clean up the repository README in the `uk_decline` style.**
  Replaced the Weibo-first introduction with a centered project title/navigation,
  overview, chart preview, linked analyses, chart guidance, automatic updates,
  setup and data-integrity sections. Existing detailed collector instructions
  are preserved in `docs/WEIBO.md`. Verified GitHub Markdown rendering, all
  relative links/anchors, the tracked preview image and all nine live analysis
  links on October 24, 2026. This is documentation work, not a new chart release
  or completion of the remaining data/UI tasks.
- [ ] **DOC-02: Require persistent coordinated work and complete request intake.**
  Put the user's instruction to keep targeting all outstanding actionable tasks
  together in `AGENTS.md`, require communication/ownership/handoffs through local
  ignored `AGENT-COMMS.md`, and keep every request and correction in this ledger.
  Reconcile the saved exchange, Weibo, screenshot and README requests against
  the task IDs; preserve explicit blockers and the separate implementation,
  commit, deployment and live-verification states. Verify the committed
  instructions and keep the communication file off the public current tree.

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
- [x] Published both directions of public opinion and age comparisons
  (`2176776`), with complete observations in `data/site/opinions.json`.
  The new freshness rule still requires retiring the obsolete alternatives.
- [x] Recovered and pushed six annual Chinese-nationality U.S. admission totals,
  new-arrival counts and adjustment counts for FY2020-FY2025 (`0c8cf49`).
  The immigration dataset has 133 observations with prior values preserved;
  publishing the new default and finding the reverse series remain DATA-10/11.
- [x] Published the dedicated Confucius program page and complete supporting
  data (`9715c95`).
- [x] Redesigned and live-verified the Weibo page (`6966b45`): all 87 documented
  channels, pagination, deep links, filters and complete downloads.
- [x] Published Confucius counts on a real year axis (`190f72f`); verified
  desktop/phone/touch/keyboard/no-JS, both export themes and 611 served asset hashes.

## 5. Release gate: required before checking off the current fixes

- [x] **VERIFY-01:** Run focused regressions for the new behavior, then the
  relevant integrated suite; resolve introduced failures.
  Wire `scripts/check_public_freshness.py` into the refresh workflow and verify
  actual enabled choices, measurement dates, nulls, zeros and snapshot cutoffs.
- [ ] **VERIFY-02:** Independently reconcile all plotted years/values/units,
  bar and COVID-band geometry, direction colours and chart download links.
  Audit the filtered public figure directory, not the deliberately complete
  historical research archive.
  Values, units, bars, COVID geometry and links pass for `2a4c646`; the remaining
  direction-colour request is tracked by UI-04 and prevents closing this item.
- [x] **VERIFY-03:** Exercise repeated direction/geography/measure/index toggles,
  hover, touch, keyboard, resizing and no-JavaScript fallback at desktop, 390px
  and 320px widths. Inspect actual screenshots.
- [x] **VERIFY-04:** Confirm complete CSV/JSON downloads, including historical
  and non-plotted records; no metadata-only or filtered-page-only downloads.
- [x] **VERIFY-05:** Commit and push as **Hans Hanley**, with no Copilot
  authorship/co-author trailers. Preserve unrelated concurrent edits.
- [x] **VERIFY-06:** Deploy the intended revision; verify the website's actual
  served manifest, relevant asset hashes and live toggle sequences. A local
  success or green deployment alone is insufficient.
  Confirm retired stale graphic URLs are no longer published and the complete
  downloadable datasets still retain their historical observations.
- [x] **VERIFY-07:** Update this file with the completion evidence and remaining
  gaps. Report only verified results; leave unfinished work unchecked.

Release evidence: website deployment **40139087280**; live source revision
**`2a4c646cedb9e6dacf21887f68af39f1cac9211c`**; **496 served assets** verified
byte-for-byte, **nine complete datasets**, and **five retired stale-graphic URLs**
confirmed 404. Evidence logs and screenshots are under `data/local/freshness/`.
The live collective browser and freshness/reverse-flow checks both passed.
These checkmarks refer to this verified release, not to all remaining data work.

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
- [ ] **WEIBO-04: Preserve the requested interactive coverage-first view.**
  The user's later preference supersedes Weibo-over-time as the primary public
  presentation because recovery is biased toward recently accessible posts.
  Keep a useful interactive account/evidence directory with explicit missing
  and unknown percentages, labelled denominators, filters and source details.
  Distinguish accounts, publisher groups and the selected top-1,000 U.S. domains;
  unknowns are not verified absent accounts. Recheck the actual deployed view
  after integration, rather than treating an older redesign as final evidence.
- [ ] **WEIBO-05: Preserve rolling research measures and the daily update request.**
  Retain the originally requested rolling-30-day active-account/outlet counts,
  recovered post totals and daily-average measures as separately labelled
  research outputs, not exhaustive historical activity or popularity estimates.
  The later directory-first preference changes the primary public display,
  not the need for accurate collection, deduplication, complete permitted
  exports and daily refresh. Coordinate permitted recurring discovery under
  WEIBO-01 and actual unattended collection under AUTO-01/AUTO-02; do not
  equate an aggregate rebuild or scheduled prompt with successful collection.
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

## 7. Resume and update protocol

1. Read this file and inspect Git status before resuming. Identify the active
   task by its stable ID; preserve other contributors' pending changes.
2. Work through actionable items in queue order. Record blocked attempts and
   concrete alternatives instead of repeating an unchanged request or marking
   the task complete. A source gap stays open until suitable data are verified.
3. Update `data/site/gap_review.csv` and the source/method documentation when
   evidence changes. The public website should link to research detail rather
   than display this internal checklist.
4. Separate recovery, implementation and publication milestones. For each
   completed item, record its evidence: source/data location, commit, and, when
   public-facing, the deployment and actual live checks.
5. Commit/push coherent progress as Hans Hanley, then update the checkboxes here.
   Do not create another competing checklist or declare the whole project done
   while these data, publication or automation items remain unresolved.
6. Continue working with the other agents until the requested tasks are
   completed and verified. A checklist, passing component, pushed commit or
   handoff is a milestone, not permission to stop while actionable work remains.
7. Use the local `AGENT-COMMS.md` throughout the work for file ownership,
   messages, blockers, integration order and release coordination. If one item
   is blocked, document it and pursue the next independent actionable task;
   do not silently abandon it or bypass a source/permission restriction.
8. Map every new request or screenshot to an existing ID or add a distinct task
   with its acceptance conditions. Preserve all requirements when consolidating
   duplicates, and do not mark a new report fixed using an earlier release's
   checks. Keep the communication file private and the completion ledger here.

### Request coverage index

This index points to the actual tasks; it is not another checklist or a claim
that the listed work is finished.

| User requirement | Tasks |
|---|---|
| Two-way students, visitors and trade; history from 2000, current 2025/2026 data and legitimate alternatives | SCOPE-01; DATA-01 through DATA-09; DATA-17; UI-12/UI-13 |
| Annual permanent immigration in both directions and longer histories, not stock or visa substitutes | DATA-10/DATA-11/DATA-12/DATA-21 |
| All-state China-born count/share map, not California alone | SCOPE-06; VERIFY-03/VERIFY-04 |
| National Chinese/Japanese/Korean learning comparisons, AP, actual course enrollments, degrees, schools and immersion | SCOPE-04/SCOPE-05; DATA-13/DATA-14/DATA-18/DATA-19; LANG-01 through LANG-07; UI-14 |
| U.S. and European businesses in China, Chinese businesses in the U.S., France/UK/other major countries, current count histories and German bars | UI-09; DATA-15; BIZ-01 through BIZ-04 |
| Opinions in both directions, age comparisons and honest survey definitions | SCOPE-07; DATA-20 |
| Confucius change over time and removal of the repetitive Operating status column | SCOPE-08; DATA-16; UI-15/UI-16 |
| Weibo integration, readable evidence, complete data, remaining discovery and automatic collection | SCOPE-09; WEIBO-01 through WEIBO-03; AUTO-01 through AUTO-03 |
| Mainland China left and Hong Kong/Macau right; no Taiwan in public comparisons | SCOPE-02/SCOPE-03 |
| UK-project house style, both backgrounds, PNG/SVG category folders, consistent colors, compact charts and final polish | STYLE-01/STYLE-04; UI-02/UI-04/UI-08; BIZ-04 |
| Hover/tap/keyboard values, correct toggling, years, definitions and no random or missing plotted points | UI-01/UI-05/UI-12/UI-13; VERIFY-01 through VERIFY-04 |
| Current public histories since 2023 and snapshots from 2024-2026, with full archives preserved | UI-07; VERIFY-04/VERIFY-06 |
| Public-facing copy, GitHub rather than internal coverage walls, collective analysis placement and the "Cooling Ties Across the Harbor" cover | STYLE-02/STYLE-03; DOC-01 |
| Remove redundant direction button and redundant Language degree view | UI-11/UI-14 |
| Audit all graphs/data; retain complete downloads and verify actual publication | DATA-01/DATA-17; VERIFY-01 through VERIFY-07 |
| Periodic commits/pushes as Hans Hanley, no Copilot attribution | VERIFY-05; AGENTS.md |
| Keep targeting all tasks with other agents and coordinate rather than stopping at handoffs | This protocol; AGENTS.md; local AGENT-COMMS.md |
6. Keep targeting the remaining actionable tasks with the other agents.
   A finished subtask, test run, commit, deployment or handoff is a checkpoint,
   not permission to stop the overall work. Reread this ledger and the latest
   local communication messages, claim the next suitable task or resolve an
   agreed integration dependency. If an item is blocked, record the actual
   blocker and alternatives and continue other work; do not leave actionable
   tasks idle, bypass restrictions or manufacture completion.
7. Record every new user request and screenshot correction here before acting.
   Consolidate repetitions, retain the latest requirements and explicitly
   identify superseded presentations. Keep local file ownership, messages and
   handoffs in ignored `AGENT-COMMS.md`; never force-add or publish that file.

### Request-coverage crosswalk

The October 24 request audit checked the saved user messages from the original
exchange and Weibo sessions, later graph/Confucius follow-ups, and the README
session. This index consolidates repeated requests; it does not add a competing
set of completion statuses. New follow-ups still require intake under step 7.

| User requirement | Authoritative task IDs |
|---|---|
| Two-way student, visitor, goods and services histories from 2000 toward the present; recover gaps through alternative sources | SCOPE-01; DATA-01 through DATA-09; DATA-17 |
| Complete early student data and explain the exact study-abroad screenshot | DATA-02 through DATA-05; UI-05, UI-12, UI-13 |
| Mainland China separate from Hong Kong/Macau; Taiwan excluded from public comparison graphs | SCOPE-02, SCOPE-03 |
| Bars for single measures; consistent directional colours; correct repeated toggles | UI-01, UI-02, UI-04; BIZ-04 |
| Both directions accessible, without the redundant reverse button | UI-03, UI-11 |
| Remove stale public histories/snapshots without deleting the complete data | UI-07; LANG-06; VERIFY-04 |
| COVID travel-restriction context throughout applicable time charts | UI-06 |
| Annual permanent immigration both ways over a long history, separate from stocks; state count/share map | DATA-10 through DATA-12; DATA-21; SCOPE-06 |
| Actual nationwide Chinese/Japanese/Korean learners, courses, awards, school availability and distinct AP measures; trace the supplied article | DATA-13, DATA-14, DATA-18, DATA-19; LANG-01 through LANG-07; SCOPE-04, SCOPE-05 |
| Remove the redundant bachelor's-degree language visualization | UI-14 |
| U.S. opinions of China and Chinese opinions of the U.S., including original age groups | DATA-20; SCOPE-07 |
| Current business evidence and longer country-count histories, Chinese businesses in the U.S., France/UK/other country coverage | UI-09; DATA-15; BIZ-01 through BIZ-04 |
| Confucius counts over time; remove the repetitive Operating status column while preserving the data | DATA-16; SCOPE-08; UI-15, UI-16 |
| Verify media accounts across the top-1,000 U.S. domains, recover permitted posts and keep missingness explicit | SCOPE-09; WEIBO-01 through WEIBO-04 |
| Daily updates and rolling-30-day research measures without recent-recovery bias or false freshness | WEIBO-05; AUTO-01 through AUTO-03 |
| House style, readable PNG/SVG, both backgrounds, topic folders, split panels, compact plots and final whitespace polish | STYLE-01, STYLE-04; UI-08; SCOPE-03 |
| Hover/touch/keyboard/no-JS, full data/value/visual audits and the faint header-line defect | UI-10; VERIFY-01 through VERIFY-04 |
| Public-facing copy, no internal gap dumps or redundant introduction; collective analysis first with the latest selected cover | STYLE-02, STYLE-03 |
| Periodic commits/pushes as Hans Hanley with no Copilot attribution; deploy and check actual served results | VERIFY-05 through VERIFY-07 |
| README in the `uk_decline` style | DOC-01 |
| Keep working together until verified completion; track all requests and keep agent communications private/local | DOC-02; resume protocol above; `AGENTS.md` |

## 8. Latest screenshot regressions: October 24, 6:54-7:01 p.m.

Prioritize these concrete examples in the current chart/source repair. Earlier
release checks do not establish that these newly reported cases are fixed.

The 6:55:30 p.m. screenshot repeats **UI-11**: remove the large extra
"View United States -> Mainland China" / opposite-direction button, not the
existing direction dropdown. Check every public topic, desktop and phone;
do not restore the rejected button merely to satisfy an old regression test.

- [ ] **UI-12: Fix and explain the study-abroad screenshot.** Reproduce
  `Screenshot 2026-10-24 at 6.54.29 PM.png`: Students, mainland China,
  United States -> mainland China, academic-credit study abroad, reported levels.
  The 2007/08 observation (13,165, shown at ending year 2008) is isolated from
  the 2014-onward bars by a large 2009-2013 gap. Investigate the original
  source/extraction, not just the appearance; DATA-04 owns recovery of those
  early periods. Preserve the valid early point and calendar spacing, do not
  interpolate or insert zeros, and explain genuinely unresolved gaps concisely.
  Make the latest actual academic year clear; an axis tick at 2025 is not proof
  of a released 2024/25 observation. Check the selected blue title/axis text
  and tooltip behavior without confusing ordinary browser selection with
  incorrect chart state. Verify this exact route after repeated toggles,
  on desktop/phone and in the deployed page.
- [ ] **UI-13: Audit China-to-U.S. graphs for intuitive meaning and full data.**
  The user reports that these graphs are confusing and omit substantial data.
  Review every enabled inbound measure separately, not only the outbound
  screenshot. Make route, unit, population and period readable: enrolled
  students versus students + OPT, visitor trips, goods/services and annual
  immigration are not interchangeable or all literal new arrivals.
  Reconcile every available canonical year with the visible bars and exact
  tooltips, then recover genuine source gaps under DATA-01/DATA-03 and the
  relevant route tasks. Do not drop existing years at definition boundaries,
  silently switch populations, mistake unreported years for zero, or describe
  a broader substitute as the missing series. Exercise both directions and
  repeated dropdown switches in final live checks. Coordinate chart behavior
  with `chart-repair` and historical student recovery with `history-recovery`.
- [ ] **UI-14: Consolidate the redundant Language degree chart.** The user
  identifies the graph in `Screenshot 2026-10-24 at 7.01.19 PM.png` as
  superfluous to the existing bachelor's-degree language-learning view.
  Its 2018/19 tooltip shows Chinese **431**, Japanese **569** and Korean
  **61** awards; these match `ipeds:bachelors` and its Japanese/Korean
  counterparts. Identify the overlapping or mislabeled selector/panel and
  remove or consolidate the redundant presentation, retaining one clear,
  correctly titled bachelor's-degree comparison. Do not delete the underlying
  observations or accidentally merge genuinely distinct graduate-degree,
  course-enrollment or school-availability measures.
  Preserve complete CSV/JSON downloads and correct academic periods, units and
  tooltips. Verify the surviving view and absence of redundant options on
  desktop/phone and the deployed site before checking this off.

## 9. Long histories, two-way permanent immigration and final visual polish

The October 24 follow-up reinforces **SCOPE-01**: try to recover comparable
annual histories back to at least **2000**, earlier where suitable, and aim
through **2026 where observations have actually been released**. This applies
to the actual data, not simply the axis limits. A short recent series does not
fulfil the long-history requirement; unpublished years and unresolved internal
gaps must remain explicit, without invented values or interpolation.

- [ ] **DATA-21: Complete permanent-immigration histories in both directions.**
  The user explicitly requires **China-to-U.S. and U.S.-to-mainland-China over
  time**, with the 2000-2026 coverage target above. Extend the verified forward
  permanent-resident admissions history before 2020 and toward the latest
  released period; retain earlier compatible observations already recovered.
  Complete the reverse annual permanent-residence grants/admissions under
  **DATA-11**, using U.S.-specific original evidence, rather than presenting
  only one direction or two isolated stock benchmarks. Keep mainland China,
  Hong Kong and Macau distinct. Do not substitute temporary residence permits,
  visas, work/student permits, resident stocks, trips or all-foreign totals.
  Preserve nationality versus birthplace, fiscal versus calendar years, new
  arrivals versus status adjustments, and source-definition breaks; do not
  splice incompatible series into a cosmetic continuous history. Verify both
  complete time-series downloads and actual plotted years/values/definitions.
  Missing reverse-flow evidence remains an open gap, not zero immigration.
  **DATA-10's checked recent forward-series milestone does not close this task.**
- [ ] **STYLE-04: Beautify the final plots after substantive work is complete.**
  After data recovery/integration, functional fixes and final graph regeneration,
  review the actual desktop/phone charts and both export themes for wasted
  canvas and excessive outer margins, as shown in the user's Goods trade
  screenshot. Rebalance plot area, title/subtitle, axes, legends and source-note
  spacing without clipping or crowding; verify high-resolution PNG and editable
  SVG exports. Preserve every value, unit, meaningful axis, missing-year gap,
  source attribution and essential disclosure. This is a final visual pass,
  not a substitute for DATA-21 or permission to make short histories appear
  complete. Leave unchecked until the resulting charts are actually reviewed.

## Business coverage and consistent bars: October 24, 7:03 p.m.

The 7:03:08 p.m. screenshot shows U.S.-parent affiliates ending in 2023; the
7:03:55 p.m. screenshot shows German enterprise counts as lines. These requests
extend UI-09 and DATA-15. Newer chamber-survey percentages or investment
positions do not complete the requested operating-company count histories.

- [ ] **BIZ-01: Extend business-count histories toward 2025.** Seek actual
  measured 2024/2025 affiliate or enterprise counts using additional compatible
  primary sources, rather than stopping at the current U.S. 2023 endpoint.
  Keep historical coverage and verify source thresholds, ownership definitions,
  sector coverage and reporting periods. A 2025 publication date does not make
  its older measurements 2025 data; surveys, investment dollars and newly formed
  firms are not substitutes for the stock of operating businesses.
- [ ] **BIZ-02: Add Chinese businesses operating in the United States.**
  Recover a genuine reverse-direction count history, not merely U.S. companies
  in China. State whether counts are controlled affiliates, enterprises,
  branches or unique parents and identify the immediate/ultimate ownership
  basis. Keep mainland China, Hong Kong and Macau distinct. Exports, investment
  flows and visa counts do not fill this business-presence request.
- [ ] **BIZ-03: Expand beyond the U.S., Germany and Norway.** Add France, the
  UK and other prominent investing countries with verified businesses in China.
  Record a clear country-coverage roster and pursue additional national or
  compatible international sources for missing/current histories. Norway is
  not a stand-in for Europe; national counts and overlapping EU aggregates
  must not be summed. Label source differences and unresolved countries.
- [ ] **BIZ-04: Make the Business count charts consistently use bars.**
  Replace Germany's line presentation with annual count bars, matching the
  treatment of the other business-count graphs on the website and in both
  export backgrounds. Preserve Eurostat/Bundesbank as separately identified
  source histories, using grouped or separate panels where needed; do not sum
  overlapping estimates or imply a compatible splice. Verify years, exact
  values, tooltips, source breaks and desktop/phone rendering on the live site.

## 10. Confucius page: October 24, 7:02 p.m. screenshot

- [ ] **UI-15: Remove the repetitive Operating status column.** Remove the
  column headed "Operating status" and its repeated "Not verified" cells from
  the operator-directory table. Keep the program names and source labels,
  explain the listing/operation distinction once, and preserve all original
  fields and unknown statuses in the complete CSV/JSON downloads.
- [ ] **UI-16: Lead with Confucius change over time.** Restore a meaningful
  chronological presentation of qualifying institute histories; the page must
  not lead with an open directory or treat one directory retrieval as a trend.
  Apply the existing history-since-2023 rule to actual histories rather than
  filtering every historical observation as a standalone snapshot. Continue
  requiring 2024-2026 for genuine standalone snapshots; do not restore the
  classroom-only history ending in 2019. Preserve source-specific populations,
  missing years, campus-only counts, bounds and approximate counts; do not
  append directory entries as verified operating counts. Retain annual bars,
  COVID context, exact tooltips, complete downloads and both export themes.
  Show the real historical endpoint rather than implying a 2026 operating
  census. Verify desktop/phone, keyboard/touch/no-JS and the deployed page
  before checking off either item.
