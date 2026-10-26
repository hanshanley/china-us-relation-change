"""Primary-source opinion checkpoints and regressions for survey comparability."""

import copy
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from us_china_exchange.theme import png_dimensions
from bs4 import BeautifulSoup

from us_china_exchange import opinion_sources as sources
from us_china_exchange.opinion_analysis import CHARTS, RETIRED_CHARTS, build_opinions, chart_groups, svg_opinion_chart


ROOT = Path(__file__).resolve().parents[1]


def data():
    return json.loads((ROOT / "data/site/opinions.json").read_text())


@pytest.mark.parametrize("theme", ["themarginoferror", "substack"])
@pytest.mark.parametrize("chart_id", [
    "us-china-favorability",
    "us-china-earlier-favorability", "china-us-earlier-favorability",
])
def test_sentiment_colors_are_distinct_in_exports_and_interactive_models(chart_id, theme):
    from us_china_exchange.theme import BLUE

    d = data()
    svg = BeautifulSoup(svg_opinion_chart(d, chart_id, theme), "html.parser").svg
    for mark in svg.select(".data-line,.opinion-point"):
        color = mark.get("stroke") if mark.name == "path" else mark["fill"]
        if mark["data-series-id"].endswith(":favorable"):
            assert color == BLUE
        else:
            red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            assert red > 1.5 * green and red > 1.5 * blue
    for legend in svg.select(".legend-label"):
        color = legend.find_previous_sibling("path")["stroke"]
        label = legend.get_text(strip=True).lower()
        marks = svg.select(f'[data-series-id$=":{label}"]')
        assert marks
        assert all((mark.get("stroke") if mark.name == "path" else mark["fill"]) == color for mark in marks)
    spec = importlib.util.spec_from_file_location("opinion_color_publication", ROOT / "scripts/build_exchange_publication.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    labels = {sid: definition["label"] for sid, definition in d["series"].items()}
    model = module.plot_model(svg, labels, {})
    groups = chart_groups(d, chart_id)
    expected_colors = {group["id"]: group["color"] for group in groups}
    assert all(group["color"] == expected_colors[group["id"]]
               for group in model.get("bars", model["groups"]))
    model_points = model["bars"] if model["kind"] == "bars" else [
        point for group in model["groups"] for point in group["points"]]
    assert [point["value"] for point in model_points] == [
        point["value"] for group in groups for point in group["points"]]


def test_c100_reported_age_panel_preserves_country_geometry_and_literal_bins():
    events = [dict(x=x, y=y, values=values) for x, y, values in (
        (165, 145, [50, 40]), (250, 145, [55, 54]),
        (165, 195, [48, 57]), (250, 195, [43, 44]),
        (355, 145, [39, 36, 39, 44]), (355, 195, [55, 60, 55, 48]))]
    text = ("2017 GENERAL PUBLIC AGE BREAKDOWN 18-34 35-49 50+ "
            "How would you describe your impression of China? "
            "How would you describe your impression of the U.S.?")
    points = sources.parse_c100_age_panel(events, text)
    assert len(points) == 16
    assert [(row["age"], row["value"]) for row in points
            if row["country"] == "USA" and row["response"] == "favorable"] == [
                ("General Population", 48), ("18-34", 57), ("35-49", 43), ("50+", 44)]
    for changed_events, changed_text in (
        (events[:-1], text), ([*events, events[0]], text),
        ([dict(events[0], x=355), *events[1:]], text),
        ([dict(events[0], values=[True, 40]), *events[1:]], text),
        ([*events, dict(x=400, y=150, values=[6, 4, 6, 8])], text),
        (events, text.replace("35-49", "35-54")),
        (events, text.replace("impression of the U.S.?", "impression of the U.S. government?")),
    ):
        with pytest.raises(ValueError):
            sources.parse_c100_age_panel(changed_events, changed_text)
    assert sources.parse_c100_age_panel([*events, dict(x=800, y=150, values=[99] * 4)], text) == points
    with pytest.raises(ValueError, match="edition changed"):
        sources.parse_c100_reported_ages(b"unreviewed edition", b"unreviewed translation", b"earlier")


def test_c100_image_review_uses_original_streams_not_platform_png_encodings():
    from pypdf.generic import DecodedStreamObject, NameObject

    class OriginalPage(dict):
        @property
        def images(self):
            raise AssertionError("Re-encoded PNG bytes are not a source fingerprint")

    image = DecodedStreamObject()
    image[NameObject("/Subtype")] = NameObject("/Image")
    image.set_data(b"reviewed table pixels")
    form = DecodedStreamObject()
    form[NameObject("/Subtype")] = NameObject("/Form")
    form.set_data(b"page drawing commands")
    objects = {"/Im0": image, "/Fm0": form}
    page = OriginalPage({"/Resources": {"/XObject": objects}})
    reviewed = sources.c100_original_image_fingerprints(page)
    assert reviewed == {"/Im0": sources.digest(b"reviewed table pixels")}
    objects["/Im0"] = image.flate_encode()
    assert sources.c100_original_image_fingerprints(page) == reviewed
    image.set_data(b"changed table pixels")
    objects["/Im0"] = image
    assert sources.c100_original_image_fingerprints(page) != reviewed
    del objects["/Im0"]
    assert sources.c100_original_image_fingerprints(page) != reviewed


def test_c100_reported_age_archive_retains_actual_interviews_unknown_dates_and_unharmonized_bins():
    d = sources.validate_opinion_data(data())
    rows = [row for row in d["observations"] if row["series_id"].startswith("c100_reported_age_")]
    assert len(rows) == 17
    assert sum(row["series_id"].startswith("c100_reported_age_us:") for row in rows) == 8
    assert sum(row["series_id"].startswith("c100_reported_age_china:") for row in rows) == 8
    assert not any(row["series_id"].endswith("not_sure") for row in rows)
    us = d["surveys"]["c100_reported_age_us_2016"]
    china = d["surveys"]["c100_reported_age_china_2017"]
    assert (us["year"], us["field_start"], us["field_end"], us["n_total"], us["n_item"]) == (
        2016, "2016-11-18", "2016-12-20", 1019, None)
    assert (china["year"], china["field_start"], china["field_end"], china["n_total"], china["n_item"]) == (
        2017, None, None, 3696, None)
    assert sources.C100_CHINA_DATE_CONFLICT in china["notes"]
    assert {d["series"][row["series_id"]]["age"] for row in rows
            if not row["series_id"].startswith("c100_reported_age_2007:")} == {"18+", "18-34", "35-49", "50+"}
    assert all(not sid.startswith("c100_reported_age_") for chart in CHARTS.values() for sid in chart["series"])
    earlier = next(row for row in rows if row["year"] == 2007)
    assert earlier["value"] == 69 and d["series"][earlier["series_id"]]["age"] == "18-29"


def test_c100_reported_age_archive_rejects_rebins_selected_dates_item_bases_and_source_substitution():
    for case in ("age", "sampling", "exact_china_dates", "report_year_as_us_interview_year",
                 "item_base", "discard_date_conflicts", "source", "publication", "bridge", "edition"):
        d = data()
        row = next(row for row in d["observations"]
                   if row["series_id"] == "c100_reported_age_china:35-49:favorable")
        survey = d["surveys"][row["survey_id"]]
        if case == "age":
            d["series"][row["series_id"]]["age"] = "35-54"
        elif case == "sampling":
            d["series"][row["series_id"]]["sampling"] = "All China residents, matched to Pew"
        elif case == "exact_china_dates":
            survey.update(field_start="2016-12-12", field_end="2017-01-09")
        elif case == "report_year_as_us_interview_year":
            survey = d["surveys"]["c100_reported_age_us_2016"]
            survey.update(year=2017, field_start="2017-11-18", field_end="2017-12-20")
            for point in d["observations"]:
                if point["survey_id"] == "c100_reported_age_us_2016":
                    point["year"] = 2017
        elif case == "item_base":
            survey["n_item"] = survey["n_total"]
        elif case == "discard_date_conflicts":
            survey["notes"] = "Exact national all-adult survey"
        elif case == "source":
            row["source_id"] = "c100_china_2007"
        elif case == "publication":
            d["sources"][row["source_id"]]["published"] = "2026"
        elif case == "bridge":
            row["comparability"] = "pew_china_telephone"
        else:
            d["sources"][row["source_id"]]["assets"][1]["sha256"] = "0" * 64
        with pytest.raises(ValueError):
            sources.validate_opinion_data(d)


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
    panel = [r for r in d["observations"] if r["series_id"].startswith("pew_us_atp:")]
    assert min(r["year"] for r in panel) == 2020
    assert {r["series_id"]: r["value"] for r in panel if r["year"] == 2026} == {
        "pew_us_atp:favorable": 27, "pew_us_atp:unfavorable": 71}


def test_plot_audit_reconciles_each_survey_round_instead_of_overwriting_its_year():
    spec = importlib.util.spec_from_file_location("plot_audit", ROOT / "scripts/audit_exchange_plots.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    polls = [r for r in data()["observations"] if r["series_id"] == "gallup_us:favorable" and r["year"] == 2000]
    assert len(polls) > 1
    audit = module.Audit.__new__(module.Audit)
    audit.exclude_weibo = False
    audit.datasets = {"opinions.html": {"observations": polls}}
    audit.plotted = {"opinions.html": [
        dict(series_id=r["series_id"], year=str(r["year"]), survey_id=r["survey_id"],
             value=str(r["value"]), plotted_value=str(r["value"])) for r in polls]}
    audit.weibo = {"accounts": []}
    audit.issues = []
    audit.reconcile_inputs()
    assert audit.issues == []
    row = audit.plotted["opinions.html"][0]
    row["value"] = row["plotted_value"] = str(polls[0]["value"] + 1)
    audit.reconcile_inputs()
    assert [issue["kind"] for issue in audit.issues] == ["reported_value", "transformed_value"]


def test_early_china_rounds_retain_their_age_city_and_fieldwork_limits():
    from us_china_exchange.public_freshness import public_charts

    d = sources.validate_opinion_data(data())
    rows = [r for r in d["observations"] if r["series_id"].startswith("pew_china_18_60:")]
    assert {(r["year"], r["series_id"].split(":")[-1]): r["value"] for r in rows} == {
        (2005, "favorable"): 42, (2005, "unfavorable"): 53,
        (2006, "favorable"): 47, (2006, "unfavorable"): 43}
    for row in rows:
        definition, survey = d["series"][row["series_id"]], d["surveys"][row["survey_id"]]
        assert definition["age"] == "18-60" and definition["respondent_country"] == "CHN"
        assert "not nationally representative" in definition["sampling"]
        assert survey["n_item"] is None
        assert row["comparability"] == f'pew_china_18_60_coverage_{row["year"]}'
    first, second = (d["surveys"][f"pew_china_{year}"] for year in (2005, 2006))
    assert (first["field_start"], first["field_end"], first["n_total"]) == ("2005-05-21", "2005-05-31", 2191)
    assert (second["field_start"], second["field_end"], second["n_total"]) == ("2006-04-07", "2006-04-18", 2180)
    assert "Chengdu" in first["notes"] and "Xinxiang" not in first["notes"]
    assert "Xinxiang" in second["notes"] and "Chengdu" not in second["notes"]
    assert d["series"]["pew_china:favorable"]["age"] == "All adults"
    with public_charts():
        assert not chart_groups(d, "china-us-earlier-favorability")
    assert all(not sid.startswith("pew_china_18_60:")
               for config in CHARTS.values() for sid in config["series"])


def test_early_china_parser_uses_the_china_nets_and_both_original_methods(monkeypatch):
    table = ("Pew Global Attitudes Project: Spring 2006 Survey\nQ.2\n"
             "FAVORABLE UNFAVORABLE\na. The United States\n"
             " United States 77 49 28 17 7 10 5=99\n May, 2005 83 50 33 14 4 10 3=100\n"
             " China 47 9 38 43 6 37 10=100\n May, 2005 42 5 37 53 13 40 5=100\n"
             " Japan 63 8 55 35 6 29 3=101\n")
    current = ("Methodological Appendix\nCountry: China\n"
               "Probability sample in six cities and surrounding rural areas - "
               "Shanghai, Beijing, Guangzhou, Xinxiang, Jinzhong, and Luzhou\n"
               "Face-to-face adults 18 to 60\nApril 7-18, 2006\n"
               "Sample size: 2180\nDisproportionately urban\nCountry: India\n"
               "Face-to-face adults 18 to 60\n")
    earlier = ("ABOUT THE SURVEY\nMay 21-3 1, 2005\nprobability sample of 2,191\n"
               "six major cities and their surrounding rural areas "
               "(Beijing, Chengdu, Guangzhou, Shanghai, Shenyang, and Wuhan)\n"
               "not representative of the entire country\nadults ages 18-60")
    dates = "Spring 2005 Survey\nChina: May 21\u201331, 2005 (N=2,191)"
    documents = {b"2006": [table, current], b"2005": [earlier, dates]}
    class Page:
        def __init__(self, text):
            self.text = text
        def extract_text(self):
            return self.text
    class Reader:
        def __init__(self, body):
            self.pages = [Page(text) for text in documents[body.getvalue()]]
    monkeypatch.setattr(sources, "PdfReader", Reader)
    result = sources.parse_early_china_history(b"2006", b"2005")
    assert [(r["year"], r["favorable"], r["unfavorable"]) for r in result] == [
        (2005, 42, 53), (2006, 47, 43)]
    for key, index, original, changed in (
            (b"2006", 0, table, table.replace("a. The United States", "a. China")),
            (b"2006", 0, table, table.replace(" China 47", " Russia 47")),
            (b"2006", 0, table, table.replace("42 5 37 53", "42 5 37 *")),
            (b"2006", 1, current, current.replace("adults 18 to 60", "adults 18 plus", 1)),
            (b"2005", 0, earlier, earlier.replace("Shenyang", "Xinxiang")),
            (b"2005", 1, dates, dates.replace("21\u201331", "21\u201330"))):
        documents[key][index] = changed
        with pytest.raises(ValueError):
            sources.parse_early_china_history(b"2006", b"2005")
        documents[key][index] = original


def test_beijing_archive_keeps_original_precision_and_qualified_urban_population():
    d = sources.validate_opinion_data(data())
    rows = [row for row in d["observations"] if row["series_id"] == "bas_beijing:us_warmth"]
    assert [(r["year"], r["value"]) for r in rows] == [
        (1998, 62), (1999, 53), (2000, 57), (2001, 47), (2002, 52)]
    assert d["sources"]["bas_beijing_history"]["published"] == "2003"
    assert d["series"]["bas_beijing:us_warmth"]["age"] == "18-65"
    sampling = d["series"]["bas_beijing:us_warmth"]["sampling"]
    assert all(token in sampling for token in
               ("eight urban districts", "fixed residence", "non-agricultural Beijing hukou"))
    for row in rows:
        survey = d["surveys"][row["survey_id"]]
        assert survey["field_start"] is None and survey["field_end"] is None
        assert survey["n_total"] == {1998: 756, 1999: 712, 2000: 757, 2001: 615, 2002: 662}[row["year"]]
        assert survey["n_item"] is None
        assert "month precision" in survey["notes"]
        assert ("Approximate mean" in row["notes"]) == (row["year"] in (1998, 1999, 2002))
        assert row["comparability"] == "bas_beijing_coverage_" + str(row["year"])
    assert "2001-12 to 2002-02" in d["surveys"]["bas_beijing_2001"]["notes"]
    assert {sources.beijing_methods_url(year) for year in range(1998, 2003)} <= {
        asset["request_url"] for asset in d["sources"]["bas_beijing_history"]["assets"]}
    assert all(not sid.startswith("bas_beijing:")
               for chart in CHARTS.values() for sid in chart["series"])


def test_beijing_parser_requires_the_original_wave_country_and_sample_evidence(monkeypatch):
    methods = ("The Beijing Area Study Survey; survey of Beijing citizens; "
               "probability proportional to size; face-to-face; December or January; "
               "sample size was 757; 2001 sample size was 615; 2002 the sample size was 662.")
    footnote = ("100 degree feeling thermometer towards the US: "
                "1998 around 62; 1999 around 53; 57 in 2000; "
                "2001 to 47, and rose in 2002 to around 52. This volatility")
    class Page:
        def __init__(self, text):
            self.text = text
        def extract_text(self, **kwargs):
            return self.text
    class Reader:
        pages = [Page(methods), Page(footnote)]
    monkeypatch.setattr(sources, "PdfReader", lambda _: Reader())
    parsed = sources.parse_beijing_history(b"reviewed original")
    assert [r["value"] for r in parsed] == [62, 53, 57, 47, 52]
    assert [r["approximate"] for r in parsed] == [True, True, False, False, True]
    for invalid in (
            footnote.replace("towards the US", "towards Japan"),
            footnote.replace("1999", "1998"),
            footnote.replace("2002", "2003"),
            footnote.replace("around 52", "around 101"),
            footnote.replace("1999 around 53; ", ""),
            footnote.replace("1998 around 62", "1998 around 62 63")):
        Reader.pages = [Page(methods), Page(invalid)]
        with pytest.raises(ValueError):
            sources.parse_beijing_history(b"changed source")
    Reader.pages = [Page(methods.replace("Beijing citizens", "national adults")), Page(footnote)]
    with pytest.raises(ValueError):
        sources.parse_beijing_history(b"wrong population")


def test_beijing_original_method_parser_checks_wave_registration_and_month_precision():
    fields = {
        "Dataset Persistent ID": "doi:10.18170/DVN/ARBTMK",
        "Title": "Beijing Area Study-2001",
        "Date of Collection": "Start: 2001-12 ; End: 2002-02",
        "Publication Date": "2016-09-06",
        "\u603b\u4f53\u4eba\u7fa4": (
            "\u4e1c\u57ce\u3001\u897f\u57ce\u3001\u5d07\u6587\u3001\u5ba3\u6b66\u3001\u671d\u9633\u3001"
            "\u4e30\u53f0\u3001\u77f3\u666f\u5c71\u3001\u6d77\u6dc0\u516b\u4e2a\u5e02\u533a\u3002"
            "\u6709\u56fa\u5b9a\u4f4f\u6240\u3002\u5317\u4eac\u5e02\u6b63\u5f0f\u7684\u975e\u519c\u4e1a\u6237\u53e3"
            "\u300218\u5c81\u81f365\u5c81"),
        "\u5e94\u7b54\u7387": "\u6709\u6548\u6837\u672c\u6570\u4e3a615\u4e2a\uff0c\u5e94\u7b54\u7387\u4e3a72%\u3002",
        "\u62bd\u6837\u65b9\u6cd5": "PPS\u5206\u4e24\u9636\u6bb5\u62bd\u53d6",
        "\u6536\u96c6\u6a21\u5f0f": "\u7eb8\u7248\u95ee\u5377\u9762\u8bbf",
        "\u6743\u91cd": "WEIGHT PSU",
    }
    body = ('<div class="metadata-panel-body">'
            + "".join('<div class="form-group"><label>' + key + "</label><div>"
                      + value + "</div></div>" for key, value in fields.items()) + "</div>")
    assert sources.parse_beijing_methods(body.encode(), 2001) == {
        "start_month": "2001-12", "end_month": "2002-02",
        "n_total": 615, "metadata_published": "2016-09-06"}
    for old, new in (
            ("ARBTMK", "OXOAFT"), ("Beijing Area Study", "National China Study"),
            ("2016-09-06", "2016-02-30"), ("2002-02", "2002-01"),
            ("2001-12", "2001-12-01"), ("18\u5c81\u81f365\u5c81", "18+"),
            ("\u975e\u519c\u4e1a\u6237\u53e3", "\u6240\u6709\u5c45\u6c11"),
            ("\u516b\u4e2a\u5e02\u533a", "\u4e5d\u4e2a\u5e02\u533a"),
            ("\u77f3\u666f\u5c71", "\u5168\u56fd"),
            ("\u6709\u6548\u6837\u672c\u6570\u4e3a615", "\u6709\u6548\u6837\u672c\u6570\u4e3a662"),
            ("WEIGHT", "unweighted")):
        with pytest.raises(ValueError):
            sources.parse_beijing_methods(body.replace(old, new).encode(), 2001)
    with pytest.raises(ValueError):
        sources.parse_beijing_methods(body.encode(), 2015)


def test_beijing_qualification_requires_primary_sources_and_honest_unknown_days():
    for change in ("missing_source", "missing_month_precision", "fabricated_days", "erased_registration"):
        d = data()
        if change == "missing_source":
            d["sources"]["bas_beijing_history"]["assets"].pop()
        elif change == "missing_month_precision":
            d["surveys"]["bas_beijing_2001"]["notes"] = "Survey conducted in 2001."
        elif change == "fabricated_days":
            d["surveys"]["bas_beijing_1998"].update(field_start="1998-12-01", field_end="1999-01-31")
        else:
            d["series"]["bas_beijing:us_warmth"]["sampling"] = (
                d["series"]["bas_beijing:us_warmth"]["sampling"].replace(
                    "non-agricultural Beijing hukou", "all residents"))
        with pytest.raises(ValueError):
            sources.validate_opinion_data(d)


def test_beijing_archive_rejects_splicing_exactness_and_fabricated_dates():
    for field, value in (("age", "All adults"), ("sampling", "National probability sample")):
        d = data()
        d["series"]["bas_beijing:us_warmth"][field] = value
        with pytest.raises(ValueError):
            sources.validate_opinion_data(d)
    for target, field, value in (
            ("observation", "source_id", "china_pulse"),
            ("observation", "comparability", "china_pulse_october_2026_weights"),
            ("observation", "notes", "Exact mean"),
            ("survey", "n_total", 757),
            ("survey", "n_item", 757),
            ("survey", "field_start", "1998-12-01"),
            ("source", "published", "2003-09-01"),
            ("source", "url", sources.PULSE_REPORT)):
        d = data()
        row = next(r for r in d["observations"] if r["series_id"] == "bas_beijing:us_warmth")
        item = row if target == "observation" else d["surveys"][row["survey_id"]] if target == "survey" else d["sources"][row["source_id"]]
        item[field] = value
        with pytest.raises(ValueError):
            sources.validate_opinion_data(d)


def test_beijing_source_cannot_be_relabelled_as_a_pew_favorable_percentage():
    d = data()
    d["observations"] = [r for r in d["observations"] if not r["series_id"].startswith("c100_")]
    for key in ("series", "surveys", "sources"):
        d[key] = {identity: item for identity, item in d[key].items() if not identity.startswith("c100_")}
    row = next(r for r in d["observations"] if r["series_id"] == "bas_beijing:us_warmth")
    row["series_id"] = "pew_china:favorable"
    with pytest.raises(ValueError):
        sources.validate_opinion_data(d)


def test_c100_archive_is_only_the_chinese_2007_general_public_country_totals():
    d = sources.validate_opinion_data(data())
    rows = [r for r in d["observations"] if r["series_id"].startswith("c100_china_18_60:")]
    assert {r["series_id"]: r["value"] for r in rows} == {
        "c100_china_18_60:favorable": 60, "c100_china_18_60:unfavorable": 26,
        "c100_china_18_60:not_sure": 14}
    survey = d["surveys"]["c100_china_2007"]
    assert (survey["year"], survey["field_start"], survey["field_end"]) == (
        2007, "2007-08-18", "2007-09-07")
    assert survey["n_total"] == 4104 and survey["n_item"] is None
    for row in rows:
        definition = d["series"][row["series_id"]]
        assert definition["respondent_country"] == "CHN" and definition["target_country"] == "USA"
        assert definition["age"] == "18-60" and definition["unit"] == "percent"
        assert row["source_id"] == "c100_china_2007"
        assert row["comparability"] == "c100_china_18_60_2007_coverage"
    assert all(not sid.startswith("c100_") for chart in CHARTS.values() for sid in chart["series"])


def test_c100_parser_selects_published_chinese_public_totals_not_elites_or_residuals(monkeypatch):
    table = ("General Feelings\n(CHINA SURVEY) How would you describe your impressions of the U.S.?\n"
             "US Survey China Survey\nGeneral Public Opinion Leaders Business Leaders Congressional Staffers "
             "General Public Opinion Leaders Business Leaders\n"
             "'07 '05 '07 '05 '07 '05 '07 '05 '07 '07 '07\nVery Favorable\n"
             "FAVORABLE 52 59 56 63 54 63 35 19 60 86 94\n"
             "UNFAVORABLE 45 35 43 37 41 35 62 79 26 11 6\n"
             "Not Sure 3 6 2 1 5 1 3 2 14 3 1\n")
    methods = ("The survey of China was self-sponsored\nChina:\n(a) General Public: "
               "August 18 and September 7, 2007; face-to-face interviews; "
               "4,104 Chinese adults (18-60 years old); multi-stage random sampling; "
               "seven cities, seven towns, and ten villages; nationwide, statistically representative. "
               "(b) Opinion Leaders: 203\nDecember 10, 2007")
    class Page:
        def __init__(self, text):
            self.text = text
        def extract_text(self):
            return self.text
    class Reader:
        pages = [Page(table), Page(methods)]
    monkeypatch.setattr(sources, "PdfReader", lambda _: Reader())
    assert sources.parse_c100_china_2007(b"original") == {
        "favorable": 60, "unfavorable": 26, "not_sure": 14}
    for changed_table, changed_methods in (
            (table.replace("impressions of the U.S.?", "impressions of the U.S. government?"), methods),
            (table.replace("China Survey", "Japan Survey"), methods),
            (table.replace("'07", "'06"), methods),
            (table.replace("Congressional Staffers General Public", "Congressional Staffers Business Leaders"), methods),
            (table.replace("FAVORABLE 52 59 56 63 54 63 35 19 60 86 94\n", ""), methods),
            (table.replace("Not Sure 3 6 2 1 5 1 3 2 14 3 1", "Not Sure 3 6 2 1 5 1 3 2 * 3 1"), methods),
            (table.replace("19 60 86 94", "19 101 86 94"), methods),
            (table, methods.replace("18-60 years old", "18+ years old")),
            (table, methods.replace("4,104", "203")),
            (table, methods.replace("September 7, 2007", "September 10, 2007")),
            (table, methods.replace("seven towns", "all towns"))):
        Reader.pages = [Page(changed_table), Page(changed_methods)]
        with pytest.raises(ValueError):
            sources.parse_c100_china_2007(b"changed source")


def test_c100_population_dates_and_source_routing_cannot_be_spliced():
    for target, field, value in (
            ("series", "age", "All adults"),
            ("series", "sampling", "National unrestricted adult population"),
            ("row", "series_id", "pew_china:favorable"),
            ("row", "source_id", "pew_china_history"),
            ("row", "comparability", "pew_china_coverage_2007"),
            ("row", "survey_id", "pew_china_2007"),
            ("survey", "n_total", 203),
            ("survey", "n_item", 4104),
            ("survey", "field_start", "2007-08-20"),
            ("survey", "field_end", "2007-09-10"),
            ("source", "published", "2017-01-01"),
            ("source", "url", sources.PEW_CHINA)):
        d = data()
        row = next(r for r in d["observations"] if r["series_id"] == "c100_china_18_60:favorable")
        item = (row if target == "row" else d["series"][row["series_id"]] if target == "series"
                else d["surveys"][row["survey_id"]] if target == "survey"
                else d["sources"][row["source_id"]])
        item[field] = value
        with pytest.raises(ValueError):
            sources.validate_opinion_data(d)


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
                                 "gallup_source", "gallup_dates", "early_china_age",
                                 "early_china_coverage", "early_china_dates"])
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
    elif kind == "gallup_dates":
        survey = d["surveys"]["gallup_us_2000-01-25"]
        survey.update(field_start=None, field_end=None)
    elif kind == "early_china_age":
        d["series"]["pew_china_18_60:favorable"]["age"] = "All adults"
    elif kind == "early_china_coverage":
        next(r for r in d["observations"] if r["series_id"] == "pew_china_18_60:favorable")[
            "comparability"] = "pew_china_coverage_2005"
    else:
        d["surveys"]["pew_china_2005"].update(field_start=None, field_end=None)
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
    retired_paths = [
        tmp_path / directory / "opinions" / theme / (chart_id + "." + extension)
        for directory in ("site/figures", "outputs/figures")
        for theme in ("themarginoferror", "substack")
        for chart_id in RETIRED_CHARTS
        for extension in ("svg", "png")]
    for path in retired_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Previously published warmth chart")
    assert build_opinions(tmp_path, d, defaultdict(list)) == len(CHARTS)
    assert all(not path.exists() for path in retired_paths)
    page = BeautifulSoup((tmp_path / "site/opinions.html").read_text(), "html.parser")
    assert all(not page.select("#" + chart_id) for chart_id in RETIRED_CHARTS)
    assert page.select_one("#us-china-favorability")
    assert page.select_one("#us-china-age")
    assert json.loads((tmp_path / "site/downloads/opinions.json").read_text()) == d
    raw = list(csv.DictReader((tmp_path / "site/downloads/opinion-observations.csv").open()))
    plotted = list(csv.DictReader((tmp_path / "site/downloads/opinion-chart-values.csv").open()))
    assert len(raw) == len(d["observations"]) and {r["series_id"] for r in raw} == set(d["series"])
    assert [int(r["value"]) for r in raw if r["series_id"] == "pew_warmth:all"] == [39, 42, 28, 37]
    assert {r["chart_id"] for r in plotted} == set(CHARTS)
    for chart in CHARTS:
        for theme in ("themarginoferror", "substack"):
            svg = BeautifulSoup((tmp_path / f"site/figures/opinions/{theme}/{chart}.svg").read_text(), "html.parser")
            assert svg.svg["data-axis-max"] == "100"
            assert len(svg.select("circle.opinion-point,rect.opinion-point")) == sum(
                len(g["points"]) for g in chart_groups(d, chart))
            with Image.open(tmp_path / f"site/figures/opinions/{theme}/{chart}.png") as png:
                assert png.size == png_dimensions(
                    (tmp_path / f"site/figures/opinions/{theme}/{chart}.svg").read_text())


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
