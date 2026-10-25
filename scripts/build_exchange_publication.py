#!/usr/bin/env python3
"""Build the collective publication offline from reviewed public aggregates."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from us_china_exchange.model import GEOGRAPHIES, json_text
from us_china_exchange.language_analysis import RETIRED_CHARTS as LANGUAGE_RETIRED_CHARTS
from us_china_exchange.render import SPLIT_REGIONAL_MEASURES, annual_table, build, figure_links, initial_panel, svg_chart
from us_china_exchange.theme import figure_category
from us_china_exchange.confucius_analysis import CHARTS as CONFUCIUS_CHARTS
from us_china_exchange.public_freshness import POLICY, eligible, public_charts
from us_china_exchange.covid_context import COVID_CONTEXT, context_for as covid_context_for


CANONICAL = "https://www.themarginoferror.com/china-us-relations/"
REPOSITORY = "https://github.com/hanshanley/china-us-relation-change"
PAGES = {
    "index.html": ("Student exchanges", "Enrollment and study abroad between the U.S., mainland China, Hong Kong and Macau.",
                   "Academic-year series · Enrollment and participation kept separate"),
    "trade.html": ("Trade", "Goods and services exchanged with the U.S., with mainland China separate from Hong Kong and Macau.",
                   "Annual reported values · Separate regional scales"),
    "travel.html": ("Travel & tourism", "Visitor trips between the U.S., mainland China, Hong Kong and Macau.",
                    "Arrivals are trips, not unique people or necessarily leisure tourists"),
    "immigration.html": ("Immigration", "Annual permanent immigration and separate views of where people live.",
                         "Resident stocks through 2024 · U.S. grants and Macau approvals through 2025"),
    "opinions.html": ("Public opinion", "How Americans view China, how Chinese respondents view the U.S., and the differences by age.",
                      "Reported survey rounds · Different questions kept separate"),
    "comparisons.html": ("Regional comparisons", "Comparisons are organized within Students, Travel and Trade.",
                         "Existing chart links lead to their topic"),
    "language-learning.html": ("Language learning", "Chinese, Japanese and Korean compared through course enrollments, degree awards and school programs.",
                              "AP exams through 2025 · Degree awards through 2024 · College census through 2021"),
    "confucius.html": ("Confucius Institutes & Classrooms", "U.S. institutes, school programs and documented replacements, counted separately.",
                       "Dated historical reports · Operator listings are not an operating census"),
    "business-presence.html": ("Business links", "U.S. investment abroad, China-linked affiliates in the U.S., and recent company decisions. Each measure and geography kept separate.",
                             "Year-end investment positions: 2000-2025 · Company surveys: 2026"),
    "weibo.html": ("U.S. media on Weibo", "Documented accounts and Chinese-language editions, with sources for each association.",
                   "Account identity evidence, not a measure of posting activity"),
}
TABS = [("index.html", "Students"), ("travel.html", "Travel & tourism"), ("trade.html", "Trade"), ("immigration.html", "Immigration"),
        ("opinions.html", "Opinions"),
        ("language-learning.html", "Language"), ("confucius.html", "Confucius programs"),
        ("business-presence.html", "Business"), ("weibo.html", "Weibo")]


def fragment(markup):
    return BeautifulSoup(markup, "html.parser")


def prune_unlinked_figures(site):
    linked = set()

    def keep(value):
        if isinstance(value, dict):
            for item in value.values():
                keep(item)
        elif isinstance(value, str):
            path = urlsplit(value).path
            if path.startswith("figures/"):
                linked.add(path)

    for path in site.glob("*.html"):
        soup = fragment(path.read_text())
        for node in soup.select('a[href^="figures/"],img[src^="figures/"]'):
            keep(node.get("href") or node["src"])
        payload = soup.select_one("#exchange-data")
        if payload:
            keep(json.loads(payload.string).get("figures", {}))
    for path in (site / "figures").rglob("*"):
        if path.is_file() and path.suffix in {".png", ".svg"} and str(path.relative_to(site)) not in linked:
            path.unlink()


def regional_topic(measure):
    return ("trade.html" if measure in {"goods", "services"} else
            "travel.html" if "visitors" in measure else "index.html")


def prepare_topic_pages(site):
    source = (site / "index.html").read_text()
    comparison = BeautifulSoup((site / "comparisons.html").read_text(), "html.parser")
    sections = [section for section in comparison.select("main > section[id]")
                if section.select_one(".comparison-chart")]
    routes = {}
    for name in ("index.html", "travel.html", "trade.html"):
        page = BeautifulSoup(source, "html.parser")
        selected = [section for section in sections
                    if regional_topic(section["id"].rsplit("-", 1)[0]) == name]
        details = page.new_tag("details", attrs={"id": "regional-comparisons", "class": "regional-explorer"})
        summary = page.new_tag("summary")
        summary.string = "Compare mainland China, Hong Kong & Macau"
        details.append(summary)
        for section in selected:
            chart = fragment(str(section)).section
            chart["data-regional-chart"] = ""
            details.append(chart)
            routes[chart["id"]] = name
        page.main.append(details)
        (site / name).write_text(str(page), encoding="utf-8")
    comparison.main.clear()
    for name, label in (("index.html", "Students"), ("travel.html", "Travel & tourism"), ("trade.html", "Trade")):
        section = comparison.new_tag("section", attrs={"class": "comparison-directory"})
        heading = comparison.new_tag("h2")
        heading.string = label
        section.append(heading)
        for original in sections:
            if routes[original["id"]] != name or not original.select_one(".comparison-chart"):
                continue
            p = comparison.new_tag("p")
            a = comparison.new_tag("a", attrs={"href": f'{name}?indicator={original["id"]}#regional-comparisons'})
            a.string = original.h2.text
            p.append(a)
            section.append(p)
        comparison.main.append(section)
    data = comparison.new_tag("script", attrs={"type": "application/json", "id": "regional-topic-routes"})
    data.string = json_text(routes)
    comparison.body.append(data)
    (site / "comparisons.html").write_text(str(comparison), encoding="utf-8")


def module_controls(soup, charts, preferred, groups=None):
    controls = soup.new_tag("div", attrs={"class": "controls module-controls", "hidden": ""})
    label = soup.new_tag("label", attrs={"for": "module-chart"})
    label.string = "Indicator"
    select = soup.new_tag("select", attrs={"id": "module-chart"})
    parents = {}
    for i, section in enumerate(charts):
        identifier = section.get("id", f"indicator-{i}")
        section["data-module-chart"] = identifier
        parent = select
        if groups and identifier in groups:
            group = groups[identifier]
            if group not in parents:
                parents[group] = soup.new_tag("optgroup", attrs={"label": group})
                select.append(parents[group])
            parent = parents[group]
        option = soup.new_tag("option", attrs={"value": identifier})
        option.string = section.h2.text
        if identifier == preferred:
            option["selected"] = ""
        parent.append(option)
    label.append(select)
    controls.append(label)
    return controls


def plot_model(svg, labels, observations):
    paths = svg.select("path.data-line")
    years = [int(n.text) for n in svg.select("text")
             if re.fullmatch(r"\d{4}", n.text or "") and float(n.get("y", 0)) >= 440]
    unit = svg.select_one(".axis-unit")
    if unit is None:
        unit = svg.find("text", attrs={"x": "115", "y": "125"})
    model = {"title": svg.get("aria-label", ""), "description": svg.find("desc").text if svg.find("desc") else "",
             "unit": unit.text if unit else "Count", "groups": [], "kind": "line"}
    if svg.select_one(".covid-band"):
        marker = svg.select_one(".covid-context[data-covid-measure]")
        context = covid_context_for(marker["data-covid-measure"]) if marker else COVID_CONTEXT
        if context is None:
            raise ValueError("Unsupported COVID context measure")
        model["covid_context"] = context
    if svg.get("data-axis-max"):
        model["axis_max"] = float(svg["data-axis-max"])
    if svg.get("data-plot-style") == "columns" or svg.select_one(".snapshot-bar"):
        from collections import defaultdict

        groups = defaultdict(list)
        colors = {}
        for point in svg.select("circle[data-series-id][data-year][data-value]"):
            sid = point["data-series-id"]
            colors[sid] = point["fill"]
            groups[sid].append({
                "year": int(point["data-year"]), "value": float(point["data-value"]), "connect": False,
                "label": point.title.text if point.title else "", "period": point.get("data-period", point["data-year"]),
                "reported_value": float(point.get("data-reported-value", point["data-value"])),
                "reported_unit": point.get("data-reported-unit", model["unit"]), "status": point.get("data-status", "")})
        for sid, points in groups.items():
            parts = sid.split(":")
            geo = (parts[2] if parts[1] == "USA" else parts[1]) if len(parts) == 4 and parts[1] in GEOGRAPHIES else None
            model["groups"].append({"id": sid, "label": GEOGRAPHIES[geo] if geo else labels.get(sid, ""),
                                    "color": colors[sid], "points": points})
        if not groups:
            raise ValueError("Column chart requires reported point metadata")
        all_years = [p["year"] for group in groups.values() for p in group]
        model.update(columns=svg.get("data-plot-style") == "columns",
                     snapshots=bool(svg.select_one(".snapshot-bar")),
                     first=int(svg.get("data-first-year", min(all_years))),
                     last=int(svg.get("data-last-year", max(years + all_years))))
        if svg.get("data-geographies"):
            model["geographies"] = svg["data-geographies"].split()
            model["show_legend"] = len(model["geographies"]) < 3
        return model
    if svg.get("data-geographies"):
        model["geographies"] = svg["data-geographies"].split()
        model["show_legend"] = len(model["geographies"]) < 3
    dated = svg.select("circle.data-point[data-date]")
    monthly = dated or svg.select("circle.data-point[data-month]")
    if monthly:
        from datetime import date
        period = "date" if dated else "month"
        points = []
        previous = None
        for point in monthly:
            month = point["data-" + period]
            index = date.fromisoformat(month).toordinal() if dated else int(month[:4]) * 12 + int(month[5:]) - 1
            value = float(point["data-value"])
            points.append({period: month, period + "_index": index, "value": value,
                           "partial_window": point["data-partial-window"] == "true",
                           "connect": previous is not None and index == previous + 1,
                           "label": point.title.text})
            previous = index
        model.update(frequency="daily" if dated else "monthly", first=points[0][period + "_index"], last=points[-1][period + "_index"],
                     groups=[{"label": model["title"], "id": svg["data-metric"],
                              "color": monthly[0]["stroke"], "points": points}])
        return model
    if svg.select_one("rect.snapshot-bar"):
        model["snapshots"] = True
    legends = [n.text for n in svg.select(".legend-label")]
    swatches = svg.select(".legend-swatch")
    if swatches:
        model["legend"] = [{"label": p.find_next_sibling("text").text.replace("*", " — unavailable"),
                            "color": p["stroke"], "dash": p.get("stroke-dasharray", "")} for p in swatches]
    for i, path in enumerate(paths):
        color = path.get("stroke")
        circles = [p for p in svg.select("circle") if p.get("fill") == color]
        commands = re.findall(r"[ML]", path.get("d", ""))
        if not circles or len(circles) != len(commands):
            return None
        sid = path.get("data-series-id") or path.get("data-geography")
        geo = path.get("data-geography")
        points = []
        for p, command in zip(circles, commands):
            year = p.get("data-year")
            if year is None and p.find("title"):
                match = re.search(r"(?:^|\s)(\d{4})(?:/\d{2})?:", p.title.text)
                year = match[1] if match else None
            value = p.get("data-value")
            if value is None and p.get("data-period"):
                reported = observations.get((sid, p["data-period"]))
                if reported:
                    value, year = reported["value"], reported["year"]
            if year is None or value is None:
                return None
            points.append({"year": int(year), "value": float(value), "connect": command == "L",
                           "label": p.title.text if p.find("title") else "",
                           "period": p.get("data-period", str(year)),
                           "reported_value": float(p.get("data-reported-value", value)),
                           "reported_unit": p.get("data-reported-unit", model["unit"]),
                           "status": p.get("data-status", "")})
        model["groups"].append({"label": GEOGRAPHIES[geo] if geo else legends[i] if i < len(legends) else labels.get(sid, ""),
                                "color": color, "dash": path.get("stroke-dasharray", ""),
                                "id": sid or "", "points": points})
    if paths:
        all_years = [p["year"] for g in model["groups"] for p in g["points"]]
        model.update(first=int(svg.get("data-first-year", min(all_years))),
                     last=int(svg.get("data-last-year", max(years + all_years))))
        return model
    bars = svg.select("rect.data-bar, rect.language-point, rect.business-point, rect.immigration-point, rect.opinion-point")
    if bars:
        model["kind"] = "bars"
        model["bars"] = []
        model["unavailable_bars"] = [
            {"id": p["data-series-id"], "label": p["data-label"], "reason": p["data-reason"]}
            for p in svg.select(".unavailable-bar")]
        for p in bars:
            label = p.get("data-label") or labels.get(p.get("data-series-id"), "")
            year = p.get("data-year")
            if year and year not in label:
                label += f" ({year})"
            model["bars"].append({"label": label, "value": float(p["data-value"]), "color": p["fill"],
                                  "id": p.get("data-series-id", label), "year": int(year) if year else None,
                                  "period": p.get("data-period"), "status": p.get("data-status", ""),
                                  "partial_window": label.endswith("*")})
        return model
    return None


def decorate(site, name, labels, revision):
    soup = BeautifulSoup((site / name).read_text(), "html.parser")
    if name == "immigration.html" and soup.select_one("#state-china-map"):
        state = json.loads((site / "downloads/state-immigration.json").read_text())
        if not eligible([{"year": state["end_year"], "value": 1}], snapshot=True):
            soup.select_one("#state-china-map").decompose()
    title, lead, scope = PAGES[name]
    if name in {"index.html", "travel.html", "trade.html"}:
        rows = json.loads((site / "downloads/observations.json").read_text())
        rows = [r for r in rows if regional_topic(r["measure"]) == name]
        annual = max(r["year"] for r in rows if r["frequency"] == "annual" and r["value"] is not None)
        partial = max((r["year"] for r in rows if r["frequency"] == "ytd" and r["value"] is not None), default=annual)
        scope = (f"Academic ending years through {annual}" if name == "index.html" else f"{annual} annual data")
        scope += f" · {partial} partial-year updates" if partial > annual else ""
    elif name == "language-learning.html":
        rows = json.loads((site / "downloads/language-learning.json").read_text())["observations"]
        latest = lambda prefix: max(r["year"] for r in rows if r["series_id"].startswith(prefix) and r["value"] is not None)
        scope = f"Degree awards through {latest('ipeds:')} · AP exams through {latest('ap:')} · School offerings: January 2024"
    elif name == "business-presence.html":
        inward_path = site / "downloads/business-inward.json"
        if inward_path.is_file():
            rows = json.loads(inward_path.read_text())["observations"]
            scope += f' · U.S. affiliate counts: {min(row["year"] for row in rows)}–{max(row["year"] for row in rows)}'
    elif name == "immigration.html" and (site / "downloads/state-immigration.json").is_file():
        state_data = json.loads((site / "downloads/state-immigration.json").read_text())
        immigration = json.loads((site / "downloads/immigration.json").read_text())
        approval_year = max(r["year"] for r in immigration["observations"] if not r["series_id"].startswith("un_stock:"))
        scope = (f"State estimates: {state_data['start_year']}–{state_data['end_year']} ACS"
                 f" · Residence approvals through {approval_year}")
    elif name == "confucius.html":
        program_data = json.loads((site / "downloads/confucius-programs.json").read_text())
        snapshot = next(r["reference"] for r in program_data["observations"] if r["id"] == "cief_institutes")
        scope = f"Operator directory retrieved {snapshot} · Listings are not an operating census"
        timelines = soup.select('svg[data-confucius-chart][data-chart-layout="timeline"]')
        if timelines:
            first = min(int(chart["data-first-year"]) for chart in timelines)
            last = max(int(chart["data-last-year"]) for chart in timelines)
            scope = f"Reported histories: {first}–{last} · Directory retrieved {snapshot}; not an operating census"
        directory = soup.select_one("main > .confucius-directory")
        if directory and not soup.select("main > .series-panel .comparison-chart"):
            directory["open"] = ""
            title = "Confucius program directory"
            lead = "U.S. operator listings, not a verified count of programs currently operating."
    elif name == "opinions.html":
        from datetime import date

        opinions = json.loads((site / "downloads/opinions.json").read_text())
        latest = {}
        for row in opinions["observations"]:
            country = opinions["series"][row["series_id"]]["respondent_country"]
            end = opinions["surveys"][row["survey_id"]]["field_end"]
            if row["value"] is not None and end:
                latest[country] = max(latest.get(country, end), end)
        scope = " · ".join(label + " fieldwork through " + date.fromisoformat(latest[country]).strftime("%B %Y")
                           for country, label in (("USA", "U.S."), ("CHN", "China")))
    soup.title.string = title + " | The Margin of Error"
    for old in soup.select('link[rel=canonical],meta[name=description]'):
        old.decompose()
    soup.head.append(soup.new_tag("link", attrs={"rel": "canonical", "href": CANONICAL + ("" if name == "index.html" else name)}))
    soup.head.append(soup.new_tag("meta", attrs={"name": "description", "content": lead + " " + scope}))
    soup.head.append(soup.new_tag("meta", attrs={"name": "chart-freshness", "content": json_text(POLICY)}))
    soup.head.append(soup.new_tag("link", attrs={"rel": "stylesheet", "href": f"assets/publication.css?v={revision[:12]}"}))
    soup.body["class"] = ["publication-page"]
    page = soup.select_one(".page")
    main = page.find("main")
    main["id"] = "analysis"
    header = page.find("header", recursive=False)
    old_intro = [n.extract() for n in header.find_all(["p", "details"], recursive=False)] if header else []
    if header:
        header.decompose()
    intro = fragment(f'<header class="analysis-heading"><p class="kicker">Interactive analysis</p>'
                     f'<h1>{title}</h1><p class="analysis-deck">{lead}</p><p class="analysis-scope">{scope}</p></header>')
    tabs = soup.new_tag("nav", attrs={"class": "analysis-tabs", "aria-label": "Analysis topics"})
    for target, label in TABS:
        if not (site / target).exists():
            continue
        a = soup.new_tag("a", attrs={"href": target})
        a.string = label
        if target == name:
            a["aria-current"] = "page"
        tabs.append(a)
    a = soup.new_tag("a", attrs={"href": REPOSITORY})
    a.string = "GitHub"
    tabs.append(a)
    page.insert(0, tabs)
    for node in reversed(list(intro.contents)):
        page.insert(0, node)
    if name in {"index.html", "travel.html", "trade.html"}:
        initial_measure = {"index.html": "international_students", "travel.html": "visitors", "trade.html": "goods"}[name]
        for p in list(main.find_all("p", recursive=False)):
            p.decompose()
        for option in soup.select('#geography option[value="TWN"]'):
            option.decompose()
        form = soup.select_one("form.controls")
        form["hidden"] = ""
        display = soup.new_tag("label", attrs={"for": "chart-mode"})
        display.string = "Display"
        display.append(soup.select_one("#chart-mode").extract())
        form.append(display)
        short_labels = {"international_students": "Students + OPT", "enrolled_students": "Enrolled students",
                        "degree_students": "Degree students", "study_abroad": "Credit study abroad",
                        "visitors": "Visitor trips", "leisure_visitors": "Leisure trips",
                        "air_visitors": "U.S. air estimates",
                        "goods": "Goods trade", "services": "Services trade"}
        for option in soup.select("#measure option"):
            option.string = short_labels[option["value"]]
            if regional_topic(option["value"]) != name:
                option.decompose()
        payload = json.loads(soup.select_one("#exchange-data").string)
        payload["restrict_to_available"] = True
        payload["prefer_current_travel"] = True
        payload["public_display"] = True
        soup.select_one('#chart-mode option[value="index"]').string = "Baseline = 100"
        for identifier in ["selection-note", "related-series"]:
            note = soup.new_tag("p", attrs={"id": identifier, "class": "chart-note", "hidden": ""})
            if identifier == "selection-note":
                note["role"] = "status"
                note["aria-live"] = "polite"
            form.insert_after(note)
        if name == "travel.html":
            available = {r["measure"] for r in payload["observations"] if r["measure"] in {"visitors", "leisure_visitors", "air_visitors"}
                         and (r["origin"] in {"CHN", "HKG", "MAC"} or r["destination"] in {"CHN", "HKG", "MAC"})
                         and r["value"] is not None}
            for option in list(soup.select("#measure option")):
                if option["value"] not in available:
                    option.decompose()
                elif option["value"] == "visitors":
                    option.string = "All-purpose arrivals"
        for option in soup.select("#measure option"):
            option.attrs.pop("selected", None)
            if option["value"] == initial_measure:
                option["selected"] = ""
        selected = [r for r in payload["observations"] if r["origin"] == "CHN" and r["destination"] == "USA" and r["measure"] == initial_measure]
        current = max((r for r in selected if r["frequency"] == "annual" and r["value"] is not None), key=lambda r: r["year"])
        soup.select_one("#series-category").string = payload["measures"][initial_measure]
        soup.select_one("#series-title").string = "Mainland China → United States"
        for target, markup in [("#annual-headlines", initial_panel(selected)), ("#series-table", annual_table(selected)),
                               ("#chart", svg_chart(selected))]:
            node = soup.select_one(target)
            node.clear()
            node.append(fragment(markup))
        soup.select_one("#definition").string = current["definition"]
        soup.select_one("#series-source").string = payload["source_names"][current["source_id"]] + " · " + current["source_vintage"]
        soup.select_one("#series-notes").string = current["notes"]
        soup.select_one("#figure-link").clear()
        soup.select_one("#figure-link").append(fragment(figure_links(payload["figures"][current["series_id"]])))
        for key in ["charts", "figures"]:
            for sid in list(payload[key]):
                if ":TWN:" in sid:
                    del payload[key][sid]
        soup.select_one("#exchange-data").string = json_text(payload).replace("<", "\\u003c")
        panel = soup.select_one(".series-panel")
        panel["class"].append("exchange-panel")
        population = soup.new_tag("p", attrs={"id": "series-population", "class": "chart-context", "hidden": ""})
        panel.find("h2").insert_after(population)
        if name == "travel.html":
            note = soup.new_tag("p", attrs={"class": "travel-definition chart-note"})
            note.string = "Arrivals include business and family travel, not just tourism. U.S. travel to mainland China uses current air-travel estimates. Country attribution follows each source, not necessarily the last departure point."
            panel.find("h2").insert_after(note)
            note.insert_after(fragment(
                '<p class="chart-note"><a href="travel.html?indicator=visitors-from_us#regional-comparisons">'
                'Compare U.S. visits to mainland China, Hong Kong and Macau side by side</a>.</p>'))
        chart = soup.select_one("#chart")
        stats = soup.select_one("#annual-headlines").extract()
        chart.insert_after(stats)
        partial = soup.select_one("#partial-panel").extract()
        stats.insert_after(partial)
        continuity = soup.new_tag("p", attrs={"id": "series-continuity", "class": "chart-note", "hidden": ""})
        chart.insert_after(continuity)
        anchor = partial
        for identifier in ["selection-note", "related-series"]:
            note = soup.select_one("#" + identifier).extract()
            anchor.insert_after(note)
            anchor = note
        heading = soup.select_one(".chart-heading")
        heading.h3.decompose()
        heading["hidden"] = ""
        theme = soup.select_one("#chart-theme").find_parent(class_="chart-control")
        theme["hidden"] = ""
        for note in soup.select(".chart-scroll-hint"):
            note.decompose()
        for note in list(panel.select(":scope > .chart-note")):
            if (note.get("id") not in {"series-notes", "selection-note", "related-series", "series-continuity"}
                    and "travel-definition" not in note.get("class", [])):
                soup.select_one("#selected-table").append(note.extract())
        definition = soup.new_tag("details", attrs={"class": "definition-details"})
        summary = soup.new_tag("summary")
        summary.string = "Sources, definitions & limits"
        definition.append(summary)
        if name == "travel.html":
            definition.append(panel.select_one(".travel-definition").extract())
        for selector in ["#definition", "#series-source", "#series-notes"]:
            definition.append(soup.select_one(selector).extract())
        panel.append(definition)
        export = soup.new_tag("details", attrs={"class": "chart-downloads"})
        summary = soup.new_tag("summary")
        summary.string = "Download this chart"
        export.append(summary)
        export.append(soup.select_one("#figure-link").extract())
        panel.append(export)
        for section in list(main.select(":scope > .reading-note")):
            section.name = "details"
            h = section.find("h2")
            summary = soup.new_tag("summary")
            summary.string = h.text
            h.replace_with(summary)
        for section in soup.select("#downloads, #coverage, #sources, #all-values"):
            section.decompose()
        for footer in page.find_all("footer", recursive=False):
            footer.decompose()
        regional = soup.select_one("#regional-comparisons")
        charts = [section for section in regional.select(":scope > section") if section.select_one(".comparison-chart")]
        for section in list(regional.select(":scope > section")):
            if section not in charts:
                section.decompose()
        groups = {section["id"]: section.h2.text.split(" · ")[0] for section in charts}
        identifiers = {section["id"] for section in charts}
        for section in charts:
            measure, direction = section["id"].rsplit("-", 1)
            opposite = measure + "-" + ("from_us" if direction == "to_us" else "to_us")
            if opposite in identifiers:
                section.append(fragment(
                    f'<p class="chart-note"><a class="reverse-chart-link" href="{name}?indicator={opposite}#regional-comparisons">'
                    'View the reverse direction</a></p>'))
        if not charts:
            regional.decompose()
            charts = []
        preferred = {"index.html": "international_students-to_us", "travel.html": "visitors-from_us",
                     "trade.html": "goods-to_us"}[name]
        if charts:
            regional.insert(1, module_controls(soup, charts, preferred, groups))
        if name == "trade.html":
            regional.find("summary", recursive=False).decompose()
            regional.name = "div"
            secondary = soup.new_tag("details", attrs={"class": "individual-series"})
            summary = soup.new_tag("summary")
            summary.string = "Individual series & partial-year updates"
            secondary.append(summary)
            secondary.append(form.extract())
            secondary.append(panel.extract())
            main.append(secondary)
            for note in main.select(":scope > details.reading-note"):
                main.append(note.extract())
    elif name == "comparisons.html":
        for node in old_intro:
            node.decompose()
    elif name == "weibo.html":
        for node in old_intro:
            node.decompose()
    elif name == "business-presence.html":
        for node in old_intro:
            node.decompose()
    else:
        for node in old_intro:
            node.decompose()
        sections = list(main.find_all("section", recursive=False))
        charts = [n for n in sections if n.select_one(".comparison-chart")]
        for section in sections:
            if section not in charts:
                section.decompose()
        if charts:
            preferred = {"language-learning.html": "chinese-bachelors", "comparisons.html": "goods-to_us",
                         "immigration.html": "annual-china-to-us", "opinions.html": "us-china-favorability"}.get(name)
            groups = None
            if name == "immigration.html":
                groups = {section["id"]: (
                    "Where people live" if section["id"].startswith(("state-", "migrant-stock")) else
                    "Annual permanent immigration" if section["id"] == "annual-china-to-us" else
                    "Single-region reference" if section["id"] in {"hong-kong-green-cards", "macau-green-cards"} else
                    "Macau residence approvals" if section["id"] == "macau-residence-approvals" else
                    "U.S. permanent-residency grants") for section in charts}
            main.insert(0, module_controls(soup, charts, preferred, groups))
        for details in main.find_all("details", recursive=False):
            if name != "confucius.html" and not details.select_one(".comparison-chart"):
                details.decompose()
    if name == "language-learning.html":
        main.insert(1, fragment(
            '<p class="chart-note language-data-downloads">Complete language data: '
            '<a href="downloads/language-observations.csv" download>All observations (CSV)</a> · '
            '<a href="downloads/language-learning.json" download>Data, definitions &amp; sources (JSON)</a>'
            '</p>'))
    observation_path = site / "downloads/observations.json"
    observations = {(r["series_id"], r["period"]): r for r in
                    (json.loads(observation_path.read_text()) if observation_path.is_file() else [])
                    if r["frequency"] == "annual"}
    if name == "language-learning.html":
        history = soup.select_one("#college-enrollments")
        if history is not None:
            history.append(fragment('<p class="chart-note">For a newer nationwide comparison, '
                                    '<a href="language-learning.html?indicator=chinese-bachelors">see degree awards by language</a>. '
                                    'Degrees and course enrollments are separate measures.</p>'))
        group_notes = {"ap-chinese-global": "Global AP exam participation counts, not U.S.-only counts or a census of all language learners. Korean is not shown because no AP Korean exam is offered; this is not zero participation."}
        for chart_id, text in group_notes.items():
            section = soup.select_one("#" + chart_id)
            if section:
                explanation = soup.new_tag("p", attrs={"class": "ap-scope-note"})
                explanation.string = text
                section.select_one(".comparison-chart").insert_before(explanation)
                link = fragment('<p class="chart-note">No AP Korean exam is offered. '
                                '<a href="language-learning.html?indicator=chinese-bachelors">Compare Korean, Chinese and Japanese degree awards instead</a>. '
                                'Different educational populations are not combined.</p>')
                section.append(link)
    for block in soup.select(".comparison-chart"):
        image = block.find("img")
        if image is None:
            continue
        path = site / image["src"].replace(".png", ".svg")
        if not path.is_file():
            continue
        svg = fragment(path.read_text()).find("svg")
        model = plot_model(svg, labels, observations)
        if model:
            model["scale"] = "log" if "-log." in path.name else "linear"
            if name == "immigration.html":
                for group in model["groups"]:
                    for point in group["points"]:
                        if group["id"].startswith("un_stock:"):
                            point["label"] = f'{group["label"]} · 1 July {point["year"]}: {point["value"]:,.0f} estimated residents'
                        elif group["id"].startswith("ohss_"):
                            point["label"] = f'{group["label"]} · FY{point["year"]}: {point["value"]:,.0f} status grants (reported)'
        image.replace_with(fragment(str(svg)))
        if model:
            block["class"].append("native-chart")
            data = soup.new_tag("script", attrs={"type": "application/json", "class": "plot-data"})
            data.string = json_text(model).replace("<", "\\u003c")
            block.append(data)
        footnote = " ".join(n.text for n in svg.select(".figure-source"))
        if footnote:
            note = soup.new_tag("details", attrs={"class": "chart-method"})
            summary = soup.new_tag("summary")
            summary.string = "Chart notes"
            note.append(summary)
            p = soup.new_tag("p")
            p.string = footnote
            note.append(p)
            block.insert_after(note)
        parent = block.find_parent("section")
        if parent:
            subtitle = svg.find("text", attrs={"y": "77"})
            if subtitle and not parent.select_one(".chart-context"):
                context = soup.new_tag("p", attrs={"class": "chart-context"})
                context.string = subtitle.text
                parent.h2.insert_after(context)
            download_parent = block.find_parent(class_="comparison-pane")
            if download_parent is None:
                download_parent = parent
            for p in download_parent.find_all("p", recursive=False):
                if p.text.startswith("Download reported values"):
                    p.decompose()
            for ul in list(download_parent.find_all("ul", recursive=False)):
                details = soup.new_tag("details", attrs={"class": "chart-downloads"})
                summary = soup.new_tag("summary")
                summary.string = "Download PNG / SVG"
                details.append(summary)
                ul.replace_with(details)
                details.append(ul)
    for a in soup.select('a[href*=".png"],a[href*=".svg"]'):
        a["data-original-chart"] = ""
    for a in soup.select('a[href^="downloads/"],a[href^="figures/"]'):
        a["href"] += ("&" if "?" in a["href"] else "?") + "v=" + revision[:12]
    for a in soup.select('a[href^="figures/index.html"]'):
        a.find_parent("p").decompose()
    for skip in soup.select(".skip"):
        skip["href"] = "#analysis"
    masthead = fragment(
        '<header class="publication-header"><div class="edition-line" aria-hidden="true">'
        '<span>Independent notes on systems and society</span><span>Est. 2021</span></div>'
        '<div class="masthead"><a class="wordmark" href="https://www.themarginoferror.com/" aria-label="The Margin of Error, home">'
        '<span class="wordmark-the">The</span><span class="wordmark-main">Margin <i>of</i> Error</span></a>'
        '<nav aria-label="Primary navigation"><ul><li><a href="https://www.themarginoferror.com/">Latest</a></li>'
        '<li><a href="https://www.themarginoferror.com/archive/">Archive</a></li>'
        '<li><a href="https://www.themarginoferror.com/interactive-analysis/">Interactive analysis</a></li>'
        '<li><a href="https://www.themarginoferror.com/about/">About</a></li>'
        '<li><a class="subscribe-link" href="https://docs.google.com/forms/d/e/1FAIpQLSeHPhVHdJ0xdCYq3wDYjkOIxgVdErP4qszNOBQYrnyzTz3xyQ/viewform">'
        'Subscribe</a></li></ul></nav></div></header>')
    soup.body.insert(0, masthead)
    skip = soup.select_one(".skip")
    if skip is None:
        skip = soup.new_tag("a", attrs={"class": "skip", "href": "#analysis"})
        skip.string = "Skip to analysis"
    soup.body.insert(0, skip.extract())
    footer = fragment('<footer class="publication-footer"><span>The Margin of Error · Hans W. A. Hanley</span>'
                      f'<span><a href="{REPOSITORY}">Data & methods on GitHub</a></span></footer>')
    if soup.select_one(".covid-band") or (soup.select_one("#exchange-data") and name in {"index.html", "travel.html"}):
        context = covid_context_for("goods") if name == "trade.html" else COVID_CONTEXT
        sources = "".join(f'<li><a href="{item["url"]}">{item["name"]}</a></li>' for item in context["sources"])
        links = f"<ul>{sources}</ul>" if sources else ""
        summary = "COVID context on goods trade" if name == "trade.html" else "About the COVID shading"
        page.append(fragment(f'<details class="covid-context"><summary>{summary}</summary>'
                             f'<p>{context["note"]}</p>{links}</details>'))
    page.append(footer)
    script = soup.new_tag("script", attrs={"src": f"assets/publication.js?v={revision[:12]}", "defer": ""})
    soup.body.append(script)
    for node in soup.select('script[src^="assets/"],link[href^="assets/"]'):
        attribute = "src" if node.name == "script" else "href"
        if "?v=" not in node[attribute]:
            node[attribute] += "?v=" + revision[:12]
    (site / name).write_text(str(soup), encoding="utf-8")


@public_charts()
def build_publication(source, output, revision):
    prior_manifest = output / "publication-manifest.json"
    previous = json.loads(prior_manifest.read_text()).get("files", {}) if prior_manifest.is_file() else {}
    with tempfile.TemporaryDirectory(prefix="china-exchange-publication-") as work:
        root = Path(work)
        shutil.copytree(source / "data/site", root / "data/site")
        result = build(root)
        site = root / "site"
        prepare_topic_pages(site)
        definitions = {}
        for name in ["language_learning", "business_current", "business_inward", "immigration", "opinions"]:
            if not (root / f"data/site/{name}.json").is_file():
                continue
            data = json.loads((root / f"data/site/{name}.json").read_text())
            definitions.update({sid: d["label"] for sid, d in data["series"].items()})
        for name in PAGES:
            if (site / name).is_file():
                decorate(site, name, definitions, revision)
        for name in ["publication.css", "publication.js"]:
            shutil.copyfile(source / "src/us_china_exchange/static" / name, site / "assets" / name)
        (site / "figures/index.html").unlink(missing_ok=True)
        for path in list((site / "figures").rglob("*")):
            if path.is_file() and "TWN" in path.name:
                path.unlink()
        prune_unlinked_figures(site)
        (site / "downloads/covid-context.json").write_text(json_text(COVID_CONTEXT), encoding="utf-8")
        files = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in site.rglob("*") if p.is_file() and p.suffix != ".html"}
        manifest = {"version": 2, "source_repository": "hanshanley/china-us-relation-change",
                    "source_revision": revision, "canonical_url": CANONICAL,
                    "scope": "Collective exchanges, immigration, public opinion, language, business and public Weibo research aggregates; no raw posts or source reports",
                    "observations": result["observations"], "files": files, "chart_freshness": POLICY,
                    "datasets": {name: files[f"downloads/{name}.json"] for name in
                                 ["exchange", "language-learning", "business-presence", "business-current", "business-inward", "weibo-summary", "immigration",
                                  "student-estimates", "state-immigration", "confucius-programs", "opinions"]
                                 if f"downloads/{name}.json" in files}}
        (site / "publication-manifest.json").write_text(json_text(manifest), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(site, output, dirs_exist_ok=True)
        for name in previous.keys() - files.keys():
            relative = PurePosixPath(name)
            if (not relative.is_absolute() and relative.parts[0] == "figures" and ".." not in relative.parts
                    and relative.suffix in {".png", ".svg"}):
                (output / name).unlink(missing_ok=True)
        for chart_id in LANGUAGE_RETIRED_CHARTS:
            for theme in ["themarginoferror", "substack"]:
                for extension in ["png", "svg", "website.png"]:
                    (output / "figures/language_learning" / theme / f"{chart_id}.{extension}").unlink(missing_ok=True)
        for old in ["business-publication.css", "business-publication.js"]:
            (output / "assets" / old).unlink(missing_ok=True)
        if "business-inward" not in manifest["datasets"]:
            for name in ("business-inward.json", "business-inward-observations.csv", "business-inward-chart-values.csv"):
                (output / "downloads" / name).unlink(missing_ok=True)
        if "opinions" not in manifest["datasets"]:
            from us_china_exchange.opinion_analysis import CHARTS as OPINION_CHARTS

            for relative in ("opinions.html", "downloads/opinions.json", "downloads/opinion-observations.csv",
                             "downloads/opinion-chart-values.csv"):
                (output / relative).unlink(missing_ok=True)
            for chart_id in OPINION_CHARTS:
                for theme in ("themarginoferror", "substack"):
                    for extension in ("png", "svg", "website.png"):
                        (output / "figures/opinions" / theme / (chart_id + "." + extension)).unlink(missing_ok=True)
        if "state-immigration" not in manifest["datasets"]:
            for relative in ("downloads/state-immigration.json", "downloads/state-immigration.csv",
                             "downloads/us-states.geojson", "assets/state-map.js", "assets/state-map.css"):
                (output / relative).unlink(missing_ok=True)
            for theme in ["themarginoferror", "substack"]:
                for metric in ["count", "share"]:
                    for extension in ["png", "svg", "website.png"]:
                        (output / "figures/immigration" / theme / f"state-china-{metric}.{extension}").unlink(missing_ok=True)
        if "confucius-programs" not in manifest["datasets"]:
            for relative in ("confucius.html", "downloads/confucius-programs.json", "downloads/confucius-observations.csv",
                             "downloads/confucius-records.csv", "assets/confucius.js", "assets/confucius.css"):
                (output / relative).unlink(missing_ok=True)
            for chart_id in CONFUCIUS_CHARTS:
                for theme in ["themarginoferror", "substack"]:
                    for extension in ["png", "svg", "website.png"]:
                        (output / "figures/language_learning" / theme / f"{chart_id}.{extension}").unlink(missing_ok=True)
        for measure in SPLIT_REGIONAL_MEASURES:
            for direction in ["to_us", "from_us"]:
                for theme in ["themarginoferror", "substack"]:
                    for scale in ["levels", "log"]:
                        for extension in ["png", "svg", "website.png"]:
                            (output / "figures" / figure_category(measure) / "comparisons" / theme /
                             f"chn-hkg-mac-{direction}-{measure}-{scale}.{extension}").unlink(missing_ok=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    manifest = build_publication(ROOT, args.output, revision)
    print(json_text({k: v for k, v in manifest.items() if k != "files"}), end="")
