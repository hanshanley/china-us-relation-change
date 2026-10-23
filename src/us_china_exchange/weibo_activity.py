"""Calendar-day recovery counts and exact trailing thirty-day sample measures."""

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
DAILY_FIELDS = {"date", "recovered_posts", "account_ids", "partial_day"}
ROLLING_FIELDS = {"date", "recovered_posts", "observed_accounts", "observed_outlets",
                  "posts_per_day", "partial_window"}
ROLLING_CHARTS = {
    "rolling30-accounts": ("Channels represented in the last 30 days", "observed_accounts", "Distinct channels, trailing 30 days"),
    "rolling30-outlets": ("Publishers represented in the last 30 days", "observed_outlets", "Distinct publisher/brand groups, trailing 30 days"),
    "rolling30-posts": ("Posts recovered in the last 30 days", "recovered_posts", "Recovered posts, trailing 30 days"),
    "rolling30-average": ("Daily posts: 30-day running average", "posts_per_day", "Recovered posts/day, trailing 30-day mean"),
}


def parsed(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Activity timestamps require a timezone")
    return dt.astimezone(SHANGHAI)


def requested_days(windows, accounts):
    intervals = sorted((parsed(w["start"]), parsed(w["end"])) for w in windows)
    if not intervals:
        dates = [parsed(a[key]) for a in accounts
                 for key in ("earliest_publication_utc", "latest_publication_utc") if a[key]]
        if not dates:
            return []
        intervals = [(min(dates), max(dates) + timedelta(microseconds=1))]
    merged = []
    for start, end in intervals:
        if start >= end:
            raise ValueError("Invalid activity collection window")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    days = {}
    for start, end in merged:
        current = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while current < end:
            following = current + timedelta(days=1)
            label = current.date().isoformat()
            days[label] = days.get(label, True) and (start > current or end < following)
            current = following
    return [{"date": day, "partial_day": days[day]} for day in sorted(days)]


def daily_activity(posts, accounts, windows):
    counts, members = Counter(), defaultdict(set)
    for post in posts:
        day = parsed(post["published_utc"]).date().isoformat()
        counts[day] += 1
        members[day].add(post["account_id"])
    daily = [dict(period, recovered_posts=counts[period["date"]],
                  account_ids=sorted(members[period["date"]]))
             for period in requested_days(windows, accounts)]
    if sum(r["recovered_posts"] for r in daily) != len(posts):
        raise ValueError("Daily activity dates fall outside requested windows")
    return daily


def rolling_activity(daily, accounts):
    outlets = {a["account_id"]: a["outlet_id"] for a in accounts}
    queue, members, posts, incomplete = deque(), Counter(), 0, 0
    result = []
    for row in daily:
        day = datetime.strptime(row["date"], "%Y-%m-%d").date()
        first = day - timedelta(days=29)
        queue.append((day, row))
        posts += row["recovered_posts"]
        incomplete += int(row["partial_day"])
        members.update(row["account_ids"])
        while queue and queue[0][0] < first:
            _, removed = queue.popleft()
            posts -= removed["recovered_posts"]
            incomplete -= int(removed["partial_day"])
            members.subtract(removed["account_ids"])
            members += Counter()
        partial = len(queue) != 30 or incomplete != 0
        result.append({
            "date": row["date"], "partial_window": partial,
            "recovered_posts": None if partial else posts,
            "observed_accounts": None if partial else len(members),
            "observed_outlets": None if partial else len({outlets[a] for a in members}),
            "posts_per_day": None if partial else posts / 30,
        })
    return result


def validate_activity(summary):
    daily, rolling = summary["daily"], summary["rolling_30d"]
    if any(set(r) != DAILY_FIELDS for r in daily) or any(set(r) != ROLLING_FIELDS for r in rolling):
        raise ValueError("Unexpected Weibo daily or rolling fields")
    if [{"date": r["date"], "partial_day": r["partial_day"]} for r in daily] != requested_days(
            summary["source"]["requested_windows"], summary["accounts"]):
        raise ValueError("Daily activity periods do not match collection windows")
    account_ids = {a["account_id"] for a in summary["accounts"]}
    for row in daily:
        if (type(row["partial_day"]) is not bool or type(row["recovered_posts"]) is not int
                or row["recovered_posts"] < 0 or not isinstance(row["account_ids"], list)
                or any(not isinstance(account, str) for account in row["account_ids"])
                or row["account_ids"] != sorted(set(row["account_ids"]))
                or not set(row["account_ids"]) <= account_ids
                or len(row["account_ids"]) > row["recovered_posts"]
                or bool(row["account_ids"]) != bool(row["recovered_posts"])):
            raise ValueError("Invalid daily recovered-post or channel counts")
    monthly = Counter()
    for row in daily:
        monthly[row["date"][:7]] += row["recovered_posts"]
    if dict(monthly) != {r["month"]: r["recovered_posts"] for r in summary["monthly"]}:
        raise ValueError("Daily and monthly recovered-post totals do not reconcile")
    for row in rolling:
        if (type(row["partial_window"]) is not bool
                or any(value is not None and (type(value) is not int or value < 0)
                       for value in (row["recovered_posts"], row["observed_accounts"], row["observed_outlets"]))
                or (row["posts_per_day"] is not None
                    and (type(row["posts_per_day"]) not in (int, float) or row["posts_per_day"] < 0))):
            raise ValueError("Invalid rolling activity counts")
    if rolling != rolling_activity(daily, summary["accounts"]):
        raise ValueError("Trailing thirty-day counts or daily averages do not reconcile")
    return summary
