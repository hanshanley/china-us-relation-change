"""Dated primary-source estimates, deliberately outside annual enrollment lines."""

import csv
import html
import io
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .language_sources import pdf_text
from .model import json_text
from .pipeline import write_atomic


DOCUMENTS = {
    "ncuscr_2023": ("https://www.ncuscr.org/podcast/cth-2023-nicholas-burns/",
                    "National Committee on U.S.–China Relations, original ambassador transcript",
                    r"We now have, we think, about 350"),
    "brookings_2023": ("https://www.brookings.edu/wp-content/uploads/2023/12/fp_20231215_burns_china_transcript.pdf",
                      "Brookings, December 15, 2023 ambassador event transcript", r"700\s+American students now"),
    "official_post_2024": ("https://commons.wikimedia.org/wiki/File:Ambassador_Burns_walking_with_Yunnan_University_faculty_outside_university_building.jpg",
                           "Official ambassador post, reproduced in its public-domain Wikimedia Commons record",
                           r"current 880\b"),
    "burns_2025": ("https://www.livemint.com/global/us-china-relations-future-competition-us-china-xi-jinping-adversary-china-military-build-up-us-china-tech-war-11744717772424.html",
                   "Nicholas Burns, firsthand commentary, licensed Economist republication in Mint",
                   r"just over 1,100 today"),
    "uscet_2026": ("https://uscet.org/wp-content/uploads/2026/03/USCET-Working-Group-Report.pdf",
                   "US–China Education Trust, original Working Group Report, March 2026",
                   r"Fewer than 2,000 Americans per year"),
}


def collect(client):
    sources = {}
    for key, (url, name, pattern) in DOCUMENTS.items():
        body, asset = client.get(url)
        plain = "\n".join(pdf_text(body)) if body.startswith(b"%PDF") else BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
        if not re.search(pattern, plain):
            raise ValueError("Reviewed student estimate changed: " + key)
        sources[key] = {"name": name, "asset": asset}
    rows = [
        {"id": "burns_oct2023", "statement_date": "2023-10-11", "reference_period": "Contemporaneous estimate; precise measurement date not supplied",
         "measurement": "point_in_time_statement", "qualifier": "about", "value": 350, "bound": None, "source_id": "ncuscr_2023"},
        {"id": "burns_dec2023", "statement_date": "2023-12-15", "reference_period": "Contemporaneous estimate; precise measurement date not supplied",
         "measurement": "point_in_time_statement", "qualifier": "as_stated", "value": 700, "bound": None, "source_id": "brookings_2023"},
        {"id": "burns_may2024", "statement_date": "2024-05-13", "reference_period": "Current figure in official post; archived reproduction",
         "measurement": "point_in_time_statement", "qualifier": "as_stated", "value": 880, "bound": None, "source_id": "official_post_2024"},
        {"id": "burns_apr2025", "statement_date": "2025-04-15", "reference_period": "Figure described as current in the dated republication; exact measurement date unspecified",
         "measurement": "point_in_time_statement", "qualifier": "greater_than", "value": None, "bound": 1100, "source_id": "burns_2025"},
        {"id": "uscet_mar2026", "statement_date": "2026-03-23", "reference_period": "Current annual participation estimate reported March 2026, not a measured calendar-2026 total",
         "measurement": "annual_participation_estimate", "qualifier": "less_than", "value": None, "bound": 2000, "source_id": "uscet_2026"},
    ]
    return validate({
        "version": 1, "observations": rows, "sources": sources,
        "scope": "Americans studying in China as described by each source. Formal eligibility and counting methods are not supplied consistently.",
        "comparability": "Dated statements and one annual-participation estimate, not a harmonized enrollment census. "
                         "Do not join them to the MOE annual degree/non-degree counts or academic-credit study-abroad line. "
                         "Statement dates are not invented measurement dates. Bounds remain bounds, not exact point estimates.",
    })


def validate(data):
    if (set(data) != {"version", "observations", "sources", "scope", "comparability"} or data["version"] != 1
            or not data["observations"] or not data["sources"] or not data["scope"] or not data["comparability"]):
        raise ValueError("Invalid student-estimate dataset")
    seen = set()
    for row in data["observations"]:
        if row["id"] in seen or row["source_id"] not in data["sources"]:
            raise ValueError("Student-estimate identity/provenance mismatch")
        seen.add(row["id"])
        date.fromisoformat(row["statement_date"])
        if row["measurement"] not in {"point_in_time_statement", "annual_participation_estimate"} or not row["reference_period"]:
            raise ValueError("Student statement and annual participation must remain separate")
        approximate = row["qualifier"] in {"about", "as_stated"}
        if row["qualifier"] not in {"about", "as_stated", "less_than", "greater_than"} or (
                (row["value"] is not None) != approximate or (row["bound"] is None) != approximate):
            raise ValueError("A bounded estimate cannot become an exact count")
        number = row["value"] if approximate else row["bound"]
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise ValueError("Invalid reported student estimate")
        asset = data["sources"][row["source_id"]]["asset"]
        if (not re.fullmatch("[0-9a-f]{64}", asset["sha256"]) or not asset["request_url"].startswith("https://")
                or datetime.fromisoformat(asset["retrieved_at"]).tzinfo is None):
            raise ValueError("Student-estimate source evidence incomplete")
    return data


def reported(row):
    number = row["value"] if row["value"] is not None else row["bound"]
    return {"about": "About ", "as_stated": "", "less_than": "<", "greater_than": ">"}[row["qualifier"]] + f"{number:,}" + (
        " per year" if row["measurement"] == "annual_participation_estimate" else "")


def export(root, data):
    validate(data)
    write_atomic(root / "site/downloads/student-estimates.json", json_text(data))
    rows = []
    for row in data["observations"]:
        source = data["sources"][row["source_id"]]
        rows.append(dict(row, reported=reported(row), scope=data["scope"], comparability=data["comparability"],
                         source_name=source["name"], **source["asset"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_atomic(root / "site/downloads/student-estimates.csv", stream.getvalue())


def panel(data):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = "".join(
        f'<tr><th scope="row">{row["statement_date"]}</th><td>{esc(reported(row))}</td>'
        f'<td>{esc(row["reference_period"])}</td><td><a href="{esc(data["sources"][row["source_id"]]["asset"]["request_url"])}">'
        f'{esc(data["sources"][row["source_id"]]["name"])}</a></td></tr>' for row in data["observations"])
    return ('<section class="series-panel" id="student-estimates"><h2>Recent reported student estimates</h2>'
            '<p>Separate evidence for Americans studying in China—not an extension of the annual enrollment line. '
            'Dates identify the statement or publication, not a verified census date. “&lt;” and “&gt;” remain bounds.</p>'
            f'<p>{esc(data["comparability"])}</p><div class="table-scroll"><table>'
            '<thead><tr><th>Reported on</th><th>Reported figure</th><th>Reference period</th><th>Primary statement</th></tr></thead>'
            '<tbody>' + rows + '</tbody></table></div><p>'
            '<a href="downloads/student-estimates.json" download>All estimates, bounds and sources · JSON</a> · '
            '<a href="downloads/student-estimates.csv" download>All estimates and bounds · CSV</a></p></section>')
