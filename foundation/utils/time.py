# utils/time.py

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

# ----------------------------
# Current Time
# ----------------------------


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_local() -> datetime:
    return datetime.now().astimezone()


# ----------------------------
# Timestamp
# ----------------------------


def to_timestamp(dt: datetime) -> float:
    return dt.timestamp()


def from_timestamp(ts: int | float, tz: timezone | None = None) -> datetime:
    if tz is None:
        return datetime.fromtimestamp(ts)
    return datetime.fromtimestamp(ts, tz=tz)


# ----------------------------
# Formatting
# ----------------------------


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return dt.strftime(fmt)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def compact_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def compact_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%d_%H%M%S")


# ----------------------------
# Timezone Utilities
# ----------------------------


def utc() -> timezone:
    return UTC


def fixed_offset(hours: int, minutes: int = 0) -> timezone:
    return timezone(timedelta(hours=hours, minutes=minutes))


def to_timezone(dt: datetime, tz: timezone) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz)


# ----------------------------
# Time Arithmetic
# ----------------------------


def add_seconds(dt: datetime, seconds: int) -> datetime:
    return dt + timedelta(seconds=seconds)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


def add_hours(dt: datetime, hours: int) -> datetime:
    return dt + timedelta(hours=hours)


def add_days(dt: datetime, days: int) -> datetime:
    return dt + timedelta(days=days)


# ----------------------------
# Comparison
# ----------------------------


def is_past(dt: datetime) -> bool:
    return dt < now_local()


def is_future(dt: datetime) -> bool:
    return dt > now_local()


def diff_seconds(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds()


def diff_minutes(a: datetime, b: datetime) -> float:
    return diff_seconds(a, b) / 60


def diff_hours(a: datetime, b: datetime) -> float:
    return diff_seconds(a, b) / 3600
