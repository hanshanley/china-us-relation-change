"""Public-facing survey histories, with complete data and house-style exports."""

import csv
import io
import json
from pathlib import Path

from .indicator_charts import svg_indicator_chart
from .model import json_text
from .opinion_sources import validate_opinion_data
from .public_freshness import current_groups
from .pipeline import write_atomic
from .theme import BLUE, CHART_THEMES, MUTED, PARTNER_COLORS


CHARTS = {
    "us-china-favorability": {
        "title": "U.S. views of China",
        "subtitle": "Gallup | telephone surveys, 2000-2026",
        "series": ["gallup_us:favorable", "gallup_us:unfavorable"], "mode": "levels",
        "first_survey_per_year": True,
        "unit": "Percent of U.S. adults",
        "summary": "The first reported poll in each year, not annual averages. Every survey round is retained in the complete downloads.",
        "note": "Gallup, March 2026 topline. First poll per year; 2000 uses January 25-26, 2026 February 2-16. Telephone sampling and weights evolved. Not joined to Pew's separate panel."},
    "us-china-panel-favorability": {
        "title": "U.S. views of China: Pew panel",
        "subtitle": "Pew Research Center | American Trends Panel, 2020-2026",
        "series": ["pew_us_atp:favorable", "pew_us_atp:unfavorable"], "mode": "levels",
        "unit": "Percent of U.S. adults",
        "summary": "The question asks about China overall, not separately about its people or government.",
        "note": "Pew Research Center, April 2026 release. Survey rounds, not annual averages. March 2026 fieldwork: March 23-29, n=3,507. Nonresponses are not shown. Earlier telephone surveys remain separate."},
    "china-us-warmth": {
        "title": "Chinese views of the U.S.",
        "subtitle": "China Pulse | October 2025-January 2026 and April-June 2026",
        "series": ["pulse:all"], "mode": "bars", "by_period": True,
        "unit": "Mean warmth (0-100)",
        "summary": "Zero is cold, 50 is neutral and 100 is warm. These scores are not percentages.",
        "note": "The Carter Center / Emory University, October 2026. Quota respondent panel; 2,506 and 2,500 adults. Both waves use the new release's demographic weights. These means must not be joined to Pew's historical favorable percentages."},
    "us-china-age": {
        "title": "U.S. views of China by age",
        "subtitle": "Pew Research Center | March 23-29, 2026 | favorable opinion",
        "series": ["pew_age:" + age + ":favorable" for age in ("18-34", "35-49", "50+")],
        "mode": "bars", "unit": "Percent favorable",
        "summary": "The published bands are ages 18-34, 35-49 and 50+. The youngest band includes 34-year-olds.",
        "note": "Pew Research Center, July 2026 detailed tables. The U.S. sample was surveyed in March, not July. These age bands are not matched to China's different age bands. A survey age gap does not establish why a social-media trend occurs."},
    "china-us-age": {
        "title": "Chinese views of the U.S. by age",
        "subtitle": "China Pulse | April 16-June 26, 2026",
        "series": ["pulse_age:" + age for age in ("18-29", "30-39", "40-49", "50+")],
        "mode": "bars", "latest": True, "unit": "Mean warmth (0-100)",
        "summary": "Original Chinese survey age bands; 50 is a neutral rating, not 50% favorable.",
        "note": "The Carter Center / Emory University, October 2026 weighted results. Quota respondent panel, full wave n=2,500; age-specific bases are not supplied. The 18-29 group is not interchangeable with the U.S. 18-34 group."},
    "us-china-warmth": {
        "title": "Americans' feelings toward China",
        "subtitle": "Pew Research Center | four survey rounds, 2016-2026",
        "series": ["pew_warmth:all"], "mode": "bars", "by_period": True,
        "unit": "Mean warmth (0-100)",
        "summary": "Published mean ratings. The latest survey was conducted September 14-20, 2026.",
        "note": "Pew Research Center, September 2026. Probability panel; 1,168 respondents received the China item, out of 5,193 in the full survey. Means are reported by Pew, not calculated from rounded response bins. No annual values are filled between these four polls."},
    "us-china-age-warmth": {
        "title": "U.S. warmth toward China by age",
        "subtitle": "Pew Research Center | September 14-20, 2026",
        "series": ["pew_warmth_age:18-49", "pew_warmth_age:50+"],
        "mode": "bars", "unit": "Mean warmth (0-100)",
        "summary": "The newer warmth question reports ages 18-49 and 50+, not the earlier 18-34 bands.",
        "note": "Pew Research Center, September 2026. Published mean ratings, with 50 neutral. This question and its age bands differ from the March favorability question. The figures do not measure participation in a social-media trend."},
    "us-china-earlier-favorability": {
        "title": "Earlier U.S. views of China",
        "subtitle": "Pew Research Center | telephone surveys, 2005-2020",
        "series": ["pew_us_phone:favorable", "pew_us_phone:unfavorable"],
        "mode": "levels", "unit": "Percent of U.S. adults",
        "summary": "Earlier telephone surveys are shown separately from the American Trends Panel.",
        "note": "Pew's April 2026 retrospective table, spring survey rounds. Telephone and panel answers differ even in the overlapping 2020 year, so they are not spliced. The separately reported summer 2020 phone results are retained in the full data download."},
    "china-us-earlier-favorability": {
        "title": "Earlier Chinese views of the U.S.",
        "subtitle": "Pew Research Center | historical survey rounds, 2007-2016",
        "series": ["pew_china:favorable"], "mode": "bars", "by_period": True,
        "unit": "Percent favorable",
        "summary": "Historical Pew favorable opinions. These are not current readings or warmth scores.",
        "note": "Pew Research Center, October 2016, published net percentages. Historical sample coverage varies; bars do not imply a continuous national probability trend. Unfavorable answers are also retained in the complete download. No connection to the different China Pulse scale is drawn."},
}


