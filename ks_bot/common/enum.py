from enum import Enum, auto


class GameMode(Enum):
    UNDEFINED = auto()
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

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED


class MatchType(Enum):
    UNDEFINED = auto()
    AIROYALE = 'airoyale'
    ARCADE = 'arcade'
    CUSTOM = 'custom'
    EVENT = 'event'
    SEASONAL = 'seasonal'
    TRAINING = 'training'
    NORMAL = 'official'
    RANKED = 'competitive'

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED


class Tier(Enum):
    UNDEFINED = auto()
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'
    DIAMOND = 'diamond'
    MASTER = 'master'

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED
