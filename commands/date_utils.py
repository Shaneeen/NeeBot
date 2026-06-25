from __future__ import annotations

from datetime import date, datetime, timedelta

WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def parse_optional_date_args(args: list[str], default_date: date) -> tuple[date, str]:
    if not args:
        return default_date, ""

    candidate = args[0].strip().lower()
    if candidate == "today":
        return default_date, " ".join(args[1:]).strip()
    if candidate == "yesterday":
        return default_date - timedelta(days=1), " ".join(args[1:]).strip()
    try:
        parsed = datetime.strptime(candidate, "%Y-%m-%d").date()
        return parsed, " ".join(args[1:]).strip()
    except ValueError:
        return default_date, " ".join(args).strip()


def format_human_date(target_date: date, today: date) -> str:
    if target_date == today:
        return "today"
    if target_date == today - timedelta(days=1):
        return "yesterday"
    return target_date.strftime("%d %b %Y")


def parse_todo_date_args(args: list[str], default_date: date) -> tuple[date | None, str]:
    if not args:
        return None, ""

    lowered = [arg.strip().lower() for arg in args]

    if lowered[0] == "today":
        return default_date, " ".join(args[1:]).strip()

    if lowered[0] == "tomorrow":
        return default_date + timedelta(days=1), " ".join(args[1:]).strip()

    if lowered[0] == "next" and len(lowered) >= 2 and lowered[1] in WEEKDAY_MAP:
        base_date = _resolve_weekday(default_date, WEEKDAY_MAP[lowered[1]]) + timedelta(days=7)
        return base_date, " ".join(args[2:]).strip()

    if lowered[0] in WEEKDAY_MAP:
        return _resolve_weekday(default_date, WEEKDAY_MAP[lowered[0]]), " ".join(args[1:]).strip()

    return None, " ".join(args).strip()


def week_bounds(target_date: date) -> tuple[date, date]:
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def _resolve_weekday(default_date: date, weekday: int) -> date:
    delta = weekday - default_date.weekday()
    if delta < 0:
        delta += 7
    return default_date + timedelta(days=delta)
