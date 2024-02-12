from enum import Enum, auto


class Error_Balancer(Exception):
    def __init__(self, message: str = ''):
        self.message = message

    def __str__(self):
        return f'[{self.__class__.__name__}] error: {self.message}'


class PlayerNotFoundError_Balancer(Error_Balancer):
    def __init__(self, player_name: str = ''):
        super().__init__()
        self.player_name = player_name
        self.message = f'[{self.__class__.__name__}] Player not found: {self.player_name}.'

    def __str__(self):
        return self.message


class PlayerMatchStatsNotFoundError_Balancer(Error_Balancer):
    def __init__(self, match_id: str = ''):
        super().__init__()
        self.match_id = match_id
        self.message = f'[{self.__class__.__name__}] Match not found: {self.match_id}.'

    def __str__(self):
        return self.message


class PlayerMatchStatsNotEnoughError_Balancer(Error_Balancer):
    def __init__(self, match_num: int, max_match_num: int):
        super().__init__()
        self.match_num = match_num
        self.max_match_num = max_match_num
        self.message = f'[{self.__class__.__name__}] Match is not enough: {self.match_num}/{self.max_match_num}.'

    def __str__(self):
        return self.message


class AlreadyExistError_Balancer(Error_Balancer):
    def __init__(self):
        super().__init__()
        self.message = f'[{self.__class__.__name__}] Already exist.'

    def __str__(self):
        return self.message


class APIRequestError_Balancer(Error_Balancer):
    def __init__(self):
        super().__init__()
        self.message = f'[{self.__class__.__name__}] API request failed.'

    def __str__(self):
        return self.message
