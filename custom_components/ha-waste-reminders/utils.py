from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
import re
import unicodedata

from homeassistant.util import dt as dt_util

GERMAN_WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

GERMAN_MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

WASTE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Restmüll", (r"\brestmull\b", r"\brestmuell\b", r"\brestabfall\b", r"\bhausmull\b", r"\bhausmuell\b")),
    ("Papier", (r"\bpapier\b", r"\bpapiertonne\b", r"\baltpapier\b", r"\bpapiermull\b", r"\bpapiermuell\b")),
    ("Gelber Sack", (r"\bgelber\s+sack\b", r"\bgelbe\s+tonne\b", r"\bwertstoff\b", r"\bwertstoffe\b", r"\bwertstofftonne\b")),
    ("Biomüll", (r"\bbio\b", r"\bbiomull\b", r"\bbiomuell\b", r"\bbiotonne\b")),
)


def normalize_text(value: str) -> str:
    """Normalize text for robust pattern matching."""
    collapsed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in collapsed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text.casefold()).strip()


def detect_waste_type(summary: str | None) -> str | None:
    """Detect a normalized waste type from a calendar event summary."""
    if not summary:
        return None

    normalized = normalize_text(summary)
    for waste_type, patterns in WASTE_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return waste_type
    return None


def normalize_event_date(value: object) -> date | None:
    """Convert calendar response start values to a local date."""
    if isinstance(value, datetime):
        return dt_util.as_local(value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if parsed_datetime := dt_util.parse_datetime(value):
            return dt_util.as_local(parsed_datetime).date()
        if parsed_date := dt_util.parse_date(value):
            return parsed_date
    return None


def slugify(value: str) -> str:
    """Build an ASCII slug for entity ids."""
    return normalize_text(value).replace(" ", "_")


def normalize_time_value(value: object, default: time) -> time:
    """Convert persisted option values to a time instance."""
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return default
    return default


def normalize_month_value(value: object, default: int) -> int:
    """Convert persisted option values to a month number."""
    try:
        month = int(value)
    except (TypeError, ValueError):
        return default
    if 1 <= month <= 12:
        return month
    return default


def join_human_list(values: Iterable[str]) -> str:
    """Format a human-friendly list in German."""
    parts = list(values)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} und {parts[-1]}"


def format_short_german_date(value: date) -> str:
    """Format a date like 'Heute (08.06.)' or 'Morgen (09.06.)'."""
    today = dt_util.now().date()
    if value == today:
        label = "Heute"
    elif value == today + timedelta(days=1):
        label = "Morgen"
    else:
        label = GERMAN_WEEKDAYS[value.weekday()]
    return f"{label} ({value.strftime('%d.%m.')})"


def month_name(month: int) -> str:
    """Return the German month name for a month number."""
    return GERMAN_MONTHS[month - 1]


def month_options() -> list[str]:
    """Return all German month names in calendar order."""
    return list(GERMAN_MONTHS)


def month_name_to_number(value: object, default: int) -> int:
    """Convert a month name or legacy stored value to a month number."""
    if isinstance(value, str):
        for index, month in enumerate(GERMAN_MONTHS, start=1):
            if value == month:
                return index
        try:
            return normalize_month_value(value, default)
        except Exception:
            return default
    return normalize_month_value(value, default)
