import csv
import io
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from PIL import Image, ImageChops, ImageColor

from us_china_exchange.model import GEOGRAPHIES, MEASURES, change, observation
from us_china_exchange.render import annual_table, baseline, build, comparison, essay_svg, initial_panel, png_chart, regional_series, svg_chart, svg_comparison
from us_china_exchange.theme import CHART_THEMES, COMPARISON_GEOGRAPHIES, FLOW_COLORS, PARTNER_COLORS, PNG_WIDTH, png_dimensions


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("theme", CHART_THEMES)
def test_standalone_essay_crop_is_tight_and_preserves_data_not_interactive_framing(theme):
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == "ntto_siat:USA:CHN:air_visitors"]
    raw = svg_chart(rows, theme=theme)
    compact = essay_svg(raw)
    original, essay = ElementTree.fromstring(raw), ElementTree.fromstring(compact)
    assert original.get("viewBox") == "0 0 1000 600"
    assert essay.get("data-presentation") == "essay"
    assert "Travel from the U.S. to mainland China" in "".join(essay.itertext())
    assert "U.S. residents" in "".join(essay.itertext())
    assert "2019 baseline" not in "".join(essay.itertext())
    assert any(n.get("class") == "covid-band" for n in essay.iter())
    observations = lambda doc: [dict(n.attrib) for n in doc.iter() if n.get("data-year")]
    assert observations(essay) == observations(original)
    _, _, width, height = map(float, essay.get("viewBox").split())
    with Image.open(io.BytesIO(png_chart(compact))) as image:
        assert image.width == PNG_WIDTH and image.height == round(PNG_WIDTH * height / width)
        assert image.getpixel((0, 0)) == (*ImageColor.getrgb(CHART_THEMES[theme]["background"]), 255)
        background = Image.new("RGB", image.size, ImageColor.getrgb(CHART_THEMES[theme]["background"]))
        bounds = ImageChops.difference(image.convert("RGB"), background).getbbox()
        margins = [bounds[0], bounds[1], image.width - bounds[2], image.height - bounds[3]]
        assert all(.01 <= margin / image.width <= .025 for margin in margins)


@pytest.mark.parametrize("indexed", [False, True])
def test_baseline_units_are_preserved_without_decorative_baseline_annotations(indexed):
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == "ntto_siat:USA:CHN:air_visitors"]
    svg = svg_chart(rows, indexed=indexed)
    assert "2019 baseline" not in svg and 'stroke-dasharray="4 5"' not in svg
    assert ("2019 = 100" in svg) is indexed
    for measure, direction, sid in (
            ("goods", "to_us", "bea:CHN:USA:goods"),
            ("international_students", "to_us", "iie:CHN:USA:international_students")):
        selected = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
                    if r["series_id"] == sid]
        for markup in (svg_chart(selected), svg_comparison(selected, measure, direction)):
            doc = ElementTree.fromstring(markup)
            note = " ".join(n.text or "" for n in doc.iter() if n.get("class") == "figure-source")
            assert "Source" in note
            assert not any(word in note.lower() for word in
                           ("stay unconnected", "not connected", "no invented", "automatic refresh"))
    for logarithmic in (False, True):
        comparison_svg = svg_comparison(rows, "air_visitors", "from_us", logarithmic=logarithmic)
        assert "2019 baseline" not in comparison_svg and 'stroke-dasharray="4 5"' not in comparison_svg


@pytest.mark.parametrize("sid,title", [
    ("ntto:CHN:USA:visitors", "Travel from mainland China to the U.S."),
    ("ntto_siat:USA:CHN:air_visitors", "Travel from the U.S. to mainland China"),
    ("ntto:HKG:USA:visitors", "Travel from Hong Kong to the U.S."),
    ("hktb:USA:HKG:visitors", "Travel from the U.S. to Hong Kong"),
])
def test_travel_titles_follow_the_same_directional_format_across_measures(sid, title):
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == sid]
    svg = ElementTree.fromstring(svg_chart(rows))
    heading = next(n for n in svg.iter() if n.tag.endswith("text") and n.get("font-weight") == "bold")
    assert heading.text == title
    assert next(n for n in svg.iter() if n.tag.endswith("title")).text.startswith(title + ":")
    points = [(int(n.get("data-year")), float(n.get("data-reported-value")))
              for n in svg.iter() if n.tag.endswith("circle")]
    assert points == [(r["year"], r["value"]) for r in sorted(rows, key=lambda r: r["year"])
                      if r["frequency"] == "annual" and r["value"] is not None]


