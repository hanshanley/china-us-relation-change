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
.venv/bin/python -m pip install -r requirements-exchange.txt
.venv/bin/python scripts/update.py
.venv/bin/python scripts/build_site.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_exchange_*.py -q
```

`update.py` checks official releases and reconciles the full small-source history.
`build_site.py` performs **no network requests**; it reproduces the website,
complete downloads and SVG figures from committed publication tables.

| Location | Purpose |
|---|---|
| `src/us_china_exchange/` | Model, source parsers, refresh orchestration, static rendering |
| `data/site/observations.json` | Canonical observations, including explicit missingness and provenance |
| `data/site/coverage.json` | All four geographies, both directions, eight distinct measures |
| `data/site/sources.json` | Published source health, release vintage and recorded check dates |
| `data/local/exchange/raw/` | Local raw responses named by SHA-256; ignored, not redistributed |
| `data/local/exchange/check.json` | Actual latest attempt, including unchanged checks and failures |
| `site/` | Generated offline website, accessible tables, complete CSV/JSON downloads |
| `outputs/figures/` | Matching standalone SVG figures |
| `tests/fixtures/exchange_reviewed_2026-10-21.json` | Frozen numeric review checkpoints, not a constraint on future source revisions |

Every downloaded observation has its definition, direction, unit, period basis,
status, exact source request, release/vintage label, retrieval timestamp and
raw-response checksum. `exchange.json` also contains sources and coverage.
CSV exports contain full observation rows, not just a source inventory.
Raw third-party PDFs and workbooks are deliberately not published.

## Definitions and comparisons

- History starts in 2010 **where verified**. The publication does not pretend
  each series is complete from that year or has the same latest period.
- Student measures are distinct: enrolled-only, including OPT, internationally
  mobile degree students, and U.S. academic-credit study abroad. Enrolled-only
  IIE counts are available for only two recent years; there is no 2020 baseline
  for that specific series. Academic years retain their labels and use ending
  years on the chart. Exact academic start/end dates are not invented.
- UIS reporting years are not physical-presence years. Fractional source
  estimates are preserved, including in exact tables and downloads.
- Visitor counts are trips, not unique tourists. NTTO is residence-based,
  qualified-visa, overnight, all-purpose visitation. Taiwan and Macau counts
  include broader arrival populations. Only Taiwan currently supplies a
  separately verified sightseeing-purpose series.
- BEA goods/services use nominal USD and balance-of-payments accounting.
  Comtrade Macau goods use customs accounting: U.S. exports FOB, imports CIF.
  Cross-geography totals are not produced.
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

Network errors, HTTP failures and exhausted retries mark a source degraded
(or unavailable if it never supplied data). Malformed candidates, changed
layouts, incompatible units, ambiguous source totals and invalid values fail
the run before candidate publication files are written. Per-file publication
writes are atomic; the validated Git commit is the published snapshot boundary.
No automatic commit occurs on a failed check.

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
PDFs can omit the U.S. or rasterize tables. The 2024 annual value was visually
reviewed in both image tables and locked to the PDF checksum; a changed
unextractable PDF fails pending renewed review. Other unverified values remain
missing, not zero. Its adapter covers annual December reports, not current
monthly highlights. The coverage matrix exposes those limits.

For browser checks:

```sh
.venv/bin/python -m pip install -r requirements-exchange-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/check_exchange_browser.py
```

These exercise every geography/direction/measure, exact values and 2020
changes, the partial-year panel, index mode, keyboard interaction, mobile
overflow, and no-JavaScript tables. Unit tests cover source units/directions,
mixed Excel header types, leap February, missingness, source outages/recovery,
numeric revisions, malformed-input rollback, unchanged refreshes and
byte-identical offline rebuilds. Review checkpoints are frozen to their source
vintage so later legitimate revisions are not blocked by obsolete constants.

No raw source documents or browser screenshots are committed. A source's
SHA-256 references the locally retained raw response; GitHub-hosted runners
are ephemeral, so preserve raw inputs privately if archival replication of a
particular online release is needed. The canonical numeric publication and
offline figures remain reproducible from Git.
