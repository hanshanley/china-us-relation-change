import io
from datetime import datetime
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from us_china_exchange.sources import COUNTRIES, parse_bea, parse_ntto, parse_taiwan
from us_china_exchange import sources
from us_china_exchange.model import change


def xlsx(book):
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_bea_scale_directions_and_matched_quarter_sums():
    book = Workbook()
    book.remove(book.active)
    for n in [4, 5, 7, 8]:
        sheet = book.create_sheet(f"Table {n}")
        for cells in [
            ["Last updated September 3, 2026"], ["Title"], ["Trade"],
            ["[Millions of dollars, quarters seasonally adjusted]"], [],
            ["Period", "China", "Hong Kong", "Taiwan"], ["Annual"],
            ["1999", 1, 2, 3], ["2000", 4, 5, 6], ["2020", 10, 20, 30], ["Quarterly"],
            ["2020 1", 1, 2, 3], ["2020 2", 4, 5, 6],
            ["2026 1 (R)", 7, 8, 9], ["2026 2", 10, 11, 12],
        ]:
            sheet.append(cells)
    rows, vintage = parse_bea(xlsx(book))
    assert len(rows) == 48
    assert min(r["year"] for r in rows) == 2000
    assert next(r for r in rows if r["year"] == 2000 and r["origin"] == "USA"
                and r["destination"] == "CHN" and r["measure"] == "goods")["value"] == 4_000_000
    assert {r["origin"] for r in rows} == {"USA", "CHN", "HKG", "TWN"}
    row = next(r for r in rows if r["origin"] == "USA" and r["destination"] == "CHN"
               and r["measure"] == "services" and r["frequency"] == "ytd" and r["year"] == 2026)
    assert row["value"] == 17_000_000
    assert row["period"] == "2026-06"
    assert "seasonally adjusted" in row["definition"]


def test_bea_ambiguous_early_labels_use_independently_labelled_archive():
    def content(archived=False):
        book = Workbook()
        book.remove(book.active)
        for n in [4, 5, 7, 8]:
            sheet = book.create_sheet(f"Table {n}")
            for cells in [
                ["Last updated December 5, 2024" if archived else "Last updated September 3, 2026"],
                ["Title"], ["Trade"], ["Millions of dollars"], [],
                ["Period", "China", "Hong Kong", "Taiwan"], ["Annual"],
                [2000, 1, 2, 3], [2001 if archived else 2000, 4, 5, 6],
                [2020, 10, 20, 30], ["Quarterly"], ["2020 1", 1, 2, 3],
            ]:
                sheet.append(cells)
        return xlsx(book)

    current, archived = content(), content(True)
    with pytest.raises(sources.BEAEarlyHistoryError):
        parse_bea(current)

    def get(url):
        page = b'<a href="https://example.test/geo-time-series.xlsx">History</a>'
        body = page if url == sources.BEA else archived if url == sources.BEA_HISTORY else current
        return body, {"url": url, "sha256": "a" * 64, "retrieved_at": "2026-10-21T00:00:00+00:00"}

    rows, _, notes = sources.bea(SimpleNamespace(get=get))
    history = [r for r in rows if r["frequency"] == "annual" and r["year"] < 2002]
    assert len(history) == 24
    assert {r["source_url"] for r in history} == {sources.BEA_HISTORY}
    assert {r["source_vintage"] for r in history} == {"Last updated December 5, 2024"}
    assert {r["value"] for r in history if r["year"] == 2001} == {4_000_000, 5_000_000, 6_000_000}
    assert all(r["source_url"] != sources.BEA_HISTORY for r in rows if r["year"] == 2020)
    assert "repeats the 2000 label" in notes


def test_ntto_mixed_headers_single_digit_months_and_provisional_ytd():
    book = Workbook()
    sheet = book.active
    sheet.title = "Monthly"
    sheet.append(["#", "Country", "Region", datetime(2020, 1, 2),
                  datetime(2020, 2, 3), "2022-1", "2022-2",
                  "2026-01", "2026-02\nPreliminary"])
    for i, country in enumerate(COUNTRIES):
        sheet.append([i, country, "Asia", 10, 20, 40, 50, 60, 70])
    rows, _ = parse_ntto(xlsx(book), monthly=True)
    assert len([r for r in rows if r["frequency"] == "monthly"]) == 24
    assert next(r for r in rows if r["period"] == "2022-02" and r["origin"] == "MAC")["value"] == 50
    current = next(r for r in rows if r["year"] == 2026 and r["frequency"] == "ytd")
    assert current["value"] == 130
    assert current["status"] == "provisional"


