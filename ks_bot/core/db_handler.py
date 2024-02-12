from dataclasses import dataclass, field, fields, is_dataclass, asdict
from datetime import datetime, timedelta
import json
import os

import aiosqlite
from ks_bot.common.dataclass import *
from ks_bot.common.common import *
from ks_bot.common.error import *
from ks_bot.utils import *
from typing import Any


@dataclass
class Player_DB:
    player: Player = field(default_factory=Player)
    updated_date: datetime = field(default_factory=unix_time_start)
    discord_id: str = ''


@dataclass
class PlayerMatchStats_DB:
    player_match_stats: PlayerMatchStats = field(default_factory=PlayerMatchStats)
    updated_date: datetime = field(default_factory=unix_time_start)


def create_table_query_for_dataclass_with_constraints(dataclass_type, table_name: str, unique_fields=None, foreign_keys=None):
    column_definitions = []
    # 데이터클래스 필드를 순회합니다.
    for field in fields(dataclass_type):
        # 내부 데이터클래스의 필드를 처리합니다.
        if is_dataclass(field.type):
            for nested_field in fields(field.type):
                column_name = nested_field.name
                column_type = "TEXT"
                if nested_field.type in [int, bool]:
                    column_type = "INTEGER"
                elif nested_field.type == float:
                    column_type = "REAL"
                elif nested_field.type == datetime:
                    column_type = "DATETIME"

                column_definition = f"{column_name} {column_type}"
                if unique_fields and column_name in unique_fields:
                    column_definition += " UNIQUE"
                column_definitions.append(column_definition)
        else:
            column_name = field.name
            column_type = "TEXT"
            if field.type == int:
                column_type = "INTEGER"
            elif field.type == float:
                column_type = "REAL"
            elif field.type == datetime:
                column_type = "DATETIME"

            column_definition = f"{column_name} {column_type}"
            if unique_fields and column_name in unique_fields:
                column_definition += " UNIQUE"
            column_definitions.append(column_definition)

    # 외래 키 제약 조건을 추가합니다.
    if foreign_keys:
        for fk in foreign_keys:
            column_definitions.append(f"FOREIGN KEY({fk['field']}) REFERENCES {fk['references']}({fk['ref_field']}) ON DELETE CASCADE")

    columns_sql = ",\n    ".join(column_definitions)
    create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {columns_sql}\n);"
    return create_table_sql


