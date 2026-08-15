"""점수 계산 로직 테스트."""

from __future__ import annotations

import pytest

from factories import make_match_stats
from ks_bot.common.enums import MatchType
from ks_bot.core.scoring import RANKED_MATCH_SCORE, SCORE_WEIGHTS, aggregate_stats, calculate_match_score, calculate_stats_score


class TestMatchScore:
    def test_normal_match_uses_weighted_formula(self):
        match = make_match_stats(win_place=2, damage_dealt=300.0, assists=1)
        expected = SCORE_WEIGHTS['BASE'] + SCORE_WEIGHTS['RANK'] / 2 + SCORE_WEIGHTS['DAMAGE'] * 3.0 + SCORE_WEIGHTS['ASSIST'] * 1
        assert calculate_match_score(match) == pytest.approx(expected)

    def test_ranked_match_uses_fixed_score(self):
        match = make_match_stats(match_type=MatchType.RANKED)
        assert calculate_match_score(match) == RANKED_MATCH_SCORE

    def test_zero_win_place_does_not_raise(self):
        # 데이터가 깨져 win_place가 0이어도 ZeroDivisionError가 나면 안 된다.
        match = make_match_stats(win_place=0, damage_dealt=0.0, assists=0)
        assert calculate_match_score(match) == pytest.approx(SCORE_WEIGHTS['BASE'])

    def test_better_rank_scores_higher(self):
        winner = make_match_stats(win_place=1)
        loser = make_match_stats(win_place=50)
        assert calculate_match_score(winner) > calculate_match_score(loser)


class TestStatsScore:
    def test_average_of_matches(self):
        matches = [make_match_stats(win_place=1), make_match_stats(win_place=10)]
        expected = sum(calculate_match_score(match) for match in matches) / 2
        assert calculate_stats_score(matches) == pytest.approx(expected)

    def test_empty_list_returns_zero(self):
        assert calculate_stats_score([]) == 0.0

    def test_unscorable_match_types_are_ignored(self):
        matches = [make_match_stats(win_place=1), make_match_stats(match_type=MatchType.TRAINING)]
        assert calculate_stats_score(matches) == pytest.approx(calculate_match_score(matches[0]))

    def test_only_unscorable_matches_returns_zero(self):
        assert calculate_stats_score([make_match_stats(match_type=MatchType.CUSTOM)]) == 0.0


class TestAggregateStats:
    def test_aggregation(self):
        matches = [
            make_match_stats(win_place=1, kills=5, assists=1, damage_dealt=500.0),
            make_match_stats(win_place=8, kills=2, assists=1, damage_dealt=200.0),
            make_match_stats(win_place=30, kills=0, assists=0, damage_dealt=50.0),
        ]
        stats = aggregate_stats(matches)

        assert stats.rounds_played == 3
        assert stats.kills == 7
        assert stats.assists == 2
        assert stats.deaths == 2  # 1등이 아닌 매치 수
        assert stats.avg_rank == pytest.approx(13.0)
        assert stats.top10_ratio == pytest.approx(2 / 3)
        assert stats.win_ratio == pytest.approx(1 / 3)
        assert stats.damage_dealt == pytest.approx(750.0)
        assert stats.kda == pytest.approx(9 / 2)

    def test_kills_and_assists_are_not_swapped(self):
        """예전 구현은 assists/deaths를 서로 바꿔 저장했다."""
        stats = aggregate_stats([make_match_stats(win_place=3, kills=4, assists=1)])
        assert stats.kills == 4
        assert stats.assists == 1
        assert stats.deaths == 1

    def test_all_wins_has_no_deaths(self):
        stats = aggregate_stats([make_match_stats(win_place=1, kills=3, assists=0)])
        assert stats.deaths == 0
        assert stats.kda == pytest.approx(3.0)

    def test_empty_returns_default_stats(self):
        assert aggregate_stats([]).rounds_played == 0
