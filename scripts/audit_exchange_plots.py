#!/usr/bin/env python3
"""Reconcile every publication plot with its data, geometry and rendered labels."""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect, sync_playwright

from us_china_exchange.language_analysis import CHARTS as LANGUAGE_CHARTS
from us_china_exchange.model import GEOGRAPHIES
from us_china_exchange.theme import FLOW_COLORS


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-7)


def compact_number(text):
    match = re.fullmatch(r"\s*[$−-]?([\d,.]+)\s*(k|m|bn|tn|M|B|T)?%?\s*", text)
    if not match:
        raise ValueError(f"Not a numeric axis label: {text!r}")
    return float(match[1].replace(",", "")) * {
        None: 1, "k": 1e3, "m": 1e6, "bn": 1e9, "tn": 1e12,
        "M": 1e6, "B": 1e9, "T": 1e12}[match[2]]


LABEL_GEOMETRY = """svg => {
  const box = svg.viewBox.baseVal;
  const texts = [...svg.querySelectorAll("text")].map(n => {
    const b=n.getBBox();
    return {text:n.textContent,kind:n.getAttribute("class")||"",
      x:b.x,y:b.y,w:b.width,h:b.height,font:parseFloat(getComputedStyle(n).fontSize)};
  }).filter(b=>b.w>0&&b.h>0);
  const clipped=texts.filter(b=>b.x < box.x-1 || b.y < box.y-1 ||
    b.x+b.w>box.x+box.width+1 || b.y+b.h>box.y+box.height+1);
  const overlaps=[];
  for(let i=0;i<texts.length;i++) for(let j=i+1;j<texts.length;j++){
    const a=texts[i],b=texts[j];
    if(Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>2 &&
       Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>3) overlaps.push([a.text,b.text]);
  }
  const grids=[...svg.querySelectorAll("path")].map(n=>{
    const m=n.getAttribute("d")?.match(/^M([\\d.]+) ([\\d.]+)H([\\d.]+)$/);
    return m&&{left:+m[1],y:+m[2],right:+m[3]};
  }).filter(Boolean);
  const native=svg.classList.contains("screen-chart");
  const ticks=grids.map(g=>{
    const n=native ? [...svg.querySelectorAll(".screen-y-tick")].find(n=>Math.abs(+n.getAttribute("y")-g.y-5)<.1) :
      [...svg.querySelectorAll("text")].find(n=>n.getAttribute("text-anchor")==="end"&&Math.abs(+n.getAttribute("y")-g.y-6)<.1);
    return n&&{...g,label:n.textContent};
  }).filter(Boolean);
  return {width:box.width,height:box.height,texts,clipped,overlaps,ticks,
    unit:svg.querySelector(".screen-unit,.axis-unit")?.textContent||"",
    points:[...svg.querySelectorAll("circle:not(.plot-hover-dot)")].map(n=>({
      id:n.dataset.seriesId||"",geography:n.dataset.geography,period:n.dataset.period,
      year:n.dataset.year,date:n.dataset.date,month:n.dataset.month,
      value:n.dataset.value===undefined?null:+n.dataset.value,x:+n.getAttribute("cx"),y:+n.getAttribute("cy"),
      title:n.querySelector("title")?.textContent||""})),
    bars:[...svg.querySelectorAll(".screen-bar,rect.data-bar,rect.language-point,rect.business-point,rect.immigration-point,rect.opinion-point")].map(n=>({
      id:n.dataset.seriesId,year:n.dataset.year,label:n.dataset.label,value:+n.dataset.value,
      x:+n.getAttribute("x"),y:+n.getAttribute("y"),width:+n.getAttribute("width"),height:+n.getAttribute("height")})),
    barLabels:[...svg.querySelectorAll(".screen-bar-value")].map(n=>n.textContent),
    columns:[...svg.querySelectorAll(".annual-column,.screen-column")].map(n=>({
      id:n.dataset.seriesId,year:+n.dataset.year,value:+n.dataset.value,
      x:+n.getAttribute("x"),y:+n.getAttribute("y"),width:+n.getAttribute("width"),height:+n.getAttribute("height")})),
    snapshots:[...svg.querySelectorAll(".snapshot-bar,.screen-snapshot")].map(n=>({
      x:+n.getAttribute("x"),y:+n.getAttribute("y"),width:+n.getAttribute("width"),height:+n.getAttribute("height")})),
    years:[...svg.querySelectorAll("text")].filter(n=>n.classList.contains("screen-year")||
      (/^\\d{4}$/.test(n.textContent)&&+n.getAttribute("y")>=440&&+n.getAttribute("y")<490))
      .map(n=>({value:+n.textContent,x:+n.getAttribute("x")})),
    dates:[...svg.querySelectorAll(".screen-month,.date-tick")].map(n=>({
      label:n.textContent,period:n.dataset.period,x:+n.getAttribute("x")})),
    paths:[...svg.querySelectorAll(".screen-line")].map(n=>({id:n.dataset.seriesId||"",d:n.getAttribute("d")})),
    allPaths:[...svg.querySelectorAll(".screen-line,.screen-partial-line,.data-line")].map(n=>({
      id:n.dataset.seriesId||"",d:n.getAttribute("d"),dash:n.getAttribute("stroke-dasharray")})),
    partialPaths:[...svg.querySelectorAll(".screen-partial-line")].map(n=>n.getAttribute("d"))};
}"""


