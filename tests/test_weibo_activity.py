from datetime import datetime, timedelta

import pytest

from us_china_exchange.weibo_activity import daily_activity, rolling_activity, validate_activity


def test_thirty_day_window_is_inclusive_deduplicated_and_not_a_month():
    accounts = [{"account_id": "a", "outlet_id": "publisher"},
                {"account_id": "b", "outlet_id": "publisher"},
                {"account_id": "c", "outlet_id": "other"}]
    window = [{"start": "2024-01-31T16:00:00+00:00", "end": "2024-03-02T16:00:00+00:00"}]
    posts = [
        {"account_id": "a", "published_utc": "2024-01-31T16:00:00+00:00"},
        {"account_id": "a", "published_utc": "2024-02-28T16:00:00+00:00"},
        {"account_id": "b", "published_utc": "2024-02-29T15:59:59+00:00"},
        {"account_id": "c", "published_utc": "2024-02-29T16:00:00+00:00"},
    ]
    daily = daily_activity(posts, accounts, window)
    rows = rolling_activity(daily, accounts)
    assert len(daily) == 31
    assert all(r["partial_window"] and r["posts_per_day"] is None for r in rows[:29])
    assert rows[29] == dict(date="2024-03-01", partial_window=False, recovered_posts=4,
                           observed_accounts=3, observed_outlets=2, posts_per_day=4 / 30)
    assert rows[30] == dict(date="2024-03-02", partial_window=False, recovered_posts=3,
                           observed_accounts=3, observed_outlets=2, posts_per_day=3 / 30)
    assert daily[0]["date"] == "2024-02-01" and daily[0]["recovered_posts"] == 1


def test_calendar_gap_and_partial_days_invalidate_rolling_estimates():
    accounts = [{"account_id": "a", "outlet_id": "p"}]
    windows = [{"start": "2024-01-01T00:00:00+08:00", "end": "2024-02-01T00:00:00+08:00"},
               {"start": "2024-02-02T00:00:00+08:00", "end": "2024-03-04T12:00:00+08:00"}]
    daily = daily_activity([], accounts, windows)
    rows = {r["date"]: r for r in rolling_activity(daily, accounts)}
    assert rows["2024-01-30"]["posts_per_day"] == 0
    assert rows["2024-02-29"]["posts_per_day"] is None
    assert rows["2024-03-02"]["posts_per_day"] == 0
    assert rows["2024-03-04"]["posts_per_day"] is None
    assert daily[-1]["partial_day"] is True


def test_daily_and_rolling_validation_rejects_fabricated_counts_and_raw_text():
    accounts = [{"account_id": "a", "outlet_id": "p"}]
    windows = [{"start": "2024-01-01T00:00:00+08:00", "end": "2024-02-01T00:00:00+08:00"}]
    daily = daily_activity([{"account_id": "a", "published_utc": "2024-01-01T00:00:00+08:00"}], accounts, windows)
    summary = {"source": {"requested_windows": windows}, "accounts": accounts, "daily": daily,
               "rolling_30d": rolling_activity(daily, accounts), "monthly": [{"month": "2024-01", "recovered_posts": 1}]}
    validate_activity(summary)
    summary["rolling_30d"][-1]["observed_outlets"] = 2
    with pytest.raises(ValueError, match="do not reconcile"):
        validate_activity(summary)
    summary["rolling_30d"] = rolling_activity(daily, accounts)
    summary["daily"][0]["text"] = "PRIVATE"
    with pytest.raises(ValueError, match="Unexpected"):
        validate_activity(summary)
