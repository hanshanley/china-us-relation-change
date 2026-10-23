# Bilateral exchange dashboard

Open `site/index.html` directly. It is a self-contained static publication; no
web server, analytics, CDN, API key or deployment account is needed to read it.
Hosting integration is intentionally deferred.

The exchange package is independent of the repository's Weibo media project.
Do not replace the latter's package configuration, CLI, data or tests.

## Refresh and build

Python 3.9+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-exchange-dev.txt
.venv/bin/python scripts/update.py
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_*.py -q
```

`update.py` checks official releases and reconciles the full small-source history.
`build_site.py` performs **no network requests**; it reproduces the website,
complete downloads, high-resolution PNG figures and optional SVGs from
committed publication tables. Building alone needs only
`requirements-exchange.txt`; the development requirements also supply the image
and browser checks.

| Location | Purpose |
|---|---|
| `src/us_china_exchange/` | Model, source parsers, refresh orchestration, static rendering |
| `data/site/observations.json` | Canonical observations, including explicit missingness and provenance |
| `data/site/coverage.json` | All four geographies, both directions, eight distinct measures |
| `data/site/sources.json` | Published source health, release vintage and recorded check dates |
| `data/local/exchange/raw/` | Local raw responses named by SHA-256; ignored, not redistributed |
| `data/local/exchange/check.json` | Actual latest attempt, including unchanged checks and failures |
| `site/` | Generated offline website, accessible tables, complete CSV/JSON downloads |
| `outputs/figures/` | PNG/SVG charts organized by category, then publication background |
| `outputs/figures/index.html` | Offline chart catalog with human-readable titles and download links |
| `tests/fixtures/exchange_reviewed_2026-10-21.json` | Frozen numeric review checkpoints, not a constraint on future source revisions |

Every downloaded observation has its definition, direction, unit, period basis,
status, exact source request, release/vintage label, retrieval timestamp and
raw-response checksum. `exchange.json` also contains sources and coverage.
CSV exports contain full observation rows, not just a source inventory.
Raw third-party PDFs and workbooks are deliberately not published.
The complete JSON also includes source access/reuse policies. Source availability
does not imply permission to automate retrieval or commercially republish it.
IIE retrieval is paused, its retained observations are explicitly a reviewed
snapshot, and IIE/MGTO reuse restrictions are shown on the pages and affected
figure footnotes. Publication-background exports do not grant publication rights.

Canonical validation requires each `series_id` to match its source, origin,
destination and measure fields. Years must be integers; calendar period labels
must be the matching `YYYY` for annual data or `YYYY-MM` for monthly/YTD data,
with the month matching the validated ending boundary. Academic and reporting
labels follow their own year-only rules.

## Plot styling and publication backgrounds

Charts follow the `uk_decline` project's `vizstyle` house settings: serif type,
near-black ink, muted grey labels, light horizontal gridlines (0.6 opacity),
0.8-width left/bottom axes, no top/right frame, and italic collecting-source
notes. Mainland China retains its deep-red country identity (`#7B2D26`);
Hong Kong, Macau and Taiwan use distinct blue, gold and green house-palette
colours. Both bilateral directions retain the same partner colour.

`src/us_china_exchange/theme.py` translates the reference settings into native
SVG so the offline build does not depend on another checkout or Matplotlib.
SVGs remain the interactive/vector representation, but **PNG is the primary
publication download**. Each PNG is **3000 by 1800 pixels**, with larger titles,
axes and source text, not merely the previous tiny image upscaled. Titles and
source notes are part of both downloadable formats, not only the website.

`resvg-py` rasterizes the SVGs entirely offline using bundled, unmodified
[DejaVu Serif 2.37](https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37)
regular, bold and italic fonts. Their license is retained in
`src/us_china_exchange/static/fonts/LICENSE` and copied into the offline site.
System fonts are disabled for PNG generation so macOS and Linux use the same
glyphs and metrics. The renderer is pinned to a release with binary wheels for
both local Python 3.9/macOS and CI Python 3.12/Linux.

Each category is in its own folder: `students`, `visitors`, `goods_trade` and
`services_trade`. Within each category, every series has both backgrounds:

| Version | Background | Output and download directories |
|---|---|---|
| The Margin of Error | Warm `#F7F5F0` | `outputs/figures/<category>/themarginoferror/`, `site/figures/<category>/themarginoferror/` |
| Substack | Article `#F5F5F5` | `outputs/figures/<category>/substack/`, `site/figures/<category>/substack/` |

These match the reference project's original house plots and its separate
`outputs/page_background/` Substack copies, respectively. Only the background
changes: data, dimensions, typography, colours and line breaks are identical.
For example, mainland-China-to-U.S. goods trade is
`outputs/figures/goods_trade/substack/bea-CHN-USA-goods.png`.
The previous flat SVG directories are retired; the build removes only their
known generated filenames, not unrelated figures.
When a series is suppressed, disappears from the canonical input, or loses all
positive values for its log view, its obsolete generated exports are removed
from both figure trees. User-owned figures are preserved. Removing the frozen
Weibo input also withdraws its known pages, aggregate downloads and figures.

Use the chart's **Background** selector to preview either version; all PNG/SVG
download links and the category catalog work without JavaScript. On narrow
screens, charts retain an 800-pixel minimum width instead of shrinking labels
to unreadable text. They scroll horizontally by touch or keyboard, initially
showing the most recent years; exact tables remain available underneath.
Downloads explicitly contain reported values even when the interactive chart
is showing an index.

### Combined regional comparisons

