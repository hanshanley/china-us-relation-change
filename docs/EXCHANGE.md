# Bilateral exchange dashboard

The active user-request checklist and release gates are in
[`TASKS.md`](../TASKS.md). Read and update it when continuing this work.

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

### Confucius Institutes, Classrooms and successor programs

`confucius.html` is a dedicated public page, separate from the Chinese/Japanese/
Korean language comparisons. It presents disconnected national historical
snapshots, separately expandable campus-only figures, and source-attributed
documented replacements. Compact native charts preserve exact hover, tap and
keyboard values; bounds have open boundary marks, never exact-count bars.
The same five charts are exported as PNG/SVG in both publication backgrounds.

`data/site/confucius_programs.json` holds 22 selected observations and 135
supporting factual records: all 17 entries returned by the operator's U.S.
directory, the ten-entry historical NAS roster, and all 108 rows of the linked
post-closure workbook. Full observations/definitions and all selected records
are downloadable as CSV; JSON includes all observations, records and provenance.
No reports, source artwork, long narrative cells, contacts or administrative
directory fields are republished.

The October 24, 2026 directory query returns ten Institute-labelled and seven
Classroom-labelled entries. These are **listings, not a verified operating
census**. The directory's `enable` field controls its website presentation,
not whether a program is open. One classroom entry is university-named, so
seven entries cannot be called seven K-12 schools.

GAO's fewer-than-five campus count refers to **July 2023**, not its October
publication date. The 2017 NAS report remains a 2017 source despite its 2025
upload path and a 2026 web-page date; the 2019 Senate report was subsequently
deposited at a 2023 hearing. The 164-case 2024 classroom inventory mixes current
and former school/district cases and is not added to the operating history.
NAS's 28 documented replacements in 2022 and at least 28 in 2023 are cumulative
source documentation, not the number open now. Proposals, retained partnerships
and transfers overlap and are not summed into a rebrand total. The workbook
has 29 R-coded rows, with prospective or ambiguous descriptions; those codes
remain source evidence, not independent current-status certifications.

`python scripts/build_confucius_data.py --cached` reproduces the explicit
reviewed collection using the checked source cache. The two GAO facts and
the 2023 tracker bound use `data/reviewed/confucius-snapshots.json`: its hash
identifies our selected-fact transcription, not a publisher response.
`--check-only` checks the public directory without altering reviewed data.
The daily workflow records actual retrieval failures and changes requiring
review in `data/local/confucius/check.json`; it does not silently reclassify
programs or refresh old observations to today's date.

`scripts/check_confucius_publication.py --site PATH` reconciles complete
downloads, every plotted identity/value/bound, original export dimensions and
both backgrounds, and desktop/phone, touch, keyboard and no-JavaScript behavior.
The full plot audit also checks the new page and each export.

### China-born residents by U.S. state

The immigration page opens with an interactive 50-state/DC map, switching between
resident counts and the share of each state's foreign-born residents. Both values,
the denominator and the Census count margins of error are available on hover,
focus, touch or the state selector. Alaska and Hawaii have independently scaled
insets; DC has an accessible callout. A complete table also works without JavaScript.
Count/share PNG and SVG exports use both publication backgrounds.

`data/site/state_immigration.json` retains all 51 state records, the national
control, source cells, margins of error and provenance. `us_states.geojson` holds
the official generalized Census state boundaries. The separate map dataset does
not change the existing immigration time-series observations.

The current map uses **2020–2024 ACS five-year estimates**, table B05006:
`B05006_E050` is **China, excluding Hong Kong and Taiwan**; `B05006_E001`
is the foreign-born universe excluding people born at sea. Do not substitute
the parent China category, which includes Hong Kong and Taiwan, or assert a
separately verified Macau exclusion. These are five-year period estimates, not
2024-only stocks or annual new immigration. The one-year detailed table has
only 30 state/DC records after Census quality filtering; do not fill its gaps
with five-year observations or the differently grouped collapsed table.

`python scripts/build_state_immigration_data.py` checks the release page for the
latest **actually released five-year** summary file, then validates all 51 states
and the national control before replacing the frozen data. An API metadata shell
is not a release. The daily workflow keeps the last verified map on retrieval
failure and records the actual attempt in `data/local/state-immigration/check.json`.
Unchanged values and geometry do not create daily timestamp-only commits.
`--year 2024 --cached` reproduces the reviewed vintage from the local cache.

The 267 MB public summary file is read using its first 1 MiB HTTP byte range;
all 51 state records and the U.S. control are present in that prefix. Validation
fails if any is absent. The retained SHA-256 describes **the retrieved prefix,
not the entire nationwide file**. Public CSV/JSON downloads contain every
selected state estimate, not a source inventory. The full state GeoJSON is
available separately. Run `scripts/check_state_immigration_map.py --site PATH`
for the independent identity/colour/value/export, desktop/phone, keyboard,
touch and no-JavaScript checks.

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

### Currentness review: October 23, 2026

Alternative primary sources recovered 34 additional bilateral observations and
17 business observations. Existing numerical observations are preserved:

