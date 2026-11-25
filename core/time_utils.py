from datetime import date, datetime, time, timedelta, timezone

def utc_today() -> date:
    return datetime.now(timezone.utc).date()

def utc_day_bounds(d: date):
    """Return [start, end) for a calendar day in UTC."""
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)