Open `site/comparisons.html`, linked from the dashboard. These new comparisons
include **mainland China, Hong Kong and Macau only**; Taiwan is excluded, while
the existing individual series and source dataset are retained. The same
`PARTNER_COLORS` mapping drives every individual and combined chart: China deep
red, Hong Kong blue and Macau gold.

Comparisons are separated by measure and direction; student populations,
visitor definitions, goods and services are never combined into one total.
Unavailable geographies remain labelled rather than acquiring a zero line.
Raw-value and logarithmic views are provided in both publication backgrounds;
logarithmic views omit genuine zeros, leave gaps, and never add pseudocounts.
Missing years and population-definition breaks remain disconnected.

Combined PNG/SVG exports live under
`outputs/figures/<category>/comparisons/<background>/` and the matching site
directory. The offline catalog includes both views. Macau goods retain their
different customs accounting and a dashed line, with an explicit caveat against
treating them as identical to the other geographies' BEA accounting.

### Weibo research graphs

`site/weibo.html` includes monthly recovered-post counts and monthly counts of
distinct channels represented in the recovered sample, alongside documented-channel
identity evidence, recovered-corpus coverage, publication years, and text completeness.
They use the same house typography
and both publication backgrounds, under `outputs/figures/weibo/<background>/`
and `site/figures/weibo/<background>/`. The figure catalog links all of them.

These are **research coverage statistics**, not a census, posting-activity trend,
audience/popularity ranking or causal explanation for exchange flows.
Current profile evidence does not establish current activity, direct U.S.
operation, present-day control or continuing licensing. No recovered
posts does not mean an account posted nothing. `source_full` means the entire
accessible source body, not an independently verified complete original.
Missing publication years remain unobserved, not zero-activity years.

To refresh after local Weibo collection and registry loading:

```sh
.venv/bin/python scripts/build_weibo_summary.py --db data/local/weibo.sqlite
```

The command reads the database in a read-only transaction, checks registry
alignment, excludes unconfirmed accounts and publications on/after historical
attribution cutoffs, and freezes `data/site/weibo_summary.json`. Publication
years use Asia/Shanghai, not UTC. Raw post text is never published.
The committed snapshot contains complete per-account, month, year and completeness
aggregates, source hashes, latest collection time, exclusion counts and
requested windows; the site supplies JSON and CSV downloads of those aggregates.
The raw private corpus retains its separate rights and redistribution limits.

Version 4 adds the complete `monthly` series and `site/downloads/weibo-months.csv`.
Monthly bins use Asia/Shanghai publication dates and the requested collection
windows, including months with zero recovered posts. Unrequested months are not
connected. `observed_accounts` counts distinct channels with recovered posts, not
publishers or all active accounts. `partial_window` identifies months not fully
covered by the requested window, independently of source recovery completeness;
the plots mark these months without extrapolating them to a full-month estimate.
For the current fixed window, October 2026 ends on October 21. Monthly totals
reconcile to annual and account totals; private post text is not included.
Older snapshots remain readable but do not invent missing monthly data.
The collective publication's interactive selector preserves the same monthly
calendar positions, distinct-channel counts and partial-month markers on mobile.

Version 2 snapshots distinguish documented historical/current channels from
resolved numeric UIDs, including historical vanity-only URLs without inventing
an account binding. Complete account downloads include UIDs, handles, display
names, operator relationships, U.S.-inclusion bases, notes and all curated
evidence. The CSV evidence column is a JSON array, not a truncated excerpt.
The legacy `confirmed_accounts` field counts documented channels, not known
numeric identities; use `resolved_numeric_accounts` for the latter.
Version 1 snapshots remain readable, but their missing UID resolution is
explicitly identified as unrecorded rather than inferred.

When the adjacent `data/discovery/us_top1000_accounts.jsonl` assessment exists,
the snapshot includes its checksum and reconciled cohort totals. The selected
domains are SCImago U.S.-classified digital-reputation results, **not the top
1,000 by traffic** or an independently audited current ownership/nationality
list. Homepage screening and manual review are separate. Unknowns and
unresolved candidates are not verified negatives; an absent assessment does
not establish any absence rate. The complete domain-level decisions remain
in `data/discovery/us_top1000_accounts.{csv,jsonl}`.

Version 3 adds a primary-source recheck, distinct from registry flags and
database/export reconciliation. The adjacent
`data/discovery/weibo_primary_audit.json` is bound to registry bytes and
canonical post content hashes. Read-only SQLite returns hashes rather than
raw post bodies for the freshness check. Registry/body changes or later
unreviewed source conflicts affecting existing posts stop publication until
the source audit is refreshed; unchanged counts alone are insufficient.
Versions 1 and 2 remain readable without inventing source-audit results.

Complete per-account recheck statuses, methods, source URLs/hashes and notes
are retained in the frozen JSON and account CSV. Rechecked numeric bindings,
historical bindings still pending recheck, and a vanity-only unresolved UID
remain separate. The dated [primary-source audit](../reports/weibo_primary_source_audit.md)
documents actual text corrections and remaining gaps. Its complete post-source
CSV is audit metadata, explicitly not the private full-text corpus.

The ordinary offline site build reproduces Weibo figures from that frozen
snapshot without requiring the database. Daily exchange refreshes **do not**
collect Weibo or silently advance its snapshot date. Refresh and commit the
aggregate input explicitly after new research; the workflow also checks pushes
to this input and its builder. Existing Weibo collection/analysis code and the
private database are not modified by the chart integration.

### Chinese-language learning

