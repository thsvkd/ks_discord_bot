"""점수 계산 로직 테스트. 설계 근거: docs/scoring-design.md §12(테스트 전략)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from factories import make_match_stats, make_match_stats_profile
from ks_bot.common.enums import GameMode, MatchType, Tier
from ks_bot.common.models import Stats
from ks_bot.core.scoring import (
    DAMAGE_REFERENCE,
    HEADSHOT_BASE,
    HEADSHOT_SWING,
    MODE_TEAM_COUNT,
    PRIOR_SCORE,
    PRIOR_WEIGHT,
    aggregate_stats,
    calculate_headshot_adjustment,
    calculate_match_score,
    calculate_stats_score,
    calculate_tier_score,
    combat_term,
    mode_family,
    place_term,
    sat,
)


class TestModeFamily:
    @pytest.mark.parametrize(
        'game_mode, expected',
        [
            (GameMode.SOLO, 'solo'),
            (GameMode.SOLO_FPP, 'solo'),
            (GameMode.NORMAL_SOLO, 'solo'),
            (GameMode.NORMAL_SOLO_FPP, 'solo'),
            (GameMode.DUO, 'duo'),
            (GameMode.DUO_FPP, 'duo'),
            (GameMode.NORMAL_DUO, 'duo'),
            (GameMode.NORMAL_DUO_FPP, 'duo'),
            (GameMode.SQUAD, 'squad'),
            (GameMode.SQUAD_FPP, 'squad'),
            (GameMode.NORMAL_SQUAD, 'squad'),
            (GameMode.NORMAL_SQUAD_FPP, 'squad'),
        ],
    )
    def test_known_modes_map_to_family(self, game_mode: GameMode, expected: str):
        assert mode_family(game_mode) == expected

    def test_undefined_falls_back_to_squad(self):
        # B7
        assert mode_family(GameMode.UNDEFINED) == 'squad'

    def test_event_mode_falls_back_to_squad(self):
        # M5
        assert mode_family(GameMode.WAR_SQUAD) == 'squad'


class TestMatchScoreProperties:
    """§12.1 성질 기반 테스트(T1~T8)."""

    def test_place_is_strictly_monotonic(self):
        # T1
        scores = [calculate_match_score(make_match_stats(win_place=r)) for r in range(1, 26)]
        assert all(a > b for a, b in pairwise(scores))

    def test_damage_is_strictly_monotonic(self):
        # T2
        scores = [calculate_match_score(make_match_stats(damage_dealt=float(d))) for d in range(0, 2001, 100)]
        assert all(a < b for a, b in pairwise(scores))

    def test_kills_is_strictly_monotonic(self):
        # T3 — DBNOs를 kills 이상으로 유지해 킬만의 효과를 측정한다.
        scores = [calculate_match_score(make_match_stats(kills=k, DBNOs=k)) for k in range(0, 11)]
        assert all(a < b for a, b in pairwise(scores))

    def test_team_kills_penalty_strictly_decreases_then_caps(self):
        # T4
        s0, s1, s2, s3 = (calculate_match_score(make_match_stats(team_kills=n)) for n in (0, 1, 2, 3))
        assert s0 > s1 > s2
        assert s2 == pytest.approx(s3)

    def test_revive_bonus_strictly_increases_then_caps(self):
        # T5
        s0, s1, s2, s3 = (calculate_match_score(make_match_stats(revives=n)) for n in (0, 1, 2, 3))
        assert s0 < s1 < s2
        assert s2 == pytest.approx(s3)

    def test_upper_bound(self):
        # T6
        extreme = make_match_stats(
            win_place=1,
            damage_dealt=5000.0,
            kills=30,
            DBNOs=30,
            assists=5,
            time_survived=1800,
            kill_place=1,
            revives=2,
            team_kills=0,
        )
        assert calculate_match_score(extreme) <= 100.0

    def test_lower_bound(self):
        # T7
        worst = make_match_stats(
            win_place=25,
            damage_dealt=0.0,
            kills=0,
            DBNOs=0,
            assists=0,
            time_survived=0,
            kill_place=0,
            revives=0,
            team_kills=2,
        )
        assert calculate_match_score(worst) == pytest.approx(0.0)

    def test_efficiency_rewards_shorter_survival_for_same_damage(self):
        # T8 — 같은 딜을 더 빨리 냈으면 더 높은 점수를 받는다.
        short = make_match_stats(win_place=5, damage_dealt=300.0, kills=2, DBNOs=2, assists=1, kill_place=20, time_survived=600)
        long_ = make_match_stats(win_place=5, damage_dealt=300.0, kills=2, DBNOs=2, assists=1, kill_place=20, time_survived=1800)
        assert calculate_match_score(short) > calculate_match_score(long_)


class TestMatchScoreBoundaries:
    """§12.2 경계값 테스트(B1~B7). B8/B9는 집계·평균 관련이라 다른 클래스에 둔다."""

    def test_zero_win_place_does_not_raise(self):
        # B1
        match = make_match_stats(win_place=0, damage_dealt=0.0, kills=0, DBNOs=0, assists=0, kill_place=0, revives=0, team_kills=0, time_survived=0)
        assert calculate_match_score(match) == pytest.approx(0.0)

    def test_win_place_beyond_team_count_clamps(self):
        # B2 — 스쿼드(T=25) 30등은 25등과 동일하게 취급된다.
        at_last = calculate_match_score(make_match_stats(win_place=25))
        beyond = calculate_match_score(make_match_stats(win_place=30))
        assert beyond == pytest.approx(at_last)

    def test_zero_time_survived_does_not_raise(self):
        # B3
        match = make_match_stats(time_survived=0)
        assert calculate_match_score(match) >= 0.0

    def test_zero_kill_place_gives_zero_component(self):
        # B4
        match = make_match_stats(damage_dealt=0.0, kills=0, DBNOs=0, assists=0, time_survived=1200, kill_place=0)
        assert combat_term(match, 'squad') == pytest.approx(0.0)

    def test_kill_place_best_and_worst(self):
        # B5 — kill_place=1 -> 1.0, kill_place=100 -> 0.0 (교전 항의 로비 킬순위 성분만 남긴다)
        best = make_match_stats(damage_dealt=0.0, kills=0, DBNOs=0, assists=0, time_survived=1200, kill_place=1)
        worst = make_match_stats(damage_dealt=0.0, kills=0, DBNOs=0, assists=0, time_survived=1200, kill_place=100)
        assert combat_term(best, 'squad') == pytest.approx(0.15 * 1.0)
        assert combat_term(worst, 'squad') == pytest.approx(0.15 * 0.0)

    def test_dbnos_below_kills_does_not_go_negative(self):
        # B6 — DBNOs < kills면 초과분이 없어 DBNOs == kills인 경우와 결과가 같다.
        below = make_match_stats(kills=5, DBNOs=2)
        equal = make_match_stats(kills=5, DBNOs=5)
        assert calculate_match_score(below) == pytest.approx(calculate_match_score(equal))

    def test_undefined_game_mode_does_not_raise(self):
        # B7
        match = make_match_stats(game_mode=GameMode.UNDEFINED)
        assert calculate_match_score(match) >= 0.0

    @pytest.mark.parametrize('damage', [-1.0, -400.0, -800.0, -10_000.0])
    def test_negative_damage_is_treated_as_zero(self, damage: float):
        """파손 데이터로 딜량이 음수면 `sat()`이 -400에서 터지고 -800에서는 64점을 준다."""
        match = make_match_stats(damage_dealt=damage, kills=0, DBNOs=0, assists=0, kill_place=0, revives=0, team_kills=0, win_place=0)
        assert calculate_match_score(match) == pytest.approx(0.0)


class TestModeNormalization:
    """§12.3 모드 정규화 테스트(M1~M5)."""

    def test_same_rank_different_mode_place_term(self):
        # M1 — 솔로 4등 > 듀오 4등 > 스쿼드 4등
        solo = place_term(4, MODE_TEAM_COUNT['solo'])
        duo = place_term(4, MODE_TEAM_COUNT['duo'])
        squad = place_term(4, MODE_TEAM_COUNT['squad'])
        assert solo > duo > squad
        assert solo == pytest.approx(0.834, abs=0.01)
        assert duo == pytest.approx(0.792, abs=0.01)
        assert squad == pytest.approx(0.722, abs=0.01)

    def test_equal_percentile_across_modes_within_tolerance(self):
        # M2 — 완전 등가는 아니지만(§5.3 한계), 편차가 0.1 미만이어야 한다.
        solo = place_term(20, MODE_TEAM_COUNT['solo'])
        duo = place_term(10, MODE_TEAM_COUNT['duo'])
        squad = place_term(5, MODE_TEAM_COUNT['squad'])
        assert max(solo, duo, squad) - min(solo, duo, squad) < 0.1

    def test_same_damage_different_mode_damage_term(self):
        # M3 — 딜 300의 딜 항: 솔로 > 듀오 > 스쿼드
        solo = sat(300 / DAMAGE_REFERENCE['solo'])
        duo = sat(300 / DAMAGE_REFERENCE['duo'])
        squad = sat(300 / DAMAGE_REFERENCE['squad'])
        assert solo > duo > squad
        assert solo == pytest.approx(0.500, abs=0.01)
        assert duo == pytest.approx(0.462, abs=0.01)
        assert squad == pytest.approx(0.429, abs=0.01)

    def test_solo_takedowns_reduce_to_kills(self):
        # M4 — 솔로는 DBNOs/assists가 구조적으로 0이라 takedowns == kills로 축약된다.
        no_dbnos = make_match_stats(game_mode=GameMode.SOLO, kills=4, DBNOs=0, assists=0, damage_dealt=0.0, time_survived=1200, kill_place=0)
        dbnos_eq_kills = make_match_stats(game_mode=GameMode.SOLO, kills=4, DBNOs=4, assists=0, damage_dealt=0.0, time_survived=1200, kill_place=0)
        assert combat_term(no_dbnos, 'solo') == pytest.approx(combat_term(dbnos_eq_kills, 'solo'))

    def test_event_mode_falls_back_without_raising(self):
        # M5
        match = make_match_stats(game_mode=GameMode.WAR_SQUAD)
        assert calculate_match_score(match) >= 0.0


class TestRankedScoring:
    """§12.4 랭크/티어 테스트(R1~R8)."""

    def test_ranked_matches_are_not_fixed_score(self):
        # R1 — 회귀 방지. 성적이 다른 두 랭크 매치의 점수는 달라야 한다.
        good = calculate_match_score(make_match_stats(match_type=MatchType.RANKED, win_place=1, damage_dealt=500.0, kills=5, DBNOs=5))
        bad = calculate_match_score(
            make_match_stats(match_type=MatchType.RANKED, win_place=25, damage_dealt=0.0, kills=0, DBNOs=0, assists=0, kill_place=0)
        )
        assert good > bad

    def test_same_stats_ranked_and_normal_score_equal(self):
        # R2 — 배율 없음.
        normal = calculate_match_score(make_match_stats(match_type=MatchType.NORMAL))
        ranked = calculate_match_score(make_match_stats(match_type=MatchType.RANKED))
        assert normal == pytest.approx(ranked)

    def test_zero_ranked_ratio_ignores_tier(self):
        # R3 — 매치가 전부 일반 매치면 티어를 넘겨도 결과가 같다(λ=0).
        matches = make_match_stats_profile('average', count=10)
        with_tier = aggregate_stats(matches, ranked=Stats(tier=Tier.GOLD, sub_tier=1))
        without_tier = aggregate_stats(matches)
        assert with_tier.score == pytest.approx(without_tier.score)

    def test_full_ranked_ratio_blends_half_tier(self):
        # R4 — 전부 랭크 매치면 final == 0.5*shrunk + 0.5*tier_score.
        matches = [make_match_stats(match_type=MatchType.RANKED, win_place=w, kills=1, DBNOs=1, headshot_kills=0) for w in (2, 5, 8, 11, 14)]
        ranked = Stats(tier=Tier.GOLD, sub_tier=2)
        stats = aggregate_stats(matches, ranked=ranked)

        tier_score = calculate_tier_score(Tier.GOLD, 2)
        expected = 0.5 * calculate_stats_score(matches) + 0.5 * tier_score
        assert stats.score == pytest.approx(expected)

    def test_ranked_none_defaults_lambda_zero(self):
        # R5 — 랭크 매치가 있어도 ranked=None이면 예외 없이 λ=0.
        matches = [make_match_stats(match_type=MatchType.RANKED, win_place=w, kills=1) for w in (2, 5, 8, 11, 14)]
        stats = aggregate_stats(matches, ranked=None)
        assert stats.score == pytest.approx(calculate_stats_score(matches))

    @pytest.mark.parametrize('tier', [Tier.UNRANKED, Tier.UNDEFINED])
    def test_invalid_tier_defaults_lambda_zero(self, tier: Tier):
        # R6
        matches = [make_match_stats(match_type=MatchType.RANKED, win_place=w, kills=1) for w in (2, 5, 8, 11, 14)]
        stats = aggregate_stats(matches, ranked=Stats(tier=tier))
        assert stats.score == pytest.approx(calculate_stats_score(matches))

    @pytest.mark.parametrize(
        'tier, sub_tier, expected',
        [
            (Tier.BRONZE, 5, 3.3),
            (Tier.GOLD, 3, 43.3),
            (Tier.DIAMOND, 1, 83.3),
            (Tier.MASTER, 0, 100.0),
        ],
    )
    def test_tier_score_reference_values(self, tier: Tier, sub_tier: int, expected: float):
        # R7
        assert calculate_tier_score(tier, sub_tier) == pytest.approx(expected, abs=0.1)

    def test_tier_score_is_strictly_monotonic(self):
        # R8 — 전 티어x서브티어 30조합이 순서대로 강한 단조 증가해야 한다.
        order = [Tier.BRONZE, Tier.SILVER, Tier.GOLD, Tier.PLATINUM, Tier.DIAMOND, Tier.MASTER]
        combos = [(tier, sub) for tier in order for sub in (5, 4, 3, 2, 1)]
        scores = [calculate_tier_score(tier, sub) for tier, sub in combos]
        assert all(a < b for a, b in pairwise(scores))


class TestSampleShrinkage:
    """§12.5 표본 수 보정 테스트(S1~S4)."""

    def test_shrinkage_formula_exact(self):
        # S3
        persona = make_match_stats_profile('skilled', count=1)[0]
        raw = calculate_match_score(persona)
        n = 20
        expected = (n * raw + PRIOR_WEIGHT * PRIOR_SCORE) / (n + PRIOR_WEIGHT)
        assert calculate_stats_score([persona] * n) == pytest.approx(expected)

    @pytest.mark.parametrize('profile', ['rookie', 'pro'])
    def test_larger_sample_converges_to_raw_mean(self, profile: str):
        # S1(고득점), S2(저득점) — 방향에 상관없이 표본이 커질수록 원점수에 접근한다.
        persona = make_match_stats_profile(profile, count=1)[0]
        raw = calculate_match_score(persona)
        distances = [abs(calculate_stats_score([persona] * n) - raw) for n in (1, 5, 20, 40)]
        assert all(a > b for a, b in pairwise(distances))

    def test_extreme_sample_size_nearly_matches_raw(self):
        # S4
        persona = make_match_stats_profile('skilled', count=1)[0]
        raw = calculate_match_score(persona)
        assert abs(calculate_stats_score([persona] * 100_000) - raw) < 1.0


class TestHeadshotAdjustment:
    """§12.6 A6/A7 헤드샷 보정 테스트."""

    def test_below_min_kills_gives_zero(self):
        # A6
        assert calculate_headshot_adjustment(kills=9, headshot_kills=9) == 0.0

    def test_at_min_kills_applies_positive_adjustment(self):
        # A6
        assert calculate_headshot_adjustment(kills=10, headshot_kills=4) > 0.0  # 비율 0.4 > 기준선 0.2

    def test_adjustment_is_capped_at_swing(self):
        # A7
        assert calculate_headshot_adjustment(kills=10, headshot_kills=10) == pytest.approx(HEADSHOT_SWING)


class TestStatsScore:
    def test_stats_score_applies_shrinkage(self):
        matches = [make_match_stats(win_place=1), make_match_stats(win_place=10)]
        raw_mean = sum(calculate_match_score(match) for match in matches) / 2
        expected = (2 * raw_mean + PRIOR_WEIGHT * PRIOR_SCORE) / (2 + PRIOR_WEIGHT)
        assert calculate_stats_score(matches) == pytest.approx(expected)

    def test_empty_list_returns_zero(self):
        # B8
        assert calculate_stats_score([]) == 0.0

    def test_unscorable_match_types_are_ignored(self):
        matches = [make_match_stats(win_place=1), make_match_stats(match_type=MatchType.TRAINING)]
        raw = calculate_match_score(matches[0])
        expected = (raw + PRIOR_WEIGHT * PRIOR_SCORE) / (1 + PRIOR_WEIGHT)
        assert calculate_stats_score(matches) == pytest.approx(expected)

    def test_only_unscorable_matches_returns_zero(self):
        # B9
        assert calculate_stats_score([make_match_stats(match_type=MatchType.CUSTOM)]) == 0.0


class TestAggregateStats:
    """§12.6 집계 테스트(A1~A5) + 기존 회귀 테스트."""

    def test_death_type_based_death_counted_even_on_win(self):
        # A1 — 팀은 치킨을 먹었지만 본인은 사망한 경우.
        stats = aggregate_stats([make_match_stats(death_type='byplayer', win_place=1)])
        assert stats.deaths == 1

    def test_alive_death_type_not_counted_even_off_win(self):
        # A2
        stats = aggregate_stats([make_match_stats(death_type='alive', win_place=3)])
        assert stats.deaths == 0

    def test_empty_death_type_falls_back_to_win_place_approx(self):
        # A3
        alive = aggregate_stats([make_match_stats(death_type='', win_place=1)])
        dead = aggregate_stats([make_match_stats(death_type='', win_place=2)])
        assert alive.deaths == 0
        assert dead.deaths == 1

    def test_kills_and_assists_are_not_swapped(self):
        # A4 — 예전 구현은 assists/deaths를 서로 바꿔 저장했다.
        stats = aggregate_stats([make_match_stats(win_place=3, kills=4, assists=1, death_type='byplayer')])
        assert stats.kills == 4
        assert stats.assists == 1
        assert stats.deaths == 1

    def test_top10_ratio_redefined_for_squad(self):
        # A5 — 스쿼드 상위 10% 임계는 3등이다(25팀의 10% = 2.5, 반올림 3).
        stats = aggregate_stats(
            [
                make_match_stats(win_place=3, game_mode=GameMode.SQUAD, match_id='a'),
                make_match_stats(win_place=8, game_mode=GameMode.SQUAD, match_id='b'),
            ]
        )
        assert stats.top10_ratio == pytest.approx(0.5)

    def test_zero_win_place_is_not_counted_as_top10(self):
        """`win_place=0`은 등수를 못 받은 파손 데이터다. 1등보다 앞선 것으로 세면 안 된다."""
        stats = aggregate_stats(
            [
                make_match_stats(win_place=0, game_mode=GameMode.SQUAD, match_id='a'),
                make_match_stats(win_place=3, game_mode=GameMode.SQUAD, match_id='b'),
            ]
        )
        assert stats.top10_ratio == pytest.approx(0.5)

    def test_aggregation(self):
        matches = [
            make_match_stats(win_place=1, kills=5, assists=1, damage_dealt=500.0, death_type='alive'),
            make_match_stats(win_place=8, kills=2, assists=1, damage_dealt=200.0),
            make_match_stats(win_place=30, kills=0, assists=0, damage_dealt=50.0),
        ]
        stats = aggregate_stats(matches)

        assert stats.rounds_played == 3
        assert stats.kills == 7
        assert stats.assists == 2
        assert stats.deaths == 2  # win_place=1인 매치만 death_type='alive'
        assert stats.avg_rank == pytest.approx(13.0)
        assert stats.top10_ratio == pytest.approx(1 / 3)  # 스쿼드 상위 10% 임계=3등, win_place=1만 해당
        assert stats.win_ratio == pytest.approx(1 / 3)
        assert stats.damage_dealt == pytest.approx(750.0)
        assert stats.kda == pytest.approx(9 / 2)

    def test_empty_returns_default_stats(self):
        # B8
        assert aggregate_stats([]).rounds_played == 0


PERSONAS = ('rookie', 'average', 'skilled', 'pro')


@pytest.fixture(scope='module')
def persona_scores() -> dict[str, float]:
    return {profile: calculate_stats_score(make_match_stats_profile(profile, count=10)) for profile in PERSONAS}


@pytest.fixture(scope='module')
def persona_aggregate_scores() -> dict[str, float]:
    """실제 `/점수`가 쓰는 경로. 헤드샷 보정까지 거친 값이다."""
    return {profile: aggregate_stats(make_match_stats_profile(profile, count=10)).score for profile in PERSONAS}


class TestPersonaVerification:
    """§13 검증 시나리오. 스쿼드 10판, 페르소나별 고수 > 중수 > 초보 순서를 고정한다."""

    def test_strict_ordering(self, persona_scores: dict[str, float]):
        assert persona_scores['rookie'] < persona_scores['average'] < persona_scores['skilled'] < persona_scores['pro']

    def test_gaps(self, persona_scores: dict[str, float]):
        assert persona_scores['average'] - persona_scores['rookie'] >= 12.0
        assert persona_scores['skilled'] - persona_scores['average'] >= 12.0
        assert persona_scores['pro'] - persona_scores['skilled'] >= 5.0

    def test_bands(self, persona_scores: dict[str, float]):
        assert 21.6 <= persona_scores['rookie'] <= 27.6
        assert 38.0 <= persona_scores['average'] <= 44.0
        assert 53.5 <= persona_scores['skilled'] <= 59.5
        assert 61.4 <= persona_scores['pro'] <= 67.4

    def test_bounded(self, persona_scores: dict[str, float]):
        assert all(0.0 <= value <= 100.0 for value in persona_scores.values())


class TestPersonaAggregateVerification:
    """§13.3 A9 — 같은 어서션을 실제 사용자 경로(`aggregate_stats().score`)에도 건다.

    `calculate_stats_score()`만 검증하면 집계 단계에서만 적용되는 헤드샷 보정·티어 결합이
    문서 수치와 임베드 출력을 조용히 갈라놓는다.
    """

    def test_strict_ordering(self, persona_aggregate_scores: dict[str, float]):
        scores = persona_aggregate_scores
        assert scores['rookie'] < scores['average'] < scores['skilled'] < scores['pro']

    def test_gaps(self, persona_aggregate_scores: dict[str, float]):
        assert persona_aggregate_scores['average'] - persona_aggregate_scores['rookie'] >= 12.0
        assert persona_aggregate_scores['skilled'] - persona_aggregate_scores['average'] >= 12.0
        assert persona_aggregate_scores['pro'] - persona_aggregate_scores['skilled'] >= 5.0

    def test_bands(self, persona_aggregate_scores: dict[str, float]):
        assert 21.6 <= persona_aggregate_scores['rookie'] <= 27.6
        assert 38.0 <= persona_aggregate_scores['average'] <= 44.0
        assert 53.5 <= persona_aggregate_scores['skilled'] <= 59.5
        assert 61.4 <= persona_aggregate_scores['pro'] <= 67.4

    def test_bounded(self, persona_aggregate_scores: dict[str, float]):
        assert all(0.0 <= value <= 100.0 for value in persona_aggregate_scores.values())

    def test_matches_the_pre_adjustment_score(self, persona_scores: dict[str, float], persona_aggregate_scores: dict[str, float]):
        """티어를 주지 않았고 페르소나 헤드샷 비율이 기준선과 같으므로 두 경로가 일치해야 한다."""
        for profile in PERSONAS:
            assert persona_aggregate_scores[profile] == pytest.approx(persona_scores[profile])

    @pytest.mark.parametrize('profile', PERSONAS)
    def test_matches_documented_values(self, profile: str, persona_aggregate_scores: dict[str, float]):
        # §13.2 표의 값이 집계 경로에서도 그대로 나와야 한다(헤드샷 비율이 기준선과 같아 보정이 0).
        documented = {'rookie': 24.6, 'average': 41.0, 'skilled': 56.5, 'pro': 64.4}
        assert persona_aggregate_scores[profile] == pytest.approx(documented[profile], abs=0.1)

    @pytest.mark.parametrize('profile', PERSONAS)
    def test_persona_headshot_ratio_is_baseline(self, profile: str):
        # 페르소나 표본의 누적 헤드샷 비율이 기준선과 같아야 위 등식이 성립한다.
        matches = make_match_stats_profile(profile, count=10)
        kills = sum(match.kills for match in matches)
        headshots = sum(match.headshot_kills for match in matches)
        if kills == 0:
            assert headshots == 0
        else:
            assert headshots / kills == pytest.approx(HEADSHOT_BASE)


class TestHeadshotAdjustmentInAggregate:
    """§12.6 A8 — 헤드샷 보정이 집계 경로에 실제로 반영되는지 확인한다."""

    def test_zero_headshot_ratio_costs_full_swing(self):
        baseline = aggregate_stats(make_match_stats_profile('skilled', count=10)).score
        no_headshot = aggregate_stats(make_match_stats_profile('skilled', count=10, headshot_kills=0)).score
        assert no_headshot == pytest.approx(baseline - HEADSHOT_SWING)

    def test_full_headshot_ratio_gains_full_swing(self):
        baseline = aggregate_stats(make_match_stats_profile('skilled', count=10)).score
        all_headshot = aggregate_stats(make_match_stats_profile('skilled', count=10, headshot_kills=4)).score  # kills=4 → 비율 1.0
        assert all_headshot == pytest.approx(baseline + HEADSHOT_SWING)

    def test_below_min_kills_leaves_score_untouched(self):
        # 총 킬이 HEADSHOT_MIN_KILLS 미만이면 보정이 없어 축소 보정 결과와 정확히 같다.
        matches = make_match_stats_profile('skilled', count=2, kills=1, DBNOs=1, headshot_kills=0)
        assert aggregate_stats(matches).score == pytest.approx(calculate_stats_score(matches))


class TestRankedPersonaScenario:
    """§13.4 — 중수 성적으로 랭크만 10판, 시즌 티어 Diamond/5."""

    def test_documented_final_score(self):
        matches = make_match_stats_profile('average', count=10, match_type=MatchType.RANKED)
        stats = aggregate_stats(matches, ranked=Stats(tier=Tier.DIAMOND, sub_tier=5))
        assert calculate_tier_score(Tier.DIAMOND, 5) == pytest.approx(70.0)
        assert stats.score == pytest.approx(55.5, abs=0.1)

    def test_beats_the_old_fixed_ranked_score(self):
        # 회귀 방지 — 예전 로직은 랭크 매치를 1.2점 고정으로 채점했다.
        matches = make_match_stats_profile('average', count=10, match_type=MatchType.RANKED)
        stats = aggregate_stats(matches, ranked=Stats(tier=Tier.DIAMOND, sub_tier=5))
        assert stats.score > 1.2
