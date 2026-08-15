"""전투력(스탯 점수) 계산.

I/O가 전혀 없는 순수 함수로 분리해 단위 테스트가 가능하도록 한다.
설계 근거는 `docs/scoring-design.md`를 따른다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from ks_bot.common.enums import GameMode, MatchType, Tier
from ks_bot.common.models import PlayerMatchStats, Stats
from ks_bot.logging_config import get_logger

__all__ = [
    'DAMAGE_REFERENCE',
    'MODE_TEAM_COUNT',
    'SCORABLE_MATCH_TYPES',
    'aggregate_stats',
    'calculate_headshot_adjustment',
    'calculate_match_score',
    'calculate_stats_score',
    'calculate_tier_score',
    'mode_family',
]

logger = get_logger(__name__)

SCORABLE_MATCH_TYPES = (MatchType.NORMAL, MatchType.RANKED)

# ---------- 게임 규칙에서 오는 값 (튜닝 대상 아님) ----------

LOBBY_SIZE = 100  # 명. PUBG 일반 매치 정원. kill_place 백분위의 분모.
MODE_TEAM_COUNT = {'solo': 100, 'duo': 50, 'squad': 25}  # 팀. 정원 100을 팀 인원으로 나눈 값. win_place 백분위의 분모.
HP_PER_ENEMY = 100.0  # HP. 적 1명분 체력. 딜량을 "적 몇 명분"으로 읽는 단위.

# ---------- 의미가 정의된 튜닝 파라미터 (재산출: scripts/calibrate_scoring.py) ----------

DAMAGE_REFERENCE = {'solo': 300.0, 'duo': 350.0, 'squad': 400.0}  # 그 모드 딜량 분포의 75백분위. 이 딜량에서 딜 항이 정확히 0.5.
REFERENCE_MINUTES = 20.0  # 분. "후반부까지 생존한 매치"의 대략적 길이. DPM_REFERENCE의 분모.
W_PLACE = 0.45  # 배치 항 가중(교전 항은 1 - W_PLACE).
COMBAT_WEIGHT_DAMAGE = 0.40  # 교전 항 내 딜 가중. 신뢰도 내림차순(딜 > 제압 > 효율 > 로비 킬순위).
COMBAT_WEIGHT_TAKEDOWNS = 0.25  # 교전 항 내 제압(킬+기절+어시) 가중.
COMBAT_WEIGHT_DPM = 0.20  # 교전 항 내 분당 딜 가중.
COMBAT_WEIGHT_KILL_PCT = 0.15  # 교전 항 내 로비 킬순위 가중. 킬 동률 타이브레이크 규칙이 비공개라 가장 낮다.
KNOCK_SHARE = 0.75  # 마무리 못 한 기절 1건(DBNOs - kills) = 킬 0.75건.
ASSIST_SHARE = 0.25  # 어시스트 1건 = 킬 0.25건(damage_dealt와의 중복 계상 할인).
REVIVE_BONUS = 0.02  # 부활 1회당 가산(=2점).
REVIVE_MAX_COUNT = 2  # 매치당 부활 보너스 상한 횟수.
TEAMKILL_PENALTY = 0.05  # 팀킬 1회당 감점(=5점).
TEAMKILL_MAX_COUNT = 2  # 매치당 팀킬 감점 상한 횟수.
PRIOR_SCORE = 40.0  # 점. 표본이 적을 때 수렴하는 기본값("중수" 표본이 산출하는 값).
PRIOR_WEIGHT = 5.0  # 매치. 사전분포의 유효 표본 수(경험적 베이즈 축소).
TIER_BLEND_MAX = 0.5  # 랭크 전용 유저에서 시즌 티어가 갖는 최대 지분.
HEADSHOT_BASE = 0.20  # 헤드샷 비율 기준선. 이보다 높으면 가점, 낮으면 감점.
HEADSHOT_SWING = 2.0  # 점. 헤드샷 보정의 최대 폭(±).
HEADSHOT_MIN_KILLS = 10  # 킬. 누적 킬이 이 미만이면 헤드샷 보정을 적용하지 않는다(표본 부족).

# ---------- 파생되는 값 (자유 파라미터가 아니다) ----------

TAKEDOWN_REFERENCE = {mode: ref / HP_PER_ENEMY for mode, ref in DAMAGE_REFERENCE.items()}  # "적 몇 명분을 제압"으로 읽는 기준선.
DPM_REFERENCE = {mode: ref / REFERENCE_MINUTES for mode, ref in DAMAGE_REFERENCE.items()}  # 분당 딜 기준선.

_SOLO_MODES = frozenset({GameMode.SOLO, GameMode.SOLO_FPP, GameMode.NORMAL_SOLO, GameMode.NORMAL_SOLO_FPP})
_DUO_MODES = frozenset({GameMode.DUO, GameMode.DUO_FPP, GameMode.NORMAL_DUO, GameMode.NORMAL_DUO_FPP})
_SQUAD_MODES = frozenset({GameMode.SQUAD, GameMode.SQUAD_FPP, GameMode.NORMAL_SQUAD, GameMode.NORMAL_SQUAD_FPP})

_TIER_ORDER = {
    Tier.BRONZE: 1,
    Tier.SILVER: 2,
    Tier.GOLD: 3,
    Tier.PLATINUM: 4,
    Tier.DIAMOND: 5,
    Tier.MASTER: 6,
}
_INVALID_TIERS = frozenset({Tier.UNDEFINED, Tier.UNRANKED})
_ALIVE_DEATH_TYPES = frozenset({'alive'})


def mode_family(game_mode: GameMode) -> str:
    """`GameMode`를 인원 구성 패밀리(`'solo'`/`'duo'`/`'squad'`)로 축약한다.

    conquest/war/zombie/lab/esports 등 규칙이 다른 이벤트 모드와 `UNDEFINED`는
    현재 매치 수집 경로가 스쿼드 전용이므로 스쿼드로 폴백한다.
    """
    if game_mode in _SOLO_MODES:
        return 'solo'
    if game_mode in _DUO_MODES:
        return 'duo'
    if game_mode in _SQUAD_MODES:
        return 'squad'
    logger.debug('점수 계산 대상이 아닌 게임 모드입니다. 스쿼드로 폴백합니다: %s', game_mode)
    return 'squad'


def sat(x: float) -> float:
    """포화 함수. 파라미터 없음. x=0 -> 0, x=1 -> 0.5, x -> ∞ -> 1.

    음수는 0으로 본다. 파손 데이터로 딜량이 음수가 되면 `x = -1`에서 0으로 나누고,
    그보다 더 낮은 값에서는 오히려 점수가 올라간다(딜량 -800이 64점).
    """
    if x <= 0:
        return 0.0
    return x / (1 + x)


def clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def place_term(win_place: int, team_count: int) -> float:
    """등수를 선형·로그 백분위 절반씩 혼합해 `[0, 1]`로 정규화한다."""
    if win_place <= 0:
        return 0.0
    r = min(win_place, team_count)
    lin = (team_count - r) / (team_count - 1)
    log_pct = 1 - math.log(r) / math.log(team_count)
    return clamp01(0.5 * lin + 0.5 * log_pct)


def combat_term(match: PlayerMatchStats, family: str) -> float:
    """살아있는 동안의 제압력을 딜/제압/효율/로비 킬순위 네 축으로 합성한다."""
    takedowns = match.kills + KNOCK_SHARE * max(match.DBNOs - match.kills, 0) + ASSIST_SHARE * match.assists
    minutes = max(match.time_survived, 60) / 60
    dpm = match.damage_dealt / minutes
    kill_pct = clamp01(1 - (match.kill_place - 1) / (LOBBY_SIZE - 1)) if match.kill_place > 0 else 0.0

    return (
        COMBAT_WEIGHT_DAMAGE * sat(match.damage_dealt / DAMAGE_REFERENCE[family])
        + COMBAT_WEIGHT_TAKEDOWNS * sat(takedowns / TAKEDOWN_REFERENCE[family])
        + COMBAT_WEIGHT_DPM * sat(dpm / DPM_REFERENCE[family])
        + COMBAT_WEIGHT_KILL_PCT * kill_pct
    )


def calculate_match_score(match: PlayerMatchStats) -> float:
    """매치 1건의 점수를 `[0, 100]`으로 계산한다. 랭크/일반 매치를 동일한 공식으로 채점한다."""
    family = mode_family(match.game_mode)
    team_count = MODE_TEAM_COUNT[family]

    raw = W_PLACE * place_term(match.win_place, team_count) + (1 - W_PLACE) * combat_term(match, family)
    raw += REVIVE_BONUS * min(match.revives, REVIVE_MAX_COUNT)
    raw -= TEAMKILL_PENALTY * min(match.team_kills, TEAMKILL_MAX_COUNT)
    return 100.0 * clamp01(raw)


def calculate_tier_score(tier: Tier, sub_tier: int) -> float:
    """시즌 티어를 `[0, 100]` 점수로 사상한다. Bronze5 -> ~3.3, Master -> 100.0.

    PUBG는 subTier 1이 최상위, 5가 최하위다. subTier가 없거나(Master 등) 범위를 벗어나면 최상위로 본다.
    """
    order = _TIER_ORDER.get(tier)
    if order is None:
        return 0.0
    sub = (6 - sub_tier) / 5 if 1 <= sub_tier <= 5 else 1.0
    return 100 * (order - 1 + sub) / 6


def calculate_headshot_adjustment(kills: int, headshot_kills: int) -> float:
    """헤드샷 비율이 기준선(`HEADSHOT_BASE`) 대비 갖는 편차를 `±HEADSHOT_SWING`점으로 환산한다.

    누적 킬이 `HEADSHOT_MIN_KILLS` 미만이면 표본이 부족하므로 보정하지 않는다(0.0).
    """
    if kills < HEADSHOT_MIN_KILLS:
        return 0.0
    hs_ratio = headshot_kills / kills
    adjust = HEADSHOT_SWING * (hs_ratio - HEADSHOT_BASE) / HEADSHOT_BASE
    return max(-HEADSHOT_SWING, min(HEADSHOT_SWING, adjust))


def calculate_stats_score(matches: Sequence[PlayerMatchStats]) -> float:
    """매치 목록의 점수를 경험적 베이즈로 축소 보정해 반환한다. 점수화할 수 없는 매치는 제외한다."""
    scores: list[float] = []
    for match in matches:
        if match.match_type not in SCORABLE_MATCH_TYPES:
            logger.debug('점수 계산에서 제외된 매치 타입입니다: %s', match.match_type)
            continue
        scores.append(calculate_match_score(match))

    if not scores:
        return 0.0
    return (sum(scores) + PRIOR_WEIGHT * PRIOR_SCORE) / (len(scores) + PRIOR_WEIGHT)


def _is_dead(match: PlayerMatchStats) -> bool:
    if match.death_type:
        return match.death_type not in _ALIVE_DEATH_TYPES
    return match.win_place != 1  # death_type이 비어 있는 구 데이터에 대한 폴백 근사


def _top_percentile_threshold(family: str) -> int:
    """모드별 '상위 10%' 등수 임계값(반올림, 최소 1등)."""
    return max(1, math.floor(MODE_TEAM_COUNT[family] * 0.1 + 0.5))


def _tier_score_or_none(ranked: Stats | None) -> float | None:
    if ranked is None or ranked.tier in _INVALID_TIERS:
        return None
    return calculate_tier_score(ranked.tier, ranked.sub_tier)


def aggregate_stats(matches: Sequence[PlayerMatchStats], *, ranked: Stats | None = None) -> Stats:
    """최근 매치 목록을 집계해 `Stats`를 만든다.

    계산 순서(고정): 매치별 점수 -> 산술 평균 -> 표본 축소 -> 헤드샷 보정 -> 티어 혼합 -> clamp(0, 100).
    `ranked`는 시즌 티어 통계다. 랭크 매치 비중만큼 티어 점수를 섞는다(§7.2). 조회 실패/무효 티어는 무시한다.
    """
    rounds_played = len(matches)
    if rounds_played == 0:
        return Stats()

    kills = sum(match.kills for match in matches)
    assists = sum(match.assists for match in matches)
    headshot_kills = sum(match.headshot_kills for match in matches)
    deaths = sum(1 for match in matches if _is_dead(match))
    # `win_place`가 0인 파손 데이터를 1등으로 세면 안 된다.
    top10_count = sum(1 for match in matches if 1 <= match.win_place <= _top_percentile_threshold(mode_family(match.game_mode)))

    score = calculate_stats_score(matches)
    score += calculate_headshot_adjustment(kills, headshot_kills)

    tier_score = _tier_score_or_none(ranked)
    scorable_count = sum(1 for match in matches if match.match_type in SCORABLE_MATCH_TYPES)
    if tier_score is not None and scorable_count:
        ranked_count = sum(1 for match in matches if match.match_type == MatchType.RANKED)
        ranked_ratio = ranked_count / scorable_count
        lam = TIER_BLEND_MAX * ranked_ratio
        score = (1 - lam) * score + lam * tier_score

    score = clamp01(score / 100.0) * 100.0

    return Stats(
        tier=ranked.tier if ranked is not None else Tier.UNDEFINED,
        sub_tier=ranked.sub_tier if ranked is not None else 0,
        rank_point=ranked.rank_point if ranked is not None else 0,
        rounds_played=rounds_played,
        avg_rank=sum(match.win_place for match in matches) / rounds_played,
        top10_ratio=top10_count / rounds_played,
        win_ratio=sum(1 for match in matches if match.win_place == 1) / rounds_played,
        damage_dealt=sum(match.damage_dealt for match in matches),
        kills=kills,
        assists=assists,
        deaths=deaths,
        kda=(kills + assists) / deaths if deaths else float(kills + assists),
        score=score,
    )