Open `site/language-learning.html`. Eleven chart families address the college
boom/reversal, comparison with other languages, school-age pipeline and narrow
specialist-degree pipeline. They use the existing house typography, stable
language colours and both publication backgrounds. PNGs are 3000 by 1800;
PNG/SVG exports live in `outputs/figures/language_learning/<background>/`
and the matching `site/figures/` directory.

These indicators remain separate from canonical bilateral flows:

| Indicator | Verified history and interpretation |
|---|---|
| MLA national college registrations | Fall 2002, 2006, 2009, 2013, 2016 and 2021, using the 2021 report's historical table. Levels, Chinese share of all language registrations, and Chinese/Japanese/Korean/all-language indexes with 2013=100. Registrations are not unique learners. |
| Matched college institutions | Same complete-count responding institution IDs in 2013 and 2021. Nonresponse placeholders and institutions with any unreported language-count row are excluded; explicit zero-language respondents are retained. This selected cohort is not a national census or a causal estimate. |
| AP annual administration | Total Chinese and Japanese global participation, 2007-2025. Not U.S.-only counts or a census of language learners. No AP Korean exam is listed; use the separate MLA college comparison for Korean. |
| Historical U.S. AP cohorts | Public-school graduating classes 2007-2013; Chinese exams taken at any point during high school. Not the administration year, all U.S. schools or unique learners. Separate from global annual counts; current U.S.-only administration history remains a documented gap. |
| IPEDS degree awards | Academic years ending 2000-2025, narrow CIP 16.0301, 50 states/DC, Title IV degree-granting institutions. Bachelor's, master's and doctoral awards are separate; second majors/certificates are excluded from 2001 onward. Reported or imputed awards are not unique people, proficiency measures or all China specialists. |
| Immersion inventories | CAL 2011, ARC 2021 and Nexus 2025 snapshots use different universes. Categorical bars deliberately do not connect them into a growth trend. |

Annual lines break on missing years and definition changes. MLA lines connect
actual census rounds, without inventing intervening annual observations. IPEDS
2000 lacks separate major numbering; doctoral classification changes in 2010,
from the old doctoral category to research/scholarship doctorates. Both boundaries
break chart lines. Original flags, revision members and filters are retained.

AP years are exam administrations, not graduating classes. The AP comparison
shows only total Chinese and Japanese exam participation; the standard-group
chart and its interpretive discussion have been withdrawn. The reviewed subset
records remain in the complete source downloads for reproducibility, but are
not plotted or promoted as a capacity proxy.
The AP comparison has verified counts for 2007-2025. Published
2026 score percentages have blank participant counts; no counts are inferred.
The final subject-specific PDFs take precedence over older program summaries
or retrospective webpage totals when those vintages disagree.

The Economist's August 24, 2023 article is interpretive context, not the numeric
source for the college census. Its rounded 2016-2020 decline uses the separate
MLA pandemic snapshot of 1,308 matched institutions, not the full 2021 census.
Proposed employment, geopolitical, cultural and technology explanations are not
a demonstrated causal decomposition.

The older K-12 estimate of 227,086 enrollments refers to a 2014-15-era mixed
reported/modelled reference period, published in 2017; it is not a current
learner census. Nexus's 335 U.S. inventoried programs are separate from its
103 survey responses, including one Hong Kong response. The associated
34,341 enrollments are therefore not published as a national U.S. learner count.
There is no summed learner total across settings.

`data/site/language_learning.json` freezes reviewed numerical aggregates,
definitions, coverage and source URLs, retrieval dates and SHA-256 checksums.
The page provides the entire JSON, every raw observation in
`language-observations.csv`, and every derived index/share/chart point in
`language-chart-values.csv`. Nothing depends on a private workbook or database
when building offline.

Source retrieval is deliberately manual, not part of daily exchange refreshes:

```sh
.venv/bin/python scripts/build_language_data.py --data-only
.venv/bin/python scripts/build_language_data.py --ap-only --data-only
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_language.py -q
```

The first command uses checksummed local assets where available; `--refresh`
explicitly fetches the reviewed public resources again. `--last-degree-year`
selects the final IPEDS survey year, default 2025; a missing annual file fails
the candidate rather than truncating history or inventing zeros. A complete
validated candidate replaces the frozen input only after all sources succeed.
The ordinary build performs no network calls. Removing the frozen input
withdraws its known page/downloads/figures but preserves user-owned files.

The itemized October 23, 2026 review resolved the apparently missing 2025
degree files by following NCES's actual **Complete Data Files** entry: new
releases use `/ipeds/complete-data-files/`, not the legacy
`/ipeds/datacenter/data/` location. `HD2025.zip` and `C2025_A.zip` supply
**292 bachelor's, 28 master's and 11 research/scholarship doctoral Chinese
language/literature awards** for July 1, 2024-June 30, 2025 under the same
institution/major filters. The July 28, 2026 release is explicitly provisional;
source checksums and reported/imputation flags are retained.
`scripts/build_language_data.py --ipeds-only --last-degree-year 2025 --data-only`
updates only that requested degree year and preserves every other observation.

The dated itemized source review is frozen in `data/site/gap_review.csv`,
exported intact as `downloads/gap-review.csv`, and included in the complete
exchange JSON. Each case records the exact route/population, reviewed period,
recovered figures or qualified bounds, remaining limitation and primary links.
Recovered, partial, confidential, not-reported, unverified and outside-source-
population cases are deliberately distinct. This is an October 23, 2026
investigation snapshot, not an automatically advancing claim that every
source has released current data. The dynamic coverage matrix and complete
observation CSV/JSON remain available alongside it.

