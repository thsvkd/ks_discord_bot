from enum import Enum, auto


class ErrorCode_Balancer(Enum):
    UNDEFINED = auto()
    NO_ERROR = 'no_error'
    PLAYER_NOT_FOUND = 'player_not_found'
    PLAYER_MATCH_STATS_NOT_FOUND = 'player_match_stats_not_found'
    PLAYER_MATCH_STATS_NOT_ENOUGH = 'player_match_stats_not_enough'
    ALREADY_EXIST = 'already_exist'
    API_REQUEST_ERROR = 'api_request_error'
    INDEX_ERROR = 'index_error'
    KEY_ERROR = 'key_error'


class Error_Balancer(Exception):
    def __init__(self, code: ErrorCode_Balancer = ErrorCode_Balancer.UNDEFINED, message: str = ''):
        self.code = code
        self.message = message

    def __str__(self):
        return f'Error_Balancer: {self.code} - {self.message}'


class NoError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.NO_ERROR, message)

    def __str__(self):
        return f'NoError_Balancer: {self.message}'


class PlayerNotFoundError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.PLAYER_NOT_FOUND, message)

    def __str__(self):
        return f'PlayerNotFoundError_Balancer: {self.message}'


class PlayerMatchStatsNotFoundError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.PLAYER_MATCH_STATS_NOT_FOUND, message)

    def __str__(self):
        return f'PlayerMatchStatsNotFoundError_Balancer: {self.message}'


class PlayerMatchStatsNotEnoughError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.PLAYER_MATCH_STATS_NOT_ENOUGH, message)

    def __str__(self):
        return f'PlayerMatchStatsNotFoundError_Balancer: {self.message}'


class AlreadyExistError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.ALREADY_EXIST, message)

    def __str__(self):
        return f'AlreadyExistError_Balancer: {self.message}'


class APIRequestError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.API_REQUEST_ERROR, message)

    def __str__(self):
        return f'APIRequestError_Balancer: {self.message}'


class IndexError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.INDEX_ERROR, message)

    def __str__(self):
        return f'IndexError_Balancer: {self.message}'


class KeyError_Balancer(Error_Balancer):
    def __init__(self, message: str = ''):
        super().__init__(ErrorCode_Balancer.KEY_ERROR, message)

    def __str__(self):
        return f'KeyError_Balancer: {self.message}'
