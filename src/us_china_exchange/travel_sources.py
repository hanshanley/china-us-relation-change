"""Manual review of the public NTTO resident-air-travel monitor."""

import json
import re
from datetime import datetime, timezone

from .model import digest, json_text, observation, validate
from .pipeline import write_atomic
from .sources import attach


MONITOR = "https://powerbi.trade.gov/#/workspace/IA-NTTO-PUBLIC/report/SIAT_Res_Final_Monitor"
COUNTRIES = {"CHN": "China, People's Republic of", "HKG": "Hong Kong"}
ANNUAL_YEARS = (*range(2012, 2021), 2022, 2023, 2024, 2025)
PARTIAL_YEAR, PARTIAL_QUARTER = 2026, 2


def parse_monitor_card(text, country, year, frequency):
    match = re.search(r"Total Traveler Estimate\s+to Destination\s+([\d,]+)\s+(.+?)\s+"
                      r"SIAT Respondent Count\s+to Destination\s+([\d,]+)", text, re.S)
    if not match:
        raise ValueError("Public SIAT estimate/respondent cards missing")
    title = " ".join(match[2].split())
    if frequency not in {"annual", "ytd"} or (frequency == "annual" and year not in ANNUAL_YEARS):
        raise ValueError("Unreviewed SIAT annual period")
    if frequency == "ytd" and (year not in {2025, PARTIAL_YEAR} or not re.search(
            r"Last Quarter Imported:\s*2026\s*Q2(?:\s|$)", text)):
        raise ValueError("A historical half-year filter or imported-quarter boundary has not been verified")
    expected = f"{year} Q1 - {year} Q{4 if frequency == 'annual' else 2} United States Travelers to {country}"
    imported_only = frequency == "ytd" and year == PARTIAL_YEAR and title == (
        f"{year} Q1 - {year} Q4 United States Travelers to {country}")
    if title != expected and not imported_only:
        raise ValueError("SIAT country/year/quarter filters do not match the displayed result: " + title)
    update = re.search(r"Last Update:\s*([^\n]+)", text)
    if not update or "06-Oct-2026" not in update[1]:
        raise ValueError("SIAT monitor vintage changed; review quarter availability")
    value, sample = int(match[1].replace(",", "")), int(match[3].replace(",", ""))
    if not sample or value % 1000:
        raise ValueError("SIAT empty sample or published estimate precision changed")
    if value == 0:
        raise ValueError("SIAT zero volume with positive survey responses requires source clarification")
    return value, sample, update[1].strip()