| Chart family | Verified extension |
|---|---|
| Macau services | BEA expanded-geography Table 2.4 supplies both directions for every year 2018-2025, including the 2019 baseline. It replaces USTR's two isolated vintages in the main and regional charts; all four USTR observations remain in complete downloads and research exports. |
| U.S.-host enrolled students | Original IIE reports deposited in the federal ERIC repository fill 2019, 2020, 2022 and 2023 for China, Hong Kong, Macau and Taiwan. All four histories now cover 2019-2025 continuously. Exact undergraduate, graduate and non-degree counts are added; OPT is excluded. The pandemic-expanded 2021-2023 population remains disconnected. |
| Macau current tourism | DSEC's September workbook, released October 23, supplies 10,378 U.S.-issued-document arrivals for September 2026 and 120,071 for January-September. Matched 2025 values are 8,322 and 112,330. Each pair reconciles separately with sea/land/air and same-day/overnight components. The MGTO September URL still returns an August-labelled report and is not relabelled. |
| Norwegian businesses in China | Statistics Norway Table 09827 supplies a complete 2008-2024 all-industry history, ending at 80 enterprises. This full source history replaces the narrower Eurostat chart, rather than splicing its endpoint onto Eurostat's different sector coverage. Original Eurostat observations remain in the data. |

```sh
.venv/bin/python scripts/build_tourism_backfill.py --services-only
.venv/bin/python scripts/build_tourism_backfill.py --dsec-only
.venv/bin/python scripts/build_contact_backfill.py --enrollment-only
.venv/bin/python scripts/build_business_data.py --norway-only --data-only
```

The BEA expanded table and current DSEC country workbook are also checked by
the ordinary exchange refresh. Public POST endpoints are queried using the
same request bodies as their official interfaces; cached requests distinguish
GET from POST and different query bodies. Every response retains its original
URL, checksum and retrieval date. Human-facing BEA source links open the
interactive table rather than a POST-only endpoint.

Source-specific publication limits are not silently filled with another
population. The fresh MLA report/database/workbook check still ends in fall
2021; 2020 is a separate sample, not a newer national census. Fresh UIS requests
still end in 2023 for U.S.-host degree mobility and 2024 for U.S.-origin students
in Hong Kong/Macau, with no new mainland-destination records. Eurostat's EU27
2023 enterprise count remains confidential. ONS explicitly reports no outward
affiliate statistics from 2020 onward; its new inward-affiliate release is not
an extension of UK businesses in China. BEA's activity release still covers
2023; its next benchmark release is scheduled for November 2026.

Current AP national/cohort reports and the Texas agency's national tables were
also reviewed. They do not supply the missing nationwide language-specific
public-graduating-cohort counts. State-only counts, all-subject totals and
global AP participation are not substituted into that historical cohort
series. Newer Chinese program respondent surveys, regional college data and
all-nationality Chinese immigration/tourism totals likewise remain distinct
from missing national Chinese/Japanese/Korean course counts or U.S.-specific
mainland enrollment/all-mode arrival histories.

### Further alternative-source recovery: October 24, 2026

This pass adds **45 records** without changing any earlier numerical observation:
eight bilateral visitor observations, eighteen German business observations,
sixteen Macau residence-approval observations and three school-availability
records, including the explicitly unreportable Korean estimate.

| Chart family | Verified update |
|---|---|
| Hong Kong visits | July/August monthly and matched cumulative U.S.-nationality counts for 2025/2026. January-August totals are 659,003 and 737,530. Both overnight + same-day components and successive cumulative totals reconcile, starting with the retained first half. Annual residence/nationality boundaries are unchanged. |
| German businesses | Eurostat's full 2010-2023 country history and Bundesbank's direct 2021-2024 workbook, ending at 1,911 provisional enterprises. Their overlapping counts differ, so two separately identified histories are shown rather than a fabricated source splice. Germany is not added to EU27 or used to reconstruct confidential aggregates. |
| Macau residence approvals | Every calendar year 2010-2025, from overlapping DSEC yearbooks, table 2.10; latest 34 people in the U.S. country category. These are neither resident stocks nor U.S. fiscal-year grants, verified U.S. departures or a permanent-residency legal classification. |
| Public-school language availability | Nationwide January 2024 NCES School Pulse Panel: Chinese 3%, Japanese 1%; Korean below reporting standards. All public schools are the denominator, not only language-offering schools. Not student counts, not 2026 observations and not a continuation of the 2014-15 respondent program counts. |

The HKTB numerical facts were manually reviewed in its publicly readable
monthly PDFs after normal automated retrieval failed. The versioned
`data/reviewed/hktb-monthly-2026-08.json` records only the selected U.S. facts,
primary report URLs, column identities and review date. Those observations'
source URL and checksum identify this exact reviewed transcription, **not a
cached publisher PDF**. The same checksummed file is publicly accessible on
GitHub. The source link on the reader-facing chart opens HKTB's official page.
No login, verification screen or access restriction was bypassed.

```sh
.venv/bin/python scripts/build_tourism_backfill.py --hktb-reviewed-only
.venv/bin/python scripts/build_business_data.py --germany-only --data-only
.venv/bin/python scripts/build_immigration_data.py --macau-only
.venv/bin/python scripts/build_language_data.py --school-pulse-only --data-only
```

The national NCES workbook is `Language.xlsx`. The separately linked
`Language_oa.xlsx` covers U.S. outlying areas and is rejected as a national
replacement. Korean's published complement is not used to reconstruct its
suppressed estimate. Historical program-count and enrollment observations
remain complete in downloads; no growth calculation joins the new percentages
to the old counts.

The September 25, 2026 Federal Reserve FEDS Note on direct-investment
decoupling was also reviewed. Its newer project/deal/capital-investment
measures do not extend the published BEA affiliate-entity count: its cited
AUSMNE activity series still ends in 2023. No confidential or proprietary
microdata, project counts or investment values substitute for affiliate counts.

## Plot styling and publication backgrounds

Charts follow the `uk_decline` project's `vizstyle` house settings: serif type,
near-black ink, muted grey labels, light horizontal gridlines (0.6 opacity),
0.8-width left/bottom axes, no top/right frame, and italic collecting-source
notes. Bilateral charts use `FLOW_COLORS`: mainland China to the U.S. is
maroon (`#7B2D26`) and the reverse is blue. Hong Kong uses blue inbound and
maroon outbound; Macau and Taiwan retain distinct direction-specific house
colours. Native charts and both export themes use the same mapping.

