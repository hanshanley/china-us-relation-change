import csv
import io
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from us_china_exchange.model import observation
from us_china_exchange.render import build, svg_chart


ROOT = Path(__file__).resolve().parents[1]


def test_offline_build_download_round_trip_and_reproducibility(tmp_path):
    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    result = build(tmp_path)
    canonical = json.loads((ROOT / "data/site/observations.json").read_text())
    site = tmp_path / "site"
    bundle = json.loads((site / "downloads/exchange.json").read_text())
    assert bundle["observations"] == canonical
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
    assert len(page.select("#all-values details")) == result["series"]
    assert page.select_one("noscript")
    assert page.select_one("#all-values table")
    for a in page.select('a[href]'):
        href = a["href"]
        if not href.startswith(("https://", "#")):
            assert (site / href).is_file(), href
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
    paths = [x for x in doc.iter() if x.tag.endswith("path") and x.get("stroke") == "#24586d"]
    assert paths[0].get("d").count("M") == 3
    assert "Definitions differ" in svg_chart(rows, indexed=True)


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
    assert page.select_one("#figure-link a")["href"] == "figures/bea-USA-TWN-goods.svg"
