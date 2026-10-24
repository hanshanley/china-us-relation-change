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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from us_china_exchange.model import GEOGRAPHIES, json_text
from us_china_exchange.language_analysis import RETIRED_CHARTS as LANGUAGE_RETIRED_CHARTS
from us_china_exchange.render import annual_table, build, figure_links, initial_panel, svg_chart


CANONICAL = "https://www.themarginoferror.com/china-us-relations/"
REPOSITORY = "https://github.com/hanshanley/china-us-relation-change"
PAGES = {
    "index.html": ("U.S.–China connections", "Students, travel, trade and the ties between two countries.",
                   "2025 annual data · 2026 partial-year updates"),
    "travel.html": ("Travel & tourism", "Visitor trips between the U.S., mainland China, Hong Kong and Macau.",
                    "Arrivals are trips, not unique people or necessarily leisure tourists"),
    "immigration.html": ("Immigration", "Resident stocks and residence approvals, kept separate from visitor trips.",
                         "Resident stocks through 2024 · U.S. grants and Macau approvals through 2025"),
    "comparisons.html": ("China, Hong Kong & Macau", "The same measure, three separately reported geographies.",
                         "Fixed regional colours · No combined regional total"),
    "language-learning.html": ("Language learning", "Chinese, Japanese and Korean compared through course enrollments, degree awards and school programs.",
                              "AP exams through 2025 · Degree awards through 2024 · College census through 2021"),
    "business-presence.html": ("Businesses in China", "U.S. and European business presence, with different counting rules kept separate.",
                             "Annual affiliate histories · Latest available year varies by origin"),
    "weibo.html": ("U.S. media on Weibo", "Explore documented outlets, channels and the evidence connecting them.",
                   "An account inventory—not a posting-history comparison"),
}
TABS = [("index.html", "Students & trade"), ("travel.html", "Travel & tourism"), ("immigration.html", "Immigration"),
        ("comparisons.html", "Regional comparison"),
        ("language-learning.html", "Language"), ("business-presence.html", "Business"), ("weibo.html", "Weibo")]


def fragment(markup):
    return BeautifulSoup(markup, "html.parser")