Only numerical aggregates and original visualizations are published, not
source PDFs, workbooks, report artwork or exam questions. MLA ordinary-use
restrictions and unverified commercial reuse permission remain disclosed in
source notes and figure footnotes; publication backgrounds do not grant rights.

### Business presence

Open `site/business-presence.html`. **China is the host in every chart.**
The page leads with annual U.S. and European business-presence histories and
a full year-by-year table, not two endpoint counts. It does not chart U.S.
businesses located in Europe.

| Measure | Verified history and definition |
|---|---|
| U.S.-parent affiliates in China | All 24 annual fiscal-year observations, 2000-2023. Affiliate entities, including holding companies, not distinct parents, branch offices or annual openings. Nonbank coverage before 2009; reporting thresholds and benchmarks create breaks. |
| EU-reporting groups in China | Historical EU27 membership (including UK, excluding Croatia) supplies 2009, 2011 and 2012. Current EU27 membership (excluding UK, including Croatia) supplies 2014-2022, with 2021 estimated. Different memberships/classifications are distinct traces, not a joined splice. Confidential and unavailable years remain gaps. |
| UK-controlled enterprises in China | Ten annual values, 2010-2019. Eurostat history through 2017; ONS revised 2018 and 2019 estimates. The 2018 source/sector boundary is disconnected. ONS total activity includes agriculture. No outward-affiliate counts from 2020 onward verified; do not use newer inward-affiliate or FDI statistics as substitutes. |
| Norwegian-controlled enterprises in China | Fourteen annual observations, 2010-2023. Eurostat NACE B-S except O; 2021 method boundary disconnected. Norway is outside the EU and is not silently added to a Europe total. |
| Supplementary U.S. parent-company benchmarks | Only 2004, 2009, 2014 and 2019 are verified. They appear in a collapsed background section, not as the main time series or an annual census. Foreign-affiliate ownership begins at 10%, not necessarily majority control; reporting exclusions apply. No interpolation. |

The U.S. affiliate reporting cutoff changes from $7 million through 2003 to
$10 million in 2004-2008 and $25 million from 2009, based on assets, sales or
net income/loss. These are nominal, not inflation-adjusted, cutoffs.
Benchmark remeasurement and coverage can create level changes; chart lines
break in 2004, 2009, 2014 and 2019. Parent benchmark observations are isolated.
No incompatible full-history percentage is calculated.

European origins are not destinations: the EU, UK and Norway series all refer
to enterprises operating **in China**. This is selected European coverage,
not a comprehensive all-Europe total; Switzerland and other unverified origins
are not invented or allocated. Eurostat uses ultimate control and different
unit/sector coverage from BEA's size-qualified affiliates. U.S. and European
levels are in separate panels, not a matched ranking or ratio. NACE revisions,
membership changes, source changes and the 2021 EBS boundary stay disconnected.
Missing/confidential values never become zero, and confidential totals are
not reconstructed from member-country data.

As verified October 22, 2026, the latest BEA activity release covers 2023
(preliminary); the 2024 release is scheduled for November 20, 2026. The source
release and definitions are retained in the manifest. Later years are not
invented or inferred from investment-position data.

The frozen input is `data/site/business_presence.json`; the page exports the
complete JSON, every source observation in `business-observations.csv`, and
every raw/derived chart point in `business-chart-values.csv`. All five chart
families have 3000-by-1800 PNGs and SVGs under
`outputs/figures/business_presence/<background>/` and the mirrored site tree.
Colors identify investor origins consistently: U.S. deep red, current EU blue,
historical EU grey, UK gold and Norway green. The four annual chart families
lead the page; the fifth is the supplementary U.S. benchmark panel.
Obsolete U.S.-in-Europe plots are withdrawn from both figure trees and catalogs.

```sh
.venv/bin/python scripts/build_business_data.py --data-only
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_business.py -q
```

The collection command is explicit and manual; `--refresh` re-fetches its
reviewed public assets rather than using checksummed local files. It writes
the frozen candidate only after all sources and validation succeed.
Daily exchange jobs only rebuild these indicators offline; they do not fetch
new business data. The shared indicator SVG renderer preserves the existing
language figures byte-for-byte. Removing a frozen input withdraws its known
page, downloads and charts, never user-owned figures.

The collective publication at
`https://www.themarginoferror.com/china-us-relations/` is built separately:

```sh
.venv/bin/python scripts/build_exchange_publication.py --output data/local/collective-publication
.venv/bin/python scripts/check_exchange_publication.py --site data/local/collective-publication
```

This offline export covers the collective analysis: student exchanges, visitor
trips, immigration, goods/services trade, language learning, business presence and public
Weibo research aggregates. It never publishes raw posts or source reports.
The masthead, topic navigation, responsive charts and indicator selectors share
one publication layout. Screen-sized charts preserve reported values, gaps,
method boundaries, regional colours and the dashed Macau customs distinction.
Original 3000-by-1800 PNGs and SVGs in both backgrounds remain unchanged.

Annual exchange data extend through 2025 where available, with separately
labelled 2026 partial-year observations; these are not annualized or inserted
into annual charts. College and business series retain their actual earlier
cutoffs. AP global participation must not be relabelled U.S.-only. Weibo
research coverage remains distinct from posting activity or popularity.
Source permission warnings and complete datasets are retained. Without
JavaScript, the initial chart, all topic charts and full tables remain readable.
The provenance manifest records the source revision and public-asset checksums.
The website deployment rebuilds committed snapshots without collecting data.

