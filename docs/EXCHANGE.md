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

Use the chart's **Background** selector to preview either version; all PNG/SVG
download links and the category catalog work without JavaScript. On narrow
screens, charts retain an 800-pixel minimum width instead of shrinking labels
to unreadable text. They scroll horizontally by touch or keyboard, initially
showing the most recent years; exact tables remain available underneath.
Downloads explicitly contain reported values even when the interactive chart
is showing an index.

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
rejected substitutes. In particular, U.S.-origin mainland/Hong Kong visitor
coverage, several degree-enrollment directions and Macau services remain
unverified or blocked. Selecting one shows its specific gap instead of a zero.

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

Network errors, HTTP failures and exhausted retries mark a source degraded
(or unavailable if it never supplied data). Malformed candidates, changed
layouts, incompatible units, ambiguous source totals and invalid values fail
the run before candidate publication files are written. Per-file publication
writes are atomic; the validated Git commit is the published snapshot boundary.
No automatic commit occurs on a failed check.
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

IIE's reviewed 2025 PDFs are re-fetched daily, but discovering/accepting a **new
annual edition requires manual review**. Update its URLs and parser only after
checking the new report's table layout and definitions. Some official index
pages return 403; do not bypass those restrictions. Macau's selected-market
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