def plot_model(svg, labels, observations):
    paths = svg.select("path.data-line")
    years = [int(n.text) for n in svg.select("text")
             if re.fullmatch(r"\d{4}", n.text or "") and float(n.get("y", 0)) >= 440]
    unit = svg.select_one(".axis-unit")
    if unit is None:
        unit = svg.find("text", attrs={"x": "115", "y": "125"})
    model = {"title": svg.get("aria-label", ""), "description": svg.find("desc").text if svg.find("desc") else "",
             "unit": unit.text if unit else "Count", "groups": [], "kind": "line"}
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
        model.update(first=min(all_years), last=max(years + all_years))
        return model
    bars = svg.select("rect.data-bar, rect.language-point, rect.business-point, rect.immigration-point")
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
    title, lead, scope = PAGES[name]
    if name in {"index.html", "travel.html"}:
        rows = json.loads((site / "downloads/observations.json").read_text())
        if name == "travel.html":
            rows = [r for r in rows if r["measure"] in {"visitors", "leisure_visitors"}]
        annual = max(r["year"] for r in rows if r["frequency"] == "annual" and r["value"] is not None)
        partial = max((r["year"] for r in rows if r["frequency"] == "ytd" and r["value"] is not None), default=annual)
        scope = f"{annual} annual data" + (f" · {partial} partial-year updates" if partial > annual else "")
    elif name == "language-learning.html":
        rows = json.loads((site / "downloads/language-learning.json").read_text())["observations"]
        latest = lambda prefix: max(r["year"] for r in rows if r["series_id"].startswith(prefix) and r["value"] is not None)
        scope = f"AP exams through {latest('ap:')} · Degree awards through {latest('ipeds:')} · College census through {latest('mla:')}"
    soup.title.string = title + " | The Margin of Error"
    for old in soup.select('link[rel=canonical],meta[name=description]'):
        old.decompose()
    soup.head.append(soup.new_tag("link", attrs={"rel": "canonical", "href": CANONICAL + ("" if name == "index.html" else name)}))
    soup.head.append(soup.new_tag("meta", attrs={"name": "description", "content": lead + " " + scope}))
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
    if name in {"index.html", "travel.html"}:
        initial_measure = "visitors" if name == "travel.html" else "goods"
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
            note.string = "Arrivals include business and family travel, not just tourism. U.S. travel to mainland China defaults to current air-travel estimates; historical all-mode arrivals remain separately available. Country attribution follows each source, not necessarily the last departure point."
            panel.find("h2").insert_after(note)
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
    elif name == "weibo.html":
        for node in old_intro:
            node.decompose()
    else:
        for node in old_intro:
            node.decompose()
        sections = list(main.find_all("section", recursive=False))
        charts = [n for n in sections if n.select_one(".comparison-chart")]
        if name == "business-presence.html":
            norway = next((n for n in charts if n.get("id") == "norway-affiliates-china"), None)
            if norway is not None:
                charts.remove(norway)
                sections.remove(norway)
                details = soup.new_tag("details", attrs={"class": "supplementary-origin"})
                summary = soup.new_tag("summary")
                summary.string = "Supplementary European coverage"
                details.append(summary)
                norway.replace_with(details)
                details.append(norway)
        for section in sections:
            if section not in charts:
                section.decompose()
        if charts:
            controls = soup.new_tag("div", attrs={"class": "controls module-controls", "hidden": ""})
            label = soup.new_tag("label", attrs={"for": "module-chart"})
            label.string = "Indicator"
            select = soup.new_tag("select", attrs={"id": "module-chart"})
            preferred = {"language-learning.html": "college-enrollments", "comparisons.html": "goods-to_us"}.get(name)
            for i, section in enumerate(charts):
                section["data-module-chart"] = section.get("id", f"indicator-{i}")
                option = soup.new_tag("option", attrs={"value": section["data-module-chart"]})
                option.string = section.h2.text
                if section["data-module-chart"] == preferred:
                    option["selected"] = ""
                select.append(option)
            label.append(select)
            controls.append(label)
            main.insert(0, controls)
        for details in main.find_all("details", recursive=False):
            if not details.select_one(".comparison-chart"):
                details.decompose()
    observations = {(r["series_id"], r["period"]): r for r in
                    json.loads((site / "downloads/observations.json").read_text()) if r["frequency"] == "annual"}
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
                                '<a href="language-learning.html?indicator=college-benchmarks">Compare Korean, Chinese and Japanese college enrollments instead</a>. '
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
            for p in parent.find_all("p", recursive=False):
                if p.text.startswith("Download reported values"):
                    p.decompose()
            for ul in list(parent.find_all("ul", recursive=False)):
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
    page.append(footer)
    script = soup.new_tag("script", attrs={"src": f"assets/publication.js?v={revision[:12]}", "defer": ""})
    soup.body.append(script)
    for node in soup.select('script[src^="assets/"],link[href^="assets/"]'):
        attribute = "src" if node.name == "script" else "href"
        if "?v=" not in node[attribute]:
            node[attribute] += "?v=" + revision[:12]
    (site / name).write_text(str(soup), encoding="utf-8")


def build_publication(source, output, revision):
    with tempfile.TemporaryDirectory(prefix="china-exchange-publication-") as work:
        root = Path(work)
        shutil.copytree(source / "data/site", root / "data/site")
        result = build(root)
        site = root / "site"
        shutil.copyfile(site / "index.html", site / "travel.html")
        definitions = {}
        for name in ["language_learning", "business_presence", "immigration"]:
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
        files = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in site.rglob("*") if p.is_file() and p.suffix != ".html"}
        manifest = {"version": 2, "source_repository": "hanshanley/china-us-relation-change",
                    "source_revision": revision, "canonical_url": CANONICAL,
                    "scope": "Collective exchanges, immigration, language, business and public Weibo research aggregates; no raw posts or source reports",
                    "observations": result["observations"], "files": files,
                    "datasets": {name: files[f"downloads/{name}.json"] for name in
                                 ["exchange", "language-learning", "business-presence", "weibo-summary", "immigration", "student-estimates"]
                                 if f"downloads/{name}.json" in files}}
        (site / "publication-manifest.json").write_text(json_text(manifest), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(site, output, dirs_exist_ok=True)
        for chart_id in LANGUAGE_RETIRED_CHARTS:
            for theme in ["themarginoferror", "substack"]:
                for extension in ["png", "svg", "website.png"]:
                    (output / "figures/language_learning" / theme / f"{chart_id}.{extension}").unlink(missing_ok=True)
        for old in ["business-publication.css", "business-publication.js"]:
            (output / "assets" / old).unlink(missing_ok=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    manifest = build_publication(ROOT, args.output, revision)
    print(json_text({k: v for k, v in manifest.items() if k != "files"}), end="")
