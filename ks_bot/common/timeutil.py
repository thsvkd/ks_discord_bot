"""시간대(timezone) 변환과 datetime 파싱 유틸리티."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone
from enum import Enum
from zoneinfo import ZoneInfo

__all__ = ['Timezone', 'datetime_now', 'parse_utc_to_datetime', 'to_iso', 'unix_time_start']


class Timezone(Enum):
    """자주 쓰이는 IANA 타임존 식별자."""

    UTC = 'UTC'
    KST = 'Asia/Seoul'  # 한국 표준시
    JST = 'Asia/Tokyo'  # 일본 표준시
    CST_CHINA = 'Asia/Shanghai'  # 중국 표준시
    IST = 'Asia/Kolkata'  # 인도 표준시
    CET = 'Europe/Berlin'  # 중앙 유럽 시간
    EST = 'America/New_York'  # 미국 동부 표준시
    CST_US = 'America/Chicago'  # 미국 중부 표준시
    MST_US = 'America/Denver'  # 미국 산지 표준시
    PST = 'America/Los_Angeles'  # 미국 태평양 표준시
    AKST = 'America/Anchorage'  # 알래스카 표준시
    HST = 'Pacific/Honolulu'  # 하와이-알류샨 표준시
    AEST = 'Australia/Sydney'  # 호주 동부 표준시

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.value)


def unix_time_start() -> datetime:
    """UTC 기준 유닉스 에포크(1970-01-01T00:00:00Z)."""
    return datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def datetime_now(tz: Timezone = Timezone.KST) -> datetime:
    """지정한 타임존의 현재 시각(aware datetime)."""
    return datetime.now(tz=tz.zone)


def parse_utc_to_datetime(value: str | datetime, tz: Timezone = Timezone.KST) -> datetime:
    """UTC 문자열/naive datetime을 지정 타임존의 aware datetime으로 변환한다.

    `2024-01-01T00:00:00Z` 형태와 ISO 8601 형태를 모두 허용한다.
    """
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as e:
                raise ValueError(f'파싱할 수 없는 datetime 문자열입니다: {value!r}') from e

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)

    return parsed.astimezone(tz.zone)


def to_iso(value: datetime) -> str:
    """DB 저장용 ISO 8601 문자열로 직렬화한다."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.isoformat()
