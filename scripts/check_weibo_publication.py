#!/usr/bin/env python3
"""Check public account identity, complete pagination and compact coverage semantics."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import expect, sync_playwright
from us_china_exchange.weibo_analysis import validate_summary


def visible_ids(page):
    return set(page.locator(".weibo-channel-link:visible").evaluate_all(
        "nodes=>nodes.map(n=>n.dataset.accountId)"))


def all_pages(page):
    seen = set()
    while not page.locator("#weibo-previous").is_disabled():
        page.locator("#weibo-previous").click()
    while True:
        current = visible_ids(page)
        assert not seen.intersection(current), "Channel repeated on different result pages"
        assert page.locator(".weibo-brand:visible").count() <= 8
        seen.update(current)
        if page.locator("#weibo-next").is_disabled():
            break
        page.locator("#weibo-next").click()
    while not page.locator("#weibo-previous").is_disabled():
        page.locator("#weibo-previous").click()
    return seen


def check_page(page, summary):
    accounts = summary["accounts"]
    ids = {a["account_id"] for a in accounts}
    expect(page.locator("#weibo-filters")).to_be_visible()
    assert page.locator("#weibo-directory").evaluate("n=>n.tagName") == "SECTION"
    assert not page.locator("#coverage-waffle,#coverage-percent").count()
    assert not page.locator("#module-chart,.native-chart,#monthly-posts,#publication-years").count()
    assert not page.locator("#weibo-recovery").evaluate("n=>n.open")
    assert page.locator(".weibo-channel-link").count() == len(accounts)
    assert page.locator(".weibo-brand").count() == len({a["outlet_id"] for a in accounts})
    for account in accounts:
        link = page.locator(f'.weibo-channel-link[data-account-id="{account["account_id"]}"]')
        expect(link.locator(".weibo-link-name")).to_have_text(account["display_name"] or account["outlet_name"])
    first = page.locator(".weibo-channel-link:visible").first
    assert first.bounding_box()["y"] < 1000, "Account browsing is buried below the primary content"
    assert first.bounding_box()["height"] >= 44
    assert all_pages(page) == ids
    expect(page.locator("#weibo-result-count")).to_contain_text(str(len(accounts)))
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    page.select_option("#weibo-evidence", "historical")
    if page.viewport_size["width"] <= 760:
        page.locator("#weibo-filter-toggle").click()
        expect(page.locator("#weibo-filter-options")).to_be_hidden()
        expect(page.locator("#weibo-filter-toggle")).to_have_text("Filters (1)")
    assert all_pages(page) == {a["account_id"] for a in accounts if a["existence"] == "historical"}
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    page.select_option("#weibo-evidence", "")
    page.check("#weibo-followup")
    assert all_pages(page) == {a["account_id"] for a in accounts
                               if a.get("primary_audit_status") != "numeric_binding_rechecked"}
    page.locator("#weibo-filters button[type=reset]").click()
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    for category in sorted({a.get("category", "not_recorded") for a in accounts}):
        page.select_option("#weibo-category", category)
        assert all_pages(page) == {a["account_id"] for a in accounts if a.get("category", "not_recorded") == category}
    page.select_option("#weibo-category", "")
    target = next(a for a in accounts if a.get("uid"))
    page.fill("#weibo-search", target["uid"])
    link = page.locator(f'.weibo-channel-link[data-account-id="{target["account_id"]}"]')
    expect(link).to_be_visible()
    link.press("Enter")
    detail = page.locator(".weibo-channel-detail:visible")
    expect(detail).to_have_count(1)
    expect(detail).to_have_attribute("data-account-id", target["account_id"])
    expect(detail.locator(".weibo-relationship")).to_have_text(target["relationship"])
    expect(detail.locator(".weibo-uid")).to_have_text(target["uid"])
    expect(detail.locator("h3")).to_be_focused()
    detail.locator("h3").press("Escape")
    expect(link).to_be_focused()
    page.fill("#weibo-search", "__no_matching_media_channel__")
    assert visible_ids(page) == set()
    expect(page.locator("#weibo-empty")).to_be_visible()
    assert not page.locator(".weibo-channel-detail:visible").count()
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    page.locator("#weibo-filters button[type=reset]").click()
    assert all_pages(page) == ids
    cohort = summary.get("cohort")
    if cohort:
        coverage = page.locator("#weibo-coverage")
        assert not coverage.evaluate("n=>n.open")
        coverage.evaluate("n=>n.open=true")
        documented = cohort["current_identity_domains"] + cohort["historical_only_domains"]
        expect(page.locator("#coverage-tally")).to_contain_text(f"{documented:,} of {cohort['selected_domains']:,}")
        actual = page.locator("#coverage-bar .coverage-segment").evaluate_all(
            "nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.state,Number(n.dataset.count)]))")
        expected = {state: count for state, count in {
            "current_evidence": cohort["current_identity_domains"],
            "historical": cohort["historical_only_domains"], "unknown": cohort["unknown_domains"],
            "candidate": cohort["candidate_domains"], "verified_negative": cohort["verified_negative_domains"],
        }.items() if count}
        assert actual == expected
        assert sum(actual.values()) == cohort["selected_domains"]
        assert page.locator("#coverage-bar").evaluate("""(bar,total)=>{
          const width=bar.clientWidth;
          return [...bar.children].every(n=>Math.abs(n.getBoundingClientRect().width/width-Number(n.dataset.count)/total)<.005);
        }""", cohort["selected_domains"]), "Coverage segment geometry does not match counts"
        page.locator('[data-coverage-mode="review"]').click()
        expect(page.locator("#coverage-tally")).to_contain_text(f"{cohort['manually_reviewed_domains']:,} of {cohort['selected_domains']:,}")
        page.locator("#coverage-bar").focus()
        page.locator("#coverage-bar").press("End")
        expect(page.locator('.coverage-category[data-state="unreviewed"]')).to_have_attribute("aria-pressed", "true")
        page.locator("#coverage-bar").press("Escape")
        assert page.locator(".coverage-dimmed").count() == 0
        page.locator('[data-coverage-mode="evidence"]').click()
        coverage.evaluate("n=>n.open=false")
    recovery = page.locator("#weibo-recovery")
    recovery.evaluate("n=>n.open=true")
    represented = sum(a["recovered_posts"] > 0 for a in accounts)
    for state, count in (("represented", represented), ("unrepresented", len(accounts) - represented)):
        segment = recovery.locator(".recovery-bar").first.locator("." + state)
        assert (int(segment.get_attribute("data-count")) if segment.count() else 0) == count
    expect(recovery).to_contain_text("cannot be estimated")
    recovery.evaluate("n=>n.open=false")
    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")


def check(site, url=None, screenshots=None):
    summary = validate_summary(json.loads((site / "downloads/weibo-summary.json").read_text()))
    url = url or (site.resolve() / "weibo.html").as_uri()
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1360, 768, 390, 320):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url)
            page.evaluate("document.fonts.ready")
            check_page(page, summary)
            if screenshots:
                page.goto(url)
                page.evaluate("document.fonts.ready")
                page.screenshot(path=str(screenshots / f"weibo-directory-{width}.png"), full_page=True)
            last = page.locator(".weibo-channel-link").last.get_attribute("data-account-id")
            base = url.split("#")[0].split("?")[0]
            page.goto(base + "?q=__conflicting_filter__#weibo-account-" + last)
            expect(page.locator(".weibo-channel-detail:visible")).to_have_attribute("data-account-id", last)
            expect(page.locator("#weibo-search")).to_have_value("")
            expect(page.locator(f'.weibo-channel-link[data-account-id="{last}"]')).to_have_attribute("aria-current", "true")
            expect(page.locator(".weibo-channel-detail:visible h3")).to_be_in_viewport()
            if width <= 760:
                expect(page.locator("#weibo-back")).to_be_in_viewport()
                page.locator("#weibo-back").click()
            else:
                page.locator(".weibo-channel-detail:visible h3").press("Escape")
            expect(page.locator(f'.weibo-channel-link[data-account-id="{last}"]')).to_be_visible()
            assert not errors, errors
            page.close()
        touch = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = touch.new_page()
        page.goto(url)
        target = page.locator(".weibo-channel-link:visible").first
        identity = target.get_attribute("data-account-id")
        target.tap()
        expect(page.locator(".weibo-channel-detail:visible")).to_have_attribute("data-account-id", identity)
        expect(page.locator("#weibo-back")).to_be_visible()
        assert page.locator(".weibo-inspector").bounding_box()["height"] < 1000
        if screenshots:
            page.screenshot(path=str(screenshots / "weibo-detail-touch.png"), full_page=True)
        page.locator("#weibo-back").tap()
        expect(target).to_be_visible()
        touch.close()
        fallback = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = fallback.new_page()
        page.goto(url)
        expect(page.locator("#weibo-filters")).to_be_hidden()
        expect(page.locator("#weibo-pagination")).to_be_hidden()
        assert page.locator(".weibo-channel-link:visible").count() == len(summary["accounts"])
        assert page.locator(".weibo-channel-detail:visible").count() == len(summary["accounts"])
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        fallback.close()
        browser.close()
    print(f"Weibo directory: all {len(summary['accounts'])} channels, full pagination, exact evidence/coverage counts, deep links, 320px layout, keyboard, touch and no-JS checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.site, args.url, args.screenshots)
