"""PUBG API가 사용하는 열거형 정의."""

from __future__ import annotations

from enum import Enum

__all__ = ['GameMode', 'MatchType', 'Tier']


class _UndefinedFallbackEnum(Enum):
    """알 수 없는 값이 들어오면 예외 대신 `UNDEFINED`로 수렴하는 열거형.

    PUBG API는 예고 없이 새 모드/타입을 추가하므로, 값 변환 실패로 봇이 죽지 않도록 한다.
    """

    @classmethod
    def _missing_(cls, value: object) -> _UndefinedFallbackEnum:
        return cls.UNDEFINED

    @classmethod
    def from_string(cls, value: str = '') -> _UndefinedFallbackEnum:
        return cls(value)

    def __str__(self) -> str:
        return str(self.value)


class GameMode(_UndefinedFallbackEnum):
    UNDEFINED = 'undefined'
    DUO = 'duo'
    DUO_FPP = 'duo-fpp'
    SOLO = 'solo'
    SOLO_FPP = 'solo-fpp'
    SQUAD = 'squad'
    SQUAD_FPP = 'squad-fpp'
    CONQUEST_DUO = 'conquest-duo'
    CONQUEST_DUO_FPP = 'conquest-duo-fpp'
    CONQUEST_SOLO = 'conquest-solo'
    CONQUEST_SOLO_FPP = 'conquest-solo-fpp'
    CONQUEST_SQUAD = 'conquest-squad'
    CONQUEST_SQUAD_FPP = 'conquest-squad-fpp'
    ESPORTS_DUO = 'esports-duo'
    ESPORTS_DUO_FPP = 'esports-duo-fpp'
    ESPORTS_SOLO = 'esports-solo'
    ESPORTS_SOLO_FPP = 'esports-solo-fpp'
    ESPORTS_SQUAD = 'esports-squad'
    ESPORTS_SQUAD_FPP = 'esports-squad-fpp'
    LAB_TPP = 'lab-tpp'
    LAB_FPP = 'lab-fpp'
    NORMAL_DUO = 'normal-duo'
    NORMAL_DUO_FPP = 'normal-duo-fpp'
    NORMAL_SOLO = 'normal-solo'
    NORMAL_SOLO_FPP = 'normal-solo-fpp'
    NORMAL_SQUAD = 'normal-squad'
    NORMAL_SQUAD_FPP = 'normal-squad-fpp'
    TDM = 'tdm'
    WAR_DUO = 'war-duo'
    WAR_DUO_FPP = 'war-duo-fpp'
    WAR_SOLO = 'war-solo'
    WAR_SOLO_FPP = 'war-solo-fpp'
    WAR_SQUAD = 'war-squad'
    WAR_SQUAD_FPP = 'war-squad-fpp'
    ZOMBIE_DUO = 'zombie-duo'
    ZOMBIE_DUO_FPP = 'zombie-duo-fpp'
    ZOMBIE_SOLO = 'zombie-solo'
    ZOMBIE_SOLO_FPP = 'zombie-solo-fpp'
    ZOMBIE_SQUAD = 'zombie-squad'
    ZOMBIE_SQUAD_FPP = 'zombie-squad-fpp'

    @property
    def is_squad(self) -> bool:
        return 'squad' in self.value


class MatchType(_UndefinedFallbackEnum):
    UNDEFINED = 'undefined'
    AIROYALE = 'airoyale'
    ARCADE = 'arcade'
    CUSTOM = 'custom'
    EVENT = 'event'
    SEASONAL = 'seasonal'
    TRAINING = 'training'
    NORMAL = 'official'
    RANKED = 'competitive'


class Tier(_UndefinedFallbackEnum):
    UNDEFINED = 'undefined'
    UNRANKED = 'unranked'
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'
    DIAMOND = 'diamond'
    MASTER = 'master'
