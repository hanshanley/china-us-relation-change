"""Primary-source opinion checkpoints and regressions for survey comparability."""

import copy
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from us_china_exchange import opinion_sources as sources
from us_china_exchange.opinion_analysis import CHARTS, build_opinions, chart_groups, svg_opinion_chart


ROOT = Path(__file__).resolve().parents[1]


def data():
    return json.loads((ROOT / "data/site/opinions.json").read_text())


def test_primary_source_checkpoints_keep_two_directions_and_scales_separate():
    d = sources.validate_opinion_data(data())
    values = {(r["series_id"], r["year"]): r["value"] for r in d["observations"]}
    assert values["pew_us_atp:favorable", 2020] == 19
    assert values["pew_us_phone:favorable", 2020] == 27
    assert values["pew_us_phone_summer:favorable", 2020] == 22
    assert [values[f"pew_age:{age}:favorable", 2026] for age in ("18-34", "35-49", "50+")] == [38, 28, 19]
    assert values["pew_us_atp:unfavorable", 2026] == 71
    assert [values["pew_warmth:all", year] for year in (2016, 2018, 2021, 2026)] == [39, 42, 28, 37]
    assert [values["pulse:all", year] for year in (2025, 2026)] == [33, 32]
    assert [values["pulse_age:" + age, 2026] for age in ("18-29", "30-39", "40-49", "50+")] == [32, 29, 32, 33]
    assert [values["pew_china:favorable", year] for year in range(2010, 2017)] == [58, 44, 43, 40, 50, 44, 50]
    assert d["series"]["pulse:all"]["unit"] == "rating_points"
    assert d["surveys"]["pew_warmth_2026"]["n_item"] == 1168
    assert d["surveys"]["pew_warmth_2026"]["n_total"] == 5193
    assert d["surveys"]["pulse_2025"]["field_end"] == "2026-01-01"
    assert d["surveys"]["pew_phone_2010"]["field_start"] is None


def test_long_run_history_preserves_every_poll_and_selects_first_round_not_an_average():
    d = sources.validate_opinion_data(data())
    rounds = [r for r in d["observations"] if r["series_id"] == "gallup_us:favorable"]
    assert len(rounds) == 29
    assert {r["year"] for r in rounds} == set(range(2000, 2027))
    assert sorted((d["surveys"][r["survey_id"]]["field_start"], r["value"])
                  for r in rounds if r["year"] == 2000) == [
                      ("2000-01-25", 33), ("2000-03-17", 35), ("2000-11-13", 36)]
    groups = chart_groups(d, "us-china-favorability")
    assert [len(group["points"]) for group in groups] == [27, 27]
    assert [group["points"][0]["value"] for group in groups] == [33, 51]
    assert [group["points"][-1]["value"] for group in groups] == [34, 61]
    latest = d["surveys"][groups[0]["points"][-1]["survey_id"]]
    assert latest["field_start"] == "2026-02-02" and latest["field_end"] == "2026-02-16"
    assert latest["n_total"] == 1001 and latest["n_item"] is None
    assert all(r["comparability"] == "gallup_us_telephone"
               for group in groups for r in group["points"])
    assert min(r["year"] for r in d["observations"] if r["series_id"] == "pew_us_phone:favorable") == 2005
    assert min(r["year"] for r in d["observations"] if r["series_id"] == "pew_china:favorable") == 2007
    panel = chart_groups(d, "us-china-panel-favorability")
    assert [group["points"][-1]["value"] for group in panel] == [27, 71]
    assert min(r["year"] for group in panel for r in group["points"]) == 2020