COVID travel shading marks 2020-2022 only on student and travel measures, not
goods/services trade, opinions, language, business, Confucius programs or
resident stocks. It is context, not a universal-ban or causal claim. Irrelevant
plots also omit the explanatory shading note.

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

### Public edition and plot audit

The collective publication uses responsive charts with 17px desktop and 14px
phone axes. Desktop plot height is approximately half its width, capped at
520px; phone plots are 310px tall. Static exports keep their publication
dimensions and both backgrounds. Without JavaScript, charts scroll internally
instead of shrinking their labels.

Hover anywhere over a plot, tap, or focus it and use the arrow/Home/End keys
to inspect actual observations. Tooltips preserve reference periods, exact
counts, missing series, source reliability and reported values behind indexes.
They never interpolate or substitute a neighbouring year's observation.
Escape dismisses them. Changing indicators, resizing or hiding plots disposes
their tooltip handlers.

The public edition keeps chart-specific definitions, source notes and downloads.
Navigation and the footer link to GitHub for full datasets, methodology and
research documentation instead of displaying source-health inventories,
collection logs, audit manifests or exhaustive research tables. Complete
coverage, observations and provenance remain in the published download files;
the research edition retains its full tables and source documentation.

```sh
.venv/bin/python scripts/build_exchange_publication.py --output data/local/collective-publication
.venv/bin/python scripts/check_exchange_publication.py --site data/local/collective-publication
.venv/bin/python scripts/audit_exchange_plots.py \
  --site data/local/collective-publication --exports outputs/figures \
  --output data/local/plot-audit --screenshots
```

The audit reconciles source rows and transformations independently, verifies
calendar positions, axis labels, line vertices and comparability breaks, and
checks label overlap/clipping with browser and bundled raster-font metrics.
It moves the pointer over every public chart at its first, middle and last
observed periods, checks displayed tooltip values and markers, and exercises
keyboard navigation at 1360px, 390px and 320px widths. The separate browser
check covers touch, redraw cleanup and the no-JavaScript fallback.

### Combined regional comparisons

Single-series annual reported-value charts use vertical annual columns,
not connected lines. Only reported years get a bar; true zeros and missing
observations remain different, and partial-year updates are not annualized.
Indexed views and multi-series comparisons retain lines. The same style is
used by the interactive chart and both PNG/SVG publication backgrounds;
hover, touch and keyboard values retain full reported precision.

Open `site/comparisons.html`, linked from the dashboard. These new comparisons
include **mainland China, Hong Kong and Macau only**; Taiwan is excluded, while
the existing individual series and source dataset are retained. The same
`FLOW_COLORS` mapping drives individual and regional bilateral charts, including
the distinct mainland-China-to-U.S. and reverse-direction colours.

Comparisons are separated by measure and direction; student populations,
visitor definitions, goods and services are never combined into one total.
Unavailable geographies remain labelled rather than acquiring a zero line.
Raw-value and logarithmic views are provided in both publication backgrounds;
logarithmic views omit genuine zeros, leave gaps, and never add pseudocounts.
Missing years and population-definition breaks remain disconnected.

Visitor comparisons use two panels: **mainland China on the left**, **Hong Kong
and Macau together on the right**. Both panels share the same year range but
use separately labelled vertical scales so smaller routes remain readable.
The panels stack on phones. This applies in both directions and to the
separate resident-air estimates; missing Macau air estimates remain unavailable,
not zero. Each panel retains exact-value hover, keyboard and touch interaction.
Trade and student comparisons use the same split layout where eligible series
exist. Multi-series panels retain comparison lines; single-series levels use
annual columns.

Combined PNG/SVG exports live under
`outputs/figures/<category>/comparisons/<background>/` and the matching site
directory. Visitor panels have separate `chn-` and `hkg-mac-` downloads in both
backgrounds and both linear/logarithmic views; obsolete combined visitor exports
are withdrawn. The offline catalog includes both views. Macau goods retain their
different customs accounting and a dashed line, with an explicit caveat against
treating them as identical to the other geographies' BEA accounting.

### Weibo coverage and uncertainty

`site/weibo.html` opens with a readable account directory, not a large
unresolved-percentage graphic or a thousand-cell research-progress map.
All 87 documented channels across 62 publisher/brand groups remain present,
with channel names, identity evidence and original sources. Publisher groups
are alphabetical and paginated eight at a time; search and filters operate
over the complete registry, not just the current page. Downloads always
contain the complete account set, not only the visible page.

Desktop uses a list beside a source inspector. Phones open a selected account
in place of the result list and provide a keyboard/touch-accessible return
path. Secondary filters collapse behind a labelled control on phones, with
the number of active filters kept visible. Direct links reveal the correct result page and clear conflicting
filters rather than silently selecting another account. Historical attribution
cutoffs are visible in the account detail. With JavaScript disabled, all account
links and evidence remain available in reading order, without dead filters or
pagination controls.

The separate selected-domain cohort belongs under **Selection & research
coverage**. Its compact proportional bar retains exact counts, percentages and
keyboard/hover explanations. Twelve documented domain associations do not mean
the broader registry has only twelve accounts, nor that other domains have no
accounts. Verified negatives, if present, are not included in the confirmed
account numerator. Account evidence and manual-review progress remain separate.

**Recovered posts & limitations** contains sample-recovery counts with explicit
denominators. Neither channel representation nor text completeness measures the
fraction of all historical posts recovered; that denominator is unknown.
Available source text is not an independently verified complete original.

