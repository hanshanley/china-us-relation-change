import copy
import csv
import io
import importlib.util
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup
from PIL import Image, ImageColor
from openpyxl import Workbook

from us_china_exchange.business_analysis import BENCHMARK_CHART, CHARTS, COLORS, RETIRED_CHARTS, build_business, chart_groups, svg_business_chart, validate_business_data
from us_china_exchange.business_sources import CBS_NETHERLANDS_METHODS, CBS_NETHERLANDS_REPORT, DENMARK_METADATA, DENMARK_DATA, DENMARK_QUERY, FINLAND_EUROSTAT_METHODS, SPAIN_EUROSTAT_METHODS, NORDIC_QUERIES, SWEDEN_COUNTRIES, SWEDEN_EUROSTAT_METHODS, SWEDEN_QUALITY, count_cell, country_counts, parse_cbs_netherlands, parse_denmark, parse_eurostat, parse_germany, parse_norway, parse_nordic, parse_ons
from us_china_exchange.render import build
from us_china_exchange.theme import CHART_THEMES, PARTNER_COLORS


ROOT = Path(__file__).resolve().parents[1]


def published():
    return json.loads((ROOT / "data/site/business_presence.json").read_text())


def eurostat():
    codes = {"freq": "A", "nace_r2": "B-S_X_O", "indic_sbs": "ENT_NR", "partner": "CN_X_HK", "geo": "EU27_2020"}
    return {
        "id": list(codes) + ["time"], "size": [1] * 5 + [3],
        "dimension": dict({k: {"category": {"index": {v: 0}}} for k, v in codes.items()},
                          time={"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}),
        "extension": {"id": "FATS_OUT_PART"}, "value": {"0": 6900, "1": 7191, "2": 0},
        "status": {"0": "e", "2": "|C"},
    }


def test_distinct_parent_and_affiliate_checkpoints_remain_different_units():
    data = validate_business_data(published())
    rows = {(r["series_id"], r["year"]): r for r in data["observations"]}
    assert [rows[("bea_parents:china", y)]["value"] for y in (2004, 2009, 2014, 2019)] == [581, 841, 1244, 1134]
    assert rows[("bea_affiliates:china", 2000)]["value"] == 458
    assert rows[("bea_affiliates:china", 2023)]["value"] == 1950
    assert rows[("bea_affiliates:china", 2023)]["status"] == "provisional"
    assert rows[("eurostat_affiliates:china", 2023)]["value"] is None
    assert rows[("eurostat_affiliates:china", 2023)]["status"] == "suppressed"
    assert rows[("eurostat_affiliates:china", 2021)]["status"] == "estimated"
    assert ("bea_parents:china", 2023) not in rows
    assert all(sid.endswith(":china") for sid in data["series"])
    assert [rows[("eurostat_historical_eu:china", y)]["value"] for y in (2009, 2011, 2012)] == [5688, 6607, 6860]
    assert [rows[("eurostat_uk:china", y)]["value"] for y in (2009, 2010, 2018, 2019)] == [691, 681, 709, 531]
    assert rows[("eurostat_uk:china", 2019)]["status"] == "estimated"
    assert rows[("eurostat_norway:china", 2023)]["value"] == 88
    assert len([r for r in rows.values() if not r["series_id"].startswith(
        ("tillvaxtanalys_", "statfin_", "eurostat_france:", "eurostat_netherlands:", "eurostat_finland:",
         "eurostat_italy", "eurostat_sweden:", "eurostat_spain:", "dst_denmark:"))]) == 112
    assert rows[("ssb_norway:china", 2023)]["value"] == 89
    assert rows[("ssb_norway:china", 2024)]["value"] == 80


def test_italian_collection_preserves_other_countries_and_separates_statistical_units(monkeypatch):
    from us_china_exchange import business_sources
    from us_china_exchange.business_sources import ITALY_EUROSTAT_METHODS, ISTAT_ITALY_REPORT

    spec = importlib.util.spec_from_file_location("italian_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def workbook(file_contents):
        data = json.loads(file_contents)
        counts = {"Totale": data["count"], "Industria": 500,
                  "Servizi": data["count"] - 500 + int(data["wrong_sector_sum"])}
        sheets = []
        for name, count in counts.items():
            rows = [[f"Imprese a controllo nazionale residenti all'estero - Anno {data['year']}"],
                    ["PAESI", "Addetti" if data["wrong_national_unit"] else "Imprese"],
                    ["Hong Kong" if data["wrong_national_country"] else "Cina", count],
                    ["Totale primi 40 paesi", count], ["Cina", 4.4]]
            sheets.append(SimpleNamespace(name=name, nrows=len(rows), row_values=lambda i, rows=rows: rows[i],
                                          cell_value=lambda i, j, rows=rows: rows[i][j]))
        return SimpleNamespace(sheets=lambda: sheets)

    monkeypatch.setattr(business_sources.xlrd, "open_workbook", workbook)
    monkeypatch.setattr(business_sources, "pdf_text", lambda content: [content.decode()])

    class Client:
        wrong_country = False
        wrong_methods = False
        wrong_national_methods = False
        wrong_workbook_year = False
        wrong_national_unit = False
        wrong_national_country = False
        wrong_sector_sum = False
        wrong_overlap_2019 = False
        wrong_overlap_2020 = False

        def get(self, url):
            if url == ITALY_EUROSTAT_METHODS:
                body = (b"Unrelated methods" if self.wrong_methods else
                        b"ISTAT-Italian National Statistical Institute. "
                        b"In previous years the legal unit was used. 2021 onwards")
            elif url == ISTAT_ITALY_REPORT:
                text = ("Nel caso del presente Report \u00e8 sempre l\u2019unit\u00e0 giuridica. "
                        "Outward, i primi dati sono relativi al 2021. "
                        "sottoposte a controllo ultimo nazionale; settori da B a N e P -Q-R-S")
                body = ("Enterprises only" if self.wrong_national_methods else text).encode()
            elif "annuarioistatice.istat.it" in url:
                edition = int(re.search(r"/(?:epo|tavole)/(\d{4})/", url).group(1))
                year = edition - 3
                if url.endswith(".html"):
                    body = (f'<table><tr><td>Imprese a controllo nazionale residenti all\'estero per '
                            f'principali paesi e macro-settore - Anno {year}</td>'
                            f'<td><a href="/tavole/{edition}/italy.xls">XLS</a></td></tr></table>').encode()
                else:
                    count = {2019: 1141, 2020: 1133, 2021: 1113, 2022: 1169, 2023: 1122}[year]
                    count += int(getattr(self, f"wrong_overlap_{year}", False))
                    body = json.dumps({"year": year + int(self.wrong_workbook_year), "count": count,
                                       "wrong_national_unit": self.wrong_national_unit,
                                       "wrong_national_country": self.wrong_national_country,
                                       "wrong_sector_sum": self.wrong_sector_sum}).encode()
            else:
                dataset = url.split("/data/")[1].split("?")[0]
                indicator = "indic_sbs" if dataset == "fats_out_part" else "indic_bp"
                activity = "nace_r1" if dataset == "fats_out2" else "nace_r2"
                codes = {"freq": "A", activity: "C-O_X_L" if activity == "nace_r1" else "B-S_X_O",
                         indicator: "ENT_NR" if indicator == "indic_sbs" else "ENT",
                         "partner": "CN_X_HK", "geo": "FR" if self.wrong_country else "IT"}
                values = ({2007: 792} if dataset == "fats_out2" else
                          {2010: 923, 2019: 1141, 2020: 1133} if dataset == "fats_out2_r2" else {2023: 669})
                data = {"id": list(codes) + ["time"], "size": [1] * len(codes) + [len(values)],
                        "dimension": {k: {"category": {"index": {v: 0}}} for k, v in codes.items()},
                        "extension": {"id": dataset}, "value": {str(i): v for i, v in enumerate(values.values())},
                        "updated": "2026-10-25"}
                data["dimension"]["time"] = {"category": {"index": {str(y): i for i, y in enumerate(values)}}}
                if dataset != "fats_out_part":
                    data["status"] = {str(i): "e" for i in range(len(values))}
                body = json.dumps(data).encode()
            return body, {"url": url, "request_url": url, "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at": "2026-10-25T00:00:00+00:00"}

    prior = published()
    prior["series"] = {k: v for k, v in prior["series"].items() if not k.startswith("eurostat_italy")}
    prior["observations"] = [r for r in prior["observations"] if not r["series_id"].startswith("eurostat_italy")]
    prior["sources"] = {k: v for k, v in prior["sources"].items()
                        if not k.endswith("_IT") and not k.startswith("istat_italy_legal_")}
    prior["coverage"] = [r for r in prior["coverage"] if not r["id"].startswith("eurostat_italy")]
    before = copy.deepcopy(prior)
    updated = validate_business_data(module.collect_italy(Client(), prior))
    assert prior == before
    actual = {(r["series_id"], r["year"]): r for r in updated["observations"]}
    assert all(actual[r["series_id"], r["year"]] == r for r in prior["observations"])
    assert all(updated["series"][k] == v for k, v in prior["series"].items())
    assert all(updated["sources"][k] == v for k, v in prior["sources"].items())
    assert actual["eurostat_italy_legal:china", 2007]["status"] == "estimated"
    assert actual["eurostat_italy:china", 2023]["status"] == "observed"
    assert updated["series"]["eurostat_italy_legal:china"]["unit"] == "legal units"
    assert updated["series"]["eurostat_italy:china"]["unit"] == "enterprises"
    assert [actual["eurostat_italy_legal:china", y]["value"] for y in (2021, 2022, 2023)] == [1113, 1169, 1122]
    assert all(actual["eurostat_italy_legal:china", y]["source_id"] == f"istat_italy_legal_{y}"
               for y in (2021, 2022, 2023))
    assert module.collect_italy(Client(), updated) == updated
    for attribute in ("wrong_country", "wrong_methods", "wrong_national_methods", "wrong_workbook_year",
                      "wrong_national_unit", "wrong_national_country", "wrong_sector_sum",
                      "wrong_overlap_2019", "wrong_overlap_2020"):
        client = Client()
        setattr(client, attribute, True)
        with pytest.raises(ValueError):
            module.collect_italy(client, prior)


def test_italian_legal_unit_history_uses_national_continuation_not_enterprise_counts():
    data = published()
    points = chart_groups(data, "italy-affiliates-china")[0]["points"]
    assert [point["year"] for point in points] == list(range(2007, 2024))
    assert [point["value"] for point in points[-3:]] == [1113, 1169, 1122]
    legacy = [r for r in data["observations"] if r["series_id"] == "eurostat_italy_legal:china"]
    assert [r["year"] for r in legacy] == list(range(2007, 2024))
    assert all(r["status"] == "estimated" for r in legacy)
    assert not any("eurostat_italy:china" in chart["series"] for chart in CHARTS.values())
    for sid, year in (("eurostat_italy_legal:china", 2024), ("eurostat_italy:china", 2020)):
        invalid = copy.deepcopy(data)
        next(r for r in invalid["observations"] if r["series_id"] == sid)["year"] = year
        with pytest.raises(ValueError, match="must not be spliced"):
            validate_business_data(invalid)
    invalid = copy.deepcopy(data)
    next(r for r in invalid["observations"]
         if r["series_id"] == "eurostat_italy_legal:china" and r["year"] == 2023)["source_id"] = "fats_out_part_IT"
    with pytest.raises(ValueError, match="method/source boundary"):
        validate_business_data(invalid)
    invalid = copy.deepcopy(data)
    invalid["series"]["eurostat_italy_legal:china"]["unit"] = "enterprises"
    with pytest.raises(ValueError, match="counting units"):
        validate_business_data(invalid)
    for theme in CHART_THEMES:
        svg = ElementTree.fromstring(svg_business_chart(data, "italy-affiliates-china", theme))
        bars = [node for node in svg.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in bars] == list(range(2007, 2024))
        assert [int(node.get("data-value")) for node in bars[-3:]] == [1113, 1169, 1122]


def test_uk_early_refresh_preserves_later_observations_and_classification_boundaries():
    spec = importlib.util.spec_from_file_location("business_uk_history_cli", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Client:
        wrong_country = False
        wrong_unit = False
        wrong_year = False

        def get(self, url):
            assert "/fats_out2?" in url and "geo=UK" in url and "indic_bp=ENT" in url
            codes = {"freq": "A", "nace_r1": "C-O_X_L", "indic_bp": "EMP" if self.wrong_unit else "ENT",
                     "partner": "CN_X_HK", "geo": "FR" if self.wrong_country else "UK"}
            years = [2007, 2008, 2010 if self.wrong_year else 2009]
            data = {
                "id": list(codes) + ["time"], "size": [1] * len(codes) + [3],
                "dimension": {key: {"category": {"index": {value: 0}}} for key, value in codes.items()},
                "extension": {"id": "FATS_OUT2"}, "value": {"2": 691},
                "label": "Outward FATS - main variables (2007-2009)", "updated": "2024-10-14"}
            data["dimension"]["time"] = {"category": {"index": {str(year): i for i, year in enumerate(years)}}}
            body = json.dumps(data).encode()
            return body, {"url": url, "request_url": url, "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at": "2026-10-25T00:00:00+00:00"}

    sid = "eurostat_uk:china"
    prior = published()
    prior["observations"] = [row for row in prior["observations"]
                             if row["series_id"] != sid or row["year"] >= 2010]
    prior["sources"].pop("fats_out2_UK", None)
    before = copy.deepcopy(prior)
    updated = validate_business_data(module.collect_uk_history(Client(), prior))
    assert prior == before
    old_rows = {(row["series_id"], row["year"]): row for row in prior["observations"]}
    new_rows = {(row["series_id"], row["year"]): row for row in updated["observations"]}
    assert all(new_rows[key] == value for key, value in old_rows.items())
    assert len(new_rows) == len(old_rows) + 3
    assert new_rows[(sid, 2009)]["value"] == 691
    assert all(new_rows[(sid, year)]["value"] is None
               and new_rows[(sid, year)]["status"] == "missing" for year in (2007, 2008))
    assert new_rows[(sid, 2009)]["comparability"] != new_rows[(sid, 2010)]["comparability"]
    assert all(updated["series"][key] == value for key, value in prior["series"].items() if key != sid)
    assert all(updated["sources"][key] == value for key, value in prior["sources"].items())
    assert updated["context"] == prior["context"]
    assert module.collect_uk_history(Client(), updated) == updated
    for attribute in ("wrong_country", "wrong_unit", "wrong_year"):
        client = Client()
        setattr(client, attribute, True)
        with pytest.raises(ValueError):
            module.collect_uk_history(client, prior)
    for year, wrong_source in ((2009, "fats_out2_r2_UK"), (2010, "fats_out2_UK")):
        invalid = copy.deepcopy(updated)
        next(row for row in invalid["observations"]
             if row["series_id"] == sid and row["year"] == year)["source_id"] = wrong_source
        with pytest.raises(ValueError, match="method/source boundary"):
            validate_business_data(invalid)


def cbs_netherlands():
    return b"""<p>* voorlopige cijfers</p>
<figure>5.3.7 Buitenlandse bedrijven in Nederland
<table><tr><th>Land</th><th>2024*</th></tr><tr><td>China</td><td>590</td></tr></table></figure>
<figure>5.4.1 Top 10 landen met Nederlandse dochterondernemingen (dochterondernemingen)
<table><tr><th>Land</th><th>2024*</th><th>2023</th></tr>
<tr><td>China</td><td>620</td><td>574</td></tr></table></figure>"""


def test_cbs_dutch_counts_are_outward_enterprises_not_inward_companies_or_employees():
    body = cbs_netherlands()
    assert parse_cbs_netherlands(body) == {2024: (620, "provisional"), 2023: (574, "observed")}
    for old, new in ((b"(dochterondernemingen)", b"(FTE)"),
                     (b"<th>2024*</th><th>2023", b"<th>2025*</th><th>2024"),
                     (b"<td>620</td>", b"<td>.</td>"),
                     (b"<td>China</td><td>620", b"<td>Japan</td><td>620"),
                     (b"* voorlopige cijfers", b"** nader voorlopige cijfers")):
        with pytest.raises(ValueError):
            parse_cbs_netherlands(body.replace(old, new))


def test_netherlands_selective_collection_preserves_other_countries_and_rejects_conflicts():
    spec = importlib.util.spec_from_file_location("business_netherlands_cli", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Client:
        conflict = False
        wrong_country = False

        def get(self, url):
            if url == CBS_NETHERLANDS_REPORT:
                body = cbs_netherlands()
                if self.conflict:
                    body = body.replace(b"<td>574</td>", b"<td>575</td>")
            elif url == CBS_NETHERLANDS_METHODS:
                body = ("UCI in Nederland; SBI 2008 sectie B t/m S exclusief O; "
                        "financi\u00eble en niet financi\u00eble; vanaf verslagperiode 2007; "
                        "Voor de cijfers van 2021 is een nieuwe methodiek gekozen").encode()
            else:
                dataset = url.split("/data/")[1].split("?")[0]
                indicator = "indic_sbs" if dataset == "fats_out_part" else "indic_bp"
                activity = "nace_r1" if dataset == "fats_out2" else "nace_r2"
                codes = {"freq": "A", activity: "C-O_X_L" if activity == "nace_r1" else "B-S_X_O",
                         indicator: "ENT_NR" if indicator == "indic_sbs" else "ENT",
                         "partner": "CN_X_HK", "geo": "UK" if self.wrong_country else "NL"}
                values = ([(2007, 465), (2008, 592), (2009, 761)] if dataset == "fats_out2" else
                          [(2019, 695), (2020, 689)] if dataset == "fats_out2_r2" else
                          [(2021, 681), (2022, 714), (2023, 574)])
                d = {"id": list(codes) + ["time"], "size": [1] * len(codes) + [len(values)],
                     "dimension": {k: {"category": {"index": {v: 0}}} for k, v in codes.items()},
                     "extension": {"id": dataset}, "value": {str(i): v for i, (_, v) in enumerate(values)},
                     "label": "Reviewed enterprise population", "updated": "2026-03-31"}
                d["dimension"]["time"] = {"category": {"index": {str(y): i for i, (y, _) in enumerate(values)}}}
                body = json.dumps(d).encode()
            return body, {"url": url, "request_url": url, "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at": "2026-10-25T00:00:00+00:00"}

    old = published()
    before = copy.deepcopy(old)
    updated = validate_business_data(module.collect_netherlands(Client(), old))
    assert old == before
    sid = "eurostat_netherlands:china"
    assert [r for r in updated["observations"] if r["series_id"] != sid] == [
        r for r in old["observations"] if r["series_id"] != sid]
    assert all(updated["series"][k] == v for k, v in old["series"].items() if k != sid)
    points = {r["year"]: r for r in updated["observations"] if r["series_id"] == sid}
    assert (points[2024]["value"], points[2024]["status"]) == (620, "provisional")
    assert points[2019]["comparability"] != points[2024]["comparability"]
    assert points[2023]["comparability"] == points[2024]["comparability"]
    assert module.collect_netherlands(Client(), updated) == updated
    for attribute in ("conflict", "wrong_country"):
        client = Client()
        setattr(client, attribute, True)
        with pytest.raises(ValueError):
            module.collect_netherlands(client, old)


def test_dutch_history_has_every_reported_year_and_explicit_method_boundaries():
    data = published()
    points = chart_groups(data, "netherlands-affiliates-china")[0]["points"]
    assert [p["year"] for p in points] == list(range(2007, 2025))
    assert [points[i]["value"] for i in (0, 12, 16, 17)] == [465, 695, 574, 620]
    assert points[2]["comparability"] != points[3]["comparability"]
    assert points[13]["comparability"] != points[14]["comparability"]
    for theme in CHART_THEMES:
        svg = ElementTree.fromstring(svg_business_chart(data, "netherlands-affiliates-china", theme))
        assert len([n for n in svg.iter() if n.get("class") == "annual-column"]) == 18
        assert not [n for n in svg.iter() if n.get("class") in {"data-line", "covid-band"}]
        assert "2024 provisional" in "".join(svg.itertext())
    wrong = copy.deepcopy(data)
    next(r for r in wrong["observations"] if r["series_id"] == "eurostat_netherlands:china" and
         r["year"] == 2024)["source_id"] = "fats_out2_r2_NL"
    with pytest.raises(ValueError, match="boundary"):
        validate_business_data(wrong)


def test_german_workbook_counts_entities_not_employment_and_does_not_splice_other_vintages():
    book = Workbook()
    book.active.title = "DATA"
    for r in [[], [], [None, 45291, 45657],
              ["BBFOFATS.A.DE.ENT.BTSXO.CN", 1929, 1911],
              ["BBFOFATS.A.DE.EMP.BTSXO.CN", 543341, 550000],
              ["BBFOFATS.A.DE.ENT.BTSXO.HK", 345, 318]]:
        book.active.append(r)
    book.create_sheet("Methodology").append([
        "Foreign affiliates ultimately controlled by German investors; more than 50%; total assets exceed €3 million"])
    book.create_sheet("Economic activity").append([
        "BTSXO", "All economic activities (without agriculture, public administration, private households)"])

    def parse():
        stream = io.BytesIO()
        book.save(stream)
        return parse_germany(stream.getvalue())

    assert parse() == [(2023, 1929, "observed"), (2024, 1911, "provisional")]
    book["DATA"].cell(4, 3, "X")
    assert parse()[1] == (2024, None, "missing")
    book["DATA"].cell(4, 1, "BBFOFATS.A.DE.EMP.BTSXO.CN")
    with pytest.raises(ValueError, match="enterprise-count"):
        parse()
    groups = (chart_groups(published(), "germany-affiliates-china-eurostat")
              + chart_groups(published(), "germany-affiliates-china"))
    assert [g["id"] for g in groups] == ["eurostat_germany:china", "bundesbank_germany:china"]
    assert [[p["year"] for p in g["points"]] for g in groups] == [
        list(range(2010, 2024)), list(range(2021, 2025))]
    assert [next(p["value"] for p in g["points"] if p["year"] == 2023) for g in groups] == [1921, 1929]
    assert groups[0]["points"][10]["comparability"] != groups[0]["points"][11]["comparability"]


def test_eurostat_confidential_zero_is_not_published_and_wrong_populations_fail():
    data = eurostat()
    points = parse_eurostat(data, "fats_out_part")
    assert [r[1:3] for r in points] == [(6900, "estimated"), (7191, "observed"), (None, "suppressed")]
    data["dimension"]["partner"]["category"]["index"] = {"CN": 0}
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out_part")
    data = eurostat()
    data["status"]["0"] = "x"
    with pytest.raises(ValueError, match="Unknown"):
        parse_eurostat(data, "fats_out_part")
    data = eurostat()
    data["status"]["1"] = "b"
    points = parse_eurostat(data, "fats_out_part")
    assert points[0][-1] != points[1][-1]
    with pytest.raises(ValueError, match="count"):
        count_cell(1.5)
    data = eurostat()
    data["dimension"]["geo"]["category"]["index"] = {"UK": 0}
    assert parse_eurostat(data, "fats_out_part", "UK")[0][1] == 6900
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out_part")


def test_norwegian_history_uses_own_full_population_not_a_eurostat_endpoint_splice():
    data = {
        "source": "Statistics Norway", "class": "dataset",
        "extension": {"px": {"tableid": "09827"}},
        "id": ["Land", "ContentsCode", "Tid"], "size": [1, 1, 2],
        "dimension": {
            "Land": {"category": {"index": {"CN": 0}}},
            "ContentsCode": {"category": {"index": {"Foretak": 0},
                "unit": {"Foretak": {"base": "enterprises", "decimals": 0}}}},
            "Tid": {"category": {"index": {"2023": 0, "2024": 1}}}},
        "value": [89, 80],
    }
    assert parse_norway(data) == [(2023, 89, "observed"), (2024, 80, "observed")]
    data["value"][1] = None
    assert parse_norway(data)[1] == (2024, None, "missing")
    data["dimension"]["Land"]["category"]["index"] = {"HK": 0}
    with pytest.raises(ValueError, match="country"):
        parse_norway(data)
    groups = chart_groups(published(), "norway-affiliates-china")
    assert len(groups) == 1 and groups[0]["id"] == "ssb_norway:china"
    assert [p["year"] for p in groups[0]["points"]] == list(range(2008, 2025))


def nordic_fixture(country):
    if country == "sweden":
        dimensions = ["Tid", "Etableringsland", "variabel"]
        years, geo, metric, label = ["2009", "2010", "2024"], "cn", "2", "Antal dotterbolag"
        publisher = "Myndigheten f\u00f6r tillv\u00e4xtpolitiska utv\u00e4rderingar och analyser"
        values, flags = [None, 433, 885], {"0": ".."}
    else:
        dimensions = ["timeperiod_y", "valtio_27_20180101", "contentscode"]
        years, geo, metric, label = ["2020", "2021", "2024"], "156", "ofats_count", "Number of affiliates"
        publisher = "Statistics Finland, finnish affiliates abroad"
        values, flags = [250, 249, 242], {}
    return {
        "class": "dataset", "source": publisher, "id": dimensions, "size": [3, 1, 1],
        "dimension": {
            dimensions[0]: {"category": {"index": {year: i for i, year in enumerate(years)}}},
            dimensions[1]: {"category": {"index": {geo: 0}}},
            dimensions[2]: {"category": {"index": {metric: 0}, "label": {metric: label}}},
        }, "value": values, "status": flags,
    }


@pytest.mark.parametrize("country,values", [("sweden", [None, 433, 885]), ("finland", [250, 249, 242])])
def test_nordic_parsers_keep_reported_counts_and_reject_wrong_country_or_unit(country, values):
    data = nordic_fixture(country)
    assert [point[1] for point in parse_nordic(data, country)] == values
    if country == "sweden":
        assert parse_nordic(data, country)[0][2] == "missing"
    else:
        assert parse_nordic(data, country)[0][3] != parse_nordic(data, country)[1][3]
    for dimension, replacement in [(1, "hk"), (2, "parent_groups")]:
        changed = copy.deepcopy(data)
        changed["dimension"][changed["id"][dimension]]["category"]["index"] = {replacement: 0}
        with pytest.raises(ValueError, match="country or affiliate counting unit"):
            parse_nordic(changed, country)
    data["status"]["1"] = "unreviewed"
    with pytest.raises(ValueError, match="Unreviewed"):
        parse_nordic(data, country)


def test_nordic_selective_collection_preserves_every_other_country_and_is_idempotent():
    spec = importlib.util.spec_from_file_location("business_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prior = published()
    prior["observations"] = [r for r in prior["observations"]
                             if not r["series_id"].startswith(("tillvaxtanalys_", "statfin_", "eurostat_france:", "eurostat_finland:"))]
    before = copy.deepcopy(prior)

    def asset(url, checksum="b" * 64):
        return dict(url=url, request_url=url, sha256=checksum, retrieved_at="2026-10-25T00:00:00+00:00")

    def post(url, query):
        country = "sweden" if url == SWEDEN_COUNTRIES else "finland"
        assert query == NORDIC_QUERIES[country]
        return json.dumps(nordic_fixture(country)).encode(), asset(url)

    client = SimpleNamespace(post_json=post, get=lambda url: (
        b"Reviewed methodology", asset(url, "5d7b77577caf3a9fb159c106bd7fe4e9196ef50f8e09b903b7cbb678d5301289")
        if url == SWEDEN_QUALITY else asset(url)))
    result = module.collect_nordic(client, prior)
    retained = {(r["series_id"], r["year"]): r for r in result["observations"]}
    assert len(retained) == len(prior["observations"]) + 6
    assert all(retained[r["series_id"], r["year"]] == r for r in prior["observations"])
    assert prior == before
    validate_business_data(result)
    assert module.collect_nordic(client, result) == result


def test_new_nordic_histories_retain_missing_years_and_source_definition_boundaries():
    data = published()
    sweden = {r["year"]: r for r in data["observations"] if r["series_id"] == "tillvaxtanalys_sweden:china"}
    assert set(sweden) == set(range(2000, 2025))
    assert all(sweden[y]["value"] is None and sweden[y]["status"] == "missing" for y in range(2000, 2010))
    assert sum(row["value"] is not None for row in sweden.values()) == 15
    for previous, current in [(2017, 2018), (2018, 2019), (2020, 2021)]:
        assert sweden[previous]["comparability"] != sweden[current]["comparability"]
    for chart, expected_years in [("sweden-affiliates-china", range(2010, 2025)),
                                   ("finland-affiliates-china", range(2020, 2025))]:
        doc = ElementTree.fromstring(svg_business_chart(data, chart))
        bars = [node for node in doc.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in bars] == list(expected_years)
        assert not any(node.get("class") == "data-line" for node in doc.iter())


def test_selective_country_refreshes_preserve_coverage_order_across_modes(monkeypatch):
    spec = importlib.util.spec_from_file_location("business_refresh_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prior = published()

    def selected(prefixes):
        definitions = {sid: value for sid, value in prior["series"].items() if sid.startswith(prefixes)}
        observations = [row for row in prior["observations"] if row["series_id"] in definitions]
        source_ids = {row["source_id"] for row in observations}
        return definitions, observations, {sid: prior["sources"][sid] for sid in source_ids}

    monkeypatch.setattr(module, "nordic_affiliates", lambda client: selected(("tillvaxtanalys_", "statfin_")))
    monkeypatch.setattr(module, "french_affiliates", lambda client: selected(("eurostat_france:",)))
    monkeypatch.setattr(module, "netherlands_affiliates", lambda client: selected(("eurostat_netherlands:",)))
    def early_uk(client):
        definitions, observations, sources = selected(("eurostat_uk:",))
        return definitions, [row for row in observations if row["year"] <= 2009], sources

    monkeypatch.setattr(module, "uk_early_affiliates", early_uk)
    monkeypatch.setattr(module, "finnish_eurostat_affiliates", lambda client: selected(("eurostat_finland:",)))
    monkeypatch.setattr(module, "swedish_eurostat_affiliates", lambda client: selected(("eurostat_sweden:",)))
    monkeypatch.setattr(module, "spanish_affiliates", lambda client: selected(("eurostat_spain:",)))
    monkeypatch.setattr(module, "danish_affiliates", lambda client: selected(("dst_denmark:",)))
    assert module.collect_nordic(None, prior) == prior
    assert module.collect_france(None, prior) == prior
    assert module.collect_netherlands(None, prior) == prior
    assert module.collect_finland_history(None, prior) == prior
    assert module.collect_uk_history(None, prior) == prior
    assert module.collect_sweden_history(None, prior) == prior
    assert module.collect_spain(None, prior) == prior
    assert module.collect_denmark(None, prior) == prior
    for collectors in (
        (module.collect_uk_history, module.collect_netherlands, module.collect_nordic, module.collect_france,
         module.collect_finland_history, module.collect_sweden_history, module.collect_spain, module.collect_denmark),
        (module.collect_denmark, module.collect_spain, module.collect_sweden_history, module.collect_finland_history,
         module.collect_france, module.collect_nordic, module.collect_netherlands, module.collect_uk_history),
    ):
        refreshed = prior
        for collector in collectors:
            refreshed = collector(None, refreshed)
            assert refreshed == prior


def test_spanish_selective_refresh_preserves_missingness_estimates_and_other_populations():
    spec = importlib.util.spec_from_file_location("business_spain_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Client:
        wrong_country = False
        truncated_history = False

        def get(self, url):
            if url == SPAIN_EUROSTAT_METHODS:
                body = b"Spanish UCI; 2021 statistical enterprise; financial activities from Bank of Spain"
            else:
                dataset = url.split("/data/")[1].split("?")[0]
                indicator = "indic_sbs" if dataset == "fats_out_part" else "indic_bp"
                activity = "nace_r1" if dataset == "fats_out2" else "nace_r2"
                codes = {"freq": "A", activity: "C-O_X_L" if activity == "nace_r1" else "B-S_X_O",
                         indicator: "ENT_NR" if indicator == "indic_sbs" else "ENT",
                         "partner": "CN_X_HK", "geo": "FR" if self.wrong_country else "ES"}
                values = ([(2007, None), (2008, None), (2009, 58)] if dataset == "fats_out2" else
                          list(zip(range(2010, 2021), (59, 84, 87, 92, 112, 105, 111, 126, 132, 127, 126)))
                          if dataset == "fats_out2_r2" else
                          [(2021, 105), (2022, 102), (2023, 100)])
                if self.truncated_history and dataset == "fats_out2_r2":
                    values = values[1:]
                data = {
                    "id": list(codes) + ["time"], "size": [1] * len(codes) + [len(values)],
                    "dimension": {key: {"category": {"index": {value: 0}}} for key, value in codes.items()},
                    "extension": {"id": dataset},
                    "value": {str(index): value for index, (_, value) in enumerate(values) if value is not None},
                    "updated": "2026-03-31"}
                data["dimension"]["time"] = {"category": {"index": {
                    str(year): index for index, (year, _) in enumerate(values)}}}
                if dataset == "fats_out_part":
                    data["status"] = {"1": "e", "2": "e"}
                body = json.dumps(data).encode()
            return body, {"url": url, "request_url": url, "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at": "2026-10-25T00:00:00+00:00"}

    prior = published()
    before = copy.deepcopy(prior)
    result = validate_business_data(module.collect_spain(Client(), prior))
    sid = "eurostat_spain:china"
    assert prior == before
    assert [row for row in result["observations"] if row["series_id"] != sid] == [
        row for row in prior["observations"] if row["series_id"] != sid]
    points = {row["year"]: row for row in result["observations"] if row["series_id"] == sid}
    assert (points[2007]["value"], points[2008]["status"]) == (None, "missing")
    assert (points[2023]["value"], points[2023]["status"]) == (100, "estimated")
    assert points[2009]["comparability"] != points[2019]["comparability"]
    assert points[2019]["comparability"] == points[2020]["comparability"]
    assert points[2020]["comparability"] != points[2021]["comparability"]
    assert any(asset["url"] == SPAIN_EUROSTAT_METHODS
               for asset in result["sources"]["fats_out_part_ES"]["assets"])
    assert module.collect_spain(Client(), result) == result
    wrong = Client()
    wrong.wrong_country = True
    with pytest.raises(ValueError, match="different geography"):
        module.collect_spain(wrong, prior)
    incomplete = Client()
    incomplete.truncated_history = True
    with pytest.raises(ValueError, match="history is incomplete"):
        module.collect_spain(incomplete, prior)


def test_spanish_chart_retains_actual_years_and_rejects_a_cross_regime_source():
    data = published()
    points = chart_groups(data, "spain-affiliates-china")[0]["points"]
    assert [point["year"] for point in points] == list(range(2009, 2024))
    assert (points[0]["value"], points[-1]["value"], points[-1]["status"]) == (58, 100, "estimated")
    for theme in CHART_THEMES:
        chart = ElementTree.fromstring(svg_business_chart(data, "spain-affiliates-china", theme))
        columns = [node for node in chart.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in columns] == list(range(2009, 2024))
        assert not any(node.get("class") in {"data-line", "covid-band"} for node in chart.iter())
    wrong = copy.deepcopy(data)
    row = next(row for row in wrong["observations"] if row["series_id"] == "eurostat_spain:china"
               and row["year"] == 2023)
    row["source_id"] = "fats_out2_r2_ES"
    with pytest.raises(ValueError, match="method/source boundary"):
        validate_business_data(wrong)


def denmark_fixture():
    years = [str(year) for year in range(2007, 2025)]
    metadata = {
        "id": "OFATS4", "suppressedDataValue": "0",
        "variables": [
            {"id": "LAND", "values": [{"id": "CN", "text": "China"}, {"id": "HK", "text": "Hong Kong"},
                                      {"id": "MO", "text": "Macao"}]},
            {"id": "ENHED", "values": [{"id": "DSANTAL", "text": "Affiliates"},
                                       {"id": "DSANSAT", "text": "Employees"}]},
            {"id": "Tid", "values": [{"id": year, "text": year} for year in years]}]}
    dimensions = {name: {"category": {"index": {code: 0}}}
                  for name, code in (("LAND", "CN"), ("ENHED", "DSANTAL"), ("ContentsCode", "OFATS4"))}
    dimensions["ContentsCode"]["category"]["unit"] = {"OFATS4": {"base": "Number", "decimals": 0}}
    dimensions["Tid"] = {"category": {"index": {year: index for index, year in enumerate(years)}}}
    dimensions.update(id=["LAND", "ENHED", "ContentsCode", "Tid"], size=[1, 1, 1, 18])
    data = {"dataset": {
        "dimension": dimensions, "extension": {"px": {"tableid": "OFATS4"}},
        "updated": "2026-01-20T07:00:00Z",
        "value": [217, 228, 272, 320, 353, 395, 417, 468, 487, 482, 468, 464,
                  485, 488, 481, 466, 480, 460]}}
    return data, metadata


def test_denmark_parser_preserves_country_counts_and_masks_ambiguous_zero():
    data, metadata = denmark_fixture()
    points = parse_denmark(data, metadata)
    assert [point[0] for point in points] == list(range(2007, 2025))
    assert (points[0][1], points[12][1], points[-1][1]) == (217, 485, 460)
    assert points[2][3] != points[3][3] and points[12][3] == points[-1][3]
    ambiguous = copy.deepcopy(data)
    ambiguous["dataset"]["value"][-1] = 0
    assert parse_denmark(ambiguous, metadata)[-1][1:3] == (None, "missing")
    for kind in ("country", "employees", "scaled_unit", "truncated", "quality_flag"):
        wrong = copy.deepcopy(data)
        if kind == "country":
            wrong["dataset"]["dimension"]["LAND"]["category"]["index"] = {"HK": 0}
        elif kind == "employees":
            wrong["dataset"]["dimension"]["ENHED"]["category"]["index"] = {"DSANSAT": 0}
        elif kind == "scaled_unit":
            wrong["dataset"]["dimension"]["ContentsCode"]["category"]["unit"]["OFATS4"]["base"] = "Thousands"
        elif kind == "truncated":
            wrong["dataset"]["value"].pop()
        else:
            wrong["dataset"]["status"] = {"0": "p"}
        with pytest.raises(ValueError):
            parse_denmark(wrong, metadata)


def test_danish_selective_refresh_preserves_other_countries_and_is_idempotent():
    spec = importlib.util.spec_from_file_location("business_denmark_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data, metadata = denmark_fixture()

    def response(url, payload):
        body = json.dumps(payload).encode()
        return body, {"url": url, "request_url": url, "sha256": hashlib.sha256(body).hexdigest(),
                      "retrieved_at": "2026-10-25T00:00:00+00:00"}

    def post(url, query):
        if url == DENMARK_METADATA:
            assert query == {"table": "OFATS4", "format": "JSON", "lang": "en"}
            return response(url, metadata)
        assert url == DENMARK_DATA and query == DENMARK_QUERY
        return response(url, data)

    client = SimpleNamespace(post_json=post, get=lambda url: response(url, "Reviewed national methodology"))
    prior = published()
    before = copy.deepcopy(prior)
    result = validate_business_data(module.collect_denmark(client, prior))
    assert prior == before
    assert [row for row in result["observations"] if row["series_id"] != "dst_denmark:china"] == [
        row for row in prior["observations"] if row["series_id"] != "dst_denmark:china"]
    assert module.collect_denmark(client, result) == result


def test_danish_chart_keeps_national_resident_parent_scope_and_all_years():
    data = published()
    points = chart_groups(data, "denmark-affiliates-china")[0]["points"]
    assert [point["year"] for point in points] == list(range(2007, 2025))
    assert (points[0]["value"], points[-1]["value"]) == (217, 460)
    for theme in CHART_THEMES:
        svg = ElementTree.fromstring(svg_business_chart(data, "denmark-affiliates-china", theme))
        columns = [node for node in svg.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in columns] == list(range(2007, 2025))
        assert not any(node.get("class") in {"data-line", "covid-band"} for node in svg.iter())
    wrong = copy.deepcopy(data)
    wrong["series"]["dst_denmark:china"]["scope"] = "Danish-UCI enterprises in China"
    with pytest.raises(ValueError, match="resident-parent"):
        validate_business_data(wrong)


def test_finnish_eurostat_refresh_preserves_national_population_and_explicit_yty_break():
    spec = importlib.util.spec_from_file_location("finnish_business_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prior = published()
    prior["observations"] = [row for row in prior["observations"] if row["series_id"] != "eurostat_finland:china"]
    before = copy.deepcopy(prior)

    def get(url):
        asset = dict(url=url, request_url=url, sha256="b" * 64, retrieved_at="2026-10-25T00:00:00+00:00")
        if url == FINLAND_EUROSTAT_METHODS:
            return b"Reviewed Finland country methodology", asset
        dataset = urlsplit(url).path.split("/")[-1]
        codes = {name: values[0] for name, values in parse_qs(urlsplit(url).query).items() if name != "lang"}
        assert codes["geo"] == "FI" and codes["partner"] == "CN_X_HK"
        points = {
            "fats_out2": [(2007, 149), (2008, 133), (2009, 163)],
            "fats_out2_r2": [(2010, 164), (2012, 205), (2013, 194), (2020, 208)],
            "fats_out_part": [(2021, 205), (2023, 185)],
        }[dataset]
        data = {"id": list(codes) + ["time"], "size": [1] * len(codes) + [len(points)],
                "extension": {"id": dataset.upper()}, "updated": "2026-03-31T23:00:00+0200",
                "dimension": {name: {"category": {"index": {code: 0}}} for name, code in codes.items()},
                "value": {str(index): value for index, (_, value) in enumerate(points)}}
        data["dimension"]["time"] = {"category": {"index": {str(year): index for index, (year, _) in enumerate(points)}}}
        return json.dumps(data).encode(), asset

    client = SimpleNamespace(get=get)
    result = module.collect_finland_history(client, prior)
    assert prior == before
    retained = {(row["series_id"], row["year"]): row for row in result["observations"]}
    assert all(retained[row["series_id"], row["year"]] == row for row in prior["observations"])
    rows = {row["year"]: row for row in result["observations"] if row["series_id"] == "eurostat_finland:china"}
    for previous, current in [(2009, 2010), (2012, 2013), (2020, 2021)]:
        assert rows[previous]["comparability"] != rows[current]["comparability"]
    assert rows[2008]["value"] == 133 and ":pilot" not in rows[2007]["comparability"]
    validate_business_data(result)
    assert module.collect_finland_history(client, result) == result


def test_finnish_eurostat_bars_do_not_fill_national_history_or_cross_source_boundaries():
    data = published()
    for chart, expected_years in [("finland-affiliates-china-eurostat", range(2007, 2024)),
                                   ("finland-affiliates-china", range(2020, 2025))]:
        svg = ElementTree.fromstring(svg_business_chart(data, chart))
        bars = [node for node in svg.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in bars] == list(expected_years)
        assert not any(node.get("class") == "data-line" for node in svg.iter())
    eurostat_group = chart_groups(data, "finland-affiliates-china-eurostat")[0]
    national_group = chart_groups(data, "finland-affiliates-china")[0]
    assert eurostat_group["id"] != national_group["id"]
    assert eurostat_group["points"][-1]["value"] != national_group["points"][-2]["value"]
    row = next(row for row in data["observations"] if row["series_id"] == "eurostat_finland:china")
    row["source_id"] = "finland_13k8"
    with pytest.raises(ValueError, match="method/source"):
        validate_business_data(data)


def test_swedish_eurostat_refresh_preserves_confidentiality_and_country_specific_breaks():
    spec = importlib.util.spec_from_file_location("swedish_business_collector", ROOT / "scripts/build_business_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prior = published()
    prior["observations"] = [row for row in prior["observations"] if row["series_id"] != "eurostat_sweden:china"]
    before = copy.deepcopy(prior)

    def get(url):
        asset = dict(url=url, request_url=url, sha256="c" * 64, retrieved_at="2026-10-25T00:00:00+00:00")
        if url == SWEDEN_EUROSTAT_METHODS:
            return b"Reviewed Sweden country methodology", asset
        dataset = urlsplit(url).path.split("/")[-1]
        codes = {name: values[0] for name, values in parse_qs(urlsplit(url).query).items() if name != "lang"}
        assert codes["geo"] == "SE" and codes["partner"] == "CN_X_HK"
        points, flags = {
            "fats_out2": ([(2007, 186), (2008, 320), (2009, 0)], {"2": "|C"}),
            "fats_out2_r2": ([(2010, 407), (2017, 702), (2018, 665), (2020, 679)], {"2": "b"}),
            "fats_out_part": ([(2021, 523), (2023, 602)], {}),
        }[dataset]
        data = {"id": list(codes) + ["time"], "size": [1] * len(codes) + [len(points)],
                "extension": {"id": dataset.upper()}, "updated": "2026-03-31T23:00:00+0200",
                "dimension": {name: {"category": {"index": {code: 0}}} for name, code in codes.items()},
                "value": {str(index): value for index, (_, value) in enumerate(points)}, "status": flags}
        data["dimension"]["time"] = {"category": {"index": {str(year): index for index, (year, _) in enumerate(points)}}}
        return json.dumps(data).encode(), asset

    client = SimpleNamespace(get=get)
    result = validate_business_data(module.collect_sweden_history(client, prior))
    assert prior == before
    retained = {(row["series_id"], row["year"]): row for row in result["observations"]}
    assert all(retained[row["series_id"], row["year"]] == row for row in prior["observations"])
    rows = {row["year"]: row for row in result["observations"] if row["series_id"] == "eurostat_sweden:china"}
    assert rows[2009]["value"] is None and rows[2009]["status"] == "suppressed"
    for previous, current in [(2007, 2008), (2008, 2010), (2017, 2018), (2020, 2021)]:
        assert rows[previous]["comparability"] != rows[current]["comparability"]
    assert module.collect_sweden_history(client, result) == result


def test_swedish_eurostat_bars_leave_confidential_year_empty_and_national_spike_unchanged():
    data = published()
    for theme in CHART_THEMES:
        svg = ElementTree.fromstring(svg_business_chart(data, "sweden-affiliates-china-eurostat", theme))
        bars = [node for node in svg.iter() if node.get("class") == "annual-column"]
        assert [int(node.get("data-year")) for node in bars] == [year for year in range(2007, 2024) if year != 2009]
        assert not any(node.get("class") == "data-line" for node in svg.iter())
    assert next(row["value"] for row in data["observations"]
                if row["series_id"] == "tillvaxtanalys_sweden:china" and row["year"] == 2022) == 1133
    row = next(row for row in data["observations"] if row["series_id"] == "eurostat_sweden:china")
    row["source_id"] = "sweden_country_table"
    with pytest.raises(ValueError, match="method/source"):
        validate_business_data(data)


def test_ons_parser_uses_enterprises_not_employment_and_verifies_year():
    book = Workbook()
    book.remove(book.active)
    for year, name, count in [(2018, "Table 1", 709), (2019, "Table 2", 531)]:
        sheet = book.create_sheet(name)
        sheet.cell(1, 1, f"UK Outward Foreign Affiliate Statistics: {year}")
        sheet.cell(9, 2, "TOTAL ACTIVITY")
        sheet.cell(10, 2, "ENT")
        sheet.append(["China", count, 124879, 15247499])
    stream = io.BytesIO()
    book.save(stream)
    assert parse_ons(stream.getvalue()) == [(2018, 709, "estimated"), (2019, 531, "estimated")]
    book["Table 2"].cell(1, 1, "2020")
    stream = io.BytesIO()
    book.save(stream)
    with pytest.raises(ValueError, match="year"):
        parse_ons(stream.getvalue())


def test_france_keeps_its_missing_cell_and_each_reported_population_boundary():
    data = published()
    rows = {r["year"]: r for r in data["observations"] if r["series_id"] == "eurostat_france:china"}
    assert set(rows) == set(range(2007, 2024))
    assert rows[2008]["value"] is None and rows[2008]["status"] == "missing"
    assert rows[2023]["value"] == 2153
    assert "China except Hong Kong" in data["series"]["eurostat_france:china"]["scope"]
    for previous, current in [(2007, 2009), (2009, 2010), (2015, 2016), (2020, 2021)]:
        assert rows[previous]["comparability"] != rows[current]["comparability"]
    doc = ElementTree.fromstring(svg_business_chart(data, "france-affiliates-china"))
    bars = [n for n in doc.iter() if n.get("class") == "annual-column"]
    assert [int(n.get("data-year")) for n in bars] == [y for y in range(2007, 2024) if y != 2008]
    assert not any(n.get("class") == "data-line" for n in doc.iter())


def test_earlier_eu_membership_and_classification_are_not_relabelled_as_current():
    data = eurostat()
    data["id"][1] = "nace_r1"
    data["id"][2] = "indic_bp"
    del data["dimension"]["nace_r2"], data["dimension"]["indic_sbs"]
    data["dimension"]["nace_r1"] = {"category": {"index": {"C-O_X_L": 0}}}
    data["dimension"]["indic_bp"] = {"category": {"index": {"ENT": 0}}}
    data["dimension"]["geo"]["category"]["index"] = {"EU27_2007": 0}
    data["dimension"]["time"]["category"]["index"] = {"2007": 0, "2008": 1, "2009": 2}
    data["extension"]["id"] = "FATS_OUT2"
    data["value"], data["status"] = {"2": 5688}, {}
    points = parse_eurostat(data, "fats_out2", "EU27_2007")
    assert [(r[0], r[1]) for r in points] == [(2007, None), (2008, None), (2009, 5688)]
    with pytest.raises(ValueError, match="different geography"):
        parse_eurostat(data, "fats_out2")


def test_count_parser_skips_contents_but_rejects_duplicate_country_rows():
    def sheet(name, rows):
        return SimpleNamespace(name=name, nrows=len(rows), row_values=lambda i: rows[i],
                               cell_value=lambda i, j: rows[i][j])
    contents = sheet("Contents", [["Number of U.S. Parents", ""]])
    table = sheet("Table I.K2", [["Number of U.S. Parents", "All industries"], ["China", 1134], ["Europe", 2701]])
    assert country_counts([contents, table], "Number of U.S. Parents") == {"China": (1134, "observed"), "Europe": (2701, "observed")}
    with pytest.raises(ValueError, match="Ambiguous"):
        country_counts([table, table], "Number of U.S. Parents")


def test_annual_histories_and_method_boundaries_are_not_endpoint_snapshots():
    data = published()
    doc = ElementTree.fromstring(svg_business_chart(data, BENCHMARK_CHART))
    assert not [n for n in doc.iter() if n.get("class") == "data-line"]
    assert len([n for n in doc.iter() if n.get("class") == "annual-column"]) == 4
    doc = ElementTree.fromstring(svg_business_chart(data, "us-affiliates-china"))
    assert not [n for n in doc.iter() if n.get("class") == "data-line"]
    assert len([n for n in doc.iter() if n.get("class") == "annual-column"]) == 24
    assert len(chart_groups(data, "us-affiliates-china")[0]["points"]) == 24
    assert sum(len(g["points"]) for g in chart_groups(data, "eu-affiliates-china")) == 12
    assert len(chart_groups(data, "uk-affiliates-china")[0]["points"]) == 11
    assert len(chart_groups(data, "norway-affiliates-china")[0]["points"]) == 17
    doc = ElementTree.fromstring(svg_business_chart(data, "eu-affiliates-china"))
    path = next(n for n in doc.iter() if n.get("class") == "data-line" and n.get("data-series-id") == "eurostat_affiliates:china")
    assert path.get("d").count("M") == 2
    assert "2023 confidential" in "".join(doc.itertext())
    assert "2023" in [n.text for n in doc.iter() if n.get("class") == "year-tick"]


def test_complete_business_downloads_exact_points_backgrounds_and_stale_cleanup(tmp_path):
    data = published()
    for base in (tmp_path / "outputs/figures/business_presence", tmp_path / "site/figures/business_presence"):
        (base / "substack").mkdir(parents=True)
        for chart_id in RETIRED_CHARTS:
            (base / "substack" / (chart_id + ".svg")).write_text("Obsolete wrong-destination chart")
    assert build_business(tmp_path, data, defaultdict(list)) == 16
    assert not any((tmp_path / "outputs/figures/business_presence/substack" / (cid + ".svg")).exists()
                   for cid in RETIRED_CHARTS)
    assert json.loads((tmp_path / "site/downloads/business-presence.json").read_text()) == data
    with (tmp_path / "site/downloads/business-observations.csv").open() as f:
        raw = list(csv.DictReader(f))
    assert len(raw) == len(data["observations"])
    legal = [r for r in raw if r["series_id"] == "eurostat_italy_legal:china"]
    assert len(legal) == 17 and all(r["unit"] == "legal units" and r["status"] == "estimated" for r in legal)
    for actual, expected in zip(raw, data["observations"]):
        assert all(actual[k] == ("" if v is None else str(v)) for k, v in expected.items())
        assert actual["unit"] == data["series"][expected["series_id"]]["unit"]
        assert json.loads(actual["source_assets"]) == data["sources"][expected["source_id"]]["assets"]
    with (tmp_path / "site/downloads/business-chart-values.csv").open() as f:
        plotted = list(csv.DictReader(f))
    wanted = {(cid, g["id"], p["year"]): p["plotted_value"]
              for cid in CHARTS for g in chart_groups(data, cid) for p in g["points"]}
    assert len(plotted) == len(wanted)
    for r in plotted:
        assert float(r["plotted_value"]) == wanted[(r["chart_id"], r["series_id"], int(r["year"]))]
    base = tmp_path / "outputs/figures/business_presence"
    for path in base.glob("*/*.svg"):
        doc = ElementTree.fromstring(path.read_text())
        points = [n for n in doc.iter() if n.get("class") == "business-point"]
        expected = {k[1:]: v for k, v in wanted.items() if k[0] == path.stem}
        assert len(points) == len(expected)
        for p in points:
            assert float(p.get("data-value")) == expected[(p.get("data-series-id"), int(p.get("data-year")))]
            assert p.get("fill") == COLORS[p.get("data-series-id")]
        for suffix in (".png", ".svg"):
            p = path.with_suffix(suffix)
            assert p.read_bytes() == (tmp_path / "site/figures/business_presence" / p.relative_to(base)).read_bytes()
        with Image.open(path.with_suffix(".png")) as image:
            assert image.size == (3000, 1800)
            assert image.getpixel((0, 0)) == (*ImageColor.getrgb(CHART_THEMES[path.parent.name]["background"]), 255)
    page = BeautifulSoup((tmp_path / "site/business-presence.html").read_text(), "html.parser")
    assert "different counting units" in page.header.text
    assert "EU27" in page.header.text and "not matched" in page.header.text
    table = page.select("#annual-values tbody tr")
    assert len(table) == 25 and table[0].th.text == "2000" and table[-1].th.text == "2024"
    assert page.select_one("#business-benchmark-background").get("open") is None
    assert page.select_one("#" + BENCHMARK_CHART).find_parent("details")["id"] == "business-benchmark-background"
    assert not page.select('#us-affiliates-europe,#us-affiliates-index,#us-parent-companies')
    custom = base / "substack/custom.svg"
    custom.write_text("User-owned")
    data["observations"] = [r for r in data["observations"] if not r["series_id"].startswith("eurostat")]
    build_business(tmp_path, data, defaultdict(list))
    assert not list(base.glob("*/eu-affiliates-china.*"))
    assert custom.read_text() == "User-owned"


def test_invalid_business_input_is_rejected_before_writes_and_deleted_input_withdraws_exports(tmp_path):
    path = tmp_path / "data/site"
    path.mkdir(parents=True)
    (path / "observations.json").write_text(json.dumps(json.loads((ROOT / "data/site/observations.json").read_text())[:1]))
    data = published()
    data["series"]["bea_parents:china"]["unit"] = "affiliates"
    frozen = path / "business_presence.json"
    frozen.write_text(json.dumps(data))
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="counting units"):
        build(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    frozen.write_text(json.dumps(published()))
    with pytest.raises(ValueError, match="current business evidence"):
        build(tmp_path)
    (path / "business_current.json").write_text((ROOT / "data/site/business_current.json").read_text())
    assert build(tmp_path)["business_charts"] == 17
    page = BeautifulSoup((tmp_path / "site/business-presence.html").read_text(), "html.parser")
    assert not page.select('a[href="language-learning.html"]')
    frozen.unlink()
    assert build(tmp_path)["business_charts"] == 0
    assert not (tmp_path / "site/business-presence.html").exists()
    assert not list((tmp_path / "site/downloads").glob("business-*"))
    assert not list((tmp_path / "outputs/figures/business_presence").glob("*/*.*"))


def test_publication_is_business_only_with_complete_data_original_downloads_and_provenance(tmp_path):
    spec = importlib.util.spec_from_file_location("business_publication", ROOT / "scripts/build_business_publication.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "published"
    manifest = module.build_publication(ROOT, output, "verified-source-revision")
    page = BeautifulSoup((output / "index.html").read_text(), "html.parser")
    assert page.select_one('link[rel="canonical"]')["href"] == manifest["canonical_url"]
    assert "Interactive analysis" in page.select_one(".publication-header nav").text
    assert not page.select('a[href="language-learning.html"],iframe')
    assert len(page.select("svg[role=img]")) == 19
    assert not page.select("#business-controls,#annual-values,#module-chart,#uk-affiliates-china,#eu-affiliates-china")
    assert len(page.select(".business-card.native-chart,.business-card .native-chart")) == 19
    assert len(page.select(".business-count-card")) == 13
    assert len(page.select("#business-inward-data table tbody tr")) == 25
    assert page.select_one("#business-data").get("open") is None
    assert set(p.name for p in (output / "downloads").iterdir()) == {
        "business-presence.json", "business-observations.csv", "business-chart-values.csv", "business-current.json",
        "business-current-observations.csv", "business-current-chart-values.csv",
        "business-inward.json", "business-inward-observations.csv", "business-inward-chart-values.csv"}
    data = json.loads((output / "downloads/business-presence.json").read_text())
    assert data == published() and manifest["historical_observations"] == 266
    assert manifest["observations"] == 59
    assert manifest["inward_observations"] == 50
    assert manifest["source_revision"] == "verified-source-revision"
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == checksum
    with (output / "downloads/business-observations.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 266
    for link in page.select('a[href^="figures/"]'):
        assert link.has_attr("data-original-chart") and (output / link["href"].split("?")[0]).is_file()
    assert not (output / "business-presence.html").exists()
    assert not any("weibo" in str(p.relative_to(output)) or "language" in str(p.relative_to(output))
                   for p in output.rglob("*"))
    custom = output / "figures/business_presence/substack/custom.svg"
    custom.write_text("User-owned")
    source = tmp_path / "source"
    (source / "data/site").mkdir(parents=True)
    (source / "src/us_china_exchange").mkdir(parents=True)
    (source / "src/us_china_exchange/static").symlink_to(ROOT / "src/us_china_exchange/static", target_is_directory=True)
    data["observations"] = [r for r in data["observations"] if not r["series_id"].startswith("eurostat")]
    (source / "data/site/business_presence.json").write_text(json.dumps(data))
    (source / "data/site/business_current.json").write_text((ROOT / "data/site/business_current.json").read_text())
    module.build_publication(source, output, "next-revision")
    assert not list((output / "figures/business_presence").glob("*/eu-affiliates-china.*"))
    assert custom.read_text() == "User-owned"
    assert not list((output / "figures/business_presence").glob("*/*ubo-us-affiliates.*"))
    assert not list((output / "downloads").glob("business-inward*"))
