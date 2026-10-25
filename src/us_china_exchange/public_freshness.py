"""Public chart eligibility; retired choices and older data remain in the archive."""

import math
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar


POLICY = {"history_since": 2023, "snapshot_from": 2024, "snapshot_through": 2026}
RETIRED_STUDENT_MEASURES = {"enrolled_students", "degree_students"}
_PUBLIC = ContextVar("public_chart_freshness", default=False)


@contextmanager
def public_charts():
    token = _PUBLIC.set(True)
    try:
        yield
    finally:
        _PUBLIC.reset(token)


def public():
    return _PUBLIC.get()


def measurement_year(row):
    for key in ("field_end", "period_end", "reference"):
        value = row.get(key)
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    year = row.get("year")
    return year if isinstance(year, int) and not isinstance(year, bool) else None


def reported(row):
    value = row.get("value")
    if value is None:
        value = row.get("bound")
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def eligible(rows, snapshot=None):
    rows = [row for row in rows if row.get("measure") not in RETIRED_STUDENT_MEASURES
            and reported(row) and measurement_year(row) is not None]
    if not rows:
        return False
    periods = {(measurement_year(row), row.get("reference", row.get("period", ""))) for row in rows}
    if snapshot is None:
        snapshot = len(periods) == 1
    latest = max(measurement_year(row) for row in rows)
    return (POLICY["snapshot_from"] <= latest <= POLICY["snapshot_through"] if snapshot
            else latest >= POLICY["history_since"])


def current_groups(groups):
    if not public():
        return groups
    rows = defaultdict(list)
    snapshots = set()
    for group in groups:
        rows[group["id"]].extend(group["points"])
        if "snapshot" in group.get("cadence", "").lower():
            snapshots.add(group["id"])
    allowed = {sid for sid, points in rows.items() if eligible(points)}
    result = []
    for group in groups:
        if group["id"] in snapshots:
            points = [row for row in group["points"] if eligible([row], snapshot=True)]
            if points:
                result.append(dict(group, points=points))
        elif group["id"] in allowed and group["points"]:
            result.append(group)
    return result


def annual_series(rows):
    grouped = defaultdict(list)
    for row in rows:
        if row["frequency"] == "annual":
            grouped[row["series_id"]].append(row)
    return {sid for sid, points in grouped.items() if eligible(points)}
