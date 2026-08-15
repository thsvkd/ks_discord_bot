"""SQLite 저장소 테스트."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import aiosqlite
import pytest

from factories import make_match_stats, make_player
from ks_bot.common.enums import GameMode, MatchType
from ks_bot.common.errors import PlayerMatchStatsNotFoundError, PlayerNotFoundError
from ks_bot.core.repository import PlayerRepository


class TestPlayerCrud:
    async def test_upsert_and_get_player(self, repository: PlayerRepository):
        player = make_player('player_a')
        await repository.upsert_player(player)

        assert await repository.get_player(normalized_id=player.normalized_id) == player
        assert await repository.get_player(player_name='player_a') == player

    async def test_upsert_twice_updates_instead_of_duplicating(self, repository: PlayerRepository):
        player = make_player('player_a')
        await repository.upsert_player(player)

        player.ban_type = 'TemporaryBan'
        await repository.upsert_player(player)

        stored = await repository.get_player(normalized_id=player.normalized_id)
        assert stored.ban_type == 'TemporaryBan'

    async def test_get_missing_player_raises(self, repository: PlayerRepository):
        with pytest.raises(PlayerNotFoundError):
            await repository.get_player(player_name='없는사람')

    async def test_player_exists(self, repository: PlayerRepository):
        await repository.upsert_player(make_player('player_a'))
        assert await repository.player_exists(player_name='player_a') is True
        assert await repository.player_exists(player_name='player_b') is False

    async def test_identifier_required(self, repository: PlayerRepository):
        with pytest.raises(ValueError):
            await repository.player_exists()


class TestUpdatedDate:
    async def test_updating_one_player_does_not_touch_others(self, repository: PlayerRepository):
        """예전 구현은 WHERE 없는 UPDATE로 모든 행의 updated_date를 덮어썼다."""
        old = make_player('old_player', normalized_id='old-id')
        await repository.upsert_player(old)
        old_date = await repository.get_player_update_date(player_name='old_player')

        await asyncio.sleep(0.01)
        await repository.upsert_player(make_player('new_player', normalized_id='new-id'))

        assert await repository.get_player_update_date(player_name='old_player') == old_date

    async def test_is_player_data_outdated(self, repository: PlayerRepository):
        await repository.upsert_player(make_player('player_a'))

        assert await repository.is_player_data_outdated(player_name='player_a', expiration_period=timedelta(days=1)) is False
        assert await repository.is_player_data_outdated(player_name='player_a', expiration_period=timedelta(seconds=-1)) is True

    async def test_unknown_player_is_outdated(self, repository: PlayerRepository):
        assert await repository.is_player_data_outdated(player_name='없는사람') is True


class TestDiscordLink:
    async def test_set_and_get_discord_id(self, repository: PlayerRepository):
        await repository.upsert_player(make_player('player_a'))
        await repository.set_discord_id('player_a', 12345)

        assert await repository.get_discord_id('player_a') == 12345
        assert await repository.get_player_name_by_discord_id(12345) == 'player_a'

    async def test_discord_id_moves_to_new_player(self, repository: PlayerRepository):
        await repository.upsert_player(make_player('player_a', normalized_id='id-a'))
        await repository.upsert_player(make_player('player_b', normalized_id='id-b'))

        await repository.set_discord_id('player_a', 999)
        await repository.set_discord_id('player_b', 999)

        assert await repository.get_player_name_by_discord_id(999) == 'player_b'
        assert await repository.get_discord_id('player_a') is None

    async def test_none_discord_id_is_ignored(self, repository: PlayerRepository):
        await repository.upsert_player(make_player('player_a'))
        await repository.set_discord_id('player_a', None)
        assert await repository.get_discord_id('player_a') is None

    async def test_unknown_discord_id_raises(self, repository: PlayerRepository):
        with pytest.raises(PlayerNotFoundError):
            await repository.get_player_name_by_discord_id(404)


class TestMatchStats:
    async def test_upsert_and_get(self, repository: PlayerRepository):
        stats = make_match_stats('player_a')
        await repository.upsert_player(make_player('player_a'))
        await repository.upsert_player_match_stats(stats)

        stored = await repository.get_player_match_stats('player_a', stats.match_id)
        assert stored == stats
        assert stored.game_mode is GameMode.SQUAD
        assert stored.match_type is MatchType.NORMAL
        assert stored.is_custom_match is False

    async def test_upsert_is_idempotent(self, repository: PlayerRepository):
        stats = make_match_stats('player_a')
        await repository.upsert_player_match_stats(stats)
        await repository.upsert_player_match_stats(stats)

        assert await repository.player_match_stats_exists('player_a', stats.match_id) is True

    async def test_missing_stats_raises(self, repository: PlayerRepository):
        with pytest.raises(PlayerMatchStatsNotFoundError):
            await repository.get_player_match_stats('player_a', 'unknown-match')

    async def test_bulk_lookup(self, repository: PlayerRepository):
        first = make_match_stats('player_a', 'match-1')
        second = make_match_stats('player_a', 'match-2')
        await repository.upsert_player_match_stats(first)
        await repository.upsert_player_match_stats(second)

        found = await repository.get_player_match_stats_bulk('player_a', ['match-1', 'match-2', 'match-3'])
        assert set(found) == {'match-1', 'match-2'}
        assert await repository.get_player_match_stats_bulk('player_a', []) == {}

    async def test_stats_arguments_required(self, repository: PlayerRepository):
        with pytest.raises(ValueError):
            await repository.player_match_stats_exists('', '')


class TestSchemaMigration:
    async def test_missing_columns_are_added_on_connect(self, db_path):
        """구버전 스키마의 DB를 열어도 부족한 컬럼이 자동으로 추가돼야 한다."""
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('CREATE TABLE players (id TEXT, normalized_id TEXT UNIQUE, name TEXT UNIQUE)')
            await conn.commit()

        repo = PlayerRepository(db_path)
        await repo.connect()
        try:
            columns = {row['name'] for row in await repo._fetch_all('PRAGMA table_info(players)')}
            assert {'discord_id', 'updated_date', 'match_list', 'clan_id'} <= columns

            # 마이그레이션 후 정상적으로 읽고 쓸 수 있어야 한다.
            player = make_player('legacy_player')
            await repo.upsert_player(player)
            assert await repo.get_player(player_name='legacy_player') == player
        finally:
            await repo.close()

    async def test_unique_column_can_be_added(self, db_path):
        """SQLite는 UNIQUE 제약이 붙은 컬럼 추가를 거부하므로, 제약 없이 추가돼야 한다."""
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('CREATE TABLE players (id TEXT)')
            await conn.execute('CREATE TABLE player_match_stats (match_id TEXT)')
            await conn.commit()

        repo = PlayerRepository(db_path)
        await repo.connect()
        try:
            columns = {row['name'] for row in await repo._fetch_all('PRAGMA table_info(players)')}
            assert {'normalized_id', 'name'} <= columns

            stats_columns = {row['name'] for row in await repo._fetch_all('PRAGMA table_info(player_match_stats)')}
            assert 'player_name' in stats_columns  # NOT NULL 제약이 붙은 컬럼
        finally:
            await repo.close()

    async def test_connection_required(self, db_path):
        repo = PlayerRepository(db_path)
        with pytest.raises(RuntimeError):
            _ = repo.conn