def chart_groups(data, chart_id):
    config, result = CHARTS[chart_id], []
    for sid in config["series"]:
        definition = data["series"][sid]
        rows = sorted((r for r in data["observations"] if r["series_id"] == sid),
                      key=lambda r: (r["year"], data["surveys"][r["survey_id"]]["field_start"] or ""))
        if config.get("first_survey_per_year"):
            annual = {}
            for row in rows:
                annual.setdefault(row["year"], row)
            rows = list(annual.values())
        if config.get("latest"):
            rows = [r for r in rows if r["year"] == max(p["year"] for p in rows)]
        color = (MUTED if sid.endswith(":unfavorable") else
                 PARTNER_COLORS["CHN"] if definition["respondent_country"] == "CHN" else BLUE)
        sets = [[r] for r in rows] if config.get("by_period") else [rows]
        for selected in sets:
            label = selected[0]["period"] if config.get("by_period") else definition["label"]
            points = [dict(r, plotted_value=r["value"], reported_unit=config["unit"])
                      for r in selected if r["value"] is not None]
            result.append({"id": sid, "label": label, "color": color,
                           "cadence": definition["cadence"], "period_basis": "survey round",
                           "scheduled_years": [r["year"] for r in selected], "points": points,
                           "unavailable_label": "Not reported"})
    return current_groups(result)


def svg_opinion_chart(data, chart_id, theme="themarginoferror"):
    config = dict(CHARTS[chart_id], y_min=0, y_max=100, bounded=True, show_bar_period=False)
    groups = chart_groups(data, chart_id)
    config["bar_width"] = min(130, 835 / max(1, len(groups)) * .7)
    return svg_indicator_chart(config, groups, theme,
                               "Reported survey estimates. Percent favorable and 0-100 mean ratings are separate measures; actual age bands and survey periods are retained.",
                               "opinion-point")


def flat_observation(data, row):
    definition, survey, source = (data[k][row[field]] for k, field in
                                  (("series", "series_id"), ("surveys", "survey_id"), ("sources", "source_id")))
    return dict(row, **{k: v for k, v in definition.items() if k != "notes"},
                series_notes=definition["notes"], field_start=survey["field_start"], field_end=survey["field_end"],
                survey_n_total=survey["n_total"], survey_n_item=survey["n_item"], survey_notes=survey["notes"],
                source_name=source["name"], source_published=source["published"], source_url=source["url"],
                source_locator=source["locator"], source_notes=source["notes"],
                source_assets=json.dumps(source["assets"], sort_keys=True))