@pytest.mark.parametrize("geo,place", [("CHN", "mainland China"), ("HKG", "Hong Kong"), ("MAC", "Macau")])
@pytest.mark.parametrize("theme", ["themarginoferror", "substack"])
def test_study_abroad_headings_name_the_students_and_destination_with_credit_scope_below(geo, place, theme):
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == f"iie:USA:{geo}:study_abroad"]
    expected = [(r["year"], r["value"]) for r in sorted(rows, key=lambda r: r["year"])
                if r["frequency"] == "annual" and r["value"] is not None]
    for markup in (svg_chart(rows, theme=theme),
                   svg_comparison(rows, "study_abroad", "from_us", theme=theme, geographies=(geo,))):
        svg = ElementTree.fromstring(markup)
        heading = next(n for n in svg.iter() if n.tag.endswith("text") and n.get("font-weight") == "bold")
        assert heading.text == f"U.S. college students studying in {place}"
        assert "course credit" in "".join(svg.itertext())
        assert "Academic-credit" not in heading.text
        assert [(int(n.get("data-year")), float(n.get("data-value")))
                for n in svg.iter() if n.tag.endswith("circle")] == expected


@pytest.mark.parametrize("absolute,percent,expected", [
    (17, 106.25, "+17 (+106.3%)"),
    (-49, -12.25, "\u221249 (-12.3%)"),
    (1.15, 1.15, "+1.15 (+1.1%)"),
    (0.01, 0.01, "+0.01 (+0.0%)"),
])
def test_comparison_percentage_ties_match_browser_rounding(absolute, percent, expected):
    assert comparison({"absolute": absolute, "percent": percent, "reason": ""}, "students") == expected


