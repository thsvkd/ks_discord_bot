"""전투력(스탯 점수) 계산.

I/O가 전혀 없는 순수 함수로 분리해 단위 테스트가 가능하도록 한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from ks_bot.common.enums import MatchType
from ks_bot.common.models import PlayerMatchStats, Stats
from ks_bot.logging_config import get_logger

__all__ = ['RANKED_MATCH_SCORE', 'SCORABLE_MATCH_TYPES', 'SCORE_WEIGHTS', 'aggregate_stats', 'calculate_match_score', 'calculate_stats_score']

logger = get_logger(__name__)

# 일반 매치 점수: BASE + RANK_WEIGHT/등수 + DAMAGE_WEIGHT*(딜량/100) + ASSIST_WEIGHT*어시스트
SCORE_WEIGHTS = {
    'BASE': -2.7557,
    'RANK': 13.2481,
    'DAMAGE': 3.5403,
    'ASSIST': 1.4424,
}
# 랭크 매치는 매치별 상세 가중치 대신 고정 점수를 사용한다.
RANKED_MATCH_SCORE = 1.2

SCORABLE_MATCH_TYPES = (MatchType.NORMAL, MatchType.RANKED)


def calculate_match_score(match: PlayerMatchStats) -> float:
    """매치 1건의 점수를 계산한다."""
    if match.match_type == MatchType.RANKED:
        return RANKED_MATCH_SCORE

    rank_term = SCORE_WEIGHTS['RANK'] / match.win_place if match.win_place > 0 else 0.0
    return SCORE_WEIGHTS['BASE'] + rank_term + SCORE_WEIGHTS['DAMAGE'] * (match.damage_dealt / 100) + SCORE_WEIGHTS['ASSIST'] * match.assists


def calculate_stats_score(matches: Sequence[PlayerMatchStats]) -> float:
    """매치 목록의 평균 점수를 계산한다. 점수화할 수 없는 매치는 제외한다."""
    scores = []
    for match in matches:
        if match.match_type not in SCORABLE_MATCH_TYPES:
            logger.debug('점수 계산에서 제외된 매치 타입입니다: %s', match.match_type)
            continue
        scores.append(calculate_match_score(match))

    return sum(scores) / len(scores) if scores else 0.0


def aggregate_stats(matches: Sequence[PlayerMatchStats]) -> Stats:
    """최근 매치 목록을 집계해 `Stats`를 만든다."""
    rounds_played = len(matches)
    if rounds_played == 0:
        return Stats()

    kills = sum(match.kills for match in matches)
    assists = sum(match.assists for match in matches)
    # 1등이 아니면 사망한 것으로 간주한다.
    deaths = sum(1 for match in matches if match.win_place != 1)

    return Stats(
        rounds_played=rounds_played,
        avg_rank=sum(match.win_place for match in matches) / rounds_played,
        top10_ratio=sum(1 for match in matches if match.win_place <= 10) / rounds_played,
        win_ratio=sum(1 for match in matches if match.win_place == 1) / rounds_played,
        damage_dealt=sum(match.damage_dealt for match in matches),
        kills=kills,
        assists=assists,
        deaths=deaths,
        kda=(kills + assists) / deaths if deaths else float(kills + assists),
        score=calculate_stats_score(matches),
    )
