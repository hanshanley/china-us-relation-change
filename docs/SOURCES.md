# Source contracts

The dashboard follows U.S. exchanges with mainland China, Hong Kong, Macau,
and Taiwan separately, from 2010. Missing coverage is not zero.

| Domain | Primary source | Contract and limitation |
|---|---|---|
| Degree enrollment | [UNESCO UIS](https://api.uis.unesco.org/api/public/documentation/) | Bilateral inbound tertiary degree/diploma mobility; exclude credit exchanges. Geo units use ISO alpha-3, including `MAC`, not numeric codes. Taiwan is not a separately available UIS reporting geography. |
| International student totals and credit study abroad | [IIE Open Doors country sheets](https://opendoorsdata.org/2025-country-and-area-fact-sheet-pdfs/) | The reviewed 2025 PDFs are accessible even though some index/data pages return 403. All four geographies: 2017/18–2024/25 totals including OPT; credit participation through 2023/24. Enrolled-only counts for 2023/24 and 2024/25 sum undergraduate, graduate and non-degree counts, excluding OPT. PDFs are rechecked daily; new report discovery requires manual review. |
| Goods and services, China/Hong Kong/Taiwan | [BEA geographic history](https://www.bea.gov/data/intl-trade-investment/international-trade-goods-and-services) | Discover the `geo-time-series.xlsx` download. Tables 4/5: goods exports/imports; 7/8: services exports/imports. **Balance-of-payments basis**, not Census customs trade. Multiply million USD by 1,000,000. Annual history from 2010; matched YTD sums of complete seasonally adjusted quarters, separately defined from annual totals. Macau is not separately reported. |
| Macau goods | [UN Comtrade public API](https://comtradeapi.un.org/) | U.S. reporter 842, Macao partner 446, aggregate HS TOTAL, annual flows X/M. Exports FOB; imports CIF. These are customs statistics, not BEA BOP; the differing import valuation is conspicuous. No uncertain Taiwan mapping is used. |
| Visitors to U.S. | [NTTO I-94](https://www.trade.gov/i-94-arrivals-program) | Official country-of-residence visitor trips, including non-leisure purposes; annual and monthly spreadsheets are public. |
| Visitors from U.S. | [NTTO SIAT](https://www.trade.gov/survey-international-air-travelers-siat), destination authorities | Preserve residence/citizenship, overnight/same-day, and air/all-mode distinctions. Never use flight passengers as tourists. |
| Hong Kong arrivals | [HKTB](https://www.discoverhongkong.com/eng/hktb/newsroom/tourism-statistics.html) | Check U.S. residence and overnight/all-visitor columns separately. |
| Macau arrivals | [MGTO statistical reports](https://dataplus.macaotourism.gov.mo/Publication/StatisticalTables?lang=E) | Discover December Tourism Highlights PDFs, 2010 onward, citing DSEC. Extract U.S. source-market cumulative annual arrivals, including same-day and overnight. Selected-market tables sometimes omit the U.S.; that is missing, not zero. Ambiguous numeric totals fail publication. The 2020 PDF contains a stale Jan–Nov section heading, but its surrounding text and annual totals identify the 2020 full year. |
| Taiwan arrivals | [Government open-data catalog](https://data.gov.tw/dataset/45512), [official CSV](https://stat.taiwan.net.tw/data/opendata/6) | Public annual purpose-by-residence CSV starts 2012. U.S. residence rows provide total arrivals and a separate declared-sightseeing series. The interactive API rejected requests; the explicitly public CSV is accessible without bypassing that restriction. |
| Mainland arrivals/enrollment | [NBS](https://www.stats.gov.cn/english/), [MOE](https://en.moe.gov.cn/) | Verify the bilateral breakdown for each publication; national totals do not establish U.S.-specific counts. |

## Interpretation

Students are stocks or academic-year participation, not departures. UIS degree
mobility, Open Doors enrollment-plus-OPT, and academic-credit study abroad are
different series and must never be spliced. Academic years use their ending year
for the 2020 baseline, with the original period label retained.

Trade direction follows goods/services, not payment direction: U.S. exports are
U.S. to partner; U.S. imports are partner to U.S. Source revisions replace earlier
vintages. Missing or suppressed observations remain nullable.

All change calculations require matching definition and period coverage. Partial
years compare identical intervals only. Geography totals are not summed across
destinations; one traveler may visit multiple places.

The generated coverage download records actual available periods for every
requested geography/direction/measure, including reasons for unavailable series.
Source manifests record exact public requests, checksums, source vintage where
available, and successful retrieval dates. Only numerical observations and
original definitions are published, with attribution. Raw workbooks, PDFs,
source page text, and source artwork remain local; no license to redistribute
those third-party documents is asserted. Taiwan's catalog identifies the
government open-data license. Consult publisher terms before redistributing
raw material; the dashboard does not redistribute IIE fact sheets.

## Verified gaps and rejected substitutes

The audit on October 21, 2026 also checked the following:

- Census current API returns a missing-key page and country tables return 403.
  Its accessible `www2` archive is stale. BEA's current geographic history is
  the documented alternative, not a silently equivalent Census series.
- The legacy BEA factsheet endpoint is frozen at December 2020. Modern iTable
  data requests returned empty tables. Neither is used.
- Hong Kong's official data.gov.hk dataset `650-80001` links C&SD JSON/CSV/XLS
  resources. Those resources and HKTB returned 403; the public archive returned
  no matching snapshot. U.S.-to-Hong Kong visitor arrivals remain a gap.
- No current U.S.-origin mainland all-mode arrival table was verified in the
  official yearbook/authority sources. SIAT air-travel or flight passengers are
  not substituted. A new adapter needs an actual country table and its definition.
- UIS origin indicator 26503 to CHN returned no records. Taiwan is not a UIS
  destination/origin in this catalog. Some UIS reporting years are absent even
  inside a series; chart lines must break at those gaps. Indicator 26528 is
  China, 26532 Hong Kong, 26547 Macau; `geoUnit` is the destination.
- IIE OPT-inclusive totals, enrolled-only counts, UIS degree mobility and U.S.
  credit-study-abroad participation remain separate measures. IIE study-abroad
  2024/25 is explicitly null, not a newer available observation.
- Macau bilateral services are not separately available in the selected-country
  BEA workbook. Comtrade service-preview requests returned no records; no
  regional allocation or mirror-series substitution is made.

The source-specific coverage download is generated for every geography,
direction and measure. Some combinations are outside the source's population,
not evidence that no such exchange occurs.

## Source updates and comparability

The September 3, 2026 BEA release currently supplies annual 2025 and quarterly
2026 Q2 data. NTTO's annual file supplies 2025; its monthly file includes
September 2026 preliminary figures. Workbook modification timestamps are
explicitly **not publication dates**. UIS indicator metadata identifies its
February 2026 release. Every observation retains its exact request URL, source
vintage, retrieval time and SHA-256 of its local raw response.

YTD rows are derived only when all January-to-cutoff months or Q1-to-cutoff
quarters exist. The same cutoff is used for the current, prior and 2020 years.
Official annual NTTO values are not overwritten with sums of revised monthly
data. Their discrepancies can be revisions, not parser corrections.