def test_offline_build_download_round_trip_and_reproducibility(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    result = build(tmp_path)
    canonical = json.loads((ROOT / "data/site/observations.json").read_text())
    site = tmp_path / "site"
    bundle = json.loads((site / "downloads/exchange.json").read_text())
    assert bundle["observations"] == canonical
    assert "iie" in bundle["source_policies"] and "macau_tourism" in bundle["source_policies"]
    assert len(bundle["coverage"]) == (len(GEOGRAPHIES) - 1) * 2 * len(MEASURES)
    assert {(row["origin"], row["destination"], row["measure"]) for row in bundle["coverage"]} == {
        (origin, destination, measure)
        for geo in GEOGRAPHIES if geo != "USA"
        for origin, destination in ((geo, "USA"), ("USA", geo))
        for measure in MEASURES}
    review_text = (ROOT / "data/site/gap_review.csv").read_text()
    assert (site / "downloads/gap-review.csv").read_text() == review_text
    assert bundle["gap_review"] == list(csv.DictReader(io.StringIO(review_text)))
    downloaded = list(csv.DictReader(io.StringIO((site / "downloads/observations.csv").read_text())))
    assert len(downloaded) == len(canonical) == result["observations"]
    for actual, expected in zip(downloaded, canonical):
        assert actual["series_id"] == expected["series_id"]
        assert actual["period"] == expected["period"]
        assert actual["frequency"] == expected["frequency"]
        assert actual["value"] == (str(expected["value"]) if expected["value"] is not None else "")
        assert actual["definition"] == expected["definition"]
        assert actual["raw_sha256"] == expected["raw_sha256"]
    page = BeautifulSoup((site / "index.html").read_text(), "html.parser")
    assert "automatic retrieval is paused" in page.select_one(".source-restrictions").text
    assert "Commercial reuse permission has not been verified" in page.select_one(".source-restrictions").text
    assert len(page.select("#all-values details")) == result["series"]
    assert page.select_one("noscript")
    assert page.select_one("#all-values table")
    assert page.select_one('#coverage a[href="downloads/gap-review.csv"]')
    for a in page.select('a[href]'):
        href = a["href"]
        if not href.startswith(("https://", "#")):
            assert (site / href).is_file(), href
    gallery = BeautifulSoup((site / "figures/index.html").read_text(), "html.parser")
    for a in gallery.select("a[href]"):
        assert (site / "figures" / a["href"]).is_file()
    comparisons = BeautifulSoup((site / "comparisons.html").read_text(), "html.parser")
    assert "automatic retrieval is paused" in comparisons.select_one(".source-restrictions").text
    for node in comparisons.select("a[href],img[src]"):
        target = node.get("href") or node["src"]
        if not target.startswith(("https://", "#")):
            assert (site / target).is_file()
    historical_panel = comparisons.select_one("#historical_students-to_us")
    assert "coverage qualified" in historical_panel.h2.get_text()
    assert len(historical_panel.select(".comparison-chart")) == 2
    assert result["comparisons"] - 1 == 13
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    build(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("value,label", [(434_000_000, "$434.0M"), (0, "$0")])
def test_single_verified_year_is_a_labelled_snapshot_not_a_left_edge_trend(value, label):
    row = observation("ustr", "USA", "MAC", "services", 2025, value,
                      "Estimated cross-border services", status="estimated")
    doc = ElementTree.fromstring(svg_chart([row]))
    bar = next(n for n in doc.iter() if n.get("class") == "snapshot-bar")
    assert float(bar.get("x")) + float(bar.get("width")) / 2 == (115 + 950) / 2
    assert (float(bar.get("height")) > 0) == (value > 0)
    text = " ".join(doc.itertext())
    assert label in text and "Annual snapshot for 2025" in text
    assert "2026" not in text
    assert not any(n.get("class") == "data-line" for n in doc.iter())


def test_charts_break_missing_years_and_definition_changes():
    def row(year, comparability="original"):
        return observation("test", "CHN", "USA", "visitors", year, 100,
                           "Visitor trips", comparability=comparability)
    rows = [row(2018), row(2020), row(2021, "new definition")]
    svg = svg_chart(rows)
    doc = ElementTree.fromstring(svg)
    assert not [x for x in doc.iter() if x.get("class") == "data-line"]
    bars = [x for x in doc.iter() if x.get("class") == "annual-column"]
    assert [int(x.get("data-year")) for x in bars] == [2018, 2020, 2021]
    assert "Population-definition changes: 2021" in "".join(doc.itertext())
    assert "Definitions differ" in svg_chart([row(2019)] + rows, indexed=True)


@pytest.mark.parametrize("measure", ["goods", "services", "visitors", "air_visitors",
                                     "international_students", "enrolled_students", "study_abroad", "degree_students"])
def test_annual_trade_columns_preserve_calendar_gaps_zero_values_and_index_lines(measure):
    rows = [observation("test", "CHN", "USA", measure, year, value, "Annual trade",
                        status="missing" if value is None else "observed")
            for year, value in [(2020, 100), (2022, None), (2023, 0), (2025, 300)]]
    doc = ElementTree.fromstring(svg_chart(rows))
    assert doc.get("data-plot-style") == "columns"
    bars = [n for n in doc.iter() if n.get("class") == "annual-column"]
    assert [(int(n.get("data-year")), float(n.get("data-value"))) for n in bars] == [
        (2020, 100), (2023, 0), (2025, 300)]
    assert float(bars[1].get("height")) == 0
    centers = [float(n.get("x")) + float(n.get("width")) / 2 for n in bars]
    assert (centers[1] - centers[0]) / (centers[2] - centers[1]) == pytest.approx(3 / 2, abs=.001)
    assert float(bars[0].get("x")) > 115
    assert float(bars[-1].get("x")) + float(bars[-1].get("width")) < 950
    assert not any(n.get("class") == "data-line" for n in doc.iter())
    indexed_rows = rows + [observation("test", "CHN", "USA", measure, 2019, 100, "Annual trade")]
    indexed = ElementTree.fromstring(svg_chart(indexed_rows, indexed=True))
    assert indexed.get("data-plot-style") is None
    assert not any(n.get("class") == "annual-column" for n in indexed.iter())
    assert any(n.get("class") == "data-line" for n in indexed.iter())


@pytest.mark.parametrize("measure", ["goods", "services", "visitors", "international_students"])
@pytest.mark.parametrize("theme", ["themarginoferror", "substack"])
def test_baseline_percentages_and_indexes_use_2019_not_the_2020_count(measure, theme):
    rows = [observation("test", "CHN", "USA", measure, year, value, "Comparable counts")
            for year, value in [(2019, 80), (2020, 20), (2025, 120)]]
    assert baseline(rows)["value"] == 80
    panel = BeautifulSoup(initial_panel(rows), "html.parser")
    assert panel.select_one("#baseline-label").text == "Change since 2019"
    assert "(+50.0%)" in panel.select_one("#baseline-change").text
    indexed = ElementTree.fromstring(svg_chart(rows, indexed=True, theme=theme))
    assert "2019 = 100" in "".join(indexed.itertext())
    current = next(n for n in indexed.iter() if n.tag.endswith("circle") and n.get("data-year") == "2025")
    assert float(current.get("data-value")) == 150
    assert float(current.get("data-reported-value")) == 120
    endpoint = next(n for n in indexed.iter() if n.get("class") == "end-label")
    assert endpoint.text == "150"


@pytest.mark.parametrize("reference,reason", [(None, "Baseline unavailable"),
                                             (0, "percentage undefined"),
                                             ("different", "Definitions or periods differ")])
def test_missing_zero_or_incompatible_2019_does_not_fall_back_to_2020(reference, reason):
    rows = [observation("test", "CHN", "USA", "visitors", year, value, "Comparable counts")
            for year, value in [(2020, 20), (2025, 120)]]
    if reference is not None:
        rows.append(observation("test", "CHN", "USA", "visitors", 2019,
                                80 if reference == "different" else reference, "Comparable counts",
                                comparability="other" if reference == "different" else None))
    panel = BeautifulSoup(initial_panel(rows), "html.parser")
    assert panel.select_one("#baseline-label").text == "Change since 2019"
    assert reason in panel.select_one("#baseline-change").text
    assert "<svg" not in svg_chart(rows, indexed=True)


@pytest.mark.parametrize("theme", ["substack", "themarginoferror"])
def test_bilateral_direction_colors_and_covid_band_match_the_annual_calendar(theme):
    def chart(origin, destination, years):
        rows = [observation("test", origin, destination, "enrolled_students", year, 100,
                            "Annual students") for year in years]
        return ElementTree.fromstring(svg_chart(rows, theme=theme))
    inbound = chart("CHN", "USA", [2019, 2020, 2021, 2022, 2023])
    outbound = chart("USA", "CHN", [2019, 2020, 2021, 2022, 2023])
    marks = lambda doc, cls: [n for n in doc.iter() if n.get("class") == cls]
    assert {n.get("fill") for n in marks(inbound, "annual-column")} == {"#7B2D26"}
    assert {n.get("fill") for n in marks(outbound, "annual-column")} == {"#3D6F8C"}
    band = marks(inbound, "covid-band")[0]
    assert float(band.get("x")) == pytest.approx(115 + 835 / 5, abs=.01)
    assert float(band.get("width")) == pytest.approx(835 * 3 / 5, abs=.01)
    assert "not a universal travel ban" in "".join(inbound.itertext())
    assert not marks(chart("USA", "CHN", [2016, 2018]), "covid-band")
    assert not marks(chart("USA", "CHN", [2024, 2025]), "covid-band")


@pytest.mark.parametrize("theme", ["substack", "themarginoferror"])
@pytest.mark.parametrize("direction", ["to_us", "from_us"])
@pytest.mark.parametrize("measure,expected", [
    ("goods", True), ("services", False), ("enrolled_students", True), ("visitors", True),
])
def test_covid_context_distinguishes_goods_from_travel_in_both_export_layouts(theme, direction, measure, expected):
    origin, destination = ("CHN", "USA") if direction == "to_us" else ("USA", "CHN")
    rows = [observation("test", origin, destination, measure, year, 100, "Reported annual level")
            for year in range(2019, 2024)]
    for markup in (svg_chart(rows, theme=theme), svg_chart(rows, theme=theme, indexed=True),
                   svg_comparison(rows, measure, direction, theme=theme),
                   svg_comparison(rows, measure, direction, theme=theme, logarithmic=True)):
        doc = ElementTree.fromstring(markup)
        assert any(n.get("class") == "covid-band" for n in doc.iter()) is expected
        labels = [n.text for n in doc.iter() if n.get("class") == "covid-label"]
        if measure == "goods":
            assert labels == ["COVID-19 period, 2020-22"]
            band = next(n for n in doc.iter() if n.get("class") == "covid-band")
            assert (band.get("data-start-year"), band.get("data-end-year")) == ("2020", "2022")
            low, high = ((2018.5, 2023.5) if doc.get("data-plot-style") == "columns"
                         else (2019, 2023))
            assert float(band.get("x")) == pytest.approx(
                115 + (2019.5 - low) / (high - low) * 835, abs=.01)
            assert float(band.get("width")) == pytest.approx(3 / (high - low) * 835, abs=.01)
            assert "travel" not in next(n for n in doc.iter() if n.get("class") == "covid-context").find(
                "{http://www.w3.org/2000/svg}title").text
        elif expected:
            assert labels == ["COVID travel restrictions, 2020-22"]


def test_export_axes_preserve_fractional_thousands_instead_of_repeating_rounded_ticks():
    rows = [observation("test", "USA", "HKG", "study_abroad", year, value, "Credit participation")
            for year, value in [(2010, 1900), (2020, 1200), (2025, 2170)]]
    doc = ElementTree.fromstring(svg_chart(rows))
    labels = [node.text for node in doc.iter() if node.tag.endswith("text") and node.get("x") == "100"]
    assert labels == ["0", "500", "1k", "1.5k", "2k", "2.5k"]
    assert len(labels) == len(set(labels))
    assert [(int(node.get("data-year")), float(node.get("data-value"))) for node in doc.iter()
            if node.tag.endswith("circle")] == [(r["year"], r["value"]) for r in rows]


@pytest.mark.parametrize("geo,segments", [("CHN", 1), ("HKG", 2)])
def test_air_travel_uses_its_own_history_and_pre_pandemic_index(geo, segments):
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == f"ntto_siat:USA:{geo}:air_visitors" and r["frequency"] == "annual"]
    assert {r["year"] for r in rows} == set(range(2000, 2026)) - ({2021} if geo == "HKG" else set())
    if geo == "CHN":
        assert next(r for r in rows if r["year"] == 2018)["value"] == 1_587_000
        assert next(r for r in rows if r["year"] == 2020)["value"] == 89_000
        assert next(r for r in rows if r["year"] == 2021)["value"] == 5_000
    doc = ElementTree.fromstring(svg_chart(rows, indexed=True))
    text = " ".join(doc.itertext())
    assert "2019 = 100" in text and "2020 baseline" not in text
    path = next(n for n in doc.iter() if n.get("class") == "data-line")
    assert path.get("d").count("M") == segments
    if geo == "CHN":
        label = next(n for n in doc.iter() if n.get("class") == "end-label")
        assert label.text == "54"


def test_comparison_colors_gaps_and_taiwan_exclusion():
    rows = [observation("test", geo, "USA", "visitors", year, 100 + year - 2018,
                        "Trips", comparability="new" if year == 2021 else "old")
            for geo in COMPARISON_GEOGRAPHIES for year in [2018, 2020, 2021]]
    svg = svg_comparison(rows, "visitors", "to_us")
    taiwan = observation("test", "TWN", "USA", "visitors", 2040, 10 ** 15, "Trips")
    assert svg_comparison(rows + [taiwan], "visitors", "to_us") == svg
    doc = ElementTree.fromstring(svg)
    lines = [x for x in doc.iter() if x.get("class") == "data-line"]
    assert {x.get("data-geography") for x in lines} == set(COMPARISON_GEOGRAPHIES)
    for path in lines:
        assert path.get("stroke") == PARTNER_COLORS[path.get("data-geography")]
        assert path.get("d").count("M") == 3
    assert "Taiwan" not in svg and "TWN" not in svg


def test_log_comparison_omits_zeros_and_preserves_missing_series():
    rows = [observation("test", "CHN", "USA", "visitors", year, value, "Trips")
            for year, value in [(2019, 10), (2020, 0), (2021, 100)]]
    doc = ElementTree.fromstring(svg_comparison(rows, "visitors", "to_us", logarithmic=True))
    points = [x for x in doc.iter() if x.tag.endswith("circle")]
    assert {x.get("data-period") for x in points} == {"2019", "2021"}
    path = next(x for x in doc.iter() if x.get("class") == "data-line")
    assert path.get("d").count("M") == 2
    assert "log scale" in "".join(doc.itertext())
    assert "*No verified series: Hong Kong, Macau" in "".join(doc.itertext())
    assert "No verified annual" in svg_comparison(rows, "services", "from_us")


def test_comparisons_reject_conflicting_sources_or_units():
    rows = [observation("test", "CHN", "USA", "goods", 2020, 100, "Goods")]
    conflict = observation("other", "CHN", "USA", "goods", 2020, 100, "Goods")
    with pytest.raises(ValueError, match="one source series"):
        svg_comparison(rows + [conflict], "goods", "to_us")
    wrong_unit = observation("test", "HKG", "USA", "goods", 2020, 100, "Goods", unit="students")
    with pytest.raises(ValueError, match="units and period bases"):
        svg_comparison(rows + [wrong_unit], "goods", "to_us")


def test_macau_comparison_prefers_consistent_bea_history_without_erasing_ustr_vintages():
    from us_china_exchange.model import primary_observations

    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    snapshots = [r for r in rows if r["source_id"] == "ustr"]
    assert len(snapshots) == 4 and {r["year"] for r in snapshots} == {2024, 2025}
    primary = primary_observations(rows)
    assert not any(r["source_id"] == "ustr" for r in primary)
    for direction, origin in (("to_us", "MAC"), ("from_us", "USA")):
        selected = [r for r in primary if r["source_id"] == "bea_expanded" and r["origin"] == origin]
        assert {r["year"] for r in selected} == set(range(2018, 2026))
        doc = ElementTree.fromstring(svg_comparison(rows, "services", direction))
        macau = [p for p in doc.iter() if p.tag.endswith("circle") and p.get("data-geography") == "MAC"]
        assert len(macau) == 8 and all(p.get("data-series-id").startswith("bea_expanded:") for p in macau)
    assert len(primary_observations(snapshots)) == 4


def test_published_comparisons_match_geography_colors_and_annual_points(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    obsolete = (tmp_path / "outputs/figures/visitors/comparisons/substack/"
                "chn-hkg-mac-from_us-visitors-levels.svg")
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text("Obsolete combined visitor chart")
    build(tmp_path)
    assert not obsolete.exists()
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    files = list((tmp_path / "outputs/figures").glob("*/comparisons/*/*.svg"))
    historical = [path for path in files if "-historical_students-" in path.name]
    assert {(path.parent.name, path.stem) for path in historical} == {
        (theme, f"hkg-mac-to_us-historical_students-{scale}")
        for theme in CHART_THEMES for scale in ("levels", "log")}
    assert len(files) - len(historical) == 96
    for path in files:
        doc = ElementTree.fromstring(path.read_text())
        if path in historical:
            assert "coverage qualified" in " ".join(doc.itertext())
        geographies = doc.get("data-geographies", "CHN HKG MAC").split()
        prefix = "-".join(geo.lower() for geo in geographies)
        direction, measure, scale = path.stem.removeprefix(prefix + "-").split("-", 2)
        groups = {geo: annual for geo, annual in regional_series(rows, measure, direction).items()
                  if geo in geographies}
        assert geographies in [["CHN"], ["HKG", "MAC"]]
        for geo, annual in groups.items():
            points = [x for x in doc.iter() if x.tag.endswith("circle") and x.get("data-geography") == geo]
            expected = {r["period"] for r in annual if r["value"] is not None and
                        (scale != "log" or r["value"] > 0)}
            assert {x.get("data-period") for x in points} == expected
            assert all(x.get("fill") == FLOW_COLORS[direction][geo] for x in points)
        assert all(x.get("data-geography") != "TWN" for x in doc.iter())
        assert {x.get("data-geography") for x in doc.iter() if x.tag.endswith("circle")} <= set(geographies)
        assert path.with_suffix(".png").read_bytes() == (
            tmp_path / "site/figures" / path.relative_to(tmp_path / "outputs/figures")).with_suffix(".png").read_bytes()
        with Image.open(path.with_suffix(".png")) as image:
            assert image.size == png_dimensions(path.read_text())
        if measure == "goods" and "MAC" in geographies:
            macau = next(x for x in doc.iter() if x.get("class") == "data-line" and x.get("data-geography") == "MAC")
            assert macau.get("stroke-dasharray") and "Accounting differs" in "".join(doc.itertext())


def test_iie_student_columns_preserve_values_periods_and_definition_breaks():
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == "iie:CHN:USA:international_students"]
    doc = ElementTree.fromstring(svg_chart(rows))
    assert doc.get("data-plot-style") == "columns"
    bars = [x for x in doc.iter() if x.get("class") == "annual-column"]
    annual_rows = sorted((r for r in rows if r["frequency"] == "annual" and r["value"] is not None),
                         key=lambda r: r["year"])
    assert [(int(b.get("data-year")), float(b.get("data-value"))) for b in bars] == [
        (r["year"], r["value"]) for r in annual_rows]
    assert [next(x.iter("{http://www.w3.org/2000/svg}title")).text for x in bars] == [
        r["period"] + ": " + f'{r["value"]:,}' for r in annual_rows]
    assert not any(x.get("class") == "data-line" for x in doc.iter())
    note = " ".join(x.text or "" for x in doc.iter() if x.get("class") == "figure-source")
    assert "2020/21" in note and "2023/24" in note
    assert "Definitions differ" in svg_chart(rows, indexed=True)
    annual = {r["year"]: r for r in rows}
    assert change(annual[2025], annual[2020])["percent"] is not None
    table = BeautifulSoup(annual_table(rows), "html.parser")
    assert table.select_one("thead th:last-child").text == "Population definition"
    pandemic = next(r for r in table.select("tbody tr") if r.th.text == "2020/21")
    assert "expanded pandemic population" in pandemic.select("td")[-1].text
    restored = next(r for r in table.select("tbody tr") if r.th.text == "2023/24")
    assert "standard temporary-visa population" in restored.select("td")[-1].text


def test_figure_background_variants_preserve_data_and_foreground(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    build(tmp_path)
    figures = tmp_path / "outputs/figures"
    assert {p.name for p in figures.iterdir() if p.is_dir()} == {
        "students", "visitors", "goods_trade", "services_trade", "weibo", "language_learning", "business_presence", "immigration", "opinions"}
    assert not list(figures.glob("*.svg"))
    originals = list(figures.glob("*/themarginoferror/*-USA-*.svg"))
    data = json.loads((ROOT / "data/site/observations.json").read_text())
    assert len(originals) == len({r["series_id"] for r in data if r["frequency"] == "annual" and r["value"] is not None})
    for original in originals:
        doc = ElementTree.fromstring(original.read_text())
        assert "serif" in original.read_text()
        assert any(x.get("class") == "figure-source" for x in doc.iter())
        sid = next(r["series_id"] for r in data if r["series_id"].replace(":", "-") == original.stem)
        first = min(r["year"] for r in data if r["series_id"] == sid and r["frequency"] == "annual" and r["value"] is not None)
        assert any(x.text == str(first) for x in doc.iter())
        bars = [x for x in doc.iter() if x.get("class") in {"annual-column", "snapshot-bar"}]
        line_color = (bars[0].get("fill") if bars else
                      next(x.get("stroke") for x in doc.iter() if x.get("class") == "data-line"))
        for theme, spec in CHART_THEMES.items():
            path = original.parent.parent / theme / original.name
            exported = path.read_bytes()
            site_path = tmp_path / "site/figures" / path.relative_to(figures)
            assert exported == site_path.read_bytes()
            assert path.with_suffix(".png").read_bytes() == site_path.with_suffix(".png").read_bytes()
            with Image.open(path.with_suffix(".png")) as image:
                assert image.size == png_dimensions(path.read_text())
                assert image.getpixel((0, 0)) == (*ImageColor.getrgb(spec["background"]), 255)
                colors = {color for count, color in image.getcolors(image.width * image.height)}
                assert (*ImageColor.getrgb(line_color), 255) in colors
            variant = ElementTree.fromstring(exported)
            background = next(x for x in variant.iter() if x.get("class") == "chart-background")
            assert background.get("fill") == spec["background"]
            background.set("fill", "#F7F5F0")
            assert ElementTree.tostring(variant) == ElementTree.tostring(doc)


def test_chart_build_removes_only_known_legacy_exports(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    path = tmp_path / "data/site/observations.json"
    rows = [r for r in json.loads(path.read_text()) if r["series_id"] == "bea:USA:TWN:goods"]
    path.write_text(json.dumps(rows))
    figures = tmp_path / "outputs/figures"
    figures.mkdir(parents=True)
    legacy = figures / "bea-USA-TWN-goods.svg"
    legacy.write_text("Previous generated figure")
    unrelated = figures / "custom.svg"
    unrelated.write_text("User-owned figure")
    build(tmp_path)
    assert not legacy.exists()
    assert unrelated.read_text() == "User-owned figure"
    assert (figures / "goods_trade/substack/bea-USA-TWN-goods.png").is_file()


@pytest.mark.parametrize("correction", ["suppressed", "removed", "zero"])
def test_corrected_series_cannot_leave_stale_individual_or_comparison_exports(tmp_path, correction):
    output = tmp_path / "data/site"
    output.mkdir(parents=True)
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] in {"bea:USA:CHN:goods", "iie:CHN:USA:international_students"}
            and r["frequency"] == "annual" and r["year"] == 2020]
    path = output / "observations.json"
    path.write_text(json.dumps(rows))
    (output / "sources.json").write_text((ROOT / "data/site/sources.json").read_text())
    build(tmp_path)
    figures = tmp_path / "outputs/figures"
    original = {p.relative_to(figures) for p in (figures / "goods_trade").rglob("*") if p.is_file()}
    assert len(original) == 12
    for directory in (figures, tmp_path / "site/figures"):
        (directory / "goods_trade/substack/custom.svg").write_text("User-owned figure")
    for row in rows:
        if row["measure"] == "goods":
            row.update(value=0 if correction == "zero" else None,
                       status="observed" if correction == "zero" else "suppressed")
    if correction == "removed":
        rows = [r for r in rows if r["measure"] != "goods"]
    path.write_text(json.dumps(rows))
    build(tmp_path)
    for relative in original:
        expected = correction == "zero" and "-log." not in relative.name
        for directory in (figures, tmp_path / "site/figures"):
            assert (directory / relative).is_file() == expected
    for directory in (figures, tmp_path / "site/figures"):
        assert (directory / "goods_trade/substack/custom.svg").read_text() == "User-owned figure"
    assert list((figures / "students").rglob("*.png"))


def test_first_build_without_default_source_uses_available_series(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    path = tmp_path / "data/site/observations.json"
    rows = [r for r in json.loads(path.read_text()) if r["series_id"] == "bea:USA:TWN:goods"]
    path.write_text(json.dumps(rows))
    build(tmp_path)
    page = BeautifulSoup((tmp_path / "site/index.html").read_text(), "html.parser")
    assert page.select_one("#geography option[selected]")["value"] == "TWN"
    assert page.select_one("#direction option[selected]")["value"] == "from_us"
    assert page.select_one("#measure option[selected]")["value"] == "goods"
    assert page.select_one("#series-title").text == "United States \u2192 Taiwan"
    assert page.select_one("#figure-link a")["href"] == "figures/goods_trade/themarginoferror/bea-USA-TWN-goods.png"