### Language-enrollment comparisons

Language now defaults to actual Chinese/Japanese/Korean college registrations
at the six observed MLA fall-census rounds, 2002-2021. The separate 2014-15-era
school snapshots show national Chinese/Japanese enrollment estimates (227,086
and 67,909) and reported high-school language programs (1,144 Chinese, 433
Japanese, 43 Korean). The 936 Korean respondent enrollments are retained in the
complete download and explanatory text, not compared with national estimates.
Availability is not unmet demand; no combined national learner total is
calculated. `scripts/build_language_data.py --schools-only` reviews those
additional school observations without replacing the other language series.

### Travel and immigration

The item-by-item follow-up adds a separate `student_estimates.json` evidence
table for recent American study in China. The original NCUSCR and Brookings
transcripts, an archived official ambassador post, the ambassador's own
licensed commentary, and USCET's March 2026 working-group report support five
dated statements/estimates from 2023-2026. These are not a replacement for the
MOE annual enrollment population. USCET's **fewer than 2,000 per year** is an
annual-participation upper bound, not 2,000 currently enrolled students.
The 2025 **just over 1,100** statement remains a lower bound. No annual line
joins these figures, and publication/statement dates are not invented census
dates. Both JSON and CSV contain the actual values, bounds and source assets.
Review with `.venv/bin/python scripts/build_student_estimates.py`.

For that first missing item, the current MOE 2024 national catalogue was
checked beyond its first page: all 60 national tables, including the actual
higher-education student table. It reports 271,064 international students of
all nationalities but no U.S.-specific row. The exact UIS U.S.-origin degree
mobility request for China from 2019 onward returns an empty `records`
array. Neither an all-nationality total nor cumulative youth exchange-program
visits is substituted for U.S.-nationality enrollment.

The October 23, 2026 re-audit recovered 54 older student observations from
NCES Digest tables and a U.S. Commerce country guide. Chinese, Hong Kong and Taiwanese
Open Doors totals now cover every academic ending year 2000-2025. The
underlying statistical provider remains IIE, but these historical rows cite
the government republication actually retrieved; direct IIE automated access
remains paused, and no existing value was replaced.

MOE U.S.-nationality student reporting observations now cover **2006-2016
and 2018**, separately from academic-credit study abroad, tertiary degree-only
counts and enrolled-at-one-date stocks. Seven missing years were recovered
from Zhang Hongwei and Li Chenying's China Agricultural University Library
statistical report, table 3, which explicitly cites the China Education
Yearbook and MOE; the three overlapping ministry years agree exactly.
Original ministry records take precedence. The 2016 table is reproduced in
China National Radio's education-briefing report. The actual MOE 2017 release
lists leading origin countries without a numeric U.S. row: 2017 is not guessed.

The original NCES *Condition of Education 2010*, table A-40-2, also adds
**13,165** U.S. academic-credit study-abroad participants in mainland China
in **2007/08**, plotted at academic ending year **2008**. Its country count
is not the table's rank, percentage, or older 1997/98 count. This population
excludes Americans taking entire degrees abroad and is never joined to MOE
reporting totals. `scripts/build_contact_backfill.py --education-only`
reviews the education additions without rechecking tourism.

The State Department's original **EducationUSA 2021 Student Mobility Facts
and Figures**, East Asia and Pacific compilation, restores another **23
observations** without accessing IIE: 16 missing credit-study-abroad counts
(academic ending years **2014-2017**, all four geographies), Macau's
**2015-2017** OPT-inclusive totals (**573, 586, 605**), and enrolled-only
counts for **2020/21** (**251,933** mainland Chinese; **4,841** Hong Kong;
**351** Macau; **14,642** Taiwan). The latter add the three exact published
academic-level counts, excluding OPT, rather than applying rounded shares.
Pandemic-expanded enrolled counts have a separate comparison identity from
2023/24 onward; they cannot supply a like-for-like growth rate.

The four relevant country pages are physical PDF pages **12, 19, 29 and
56**. Raster-chart value labels are manually reviewed against a pinned
checksum, never read from approximate line coordinates. All **12** retained
credit-chart overlaps (2018-2020 across four geographies), all four Macau
2018-2021 totals and all four 2021 sums reconcile before the merge. A conflicting
**7,923** label in the Hong Kong 2017 inbound chart is not imported:
the retained NCES country count **7,547** takes precedence. No other historical
Hong Kong stock-chart cells are imported from that report. The current
EducationUSA catalogue directs 2022 onward to IIE; this is not treated as
permission to resume automated IIE retrieval. Together with the additional
18 Taiwan NCES rows, this pass adds **41** education observations and preserves
every field of all **2,537** previously retained observations.

HKTDC's official U.S. profile republishes HKTB **nationality** arrivals for
2023-2025. Its 2023 U.S. count is 596,958, not the 594,752 residence-based
count in other releases. These populations are intentionally not treated as
continuous. Retained
browser-visible report text is checksummed as such, not described as the
original HTML or PDF. Review explicitly with
`.venv/bin/python scripts/build_contact_backfill.py`; `--refresh` rechecks
only the public republications, never IIE. All candidates are validated in
a temporary staging tree before canonical files are updated.

The itemized tourism recovery restores **every annual Hong Kong arrival year
from 2000 through 2025**. C&SD's 2003 Annual Digest (table 9.20, printed page
200) supplies 2000-2002; MGTO's original 2008, 2013, 2018 and 2023 reports
republish the overlapping HKTB residence histories. Through 2022 the population
is **U.S. residence**; from 2023 the retained observations use **U.S.
nationality**. The line breaks at this boundary, and a 2020-based index/change
across it is unavailable. C&SD table 650-80001 documents the October 16, 2024
arrival-card abolition and change of classification.

