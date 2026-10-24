from copy import deepcopy
import json
from pathlib import Path

import pytest

from us_china_exchange.mainland_history import (
    TIAN_HISTORY, TIAN_SHA256, UNIVERSITY_2017, UNIVERSITY_SHA256,
    mainland_history, parse_tian_history, parse_university_2017,
)
from us_china_exchange.model import key, observation
from us_china_exchange.public_freshness import eligible


def article():
    rows = ["<tr><th>Year Rank</th><th></th>"
            + "".join(f"<th>Top {i}</th>" for i in range(1, 11)) + "</tr>"]
    for year in range(1999, 2020):
        # Vary the U.S. rank so row positions cannot substitute for country identity.
        labels = [f"Country {i}" for i in range(10)]
        labels[year % 10] = "USA"
        counts = [str(i + 20) for i in range(10)]
        counts[year % 10] = f"{year + 1000:,}"
        rows.append(f"<tr><td>{year}</td><td>country</td>"
                    + "".join(f"<td>{label}</td>" for label in labels) + "</tr>")
        rows.append("<tr><td></td><td>student number</td>"
                    + "".join(f"<td>{value}</td>" for value in counts) + "</tr>")
    return ('<article><article-id pub-id-type="doi">10.1007/s10734-020-00522-5</article-id>'
            '<table-wrap id="Tab3"><label>Table 3</label><caption>The top 10 countries</caption>'
            "<table>" + "".join(rows) + "</table></table-wrap></article>")


def test_historical_country_ranks_and_reference_years_are_not_publication_years():
    content = article()
    values = parse_tian_history(content)
    assert values == {year: year + 1000 for year in range(2000, 2016)}
    for invalid in (
            content.replace("00522-5", "00522-6"),
            content.replace("<td>2008</td>", "<td>2007</td>"),
            content.replace("<td>3,008</td>", "<td>--</td>"),
            content.replace("<th>Top 4</th>", ""),
            content.replace("<td>country</td>", "<td>students</td>", 1),
            content.replace("<td>3,008</td>", "<td>30,08</td>")):
        with pytest.raises(ValueError):
            parse_tian_history(invalid)


def test_university_count_requires_the_named_author_and_explicit_2017_us_population():
    content = ("\u5218\u732e\u541b\u6559\u6388 "
               "2017\u5e74\u7684\u6570\u636e\u663e\u793a\uff0c"
               "\u6765\u534e\u7559\u5b66\u7684\u7f8e\u56fd\u5b66\u751f\u4e3a23911\u4eba")
    assert parse_university_2017(content) == 23911
    assert parse_university_2017(
        content.replace("2017", "<span>2017</span> ").replace("23911", " 23,911 ")) == 23911
    for invalid in (
            content.replace("2017", "2018"),
            content.replace("\u7f8e\u56fd", "\u65e5\u672c"),
            content.replace("\u5218\u732e\u541b", ""),
            content + content):
        with pytest.raises(ValueError):
            parse_university_2017(invalid)


class SourceClient:
    def get(self, url):
        if url == TIAN_HISTORY:
            body, checksum = article(), TIAN_SHA256
        else:
            assert url == UNIVERSITY_2017
            body = ("\u5218\u732e\u541b 2017\u5e74\u7684\u6570\u636e\u663e\u793a\uff0c"
                    "\u6765\u534e\u7559\u5b66\u7684\u7f8e\u56fd\u5b66\u751f\u4e3a23911\u4eba")
            checksum = UNIVERSITY_SHA256
        return body.encode(), {
            "url": url, "sha256": checksum, "retrieved_at": "2026-10-24T23:00:00+00:00"}


def controls():
    return [observation("moe", "USA", "CHN", "enrolled_students", year, year + 1000,
                        "Annual degree and non-degree participation", period_basis="reporting")
            for year in list(range(2006, 2017)) + [2018]]


def test_backfill_preserves_every_prior_row_and_does_not_refresh_old_public_charts():
    prior = controls()
    original = deepcopy(prior)
    rows = mainland_history(SourceClient(), prior)
    by_key = {key(row): row for row in rows}
    assert all(by_key[key(row)] == row for row in original)
    assert prior == original
    assert len(rows) - len(prior) == 7
    assert {r["year"] for r in rows} == set(range(2000, 2019))
    assert not eligible(rows)
    assert all(r["period_basis"] == "reporting" and r["period_start"] is None
               and r["period_end"] is None for r in rows)
    row = next(r for r in rows if r["year"] == 2017)
    assert row["value"] == 23911 and row["source_url"] == UNIVERSITY_2017
    row["notes"] = "Previously retained independent provenance"
    assert next(r for r in mainland_history(SourceClient(), rows)
                if r["year"] == 2017)["notes"] == row["notes"]


@pytest.mark.parametrize("fault", ["overlap", "existing-2017", "missing-control"])
def test_conflicting_or_missing_independent_evidence_stops_the_merge(fault):
    prior = controls()
    if fault == "overlap":
        prior[0]["value"] += 1
    elif fault == "existing-2017":
        prior.append(observation("moe", "USA", "CHN", "enrolled_students", 2017, 1,
                                 prior[0]["definition"], period_basis="reporting"))
    else:
        prior.pop()
    with pytest.raises(ValueError):
        mainland_history(SourceClient(), prior)


def test_frozen_mainland_history_includes_earlier_reporting_years_and_the_missing_2017_count():
    root = Path(__file__).resolve().parents[1]
    history = {r["year"]: r for r in json.loads((root / "data/site/observations.json").read_text())
               if r["series_id"] == "moe:USA:CHN:enrolled_students"}
    assert set(history) == set(range(2000, 2019))
    assert {year: history[year]["value"] for year in range(2000, 2006)} == {
        2000: 4280, 2001: 5413, 2002: 7359, 2003: 3693, 2004: 8480, 2005: 10343}
    assert history[2017]["value"] == 23911 and history[2017]["source_url"] == UNIVERSITY_2017
    assert history[2016]["value"] == 23838 and history[2018]["value"] == 20996
    assert all(r["period_basis"] == "reporting" and r["period_start"] is None
               and r["period_end"] is None for r in history.values())
    assert not eligible(history.values())
