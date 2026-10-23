# Source contracts

The dashboard follows U.S. exchanges with mainland China, Hong Kong, Macau,
and Taiwan separately, from 2000 where verified. Missing coverage is not zero.

| Domain | Primary source | Contract and limitation |
|---|---|---|
| Degree enrollment | [UNESCO UIS](https://api.uis.unesco.org/api/public/documentation/) | Bilateral inbound tertiary degree/diploma mobility; exclude credit exchanges. Geo units use ISO alpha-3, including `MAC`, not numeric codes. Taiwan is not a separately available UIS reporting geography. |
| International student totals and credit study abroad | [IIE Open Doors country sheets](https://opendoorsdata.org/2025-country-and-area-fact-sheet-pdfs/) | Retained reviewed 2025 snapshot, not automatically refreshed: IIE's terms prohibit automated downloading/analysis and separate permission is not verified. All four geographies: 2017/18–2024/25 totals including OPT; credit participation through 2023/24. Enrolled-only counts for 2023/24 and 2024/25 sum undergraduate, graduate and non-degree counts, excluding OPT. New retrieval/reuse requires permission review as well as layout/definition review. |
| Historical student aggregates | [EducationUSA 2021 official regional compilation](https://educationusa.state.gov/sites/default/files/educationusa/2021_EAP_COMBINED_SMFF.pdf) and [NCES Digest](https://nces.ed.gov/programs/digest/) | Government republications only; no direct IIE retrieval. CHN/HKG/TWN inbound OPT-inclusive histories now cover 2000-2025; Macau 2015-2025. Credit participation covers 2014-2024 for all four geographies, plus mainland 2007/08. Exact 2020/21 enrolled-only level sums are separate from OPT and from the standard-population 2023/24 onward. Raster chart labels are checksum-pinned; all retained overlaps must reconcile. Conflicting Hong Kong 2017 stock-chart label is rejected in favor of the original NCES count. |
| Goods and services, China/Hong Kong/Taiwan | [BEA geographic history](https://www.bea.gov/data/intl-trade-investment/international-trade-goods-and-services) | Discover the `geo-time-series.xlsx` download. Tables 4/5: goods exports/imports; 7/8: services exports/imports. **Balance-of-payments basis**, not Census customs trade. Multiply million USD by 1,000,000. Annual history from 2000; matched YTD sums of complete seasonally adjusted quarters, separately defined from annual totals. The current workbook's repeated 2000 / missing 2001 annual labels require the independently labelled December 2024 archive for those two years; no row-position correction. Macau is not separately reported. |
| Macau goods | [UN Comtrade public API](https://comtradeapi.un.org/) | U.S. reporter 842, Macao partner 446, aggregate HS TOTAL, annual flows X/M. Exports FOB; imports CIF. These are customs statistics, not BEA BOP; the differing import valuation is conspicuous. No uncertain Taiwan mapping is used. |
| Macau services | [USTR Macau Trade Summary](https://ustr.gov/countries-regions/china-mongolia-taiwan/macau) | Direct estimated 2025 U.S. services exports $434.0m and imports $208.0m. Reconciled with $642.0m total and $226m surplus, retaining quoted rounding. Nominal cross-border services, not affiliate sales. Older years are not inferred from rounded year-on-year changes. |
| Visitors to U.S. | [NTTO I-94](https://www.trade.gov/i-94-arrivals-program) | Official country-of-residence visitor trips, including non-leisure purposes; annual and monthly spreadsheets are public. |
| Visitors from U.S. | [NTTO SIAT](https://www.trade.gov/survey-international-air-travelers-siat), destination authorities | Preserve residence/citizenship, overnight/same-day, and air/all-mode distinctions. Never use flight passengers as tourists. |
| Hong Kong arrivals | [HKTB](https://www.discoverhongkong.com/eng/hktb/newsroom/tourism-statistics.html) | Check U.S. residence and overnight/all-visitor columns separately. |
| Macau arrivals | [MGTO statistical reports](https://dataplus.macaotourism.gov.mo/Publication/StatisticalTables?lang=E) | Discover December Tourism Highlights PDFs and full annual market profiles, citing DSEC. Profiles extend verified history to 2003; 2000–2002 remain unverified. Extract U.S. source-market cumulative annual arrivals, including same-day and overnight. Selected-market tables sometimes omit the U.S.; that is missing, not zero. Ambiguous numeric totals fail publication. The 2020 PDF contains a stale Jan–Nov section heading, but its surrounding text and annual totals identify the 2020 full year. |
| Taiwan arrivals | [Government open-data catalog](https://data.gov.tw/dataset/45512), [official CSV](https://stat.taiwan.net.tw/data/opendata/6) | Public annual purpose-by-residence CSV starts 2012. U.S. residence rows provide total arrivals and a separate declared-sightseeing series. The interactive API rejected requests; the explicitly public CSV is accessible without bypassing that restriction. |
| Mainland arrivals/enrollment | [NBS](https://www.stats.gov.cn/english/), [MOE](https://en.moe.gov.cn/) | Verify the bilateral breakdown for each publication; national totals do not establish U.S.-specific counts. |

## Chinese-language learning sources

The separate language-learning publication does not add domestic registrations,
global exams, program inventories or degree awards to bilateral observations.
Complete source asset identities and checksums are in
`data/site/language_learning.json` and its downloadable copy.

| Primary source | Contract |
|---|---|
| [MLA fall 2021 report](https://www.mla.org/content/download/191324/file/Enrollments-in-Languages-Other-Than-English-in-US-Institutions-of-Higher-Education-Fall-2021.pdf), Table 5, PDF page 63 | Consistent published-report history for Chinese/Mandarin, Japanese, Korean, Spanish and all languages. Course registrations, undergraduate and graduate, not unique students. All-language denominator includes ASL/classical languages. No fabricated annual observations. |
| [MLA historical workbook](https://www.mla.org/content/download/191323/file/Historical-language-enrollments-1958-2021.xlsx), `FL history` | Match responding `INST_ID`s in 2013/2021, exclude `N_RESP=NR` even when a placeholder count is zero, and retain explicit `ZERO_ERL=Z`. Exclude institutions with any unreported language-count row in either endpoint; missing counts are not zeros. Chinese is exact CHINESE plus MANDARIN; do not deduplicate legitimate repeated language rows. National endpoint sums independently reconcile to the report. |
| [MLA pandemic snapshot](https://www.mla.org/content/download/191129/file/Fall-2022-NL-snapshot.pdf) | Separate 2016/2020 matched-institution comparison underlying the Economist article, not a 2020 national census or part of the 2021 national series. |
| [College Board AP archive](https://reports.collegeboard.org/ap-program-results/data-archive) and [Chinese 2025 subject report](https://apcentral.collegeboard.org/media/pdf/ap25-chinese-language-score-distributions.pdf) | Global annual administration history 2007-2025. Subject-specific reports supersede overlapping earlier program-volume vintages. Parse **Number of Students**, not the number scoring 3+. Standard group is a subset, not U.S. geography or a nonheritage/ancestry classification; never add it to total. |
| [AP Report to the Nation 2011](https://secure-media.collegeboard.org/digitalServices/public/pdf/ap/rtn/AP-Report-2011-Subject-Supplement.pdf), [2013 supplement](https://secure-media.collegeboard.org/digitalServices/pdf/ap/rtn/9th-annual/9th-annual-ap-report-subject-supplement-all-subjects.pdf), [2014 Chinese supplement](https://secure-media.collegeboard.org/digitalServices/pdf/ap/rtn/10th-annual/10th-annual-ap-report-subject-supplement-chinese-language-and-culture.pdf) | U.S. public-school graduating cohorts 2007-2013. Sum five total-group score categories; year is the graduating class, with exams taken throughout high school. Later report vintages take priority for overlapping cohorts, including the revised 2008 total. Never splice into annual global administrations. |
| [NCES IPEDS public files](https://nces.ed.gov/ipeds/datacenter/data/), `CYYYY_A.zip` plus annual institutional directory | Exact CIP 16.0301, 50 states/DC, degree-granting and Title IV eligibility; first-major `MAJORNUM=1` from 2001. Use revised `_RV` CSV only when present. Modern total `CTOTALT`; older `CRACE15+CRACE16` are male plus female totals. Preserve source-flag frequencies and selected revision. |
| [NCES independent degree checkpoint](https://nces.ed.gov/programs/digest/d23/tables/xls/tabn318.30.xlsx) | Digest table 318.30 independently confirms 2022 Chinese bachelor's 364, master's 26 and doctorates 14. Awards are not unique people or all China expertise; the 2000 major-number and 2010 doctoral-classification breaks are explicit. |
| [CAL 2011 language inventory](https://webapp.cal.org/Immersion/Doc/Language%20of%20Instruction%20in%20Immersion%20Programs.pdf), [ARC 2021 canvass](https://www.americancouncils.org/sites/default/files/documents/pages/2021-10/Canvass%20DLI%20-%20October%202021-2_ac.pdf), [Nexus publications](https://nexusmandarin.org/publications-1) | 71 Mandarin directory programs, 312 Chinese public-school DLI programs and 335 U.S. inventoried immersion programs, respectively. Definitions differ; these are disconnected inventory snapshots, not comparable growth or learner counts. Nexus's state appendix independently sums to 335. |
| [American Councils June 2017 K-16 report](https://www.americancouncils.org/sites/default/files/FLE-report-June17.pdf), Table 2 | Chinese K-12 estimate 227,086 combines reported state data and model estimates, with a 2014-15-era reference period. The ending-year key 2015 is not an exact common measurement date or current census. |

The MLA workbook's 2016 totals differ from the published report: Chinese 54,285
versus 54,248 and all languages 1,419,699 versus 1,418,584. National charts retain
the report vintage; the workbook supplies only the independently reconciled
2013/2021 matched panel. This avoids a silent revision splice.

The [Economist article, August 24, 2023](https://www.economist.com/china/2023/08/24/why-fewer-university-students-are-studying-mandarin)
provides hypotheses, not causal estimates. Its rounded 21% decline belongs to
the separate pandemic snapshot. The Nexus survey's 103 responses include
102 U.S. programs plus one in Hong Kong; its 34,341 associated enrollments are
not republished as a national U.S. total. Founding years of surviving programs
are not reconstructed as past active-program inventories.

Current subject-specific AP reports are global; national/state public-school
participation workbooks aggregate subjects. No current U.S.-only annual Chinese
administration series was verified from those files. Historical U.S. cohorts
and standard-group subsets do not fill that gap. College Board's public files
are downloaded with verified-TLS system `curl`; certificate verification is
never disabled.

Retrieval is an explicit reviewed-source command, not scheduled scraping.
[MLA terms](https://www.mla.org/About-Us/About-the-MLA/Terms-of-Use-for-MLA-Network)
and unverified commercial reuse remain disclosed. No raw source reports,
institution-level workbook, report artwork or exam questions are redistributed.

## Business-presence sources

`data/site/business_presence.json` retains all 74 China-hosted observations, including
explicit confidential/unavailable cells, series definitions, source URLs,
selected table members, retrieval timestamps and SHA-256 checksums.

| Primary source | Contract |
|---|---|
| [BEA majority-owned affiliate history](https://www.bea.gov/sites/default/files/2025-08/selected-mofas-cntry.xls) | Country sheets 2009-2023, China row, first numeric column: affiliate counts above $25m assets, sales or net income/loss, not employees, dollars or unique parents. No U.S.-in-Europe series remains in this publication. 2023 is preliminary. |
| [BEA data archive](https://www.bea.gov/international/di1usdop/archives) | Retained revised 2000-2008 ZIPs: Table III.A1, including split `Tab3A1a/b/c` and the 2007 `_new` filename. Nonbank coverage and historical reporting exclusions; $7m through 2003, $10m for 2004-2008. The 2004 benchmark's original methodology confirms those thresholds. |
| [BEA 2004 benchmark](https://apps.bea.gov/international/zip/usdia2004revised.zip), [2009 parent tables](https://apps.bea.gov/international/xls/usdia_2009r/Part%20I%20K1-K2.xls), [2014 parent tables](https://apps.bea.gov/international/xls/usdia2014r/PartI-K1-K2.xls), [2019 parent tables](https://apps.bea.gov/international/xls/usdia2019r/PartI-K1-K2.xls) | Table I.M2 in 2004 and I.K2 subsequently: **Number of U.S. parents**, country by affiliate industry, All industries. Unique within each host region, not across regions. Reporting/coverage changes and minority-owned affiliates prevent substitution with majority-owned entity counts. Annual 2018, 2022 and 2023 parent-table inventories do not supply this country table. |
| [BEA definitions](https://www.bea.gov/international/usdia2023p-info), [geography](https://apps.bea.gov/international/bp_web/geographic_area_definitions.pdf), [2023 release](https://www.bea.gov/news/2025/activities-us-multinational-enterprises-2023) | U.S.-resident parents, not necessarily ultimately U.S.-owned; majority-owned foreign affiliates exceed 50% combined U.S.-parent ownership. The release confirms the 2024 activity data are scheduled for November 2026, not yet observed on October 22. |
| [Eurostat historical API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=EU27_2020&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O) | `A`, `EU27_2020`, `CN_X_HK`, `B-S_X_O`, `ENT`; 2010-2020. Validate the returned dimensions, not just the requested URL. Keep fixed EU27 membership; do not replace missing EU27 values with EU28 or sums of confidential country cells. |
| [Eurostat current API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out_part?lang=EN&geo=EU27_2020&partner=CN_X_HK&indic_sbs=ENT_NR&nace_r2=B-S_X_O), [methodology](https://ec.europa.eu/eurostat/cache/metadata/en/fats_out_sims.htm) | Same geographic/sector selection; `ENT_NR`, from 2021. `e` stays estimated; `|C` stays null/suppressed, even if the API supplied a zero placeholder. Preserve source flags, break on `b`/`d` and the 2021 EBS boundary, and fail on unknown flags. Not a matched U.S./EU count of all companies. |
| [Earlier EU membership, 2007-2009](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2?lang=EN&geo=EU27_2007&partner=CN_X_HK&indic_bp=ENT&nace_r1=C-O_X_L), [2010-2013](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=EU27_2007&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O) | `EU27_2007` includes the UK and excludes Croatia. Verified values 2009=5,688, 2011=6,607, 2012=6,860; missing/confidential years stay blank. Keep the NACE Rev. 1.1/Rev. 2 and membership transitions separate; do not relabel this as the current EU27. |
| [UK historical API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=UK&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O), [ONS 2018/2019 workbook](https://www.ons.gov.uk/businessindustryandtrade/internationaltrade/datasets/ukoutwardforeignaffiliatestatisticsofats) | UK-controlled foreign enterprises located in China. Eurostat flags breaks in 2013, 2014 and 2015. Use ONS Table 1 (2018 revised), Table 2 (2019), China, TOTAL ACTIVITY / ENT, not EMP or TUR. Counts 709 and 531 are survey-based estimates; total activity includes agriculture. The 2018 source/sector boundary is not connected. |
| [ONS coverage disclosure](https://www.ons.gov.uk/aboutus/transparencyandgovernance/freedomofinformationfoi/ukoutwardforeignaffiliatestatisticsofats2015to2025) | Latest outward-affiliate estimates remain 2018/2019; no OFATS data from 2020 onward. Newer inward-affiliate statistics concern businesses **in the UK**, the wrong direction, and are not substituted. |
| [Norway historical API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=NO&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O), [current API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out_part?lang=EN&geo=NO&partner=CN_X_HK&indic_sbs=ENT_NR&nace_r2=B-S_X_O) | All fourteen annual Norwegian-controlled enterprise counts in China, 2010-2023. Preserve the 2021 EBS method boundary. Norway is shown separately, never silently added to an EU/all-Europe total. |

Raw source archives, workbooks, publication text and artwork remain local.
Only numerical aggregates, original definitions and our figures are published.
All indicators are business-presence stocks, not border crossings, investment
flows or a composite measure of U.S.-China contact.

## Interpretation

Students are stocks or academic-year participation, not departures. UIS degree
mobility, Open Doors enrollment-plus-OPT, and academic-credit study abroad are
different series and must never be spliced. Academic years use their ending year
for the 2020 baseline, with the original period label retained.

[IIE's student-census methodology](https://opendoorsdata.org/about/about-international-student-census/)
expands the international-student definition in Open Doors 2021–2023
(2020/21–2022/23) to cover coursework from outside the U.S. regardless of visa
status, then returns to the pre-pandemic definition in Open Doors 2024
(2023/24). OPT-inclusive and recovered enrolled-only observations receive separate standard and
pandemic-expanded comparison identities. Charts break at both boundaries,
display those dates in exported figure notes, and reject the incompatible
full-history 2020 index. Standard-population 2024/25-versus-2019/20 comparisons
remain valid. This is not a definition change to the separate study-abroad
participation measure. Annual tables show each year's population definition
when it varies.

UIS responses provide reporting years rather than exact reference dates.
`period_start` and `period_end` are therefore null for reporting-year rows;
the year, source footnotes and fractional estimates remain unchanged.
Magnitude and qualifier flags are preserved in notes. `NA` source zeros become
null `not_applicable` observations, `SUPP` is `suppressed`, and `INCLUDED` is
`included_elsewhere`. `NIL` remains a flagged source zero. `LOWREL` is
`low_reliability`, while `NAT_EST` and `UIS_EST` produce `estimated` numeric
observations. `INCLUDES` remains explicitly flagged. Unknown flags and
contradictory value/flag pairs fail validation instead of silently becoming
observed counts.

Trade direction follows goods/services, not payment direction: U.S. exports are
U.S. to partner; U.S. imports are partner to U.S. Source revisions replace earlier
vintages. Missing or suppressed observations remain nullable.
Each Comtrade row must explicitly match its requested `period`/`refYear`,
annual `freqCode=A`, and goods `typeCode=C`. Mismatches fail candidate validation
rather than inheriting a year or frequency from the request.

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

### Source access and reuse restrictions

As reviewed on October 21, 2026, [IIE's terms](https://www.iie.org/terms-and-conditions/)
prohibit automated downloading/analysis and restrict commercial use. IIE's
adapter and refresh orchestrator therefore block network retrieval, retain
reviewed observations with `permission_required` health, and do not advance
their retrieval provenance. No separate permission has been verified.

[MGTO's limited license](https://dataplus.macaotourism.gov.mo/Indicator/VisitorsSummary/SummaryBar?lang=E)
states noncommercial use. Separate commercial republication permission remains
unverified. Source notes, complete JSON policy records, page notices and
affected PNG/SVG footnotes expose that limitation. Raw document exclusion and
a publication-background export do not establish reuse permission. Resolving
permission requires an actual permission review, not toggling an automated
override; these controls do not make a legal determination about factual data.

## Verified gaps and rejected substitutes

The audit on October 21, 2026 also checked the following:

- Census current API returns a missing-key page and country tables return 403.
  Its accessible `www2` archive is stale. BEA's current geographic history is
  the documented alternative, not a silently equivalent Census series.
- The legacy BEA factsheet endpoint is frozen at December 2020. Modern iTable
  data requests returned empty tables. Neither is used.
- Hong Kong's original data.gov.hk dataset `650-80001` linked resources that
  returned 403. The subsequent itemized recovery obtained a complete 2000-2025
  history from C&SD, MGTO and HKTDC official republications, preserving the
  residence/nationality break at 2023, and matching first-half 2025/2026 counts.
  The earlier failed resource requests no longer mean this route is empty.
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
- Macau bilateral services are absent from the selected-country BEA workbook,
  and Comtrade service-preview requests returned no records. **USTR separately
  reports both directions for 2025**, now recovered by its own adapter. This
  resolves the empty current services routes, not their older annual history.
  No regional allocation or mirror-series substitution is made.

The source-specific coverage download is generated for every geography,
direction and measure. Some combinations are outside the source's population,
not evidence that no such exchange occurs.

## Source updates and comparability

All adapters request or retain history from 2000, rather than discarding pre-2010
observations. Annual goods trade in all four geographies, services in the three
BEA geographies, and NTTO arrivals all cover 2000–2025 in the reviewed snapshot.
UIS student history begins in 2001 for U.S.-to-Hong Kong, 2003 for
U.S.-to-Macau, and 2005 for the three available reverse directions; gaps within
those series remain explicit. IIE country sheets still start in 2017/18.
IIE's public historical/origin/destination pages expose a member-login gate;
no protected data are retrieved or inferred. The Taiwan open CSV begins in 2012.

The current BEA workbook has two annual rows labelled 2000 and no 2001 in all
four selected tables. Annual 2000/2001 are read instead from the [December 5,
2024 official workbook](https://www.bea.gov/sites/default/files/2024-12/trad-geo-time-series-1024.xlsx),
whose labels are unambiguous. Its services values differ from the current
unlabelled rows, so those rows are not relabelled on the strength of neighbouring
years. Archive observations retain their own release, URL and checksum.
Current-release annual 2002+ and quarterly 2000+ data are unaffected.

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

### Macau annual profiles and classification break

The [2008 annual profile](https://dataplus.macaotourism.gov.mo/document/CHT/Book/MarketPerformance/2008/M12_MarketingPerformance_2008_1246941849.pdf),
PDF page 44, extends U.S.-attributed arrivals back to 2003 (**56,642**).
The [2010 profile](https://dataplus.macaotourism.gov.mo/document/CHT/Book/MarketPerformance/2010/M12_MarketPerformance_2010_1298431536.pdf),
page 42, supplies the revised 2008 total **203,198** and 2009 **179,500**.
Both identify residence attribution and explicitly exclude non-resident
workers/students starting in 2008. Pre-2008 observations have a separate
comparison identity; they are not connected to the later visitor definition.

MGTO's [December 2024 report](https://dataplus.macaotourism.gov.mo/document/ENG/Book/VAHightlights/2024/tourism%20highlights_Dec_%202024_E.pdf)
has image-only annual market tables on page 2. Both the overall selected-market
table and the long-haul-market table show **147,941 USA arrivals** for 2024;
both report +57.7% against 2023. This is an annual total, not December alone.
Direct image review initially recovered that value, but the live adapter no
longer needs a manual seed: [Market Performance 2024](https://dataplus.macaotourism.gov.mo/document/CHT/Book/MarketPerformance/2024/Market%20Performance%202024.pdf),
PDF page 42, has a machine-readable U.S. profile for 2019–2024. It confirms the
2024 value and supplies 2021 **171** and 2022 **1,777**. Its issuing-document
profile is distinct from the nationality tables elsewhere in the same report.

The archive also supplies [Market Performance 2015](https://dataplus.macaotourism.gov.mo/document/CHT/Book/MarketPerformance/2015/Market%20Performance%20%202015.pdf),
PDF page 42, covering 2010–2015: 2010 **188,254**, 2011 **196,065**, and
2012 **188,730**. Its overlapping 2013–2015 totals match the December highlights.
The adapter discovers the latest complete annual market report, rechecks the
2008/2010/2015 history, requires six complete years, and reconciles sea + land + air for
every total. Profile rows take precedence over older highlights; newer profiles
take precedence over older profiles. Exact PDF URLs, editions and checksums
remain attached to observations. No PDFs or extracted images are redistributed.

[MGTO's methodology](https://dataplus.macaotourism.gov.mo/Indicator/VisitorsSummary/SummaryBar?lang=E)
documents a switch in April 2015 from place of residence to place of issue of
travel document. Pre-2015 observations, the mixed 2015 transition and 2016+
observations receive distinct comparison identities. Chart paths break at both
boundaries; pre-transition values are not comparable with 2020. Document-issue
attribution does not establish U.S. residence or a departure from the U.S.
