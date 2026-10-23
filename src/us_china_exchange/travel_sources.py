"""Manual review of the public NTTO resident-air-travel monitor."""

import json
import re
from datetime import datetime, timezone

from .model import digest, json_text, observation, validate
from .pipeline import write_atomic
from .sources import attach


MONITOR = "https://powerbi.trade.gov/#/workspace/IA-NTTO-PUBLIC/report/SIAT_Res_Final_Monitor"
COUNTRIES = {"CHN": "China, People's Republic of", "HKG": "Hong Kong"}
ANNUAL_YEARS = (2019, 2022, 2023, 2024, 2025)
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
                        previous = frame.locator(f'[role=treeitem][title="{expanded}"]')
                        if previous.get_attribute("aria-expanded") == "true":
                            previous.locator(".expandButton").click()
                    year_node = frame.locator(f'[role=treeitem][title="{year}"]')
                    year_node.locator(".slicerText").click()
                    expanded = year
                    if frequency == "ytd":
                        if year_node.get_attribute("aria-expanded") != "true":
                            year_node.locator(".expandButton").click()
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
                              "2020-2021 are not filled or treated as zero; survey and border-arrival populations are not spliced.")
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
        "Annual 2019 and 2022–2025; separately selected Q1-Q2 observations in 2025 and 2026 support matched January–June comparisons. "
        "Quarter checkboxes are selected directly, not inferred by subtracting rounded annual and half-year totals. "
        "Monitor total-traveler and respondent cards read from the public report with explicit year, quarter and destination filters; "
        "source checksums identify retained browser-visible report text, not API responses. "
        "Estimates are rounded to 1,000; respondent counts appear in each observation's notes. "
        "Under-100 respondent bases are conservatively flagged low reliability. "
        "No 2020–2021 estimates or invented zeros; no aggregation across destinations.")
