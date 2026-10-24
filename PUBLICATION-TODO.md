# Public dashboard completion checklist

Updated: October 24, 2026.

This is the working checklist for the user's requests. Keep it current as work
progresses. A task is not finished just because code was written or a local graph
looks plausible. Check the deployed website, its actual data and its downloads
before checking off a publication task.

## Current work: finish in this order

- [x] Inventory stale graphs throughout the website, including individual route
  controls, regional comparisons, supplemental charts and graphic downloads.
- [ ] **Remove stale public graphs everywhere.** A history needs a nonmissing
  observation from **2023 or later**. A standalone snapshot must refer to
  **2024–2026**. Source upload, publication or retrieval dates do not make an old
  measurement current. Remove stale choices, empty panes, old deep links and
  unlinked graphics from the public build. Keep complete archived data downloads.
  Status: implemented; final regression and live verification pending.
- [ ] **Use bars for graphs measuring one series.** Apply to interactive charts
  and both PNG/SVG backgrounds, not just goods trade or one student chart.
  Preserve calendar spacing, missing years, real zeros, exact hover values and
  source-definition changes. Keep multi-series comparisons and baseline indices
  distinct.
  Status: implemented; final regression and live verification pending.
- [ ] **Expose reverse-direction graphs.** Make both U.S.-to-China and
  China-to-U.S. travel, student and trade views easy to reach. Add reverse links
  and controls where data exist; never invent a reciprocal series or substitute
  a different population without labelling it.
  Status: implemented; navigation and live verification pending.
- [ ] **Show annual immigration, not just resident stocks.** Open the immigration
  page with annual Chinese-nationality new permanent-resident arrivals to the
  U.S. Keep approvals for people already in the U.S. separate from new arrivals.
  Preserve the state map and resident-stock charts as separate views.
  Status: official FY2020–2025 arrivals and adjustments recovered and published
  in the source data; revised default charts await final live verification.
- [ ] **Investigate the reverse annual immigration series.** Find a verified
  U.S.-to-mainland-China annual count with the correct nationality, destination,
  legal status and reporting period. Do not use tourist arrivals, all-foreigner
  permits, Macau counts, or changes in resident stocks as substitutes.
  Status: not verified in reviewed official sources. This remains an explicit
  data limitation, not a completed reverse-flow graph and not zero immigration.
- [ ] **Mark the COVID travel-restriction period.** Add restrained shading and a
  readable label to dated charts covering 2020–2022, including downloadable
  graphics. Explain that restrictions, exemptions and reopening dates differed;
  do not call it a universal travel ban. Link original U.S., mainland, Hong Kong
  and Macau notices.
  Status: implemented; final small-screen, export and live verification pending.
- [ ] **Run the final integrated checks.** Reconcile every displayed value,
  source year, unit, direction, bar position, COVID band and export. Test desktop,
  phone, keyboard, touch, no-JavaScript fallbacks, and every enabled public
  route/indicator. Fix actual failures instead of weakening the checks.
- [ ] **Commit, push and deploy the complete changes.** Commit as Hans Hanley,
  with no Copilot attribution. Preserve other work in the shared checkout.
- [ ] **Verify the deployed result.** Check the exact served source revision,
  all manifest asset hashes, complete datasets, retired stale URLs, reverse
  navigation, annual immigration charts, bar charts and COVID labels. Only then
  mark the publication tasks above complete.

## Earlier requested features: preserve and recheck

- [x] Two-way student, travel, goods and services histories, with mainland China,
  Hong Kong, Macau and Taiwan kept statistically distinct in complete data.
- [x] Separate Students, Travel and Trade public topics, with regional
  comparisons accessible within their respective topics.
- [x] Mainland China on the left and Hong Kong/Macau on the right where both
  panes have eligible observations; independent vertical scales are labelled.
- [x] Complete data downloads rather than metadata-only exports.
- [x] The existing house plotting style and both The Margin of Error and
  Substack export backgrounds.
- [x] Interactive value inspection using hover, touch and keyboard.
- [x] Public-facing presentation rather than internal audit logs and lengthy
  coverage diagnostics; sources and methods available through GitHub/details.
- [x] Nationwide Chinese, Japanese and Korean comparisons, not a
  California-only comparison or an indiscriminate collection of languages.
  Preserve actual educational populations; newer degree awards do not update
  older course-enrollment measurements.
- [x] U.S. state map with China-born resident counts and their share of each
  state's foreign-born population, covering all 50 states and D.C.
  The 2020–2024 ACS five-year estimate is not a 2024-only count or annual flow.
- [x] Opinion graphs in both directions, with original age bands and methods.
  Percentage-favorable answers and 0–100 warmth scores stay separate.
- [ ] Apply the new freshness policy to these earlier features too; do not keep
  an obsolete plot merely because an earlier task asked for it.

## Data and presentation rules for every remaining item

- Recover current data from original sources and try valid alternative public
  sources when one delivery channel is unavailable.
- Preserve the precise observation period, population, unit, source and
  comparability boundary. Do not fabricate missing years or convert missing
  values, suppressed cells or unverified reverse routes to zero.
- Keep earlier observations within an eligible history. The freshness rule is
  not a request to delete historical data or replace complete downloads with
  a filtered metadata extract.
- Do not imply that old counts became current because a report was uploaded,
  republished or retrieved recently.
- Preserve survey means, age bands, probability versus quota samples, fiscal
  versus calendar periods, academic ending years, and approvals versus arrivals.
- Check that charts are compact, readable and uncluttered on phones as well as
  desktop. No clipped labels, misleading axes or disconnected unexplained data.
- Record genuinely unavailable data as such and leave its recovery task open;
  report the limitation rather than silently declaring everything complete.

## Verification evidence

Source-recovery logs, immutable test candidates, browser checks, plot audits and
screenshots for the current work are under `data/local/freshness/` (not public).
The final commit, deployment run, live source revision and validation results
will be recorded here after verification.
