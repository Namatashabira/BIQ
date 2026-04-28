from datetime import datetime, timedelta

def format_date(date_obj: datetime, fmt: str = "%d %B %Y") -> str:
    """
    Formats a datetime object into a human-readable string.
    Default format: "23 January 2026"
    """
    if not date_obj:
        return ""
    return date_obj.strftime(fmt)


def parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime:
    """
    Converts a string to a datetime object.
    Default input format: "2026-01-23"
    """
    return datetime.strptime(date_str, fmt)


def reporting_period(days: int = 30) -> tuple[datetime, datetime]:
    """
    Returns a tuple of (start_date, end_date) for a report.
    Default is last 30 days.
    """
    end = datetime.today()
    start = end - timedelta(days=days)
    return start, end


def start_of_month(date_obj: datetime = None) -> datetime:
    """
    Returns the first day of the month for the given date.
    """
    date_obj = date_obj or datetime.today()
    return datetime(date_obj.year, date_obj.month, 1)


def end_of_month(date_obj: datetime = None) -> datetime:
    """
    Returns the last day of the month for the given date.
    """
    date_obj = date_obj or datetime.today()
    next_month = date_obj.replace(day=28) + timedelta(days=4)  # always next month
    return next_month - timedelta(days=next_month.day)
