#!/usr/bin/env python3
"""Build current Business evidence and its complete historical count archive."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bs4 import BeautifulSoup
from build_exchange_publication import decorate
from us_china_exchange.business_analysis import CHARTS as OLD_CHARTS, RETIRED_CHARTS, validate_business_data
from us_china_exchange.business_current import CHARTS, build_current_business, validate
from us_china_exchange.model import json_text
from us_china_exchange.theme import CHART_THEMES, FONT_FILES


def build_publication(source, output, revision, canonical="https://www.themarginoferror.com/china-us-relations/"):
    data = validate_business_data(json.loads((source / "data/site/business_presence.json").read_text()))
    current = validate(json.loads((source / "data/site/business_current.json").read_text()))
    url = urlsplit(canonical)
    if url.scheme != "https" or url.netloc != "www.themarginoferror.com" or not url.path.endswith("/"):
        raise ValueError("Publication canonical URL must be on the publication's HTTPS site")
    with tempfile.TemporaryDirectory(prefix="china-business-publication-") as work:
        root = Path(work)
        (root / "data/site").mkdir(parents=True)
        (root / "data/site/business_current.json").write_text(json_text(current))
        count = build_current_business(root, data, defaultdict(list))
        site = root / "site"
        static = source / "src/us_china_exchange/static"
        assets = site / "assets"
        (assets / "fonts").mkdir(parents=True)
        for name in ["style.css", "publication.css", "publication.js"]:
            shutil.copyfile(static / name, assets / name)
        for name in FONT_FILES + ("LICENSE",):
            shutil.copyfile(static / "fonts" / name, assets / "fonts" / name)
        decorate(site, "business-presence.html", {sid: d["label"] for sid, d in current["series"].items()}, revision)
        soup = BeautifulSoup((site / "business-presence.html").read_text(), "html.parser")
        soup.select_one('link[rel="canonical"]')["href"] = canonical
        for link in soup.select(".analysis-tabs a"):
            if link.has_attr("aria-current"):
                link["href"] = "index.html"
            elif not link["href"].startswith("https://"):
                link.decompose()
        (site / "index.html").write_text(str(soup), encoding="utf-8")
        (site / "business-presence.html").unlink()
        files = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in site.rglob("*") if p.is_file() and p.suffix != ".html"}
        manifest = {"version": 1, "source_repository": "hanshanley/china-us-relation-change",
                    "source_revision": revision, "canonical_url": canonical, "business_charts": count,
                    "observations": len(current["observations"]), "historical_observations": len(data["observations"]),
                    "dataset_sha256": files["downloads/business-current.json"],
                    "scope": "Business investment histories and separate company surveys, with historical counts archived; no other project datasets",
                    "files": files}
        (site / "publication-manifest.json").write_text(json_text(manifest), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        for chart in set(CHARTS) | set(OLD_CHARTS) | RETIRED_CHARTS:
            for theme in CHART_THEMES:
                for suffix in ("svg", "png", "website.png"):
                    relative = Path("figures/business_presence") / theme / f"{chart}.{suffix}"
                    if not (site / relative).is_file():
                        (output / relative).unlink(missing_ok=True)
        shutil.copytree(site, output, dirs_exist_ok=True)
        for relative in ("assets/business-publication.css", "assets/business-publication.js", "downloads/business-chart-values.csv"):
            (output / relative).unlink(missing_ok=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    manifest = build_publication(ROOT, args.output, revision)
    print(json_text({k: v for k, v in manifest.items() if k != "files"}), end="")
