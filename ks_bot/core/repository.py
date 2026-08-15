"""플레이어/매치 전적 영속성 계층.

스키마는 명시적으로 선언한다(예전에는 dataclass에서 DDL을 생성했는데, 컬럼 순서/타입이
데이터클래스 정의에 암묵적으로 묶여 있어 추적이 어려웠다).
연결 관리와 누락 컬럼 마이그레이션은 `SqliteRepository`가 담당한다.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from ks_bot.common.enums import GameMode, MatchType
from ks_bot.common.errors import PlayerMatchStatsNotFoundError, PlayerNotFoundError
from ks_bot.common.models import Player, PlayerMatchStats
from ks_bot.common.timeutil import datetime_now, parse_utc_to_datetime, to_iso
from ks_bot.core.sqlite import SqliteRepository
from ks_bot.logging_config import get_logger

__all__ = ['PlayerRepository']

logger = get_logger(__name__)

_PLAYERS_TABLE = 'players'
_MATCH_STATS_TABLE = 'player_match_stats'

_CREATE_PLAYERS_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_PLAYERS_TABLE} (
    id            TEXT,
    normalized_id TEXT UNIQUE,
    name          TEXT UNIQUE,
    platform      TEXT,
    ban_type      TEXT,
    clan_id       TEXT,
    rank_stats    TEXT,
    normal_stats  TEXT,
    match_list    TEXT,
    discord_id    INTEGER,
    updated_date  DATETIME
);
"""

