from datetime import datetime
import pytz
from enum import Enum


class Timezone(Enum):
    UTC = 'UTC'
    KST = 'Asia/Seoul'  # 한국 시간대
    EST = 'America/New_York'  # 동부 표준시 (미국)
    PST = 'America/Los_Angeles'  # 태평양 표준시 (미국)
    CET = 'Europe/Berlin'  # 중앙 유럽 시간
    IST = 'Asia/Kolkata'  # 인도 표준시
    CST_CHINA = 'Asia/Shanghai'  # 중국 표준시
    JST = 'Asia/Tokyo'  # 일본 표준시
    AST_CANADA = 'America/Halifax'  # 대서양 표준시 (캐나다)
    NST_CANADA = 'America/St_Johns'  # 뉴펀들랜드 표준시 (캐나다)
    MST_CANADA = 'America/Edmonton'  # 산지 표준시 (캐나다)
    PST_CANADA = 'America/Vancouver'  # 태평양 표준시 (캐나다)
    EST_CANADA = 'America/Toronto'  # 동부 표준시 (캐나다)
    CST_US = 'America/Chicago'  # 중부 표준시 (미국)
    MST_US = 'America/Denver'  # 산지 표준시 (미국)
    HST = 'Pacific/Honolulu'  # 하와이-알류샨 표준시
    AKST = 'America/Anchorage'  # 알래스카 표준시
    AEST = 'Australia/Sydney'  # 호주 동부 표준시
    ACST = 'Australia/Adelaide'  # 호주 중부 표준시
    AWST = 'Australia/Perth'  # 호주 서부 표준시

    def to_pytz_timezone(self) -> pytz.timezone:
        return pytz.timezone(self.value)


def unix_time_start() -> datetime:
    return datetime(1970, 1, 1)


def parse_utc_to_datetime(utc_str, tz_str: Timezone = Timezone.KST) -> datetime:
    try:
        utc_time = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            utc_time = datetime.fromisoformat(utc_str)
        except ValueError as e:
            raise ValueError(f"Unable to parse the datetime string: {utc_str}") from e

    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=pytz.utc)

    target_tz = pytz.timezone(tz_str.value)
    converted_time = utc_time.astimezone(target_tz)

    return converted_time