def test_taiwan_all_purpose_and_leisure_are_separate():
    content = "年別,細分,合計,觀光\n2020,美國 USA,\"82,872\",\"26,634\"\n".encode("utf-8-sig")
    rows = parse_taiwan(content)
    assert {r["measure"]: r["value"] for r in rows} == {
        "visitors": 82872, "leisure_visitors": 26634}
    with pytest.raises(ValueError):
        parse_taiwan(b"year,country\n2020,USA\n")


def test_ntto_retains_annual_history_from_2000():
    book = Workbook()
    sheet = book.active
    sheet.title = "Annual"
    sheet.append(["Country", 1999, 2000, 2001])
    for country in COUNTRIES:
        sheet.append([country, 9, 10, 11])
    rows, _ = parse_ntto(xlsx(book))
    assert {r["year"] for r in rows} == {2000, 2001}
    assert {r["value"] for r in rows if r["year"] == 2000} == {10}


@pytest.mark.parametrize("edition,basis,share", [
    (2008, "PLACE OF RESIDENCE", "100.00%"),
    (2024, "Place of Issue of Travel Document", "100.0%"),
])
def test_macau_profile_reconciles_modes_and_excludes_monthly_rows(monkeypatch, edition, basis, share):
    text = "VISITOR ARRIVALS FROM U.S.A.\n" + basis + "\n"
    years = range(edition - 5, edition + 1)
    text += "\n".join(f"{year} 3 104 64 171 {share}" for year in years)
    text += "\nJanuary 1 2 3 6 4.0%"
    page = SimpleNamespace(extract_text=lambda: text)
    monkeypatch.setattr(sources, "PdfReader", lambda stream: SimpleNamespace(pages=[page]))
    assert sources.parse_macau_market(b"%PDF fixture", edition) == dict.fromkeys(years, 171)
    text = text.replace(f"{edition - 2} 3 104 64 171", f"{edition - 2} 3 104 64 172")
    with pytest.raises(ValueError, match="reconcile"):
        sources.parse_macau_market(b"%PDF fixture", edition)
    text = text.replace(basis, "Nationality")
    with pytest.raises(ValueError, match="issuing-document profile"):
        sources.parse_macau_market(b"%PDF fixture", edition)


def test_macau_classification_break_is_not_compared_with_2020():
    rows = {year: sources.macau_observation(year, 100, "")
            for year in [2007, 2008, 2014, 2015, 2016, 2020, 2025]}
    assert change(rows[2007], rows[2008])["absolute"] is None
    assert change(rows[2014], rows[2020])["absolute"] is None
    assert change(rows[2015], rows[2020])["absolute"] is None
    assert change(rows[2016], rows[2020])["absolute"] == 0
    assert change(rows[2025], rows[2020])["absolute"] == 0


def test_macau_discovers_historical_and_latest_complete_profiles(monkeypatch):
    paths = [
        "/VAHightlights/2015/Dec.pdf", "/VAHightlights/2025/Dec.pdf",
        "/MarketPerformance/2015/Market Performance  2015.pdf",
        "/MarketPerformance/2023/Market Performance 2023.pdf",
        "/MarketPerformance/2024/Market Performance 2024.pdf",
        "/MarketPerformance/2025/Market Performance 2025 Jan-Sep.pdf",
        "/MarketPerformance/2008/M12_MarketingPerformance_2008_1246941849.pdf",
        "/MarketPerformance/2010/M12_MarketPerformance_2010_1298431536.pdf",
    ]
    archive = "".join(f'<option value="{path}"></option>' for path in paths).encode()
    requested = []

    def get(url):
        requested.append(url)
        return (archive if url == sources.MACAU_INDEX else b"%PDF fixture",
                {"url": url, "sha256": "a" * 64, "retrieved_at": "2026-10-21T00:00:00+00:00"})

    monkeypatch.setattr(sources, "parse_macau", lambda content, year: 999)
    monkeypatch.setattr(sources, "parse_macau_market",
                        lambda content, edition: dict.fromkeys(range(edition - 5, edition + 1), edition))
    rows, _, _ = sources.macau(SimpleNamespace(get=get))
    rows = {row["year"]: row for row in rows}
    assert rows[2010]["value"] == rows[2015]["value"] == 2015
    assert rows[2024]["value"] == 2024
    assert rows[2025]["value"] == 999
    assert rows[2003]["value"] == 2008
    assert rows[2015]["source_url"].endswith(paths[2])
    assert rows[2024]["source_url"].endswith(paths[4])
    assert not any("2023" in url or "Jan-Sep" in url for url in requested)


def test_macau_rejects_conflicting_extracted_us_totals(monkeypatch):
    page = SimpleNamespace(extract_text=lambda: "Visitor Arrivals 2025\nUSA 100 \nU.S.A. 200 ")
    monkeypatch.setattr(sources, "PdfReader", lambda stream: SimpleNamespace(pages=[page]))
    with pytest.raises(ValueError, match="Ambiguous"):
        sources.parse_macau(b"%PDF fixture", 2025)
