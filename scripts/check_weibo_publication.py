#!/usr/bin/env python3
"""Reconcile the publisher wall, account evidence, complete pagination and coverage."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import expect, sync_playwright
from us_china_exchange.weibo_analysis import validate_summary


def visible_ids(page):
    return set(page.locator(".weibo-publisher-link:visible").evaluate_all(
        "nodes=>nodes.map(n=>n.dataset.outletId)"))


def all_pages(page):
    seen = set()
    while not page.locator("#weibo-previous").is_disabled():
        page.locator("#weibo-previous").click()
    while True:
        current = visible_ids(page)
        assert not seen.intersection(current), "Publisher repeated on different result pages"
        assert page.locator(".weibo-brand:visible").count() <= 12
        seen.update(current)
        if page.locator("#weibo-next").is_disabled():
            break
        page.locator("#weibo-next").click()
    while not page.locator("#weibo-previous").is_disabled():
        page.locator("#weibo-previous").click()
    return seen


def check_page(page, summary):
    accounts = summary["accounts"]
    payload = json.loads(page.locator("#weibo-explorer-data").text_content())
    publishers = {p["id"]: p for p in payload["publishers"]}
    account_model = {a["id"]: a for a in payload["accounts"]}
    groups = {}
    for account in accounts:
        groups.setdefault(account["outlet_id"], []).append(account)
    def state(rows):
        periods = {a["existence"] for a in rows}
        return ("mixed" if {"current_evidence", "historical"} <= periods else
                "unknown" if "unknown" in periods else "profile" if "current_evidence" in periods else "historical")
    expect(page.locator("#weibo-filters")).to_be_visible()
    assert page.locator("#weibo-directory").evaluate("n=>n.tagName") == "SECTION"
    assert not page.locator("#coverage-waffle,#coverage-percent").count()
    assert not page.locator("#module-chart,.native-chart,#monthly-posts,#publication-years").count()
    assert not page.locator("#weibo-recovery").evaluate("n=>n.open")
    assert "%" not in page.locator("#weibo-directory").inner_text()
    assert page.locator(".weibo-channel-link").count() == len(accounts)
    assert page.locator(".weibo-brand").count() == len(groups)
    assert page.locator(".weibo-publisher-link").count() == len(groups)
    requested = [identity for identity in ("nyt", "wsj", "bloomberg", "forbes", "npr", "vogue") if identity in groups]
    assert page.locator(".weibo-brand").evaluate_all(
        "nodes=>nodes.slice(0,6).map(n=>n.dataset.outletId)")[:len(requested)] == requested
    for identity, rows in groups.items():
        assert set(publishers[identity]["research_categories"]) == {
            a.get("category", "not_recorded") for a in rows}
        assert set(publishers[identity]["categories"]) == {
            account_model[a["account_id"]]["editorial_category"] for a in rows}
        assert set(publishers[identity]["relationships"]) == {
            account_model[a["account_id"]]["relationship"] for a in rows}
        card = page.locator(f'.weibo-brand[data-outlet-id="{identity}"]')
        expect(card).to_have_attribute("data-evidence-state", state(rows))
        expect(card.locator(".weibo-publisher-state")).to_have_text({
            "mixed": "Mixed evidence", "profile": "Profile evidence only",
            "historical": "Historical evidence only", "unknown": "Evidence period incomplete"}[state(rows)])
    assert page.locator(".weibo-publisher-mark img").evaluate_all(
        "nodes=>nodes.every(n=>n.complete&&n.naturalWidth>0)"), "A publisher mark failed to load"
    for account in accounts:
        link = page.locator(f'.weibo-channel-link[data-account-id="{account["account_id"]}"]')
        expect(link.locator(".weibo-link-name")).to_have_text(account["display_name"] or account["outlet_name"])
        detail = page.locator(f'.weibo-channel-detail[data-account-id="{account["account_id"]}"]')
        expect(detail.locator(".weibo-relationship")).to_have_text(account["relationship"])
        if account.get("attribution_end"):
            expect(detail.locator(".weibo-period")).to_contain_text(account["attribution_end"])
    first = page.locator(".weibo-publisher-link:visible").first
    assert first.bounding_box()["y"] < 1000, "Publisher browsing is buried below the primary content"
    assert first.bounding_box()["height"] >= 44
    assert all_pages(page) == set(groups)
    expect(page.locator("#weibo-result-count")).to_contain_text(f"of {len(groups)} publishers")
    expect(page.locator(".weibo-overview")).to_contain_text(str(len(accounts)))
    expect(page.locator("#weibo-filter-options")).to_be_hidden()
    for evidence in ("profile", "historical", "mixed"):
        button = page.locator(f'[data-publisher-filter="{evidence}"]')
        expect(button).to_be_visible()
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        assert all_pages(page) == {identity for identity, rows in groups.items() if state(rows) == evidence}
        expect(page.locator("#weibo-filter-options")).to_be_hidden()
    page.locator('[data-publisher-filter=""]').click()
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    page.check("#weibo-followup")
    assert all_pages(page) == {identity for identity, rows in groups.items()
                               if any(a.get("primary_audit_status") != "numeric_binding_rechecked" for a in rows)}
    page.locator("#weibo-filters button[type=reset]").click()
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    for category in sorted({c for p in publishers.values() for c in p["categories"]}):
        page.select_option("#weibo-category", category)
        assert all_pages(page) == {identity for identity, p in publishers.items() if category in p["categories"]}
    page.select_option("#weibo-category", "")
    for relationship in sorted({r for p in publishers.values() for r in p["relationships"]}):
        page.select_option("#weibo-relationship", relationship)
        assert all_pages(page) == {identity for identity, p in publishers.items() if relationship in p["relationships"]}
    page.select_option("#weibo-relationship", "")
    target = next(a for a in accounts if a.get("uid"))
    page.fill("#weibo-search", target["uid"])
    tile = page.locator(f'.weibo-publisher-link[data-outlet-id="{target["outlet_id"]}"]')
    expect(tile).to_be_visible()
    tile.press("Enter")
    link = page.locator(f'.weibo-channel-link[data-account-id="{target["account_id"]}"]')
    link.press("Enter")
    detail = page.locator(".weibo-channel-detail:visible")
    expect(detail).to_have_count(1)
    expect(detail).to_have_attribute("data-account-id", target["account_id"])
    expect(detail.locator(".weibo-relationship")).to_have_text(target["relationship"])
    expect(detail.locator(".weibo-uid")).to_have_text(target["uid"])
    expect(detail.locator("h4")).to_be_focused()
    expect(page.locator("#weibo-map")).to_be_visible()
    assert page.locator(".weibo-publisher-detail:visible").evaluate("n=>n.parentElement.id") == "weibo-map"
    assert page.locator(".weibo-publisher-detail:visible").evaluate("n=>getComputedStyle(n).position") != "sticky"
    detail.locator("h4").press("Escape")
    expect(tile).to_be_focused()
    page.fill("#weibo-search", "__no_matching_media_channel__")
    assert visible_ids(page) == set()
    expect(page.locator("#weibo-empty")).to_be_visible()
    assert not page.locator(".weibo-channel-detail:visible").count()
    if not page.locator("#weibo-filter-options").is_visible():
        page.locator("#weibo-filter-toggle").click()
    page.locator("#weibo-filters button[type=reset]").click()
    assert all_pages(page) == set(groups)
    composition = page.locator("#weibo-channel-composition")
    for evidence in ("current_evidence", "historical", "unknown"):
        count = sum(a["existence"] == evidence for a in accounts)
        segment = composition.locator(f'[data-state="{evidence}"]')
        assert (int(segment.get_attribute("data-count")) if segment.count() else 0) == count
        if count:
            expect(composition).to_contain_text(f"{count:,} of {len(accounts):,}")
            expect(composition).to_contain_text(f"{count / len(accounts) * 100:.1f}%")
    first = page.locator(".weibo-publisher-link:visible").first
    second = page.locator(".weibo-publisher-link:visible").nth(1)
    first.focus()
    first.press("ArrowRight")
    expect(second).to_be_focused()
    second.press("Enter")
    expect(second).to_have_attribute("aria-expanded", "true")
    page.locator(".weibo-publisher-detail:visible .weibo-close-publisher").click()
    expect(second).to_have_attribute("aria-expanded", "false")
    expect(second).to_be_focused()
    cohort = summary.get("cohort")
    if cohort:
        page.locator(".weibo-cohort > summary").click()
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
            expect(page.locator(".weibo-channel-detail:visible h4")).to_be_in_viewport()
            expect(page.locator(".weibo-publisher-detail:visible .weibo-close-publisher")).to_be_in_viewport()
            page.locator(".weibo-publisher-detail:visible .weibo-close-publisher").click()
            publisher = next(a["outlet_id"] for a in summary["accounts"] if a["account_id"] == last)
            expect(page.locator(f'.weibo-publisher-link[data-outlet-id="{publisher}"]')).to_be_visible()
            assert not errors, errors
            page.close()
        touch = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 390, "height": 844})
        page = touch.new_page()
        page.goto(url)
        target = page.locator(".weibo-publisher-link:visible").first
        identity = target.get_attribute("data-outlet-id")
        target.tap()
        expect(page.locator(".weibo-publisher-detail:visible")).to_have_attribute("data-outlet-id", identity)
        expect(page.locator(".weibo-publisher-detail:visible .weibo-close-publisher")).to_be_visible()
        assert page.locator(".weibo-publisher-detail:visible").bounding_box()["height"] < 1000
        if screenshots:
            page.screenshot(path=str(screenshots / "weibo-detail-touch.png"), full_page=True)
        page.locator(".weibo-publisher-detail:visible .weibo-close-publisher").tap()
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
