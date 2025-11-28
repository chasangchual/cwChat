import datetime
from typing import Optional
from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo  # py>=3.9

class DateUtil:
    @classmethod
    def now_datetime_iso(cls) -> str:
        return datetime.now(dt_timezone.utc).isoformat()

    @classmethod
    def iso_date_or_default(cls, value: Optional[str], *, default: str) -> str:
        """why: keep rendering robust even if upstream passes a bad date."""
        if not value:
            return default
        try:
            return date.fromisoformat(str(value)).isoformat()
        except (TypeError, ValueError):
            return default

    @classmethod
    def now_date_iso(cls, tz: str = "UTC") -> str:
        """why: align 'today' with business TZ to prevent off-by-one errors."""
        tz_info = dt_timezone.utc
        if ZoneInfo is not None:
            try:
                tz_info = ZoneInfo(cls.normalize_timezone(tz))
            except (TypeError, ValueError):
                tz_info = dt_timezone.utc
        return datetime.now(tz_info).date().isoformat()


    @classmethod
    def normalize_timezone(cls, value: Optional[str]) -> str:
        """why: avoid breaking on bad tz strings; default to UTC."""
        tz = (value or "UTC").strip() or "UTC"
        if ZoneInfo is None:
            return "UTC" if tz.upper() in {"Z", "UTC"} else tz  # best-effort without validation
        try:
            ZoneInfo(tz)  # validate existence
            return tz
        except (TypeError, ValueError):
            return "UTC"