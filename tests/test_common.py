"""공통 계층(열거형, 시간 유틸, 모델, 예외) 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factories import make_match_payload, make_player_payload
from ks_bot.common.enums import SQUAD_GAME_MODES, GameMode, MatchType, Tier
from ks_bot.common.errors import KSBotError, NotEnoughMatchesError, PlayerMatchStatsNotFoundError, PlayerNotFoundError
from ks_bot.common.models import Match, Player, Stats, normalize_player_id
from ks_bot.common.timeutil import Timezone, datetime_now, parse_utc_to_datetime, to_iso, unix_time_start


class TestEnums:
    @pytest.mark.parametrize(
        'value, expected',
        [
            ('squad', GameMode.SQUAD),
            ('squad-fpp', GameMode.SQUAD_FPP),
            ('', GameMode.UNDEFINED),
            ('알수없는모드', GameMode.UNDEFINED),
        ],
    )
    def test_game_mode_from_string(self, value: str, expected: GameMode):
        assert GameMode.from_string(value) is expected

    def test_unknown_value_does_not_raise(self):
        # PUBG가 새 매치 타입을 추가해도 봇이 죽지 않아야 한다.
        assert MatchType('brand-new-type') is MatchType.UNDEFINED
        assert Tier('brand-new-tier') is Tier.UNDEFINED

    @pytest.mark.parametrize(
        'mode, expected',
        [
            (GameMode.SQUAD, True),
            (GameMode.SQUAD_FPP, True),
            (GameMode.NORMAL_SQUAD, True),
            (GameMode.SOLO, False),
            (GameMode.DUO_FPP, False),
            # 이벤트성 모드의 스쿼드는 일반 스쿼드로 보지 않는다.
            (GameMode.ZOMBIE_SQUAD, False),
            (GameMode.WAR_SQUAD, False),
        ],
    )
    def test_is_squad(self, mode: GameMode, expected: bool):
        assert mode.is_squad is expected

    def test_squad_game_modes_membership(self):
        assert GameMode.SQUAD in SQUAD_GAME_MODES
        assert GameMode.SQUAD_FPP in SQUAD_GAME_MODES
        assert GameMode.DUO not in SQUAD_GAME_MODES


class TestTimeUtil:
    def test_unix_time_start_is_aware(self):
        assert unix_time_start().tzinfo is not None

    def test_datetime_now_uses_requested_timezone(self):
        now = datetime_now(Timezone.KST)
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(hours=9)

    @pytest.mark.parametrize('raw', ['2024-01-01T00:00:00Z', '2024-01-01T00:00:00+00:00'])
    def test_parse_utc_to_datetime(self, raw: str):
        parsed = parse_utc_to_datetime(raw, Timezone.KST)
        assert parsed == datetime(2024, 1, 1, 9, 0, tzinfo=parsed.tzinfo)

    def test_parse_naive_datetime_is_treated_as_utc(self):
        parsed = parse_utc_to_datetime(datetime(2024, 1, 1), Timezone.UTC)
        assert parsed == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_utc_to_datetime('not-a-datetime')

    def test_to_iso_roundtrip(self):
        now = datetime_now()
        assert parse_utc_to_datetime(to_iso(now)) == now


class TestModels:
    def test_normalize_player_id(self):
        assert normalize_player_id('account.abc123') == 'abc123'
        assert normalize_player_id('ab-cd-ef') == 'abcdef'
        assert normalize_player_id('') == ''

    def test_player_from_api_filters_non_match_relationships(self):
        player = Player.from_api(make_player_payload('tester', match_count=3))
        assert player.name == 'tester'
        assert player.normalized_id == '1ed1250b36304678ae706a0c5fa18f64'
        assert len(player.match_ids) == 3

    def test_match_from_api_and_player_stats(self):
        match = Match.from_api('match-1', make_match_payload('match-1', 'tester', win_place=3))
        stats = match.player_stats('tester')

        assert match.game_mode is GameMode.SQUAD
        assert match.match_type is MatchType.NORMAL
        assert stats.win_place == 3
        assert stats.damage_dealt == pytest.approx(250.5)
        assert stats.match_id == 'match-1'

    def test_match_player_stats_missing_raises(self):
        match = Match.from_api('match-1', make_match_payload('match-1', 'tester'))
        with pytest.raises(PlayerMatchStatsNotFoundError):
            match.player_stats('other_player')

    def test_stats_derived_properties(self):
        stats = Stats(rounds_played=4, damage_dealt=400.0, kills=6, deaths=3)
        assert stats.avg_damage_dealt == pytest.approx(100.0)
        assert stats.kd == pytest.approx(2.0)

    def test_stats_derived_properties_handle_zero(self):
        stats = Stats()
        assert stats.avg_damage_dealt == 0.0
        assert stats.kd == 0.0


class TestErrors:
    def test_all_errors_share_base_type(self):
        assert issubclass(PlayerNotFoundError, KSBotError)

    def test_player_not_found_user_message(self):
        error = PlayerNotFoundError(player_name='SonPANG')
        assert 'SonPANG' in error.user_message
        assert 'PlayerNotFoundError' in str(error)

    def test_not_enough_matches_message(self):
        error = NotEnoughMatchesError(match_num=3, required_match_num=20)
        assert '3/20' in error.user_message