MGTO's U.S. market profiles separately supply directly reported **January-June
2025: 489,417** and **January-June 2026: 552,528** Hong Kong arrivals. Its older
2024 vintage differs by one arrival from the retained HKTDC figure; it does not
overwrite that observation. No partial value is inferred from a percentage.

Run `.venv/bin/python scripts/build_tourism_backfill.py` for the reviewed
Hong Kong history and Macau 2025/2026 monthly recovery; `--refresh` fetches new
copies and rejects changed pinned historical documents pending review. All
updates are validated in staging before publication. Macau's latest reviewed
period is **August 2026**, with **11,713** arrivals in the month and **109,693**
in January-August; matching 2025 counts are **11,755** and **104,008**.
The reviewed 2025 monthly history is now complete through December: September
**8,322**, October **15,467**, November **17,502**, and December **17,161**.
All twelve monthly counts sum to **162,460**, matching both the direct
December cumulative report and the independently retained annual value.
The September 2026 endpoint currently returns an **August-labelled** PDF;
strict period-caption checks prevent importing those August figures as
September or inventing a zero for the missing month.
The two PDF columns are read independently, because a country's monthly and
cumulative market ranks can differ. An omitted top-ten row is not zero.
May 2025 is absent from the monthly top ten; the complete U.S. first-half
profile directly reports 11,241 arrivals (3,409 sea + 6,427 land + 1,405 air).
That primary table fills the omission. Every other overlapping first-half
monthly count reconciles with the top-ten publications.

The separate USTR Macau country summary resolves both previously empty
services directions in **2025**: U.S. exports **$434.0 million**, U.S. imports
**$208.0 million**. Their sum agrees with the reported **$642.0 million**
services total and their difference with the **$226 million** surplus.
These are direct estimated country figures, not goods/services subtraction,
affiliate sales, or an allocation from Other Asia/Pacific. Quoted rounded
amounts are normalized to USD without implying dollar-level accuracy. Older
values are not reverse-engineered from rounded percentage or dollar changes.
The USTR adapter is included in normal revision-aware refreshes.
Genuinely single-year plots use a labelled bar snapshot in both
publication backgrounds and the interactive view. One verified year is not
drawn as a historical trend or left as an almost-empty line chart.

An actual **December 18, 2025 archive of USTR's original government page**
also supplies **2024** services exports **$440 million** and imports
**$34 million**. These are directly printed figures, not reconstructed
from the newer page's growth rates. The archived aggregate incorrectly
says **$474 billion**. The manual adapter corrects only that known aggregate
unit for validation, after pinning the original statistical passage:
the separately quoted **$406 million** surplus and same-year **$864.0
million** combined trade less **$390 million** goods independently confirm
the **$474 million** component sum. No directional value is changed or
allocated. The original raw checksum and capture URL remain on both rows;
the semantic checksum excludes Wayback's variable toolbar.

The archived 2024 estimates and current 2025 release have separate
comparison identities: no line segment or growth rate implies identical
revision vintages. Captions call this a **release-vintage**, not a population,
break. The two independent annual estimates render as restrained labelled
bar snapshots in both static backgrounds and responsive charts, with exactly
the two observed years, not nearly empty disconnected-dot plots. Earlier services years remain unverified. Review just these sources
with `.venv/bin/python scripts/build_tourism_backfill.py --services-only`.
Normal daily refreshes retain the reviewed archive rows without pretending
to retrieve them again. A fresh requested September 2026 tourism report on
October 23 still returned August captions, so no September count is added.

The original DSEC *Tourism Statistics 2002*, table 1 (physical pages 53-54),
also supplies U.S.-**residence** arrivals for **2001: 73,607** and
**2002: 76,904**. Each total reconciles with its separately reported sea,
land and air counts. These are not the report's table 12 U.S.-nationality
totals (80,740 and 86,648) or its combined U.S./Canada hotel-guest figures.
The pre-2008 inclusion of non-resident workers/students matches the retained
early series; its existing 2008 and 2015 population breaks are preserved.
Macau annual history is now continuous from 2001, while 2000 remains under
source review.

The public explorer disables unpopulated choices for each selected route,
announces any necessary measure fallback, and offers separately labelled
newer/broader series where appropriate. Incompatible indexes fall back to
reported levels rather than blanking verified data. Complete coverage and
unresolved gaps remain visible and downloadable. Sparse census/benchmark
charts label actual observation years when they fit.

The collective site has direct **Travel & tourism** and **Immigration** tabs.
The travel view uses the same reviewed visitor-arrival observations, including
2025 annual values and 2026 partial-year NTTO updates. All-purpose visits are
not relabelled leisure tourists, and trips are not unique people. The selector
does not offer a leisure-only series without verified values for the displayed
geographies.

The manual travel review adds NBS country-attributed U.S. visitor arrivals to
mainland China for 2000-2018. Separately, NTTO SIAT supplies U.S.-resident
air-travel estimates to mainland China and Hong Kong for 2019 and 2022-2025.
The 2025 and 2026 Q1-Q2 selections now explicitly deselect Q3 and Q4 with
ordinary checkbox clicks; modifier-click was opening a macOS context menu.
Their January-June values are read directly, not inferred by subtracting rounded
totals: China 442,000 in 2025 and 474,000 in 2026; Hong Kong 304,000 and 251,000.
No unverified 2020-2021 value is inferred. Survey estimates, all-mode border arrivals and
leisure-only tourists are not spliced together. Later all-mode mainland
arrivals and pre-2023 U.S.-nationality Hong Kong arrivals remain unverified.