class Audit:
    def __init__(self, site, output, exclude_weibo=False):
        self.site, self.output = site, output
        self.exclude_weibo = exclude_weibo
        self.issues, self.charts, self.pictures = [], [], defaultdict(list)
        self.fonts = {}
        self.hover_checks = 0
        self.exchange = json.loads((site / "downloads/observations.json").read_text())
        payload = json.loads(BeautifulSoup((site / "index.html").read_text(), "html.parser").select_one("#exchange-data").string)
        visible = set(payload.get("visible_series", {r["series_id"] for r in self.exchange}))
        preferred = json.loads((site / "downloads/exchange.json").read_text()).get("primary_series", {})
        self.primary_exchange = [r for r in self.exchange if r["series_id"] in visible and r["series_id"] == preferred.get(
            ":".join((r["origin"], r["destination"], r["measure"])), r["series_id"])]
        self.weibo = json.loads((site / "downloads/weibo-summary.json").read_text())
        self.datasets, self.plotted = {}, {}
        for page, stem, source in [
                ("language-learning.html", "language", "language-learning"),
                ("business-presence.html", "business-current", "business-current"),
                ("business-presence.html", "business-inward", "business-inward"),
                ("business-presence.html", "business", "business-presence"),
                ("immigration.html", "immigration", "immigration"),
                ("opinions.html", "opinion", "opinions")]:
            if not (site / f"downloads/{source}.json").is_file():
                continue
            if source == "business-presence" and not (site / "downloads/business-chart-values.csv").is_file():
                continue
            data = json.loads((site / f"downloads/{source}.json").read_text())
            combined = self.datasets.setdefault(page, {"series": {}, "observations": []})
            combined["series"].update(data["series"])
            combined["observations"].extend(data["observations"])
            with (site / f"downloads/{stem}-chart-values.csv").open() as stream:
                self.plotted.setdefault(page, []).extend(csv.DictReader(stream))
        self.raw = {(r["series_id"], r["year"]): r for r in self.exchange if r["frequency"] == "annual"}
        self.cadences = {r["series_id"]: "annual" for r in self.exchange}
        for data in self.datasets.values():
            self.raw.update({(r["series_id"], r["year"]): r for r in data["observations"]})
            self.cadences.update({sid: definition["cadence"] for sid, definition in data["series"].items()})
        self.scheduled = defaultdict(list)
        for sid, year in sorted(self.raw):
            self.scheduled[sid].append(year)

    def issue(self, chart, kind, detail):
        self.issues.append({"chart": chart, "kind": kind, "detail": detail})

    def reconcile_inputs(self):
        for page, rows in self.plotted.items():
            data = self.datasets[page]
            raw = {(r["series_id"], r.get("survey_id") or r["year"]): r for r in data["observations"]}
            for row in rows:
                original = raw[(row["series_id"], row.get("survey_id") or int(row["year"]))]
                expected = original["value"]
                if not close(row["value"], expected):
                    self.issue(page, "reported_value", row)
                if page == "language-learning.html":
                    config = LANGUAGE_CHARTS[row["chart_id"]]
                    if config["mode"] == "index":
                        expected = expected / raw[(row["series_id"], config["baseline"])]["value"] * 100
                    elif config["mode"] == "share":
                        expected = expected / raw[(config["denominator"], int(row["year"]))]["value"] * 100
                if not close(row["plotted_value"], expected):
                    self.issue(page, "transformed_value", row)
        if self.exclude_weibo:
            return
        daily = {date.fromisoformat(r["date"]): r for r in self.weibo.get("daily", [])}
        outlets = {r["account_id"]: r["outlet_id"] for r in self.weibo["accounts"]}
        for row in self.weibo.get("rolling_30d", []):
            day = date.fromisoformat(row["date"])
            window = [daily.get(day - timedelta(days=i)) for i in range(30)]
            complete = all(r is not None and not r["partial_day"] for r in window)
            if complete:
                members = set().union(*(set(r["account_ids"]) for r in window))
                posts = sum(r["recovered_posts"] for r in window)
                expected = [posts, len(members), len({outlets[a] for a in members}), posts / 30]
            else:
                expected = [None] * 4
            actual = [row[k] for k in ("recovered_posts", "observed_accounts", "observed_outlets", "posts_per_day")]
            if actual != expected or row["partial_window"] == complete:
                self.issue("weibo:rolling", "window_calculation", row["date"])

    def expected_groups(self, page, chart, model):
        if page == "comparisons.html" or (page in {"index.html", "travel.html", "trade.html"} and model.get("geographies")):
            result = {}
            measure, direction = chart.rsplit("-", 1)
            for geo in model.get("geographies", ("CHN", "HKG", "MAC")):
                origin, destination = (geo, "USA") if direction == "to_us" else ("USA", geo)
                rows = sorted((r for r in self.primary_exchange if
                               (r["origin"], r["destination"], r["measure"], r["frequency"]) ==
                               (origin, destination, measure, "annual") and r["value"] is not None),
                              key=lambda r: r["year"])
                if rows:
                    result[rows[0]["series_id"]] = [r for r in rows if model["scale"] != "log" or r["value"] > 0]
            return result
        if page in self.plotted:
            groups = defaultdict(list)
            for row in self.plotted[page]:
                if row["chart_id"] == chart:
                    if model.get("geographies") and not any(
                            g in row["series_id"].split(":") for g in model["geographies"]):
                        continue
                    groups[row["series_id"]].append(dict(
                        year=int(row["year"]), value=float(row["plotted_value"]), label=row["label"],
                        comparability=row["comparability"]))
            return groups
        if page == "weibo.html" and model["kind"] == "line":
            field = {"monthly-posts": "recovered_posts", "monthly-accounts": "observed_accounts",
                     "rolling30-posts": "recovered_posts", "rolling30-average": "posts_per_day",
                     "rolling30-accounts": "observed_accounts", "rolling30-outlets": "observed_outlets"}[chart]
            source = self.weibo["monthly"] if model["frequency"] == "monthly" else [
                r for r in self.weibo["rolling_30d"] if not r["partial_window"]]
            period = "month" if model["frequency"] == "monthly" else "date"
            return {chart: [dict(r, value=r[field], period=r[period]) for r in source]}
        return {}

    def model_values(self, key, page, chart, model):
        expected = self.expected_groups(page, chart, model)
        if page in self.plotted:
            units = {r["plotted_unit"] for r in self.plotted[page] if r["chart_id"] == chart}
            if units != {model["unit"]}:
                self.issue(key, "wrong_counting_unit", {"actual": model["unit"], "expected": list(units)})
        if model["kind"] == "line":
            if page == "comparisons.html" or (page in {"index.html", "travel.html", "trade.html"} and model.get("geographies")):
                for group in model["groups"]:
                    _, origin, destination, _ = group["id"].split(":")
                    partner = destination if origin == "USA" else origin
                    direction = "from_us" if origin == "USA" else "to_us"
                    if group["color"].lower() != FLOW_COLORS[direction][partner].lower() or group["label"] != GEOGRAPHIES[partner]:
                        self.issue(key, "wrong_geography_legend", group["id"])
            actual = {g["id"]: g["points"] for g in model["groups"]}
            if set(actual) != {sid for sid, rows in expected.items() if rows}:
                self.issue(key, "series_identity", {"actual": list(actual), "expected": list(expected)})
            for sid, rows in expected.items():
                points = actual.get(sid, [])
                if len(points) != len(rows) or any(
                        not close(a["value"], e["value"]) or
                        (a.get("year") != e.get("year") if "year" in e else
                         a.get("date", a.get("month")) != e["period"])
                        for a, e in zip(points, rows)):
                    self.issue(key, "source_points", sid)
                for i, point in enumerate(points):
                    should_connect = bool(i and self.connected(sid, points[i - 1], point, model.get("frequency")))
                    if not model.get("columns") and point["connect"] != should_connect:
                        self.issue(key, "wrong_source_connection", {"series": sid, "point": point})
        elif page in self.plotted:
            rows = [r for r in self.plotted[page] if r["chart_id"] == chart]
            bars = model["bars"]
            if len(bars) != len(rows) or any(not close(a["value"], e["plotted_value"]) for a, e in zip(bars, rows)):
                self.issue(key, "source_bars", chart)
            for bar, row in zip(bars, rows):
                labels = {row["label"], self.datasets[page]["series"][row["series_id"]]["label"]}
                labels |= {f'{label} ({row["year"]})' for label in labels}
                if bar["label"] not in labels or row["year"] not in bar["label"]:
                    self.issue(key, "bar_identity_or_year", {"bar": bar, "source": row["series_id"], "year": row["year"]})
        elif page == "weibo.html":
            accounts = self.weibo["accounts"]
            if chart == "identity-evidence":
                c = Counter(a["existence"] for a in accounts)
                values = [c["current_evidence"], c["historical"], c["unknown"]]
            elif chart == "recovery-coverage":
                recovered = sum(a["recovered_posts"] > 0 for a in accounts)
                unattempted = sum(a["recovered_posts"] == 0 and a["latest_run_status"] is None for a in accounts)
                values = [recovered, len(accounts) - recovered - unattempted, unattempted]
            elif chart == "text-completeness":
                values = [r["recovered_posts"] for r in self.weibo["text_completeness"]]
            else:
                values = [r["recovered_posts"] for r in self.weibo["yearly"]]
            if [b["value"] for b in model["bars"]] != values:
                self.issue(key, "source_bars", {"actual": [b["value"] for b in model["bars"]], "expected": values})

    def geometry(self, key, geometry, model=None):
        if geometry["clipped"]:
            self.issue(key, "clipped_labels", geometry["clipped"])
        if geometry["overlaps"]:
            self.issue(key, "overlapping_labels", geometry["overlaps"])
        years = sorted((t for t in geometry.get("texts", []) if t["kind"] == "screen-year"), key=lambda t: t["x"])
        crowded = [[a["text"], b["text"]] for a, b in zip(years, years[1:]) if b["x"] - a["x"] - a["w"] < 7.9]
        if crowded:
            self.issue(key, "crowded_year_labels", crowded)
        outside = [p for p in geometry["points"] if
                   p["x"] < -.02 or p["x"] > geometry.get("width", math.inf) + .02 or
                   p["y"] < -.02 or p["y"] > geometry.get("height", math.inf) + .02]
        if outside:
            self.issue(key, "points_outside_canvas", outside[:3])
        outside_bars = [b for b in geometry["bars"] if b["x"] < -.02 or b["width"] < 0 or
                        b["x"] + b["width"] > geometry.get("width", math.inf) + .02]
        if outside_bars:
            self.issue(key, "bars_outside_canvas", outside_bars[:3])
        ticks = geometry["ticks"]
        if len(ticks) >= 2:
            divisor = next((scale for word, scale in [
                ("trillions", 1e12), ("billions", 1e9), ("millions", 1e6), ("thousands", 1e3)]
                if word in geometry["unit"].lower()), 1)
            values = [compact_number(t["label"]) * divisor for t in ticks]
            logarithmic = model and model.get("scale") == "log"
            transform = math.log10 if logarithmic else float
            if len(set(values)) != len(values) or values != sorted(values):
                self.issue(key, "invalid_axis_labels", values)
                return
            low, high = transform(values[0]), transform(values[-1])
            y0, y1 = ticks[0]["y"], ticks[-1]["y"]
            errors = []
            for tick, value in zip(ticks, values):
                expected = y0 + (transform(value) - low) / (high - low) * (y1 - y0)
                if abs(expected - tick["y"]) > .1:
                    errors.append({"label": tick["label"], "pixel_error": tick["y"] - expected})
            if errors:
                self.issue(key, "axis_labels_do_not_match_scale", errors[:5])
            elif model and model["kind"] == "line":
                actual = geometry["points"]
                expected = [p for g in model["groups"] for p in g["points"]]
                if len(actual) != len(expected):
                    self.issue(key, "rendered_point_count", [len(actual), len(expected)])
                errors = []
                for a, e in zip(actual, expected):
                    yy = y0 + (transform(e["value"]) - low) / (high - low) * (y1 - y0)
                    if not close(a["value"], e["value"]) or abs(a["y"] - yy) > .15:
                        errors.append({"point": e, "actual_y": a["y"], "expected_y": yy})
                if errors:
                    self.issue(key, "misplaced_y_coordinate", errors[:3])
                for bar, point in zip(geometry["snapshots"], actual):
                    if (abs(bar["x"] + bar["width"] / 2 - point["x"]) > .1
                            or abs(bar["y"] - point["y"]) > .1
                            or abs(bar["height"] - (y0 - point["y"])) > .1):
                        self.issue(key, "misplaced_snapshot", bar)
                if model.get("columns"):
                    columns = geometry["columns"]
                    if len(columns) != len(actual):
                        self.issue(key, "annual_column_count", [len(columns), len(actual)])
                    for bar, point in zip(columns, actual):
                        if (bar["year"] != int(point["year"]) or not close(bar["value"], point["value"])
                                or bar["width"] <= 0 or bar["height"] < 0
                                or abs(bar["x"] + bar["width"] / 2 - point["x"]) > .1
                                or abs(bar["y"] - point["y"]) > .1
                                or abs(bar["height"] - (y0 - point["y"])) > .1):
                            self.issue(key, "misplaced_annual_column", bar)
                    if any(a["x"] + a["width"] > b["x"] + .1 for a, b in zip(columns, columns[1:])):
                        self.issue(key, "overlapping_annual_columns", key)
        if model and model["kind"] == "line" and model.get("frequency") not in {"daily", "monthly"}:
            years = geometry["years"]
            if len(years) >= 2:
                first, last = years[0], years[-1]
                errors = []
                for point in geometry["points"]:
                    expected = first["x"] + (int(point["year"]) - first["value"]) / (
                        last["value"] - first["value"]) * (last["x"] - first["x"])
                    if abs(point["x"] - expected) > .1:
                        errors.append(point)
                if errors:
                    self.issue(key, "misplaced_calendar_year", errors[:3])
        if model and model.get("frequency") in {"daily", "monthly"}:
            daily = model["frequency"] == "daily"
            ticks = geometry["dates"]
            if len(ticks) >= 2:
                def calendar_index(value):
                    return date.fromisoformat(value).toordinal() if daily else int(value[:4]) * 12 + int(value[5:]) - 1

                def parsed_label(tick, endpoint):
                    label = tick["label"].rstrip("*")
                    patterns = (["%b %d, %Y", "%d %b %Y"] if daily and endpoint else
                                ["%Y", "%b %Y", "%b %d, %Y", "%d %b %Y"])
                    for pattern in patterns:
                        try:
                            parsed = datetime.strptime(label, pattern)
                            return parsed.date().toordinal() if daily else parsed.year * 12 + parsed.month - 1
                        except ValueError:
                            pass
                    return None

                endpoints = [(tick, parsed_label(tick, True)) for tick in (ticks[0], ticks[-1])]
                if any(value is None for _, value in endpoints):
                    self.issue(key, "ambiguous_daily_endpoint", [tick["label"] for tick, _ in endpoints])
                else:
                    first, low = endpoints[0]
                    last, high = endpoints[1]
                    if high != low:
                        errors = []
                        for point in geometry["points"]:
                            period = point.get("date" if daily else "month")
                            expected = first["x"] + (calendar_index(period) - low) / (high - low) * (last["x"] - first["x"])
                            if abs(point["x"] - expected) > .1:
                                errors.append({"period": period, "actual_x": point["x"], "expected_x": expected})
                        if errors:
                            self.issue(key, "misplaced_calendar_date", errors[:3])
        if model and model["kind"] == "bars" and geometry["bars"] and not geometry["ticks"]:
            nonzero = [b for b in geometry["bars"] if b["value"]]
            reference = max(nonzero, key=lambda b: b["value"]) if nonzero else None
            if reference:
                errors = [b for b in nonzero if abs(b["width"] - reference["width"] * b["value"] / reference["value"]) > .02]
                if errors:
                    self.issue(key, "inconsistent_bar_scale", errors)
            if geometry["barLabels"] and any(
                    not close(compact_number(label), bar["value"]) for label, bar in zip(geometry["barLabels"], geometry["bars"])):
                self.issue(key, "rounded_bar_value", geometry["barLabels"])
        if model and model["kind"] == "line" and geometry["paths"]:
            for group, path in zip(model["groups"], geometry["paths"]):
                if all("connect" in p for p in group["points"]):
                    expected = ["L" if p["connect"] and not (
                        model.get("frequency") in {"daily", "monthly"} and i and
                        (p.get("partial_window") or group["points"][i - 1].get("partial_window"))) else "M"
                        for i, p in enumerate(group["points"])]
                    if re.findall("[ML]", path["d"]) != expected:
                        self.issue(key, "incorrect_line_connections", group.get("id"))
        if model and model["kind"] == "line":
            self.line_geometry(key, geometry, model)

    def connected(self, sid, before, after, frequency=None):
        if frequency in {"daily", "monthly"}:
            def index(row):
                value = row.get("date", row.get("month", row.get("period")))
                return date.fromisoformat(value).toordinal() if frequency == "daily" else int(value[:4]) * 12 + int(value[5:]) - 1
            return index(after) == index(before) + 1
        previous, current = int(before["year"]), int(after["year"])
        a, b = self.raw[(sid, previous)], self.raw[(sid, current)]
        if a["comparability"] != b["comparability"]:
            return False
        return current == previous + 1 if self.cadences[sid] == "annual" else (
            self.scheduled[sid].index(current) == self.scheduled[sid].index(previous) + 1)

    def line_geometry(self, key, geometry, model):
        expected = [dict(point, _sid=group.get("id", "")) for group in model["groups"] for point in group["points"]]
        lookup = defaultdict(list)
        for i, point in enumerate(geometry["points"]):
            lookup[(round(point["x"], 2), round(point["y"], 2))].append(i)
        for path in geometry["allPaths"]:
            previous = None
            for command, x, y in re.findall(r"([ML])\s*(-?[\d.]+)[ ,]+(-?[\d.]+)", path["d"]):
                x, y = float(x), float(y)
                candidates = [i for dx in (-.01, 0, .01) for dy in (-.01, 0, .01)
                              for i in lookup.get((round(x + dx, 2), round(y + dy, 2)), [])
                              if i < len(expected) and (not path["id"] or expected[i]["_sid"] == path["id"])
                              and abs(geometry["points"][i]["x"] - x) < .02
                              and abs(geometry["points"][i]["y"] - y) < .02]
                if not candidates:
                    self.issue(key, "stray_line_vertex", [x, y])
                    break
                point = expected[candidates[0]]
                if command == "L" and previous is not None:
                    if point["_sid"] != previous["_sid"] or not self.connected(
                            point["_sid"], previous, point, model.get("frequency")):
                        self.issue(key, "line_crosses_missingness_or_definition", [previous, point])
                    if (model.get("frequency") == "monthly" and
                            (previous.get("partial_window") or point.get("partial_window")) and not path["dash"]):
                        self.issue(key, "unmarked_partial_period", point)
                previous = point

    def remember(self, key, geometry, screenshot=None):
        self.charts.append({"chart": key, "points": len(geometry["points"]),
                            "bars": len(geometry["bars"]), "width": geometry["width"], "height": geometry["height"]})
        if screenshot:
            self.pictures[key.split(":")[0]].append((key, screenshot))

    def hover(self, key, page, container, model):
        bars = model["kind"] == "bars"
        field = "date" if model.get("frequency") == "daily" else "month" if model.get("frequency") == "monthly" else "year"
        periods = list(range(len(model["bars"]))) if bars else sorted({
            p[field] for group in model["groups"] for p in group["points"]})
        svg = container.locator(".screen-chart")
        container.scroll_into_view_if_needed()
        for index in sorted({0, len(periods) // 2, len(periods) - 1}):
            period = periods[index]
            expected = ([{"id": model["bars"][period]["id"], "point": model["bars"][period]}] if bars else [
                {"id": group["id"], "point": next((p for p in group["points"] if p[field] == period), None)}
                for group in model["groups"]])
            point = container.locator(".screen-bar").nth(period) if bars else container.locator(
                f'.screen-point[data-{field}="{period}"]').first
            box, plot = point.bounding_box(), svg.bounding_box()
            page.mouse.move(plot["x"] + plot["width"] / 2 if bars else box["x"] + box["width"] / 2,
                            box["y"] + box["height"] / 2 if bars else plot["y"] + 55)
            tip = page.locator("#" + container.get_attribute("data-tooltip-id"))
            expect(tip).to_be_visible()
            actual = tip.locator(".plot-tooltip-row").evaluate_all("""nodes=>nodes.map(n=>({
              id:n.dataset.seriesId, value:n.querySelector(".plot-tooltip-value")?.dataset.value,
              text:n.querySelector(".plot-tooltip-value")?.textContent,
              reported:n.querySelector(".plot-tooltip-reported")?.dataset.value,
              reportedText:n.querySelector(".plot-tooltip-reported")?.textContent,
              missing:!!n.querySelector(".plot-tooltip-missing")}))""")
            if len(actual) != len(expected):
                self.issue(key, "tooltip_series_count", [len(actual), len(expected)])
            for a, e in zip(actual, expected):
                p = e["point"]
                if a["id"] != e["id"] or (p is None and (not a["missing"] or a.get("value") is not None)) or (
                        p is not None and (a["missing"] or a.get("value") is None or not close(a["value"], p["value"]))):
                    self.issue(key, "tooltip_source_value", {"actual": a, "expected": e})
                if p is not None and (a.get("text") is None or abs(compact_number(a["text"]) - p["value"]) > .00501):
                    self.issue(key, "tooltip_visible_value", {"actual": a, "expected": e})
                if a.get("reported") is not None and not close(a["reported"], p["reported_value"]):
                    self.issue(key, "tooltip_reported_value", {"actual": a, "expected": p})
                if a.get("reportedText") is not None:
                    visible = re.match(r"Reported:\s*([$]?[\d,.]+%?)", a["reportedText"])
                    if not visible or abs(compact_number(visible[1]) - p["reported_value"]) > .00501:
                        self.issue(key, "tooltip_visible_reported_value", {"actual": a, "expected": p})
                if p is not None and "reported_value" in p and p["reported_value"] != p["value"] and a.get("reported") is None:
                    self.issue(key, "tooltip_missing_reported_value", p)
            p = next(e["point"] for e in expected if e["point"] is not None)
            label = p.get("period")
            if not label and model.get("frequency") in {"daily", "monthly"}:
                d = date.fromisoformat(p["date"] if field == "date" else p["month"] + "-01")
                label = f"{d:%b} {d.day}, {d.year}" if field == "date" else f"{d:%b} {d.year}"
            label = label or str(p.get("year") or p.get("label", ""))
            if label not in tip.locator(".plot-tooltip-period").inner_text():
                self.issue(key, "tooltip_wrong_period", label)
            bounds = tip.bounding_box()
            if (bounds["x"] < 0 or bounds["y"] < 0 or bounds["x"] + bounds["width"] > page.viewport_size["width"] + 1
                    or bounds["y"] + bounds["height"] > page.viewport_size["height"] + 1):
                self.issue(key, "tooltip_clipping", bounds)
            if not bars:
                markers = svg.locator(".plot-hover-dot").evaluate_all("""nodes=>nodes.map(n=>({
                  id:n.dataset.seriesId,x:+n.getAttribute("cx"),y:+n.getAttribute("cy")}))""")
                source = svg.locator(f'.screen-point[data-{field}="{period}"]').evaluate_all("""nodes=>nodes.map(n=>({
                  id:n.dataset.seriesId,x:+n.getAttribute("cx"),y:+n.getAttribute("cy")}))""")
                if markers != source:
                    self.issue(key, "tooltip_misplaced_markers", [markers, source])
            self.hover_checks += 1
        svg.focus()
        svg.press("Home")
        tip = page.locator("#" + container.get_attribute("data-tooltip-id"))
        expect(tip).to_be_visible()
        if len(periods) > 1:
            for _ in range(periods[1] - periods[0] if model.get("annual") else 1):
                svg.press("ArrowRight")
            second = model["bars"][1] if bars else next(
                p for g in model["groups"] for p in g["points"] if p[field] == periods[1])
            if not close(tip.locator(".plot-tooltip-value").first.get_attribute("data-value"), second["value"]):
                self.issue(key, "keyboard_wrong_step", second)
        svg.press("End")
        if model.get("annual") and model["last"] > periods[-1]:
            expect(tip.locator(".plot-tooltip-missing")).to_have_count(len(model["groups"]))
            for _ in range(model["last"] - periods[-1]):
                svg.press("ArrowLeft")
        last_point = model["bars"][-1] if bars else next(
            p for g in model["groups"] for p in g["points"] if p[field] == periods[-1])
        last_value = tip.locator(".plot-tooltip-value").first.get_attribute("data-value")
        if not close(last_value, last_point["value"]):
            self.issue(key, "keyboard_wrong_value", [last_value, last_point])
        svg.press("Escape")
        expect(tip).to_be_hidden()
        svg.evaluate("node=>node.blur()")
        page.mouse.move(0, 0)

    def native(self, browser, width, screenshots, url):
        page = browser.new_page(viewport={"width": width, "height": 1000})
        program_pages = ["confucius.html"] if (self.site / "confucius.html").is_file() else []
        for filename in ["index.html", "travel.html", "trade.html", *self.datasets, "weibo.html", *program_pages]:
            if self.exclude_weibo and filename == "weibo.html":
                continue
            soup = BeautifulSoup((self.site / filename).read_text(), "html.parser")
            scripts = soup.select(".native-chart script.plot-data")
            page.goto(url + filename)
            page.evaluate("document.fonts.ready")
            page.mouse.move(0, 0)
            if filename == "confucius.html":
                from check_confucius_publication import check_page

                program_data = json.loads((self.site / "downloads/confucius-programs.json").read_text())
                try:
                    check_page(page, program_data)
                except AssertionError as exc:
                    self.issue(f"confucius:{width}", "program_count_interaction", str(exc))
                self.charts.append({"chart": f"confucius:{width}", "observations": len(program_data["observations"])})
                continue
            if filename == "immigration.html" and (self.site / "downloads/state-immigration.json").is_file():
                from check_state_immigration_map import check_page

                try:
                    check_page(page, json.loads((self.site / "downloads/state-immigration.json").read_text()))
                except AssertionError as exc:
                    self.issue(f"state-map:{width}", "state_map_interaction", str(exc))
                self.charts.append({"chart": f"state-map:{width}", "states": 51})
            if filename == "weibo.html":
                from check_weibo_publication import check_page

                expected = {a["account_id"] for a in self.weibo["accounts"]}
                actual = page.locator(".weibo-dot").evaluate_all("nodes=>nodes.map(n=>n.dataset.accountId)")
                if len(actual) != len(expected) or set(actual) != expected:
                    self.issue(f"weibo:account-map:{width}", "account_identity_mismatch", actual)
                if page.locator(".native-chart,#monthly-posts,#publication-years,#rolling30-posts").count():
                    self.issue(f"weibo:account-map:{width}", "recovery_timeline_in_primary_view", None)
                if page.evaluate("document.documentElement.scrollWidth>innerWidth"):
                    self.issue(f"weibo:account-map:{width}", "page_overflow", width)
                try:
                    check_page(page, self.weibo)
                except AssertionError as exc:
                    self.issue(f"weibo:directory:{width}", "account_or_coverage_interaction", str(exc))
                panel = page.locator("#weibo-directory")
                bounds = panel.bounding_box()
                self.charts.append({"chart": f"weibo:directory:{width}", "points": len(expected),
                                    "bars": page.locator(".coverage-segment,.recovery-segment").count(),
                                    "width": bounds["width"], "height": bounds["height"]})
                if screenshots:
                    picture = self.output / "screens" / f"weibo-directory-{width}.png"
                    panel.screenshot(path=str(picture))
                    self.pictures[filename].append((f"weibo:directory:{width}", picture))
                continue
            for index, script in enumerate(scripts):
                model = json.loads(script.string)
                section = script.find_parent("section")
                chart = section["id"]
                scale = model.get("scale", "linear")
                panel = "-".join(model.get("geographies", []))
                key = f"{filename}:{chart}:{scale}:{panel}:{width}"
                self.model_values(key, filename, chart, model)
                container = page.locator(".native-chart").nth(index)
                identifier = container.evaluate("""e=>{
                  const section=e.closest("[data-module-chart]");
                  for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==="DETAILS")p.open=true;
                  return section?.dataset.moduleChart;
                }""")
                if identifier:
                    page.select_option("#module-chart", identifier)
                expect(container.locator(".screen-chart")).to_be_visible()
                geometry = container.locator(".screen-chart").evaluate(LABEL_GEOMETRY)
                self.geometry(key, geometry, model)
                self.hover(key, page, container, model)
                if page.evaluate("document.documentElement.scrollWidth>innerWidth"):
                    self.issue(key, "page_overflow", width)
                screenshot = None
                if screenshots:
                    screenshot = self.output / "screens" / f"{filename[:-5]}-{chart}-{scale}-{panel}-{width}.png"
                    container.screenshot(path=str(screenshot))
                self.remember(key, geometry, screenshot)
        page.goto(url + "index.html")
        data = json.loads(BeautifulSoup((self.site / "index.html").read_text(), "html.parser").select_one("#exchange-data").string)
        groups = defaultdict(list)
        for row in self.primary_exchange:
            if row["frequency"] == "annual" and row["value"] is not None and "TWN" not in (row["origin"], row["destination"]):
                groups[row["series_id"]].append(row)
        for sid, rows in groups.items():
            rows.sort(key=lambda r: r["year"])
            sample = rows[0]
            geo = sample["destination"] if sample["origin"] == "USA" else sample["origin"]
            target = ("trade.html" if sample["measure"] in {"goods", "services"} else
                      "travel.html" if "visitors" in sample["measure"] else "index.html")
            if not page.url.split("?")[0].endswith("/" + target):
                page.goto(url + target)
            if target == "trade.html":
                page.locator(".individual-series").evaluate("node=>node.open=true")
            page.select_option("#geography", geo)
            page.select_option("#direction", "from_us" if sample["origin"] == "USA" else "to_us")
            page.select_option("#measure", sample["measure"])
            for mode in ("levels", "index"):
                if mode == "index" and not data["charts"][sid]["index"].startswith("<svg"):
                    continue
                page.select_option("#chart-mode", mode)
                ref = next((r for r in rows if r["year"] == 2019), None)
                points = [dict(year=r["year"], period=r["period"], reported_value=r["value"],
                               value=r["value"] if mode == "levels" else r["value"] / ref["value"] * 100)
                          for r in rows]
                snapshots = len(rows) == 1 or (len(rows) == 2 and sample["source_id"] == "ustr"
                    and len({r["comparability"] for r in rows}) == 2)
                all_rows = [r for r in self.primary_exchange if r["series_id"] == sid and r["frequency"] == "annual"]
                model = {"kind": "line", "columns": mode == "levels" and not snapshots, "annual": True,
                         "last": max(r["year"] for r in all_rows),
                         "groups": [{"id": sid, "points": points}]}
                key = f"exchange:{sid}:{mode}:{width}"
                geometry = page.locator("#chart .screen-chart").evaluate(LABEL_GEOMETRY)
                actual = [(p["year"], p["value"]) for p in geometry["points"]]
                if len(actual) != len(points) or any(
                        int(a[0]) != e["year"] or not close(a[1], e["value"]) for a, e in zip(actual, points)):
                    self.issue(key, "source_points", actual[:3])
                self.geometry(key, geometry, model)
                self.hover(key, page, page.locator("#chart"), model)
                screenshot = None
                if screenshots:
                    screenshot = self.output / "screens" / f"{sid.replace(':','-')}-{mode}-{width}.png"
                    page.locator("#chart").screenshot(path=str(screenshot))
                self.remember(key, geometry, screenshot)
        page.close()

    def exports(self, browser, root):
        page = browser.new_page()
        for path in sorted(root.rglob("*.svg")):
            if self.exclude_weibo and path.relative_to(root).parts[0] == "weibo":
                continue
            key = "export:" + str(path.relative_to(root))
            page.goto(path.resolve().as_uri())
            soup = BeautifulSoup(path.read_text(), "html.parser")
            if soup.svg.get("data-confucius-chart"):
                from check_confucius_publication import check_export

                try:
                    check_export(path, json.loads((self.site / "downloads/confucius-programs.json").read_text()))
                except AssertionError as exc:
                    self.issue(key, "program_count_export", str(exc))
                self.charts.append({"chart": key, "observations": len(soup.select(".confucius-mark"))})
                continue
            if soup.svg.get("data-state-map"):
                from check_state_immigration_map import check_export

                try:
                    check_export(path, json.loads((self.site / "downloads/state-immigration.json").read_text()))
                except AssertionError as exc:
                    self.issue(key, "state_map_export", str(exc))
                self.charts.append({"chart": key, "states": 51})
                continue
            geometry = page.locator("svg").evaluate(LABEL_GEOMETRY)
            logarithmic = "log scale" in geometry["unit"]
            model = self.export_model(path.relative_to(root), soup, geometry, logarithmic)
            self.geometry(key, geometry, model)
            self.export_font_layout(key, soup)
            self.remember(key, geometry)
        page.close()

    def export_model(self, path, soup, geometry, logarithmic):
        family, chart = path.parts[0], path.stem
        model = {"kind": "line" if geometry["points"] else "bars", "scale": "log" if logarithmic else "linear",
                 "columns": soup.svg.get("data-plot-style") == "columns"}
        if family in {"students", "visitors", "goods_trade", "services_trade"}:
            if "comparisons" in path.parts:
                match = re.fullmatch(r"(chn-hkg-mac|chn|hkg-mac)-(to_us|from_us)-(.+)-(levels|log)", chart)
                if match is None:
                    raise ValueError("Unknown regional comparison export identity: " + chart)
                model["geographies"] = soup.svg.get("data-geographies", "CHN HKG MAC").split()
                expected = self.expected_groups("comparisons.html", f"{match[3]}-{match[2]}", model)
            else:
                sid = next(r["series_id"] for r in self.exchange if r["series_id"].replace(":", "-") == chart)
                expected = {sid: sorted((r for r in self.exchange if r["series_id"] == sid
                                        and r["frequency"] == "annual" and r["value"] is not None), key=lambda r: r["year"])}
        elif family in {"language_learning", "business_presence", "immigration", "opinions"}:
            page = {"language_learning": "language-learning.html", "business_presence": "business-presence.html",
                    "immigration": "immigration.html", "opinions": "opinions.html"}[family]
            if soup.svg.get("data-geographies"):
                model["geographies"] = soup.svg["data-geographies"].split()
                chart = re.sub(r"-(?:chn|hkg-mac)$", "", chart)
            expected = self.expected_groups(page, chart, model)
        else:
            if geometry["points"]:
                model["frequency"] = "daily" if chart.startswith("rolling30-") else "monthly"
                expected = self.expected_groups("weibo.html", chart, model)
            else:
                model["bars"] = geometry["bars"]
                self.model_values(str(path), "weibo.html", chart, model)
                return model
        flattened = [dict(row, id=sid) for sid, rows in expected.items() for row in rows]
        actual = geometry["points"] if geometry["points"] else geometry["bars"]
        if len(actual) != len(flattened):
            self.issue(str(path), "export_point_count", [len(actual), len(flattened)])
        normalized = []
        for point, row in zip(actual, flattened):
            if point.get("value") is None:
                match = re.search(r":\s*\$?([\d,.]+)", point["title"])
                point["value"] = float(match[1].replace(",", "")) if match else None
            if point.get("year") is None and "year" in row:
                period = point.get("period")
                if period:
                    point["year"] = int(period[:4]) + int("/" in period)
                else:
                    match = re.search(r"(\d{4})(/\d{2})?:", point.get("title", ""))
                    point["year"] = int(match[1]) + bool(match[2]) if match else None
            if (point.get("value") is None or not close(point["value"], row["value"])
                    or ("year" in row and int(point.get("year") or 0) != row["year"])
                    or (point.get("id") and point["id"] != row["id"])
                    or (point.get("geography") and point["geography"] not in row["id"].split(":")[1:3])):
                self.issue(str(path), "export_source_identity", {"actual": point, "expected": row})
            normalized.append(dict(row))
        model["groups"] = [{"id": sid, "points": [r for r in normalized if r["id"] == sid]} for sid in expected]
        if not geometry["points"] and geometry["ticks"]:
            ticks = geometry["ticks"]
            values = [compact_number(t["label"]) for t in ticks]
            low_y, high_y = ticks[0]["y"], ticks[-1]["y"]
            for bar in geometry["bars"]:
                expected_y = low_y + (bar["value"] - values[0]) / (values[-1] - values[0]) * (high_y - low_y)
                if abs(bar["y"] - expected_y) > .1 or abs(bar["height"] - (low_y - expected_y)) > .1:
                    self.issue(str(path), "misplaced_export_bar", bar)
        return model

    def export_font_layout(self, key, soup):
        texts = []
        for node in soup.select("text"):
            attrs = {}
            for parent in [*reversed(list(node.parents)), node]:
                if hasattr(parent, "attrs"):
                    attrs.update(parent.attrs)
            size = int(float(attrs.get("font-size", 20)))
            style = "Bold" if attrs.get("font-weight") == "bold" else "Italic" if attrs.get("font-style") == "italic" else ""
            identity = size, style
            if identity not in self.fonts:
                filename = "DejaVuSerif" + ("-" + style if style else "") + ".ttf"
                self.fonts[identity] = ImageFont.truetype(str(ROOT / "src/us_china_exchange/static/fonts" / filename), size)
            font = self.fonts[identity]
            text = node.get_text()
            width = font.getlength(text)
            x, y = float(node.get("x", 0)), float(node.get("y", 0))
            anchor = node.get("text-anchor")
            left = x - (width if anchor == "end" else width / 2 if anchor == "middle" else 0)
            bounds = font.getbbox(text, anchor="ls")
            texts.append({"text": text, "x": left + bounds[0], "y": y + bounds[1],
                          "right": left + bounds[2], "bottom": y + bounds[3]})
        left, top, width, height = map(float, soup.svg.get("viewbox", "0 0 1000 600").split())
        clipped = [t for t in texts if t["x"] < left - 1 or t["y"] < top - 1
                   or t["right"] > left + width + 1 or t["bottom"] > top + height + 1]
        if clipped:
            self.issue(key, "raster_font_clipping", clipped)
        overlaps = [[a["text"], b["text"]] for i, a in enumerate(texts) for b in texts[i + 1:]
                    if min(a["right"], b["right"]) - max(a["x"], b["x"]) > 2 and
                    min(a["bottom"], b["bottom"]) - max(a["y"], b["y"]) > 3]
        if overlaps:
            self.issue(key, "raster_font_overlaps", overlaps)

    def sheets(self):
        for category, pictures in self.pictures.items():
            for start in range(0, len(pictures), 6):
                selected = pictures[start:start + 6]
                canvas = Image.new("RGB", (1500, 1320), "#ffffff")
                draw = ImageDraw.Draw(canvas)
                for i, (label, path) in enumerate(selected):
                    x, y = i % 2 * 750, i // 2 * 440
                    draw.text((x + 8, y + 4), label, fill="#171713")
                    image = Image.open(path).convert("RGB")
                    image.thumbnail((730, 400))
                    canvas.paste(image, (x + 8, y + 30))
                canvas.save(self.output / f"sheet-{category}-{start // 6 + 1:02}.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exports", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--widths", type=int, nargs="+", default=[1360, 390, 320])
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--exclude-weibo", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "screens").mkdir(exist_ok=True)
    audit = Audit(args.site, args.output, exclude_weibo=args.exclude_weibo)
    audit.reconcile_inputs()
    url = args.url or args.site.resolve().as_uri() + "/"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in args.widths:
            audit.native(browser, width, args.screenshots, url)
        audit.exports(browser, args.exports or args.site / "figures")
        browser.close()
    if args.screenshots:
        audit.sheets()
    report = {"source_revision": json.loads((args.site / "publication-manifest.json").read_text())["source_revision"],
              "charts": audit.charts, "issues": audit.issues,
              "summary": {"charts_checked": len(audit.charts), "hover_checks": audit.hover_checks, "issues": len(audit.issues),
                          "by_kind": dict(Counter(i["kind"] for i in audit.issues))}}
    (args.output / "audit.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    for issue in audit.issues[:15]:
        print(json.dumps(issue))
    return bool(audit.issues)


if __name__ == "__main__":
    raise SystemExit(main())
