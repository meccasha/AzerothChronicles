"""Expansion/season windows and named reporting periods.

The windows are configuration (app/data/periods.json), not facts fetched from Blizzard.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

PERIODS_FILE = Path(__file__).resolve().parent.parent / "data" / "periods.json"


@dataclass(frozen=True)
class Window:
    key: str
    name: str
    start: datetime
    end: datetime | None
    expansion: str | None = None

    def contains(self, ts: datetime) -> bool:
        return ts >= self.start and (self.end is None or ts < self.end)


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)


@lru_cache
def _load() -> tuple[list[Window], list[Window]]:
    raw = json.loads(PERIODS_FILE.read_text())
    expansions = [Window(e["key"], e["name"], _dt(e["start"]), _dt(e["end"])) for e in raw["expansions"]]
    seasons = [
        Window(s["key"], s["name"], _dt(s["start"]), _dt(s["end"]), s.get("expansion"))
        for s in raw["seasons"]
    ]
    return expansions, seasons


def expansions() -> list[Window]:
    return _load()[0]


def seasons() -> list[Window]:
    return _load()[1]


def expansion_for(ts: datetime) -> Window | None:
    return next((w for w in expansions() if w.contains(ts)), None)


def season_for(ts: datetime) -> Window | None:
    return next((w for w in seasons() if w.contains(ts)), None)


def window_by_key(key: str) -> Window | None:
    return next((w for w in [*expansions(), *seasons()] if w.key == key), None)


PERIOD_KEYS = ("all_time", "current_expansion", "current_season", "last_30_days", "last_90_days", "custom")


def resolve_period(
    period: str, start: datetime | None = None, end: datetime | None = None, now: datetime | None = None
) -> tuple[datetime | None, datetime | None, str]:
    """Return (start, end, label) for a named reporting period. None bounds mean unbounded."""
    now = now or datetime.now(UTC)
    if period == "all_time":
        return None, None, "All time"
    if period == "last_30_days":
        return now - timedelta(days=30), None, "Last 30 days"
    if period == "last_90_days":
        return now - timedelta(days=90), None, "Last 90 days"
    if period == "current_expansion":
        w = expansion_for(now)
        return (w.start, w.end, w.name) if w else (None, None, "All time")
    if period == "current_season":
        w = season_for(now)
        if w:
            return w.start, w.end, w.name
        return now - timedelta(days=90), None, "No active season configured (last 90 days)"
    if period == "custom":
        if start is None and end is None:
            raise ValueError("custom period requires start and/or end")
        if start and end and end <= start:
            raise ValueError("end must be after start")
        return start, end, "Custom range"
    raise ValueError(f"unknown period '{period}'")


def week_start(ts: datetime) -> datetime:
    d = ts.astimezone(UTC).date()
    monday = d - timedelta(days=d.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=UTC)


def month_start(ts: datetime) -> datetime:
    d = ts.astimezone(UTC)
    return datetime(d.year, d.month, 1, tzinfo=UTC)


def next_month(ts: datetime) -> datetime:
    return datetime(ts.year + (ts.month // 12), ts.month % 12 + 1, 1, tzinfo=UTC)