def build_opinions(root, data, gallery):
    from .render import esc, export_figure, figure_links, remove_figure

    validate_opinion_data(data)
    cards, plotted = [], []
    for chart_id, config in CHARTS.items():
        paths = {}
        for theme in CHART_THEMES:
            svg = svg_opinion_chart(data, chart_id, theme)
            relative = Path("opinions") / theme / chart_id
            if svg is None:
                remove_figure(root, relative)
            else:
                paths[theme] = export_figure(root, relative, svg)
        if not paths:
            continue
        source_ids, exact = set(), []
        for group in chart_groups(data, chart_id):
            for point in group["points"]:
                source_ids.add(point["source_id"])
                plotted.append(dict(flat_observation(data, {k: point[k] for k in
                    ("series_id", "survey_id", "source_id", "year", "period", "value", "status", "comparability", "notes")}),
                    chart_id=chart_id, label=group["label"], plotted_value=point["plotted_value"], plotted_unit=config["unit"]))
                survey = data["surveys"][point["survey_id"]]
                dates = (survey["field_start"] + " to " + survey["field_end"]) if survey["field_start"] else "Not supplied in the retrospective table"
                value = f'{point["value"]:g}' if point["value"] is not None else "Not reported"
                exact.append(f'<tr><th scope="row">{esc(group["label"])}</th><td>{esc(point["period"])}</td>'
                             f'<td>{esc(value)}</td><td>{esc(config["unit"])}</td><td>{esc(dates)}</td></tr>')
        sources = "".join(f'<li><a href="{esc(data["sources"][sid]["url"])}">'
                          f'{esc(data["sources"][sid]["name"])}</a>: {esc(data["sources"][sid]["notes"])}</li>'
                          for sid in sorted(source_ids))
        cards.append(f'<section class="series-panel" id="{chart_id}"><h2>{esc(config["title"])}</h2>'
                     f'<div class="comparison-chart" tabindex="0" role="region" aria-label="{esc(config["title"])}">'
                     f'<img src="{esc(paths["themarginoferror"]["png"])}" width="1000" height="600" loading="lazy" '
                     f'alt="{esc(config["title"])} - {esc(config["subtitle"])}"></div>'
                     f'<p class="chart-note">{esc(config["summary"])}</p>'
                     '<details><summary>Reported values and survey dates</summary><div class="table-scroll"><table>'
                     '<thead><tr><th>Group</th><th>Survey round</th><th>Value</th><th>Measure</th><th>Fieldwork</th></tr></thead><tbody>'
                     + "".join(exact) + '</tbody></table></div></details>'
                     f'<details><summary>Sources and survey methods</summary><p>{esc(config["note"])}</p><ul>{sources}</ul></details>'
                     '<details class="chart-downloads"><summary>Download data and graphics</summary>'
                     '<p><a href="downloads/opinions.json">Complete data and definitions (JSON)</a> &middot; '
                     '<a href="downloads/opinion-observations.csv">All observations (CSV)</a> &middot; '
                     '<a href="downloads/opinion-chart-values.csv">Plotted values (CSV)</a></p>'
                     + figure_links(paths) + '</details></section>')
        gallery_paths = {t: {k: p.removeprefix("figures/") for k, p in files.items()} for t, files in paths.items()}
        gallery["opinions"].append(f'<article><h3>{esc(config["title"])}</h3><p>{esc(config["subtitle"])}</p>'
                                   + figure_links(gallery_paths) + '</article>')
    write_atomic(root / "site/downloads/opinions.json", json_text(data))
    for name, rows in (("opinion-observations", [flat_observation(data, r) for r in data["observations"]]),
                       ("opinion-chart-values", plotted)):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        write_atomic(root / ("site/downloads/" + name + ".csv"), stream.getvalue())
    write_atomic(root / "site/opinions.html",
                 '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>Public opinion | U.S.-China connections</title><link rel="stylesheet" href="assets/style.css">'
                 '</head><body><a class="skip" href="#main">Skip to content</a><div class="page">'
                 '<header><p><a href="index.html">Exchange dashboard</a></p><h1>Public opinion</h1>'
                 '<p>How Americans view China, and how Chinese respondents view the United States.</p></header>'
                 '<main id="main">' + "".join(cards) + '</main></div></body></html>')
    return len(cards)
