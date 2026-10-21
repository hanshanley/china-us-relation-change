import pytest

from us_china_exchange.model import MEASURES, change, coverage, observation, validate


def row(year=2020, value=100, **kwargs):
    return observation("test", "CHN", "USA", "visitors", year, value, "Residence; overnight", **kwargs)


def test_zero_is_not_missing_and_duplicate_fails():
    assert validate([row(value=0)])[0]["value"] == 0
    with pytest.raises(ValueError, match="Duplicate"):
        validate([row(), row()])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_values_rejected(value):
    with pytest.raises(ValueError):
        validate([row(value=value)])


def test_null_requires_explicit_status():
    with pytest.raises(ValueError):
        validate([row(value=None)])
    assert validate([row(value=None, status="suppressed")])[0]["status"] == "suppressed"


def test_change_and_zero_baseline():
    assert change(row(2024, 150), row())["percent"] == 50
    assert change(row(2024), row(value=0))["percent"] is None
    assert change(row(2024), None)["absolute"] is None


def test_incompatible_population_and_periods_not_compared():
    current = row(2024, comparability="citizenship")
    assert change(current, row())["absolute"] is None
    assert change(row(2024, frequency="ytd", month=6), row())["absolute"] is None


def test_coverage_includes_all_geographies_and_explicit_gaps():
    result = coverage([row()])
    assert len(result) == 4 * 2 * len(MEASURES)
    assert sum(r["observations"] for r in result) == 1
    assert all(r["reason"] for r in result if not r["observations"])


def test_academic_label_preserves_year_ending():
    assert row(period_basis="academic")["period"] == "2019/20"
    assert row(period_basis="academic")["period_start"] is None
    assert change(row(2024, 200, period_basis="academic"),
                  row(period_basis="academic"))["percent"] == 100


def test_february_compares_across_leap_years():
    assert change(row(2024, 150, frequency="monthly", month=2),
                  row(2023, 100, frequency="monthly", month=2))["percent"] == 50
    with pytest.raises(ValueError, match="ending month"):
        row(frequency="monthly")
