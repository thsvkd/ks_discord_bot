"""봇 전역에서 사용하는 예외 계층.

모든 예외는 `KSBotError`를 상속하므로, 최상위 핸들러에서 한 번에 잡을 수 있다.
사용자에게 그대로 보여줄 문구는 `user_message`로 노출한다.
"""

from __future__ import annotations

__all__ = [
    'AlreadyExistsError',
    'ApiRequestError',
    'BalancerError',
    'ConfigError',
    'KSBotError',
    'NotEnoughMatchesError',
    'PlayerMatchStatsNotFoundError',
    'PlayerNotFoundError',
    'RateLimitError',
    'ResourceNotFoundError',
]


class KSBotError(Exception):
    """모든 봇 예외의 최상위 타입."""

    default_message = '알 수 없는 오류가 발생했습니다.'

    def __init__(self, message: str = ''):
        self.message = message or self.default_message
        super().__init__(self.message)

    @property
    def user_message(self) -> str:
        """디스코드 사용자에게 보여줄 메시지."""
        return self.message

    def __str__(self) -> str:
        return f'[{type(self).__name__}] {self.message}'


class ConfigError(KSBotError):
    """환경 변수 등 실행 설정이 잘못된 경우."""

    default_message = '봇 설정이 올바르지 않습니다.'


class BalancerError(KSBotError):
    """PUBG 밸런서 도메인 오류의 기반 타입."""

    default_message = '밸런서 처리 중 오류가 발생했습니다.'


class PlayerNotFoundError(BalancerError):
    def __init__(self, player_name: str = '', message: str = ''):
        self.player_name = player_name
        super().__init__(message or f'플레이어를 찾을 수 없습니다: {player_name or "(이름 없음)"}')

    @property
    def user_message(self) -> str:
        if self.player_name:
            return f'플레이어 `{self.player_name}`을(를) 찾을 수 없습니다.'
        return '플레이어를 찾을 수 없습니다.'


class PlayerMatchStatsNotFoundError(BalancerError):
    def __init__(self, player_name: str = '', match_id: str = '', message: str = ''):
        self.player_name = player_name
        self.match_id = match_id
        super().__init__(message or f'매치 전적을 찾을 수 없습니다. player={player_name or "?"}, match={match_id or "?"}')

    @property
    def user_message(self) -> str:
        return '최근 매치 전적을 찾을 수 없습니다.'


class NotEnoughMatchesError(BalancerError):
    def __init__(self, match_num: int = 0, required_match_num: int = 0, message: str = ''):
        self.match_num = match_num
        self.required_match_num = required_match_num
        super().__init__(message or f'매치 수가 부족합니다: {match_num}/{required_match_num}')

    @property
    def user_message(self) -> str:
        return f'점수를 계산하기에 매치 수가 부족합니다. ({self.match_num}/{self.required_match_num})'


class AlreadyExistsError(BalancerError):
    default_message = '이미 존재하는 데이터입니다.'


class ApiRequestError(KSBotError):
    """외부 API 호출 실패."""

    default_message = 'API 요청에 실패했습니다.'

    @property
    def user_message(self) -> str:
        return 'PUBG API 요청에 실패했습니다. 잠시 후 다시 시도해주세요.'


class ResourceNotFoundError(ApiRequestError):
    """외부 API가 404를 반환한 경우."""

    default_message = '요청한 리소스를 찾을 수 없습니다.'


class RateLimitError(ApiRequestError):
    """외부 API 호출량 제한에 걸린 경우."""

    default_message = 'API 요청 한도를 초과했습니다.'

    @property
    def user_message(self) -> str:
        return 'PUBG API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.'