class SQLiteDBHandler:
    SQL_CREATE_PLAYERS_TABLE = create_table_query_for_dataclass_with_constraints(Player_DB, "players", unique_fields=["normalized_id", "name"])
    SQL_CREATE_PLAYER_MATCH_STATS_TABLE = create_table_query_for_dataclass_with_constraints(
        PlayerMatchStats_DB, "player_match_stats", foreign_keys=[{"field": "player_name", "references": "players", "ref_field": "name"}]
    )
    SQL_DROP_PLAYERS_TABLE = "DROP TABLE IF EXISTS players;"
    SQL_DROP_PLAYER_MATCH_STATS_TABLE = "DROP TABLE IF EXISTS player_match_stats;"

    def __init__(self, db_file: str):
        self.db_file: str = os.path.abspath(db_file)

    async def __aenter__(self):
        return await self._create_connection()

    async def __aexit__(self, exc_type, exc, tb):
        await self._close_connection()

    async def _create_connection(self):
        self.conn = await aiosqlite.connect(self.db_file)
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        print(f'SQLite DB {self.db_file} connected.')

    async def _close_connection(self):
        if self.conn:
            await self.conn.close()
            print('SQLite DB connection closed.')

    async def _execute_query(self, query: str, params=None):
        async with self.conn.execute(query, params or ()) as cursor:
            if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("PRAGMA"):
                return await cursor.fetchall()
            else:
                await self.conn.commit()

    async def _insert_dataclass(self, table_name: str, dataclass_instance: Any) -> None:
        column_names, column_values = [], []
        for field in fields(dataclass_instance):
            column_names.append(field.name)
            value = getattr(dataclass_instance, field.name)
            if isinstance(value, (list, dict, bool)) or is_dataclass(value):
                value = json.dumps(value if not isinstance(value, bool) else int(value))
            elif hasattr(value, 'value'):  # Enum 처리
                value = value.value
            column_values.append(value)

        columns_str = ', '.join(column_names)
        placeholders_str = ', '.join(['?' for _ in column_values])
        sql_query = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders_str})'

        async with self.conn.cursor() as cursor:
            await cursor.execute(sql_query, column_values)
            await self.conn.commit()

    async def _update_dataclass(self, table_name: str, dataclass_instance: Any, identifier_field: str) -> None:
        update_columns, update_values = [], []
        identifier_value = None

        for field in fields(dataclass_instance):
            value = getattr(dataclass_instance, field.name)
            if field.name == identifier_field:
                identifier_value = value
                continue

            if isinstance(value, (list, dict, bool)) or is_dataclass(value):
                value = json.dumps(value if not isinstance(value, bool) else int(value))
            elif hasattr(value, 'value'):  # Enum 처리
                value = value.value
            update_columns.append(f"{field.name} = ?")
            update_values.append(value)

        update_columns_str = ', '.join(update_columns)
        sql_query = f"UPDATE {table_name} SET {update_columns_str} WHERE {identifier_field} = ?"
        update_values.append(identifier_value)

        async with self.conn.cursor() as cursor:
            await cursor.execute(sql_query, update_values)
            await self.conn.commit()

    async def _get_player_update_date(self, normalized_id: str = None, player_name: str = None) -> datetime:
        if normalized_id is None and player_name is None:
            raise ValueError("Either 'normalized_id' or 'player_name' must be provided.")

        query = "SELECT updated_date FROM players WHERE "
        params = ()
        if normalized_id:
            query += "normalized_id = ?"
            params = (normalized_id,)
        elif player_name:
            query += "name = ?"
            params = (player_name,)

        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

        if row:
            return parse_utc_to_datetime(row[0], Timezone.KST)
        else:
            raise PlayerNotFoundError_Balancer

    async def compare_and_update_structure(self, table_name: str, create_table_sql: str):
        # 기존 테이블 구조를 가져오는 SQL
        query = f"PRAGMA table_info({table_name})"
        existing_columns = [row[1] for row in await self._execute_query(query)]

        # 새로운 테이블 구조에서 컬럼 추출
        new_columns = [part.split()[0] for part in create_table_sql.split('(')[1].split(')')[0].split(',')]

        # 컬럼 추가 확인 및 실행
        for column_definition in new_columns:
            column_name = column_definition.split()[0]
            if column_name not in existing_columns:
                # 새로운 컬럼 추가
                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"
                await self._execute_query(alter_query)
            else:
                # 기존 컬럼이 있으므로, 변경 없음
                pass

        # 컬럼 삭제 확인 (에러 발생)
        for existing_column in existing_columns:
            if existing_column not in new_columns:
                raise Exception(f"자동 DB 마이그레이션에 실패하였습니다. 삭제되는 컬럼: {existing_column} in {table_name}")

    #### DBHandler methods

    async def init(self) -> 'SQLiteDBHandler':
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        await self._create_connection()

        await self._execute_query(SQLiteDBHandler.SQL_DROP_PLAYERS_TABLE)
        await self._execute_query(SQLiteDBHandler.SQL_DROP_PLAYER_MATCH_STATS_TABLE)

        await self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYERS_TABLE)
        await self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYER_MATCH_STATS_TABLE)

        return self

    async def open(self) -> 'SQLiteDBHandler':
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        await self._create_connection()

        await self.compare_and_update_structure('players', SQLiteDBHandler.SQL_CREATE_PLAYERS_TABLE)
        await self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYERS_TABLE)
        await self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYER_MATCH_STATS_TABLE)

        return self

    async def close(self):
        await self._close_connection()

    async def is_player_exists(self, normalized_id: str = None, player_name: str = None) -> bool:
        if normalized_id is None and player_name is None:
            raise ValueError("Either 'normalized_id' or 'player_name' must be provided.")

        query = "SELECT COUNT(*) FROM players WHERE "
        params = ()
        if normalized_id:
            query += "normalized_id = ?"
            params = (normalized_id,)
        elif player_name:
            query += "name = ?"
            params = (player_name,)

        async with self.conn.execute(query, params) as cursor:
            count = (await cursor.fetchone())[0]

        return count > 0

    async def get_player(self, normalized_id: str = None, player_name: str = None) -> Player:
        if normalized_id is None and player_name is None:
            raise ValueError("Either 'normalized_id' or 'player_name' must be provided.")

        query = "SELECT * FROM players WHERE "
        params = ()
        if normalized_id:
            query += "normalized_id = ?"
            params = (normalized_id,)
        elif player_name:
            query += "name = ?"
            params = (player_name,)

        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

        if row:
            player_data = {field[0]: row[idx] for idx, field in enumerate(cursor.description) if field[0] in Player.__annotations__}
            player = Player(**player_data)
            player.match_list = json.loads(player.match_list)['data']
            player.normal_stats = json.loads(player.normal_stats)
            player.rank_stats = json.loads(player.rank_stats)
            return player
        else:
            raise PlayerNotFoundError_Balancer

    async def is_player_match_stats_exists(self, player_name: str, match_id: str) -> bool:
        if not match_id or not player_name:
            raise ValueError("Both 'player_name' and 'match_id' must be provided.")

        query = "SELECT COUNT(*) FROM player_match_stats WHERE player_name = ? AND match_id = ?"
        params = (
            player_name,
            match_id,
        )

        async with self.conn.execute(query, params) as cursor:
            count = (await cursor.fetchone())[0]

        return count > 0

    async def get_player_match_stats(self, player_name: str, match_id: str) -> PlayerMatchStats:
        async with self.conn.execute(
            "SELECT * FROM player_match_stats WHERE player_name = ? AND match_id = ?",
            (
                player_name,
                match_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            match_stats_data = {field[0]: row[idx] for idx, field in enumerate(cursor.description) if field[0] in PlayerMatchStats.__annotations__}
            player_match_stats = PlayerMatchStats(**match_stats_data)
            player_match_stats.is_custom_match = True if player_match_stats.is_custom_match == '1' else False
            player_match_stats.game_mode = GameMode(player_match_stats.game_mode)
            player_match_stats.match_type = MatchType(player_match_stats.match_type)
            return player_match_stats
        else:
            raise PlayerMatchStatsNotFoundError_Balancer

    async def is_player_data_outdated(
        self, normalized_id: str = None, player_name: str = None, expiration_period: timedelta = timedelta(days=7)
    ) -> bool:
        last_update = await self._get_player_update_date(normalized_id, player_name)
        if isinstance(last_update, Error_Balancer):
            return True  # 에러가 발생한 경우 데이터를 업데이트해야 한다고 가정

        if last_update is None:
            return True
        else:
            return datetime_now() - last_update > expiration_period

    async def insert_player(self, player: Player, updated_date: datetime = datetime_now()) -> None:
        player_copy = Player(**asdict(player))
        player_copy.match_list = json.dumps({'data': player.match_list})

        await self._insert_dataclass('players', player_copy)
        await self.conn.execute("UPDATE players SET updated_date = ?", (updated_date,))
        await self.conn.commit()

    async def insert_player_match_stats(self, player_match_stats: PlayerMatchStats, updated_date: datetime = datetime_now()) -> None:
        player_match_stats_copy = PlayerMatchStats(**asdict(player_match_stats))

        await self._insert_dataclass('player_match_stats', player_match_stats_copy)
        await self.conn.execute("UPDATE player_match_stats SET updated_date = ?", (updated_date,))
        await self.conn.commit()

    async def update_player(self, player: Player, updated_date: datetime = datetime_now()) -> None:
        player_copy = Player(**asdict(player))
        player_copy.match_list = json.dumps({'data': player.match_list})

        await self._update_dataclass('players', player_copy, 'normalized_id')
        await self.conn.execute("UPDATE players SET updated_date = ?", (updated_date,))
        await self.conn.commit()

    async def update_player_match_stats(self, player_match_stats: PlayerMatchStats, updated_date: datetime = datetime_now()) -> None:
        player_match_stats_copy = PlayerMatchStats(**asdict(player_match_stats))

        await self._update_dataclass('player_match_stats', player_match_stats_copy, 'match_id')
        await self.conn.execute("UPDATE player_match_stats SET updated_date = ?", (updated_date,))
        await self.conn.commit()

    async def update_discord_id(self, player_name: str, discord_id: str) -> None:
        await self.conn.execute("UPDATE players SET discord_id = ? WHERE name = ?", (discord_id, player_name))
        await self.conn.commit()

    async def get_discord_id(self, player_name: str) -> str:
        async with self.conn.execute("SELECT discord_id FROM players WHERE name = ?", (player_name,)) as cursor:
            row = await cursor.fetchone()
        if row:
            return row[0]
        else:
            raise PlayerNotFoundError_Balancer

    async def get_player_name_by_discord_id(self, discord_id: str) -> str:
        async with self.conn.execute("SELECT name FROM players WHERE discord_id = ?", (discord_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            return row[0]
        else:
            raise PlayerNotFoundError_Balancer


if __name__ == '__main__':
    import asyncio

    db_handler = SQLiteDBHandler('test_history.db')
    asyncio.run(db_handler.init())

    async def insert_player_main():
        player1 = Player(
            id='account.1ed1250b36304678ae706a0c5fa18f64',
            normalized_id='1ed1250b36304678ae706a0c5fa18f64',
            name='example_player_name1',
            platform='steam',
            ban_type='Innocent',
            match_list=[
                {"type": "match", "id": "f6a69afd-fb60-45da-8b40-a2e013db0f33"},  # 1
                {"type": "match", "id": "456ad743-389e-44e1-9da4-18fb12ea54de"},  # 2
                {"type": "match", "id": "bdae2395-0552-49bb-b543-3c3b33e758f4"},  # 3
                {"type": "match", "id": "7cbaf996-cc3f-426b-bba4-ba5920da75d0"},  # 4
                {"type": "match", "id": "4c8e3260-6cf1-47bb-9072-6ec1959c7b90"},  # 5
                {"type": "match", "id": "9b32dcb9-8389-4bb6-8f93-cd660e8c9d50"},  # 6
                {"type": "match", "id": "8fcf2fc9-dd1a-4c45-b335-a3ed611a9157"},  # 7
                {"type": "match", "id": "6dfac99a-fec5-4a5c-8c65-278f9603778a"},  # 8
            ],
        )
        await db_handler.insert_player(player1)

        player2 = await db_handler.get_player(player1.normalized_id)
        print(player2)

        assert player1 == player2

    async def insert_player_match_stats_main():
        player_match_stats1 = PlayerMatchStats(
            player_name='example_player_name1',
            match_id='f6a69afd-fb60-45da-8b40-a2e013db0f33',
            is_custom_match=False,
            game_mode=GameMode.SQUAD,
            match_type=MatchType.NORMAL,
            DBNOs=5,
            boosts=5,
            damage_dealt=5.0,
            death_type='',
            headshot_kills=5,
            heals=5,
            win_place=5,
            kill_place=5,
            kill_streaks=5,
            kills=5,
            assists=5,
            longest_kill=5.0,
            revives=5,
            ride_distance=5.0,
            swim_distance=5.0,
            walk_distance=5.0,
            road_kills=5,
            team_kills=5,
            time_survived=5,
            vehicle_destroys=5,
            weapons_acquired=5,
        )
        await db_handler.insert_player_match_stats(player_match_stats1)

        player_match_stats2 = await db_handler.get_player_match_stats(player_match_stats1.match_id)
        print(player_match_stats2)

        assert player_match_stats1 == player_match_stats2

    asyncio.run(insert_player_main())
    asyncio.run(insert_player_match_stats_main())
    asyncio.run(db_handler.close())