def test_gallup_parser_keeps_distinct_polls_and_rejects_missing_or_wrong_country_data(monkeypatch):
    rows = ["2000 Jan 25-26 4 29 33 18 16 33 51",
            "2000 Mar 17-19 6 29 40 16 9 35 56",
            "2000 Nov 13-15 5 31 39 18 7 36 57"]
    rows += [f"{year} Feb 2-16 5 29 37 24 * 34 61" for year in range(2001, 2027)]
    table = "D. China\nTotal favorable Total unfavorable\n" + "\n".join(rows) + "\nAsked of half sample"
    class Page:
        def __init__(self, text):
            self.text = text
        def extract_text(self):
            return self.text
    class Reader:
        pages = [Page("telephone interviews conducted February 2-16, 2026"),
                 Page(table.replace("D. China", "C. Canada").replace("34 61", "80 15")), Page(table)]
    monkeypatch.setattr(sources, "PdfReader", lambda _: Reader())
    result = sources.parse_gallup_history(b"source")
    assert len(result) == 29 and result[0]["favorable"] == 33 and result[-1]["unfavorable"] == 61
    for invalid in (table.replace(rows[3] + "\n", ""),
                    table.replace("34 61", "* 61"),
                    table.replace(rows[0], rows[0] + "\n" + rows[0]),
                    table.replace("2000 Mar 17-19", "2000 Mar 17-Apr 1")):
        Reader.pages[-1] = Page(invalid)
        with pytest.raises(ValueError):
            sources.parse_gallup_history(b"changed source")


def test_opinion_charts_never_have_travel_restriction_context():
    for chart_id in CHARTS:
        for theme in ("themarginoferror", "substack"):
            svg = BeautifulSoup(svg_opinion_chart(data(), chart_id, theme), "html.parser")
            assert not svg.select(".covid-context,.covid-band,.covid-label")


def test_generic_indicator_travel_context_requires_explicit_opt_in():
    from us_china_exchange.indicator_charts import svg_indicator_chart

    config = {"title": "Arrivals", "subtitle": "Reported arrivals", "mode": "levels",
              "unit": "Trips", "note": ""}
    group = {"id": "arrivals", "label": "Arrivals", "color": "#39748F", "cadence": "annual",
             "scheduled_years": [2019, 2020], "points": [
                 {"year": year, "value": 10, "plotted_value": 10, "comparability": "same"}
                 for year in (2019, 2020)]}
    for enabled in (False, True):
        configured = dict(config, covid_context=True) if enabled else config
        svg = BeautifulSoup(svg_indicator_chart(configured, [group], "substack", "", "travel-point"),
                            "html.parser")
        assert bool(svg.select(".covid-band")) == enabled


@pytest.mark.parametrize("kind", ["scale", "direction", "age", "infinite", "missing", "survey_date", "sample",
                                 "gallup_source", "gallup_dates"])
def test_invalid_survey_semantics_fail_before_publication(kind):
    d = data()
    if kind == "scale":
        d["series"]["pulse:all"].update(measure="favorability", unit="percent")
    elif kind == "direction":
        d["series"]["pew_us_atp:favorable"].update(respondent_country="CHN", target_country="USA")
    elif kind == "age":
        d["series"]["pew_age:18-34:favorable"].update(age="50+", label="50+")
    elif kind == "infinite":
        d["observations"][0]["value"] = float("nan")
    elif kind == "missing":
        d["observations"][0]["value"] = None
    elif kind == "survey_date":
        d["surveys"]["pulse_2025"]["field_start"] = "2027-01-01"
    elif kind == "sample":
        d["surveys"]["pew_warmth_2026"]["n_item"] = 5194
    elif kind == "gallup_source":
        next(r for r in d["observations"] if r["series_id"] == "gallup_us:favorable")["comparability"] = "pew_us_atp"
    else:
        survey = d["surveys"]["gallup_us_2000-01-25"]
        survey.update(field_start=None, field_end=None)
    with pytest.raises(ValueError):
        sources.validate_opinion_data(d)


def test_age_pdf_parser_does_not_read_the_neighboring_country(monkeypatch):
    text = ("Views of China by age\nCountry Response Ages 18-34 35-49 50+\n"
            "U.S. Favorable 38% 28% 19% Australia Favorable 37 33 27\n"
            " Unfavorable 59 69 79 Unfavorable 61 66 72\n")
    class Page:
        def extract_text(self):
            return text
    class Reader:
        pages = [Page()]
    monkeypatch.setattr(sources, "PdfReader", lambda _: Reader())
    result = sources.parse_pew_age(b"reviewed numeric layout")
    assert result == {"18-34": {"favorable": 38, "unfavorable": 59},
                      "35-49": {"favorable": 28, "unfavorable": 69},
                      "50+": {"favorable": 19, "unfavorable": 79}}