`data/site/immigration.json` freezes 102 observations from five primary assets:
four OHSS workbooks/archives and the UN DESA International Migrant Stock 2024
workbook. UN stocks cover six published 1 July benchmarks (2000, 2005, 2010,
2015, 2020 and 2024), in both directions for mainland China/Hong Kong.
Mainland-China destination uses U.S. citizenship; the other reviewed routes
use birthplace. They are resident stocks, not annual arrivals or grants.
No separate reviewed U.S.-Macau stock is reported; absence is not zero.
Attribution and CC BY 3.0 IGO terms accompany the selected UN aggregates.

OHSS country-of-birth histories cover fiscal years 2000-2024 for
mainland China, Hong Kong and Macau. These are grants of lawful permanent
residency, including both new arrivals and adjustments by people already in
the U.S.; birthplace is not nationality or a departure country. Historical
source vintages remain explicit; FY2015-2024 cells are rounded to the nearest
ten rather than presented as exact counts.

A separate FY2025 nationality snapshot reports the DHS China category:
65,670 total grants, 27,020 new arrivals and 38,650 adjustments. These are the
report's annual Total columns, not sums of quarterly values. Nationality is
not birthplace, so the snapshot is not joined to the historical lines or used
to infer a year-over-year change. U.S. fiscal years end September 30.
No comparable annual U.S.-to-mainland-China permanent-residency series has been
verified here. China-wide totals for foreign permits or border crossings do
not fill that bilateral gap.

```sh
.venv/bin/python scripts/build_immigration_data.py
.venv/bin/python scripts/build_travel_data.py
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_immigration.py -q
```

Retrieval is explicit/manual; `--refresh` rechecks the five immigration source
assets. The ordinary build is offline. JSON, all source observations as CSV,
and every plotted value as CSV are complete downloads. Both publication
backgrounds have matching PNG/SVG figures under `immigration/`. Missing or
confidential cells stay distinct from zero; raw source files are not published.

## Definitions and comparisons

- History starts in 2000 **where verified**. The publication does not pretend
  each series is complete from that year or has the same latest period.
  Goods, BEA services and visitors to the U.S. now have annual coverage from
  2000. Macau-bound arrivals start in 2003, Taiwan-bound arrivals in 2012, and
  student coverage varies by source. Missing earlier years are not estimated.
- Student measures are distinct: enrolled-only, including OPT, internationally
  mobile degree students, and U.S. academic-credit study abroad. Enrolled-only
  IIE counts are available for only two recent years; there is no 2020 baseline
  for that specific series. Academic years retain their labels and use ending
  years on the chart. Exact academic start/end dates are not invented.
- IIE's OPT-inclusive population expands in 2020/21–2022/23 to include online
  coursework from outside the U.S. regardless of visa status, then returns to
  the pre-pandemic definition in 2023/24. Distinct comparison identities break
  chart lines at 2020/21 and 2023/24; the full-history index is unavailable
  because those populations cannot all share the 2020 baseline. Latest
  2024/25-versus-2019/20 comparisons remain valid. Study-abroad participation
  does not inherit this international-student definition break.
- UIS reporting years are not physical-presence years. Fractional source
  estimates are preserved, including in exact tables and downloads. Reporting
  years retain their year label but have null exact start/end dates, just as
  academic years do; neither implies a January–December reference period.
  UIS magnitude and qualifier codes remain in observation notes. `NA` becomes
  null with `not_applicable` status, not an observed zero; `SUPP` stays
  `suppressed`, and `INCLUDED` becomes `included_elsewhere`. `NIL` retains its
  genuine source zero and flag. `LOWREL` is labelled `low_reliability`, and
  national/UIS estimates are `estimated`. `INCLUDES` remains explicitly flagged;
  unknown flags and flag/value contradictions fail closed.
- Visitor counts are trips, not unique tourists. NTTO is residence-based,
  qualified-visa, overnight, all-purpose visitation. Taiwan and Macau counts
  include broader arrival populations. Only Taiwan currently supplies a
  separately verified sightseeing-purpose series. Macau excluded non-resident
  workers and students starting in 2008, then changed from residence
  to travel-document issuing place in April 2015; 2015 is a mixed-method
  transition. Charts break at all those boundaries and incompatible years cannot
  be compared with 2020.
- BEA goods/services use nominal USD and balance-of-payments accounting.
  Comtrade Macau goods use customs accounting: U.S. exports FOB, imports CIF.
  Cross-geography totals are not produced. BEA's current annual workbook has a
  repeated 2000 label and no 2001 label. Those two annual years use the correctly
  labelled December 5, 2024 official workbook, retaining that older vintage and
  its exact provenance. Current-release quarterly data and later annual years
  remain separate. No year is inferred from row position.
- Latest complete annual values compare with **2020**, not 2019. Academic
  baselines use 2019/20. Absolute and percent changes require matching
  populations, units, series and period coverage. Zero or unavailable
  baselines never produce an invented percentage.
- The partial-year panel compares identical January-to-month or Q1-to-quarter
  intervals with 2020 and the prior year. Quarterly BEA sums are seasonally
  adjusted and separate from the annual definition. Provisional NTTO months
  propagate provisional status into derived YTD totals.
- Missing, suppressed and absent years remain gaps. Chart paths also break on
  definition changes. No forward fill, interpolation, annualization, composite
  exchange score, or causal inference is used.