Current profile evidence is distinct from historical-only evidence and is not
labelled active/inactive. Observed evidence dates are shown without implying live
posting or current U.S. editorial control. Recovered-post counts do not affect
account ordering or visibility. No posting-history/popularity trend is invented.

Run `scripts/check_weibo_publication.py --site PATH` for exact coverage geometry,
every channel across pagination and filters, direct-link identity and viewport
position, 320px layout, touch, keyboard and no-JavaScript checks. The shared
browser checks and independent plot audit use the same acceptance contract.

Complete recovery datasets and original figure exports remain available for
audit and reproducibility under `outputs/figures/weibo/<background>/` and
`site/figures/weibo/<background>/`; those archival recovery charts are not
embedded in the account explorer.

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
The original baseline ends October 21, 2026; the live cutoff is recorded
separately in the snapshot. Monthly totals
reconcile to annual and account totals; private post text is not included.
Older snapshots remain readable but do not invent missing monthly data.
These complete exports retain calendar positions, distinct-channel counts
and partial-month flags; the interactive account map does not turn them into
apparent posting-activity trends.

Version 5 adds complete daily counts and trailing-30-day measures:
`site/downloads/weibo-days.csv` and `site/downloads/weibo-rolling30.csv`.
Each point includes its date and the preceding 29 Asia/Shanghai calendar days.
Channel counts deduplicate account IDs across the entire window; publisher
counts additionally deduplicate publisher/brand groups. The daily running
average is the recovered-post total divided by exactly 30, not a monthly total
or an average over posting days. The first 29 requested days and windows
crossing unrequested or partial days are unavailable, not zero. All measures
remain recovered-sample lower bounds, never a census of active/inactive accounts.

### Automatic private Weibo refresh

The GitHub exchange workflow rebuilds frozen Weibo aggregates; hosted runners
do not have the private corpus. Actual collection runs on the collection Mac:

```sh
PYTHONPATH=src .venv/bin/python scripts/refresh_weibo.py
PYTHONPATH=src .venv/bin/python scripts/refresh_weibo.py --publish --push
.venv/bin/python scripts/install_weibo_refresh.py
```

**Observed unattended-execution blocker:** the first scheduled invocation
failed at approximately 19:35 UTC on October 23, 2026. The second natural
invocation, at 21:35 Mac local time on October 23 (01:35 UTC on October 24),
failed in the same way before Python could initialize its `site` module.
The third natural invocation, at 03:35 Mac local time on October 24
(07:35 UTC), failed at the same startup stage. The fourth natural invocation,
at 09:35 Mac local time on October 24 (13:35 UTC), failed before Python
initialized as well. The fifth natural invocation, at 15:35 Mac local time
on October 24 (19:35 UTC), failed at the same startup stage.
Actual stderr now records five
`PermissionError: [Errno 1]` startup failures reading
the repository's `.venv/pyvenv.cfg` under Documents; `launchctl` records five
runs and last exit code 1. No collector code or network collection started.
This is consistent with macOS Documents-folder access protection, not a Sina
denial. Schedule registration, successful local tests and the earlier bounded
manual collection do not prove unattended execution works.

