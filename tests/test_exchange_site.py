import csv
import io
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from PIL import Image, ImageColor

from us_china_exchange.model import change, observation
from us_china_exchange.render import annual_table, build, regional_series, svg_chart, svg_comparison
from us_china_exchange.theme import CHART_THEMES, COMPARISON_GEOGRAPHIES, PARTNER_COLORS, PNG_HEIGHT, PNG_WIDTH


ROOT = Path(__file__).resolve().parents[1]


def test_offline_build_download_round_trip_and_reproducibility(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    result = build(tmp_path)
    canonical = json.loads((ROOT / "data/site/observations.json").read_text())
    site = tmp_path / "site"
    bundle = json.loads((site / "downloads/exchange.json").read_text())
    assert bundle["observations"] == canonical
    assert "iie" in bundle["source_policies"] and "macau_tourism" in bundle["source_policies"]
    assert len(bundle["coverage"]) == 64
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
    assert result["comparisons"] == 11
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    build(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_charts_break_missing_years_and_definition_changes():
    def row(year, comparability="original"):
        return observation("test", "CHN", "USA", "visitors", year, 100,
                           "Visitor trips", comparability=comparability)
    rows = [row(2018), row(2020), row(2021, "new definition")]
    svg = svg_chart(rows)
    doc = ElementTree.fromstring(svg)
    paths = [x for x in doc.iter() if x.get("class") == "data-line"]
    assert paths[0].get("d").count("M") == 3
    assert "Definitions differ" in svg_chart(rows, indexed=True)


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
    assert "zeros are omitted" in "".join(doc.itertext())
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


def test_published_comparisons_match_geography_colors_and_annual_points(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    build(tmp_path)
    rows = json.loads((ROOT / "data/site/observations.json").read_text())
    files = list((tmp_path / "outputs/figures").glob("*/comparisons/*/*.svg"))
    assert len(files) == 44
    for path in files:
        direction, measure, scale = path.stem.removeprefix("chn-hkg-mac-").split("-", 2)
        groups = regional_series(rows, measure, direction)
        doc = ElementTree.fromstring(path.read_text())
        for geo, annual in groups.items():
            points = [x for x in doc.iter() if x.tag.endswith("circle") and x.get("data-geography") == geo]
            expected = {r["period"] for r in annual if r["value"] is not None and
                        (scale != "log" or r["value"] > 0)}
            assert {x.get("data-period") for x in points} == expected
            assert all(x.get("fill") == PARTNER_COLORS[geo] for x in points)
        assert all(x.get("data-geography") != "TWN" for x in doc.iter())
        assert path.with_suffix(".png").read_bytes() == (
            tmp_path / "site/figures" / path.relative_to(tmp_path / "outputs/figures")).with_suffix(".png").read_bytes()
        with Image.open(path.with_suffix(".png")) as image:
            assert image.size == (PNG_WIDTH, PNG_HEIGHT)
        if measure == "goods":
            macau = next(x for x in doc.iter() if x.get("class") == "data-line" and x.get("data-geography") == "MAC")
            assert macau.get("stroke-dasharray") and "Accounting differs" in "".join(doc.itertext())


def test_iie_publication_breaks_pandemic_history_without_losing_valid_headline():
    rows = [r for r in json.loads((ROOT / "data/site/observations.json").read_text())
            if r["series_id"] == "iie:CHN:USA:international_students"]
    doc = ElementTree.fromstring(svg_chart(rows))
    path = next(x for x in doc.iter() if x.get("class") == "data-line")
    assert path.get("d").count("M") == 3
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
        "students", "visitors", "goods_trade", "services_trade", "weibo"}
    assert not list(figures.glob("*.svg"))
    originals = list(figures.glob("*/themarginoferror/*-USA-*.svg"))
    assert len(originals) == 38
    for original in originals:
        doc = ElementTree.fromstring(original.read_text())
        assert "serif" in original.read_text()
        assert any(x.get("class") == "figure-source" for x in doc.iter())
        assert any(x.text == "2000" for x in doc.iter())
        line_color = next(x.get("stroke") for x in doc.iter() if x.get("class") == "data-line")
        for theme, spec in CHART_THEMES.items():
            path = original.parent.parent / theme / original.name
            exported = path.read_bytes()
            site_path = tmp_path / "site/figures" / path.relative_to(figures)
            assert exported == site_path.read_bytes()
            assert path.with_suffix(".png").read_bytes() == site_path.with_suffix(".png").read_bytes()
            with Image.open(path.with_suffix(".png")) as image:
                assert image.size == (PNG_WIDTH, PNG_HEIGHT)
                assert image.getpixel((0, 0)) == (*ImageColor.getrgb(spec["background"]), 255)
                colors = {color for count, color in image.getcolors(PNG_WIDTH * PNG_HEIGHT)}
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