[Source contracts and specific gaps](SOURCES.md) document primary links and
rejected substitutes. Mainland U.S.-attributed all-mode visitor history after
2018 and several degree-enrollment directions remain unverified or blocked.
Hong Kong's full 2000-2025 arrival history is recovered with a documented
population break. Macau services now have direct current USTR 2025 estimates
and separately qualified archival 2024 estimates in both directions, not an
invented continuous history. Missing observations show a
specific gap instead of a zero.

## Scheduled operation

`.github/workflows/update-exchange.yml` runs daily at 11:23 UTC and supports
manual dispatch. It also checks relevant implementation pushes. There is no
deployment step.

The workflow uses Ubuntu 24.04 and Python 3.12 rather than a moving runner image.
It checks the existing publication/parsers, refreshes sources, builds
offline, then checks downloads, computations and browser behavior before any
publication commit. A concurrency group serializes refresh jobs. Unexpected
remote branch advances fail a push rather than forcing or rewriting history.
The next run can reconcile from the new branch head.

Numeric, definition, release, source-URL, and health transitions are meaningful
changes. A retrieval timestamp or raw-response checksum alone is not:
responses can contain volatile metadata. Unchanged rows retain their original
published provenance. A daily no-op creates a run log/artifact but **no commit**.
Source outage transitions are recorded without erasing last-known-good rows.
Custom adapter mappings refresh only the selected sources: omitted observation
rows and source manifests remain unchanged, including their health and dates.
The attempt log lists only sources actually checked. An empty mapping is a
publication no-op; it does not clear the dataset.
IIE is an explicit policy check, not a network attempt: it reports
`permission_required` and `retrieval_attempted: false`, retaining the reviewed
observations, release vintage and last successful retrieval date. Repeated
policy checks are publication no-ops. Explicitly selecting the IIE adapter does
not bypass this gate.

Network errors, HTTP failures and exhausted retries mark a source degraded
(or unavailable if it never supplied data). Malformed candidates, changed
layouts, incompatible units, ambiguous source totals and invalid values fail
the run before candidate publication files are written. Per-file publication
writes are atomic; the validated Git commit is the published snapshot boundary.
No automatic commit occurs on a failed check.
Final cross-source/provenance validation and JSON serialization also finish
before any publication file is written. If either fails, `check.json` records
the current attempt time, `publication_blocked: true`,
`publication_changed: false` and a top-level `error` diagnostic. This creates a
new failure log or replaces an older successful one, while preserving the
prior publication files.
Comtrade responses must match the requested year in both `period` and
`refYear`, use annual frequency `A` and goods type `C`, and retain the required
reporter, partner, aggregate and paired flows. A wrong-period or monthly response
cannot be relabelled as an annual observation.

The workflow writes commits as **Hans Hanley**, without Copilot authorship,
co-author or session trailers. It uses the repository's `GITHUB_TOKEN` with
contents-write permission; no personal token or committed secret is required.
Repository/organization Actions policies must permit that permission.

Published dates are not a claim that a daily check just happened. Every actual
check is in the run's `check.json` artifact and job summary, including no-ops.
Source release labels, published successful retrievals and recorded publication
checks remain separate. Workbook modification timestamps are not asserted to
be official release dates.

## Maintenance and validation

IIE's reviewed 2025 observations remain frozen. Its current terms prohibit
automated downloading/analysis, so neither daily refreshes nor explicit adapter
calls retrieve its PDFs. There is no environment-variable override. Before any
new IIE retrieval or commercial reuse, establish and document applicable
permission or a permitted replacement source, then review the report's layout
and definitions before changing the gate. Existing data do not become newly
checked just because another source refreshes.

MGTO's published site terms limit use to noncommercial purposes; separate
commercial reuse permission is not verified. The source manifests, JSON policy
records, page notices and affected figure footnotes expose this restriction.
Neither the Substack nor The Margin of Error background is a rights clearance.
These notices do not determine copyright or contractual enforceability.

Some official index pages return 403; do not bypass those restrictions.
Macau's selected-market
PDFs can omit the U.S. or rasterize tables. Its 2008, 2010 and 2015 historical market profiles
and automatically discovered latest complete market profile supply machine-read
annual U.S. totals; sea, land and air components must sum to each total. They
fill the December highlights' gaps, including the previously image-only 2024
value. Newest profiles take priority over older annual highlights. The adapter
covers annual reports, not current monthly highlights. Other unverified values
remain missing, not zero. The coverage matrix exposes those limits.

For browser checks:

```sh
.venv/bin/python -m pip install -r requirements-exchange-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/check_exchange_browser.py
```

These exercise every geography/direction/measure, exact values and 2020
changes, the partial-year panel, index mode, keyboard interaction, mobile
overflow, both publication backgrounds, figure-text clipping, and no-JavaScript
tables/downloads. Unit tests verify all PNG dimensions, background and series
colours, categorized files/catalog links and byte-identical offline rebuilds.
They also cover source units/directions,
mixed Excel header types, leap February, missingness, source outages/recovery,
numeric revisions, malformed-input rollback, unchanged refreshes and
byte-identical offline rebuilds. Review checkpoints are frozen to their source
vintage so later legitimate revisions are not blocked by obsolete constants.

No raw source documents or browser screenshots are committed. A source's
SHA-256 references the locally retained raw response; GitHub-hosted runners
are ephemeral, so preserve raw inputs privately if archival replication of a
particular online release is needed. The canonical numeric publication and
offline figures remain reproducible from Git.
