<div align="center">
  <h1>U.S.–China Exchange</h1>
  <p>
    <a href="#tracking-change-since-2000">Overview</a> ·
    <a href="#explore-the-evidence">Analyses</a> ·
    <a href="#setup">Setup</a> ·
    <a href="https://www.themarginoferror.com/china-us-relations/">Live site</a>
  </p>
</div>

---

U.S.–China Exchange is an interactive study of how ties between the United
States and China have changed since 2000: student exchanges, travel and
tourism, migration, goods and services trade,
business presence, public opinion, language learning, institutions and media.
The analyses follow these different dimensions of the relationship rather than
reducing them to a single measure.

Explore changes in both directions where data are available, with distinct
comparisons for mainland China, Hong Kong and Macau. Taiwan observations are
retained separately in the complete research data.

<p align="center">
  <a href="https://www.themarginoferror.com/china-us-relations/">
    <img src="https://www.themarginoferror.com/artifacts/china-us-relations/us-china-fractured-network.webp" width="1200" alt="U.S.–China Exchange illustrated as a fractured network">
  </a>
</p>

## Explore the evidence

**Movement and exchange:** [student enrollment and study abroad](https://www.themarginoferror.com/china-us-relations/),
[travel and tourism](https://www.themarginoferror.com/china-us-relations/travel.html),
and [goods and services trade](https://www.themarginoferror.com/china-us-relations/trade.html).
Both directions are available where verified. Student-enrollment charts show
enrolled students plus OPT; academic-credit study abroad remains separate.
Visitor trips are not unique people or necessarily leisure travel; goods and
services remain separate.

**Migration and attitudes:** [immigration](https://www.themarginoferror.com/china-us-relations/immigration.html)
distinguishes annual permanent-resident admissions from resident stocks and
includes a 50-state/DC China-born resident map.
[Public opinion](https://www.themarginoferror.com/china-us-relations/opinions.html)
covers both directions and age comparisons, keeping favorable percentages
separate from warmth scores and preserving each survey's population.

**Language and institutions:** [Chinese, Japanese and Korean](https://www.themarginoferror.com/china-us-relations/language-learning.html)
are compared separately through available course, degree and school indicators.
[Confucius Institutes and Classrooms](https://www.themarginoferror.com/china-us-relations/confucius.html)
distinguishes dated counts, directory listings and documented successors.
[Business presence](https://www.themarginoferror.com/china-us-relations/business-presence.html)
keeps source populations and enterprise definitions separate, without combining
different European countries into an invented total.

**Media connections:** [U.S. media on Weibo](https://www.themarginoferror.com/china-us-relations/weibo.html)
is an evidence-backed directory of accounts and Chinese-language editions,
not an exhaustive census or a measure of popularity. See the
[research inventory](reports/weibo_media_inventory.md) and
[collector guide](docs/WEIBO.md) for identity evidence and recovery limits.

## Working with the charts

Charts provide source notes, exact values through hover, touch or keyboard,
and complete CSV/JSON downloads. The research figure collection is in
[`outputs/figures/`](outputs/figures), organized by topic. Editable SVG and
high-resolution PNG versions use the same house style as `uk_decline`, with
**The Margin of Error** (`#F7F5F0`) and **Substack** (`#F5F5F5`) backgrounds.

The public edition shows histories reaching at least **2023** and standalone
snapshots from **2024-2026**, using measurement dates rather than upload dates.
Complete downloads and the offline research edition retain older observations;
the archive is not the current public chart selection.
Single-series annual levels use bars, with missing years left blank. Shading
marks the principal **2020-2022 COVID travel-restriction years**, not a universal
ban or an explanation of every change.

## Setup

Python 3.9+:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-exchange-dev.txt
```

Build from the committed data without fetching sources:

```bash
./.venv/bin/python scripts/build_site.py
./.venv/bin/python scripts/build_exchange_publication.py --output data/local/publication
```

Open `site/index.html` for the complete offline research edition, or
`data/local/publication/index.html` for the filtered public edition.
The builders also generate downloads and chart exports.

```bash
./.venv/bin/python scripts/update.py                         # check supported sources
PYTHONPATH=src ./.venv/bin/python -m pytest tests/test_exchange_*.py -q
```

See [methods and operation](docs/EXCHANGE.md), [source contracts](docs/SOURCES.md),
and the [Weibo CLI guide](docs/WEIBO.md) for source-specific commands and checks.