def test_reviewed_china_pulse_table_rejects_missing_values_and_changed_age_bands():
    body = ("Topic\tFall/Winter 2025\tSpring/Summer 2026\tDemographic\n"
            "\t33\t32\tOverall\n18-29\t39\t32\tAge\n30-39\t35\t29\tAge\n"
            "40-49\t30\t32\tAge\n50+\t32\t33\tAge\n").encode()
    assert sources.parse_pulse(body)[0]["Spring/Summer 2026"] == 32
    for bad in (body.replace(b"18-29", b"18-34"), body.replace(b"\t33\t32\t", b"\t\t32\t")):
        with pytest.raises(ValueError):
            sources.parse_pulse(bad)


def test_missing_age_bar_is_not_a_zero_and_real_zero_is_drawn():
    d = data()
    row = next(r for r in d["observations"] if r["series_id"] == "pew_age:18-34:favorable")
    row.update(value=None, status="missing")
    sources.validate_opinion_data(d)
    svg = BeautifulSoup(svg_opinion_chart(d, "us-china-age"), "html.parser")
    assert svg.select_one('.unavailable-bar[data-series-id="pew_age:18-34:favorable"]')
    assert len(svg.select("rect.opinion-point")) == 2
    row.update(value=0, status="observed")
    svg = BeautifulSoup(svg_opinion_chart(d, "us-china-age"), "html.parser")
    bar = svg.select_one('rect.opinion-point[data-series-id="pew_age:18-34:favorable"]')
    assert bar["data-value"] == "0" and float(bar["height"]) == 0


def test_complete_downloads_and_bounded_graphics(tmp_path):
    from collections import defaultdict
    from PIL import Image

    d = data()
    assert build_opinions(tmp_path, d, defaultdict(list)) == len(CHARTS)
    assert json.loads((tmp_path / "site/downloads/opinions.json").read_text()) == d
    raw = list(csv.DictReader((tmp_path / "site/downloads/opinion-observations.csv").open()))
    plotted = list(csv.DictReader((tmp_path / "site/downloads/opinion-chart-values.csv").open()))
    assert len(raw) == len(d["observations"]) and {r["series_id"] for r in raw} == set(d["series"])
    assert {r["chart_id"] for r in plotted} == set(CHARTS)
    for chart in CHARTS:
        for theme in ("themarginoferror", "substack"):
            svg = BeautifulSoup((tmp_path / f"site/figures/opinions/{theme}/{chart}.svg").read_text(), "html.parser")
            assert svg.svg["data-axis-max"] == "100"
            assert len(svg.select("circle.opinion-point,rect.opinion-point")) == sum(
                len(g["points"]) for g in chart_groups(d, chart))
            with Image.open(tmp_path / f"site/figures/opinions/{theme}/{chart}.png") as png:
                assert png.size == (3000, 1800)


def test_source_checks_are_noops_for_metadata_only_changes_and_preserve_data_on_failure(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("opinion_builder_test", ROOT / "scripts/build_opinion_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = data()
    checked = copy.deepcopy(original)
    checked["sources"]["pew_us_trend"]["assets"][0]["sha256"] = "a" * 64
    assert module.stable(original) == module.stable(checked)
    changed = copy.deepcopy(original)
    changed["observations"][0]["value"] += 1
    assert module.stable(original) != module.stable(changed)
    frozen = tmp_path / "data/site/opinions.json"
    frozen.parent.mkdir(parents=True)
    frozen.write_text(json.dumps(original))
    seed = tmp_path / sources.REVIEWED_PATH
    seed.parent.mkdir(parents=True)
    seed.write_text("{}")
    before = frozen.read_bytes()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "argv", ["build_opinion_data.py", "--cached"])
    def fail(*args):
        raise ValueError("Changed survey question")
    monkeypatch.setattr(module, "collect", fail)
    with pytest.raises(ValueError, match="Changed survey question"):
        module.main()
    assert frozen.read_bytes() == before
    assert json.loads((tmp_path / "data/local/opinions/check.json").read_text())["status"] == "error"
