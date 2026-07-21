from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


UTC = timezone.utc


def get_business_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def get_utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_utc(value: datetime) -> datetime:
    return ensure_aware_utc(value)


def to_business_timezone(value: datetime) -> datetime:
    return ensure_aware_utc(value).astimezone(get_business_timezone())


def get_business_now() -> datetime:
    return get_utc_now().astimezone(get_business_timezone())


def get_business_date() -> date:
    return get_business_now().date()


def get_business_day_range(target_date: date | str | None = None) -> tuple[datetime, datetime]:
    if target_date is None:
        target = get_business_date()
    elif isinstance(target_date, str):
        target = date.fromisoformat(target_date)
    else:
        target = target_date

    business_tz = get_business_timezone()
    start_local = datetime.combine(target, time.min, tzinfo=business_tz)
    next_start_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), next_start_local.astimezone(UTC)
