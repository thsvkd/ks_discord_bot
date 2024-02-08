from enum import Enum, auto


class ErrorCode_Balancer(Enum):
    UNDEFINED = auto()
    NO_ERROR = 'no_error'
    PLAYER_NOT_FOUND = 'player_not_found'
    ALREADY_EXIST = 'already_exist'
    ALREADY_UPDATED = 'already_updated'
