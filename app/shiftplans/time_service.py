"""Time and date parsing helpers for shift planning."""

from datetime import date, datetime, timedelta


def parse_date(value):
    """Parse an ISO date string or default to today."""
    if not value:
        return date.today()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("start_date must use YYYY-MM-DD") from exc


def parse_days(value):
    """Parse and clamp the shift plan duration in days."""
    try:
        days = int(value or 7)
    except (TypeError, ValueError) as exc:
        raise ValueError("days must be a number") from exc
    return min(max(days, 1), 31)


def parse_time(value):
    """Parse a HH:MM time value."""
    return datetime.strptime(value, "%H:%M").time()


def hours_between(start, end):
    """Calculate shift length in hours, supporting overnight shifts."""
    start_time = parse_time(start)
    end_time = parse_time(end)
    start_dt = datetime.combine(date.today(), start_time)
    end_dt = datetime.combine(date.today(), end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return (end_dt - start_dt).total_seconds() / 3600


def shift_datetimes(work_date, start, end):
    """Return start and end datetimes for one shift entry."""
    start_dt = datetime.combine(work_date, parse_time(start))
    end_dt = datetime.combine(work_date, parse_time(end))
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt
