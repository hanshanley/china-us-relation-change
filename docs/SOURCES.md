# Source contracts

The dashboard follows U.S. exchanges with mainland China, Hong Kong, Macau,
and Taiwan separately, from 2010. Missing coverage is not zero.

| Domain | Primary source | Contract and limitation |
|---|---|---|
| Degree enrollment | [UNESCO UIS](https://api.uis.unesco.org/api/public/documentation/) | Bilateral inbound tertiary degree/diploma mobility; exclude credit exchanges. Geo units use ISO alpha-3, including `MAC`, not numeric codes. Taiwan is not a separately available UIS reporting geography. |
| International student totals and credit study abroad | [IIE Open Doors](https://opendoorsdata.org/data/all/) | U.S. totals include OPT; pandemic coverage differs. Credit study abroad is a separate measure. Public pages/downloads currently return HTTP 403 from this environment; no access controls are bypassed. |
| Goods | [Census](https://www.census.gov/foreign-trade/balance/) | U.S.-reported, nominal, unadjusted trade, million USD in country balance tables. API currently requires a key; the historical `www2` archive is not a current-data substitute. |
| Services | [BEA](https://www.bea.gov/data/intl-trade-investment/international-services-expanded) | Cross-border services only, not affiliate sales. The public legacy country factsheet endpoint has a December 2020 vintage and must not be mistaken for a current release. |
| Visitors to U.S. | [NTTO I-94](https://www.trade.gov/i-94-arrivals-program) | Official country-of-residence visitor trips, including non-leisure purposes; annual and monthly spreadsheets are public. |
| Visitors from U.S. | [NTTO SIAT](https://www.trade.gov/survey-international-air-travelers-siat), destination authorities | Preserve residence/citizenship, overnight/same-day, and air/all-mode distinctions. Never use flight passengers as tourists. |
| Hong Kong arrivals | [HKTB](https://www.discoverhongkong.com/eng/hktb/newsroom/tourism-statistics.html) | Check U.S. residence and overnight/all-visitor columns separately. |
| Macau arrivals | [DSEC](https://www.dsec.gov.mo/timeseriesdatabase.aspx?keyindicatorid=27&lang=en-US) | Country-of-residence visitor arrivals; distinguish excursionists and overnight tourists. |
| Taiwan arrivals | [Tourism Administration](https://stat.taiwan.net.tw/) | U.S. residence versus nationality must be explicit. |
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
available, and successful retrieval dates. Public government facts may be
redistributed with attribution; do not redistribute restricted Open Doors
materials without checking the applicable terms.