_CREATE_MATCH_STATS_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_MATCH_STATS_TABLE} (
    player_name      TEXT NOT NULL,
    match_id         TEXT NOT NULL,
    is_custom_match  INTEGER,
    game_mode        TEXT,
    match_type       TEXT,
    DBNOs            INTEGER,
    boosts           INTEGER,
    damage_dealt     REAL,
    death_type       TEXT,
    headshot_kills   INTEGER,
    heals            INTEGER,
    win_place        INTEGER,
    kill_place       INTEGER,
    kill_streaks     INTEGER,
    kills            INTEGER,
    assists          INTEGER,
    longest_kill     REAL,
    revives          INTEGER,
    ride_distance    REAL,
    swim_distance    REAL,
    walk_distance    REAL,
    road_kills       INTEGER,
    team_kills       INTEGER,
    time_survived    INTEGER,
    vehicle_destroys INTEGER,
    weapons_acquired INTEGER,
    updated_date     DATETIME,
    PRIMARY KEY (player_name, match_id)
);
"""

_CREATE_INDEXES = (
    f'CREATE INDEX IF NOT EXISTS idx_players_discord_id ON {_PLAYERS_TABLE}(discord_id);',
    f'CREATE INDEX IF NOT EXISTS idx_match_stats_player ON {_MATCH_STATS_TABLE}(player_name);',
)

_JSON_PLAYER_FIELDS = ('rank_stats', 'normal_stats')


class PlayerRepository(SqliteRepository):
    """플레이어/매치 전적 저장소."""

    TABLES = (
        (_PLAYERS_TABLE, _CREATE_PLAYERS_TABLE),
        (_MATCH_STATS_TABLE, _CREATE_MATCH_STATS_TABLE),
    )
    INDEXES = _CREATE_INDEXES

    @staticmethod
    def _identifier_clause(normalized_id: str | None, player_name: str | None) -> tuple[str, tuple[Any, ...]]:
        if normalized_id:
            return 'normalized_id = ?', (normalized_id,)
        if player_name:
            return 'name = ?', (player_name,)
        raise ValueError("'normalized_id' 또는 'player_name' 중 하나는 반드시 필요합니다.")

    # ---------- 플레이어 ----------

    async def upsert_player(self, player: Player, updated_date: datetime | None = None) -> None:
        """플레이어를 저장한다. 이미 있으면 갱신한다(discord_id는 보존)."""
        updated_date = updated_date or datetime_now()
        await self._execute(
            f"""
            INSERT INTO {_PLAYERS_TABLE}
                (id, normalized_id, name, platform, ban_type, clan_id, rank_stats, normal_stats, match_list, updated_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_id) DO UPDATE SET
                id           = excluded.id,
                name         = excluded.name,
                platform     = excluded.platform,
                ban_type     = excluded.ban_type,
                clan_id      = excluded.clan_id,
                rank_stats   = excluded.rank_stats,
                normal_stats = excluded.normal_stats,
                match_list   = excluded.match_list,
                updated_date = excluded.updated_date
            """,
            (
                player.id,
                player.normalized_id,
                player.name,
                player.platform,
                player.ban_type,
                player.clan_id,
                json.dumps(player.rank_stats, ensure_ascii=False),
                json.dumps(player.normal_stats, ensure_ascii=False),
                json.dumps({'data': player.match_list}, ensure_ascii=False),
                to_iso(updated_date),
            ),
        )

    async def player_exists(self, normalized_id: str | None = None, player_name: str | None = None) -> bool:
        clause, params = self._identifier_clause(normalized_id, player_name)
        row = await self._fetch_one(f'SELECT 1 FROM {_PLAYERS_TABLE} WHERE {clause} LIMIT 1', params)
        return row is not None

    async def get_player(self, normalized_id: str | None = None, player_name: str | None = None) -> Player:
        clause, params = self._identifier_clause(normalized_id, player_name)
        row = await self._fetch_one(f'SELECT * FROM {_PLAYERS_TABLE} WHERE {clause}', params)
        if row is None:
            raise PlayerNotFoundError(player_name=player_name or normalized_id or '')
        return _row_to_player(row)

    async def get_player_update_date(self, normalized_id: str | None = None, player_name: str | None = None) -> datetime:
        clause, params = self._identifier_clause(normalized_id, player_name)
        row = await self._fetch_one(f'SELECT updated_date FROM {_PLAYERS_TABLE} WHERE {clause}', params)
        if row is None or row['updated_date'] is None:
            raise PlayerNotFoundError(player_name=player_name or normalized_id or '')
        return parse_utc_to_datetime(row['updated_date'])

    async def is_player_data_outdated(
        self,
        normalized_id: str | None = None,
        player_name: str | None = None,
        expiration_period: timedelta = timedelta(days=7),
    ) -> bool:
        """마지막 갱신 시각이 `expiration_period`보다 오래됐는지 판단한다."""
        try:
            last_update = await self.get_player_update_date(normalized_id, player_name)
        except PlayerNotFoundError:
            return True
        return datetime_now() - last_update > expiration_period

    async def set_discord_id(self, player_name: str, discord_id: int | None) -> None:
        """플레이어에 디스코드 계정을 연결한다. 다른 플레이어에 걸린 동일 ID는 해제한다."""
        if discord_id is None:
            return
        await self.conn.execute(
            f'UPDATE {_PLAYERS_TABLE} SET discord_id = NULL WHERE discord_id = ? AND name != ?',
            (int(discord_id), player_name),
        )
        await self.conn.execute(
            f'UPDATE {_PLAYERS_TABLE} SET discord_id = ? WHERE name = ?',
            (int(discord_id), player_name),
        )
        await self.conn.commit()

    async def get_discord_id(self, player_name: str) -> int | None:
        row = await self._fetch_one(f'SELECT discord_id FROM {_PLAYERS_TABLE} WHERE name = ?', (player_name,))
        if row is None:
            raise PlayerNotFoundError(player_name=player_name)
        return int(row['discord_id']) if row['discord_id'] is not None else None

    async def get_player_name_by_discord_id(self, discord_id: int) -> str:
        row = await self._fetch_one(f'SELECT name FROM {_PLAYERS_TABLE} WHERE discord_id = ?', (int(discord_id),))
        if row is None:
            raise PlayerNotFoundError(player_name=f'discord_id={discord_id}')
        return row['name']

    # ---------- 매치 전적 ----------

    async def upsert_player_match_stats(self, stats: PlayerMatchStats, updated_date: datetime | None = None) -> None:
        updated_date = updated_date or datetime_now()
        columns = [f.name for f in fields(PlayerMatchStats)] + ['updated_date']
        values = [_serialize_value(getattr(stats, f.name)) for f in fields(PlayerMatchStats)] + [to_iso(updated_date)]
        placeholders = ', '.join('?' for _ in columns)
        await self._execute(
            f'INSERT OR REPLACE INTO {_MATCH_STATS_TABLE} ({", ".join(columns)}) VALUES ({placeholders})',
            values,
        )

    async def player_match_stats_exists(self, player_name: str, match_id: str) -> bool:
        if not player_name or not match_id:
            raise ValueError("'player_name'과 'match_id'가 모두 필요합니다.")
        row = await self._fetch_one(
            f'SELECT 1 FROM {_MATCH_STATS_TABLE} WHERE player_name = ? AND match_id = ? LIMIT 1',
            (player_name, match_id),
        )
        return row is not None

    async def get_player_match_stats(self, player_name: str, match_id: str) -> PlayerMatchStats:
        row = await self._fetch_one(
            f'SELECT * FROM {_MATCH_STATS_TABLE} WHERE player_name = ? AND match_id = ?',
            (player_name, match_id),
        )
        if row is None:
            raise PlayerMatchStatsNotFoundError(player_name=player_name, match_id=match_id)
        return _row_to_match_stats(row)

    async def get_player_match_stats_bulk(self, player_name: str, match_ids: list[str]) -> dict[str, PlayerMatchStats]:
        """여러 매치 전적을 한 번의 쿼리로 조회한다(match_id → 전적)."""
        if not match_ids:
            return {}
        placeholders = ', '.join('?' for _ in match_ids)
        rows = await self._fetch_all(
            f'SELECT * FROM {_MATCH_STATS_TABLE} WHERE player_name = ? AND match_id IN ({placeholders})',
            (player_name, *match_ids),
        )
        return {row['match_id']: _row_to_match_stats(row) for row in rows}


# ---------- 직렬화 헬퍼 ----------


def _serialize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (GameMode, MatchType)):
        return value.value
    if isinstance(value, datetime):
        return to_iso(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _loads_json(raw: Any, default: Any) -> Any:
    if raw in (None, ''):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning('JSON 컬럼을 파싱하지 못했습니다. 기본값을 사용합니다.')
        return default


def _row_to_player(row: aiosqlite.Row) -> Player:
    match_list = _loads_json(row['match_list'], {'data': []})
    if isinstance(match_list, dict):
        match_list = match_list.get('data', [])

    player = Player(
        id=row['id'] or '',
        normalized_id=row['normalized_id'] or '',
        name=row['name'] or '',
        platform=row['platform'] or '',
        ban_type=row['ban_type'] or '',
        clan_id=row['clan_id'] or '',
        match_list=match_list,
    )
    for json_field in _JSON_PLAYER_FIELDS:
        setattr(player, json_field, _loads_json(row[json_field], {}))
    return player


def _row_to_match_stats(row: aiosqlite.Row) -> PlayerMatchStats:
    kwargs: dict[str, Any] = {}
    for f in fields(PlayerMatchStats):
        value = row[f.name]
        if f.name == 'is_custom_match':
            kwargs[f.name] = bool(int(value)) if value not in (None, '') else False
        elif f.name == 'game_mode':
            kwargs[f.name] = GameMode.from_string(value or '')
        elif f.name == 'match_type':
            kwargs[f.name] = MatchType.from_string(value or '')
        elif f.type in ('int', int):
            kwargs[f.name] = int(value) if value is not None else 0
        elif f.type in ('float', float):
            kwargs[f.name] = float(value) if value is not None else 0.0
        else:
            kwargs[f.name] = value if value is not None else ''
    return PlayerMatchStats(**kwargs)