The job remains registered but collection is blocked pending user-approved
access for the actual scheduled process. Apple documents
[file and folder access controls](https://support.apple.com/guide/mac-help/mchld5a35146/mac)
under System Settings, Privacy & Security, Files & Folders. No privacy
settings were changed, permission database reset, alternate launcher tried
or protected data relocated to evade the denial. Approval must be followed
by a successful real scheduled-process run before this is marked operational.
Private evidence is in `data/local/automation/scheduler-health.json` and
`refresh.stderr.log`. Published refresh status now records this startup block
with zero attempted feeds while retaining the last successful bounded manual
collection time and cutoff. The fifth failure's attempt timestamp comes from
the actual stderr modification time, `2026-10-24T19:35:05.213988+00:00`,
not an observed feed-request start. Zero new records for
this failed invocation is not an inactivity finding or a fresh collection.

The first command is a private, non-promoting preview. The installed per-user
LaunchAgent is configured for 03:35, 09:35, 15:35 and 21:35 local time when the Mac is
available; missed sleep-time events coalesce on wake. It uses the existing
private SQLite corpus, not a fresh metadata-only database. The last completed
Shanghai day becomes the rolling-measure cutoff. The partial current day is
buffered privately with an exact request timestamp, so frequent polls do not
discard today's posts before the day closes. Its incomplete 30-day estimate
remains unavailable rather than being prorated. A consistent private baseline is
preserved under `data/local/automation/baseline_2026-10-21/` and the original
published baseline remains in Git history.

Only currently attributed, confirmed numeric channels are polled, sequentially
and with source spacing/robots restrictions. Existing audited complete bodies
are reused without pretending they were freshly retrieved. New/changed records
must match newly saved primary text, UID and publication date. Full private
exports, source proofs, domain ledgers, inventory, charts and complete downloads
advance together. No raw post bodies, private database or source HTML is pushed.

Access/identity holds persist in `data/local/automation/access-holds.json` and
are not automatically retried through other routes. Source conflicts, stale
audits, concurrent corpus changes or relevant dirty files stop promotion.
Unrelated changes and staged work are not committed. Automatic commits use
Hans Hanley's identity without agent attribution. Failed collection does not
advance the corpus/cutoff; refresh status distinguishes attempts from readable
collections. Inspect `data/site/weibo_refresh.json`, the page's refresh-status
note and private `data/local/automation/last-check.json`/logs. A Mac that is off
cannot provide an always-on collection service.

Remove only this agent with
`.venv/bin/python scripts/install_weibo_refresh.py --remove`.

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

Open `site/language-learning.html`. The chart families address the college
boom/reversal, comparison with other languages, school-age pipeline and narrow
specialist-degree pipeline. They use the existing house typography, stable
language colours and both publication backgrounds. PNGs are 3000 by 1800;
PNG/SVG exports live in `outputs/figures/language_learning/<background>/`
and the matching `site/figures/` directory.

National course enrollments must not be replaced by a single state's counts,
individual university reports, degree awards or a newer survey with a different
population. On October 23, 2026, the MLA release page, live national query tool
and freshly downloaded institution-level workbook all still ended in fall 2021.
The workbook contained a 2020 sample and summer rounds as well; neither is a
newer nationwide fall census.

`scripts/check_language_releases.py` now checks the release page, discovers the
workbook linked by the live database, and reads its actual fall survey years.
The daily workflow retains its dated, checksummed result and warns when newer
national data become available. A failed check is not reported as confirmation
that the old release is current. Review and reconcile a new release before
changing the published national series.

The separate 2024 CLTA study, published September 21, 2026
(DOI `10.1075/csl.25019.li`), reports 191 U.S. and 11 Canadian respondents, not
the MLA national census. Its abstract is verified, but its numerical enrollment
tables have not been retrieved; no numbers are inferred from its conclusions.
California's official 2010–2026 course exports and Ohio's recent institutional
reports are supplementary recovery leads, not a solution to the national gap.

These indicators remain separate from canonical bilateral flows:

| Indicator | Verified history and interpretation |
|---|---|
| MLA national college registrations | Fall 2002, 2006, 2009, 2013, 2016 and 2021, using the 2021 report's historical table. Separate Chinese/Japanese/Korean levels, shares and indexes with 2013=100. The all-language total is a denominator, not a fourth displayed series. Registrations are not unique learners. |
| Matched college institutions | Same complete-count responding institution IDs in 2013 and 2021. Nonresponse placeholders and institutions with any unreported language-count row are excluded; explicit zero-language respondents are retained. This selected cohort is not a national census or a causal estimate. |
| AP annual administration | Total Chinese and Japanese global participation, 2007-2025. Not U.S.-only counts or a census of language learners. No AP Korean exam is listed; use the separate MLA college comparison for Korean. |
| Historical U.S. AP cohorts | Public-school graduating classes 2007-2013; Chinese exams taken at any point during high school. Not the administration year, all U.S. schools or unique learners. Separate from global annual counts; current U.S.-only administration history remains a documented gap. |
| IPEDS degree awards | Academic years ending 2000-2025, separate Chinese 16.0301, Japanese 16.0302 and Korean 16.0303 codes, 50 states/DC, Title IV degree-granting institutions. Each award level has three language lines. Second majors/certificates are excluded from 2001 onward. Awards are not enrollments, unique people or proficiency measures. The 2025 release is provisional. |
| Immersion inventories | CAL 2011, ARC 2021 and Nexus 2025 snapshots use different universes. Categorical bars deliberately do not connect them into a growth trend. |

Annual lines break on missing years and definition changes. MLA lines connect
actual census rounds, without inventing intervening annual observations. IPEDS
2000 lacks separate major numbering; doctoral classification changes in 2010,
from the old doctoral category to research/scholarship doctorates. Both boundaries
break chart lines. Original flags, revision members and filters are retained.

The degree comparisons use language-specific national counts, not the combined
East Asian field or institution-sector totals. The 2024/25 bachelor's checkpoints
are Chinese 292, Japanese 464 and Korean 44. Reproduce all three degree histories
without changing other indicators:

```sh
.venv/bin/python scripts/build_language_data.py --ipeds-history --last-degree-year 2025 --data-only
```

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

Open `site/business-presence.html`. Investment positions, reverse-direction
U.S. affiliate counts and company surveys remain distinct from foreign
business counts in China. The new Swedish, Finnish, French and Dutch histories
are separate annual bar panels, with their actual reporting windows.
Finland also has a separate Eurostat UCI history back to2007. Its market-
producer population differs from the broader national count and is not
spliced into it; the2013 YTY system break remains explicit alongside the
classification and2021 EBS boundaries.
Earlier U.S., German and Norwegian count histories are explicitly labelled
secondary references in a closed disclosure, not newly recovered current
evidence. Stale EU/UK and parent-company benchmarks stay download-only.

| Measure | Verified history and definition |
|---|---|
| U.S.-parent affiliates in China | All 24 annual fiscal-year observations, 2000-2023. Affiliate entities, including holding companies, not distinct parents, branch offices or annual openings. Nonbank coverage before 2009; reporting thresholds and benchmarks create breaks. |
| EU-reporting groups in China | Historical EU27 membership (including UK, excluding Croatia) supplies 2009, 2011 and 2012. Current EU27 membership (excluding UK, including Croatia) supplies 2014-2022, with 2021 estimated. Different memberships/classifications are distinct traces, not a joined splice. Confidential and unavailable years remain gaps. |
| UK-controlled enterprises in China | Ten annual values, 2010-2019. Eurostat history through 2017; ONS revised 2018 and 2019 estimates. The 2018 source/sector boundary is disconnected. ONS total activity includes agriculture. No outward-affiliate counts from 2020 onward verified; do not use newer inward-affiliate or FDI statistics as substitutes. |
| Norwegian-controlled enterprises in China | Seventeen annual Statistics Norway observations, 2008-2024, all industries. The full SSB history is used, not spliced to the narrower Eurostat population. The fourteen old Eurostat observations remain in complete downloads. Norway is outside the EU and is not added to a Europe total. |
| Swedish-group subsidiaries | Fifteen reported2010-2024 counts, ending885;2000-2009 remain explicitly missing. Subsidiary variable2 is not the longer parent-group variable0. The 2018 EGR/imputation,2019 frame and2021 ownership changes remain separate. |
| Swedish-UCI enterprises, Eurostat | Sixteen reported2007-2023 counts and confidential2009, ending602. A separate market-producer population, not a splice into the national subsidiary table. Keep the metadata's2008classification boundary, original legacy NACE label/2010table transition,2018legal-unit-to-enterprise/EGR change and2021EBS boundary. Official imputation can apply; the national2022count1133 is not replaced or smoothed. |
| Finnish-reported affiliates | All five2020-2024 country counts, ending242. Active subsidiaries and branches, all sizes/industries. The 2021 EBS boundary remains explicit; no earlier China count is inferred from regional aggregates. |
| Finnish-UCI enterprises, Eurostat | Seventeen2007-2023 enterprise counts in China except Hong Kong, ending185. Legacy NACE C-O except L, then market producers B-S except O. The2010 classification,2013 YTY and2021 EBS boundaries are retained. Overlapping national counts differ; this is a separate annual-bar panel, not an extension or denominator for the national series. |
| French-controlled enterprises | Sixteen reported2007-2023 counts and one missing2008 cell, ending2153. Eurostat's host category is China except Hong Kong. The 2007/2009,2010,2016 and2021 boundaries are not spliced or used for cross-regime growth. INSEE's rounded count remains a separate source finding. |
| Dutch-controlled enterprises | Eighteen reported2007-2024 counts;2024=620 is provisional. Eurostat's seventeen earlier observations match original native TSVs; CBS's2023 control574 agrees. Dutch-resident UCI, financial/nonfinancial B-S except O. Preserve the2010 classification and2021 method boundaries; no comparable2019 change, pre-2007 history or2025 count is inferred. |
| Supplementary U.S. parent-company benchmarks | Only 2004,2009,2014 and2019 are verified and remain archive-only, not an annual census. Foreign-affiliate ownership begins at10%, not necessarily majority control; reporting exclusions apply. No interpolation. |

The U.S. affiliate reporting cutoff changes from $7 million through 2003 to
$10 million in 2004-2008 and $25 million from 2009, based on assets, sales or
net income/loss. These are nominal, not inflation-adjusted, cutoffs.
Benchmark remeasurement and coverage can create level changes; boundaries
in 2004,2009,2014 and2019 remain explicit. Parent benchmark observations are isolated.
No incompatible full-history percentage is calculated.

European origins are not destinations: these national series concern
enterprises in their reported China host category, not U.S. businesses in Europe.
This is selected European coverage,
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
every raw/derived chart point in `business-chart-values.csv`. Every displayed
count chart has 3000-by-1800 PNGs and SVGs under
`outputs/figures/business_presence/<background>/` and the mirrored site tree.
Annual count charts use bars, including separate Eurostat/Bundesbank German
source panels. The nine primary panels retain the six investment/reverse-count/
survey panels and add the three new country histories; earlier reference bars
remain secondary and no source population is summed into an all-Europe total.
Obsolete U.S.-in-Europe plots are withdrawn from both figure trees and catalogs.

```sh
.venv/bin/python scripts/build_business_data.py --data-only
.venv/bin/python scripts/build_business_data.py --nordic-only --data-only
.venv/bin/python scripts/build_business_data.py --france-only --data-only
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

### Topic organization and regional scales

The collective publication has one home for each topic. Students and Travel
retain individual-series controls and their latest partial-year updates, with
regional comparisons inside the same topic. Trade contains goods and services,
grouped by measure and direction; its individual-series controls are secondary.
Legacy `comparisons.html?indicator=...` links lead to the appropriate topic,
and a readable directory remains available without JavaScript.

Regional comparisons use mainland China in one panel and Hong Kong/Macau in
the other, side by side on wide screens and stacked on narrow screens.
They share the year range but use separately labeled vertical scales.
Unavailable series remain explicit rather than becoming zero. Macau customs
goods accounting and separate services vintages retain visible qualifications.
Comparable immigration regional views use the same layout while keeping
citizenship, birthplace, stocks and status grants distinct.

Business stays separate from cross-border trade flows. Annual affiliate and
enterprise histories are grouped by reporting origin; parent-company
benchmarks remain supplementary. EU, German, UK and Norwegian coverage is not
added into a European total, and entity counts are not relabeled offices.
Complete downloads, exact-value tables and source/definition boundaries remain
available; this presentation change does not alter reported observations.

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
nationality**. The line breaks at this boundary, and a 2019-based index/change
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
air-travel estimates to mainland China and Hong Kong for 2012-2020 and 2022-2025.
The public monitor's year selector is virtualized: the initially visible
years are not its full history. The collector now scrolls that selector and
verifies every displayed calendar-year/country caption. Fourteen additional
annual observations extend these two consistent survey histories back to 2012.
On switching to U.S.-to-mainland travel, the public controls default to this
current series, not the all-mode series ending in 2018. The indicator menu and
visible population caption identify the old series as historical; either
population remains available in the complete downloads. The air-travel index
and change headline explicitly use **2019**, not an invented 2020 baseline.
The 2025 and 2026 Q1-Q2 selections now explicitly deselect Q3 and Q4 with
ordinary checkbox clicks; modifier-click was opening a macOS context menu.
Their January-June values are read directly, not inferred by subtracting rounded
totals: China 442,000 in 2025 and 474,000 in 2026; Hong Kong 304,000 and 251,000.
The 2020 selections directly report 89,000 trips to mainland China (357
respondents) and 39,000 to Hong Kong (64 respondents, flagged low reliability).
Their earlier omission was a collection error, not absence of source data.
In 2021 the monitor displays zero estimated volume despite positive respondent
counts (267 for mainland China and 44 for Hong Kong). These outputs do not
establish zero actual travel and remain excluded pending source clarification.
Survey estimates, all-mode border arrivals and
leisure-only tourists are not spliced together. Later all-mode mainland
arrivals and pre-2023 U.S.-nationality Hong Kong arrivals remain unverified.

Historical comparisons take priority over isolated snapshots. Interactive
charts use legible native-size typography, restrained grid lines and markers,
rounded axis intervals, and a latest-value end label for single-series plots.
Long bar labels wrap without dropping the reference year. SVG/PNG exports
retain the reference project's serif palette and both publication backgrounds;
changes in population and missing years still break the plotted lines.
The interactive plotting area is proportional to its width rather than fixed
at a shallow desktop height. Desktop axes use 17px type, phone axes 14px, and
large-value ticks use one declared scale (for example, trips in millions).

`data/site/immigration.json` freezes 181 observations from 23 reviewed sources:
three OHSS birthplace workbooks/archives, ten OHSS nationality/admission reports,
the UN DESA International Migrant Stock 2024 workbook and nine DSEC yearbooks.
UN stocks cover six published 1 July benchmarks (2000, 2005, 2010,
2015, 2020 and 2024), in both directions for mainland China/Hong Kong.
Mainland-China destination uses U.S. citizenship; the other reviewed routes
use birthplace. They are resident stocks, not annual arrivals or grants.
No separate reviewed U.S.-Macau stock is reported; absence is not zero.
Attribution and CC BY 3.0 IGO terms accompany the selected UN aggregates.

OHSS country-of-birth histories cover fiscal years 1989-2024 for
mainland China, Hong Kong and Macau. These are grants of lawful permanent
residency, including both new arrivals and adjustments by people already in
the U.S.; birthplace is not nationality or a departure country. Historical
source vintages remain explicit; FY2015-2024 cells are rounded to the nearest
ten rather than presented as exact counts.

A separate nationality/admission-type history covers every FY2016-FY2025.
The FY2025 DHS China category reports 65,670 total grants, 27,020 new arrivals
and 38,650 adjustments. These are each report's full-year Total columns, not
sums of quarterly values. Each year retains its preliminary Q4 administrative
vintage; it is not a harmonized final-yearbook revision. FY2016-FY2022 counts
are exact as published; FY2023-FY2025 are rounded to ten. Nationality is not
birthplace or previous residence, so the two populations are never spliced.
The actual plotted years determine each caption. U.S. fiscal years end September 30.

The original DSEC 2008 table 2.2.9 and compatible table 2.10 republications
extend the separate U.S.-category residence-approval history to 2007-2025.
The 2007 count is 109; the independent 2009 edition repeats it and the
retained 2008/2009 counts of 112/125. The 2008 original explicitly identifies
identity-document issuing country, not citizenship. Its method note says
that the revised compilation is not directly comparable with figures before
2007. Those earlier-method figures are not joined. The 2002/2004/2006
selected-resident end-of-year tables are not imported or differenced to fill
earlier years; this remains residence approval, not a verified permanent-
resident legal classification or a count of physical U.S. departures.
The extension adds 47 observations while preserving all 133 prior observation
dictionaries exactly. Selective cached review uses `--birthplace-only`,
`--admissions-only` or `--macau-only`; complete previously reviewed vintages
remain valid during staged updates.

No comparable annual U.S.-to-mainland-China permanent-residency series has been
verified here. China-wide totals for foreign permits or border crossings do
not fill that bilateral gap.

```sh
.venv/bin/python scripts/build_immigration_data.py
.venv/bin/python scripts/build_travel_data.py
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_immigration.py -q
```

Retrieval is explicit/manual; `--refresh` rechecks the reviewed immigration source
assets. The ordinary build is offline. JSON, all source observations as CSV,
and every plotted value as CSV are complete downloads. Both publication
backgrounds have matching PNG/SVG figures under `immigration/`. Missing or
confidential cells stay distinct from zero; raw source files are not published.

### Public opinion in both directions

`opinions.html` provides eight separately defined views: U.S. favorable/unfavorable
opinion, Chinese warmth toward the U.S., each public's actual age bands, U.S.
warmth over four survey rounds and by age, and the earlier U.S. telephone and
Chinese Pew histories. The complete `data/site/opinions.json` contains 74 reported
estimates, 22 series and 32 survey rounds. All observations, survey dates,
definitions and source identities are downloadable, including observations not
selected in the default chart.

Percent favorable and mean **0-100 rating points** are never joined, indexed or
relabelled as one another. Fifty is neutral on the latter scale. Every opinion
plot retains a 0-100 scale in both the interactive view and the PNG/SVG exports.
Sparse survey rounds use bars, not continuous annual-looking lines. Each export
is available in both publication backgrounds. Exact values work on hover,
keyboard and touch; static figures and complete tables work without JavaScript.

Pew's U.S. favorable/unfavorable telephone and probability-panel histories remain
separate even in their overlapping 2020 year. The current favorable-opinion age
bands are **18-34, 35-49 and 50+**, from March 23-29, 2026, though published in
July. The newer warmth question uses **18-49 and 50+**, from September 14-20.
The China Pulse age bands are **18-29, 30-39, 40-49 and 50+**, from April 16-June
26. They are not rebinned into allegedly matched generations.

The China Pulse October 2026 report reweights **both** waves. Its late-2025 mean
is 33, not the earlier release's 34; this release's common weights are retained
throughout the comparison. The Chinese quota panel is not represented as Pew's
probability panel. The September U.S. China-item base is 1,168, not all 5,193
people in the survey; subgroup sample sizes are not inferred.

```sh
.venv/bin/python scripts/build_opinion_data.py --cached
.venv/bin/python scripts/build_site.py
.venv/bin/python scripts/build_exchange_publication.py --output data/local/publication
.venv/bin/python scripts/check_opinion_publication.py --site data/local/publication
```

The daily check revisits reviewed source releases for revisions and preserves
the frozen data on failure. New publications, question changes or age categories
require explicit source review, not automatic splicing. Timestamp-only checks
do not rewrite the publication. The reviewed Pew warmth means are in
`data/reviewed/opinion-warmth.json`: its fingerprint identifies our factual
transcription, not the publisher article. The separately retained topline PDF
verifies wording, dates and bases, not the means. No means are reconstructed
from rounded response bins. Source reports and microdata are not redistributed.

### Public chart freshness, annual bars and COVID context

The public website now excludes histories without a reported observation in
2023 or later, and independent snapshots outside 2024–2026. This applies to
individual route controls, regional panes, topic selectors and downloadable
graphics. Null/suppressed cells and recent upload timestamps cannot make a
stale series current. Older points remain in an eligible history; independently
dated program inventories are filtered individually. Complete canonical CSV/JSON
downloads still contain every archived observation.

Single-series levels use calendar-spaced columns in both interactive charts
and PNG/SVG exports. Missing years remain empty and actual zero observations
retain zero-height bars. Multi-series comparisons and baseline indices retain
lines. Reverse-direction controls and chart links expose available two-way
histories without substituting an incompatible measure.

Immigration opens with FY2016-2025 new permanent-resident arrivals for Chinese
nationals. Status adjustments for people already in the U.S. are separate.
Neither is a count of departures from mainland China. The reverse annual
U.S.-to-mainland-China count remains unverified; UN resident stocks are never
differenced or relabelled as yearly arrivals.

Travel-linked time-series charts covering 2020–2022 shade the principal COVID travel-restriction
years. This is context, **not a universal travel ban or causal attribution**.
The public explanation and `downloads/covid-context.json` link original U.S.,
mainland, Hong Kong and Macau notices. Country-specific U.S. restrictions ended
November 8, 2021; mainland quarantine measures changed January 8, 2023.
Hong Kong and Macau nonresident restrictions had different dates and exemptions.
Goods-trade charts use the same 2020–2022 visual window with a separate
**COVID-19 period** label, not the travel-restriction explanation. This does
not indicate a suspension of goods trade or estimate the pandemic's causal
effect. Services trade remains unshaded. Each applicable annotation appears
in both export backgrounds without altering data, filling missing years,
changing the chart scale or moving the 2019 comparison baseline.

`scripts/check_public_freshness.py --site PATH` examines every public plot model,
SVG export and enabled individual route, including retired deep links. The plot
audit checks column coordinates, calendar gaps, hover values and annotation
layout on desktop and small screens.

## Definitions and comparisons

- History starts in 2000 **where verified**. The publication does not pretend
  each series is complete from that year or has the same latest period.
  Goods, BEA services and visitors to the U.S. now have annual coverage from
  2000. Macau-bound arrivals start in 2003, Taiwan-bound arrivals in 2012, and
  student coverage varies by source. Missing earlier years are not estimated.
- Student measures are distinct: enrolled-only, including OPT, internationally
  mobile degree students, and U.S. academic-credit study abroad. Enrolled-only
  IIE histories cover 2007-2025 for all four geographies, with OPT excluded.
  Academic years retain their labels and use ending
  years on the chart. Exact academic start/end dates are not invented.
- IIE's OPT-inclusive population expands in 2020/21–2022/23 to include online
  coursework from outside the U.S. regardless of visa status, then returns to
  the pre-pandemic definition in 2023/24. Distinct comparison identities break
  chart lines at 2020/21 and 2023/24; the full-history index is unavailable
  because those populations cannot all share the 2019 baseline. Latest
  2024/25-versus-2018/19 comparisons remain valid. Study-abroad participation
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
  be compared with 2019.
- BEA goods/services use nominal USD and balance-of-payments accounting.
  Comtrade Macau goods use customs accounting: U.S. exports FOB, imports CIF.
  Cross-geography totals are not produced. BEA's current annual workbook has a
  repeated 2000 label and no 2001 label. Those two annual years use the correctly
  labelled December 5, 2024 official workbook, retaining that older vintage and
  its exact provenance. Current-release quarterly data and later annual years
  remain separate. No year is inferred from row position.
- Latest complete annual values compare with **2019**, not 2020. Academic
  baselines use 2018/19. Absolute and percent changes require matching
  populations, units, series and period coverage. Zero or unavailable
  baselines never produce an invented percentage.
- The partial-year panel compares identical January-to-month or Q1-to-quarter
  intervals with 2019 and the prior year. Quarterly BEA sums are seasonally
  adjusted and separate from the annual definition. Provisional NTTO months
  propagate provisional status into derived YTD totals.
- Missing, suppressed and absent years remain gaps. Chart paths also break on
  definition changes. No forward fill, interpolation, annualization, composite
  exchange score, or causal inference is used.

[Source contracts and specific gaps](SOURCES.md) document primary links and
rejected substitutes. Mainland U.S.-attributed all-mode visitor history after
2018 and several degree-enrollment directions remain unverified or blocked.
Hong Kong's full 2000-2025 arrival history is recovered with a documented
population break. Macau services now have directly published BEA annual
histories for 2018-2025 in both directions, including the 2019 baseline.
Current and archival USTR vintages remain separate, not spliced into BEA.
Missing observations show a
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

These exercise every geography/direction/measure, exact values and 2019
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
