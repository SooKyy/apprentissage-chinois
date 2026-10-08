from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def utcnow() -> datetime:
    """Maintenant, en UTC naïf (format stocké en base)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc)


def to_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def study_day(moment: datetime):
    """Jour d'étude local d'un instant UTC naïf. La journée bascule à day_rollover_hour, pas à minuit."""
    settings = get_settings()
    local = to_aware(moment).astimezone(ZoneInfo(settings.app_timezone))
    return (local - timedelta(hours=settings.day_rollover_hour)).date()


def day_start(moment: datetime) -> datetime:
    """Début (UTC naïf) du jour d'étude contenant `moment`."""
    settings = get_settings()
    tz = ZoneInfo(settings.app_timezone)
    day = study_day(moment)
    local_start = datetime(day.year, day.month, day.day, settings.day_rollover_hour, tzinfo=tz)
    return to_naive(local_start)
