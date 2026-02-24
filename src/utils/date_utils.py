from datetime import date, datetime, timedelta
from typing import Optional, Union


DateLike = Union[str, int, float, date, datetime, None]


def parse_any_date(value: DateLike) -> Optional[date]:
    """Parse Google Sheets serials and common date strings into a date object."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip().replace("'", "")
    if not raw or raw.lower() == "none":
        return None

    try:
        serial = float(raw)
        return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    except (TypeError, ValueError):
        pass

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def to_us_date(value: DateLike, fallback_today: bool = False) -> str:
    """Return M/D/YYYY for display/storage in Sheets."""
    parsed = parse_any_date(value)
    if parsed is None and fallback_today:
        parsed = datetime.now().date()
    if parsed is None:
        return ""
    return f"{parsed.month}/{parsed.day}/{parsed.year}"
