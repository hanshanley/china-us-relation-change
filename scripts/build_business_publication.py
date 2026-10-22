#!/usr/bin/env python3
"""Build only the public business histories; never stage other project datasets."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup
from us_china_exchange.business_analysis import CHARTS, RETIRED_CHARTS, build_business, validate_business_data
from us_china_exchange.model import json_text
from us_china_exchange.theme import CHART_THEMES, FONT_FILES


def build_publication(source, output, revision, canonical="https://www.themarginoferror.com/china-us-relations/"):
    data = validate_business_data(json.loads((source / "data/site/business_presence.json").read_text()))
    url = urlsplit(canonical)
    if url.scheme != "https" or url.netloc != "www.themarginoferror.com" or not url.path.endswith("/"):
        raise ValueError("Publication canonical URL must be on the publication's HTTPS site")
    with tempfile.TemporaryDirectory(prefix="china-business-publication-") as work:
        root = Path(work)
        count = build_business(root, data, defaultdict(list), publication=True)
        site = root / "site"
        static = source / "src/us_china_exchange/static"
        assets = site / "assets"
        (assets / "fonts").mkdir(parents=True)
        for name in ["style.css", "business-publication.css", "business-publication.js"]:
            shutil.copyfile(static / name, assets / name)
        for name in FONT_FILES + ("LICENSE",):
            shutil.copyfile(static / "fonts" / name, assets / "fonts" / name)
        soup = BeautifulSoup((site / "business-presence.html").read_text(), "html.parser")
        for attrs in [{"rel": "canonical", "href": canonical},
                      {"rel": "stylesheet", "href": "assets/business-publication.css"}]:
            soup.head.append(soup.new_tag("link", attrs=attrs))
        soup.head.append(soup.new_tag("meta", attrs={
            "name": "description", "content": "Explore annual U.S. and European business presence in China, with exact values, source definitions and complete downloads."}))
        soup.body["class"] = ["publication-page"]
        masthead = BeautifulSoup(
            '<a class="publication-skip" href="#business-controls">Skip to the analysis</a>'
            '<header class="publication-header"><div class="publication-edition" aria-hidden="true">'
            '<span>Independent notes on systems and society</span><span>Est. 2021</span></div>'
            '<div class="publication-masthead"><a class="publication-wordmark" href="https://www.themarginoferror.com/" '
            'aria-label="The Margin of Error, home"><span>The</span><span>Margin <i>of</i> Error</span></a>'
            '<nav aria-label="Primary navigation"><a href="https://www.themarginoferror.com/">Latest</a>'
            '<a href="https://www.themarginoferror.com/archive/">Archive</a>'
            '<a href="https://www.themarginoferror.com/interactive-analysis/">Interactive analysis</a>'
            '<a href="https://www.themarginoferror.com/about/">About</a></nav></div></header>',
            "html.parser")
        for node in reversed(list(masthead.contents)):
            soup.body.insert(0, node)
        main = soup.find("main")
        main["id"] = "analysis"
        soup.select_one(".publication-skip")["href"] = "#analysis"
        footer = soup.new_tag("footer", attrs={"class": "publication-footer"})
        footer.append(BeautifulSoup(
            '<p>The Margin of Error · Hans W. A. Hanley. '
            '<a href="https://github.com/hanshanley/china-us-relation-change">Analysis code and source data</a> · '
            '<a href="publication-manifest.json">Publication provenance</a></p>', "html.parser"))
        soup.select_one(".page").append(footer)
        script = soup.new_tag("script", attrs={"src": "assets/business-publication.js", "defer": ""})
        soup.body.append(script)
        (site / "index.html").write_text(str(soup), encoding="utf-8")
        (site / "business-presence.html").unlink()
        files = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in site.rglob("*") if p.is_file() and p.suffix != ".html"}
        manifest = {"version": 1, "source_repository": "hanshanley/china-us-relation-change",
                    "source_revision": revision, "canonical_url": canonical, "business_charts": count,
                    "observations": len(data["observations"]), "dataset_sha256": files["downloads/business-presence.json"],
                    "scope": "China-hosted business histories only; no exchange, language-learning or private Weibo datasets",
                    "files": files}
        (site / "publication-manifest.json").write_text(json_text(manifest), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        for chart in set(CHARTS) | RETIRED_CHARTS:
            for theme in CHART_THEMES:
                for suffix in ("svg", "png", "website.png"):
                    relative = Path("figures/business_presence") / theme / f"{chart}.{suffix}"
                    if not (site / relative).is_file():
                        (output / relative).unlink(missing_ok=True)
        shutil.copytree(site, output, dirs_exist_ok=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    manifest = build_publication(ROOT, args.output, revision)
    print(json_text({k: v for k, v in manifest.items() if k != "files"}), end="")
