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


@pytest.mark.parametrize("kind", ["scale", "direction", "age", "infinite", "missing", "survey_date", "sample"])
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
    else:
        d["surveys"]["pew_warmth_2026"]["n_item"] = 5194
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
