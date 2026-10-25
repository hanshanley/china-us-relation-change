# Source contracts

The dashboard follows U.S. exchanges with mainland China, Hong Kong, Macau,
and Taiwan separately, from 2000 where verified. Missing coverage is not zero.

| Domain | Primary source | Contract and limitation |
|---|---|---|
| Degree enrollment | [UNESCO UIS](https://api.uis.unesco.org/api/public/documentation/) | Bilateral inbound tertiary degree/diploma mobility; exclude credit exchanges. Geo units use ISO alpha-3, including `MAC`, not numeric codes. Taiwan is not a separately available UIS reporting geography. |
| International student totals and credit study abroad | [IIE Open Doors country sheets](https://opendoorsdata.org/2025-country-and-area-fact-sheet-pdfs/) | Retained reviewed 2025 snapshot, not automatically refreshed: IIE's terms prohibit automated downloading/analysis and separate permission is not verified. All four geographies: 2017/18–2024/25 totals including OPT; credit participation through 2023/24. Enrolled-only counts for 2023/24 and 2024/25 sum undergraduate, graduate and non-degree counts, excluding OPT. New retrieval/reuse requires permission review as well as layout/definition review. |
| Historical student aggregates | [EducationUSA 2021 official regional compilation](https://educationusa.state.gov/sites/default/files/educationusa/2021_EAP_COMBINED_SMFF.pdf) and [NCES Digest](https://nces.ed.gov/programs/digest/) | Government republications only; no direct IIE retrieval. CHN/HKG/TWN inbound OPT-inclusive histories now cover 2000-2025; Macau 2015-2025. Credit participation covers 2014-2024 for all four geographies, plus mainland 2007/08. Exact 2020/21 enrolled-only level sums are separate from OPT and from the standard-population 2023/24 onward. Raster chart labels are checksum-pinned; all retained overlaps must reconcile. Conflicting Hong Kong 2017 stock-chart label is rejected in favor of the original NCES count. |
| Enrolled-student histories | Original IIE [Open Doors 2020](https://files.eric.ed.gov/fulltext/ED661341.pdf) and [2023](https://files.eric.ed.gov/fulltext/ED661412.pdf), deposited in the federal ERIC repository | Exact Table 1.15 counts restore 2019, 2020, 2022 and 2023 for all four origins. Undergraduate + graduate + non-degree excludes OPT; all four categories reconcile with retained country totals. Combined coverage is continuous 2019-2025. Original IIE authorship is retained; these are selected numerical facts, not government-authored books or redistributed reports. Direct IIE retrieval remains paused. Pandemic 2021-2023 populations remain separately identified. |
| Goods and services, China/Hong Kong/Taiwan | [BEA geographic history](https://www.bea.gov/data/intl-trade-investment/international-trade-goods-and-services) | Discover the `geo-time-series.xlsx` download. Tables 4/5: goods exports/imports; 7/8: services exports/imports. **Balance-of-payments basis**, not Census customs trade. Multiply million USD by 1,000,000. Annual history from 2000; matched YTD sums of complete seasonally adjusted quarters, separately defined from annual totals. The current workbook's repeated 2000 / missing 2001 annual labels require the independently labelled December 2024 archive for those two years; no row-position correction. Macau is not separately reported. |
| Macau goods | [UN Comtrade public API](https://comtradeapi.un.org/) | U.S. reporter 842, Macao partner 446, aggregate HS TOTAL, annual flows X/M. Exports FOB; imports CIF. These are customs statistics, not BEA BOP; the differing import valuation is conspicuous. No uncertain Taiwan mapping is used. |
| Macau services history | [BEA expanded-geography Table 2.4](https://apps.bea.gov/iTable/?isuri=1&product=4&reqid=62&step=6&tablelist=30700) | Direct annual exports/imports, 2018-2025; actual release July 7, 2026. Public `GetStep` POST uses product 4, table 30700 and all years. Multiply published millions by 1,000,000. Three overlapping control geographies reconcile with existing BEA history; each country balance allows only the combined precision of independently rounded components. Suppression and amounts under $500,000 are not zero or inferred from balances. Preferred in main/regional charts, with all USTR vintages retained separately. |
| Macau services current estimate | [USTR Macau Trade Summary](https://ustr.gov/countries-regions/china-mongolia-taiwan/macau) | Direct estimated 2025 U.S. services exports $434.0m and imports $208.0m. Reconciled with $642.0m total and $226m surplus, retaining quoted rounding. Preserved as a separate source vintage, not spliced into BEA. Nominal cross-border services, not affiliate sales. Older years are not inferred from rounded year-on-year changes. |
| Archival Macau services | [Original USTR page, December 18, 2025 capture](https://web.archive.org/web/20251218202809/https://ustr.gov/countries-regions/china-mongolia-taiwan/macau) | Direct 2024 exports $440m and imports $34m. The original aggregate-unit typo ($474 billion) is explicitly corrected only for validation; $406m surplus and same-year $864m combined trade less $390m goods independently reconcile the component sum. Checksum-pinned statistical passage; raw response checksum/capture URL retained. Not used for growth against the newer 2025 vintage. |
| Visitors to U.S. | [NTTO I-94](https://www.trade.gov/i-94-arrivals-program) | Official country-of-residence visitor trips, including non-leisure purposes; annual and monthly spreadsheets are public. |
| Visitors from U.S. | [NTTO SIAT](https://www.trade.gov/survey-international-air-travelers-siat), destination authorities | Preserve residence/citizenship, overnight/same-day, and air/all-mode distinctions. Never use flight passengers as tourists. |
| Historical U.S.-resident air travel | Original OTTI/NTTO *U.S. Resident Travel Abroad* reports for 2009, 2010, 2011 and 2012, publicly archived from the retired government site; [original 2021 China profile](https://trade.gov/sites/default/files/2022-10/U.S.%20Outbound%20China%20-%202021.xlsx) | Recover 24 actual mainland China/Hong Kong observations in 2000-2011 from page 7. All country/year overlaps agree, and the 2012 mainland 1,140,000 and Hong Kong 627,000 values exactly match the current public monitor. The 2000 values are separately reported mainland 644,000 and Hong Kong 832,000, not the BTS combined geography. Read published thousands; preserve the original overnight-trip scope and sample thresholds (at least 100 in 2000-2005, at least 400 in 2006-2010), without inventing exact sample sizes. Original publication months, archive URLs and actual response checksums are retained separately from retrieval/capture dates. Separately recover the 2021 mainland estimate of 5,000 trips from the checksum-pinned profile's chronological AA column, not its stale AB duplicate-year helper. All 21 rounded 2000-2020 overlaps agree; the 267 respondents and original report vintage remain explicit. The original and August 2023 archived workbook are byte-identical. The monitor's contradictory 2021 zero remains excluded; Hong Kong 2021 is still unreported. |
| Hong Kong arrivals | [HKTB](https://www.discoverhongkong.com/eng/hktb/newsroom/tourism-statistics.html) | Check U.S. residence and overnight/all-visitor columns separately. |
| Macau arrivals | [MGTO statistical reports](https://dataplus.macaotourism.gov.mo/Publication/StatisticalTables?lang=E) and [DSEC country-workbook catalogue](https://www.dsec.gov.mo/StatisticsJSON/AllReleases_en-US_TourismAndServices.json) | Annual 2001-2025 history; 2000 remains unverified. Monthly/YTD now extend through September 2026, using the October 23 DSEC release when MGTO's requested September endpoint still serves August. Read count columns, not shares or rounded growth. Source table 1 is issuing place of travel document, not residence; sea/land/air and same-day/overnight totals independently reconcile for both comparison years. Earlier population boundaries remain explicit. |
| Taiwan arrivals | [Government open-data catalog](https://data.gov.tw/dataset/45512), [official CSV](https://stat.taiwan.net.tw/data/opendata/6) | Public annual purpose-by-residence CSV starts 2012. U.S. residence rows provide total arrivals and a separate declared-sightseeing series. The interactive API rejected requests; the explicitly public CSV is accessible without bypassing that restriction. |
| Mainland arrivals/enrollment | [NBS](https://www.stats.gov.cn/english/), [MOE](https://en.moe.gov.cn/) | Verify the bilateral breakdown for each publication; national totals do not establish U.S.-specific counts. |

## Historical U.S. students in mainland China

`scripts/build_mainland_history.py` reviews two checksum-pinned scholarly
republications of the MOE reporting population. It writes a private candidate
by default; `--apply` merges reviewed observations into the canonical data,
preserving existing values and provenance. It does not fetch IIE resources.

[Tian and Liu's original article](https://doi.org/10.1007/s10734-020-00522-5),
Table 3, supplies the six missing 2000-2005 U.S.-origin counts. The article is
read through the public Europe PMC XML service. All ten 2006-2015 overlaps
reconcile with the independently retained MOE history. The article's conflicting
2016 count and mislabelled later periods are excluded, not silently corrected.
Only the selected numerical facts are published, not the article or its artwork;
its repository access statement is not asserted to grant perpetual reuse rights.

The exact **2017 count, 23,911**, is separately and explicitly dated in
[Liu Xianjun's retrospective account hosted by Xi'an University](https://fzgh.xawl.edu.cn/info/1130/1873.htm),
attributed to the China Association of Higher Education. This is a scholarly
republication, not a newly retrieved original ministry table. The selected count
is annual reporting-year degree/non-degree participation, not an academic-credit
study-abroad count, departures, or the number physically present on one date.
No precise within-year boundaries are invented.

These recoveries make the historical series continuous for 2000-2018. They do
not supply a comparable annual U.S.-specific post-2018 series or qualify this
old history for the current public charts. Dated embassy statements, degree-only
statistics and short-program participation remain distinct measures.

The [original authors' 2025 mobility review](https://peidongyang.com/wp-content/uploads/2025/10/chpt7_student-mobility-to-china_an-overview_yang-lu-yin-2025.pdf)
was also checked. Its newer 2022/2023 national aggregates do not supply an annual
U.S.-nationality breakdown. Neither those totals nor the chapter's publication
date extend the bilateral all-program series.

## Confucius-program counts

These indicators live in their own `confucius_programs.json` dataset and public
page. They do not change the learner/enrollment datasets.

| Primary source | Contract |
|---|---|
| China MFA, September 29, 2014 press conference, embassy-hosted original transcript | Reported 100 U.S. institutes and 366 classrooms; counting rules are not independently harmonized with later school-site counts. |
| NAS, *Outsourced to China*, April 2017, amended June 2017 | Summary: 103 operating institutes and 501 primary/secondary school sites. The 2025 upload path and a later webpage date are not new observations. |
| NAS, *After Confucius Institutes*, June 2022 | Retrospective 2006/2007/2015 counts and the original 28 documented replacements, 12 proposed replacements, 58 retained partnerships and five transfers. Groups can overlap. Attribute source classifications; do not adopt advocacy framing or infer current operation. |
| GAO-19-278 and GAO-24-105981 | 96 campus institutes as of December 2018; fewer than five as of July 2023. Preserve the campus-only population and the exclusive upper bound, not exactly five. Original facts were browser-reviewed; the selected-facts transcription is versioned and separately checksummed, never falsely labelled a downloaded GAO response. |
| CRS IF11180 versions 11 and 13 | April 2022: 18 reported institutes including announced closures and non-college hosts. December 2022: approximately seven on campuses, attributed to NASEM. Verify the date inside each PDF; version 12 still contains the May 2022 report and is not the 2023 vintage. |
| U.S. Senate, *China's Impact on the U.S. Education System*, February 2019 | Executive Summary reports 519 classrooms/school sites. Its later inclusion as an exhibit at a 2023 hearing does not update the observation. |
| USC US-China Institute, November 18, 2021 | Original article/map reports 30 still open, including some announced future closures. Not an independently harmonized annual series. |
| NAS, *China and Our Children*, July 2024 | 164 documented school/district cases, including current and former programs. An incomplete mixed-unit inventory; the report explicitly says the current operating total is unknown. |
| NAS, June 22, 2023 tracker and its linked workbooks | Retain ten listed institutes including one paused program, and the source's at-least-28 replacement statement. Keep all 108 post-closure workbook rows and overlapping R/M/T flags. Do not fabricate the difference from the webpage's 111 closed/closing figure, promote a proposal to a completion, or substitute 29 R flags for current active programs. |
| CIEF public U.S.-filtered directory, observed October 24, 2026 | Complete returned set of 17 names: ten Institute-labelled and seven Classroom-labelled entries. A listed name is not proof of operation; API `enable` is website presentation, not active/closed status. No national K-12 school total is derived from university-named classroom entries. |

Historical observations retain year/month/day precision and distinguish as-of,
reported-by and retrieval dates. There is no interpolation or combined
Institutes/Classrooms/successors total. A complete inventory of current programs
was not established; do not infer zero from closures, new policies or a missing
entry. Official operator releases and public-directory records are used for
currentness, not derivative news claims of a nationwide count.

Redistributed records contain factual names, dates, flags and evidence links,
not source report text, artwork or long workbook narratives. Full selected
observations and records—not just metadata—are included in every dataset export.
The source cache retains original downloads locally with their SHA-256 identities.

## State immigration map

The [Census ACS summary-file release page](https://www.census.gov/programs-surveys/acs/data/summary-file.html)
links the actually released five-year data. Table **B05006** uses the foreign-born
universe excluding people born at sea. The map numerator is **E050, China excluding
Hong Kong and Taiwan**, not E049 (their parent group). E001 is the denominator;
M050/M001 are published 90% count margins of error, not percentage margins of
error. Parent China, Hong Kong and Taiwan counts and source cells are retained
for reconciliation. Macau is not independently identified.

The October 24, 2026 review selected **2020–2024 five-year period estimates** for
all 50 states and DC. The same year's one-year detailed table contains only 30
states after [ACS quality filtering](https://www2.census.gov/programs-surveys/acs/tech_docs/data_suppression/ACS_Data_Release_Rules.pdf);
do not mix annual and five-year data to fill it. The five-year estimates describe
the whole collection period, not 2024 alone. Every state and the national control
must be present and reconcile before publication.

The public 267 MB table-based summary file supports ordinary HTTP byte ranges.
Its first 1 MiB contains every selected state and national row; the retained
checksum and `byte_range` identify that prefix, never the whole file. Complete
selected observations, original cells and provenance are in the public JSON/CSV.
Boundaries are the official generalized 2024 TIGERweb state polygons, joined by
FIPS and checked against state names/postal codes. Alaska and Hawaii insets use
separate scales. Census data and boundaries are U.S. government statistical
products; no personal records or proprietary map tiles are redistributed.

## Chinese-language learning sources

The separate language-learning publication does not add domestic registrations,
global exams, program inventories or degree awards to bilateral observations.
Complete source asset identities and checksums are in
`data/site/language_learning.json` and its downloadable copy.

| Primary source | Contract |
|---|---|
| [MLA fall 2021 report](https://www.mla.org/content/download/191324/file/Enrollments-in-Languages-Other-Than-English-in-US-Institutions-of-Higher-Education-Fall-2021.pdf), Table 5, PDF page 63 | Consistent published-report history for Chinese/Mandarin, Japanese, Korean, Spanish and all languages. Course registrations, undergraduate and graduate, not unique students. All-language denominator includes ASL/classical languages. No fabricated annual observations. |
| [MLA historical workbook](https://www.mla.org/content/download/191323/file/Historical-language-enrollments-1958-2021.xlsx), `FL history` | Match responding `INST_ID`s in 2013/2021, exclude `N_RESP=NR` even when a placeholder count is zero, and retain explicit `ZERO_ERL=Z`. Exclude institutions with any unreported language-count row in either endpoint; missing counts are not zeros. Chinese is exact CHINESE plus MANDARIN; do not deduplicate legitimate repeated language rows. National endpoint sums independently reconcile to the report. |
| [MLA pandemic snapshot](https://www.mla.org/content/download/191129/file/Fall-2022-NL-snapshot.pdf) | Separate 2016/2020 comparison at 1,308 matched institutions: Chinese 33,561/26,528; Japanese 46,936/43,268; Korean 9,033/11,323. `data/reviewed/language-snapshot-2020.json` holds selected facts checked against Figure 1's table image and locked to the publisher PDF checksum. The review JSON hash is identified separately, not presented as a publisher response. Not a national 2020 census or an extension of the national 2021 series. |
| [BACS 2021-22 report, HESA Table 7](https://bacsuk.org.uk/wp-content/uploads/2015/05/BACS-State-of-the-Field-2021-22-Report.pdf), checked against the [2016 report](https://bacsuk.org.uk/wp-content/uploads/2023/04/BACS-report-on-China-Studies-2016.pdf) | Eight Table 7 totals for 2014/15-2021/22, plus a separately identified quoted 2012/13 endpoint. The older report labels the matching 1,535 as full-time and reports part-time separately; equivalence with later all-mode totals is unverified, so the article's 31% is not imported as a like-for-like decline. Academic ending years, apportioned and rounded counts, not admissions or unique learners. Preserve the JACS/HECoS boundary and do not interpolate 2013/14 or infer Japanese/Korean figures. October 25, 2026 alternative-source check: BACS's linked 2022-23 files are funding information; the selected April 2024 archived HESA page still ends in 2021/22. The reviewed Jisc CAH dashboard documentation supplies no separately verified Chinese/Japanese/Korean count here. These checks do not establish that newer data do not exist or authorize allocating Asian-studies totals to individual languages. |
| [College Board AP archive](https://reports.collegeboard.org/ap-program-results/data-archive) and [Chinese 2025 subject report](https://apcentral.collegeboard.org/media/pdf/ap25-chinese-language-score-distributions.pdf) | Global annual administration history 2007-2025. Subject-specific reports supersede overlapping earlier program-volume vintages. Parse **Number of Students**, not the number scoring 3+. Standard group is a subset, not U.S. geography or a nonheritage/ancestry classification; never add it to total. October 24, 2026 check: the official 2026 Chinese/Japanese web tables contain score percentages but blank Test Takers cells; checked catalogs supply no 2026 count link, and standard 2026 subject-PDF URLs return 404. Do not infer participant totals from percentages or make the retained 2025 count a 2026 observation. |
| [Texas Education Agency national AP reports](https://tea.texas.gov/data-reports/school-performance/accountability-research/accountability-research-reports-and-abstracts), including [2006-07](https://tea.texas.gov/sites/default/files/AP_IB_2006-07.pdf) and [2021-22](https://tea.texas.gov/sites/default/files/ap-tx-and-us-2021-22.pdf) | Separate U.S.-only Chinese/Japanese annual exam counts for school years ending 2007-2022, public and nonpublic schools and all grades. Read the **U.S. number of examinations** column, not adjacent Texas counts, score percentages or means. The combined 2012-13/2013-14 table changes year within a page; preserve section state across page breaks. Reporting year is not publication year. These historical-only series remain in complete downloads, not current public plots or spliced global/cohort histories. Reviewed 2023-2025 national summaries omit subject counts; national aggregate growth cannot fill them. Only selected numerical facts are republished, not source reports or artwork. |
| [AP Report to the Nation 2011](https://secure-media.collegeboard.org/digitalServices/public/pdf/ap/rtn/AP-Report-2011-Subject-Supplement.pdf), [2013 supplement](https://secure-media.collegeboard.org/digitalServices/pdf/ap/rtn/9th-annual/9th-annual-ap-report-subject-supplement-all-subjects.pdf), [2014 Chinese supplement](https://secure-media.collegeboard.org/digitalServices/pdf/ap/rtn/10th-annual/10th-annual-ap-report-subject-supplement-chinese-language-and-culture.pdf) | U.S. public-school graduating cohorts 2007-2013. Sum five total-group score categories; year is the graduating class, with exams taken throughout high school. Later report vintages take priority for overlapping cohorts, including the revised 2008 total. Never splice into annual global administrations. |
| [NCES IPEDS public files](https://nces.ed.gov/ipeds/datacenter/data/), `CYYYY_A.zip` plus annual institutional directory | Exact CIP 16.0301, 50 states/DC, degree-granting and Title IV eligibility; first-major `MAJORNUM=1` from 2001. Use revised `_RV` CSV only when present. Modern total `CTOTALT`; older `CRACE15+CRACE16` are male plus female totals. Preserve source-flag frequencies and selected revision. |
| [NCES independent degree checkpoint](https://nces.ed.gov/programs/digest/d23/tables/xls/tabn318.30.xlsx) | Digest table 318.30 independently confirms 2022 Chinese bachelor's 364, master's 26 and doctorates 14. Awards are not unique people or all China expertise; the 2000 major-number and 2010 doctoral-classification breaks are explicit. |
| [CAL 2011 language inventory](https://webapp.cal.org/Immersion/Doc/Language%20of%20Instruction%20in%20Immersion%20Programs.pdf), [ARC 2021 canvass](https://www.americancouncils.org/sites/default/files/documents/pages/2021-10/Canvass%20DLI%20-%20October%202021-2_ac.pdf), [Nexus publications](https://nexusmandarin.org/publications-1) | 71 Mandarin directory programs, 312 Chinese public-school DLI programs and 335 U.S. inventoried immersion programs, respectively. Definitions differ; these are disconnected inventory snapshots, not comparable growth or learner counts. Nexus's state appendix independently sums to 335. |
| [American Councils June 2017 K-16 report](https://www.americancouncils.org/sites/default/files/FLE-report-June17.pdf), Table 2 | Chinese K-12 estimate 227,086 combines reported state data and model estimates, with a 2014-15-era reference period. The ending-year key 2015 is not an exact common measurement date or current census. |
| [NCES School Pulse Panel national workbook](https://nces.ed.gov/surveys/spp/docs/release/Language.xlsx) | January 2024 experimental national public-school sample; `All Schools`, `Lang1_3`, `Lang1_9`, `Lang1_10`, `Jan24 Pct / SE`. Chinese 3% (SE 0.4 percentage points), Japanese 1% (SE 0.3), Korean unreportable. Denominator is all public schools. The outlying-area workbook is not national; program counts, learners and published complements of suppressed estimates are not substituted. |

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

`data/site/business_presence.json` retains all 304 China-hosted observations, including
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
| [UK 2007-2009 table](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2?lang=EN&geo=UK&partner=CN_X_HK&indic_bp=ENT&nace_r1=C-O_X_L), [2010 onward](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=UK&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O), [ONS 2018/2019 workbook](https://www.ons.gov.uk/businessindustryandtrade/internationaltrade/datasets/ukoutwardforeignaffiliatestatisticsofats) | UK-controlled enterprises in China except Hong Kong. Original JSON/native TSV agree on 2009=691; 2007/2008 are unreported. Keep NACE Rev. 1.1 C-O except L separate from Rev. 2 B-S except O from 2010. Eurostat also flags breaks in 2013, 2014 and 2015. Use ONS Table 1 (2018 revised), Table 2 (2019), China, TOTAL ACTIVITY / ENT, not EMP or TUR. Counts 709 and 531 are survey-based estimates; total activity includes agriculture. The 2018 source/sector boundary is not connected. |
| [ONS coverage disclosure](https://www.ons.gov.uk/aboutus/transparencyandgovernance/freedomofinformationfoi/ukoutwardforeignaffiliatestatisticsofats2015to2025) | Latest outward-affiliate estimates remain 2018/2019; no OFATS data from 2020 onward. Newer inward-affiliate statistics concern businesses **in the UK**, the wrong direction, and are not substituted. |
| [Norway historical API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out2_r2?lang=EN&geo=NO&partner=CN_X_HK&indic_bp=ENT&nace_r2=B-S_X_O), [current API](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fats_out_part?lang=EN&geo=NO&partner=CN_X_HK&indic_sbs=ENT_NR&nace_r2=B-S_X_O) | All fourteen annual Norwegian-controlled enterprise counts in China, 2010-2023. Preserve the 2021 EBS method boundary. Norway is shown separately, never silently added to an EU/all-Europe total. |
| [Statistics Norway Table 09827](https://www.ssb.no/en/statbank/table/09827/) | All seventeen 2008-2024 country observations under direct/indirect Norwegian control, all industries; 2024=80 enterprises. Public API POST selects `Land=CN`, `ContentsCode=Foretak`, all `Tid` values. Hong Kong and Macao remain separate countries. The entire SSB history replaces the narrower Eurostat chart, not just its last point; original Eurostat observations remain in complete downloads. |
| [Bundesbank outward FATS](https://www.bundesbank.de/en/statistics/external-sector/direct-investments/foreign-affiliates-statistics-fats--795240) | Discover the linked workbook; `DATA`, `BBFOFATS.A.DE.ENT.BTSXO.CN`, 2021-2024. The archived original November2020 report, TableII.1.1/page7, independently matches its German-language edition for2015-2018:1646/1688/1735/1735. Archive-capture dates are not data years. German ultimate control above50%; assets above EUR3m; branches included, agriculture/public administration/private households excluded.2018 remains provisional in its original release; current2024=1911 is separately provisional. No2019/2020 count or later historical revision is inferred. Country CN, not HK/MO; entity counts, not employment/turnover, and not spliced with Eurostat. |
| Eurostat German country history, `fats_out2_r2` / `fats_out_part`, `geo=DE` | Every 2010-2023 count, with the 2021 EBS boundary disconnected. Overlapping 2023 is 1,921 versus Bundesbank's 1,929: separate series, not a joined or averaged revision. Germany overlaps the EU aggregate; no addition or confidential-total reconstruction. |
| [Swedish country database](https://statistik.tillvaxtanalys.se/PxWeb/pxweb/sv/) | `Etableringsland=cn`, `variabel=2` (subsidiaries), not `0` (parent groups). Fifteen reported 2010-2024 counts; ten 2000-2009 cells remain null. Swedish-headed groups, subsidiaries under >50% ownership or dominant influence; all industries. Preserve 2018 EGR/imputation, 2019 frame-repair and 2021 ownership-concept boundaries. The 2024 quality declaration is checksum-pinned; the API's year9999 timestamp is not a release. |
| [Statistics Finland table13k8](https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__stu/13k8.px/) | Country156=China, `ofats_count`, 2020-2024:250/249/256/239/242. Active affiliates and branches controlled by Finland-resident enterprises, all size classes/industries; financial years ending within the reference calendar year. Hong Kong/Macao remain separately coded. Preserve the 2021 EBS boundary; older regional aggregates are not allocated to China. |
| Eurostat Finnish-UCI history, `geo=FI`, `partner=CN_X_HK` | Seventeen2007-2023 enterprise counts, independently reconciled to native TSV exports. Legacy `fats_out2`/C-O except L, then `fats_out2_r2`/B-S except O and `fats_out_part`/`ENT_NR`. Country-specific official metadata preserves2007-2012,2013-2020 and2021-2023 comparison blocks; retain the2010 classification transition as well. National data additionally include enterprises linked abroad through Finland and have broader sector coverage; all four2020-2023 overlaps differ. Separate population/chart, never a splice into table13k8 or a manufactured current-year count. |
| Eurostat Swedish-UCI history, `geo=SE`, `partner=CN_X_HK` | Seventeen2007-2023 source rows, including confidential2009; sixteen counts independently match native TSV. The original selected legacy NACE label remains explicit alongside the country's2008classification boundary and2010table transition.2018 changes legal units to enterprises and the frame from Bisnode to EGR;2021introduces EBS. GGH is used as UCI proxy, and official imputation can apply. Eleven of fourteen national overlaps differ; no splice or suppressed-as-zero value. |
| Eurostat Spanish-UCI history, `geo=ES`, `partner=CN_X_HK`; [Spanish reporter metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_es.htm); INE national [2023](https://www.ine.es/jaxi/Tabla.htm?tpx=76249&L=0) and [2024](https://www.ine.es/jaxi/Tabla.htm?tpx=82151&L=0) tables | Fifteen actual2009-2023 enterprise counts plus explicit missing2007/2008 cells. All three original dataset identities, host/reporter/enterprise/activity dimensions and source flags are checked.2022=102 and2023=100 retain estimated status. The reporter documents financial activities supplied through Bank of Spain and a2021 legal-unit/statistical-enterprise break; retain2010 classification as well. National INE nonfinancial2023=98 and2024=134 come from a different population, not an extension or a comparable2019 denominator for this series. No values inferred from percentages, all-Spain totals or missing early years. |
| [Statistics Denmark OFATS4](https://www.statbank.dk/OFATS4); [definitions](https://www.dst.dk/da/Statistik/dokumentation/statistikdokumentation/danske-datterselskaber-i-udlandet/indhold); [comparability](https://www.dst.dk/da/Statistik/dokumentation/statistikdokumentation/danske-datterselskaber-i-udlandet/sammenlignelighed) | Complete18-country/year cells2007-2024 independently reconcile CSV and JSONSTAT:2007=217,2019=485,2023=480,2024=460. Select `LAND=CN`, `ENHED=DSANTAL` (affiliates, not employees), all published years; HK/MO are separately coded. The national resident-parent population includes foreign ultimate owners and excludes branches; it is not Eurostat's Danish-UCI population (2023=335). Private non-agricultural activities include finance; no lower activity threshold. Preserve2010 classification. Source metadata also uses zero for suppression, so zero is not automatically an observed count. Only actual national subsidiary values extend this chart; no country allocation, UCI splice or pre2007 invention. |
| Eurostat French country history, `geo=FR`, `partner=CN_X_HK` | Seventeen 2007-2023 cells, including unreported2008; latest2153. `fats_out2`/NACE C-O except L before2010, `fats_out2_r2`/B-S except O for2010-2020, `fats_out_part`/`ENT_NR` from2021. Retain the 2007 pilot/2009 frame, 2010 NACE, 2016 `b` flag and 2021 EBS boundaries. The host category is explicitly China except Hong Kong. Not a splice to INSEE's rounded, differently scoped2.8-thousand count. |
| Eurostat Polish country history, `geo=PL`, `partner=CN_X_HK`; [Polish reporter metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_pl.htm) | Seventeen source cells, including missing2007; all16reported2008-2023 counts and flags independently match native TSV. Latest2023=32, not a2026 measurement. The enterprise unit begins2018; the reporter declares2018-2023 comparable, so2021 is dataset provenance rather than an invented second country unit break. Retain the selected legacy NACE2010 transition. Ultimate control can include joint50/50 and documented minority control, without a size cutoff. The broad national foreign-equity survey is not substituted. No pre2008, missing-as-zero or unreported2024+ observation. |
| Eurostat Dutch country history, `geo=NL`, `partner=CN_X_HK`; [CBS Nederland Handelsland2026, figure5.4.1](https://longreads.cbs.nl/nederland-handelsland-2026/buitenlandse-investeringen-en-multinationals/); [CBS OFATS methods](https://www.cbs.nl/nl-nl/onze-diensten/methoden/onderzoeksomschrijvingen/korte-onderzoeksbeschrijvingen/outward-fats-statistiek-over-nederlandse-zeggenschappen-over-buitenlandse-bedrijven) | Seventeen Eurostat enterprise counts2007-2023 independently match native TSV exports. The original CBS HTML outward table, not the inward China row or digitized PDF, reports2024*=620 and2023=574;2023 reconciles. Star means provisional, and the reference year is2024, not the2026 publication. Dutch-resident UCI; financial/nonfinancial B-S except O with nonresponse weighting. Keep2010 NACE and2021 methodology boundaries; do not compare2024 with2019 across that break or add Netherlands to its overlapping EU aggregate. |

Belgian Eurostat queries select `geo=BE`, `partner=CN_X_HK` and exact
enterprise indicators in `fats_out2`, `fats_out2_r2` and `fats_out_part`.
All seventeen 2007-2023 count cells match independent native TSVs.
[Belgian reporter metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_be.htm)
starts UCI attribution in 2009 and enterprise-level counting in 2022, not 2021.
Two pre-UCI legal units and thirteen UCI legal units remain separate archives;
only 2022=72/2023=80 enter the short current-enterprise chart. Keep 2010 NACE,
2014 non-resident activity, 2016 declared-window and 2021 EBS-source boundaries.
The 3.8/15.2.1 comparable-window paragraphs differ; the explicit 2022 unit rule
does not authorize cross-regime 2019 growth. Current metadata's FDI reporting-unit
frame uses EUR 30m equity/75m assets/15m long-term investments (any criterion);
historical stability is unverified. Control-concept wording is greater than
half, while the screening frame says at least half; no extra 50/50 population
is inferred. Original experimental 2004-2006 responses contain employment and
turnover but no enterprise-count cells for this pair, not zeros to backfill.
No national dissemination or unreported 2024+ country count is substituted.

Italian Eurostat queries select `geo=IT`, `partner=CN_X_HK` and enterprise
indicators in `fats_out2`, `fats_out2_r2` and `fats_out_part`.
All seventeen2007-2023 values independently reconcile to original native TSVs.
[Italy-specific metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_it.htm)
explicitly distinguishes legal units through2020 from enterprises since2021
and rejects a cross-unit comparison. The fourteen older values retain
their original estimated flags. The original
[national2023 report](https://www.istat.it/wp-content/uploads/2025/11/Report_Imprese-multinazionali_Anno-2023.pdf),
pages10/12, explicitly retains legal units in national dissemination, Italian
ultimate control and B-N/P-S activity. Catalogue-linked ISTAT-ICE2022-2026
workbooks select the absolute `Cina` row and `Imprese` column on `Totale`,
not the repeated percentage row. Industry+services sums reconcile for all
five years;2019=1141 and2020=1133 match the older Eurostat legal units.
The national continuation is2021=1113,2022=1169,2023=1122, making a genuine
2007-2023 legal-unit chart. The2010 classification and2021 source boundaries
remain explicit. These census-survey estimates receive no invented Eurostat
flag. Separate Eurostat enterprises675/687/669 remain download-only:
1122legal units and669grouped enterprises are different counting units,
not competing measurements or an unexplained numerical discrepancy.
No pre-2007, cross-source2019 change or unreported2024/2025 count is inferred.
The official [2026 release calendar](https://www.istat.it/wp-content/uploads/2026/01/CALENDARIO-COMUNICATI-2026_10.11.pdf)
schedules reference2024 multinational statistics for November10,2026;
that release is still in the future as of October25,2026.

| Eurostat Austrian-UCI counts, `geo=AT`, `partner=CN_X_HK`; [Austria-specific methods](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_at.htm) | All seventeen 2007-2023 counts independently match native TSV exports. Keep fourteen 2007-2020 legal-unit observations separate from three 2021-2023 enterprise observations, ending at 175. Methods 3.5 explicitly acknowledge that foreign legal units remain an imperfect enterprise proxy; 15.2.2 retains limited comparability across 2021. Preserve the 2010 NACE transition. Broader national resident-parent counts and the separate all-industry 2024 control subset are different populations, not extensions of this UCI series. No earlier/current count or 2019 comparison is inferred. |

| Portuguese counts, `geo=PT`, `partner=CN_X_HK`; [national methods](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_pt.htm) | Three exact Eurostat datasets retain every 2007-2023 source cell. The 2007 count of 3 predates the documented 2008 UCI implementation and is a separate qualified archive, not a Portuguese-UCI observation. The 2008-2023 UCI population has fifteen counts, ending at 41, and a confidential 2012 null. Keep the selected 2010 classification transition, 2014 sample-to-IES source change and 2020 coverage expansion. The national producer declares 2020-2023 comparable; the 2021 dataset change is not a fabricated extra unit break. No current 2019 denominator across the 2020 boundary or allocation from an EU total. |
| Czech counts, `geo=CZ`, `partner=CN_X_HK`; [national methods](https://ec.europa.eu/eurostat/cache/metadata/EN/fats_out_simsofat_cz.htm) | Three exact Eurostat datasets retain seventeen 2007-2023 source cells: sixteen counts, ending at 7, and a confidential 2021 null. Czech National Bank metadata identifies UCI introduction in 2007, NACE Rev. 2 in 2008 and EBS coverage/definition changes in 2021. Preserve the selected 2010 legacy-dataset transition too. These are controlled enterprises/branches, not a count of all minority FDI interests. No cross-2021 comparison to 2019, pre-2007 padding, unreported later year or sum with overlapping EU aggregates. |

Raw source archives, workbooks, publication text and artwork remain local.
Only numerical aggregates, original definitions and our figures are published.
All indicators are business-presence stocks, not border crossings, investment
flows or a composite measure of U.S.-China contact.

## Public opinion

`data/site/opinions.json` is separate from counts of people and exchanges.
Only U.S. views of China and Chinese views of the U.S. are plotted; no global
average or social-media sample is substituted.

| Primary source | Contract |
|---|---|
| Gallup, March 12, 2026 country-ratings release and original final topline, page 4, Q17 D | All 29 China survey rounds in 2000-2026, including three in 2000; 58 favorable/unfavorable net percentages. The main history explicitly uses the first reported poll per year, never an annual average. All rounds remain in complete downloads. Telephone interviews, separate from Pew; sampling frames and weights evolved. Latest fieldwork February 2-16, 2026, full n=1,001; each country item approximately 800, not an exact item sample of 800. Retain the 2001 half-sample note and published rounded nets. |
| Pew Research Center, April 14, 2026 U.S. China analysis | Embedded favorable/unfavorable table, 2005 onward. Retain phone, summer-phone and American Trends Panel observations separately. The March 1 dates used for chart positioning are not actual fieldwork dates. |
| Pew, July 15, 2026 *Views of China and Xi Are Improving Globally*, PDF appendix page 20 | U.S. favorable/unfavorable percentages for ages 18-34, 35-49 and 50+. Read the left-hand U.S. column, not adjacent Australia. Actual U.S. fieldwork was March 23-29, n=3,507, not a July poll. |
| Pew, September 23, 2026 U.S. warmth article and linked topline | Published means 39, 42, 28 and 37 in 2016/2018/2021/2026. Current age means 42 for 18-49 and 31 for 50+. Means are reviewed article facts, not computed from rounded bins in the topline. Direct article retrieval returned 403; no access restriction was bypassed. The separately published PDF verifies the question and field dates. The China-specific base is 1,168, not the full 5,193 sample. |
| The Carter Center / Emory University, October 2026 China Pulse report and its published Datawrapper LU2Fb dataset | Means on a 0-100 cold-to-warm scale, not percent favorable. Fieldwork October 27, 2025-January 1, 2026 (2,506) and April 16-June 26, 2026 (2,500). Both waves are reweighted in this release, yielding overall means 33 and 32. Keep original Chinese age bands and do not claim a matched U.S. probability sample. The PDF supplies a publication month, not an exact day. |
| Pew, October 5, 2016 China report, page 13, Q10a | Direct published net favorable/unfavorable percentages, 2007-2016. Do not sum separately rounded component percentages. Sample coverage varied historically; disconnected bars do not imply a continuous current national trend. |
| Pew, September 21, 2006 Asia report, PDF pages 11-12, Q2a; November 16, 2005 China report, PDF pages 6-7 | Published favorable/unfavorable nets: 42/53 in 2005 and 47/43 in 2006. Ages 18-60 in six city areas and surrounding rural areas, disproportionately urban, not nationally representative. Fieldwork May 21-31, 2005 (n=2,191) and April 7-18, 2006 (n=2,180). Keep the differing city sets, exact dates, unknown question-specific bases and separate per-round coverage keys. Archive in complete downloads, not the later all-adult series, current charts or China Pulse warmth scale. |
| Alastair Iain Johnston, RSIS Working Paper 50 (2003), original PDF page 13 footnote 33; methods page 8 footnote 20 | Five historical Beijing means in 1998-2002: 62/53/57/47/52 on a 0-100 warmth scale, not favorable percentages or national Chinese estimates. The source says "around" for 1998, 1999 and 2002. Full-wave samples 757/615/662 for 2000/2001/2002 are not item denominators. Original provider metadata below supplements the sampling frame and collection months, not the numerical precision. Exact days, thermometer-item bases and weighting of these published means remain unverified. Publication year only, not an invented month/day. Separate coverage keys, archive-only complete downloads, no new public chart or link to Pew/China Pulse. The original publisher's indexed catalogue identifies 2003, but its direct body returns 403 and is not claimed retrieved. |
| Peking University China Survey Data Archive, original BAS 1998-2002 public dataset metadata | Ages18-65, fixed residence and formal non-agricultural Beijing household registration in eight urban districts, not all Beijing residents or national China. Whole-wave n=756/712/757/615/662. Collection months: 1998Dec-1999Jan, 1999Dec-2000Jan, 2000Dec-2001Jan, 2001Dec-2002Feb, 2002Dec-2003Jan; no exact day is fabricated. Retain the provider's February2002 endpoint alongside RSIS's generic December/January summary. Paper face-to-face, two-stage PPS; provider WEIGHT/PSU documentation does not establish the thermometer-item base or independently reproduce mean weighting. These separately published 2016 catalogue records qualify methods, not new warmth observations or later broader18+resident frames. Five public HTML assets are preserved in complete JSON/CSV source provenance. Restricted questionnaires/codebooks/microdata are not retrieved; the public metadata-export API returned403 and is held without client/alias retries. Public metadata is not a complete numeric survey download. |
| Committee of 100 / Horizon Research, December 10, 2007 report, PDF page 14 / printed12 Q1; PDF page62 / printed60 methods | Only the Chinese general-public totals: 60% favorable, 26% unfavorable and 14% not sure about the United States as a country. Fieldwork August18-September7,2007; full-wave n=4,104, ages18-60, face-to-face multistage sampling in seven cities, seven towns and ten villages. Retain the publisher's national description within that age/sample frame, not unrestricted all-adult coverage. Item denominator remains unknown; elite86/94% and historical U.S. columns are not substituted or imported. Separate archive-only series, never a Pew/BAS/ChinaPulse splice, new current chart or uninterrupted national history. Full original77-cell source-query evidence remains separately retained for verification. |

The 2025 Pew age figure relevant to the cited social-media commentary uses ages
**18-34**, not "under 34." It displays 17 statistically significant age gaps
from a **25-country** survey: 16 in one direction and Hungary in the other.
It is not the full set of countries polled. The dashboard uses the newer verified
U.S. data and does not treat the existence or motivation of a social-media trend
as something an opinion survey establishes.

Complete public CSV/JSON retain all 160 estimates, not just favorable observations
or the default chart, plus source fingerprints, actual or explicitly unknown
field dates, original age bands and question-specific sample bases. Reviewed
transcription checksums are distinguished from publisher download checksums.
Only aggregate numerical facts and original visualizations are redistributed.

## COVID-period and travel-restriction annotations

On travel-linked charts, the shaded 2020–2022 interval denotes the main period of pandemic restrictions,
not a prohibition on all travel. It is calendar context, not an estimate of
how much any series was affected. Original notices are linked in the public
`covid-context.json` download:

- U.S. Proclamation 10294 and its Federal Register publication: the country-based
  entry suspensions were replaced effective November 8, 2021.
- China MFA/NIA announcement: suspension affecting existing foreign-national
  visas/residence permits began March 28, 2020, with exceptions and subsequent
  changes. The December 2022 notice introduced revised measures January 8, 2023.
- Hong Kong's April 22, 2022 notice identifies the overseas nonresident
  restriction beginning March 25, 2020 and its relaxation May 1, 2022.
- Macau DSEC's published statistical footnote identifies March 18, 2020–August
  31, 2022 restrictions on foreign visitors, excluding specified groups and
  exemptions; conditional entry followed before January 8, 2023.

Neither chart shading nor publication year makes an older observation current.
Travel-restriction context is only appropriate for directly travel-linked
measures. Generic indicator charts must explicitly opt in; opinion, business,
language-learning, Confucius programs, goods trade and resident stocks must not
receive a travel-restriction band merely because their dates overlap 2020-2022.
Goods-trade charts instead carry an explicitly separate **COVID-19 period,
2020-22** marker, as requested. Its note does not claim a goods-trade suspension
or a causal effect; it does not reuse the destination-specific entry rules
above. Native modes, regional comparisons, no-JS and both export themes use
that same goods context. Services trade remains unshaded.
The public recency rule uses the reference/measurement period and preserves all
historical records in complete archival downloads.

## Interpretation

Students are stocks or academic-year participation, not departures. UIS degree
mobility, Open Doors enrollment-plus-OPT, and academic-credit study abroad are
different series and must never be spliced. Academic years use their ending year
for the 2019 baseline (2018/19), with the original period label retained.

[IIE's student-census methodology](https://opendoorsdata.org/about/about-international-student-census/)
expands the international-student definition in Open Doors 2021–2023
(2020/21–2022/23) to cover coursework from outside the U.S. regardless of visa
status, then returns to the pre-pandemic definition in Open Doors 2024
(2023/24). OPT-inclusive and recovered enrolled-only observations receive separate standard and
pandemic-expanded comparison identities. Charts break at both boundaries,
display those dates in exported figure notes, and reject the incompatible
full-history 2019 index. Standard-population 2024/25-versus-2018/19 comparisons
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
- The legacy BEA factsheet endpoint is frozen at December 2020. Earlier
  iTable requests returned empty tables, but the normal public interface now
  supplies the verified Table 2.4 all-years `GetStep` request described above.
  The frozen factsheet is not substituted for it.
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
  but **BEA expanded-geography Table 2.4 now restores 2018-2025 in both
  directions**, including the 2019 baseline. Direct USTR 2025 and archived
  2024 estimates remain separate, with their original rounding and known
  aggregate-unit error documented. Neither is spliced into BEA or used for
  cross-vintage growth. Before 2018 remains unverified; no regional allocation
  or mirror-series substitution is made.

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
vintage, retrieval time and SHA-256 of its local raw response. For the manually
reviewed HKTB July/August 2026 supplement, the exact asset is instead the
versioned selected-facts JSON transcription, explicitly identified as such.
The original PDF URLs remain in every observation's notes; no publisher-PDF
checksum is invented.

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
boundaries; pre-transition values are not comparable with 2019. Document-issue
attribution does not establish U.S. residence or a departure from the U.S.