def collect_siat(client):
    from playwright.sync_api import sync_playwright

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        try:
            page.goto(MONITOR, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(18000)
            frame = next(f for f in page.frames if "reportEmbed" in f.url)
            imported = "\n".join(f.locator("body").inner_text() for f in page.frames)
            if not re.search(r"Last Quarter Imported:\s*2026\s*Q2", imported):
                raise ValueError("SIAT imported-quarter boundary changed; review before collection")
            for year in (2026, 2025):
                node = frame.locator(f'[role=treeitem][title="{year}"]')
                if node.get_attribute("aria-expanded") == "true":
                    node.locator(".expandButton").click()
            year_scroller = frame.locator('[role=treeitem][title="2025"]').evaluate_handle(
                "(e)=>{let p=e.parentElement;while(p&&p.scrollHeight<=p.clientHeight)p=p.parentElement;return p;}")

            def year_node(year):
                node = frame.locator(f'[role=treeitem][title="{year}"]')
                if not node.count():
                    year_scroller.evaluate("(e)=>e.scrollTop=0")
                    for _ in range(12):
                        page.wait_for_timeout(150)
                        if node.count():
                            break
                        year_scroller.evaluate("(e)=>e.scrollTop+=180")
                if not node.count():
                    raise ValueError(f"SIAT year {year} is not available in the public year selector")
                return node

            frame.locator('[role=treeitem][title="OS"] .expandButton').click()
            frame.locator('[role=treeitem][title="Asia"] .expandButton').click()
            scroller = frame.locator('[role=treeitem][title="Asia"]').evaluate_handle(
                "(e)=>{let p=e.parentElement;while(p&&p.scrollHeight<=p.clientHeight)p=p.parentElement;return p;}")
            expanded = None
            periods = [(year, "annual") for year in ANNUAL_YEARS] + [(2026, "ytd"), (2025, "ytd")]
            for geo, country in COUNTRIES.items():
                selector = '[role=treeitem][title^="China,"]' if geo == "CHN" else '[role=treeitem][title="Hong Kong"]'
                node = frame.locator(selector)
                for attempt in range(8):
                    if node.count():
                        break
                    scroller.evaluate("(e)=>e.scrollTop+=100")
                    page.wait_for_timeout(500)
                node.locator(".slicerText").click()
                for year, frequency in periods:
                    if expanded is not None:
                        previous = year_node(expanded)
                        if previous.get_attribute("aria-expanded") == "true":
                            previous.locator(".expandButton").click()
                    selected_year = year_node(year)
                    selected_year.locator(".slicerText").click()
                    expanded = year
                    if frequency == "ytd":
                        if selected_year.get_attribute("aria-expanded") != "true":
                            selected_year.locator(".expandButton").click()
                        # Child checkboxes toggle independently; modifier-click can open a macOS context menu.
                        for quarter in ("Q3", "Q4"):
                            frame.locator(f'[role=treeitem][aria-level="2"][title="{quarter}"] .slicerText').click()
                    page.wait_for_timeout(2000)
                    text = frame.locator("body").inner_text() + "\n" + re.search(
                        r"Last Quarter Imported:\s*2026\s*Q2", imported)[0]
                    value, sample, update = parse_monitor_card(text, country, year, frequency)
                    body = text.encode()
                    checksum = digest(body)
                    write_atomic(client.cache / checksum, body)
                    asset = {"url": MONITOR, "sha256": checksum,
                             "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    row = observation(
                        "ntto_siat", "USA", geo, "air_visitors", year, value,
                        "NTTO SIAT estimates of U.S.-resident air travelers visiting the destination; all purposes, "
                        "including multi-destination trips; not all-mode border arrivals, unique people or U.S. citizenship counts",
                        frequency=frequency, month=6 if frequency == "ytd" else None,
                        status="low_reliability" if sample < 100 else "estimated",
                        notes=f"Public monitor, all U.S.A. source filters; {country}; "
                              + ("explicit Q1-Q2 selection, January–June, not a full-year total. " if frequency == "ytd"
                                 else "calendar-year Q1-Q4 selection. ")
                              + f"SIAT respondent count {sample:,}; published estimate rounded to 1,000. "
                              + ("Small respondent base (<100), interpret cautiously. " if sample < 100 else "")
                              + f"Monitor updated {update}; last imported quarter 2026 Q2. "
                              "Source checksum identifies the browser-captured visible report text with the selected filters, not an API response. "
                              "2021 is excluded: the monitor displays zero volume despite positive survey responses; "
                              "no literal zero is inferred. Survey and border-arrival populations are not spliced.")
                    rows.extend(attach([row], asset, "NTTO public SIAT outbound monitor; 6 October 2026"))
        finally:
            browser.close()
    return validate(rows)


def siat(client, refresh=False):
    cache = client.cache / "siat-reviewed.json"
    if cache.is_file() and not refresh:
        rows = validate(json.loads(cache.read_text()))
        for row in rows:
            body = (client.cache / row["raw_sha256"]).read_bytes()
            if digest(body) != row["raw_sha256"]:
                raise ValueError("Retained SIAT source response checksum mismatch")
            value, sample, _ = parse_monitor_card(
                body.decode(), COUNTRIES[row["destination"]], row["year"], row["frequency"])
            if value != row["value"] or row["status"] != ("low_reliability" if sample < 100 else "estimated"):
                raise ValueError("Retained SIAT observation differs from visible source evidence")
    else:
        rows = collect_siat(client)
        write_atomic(cache, json_text(rows))
    if {(r["destination"], r["year"], r["frequency"]) for r in rows} != {
            (geo, year, frequency) for geo in COUNTRIES for year, frequency in
            [(y, "annual") for y in ANNUAL_YEARS] + [(2026, "ytd"), (2025, "ytd")]}:
        raise ValueError("Reviewed SIAT destination/year coverage incomplete")
    return rows, "NTTO SIAT public monitor, 6 October 2026; through 2026 Q2", (
        "U.S.-resident air-travel destination estimates, kept separate from all-mode visitor arrivals. "
        "Annual 2012–2020 and 2022–2025; separately selected Q1-Q2 observations in 2025 and 2026 support matched January–June comparisons. "
        "Quarter checkboxes are selected directly, not inferred by subtracting rounded annual and half-year totals. "
        "Monitor total-traveler and respondent cards read from the public report with explicit year, quarter and destination filters; "
        "source checksums identify retained browser-visible report text, not API responses. "
        "Estimates are rounded to 1,000; respondent counts appear in each observation's notes. "
        "Under-100 respondent bases are conservatively flagged low reliability. "
        "The 2021 monitor cards show zero volume despite positive respondent counts (China 267; Hong Kong 44); "
        "these contradictory volume outputs are not interpreted as zero actual travel. No aggregation across destinations.")
