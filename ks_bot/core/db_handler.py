from dataclasses import dataclass, field, fields, is_dataclass, asdict
from datetime import datetime, timedelta
import json

import sqlite3
from sqlite3 import Error, Cursor
from ks_bot.common.dataclass import *
from ks_bot.common.common import *
from ks_bot.common.error import *
from typing import Any


@dataclass
class Player_DB:
    player: Player = field(default_factory=Player)
    updated_date: datetime = field(default_factory=unix_time_start)


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

    def __init__(self):
        self.conn = None

    def _create_connection(self, db_file: str):
        try:
            self.db_file = db_file
            self.conn = sqlite3.connect(self.db_file)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            print(f'SQLite DB {self.db_file} connected.')
        except Error as e:
            print(e)

    def _close_connection(self):
        if self.conn:
            self.conn.close()
            print('SQLite DB connection closed.')

    def _execute_query(self, query: str, params=None):
        try:
            c = self.conn.cursor()
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            if query.strip().upper().startswith("SELECT"):
                return c.fetchall()
            else:
                self.conn.commit()
        except Error as e:
            print(e)
            return None

    def init(self) -> 'SQLiteDBHandler':
        self._create_connection('res/history.db')

        self._execute_query(SQLiteDBHandler.SQL_DROP_PLAYERS_TABLE)
        self._execute_query(SQLiteDBHandler.SQL_DROP_PLAYER_MATCH_STATS_TABLE)

        self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYERS_TABLE)
        self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYER_MATCH_STATS_TABLE)

        return self

    def open(self) -> 'SQLiteDBHandler':
        self._create_connection('res/history.db')

        self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYERS_TABLE)
        self._execute_query(SQLiteDBHandler.SQL_CREATE_PLAYER_MATCH_STATS_TABLE)

        return self

    def close(self):
        self._close_connection()

    def insert_dataclass(self, db_cursor: Cursor, table_name: str, dataclass_instance: Any) -> None:
        # 데이터클래스 필드 목록을 가져옵니다.
        dataclass_fields = fields(dataclass_instance)

        # 삽입할 컬럼 이름과 해당 값을 저장할 리스트를 준비합니다.
        column_names = []
        column_values = []

        for field in dataclass_fields:
            # 필드 이름을 컬럼 이름 리스트에 추가합니다.
            column_names.append(field.name)

            # 필드 값 가져오기
            value = getattr(dataclass_instance, field.name)

            # 필드 타입에 따라 처리
            if isinstance(value, (list, dict)):
                # 복잡한 타입은 JSON 문자열로 변환합니다.
                column_values.append(json.dumps(value))
            elif isinstance(value, bool):
                column_values.append(1 if value else 0)
            elif is_dataclass(value):
                # 데이터클래스 타입은 JSON 문자열로 변환합니다.
                column_values.append(json.dumps(asdict(value)))
            elif hasattr(value, 'value'):  # Enum 처리
                column_values.append(value.value)
            else:
                # 그 외의 타입은 직접 값을 사용합니다.
                column_values.append(value)

        # SQL 쿼리 문자열을 동적으로 구성합니다.
        columns_str = ', '.join(column_names)
        placeholders_str = ', '.join(['?' for _ in column_values])
        sql_query = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders_str})'

        # 데이터베이스에 쿼리를 실행합니다.
        db_cursor.execute(sql_query, column_values)

    def update_dataclass(self, db_cursor: Cursor, table_name: str, dataclass_instance: Any, identifier_field: str) -> None:
        """
        데이터클래스 인스턴스를 기반으로 데이터베이스 레코드를 업데이트합니다.

        :param db_cursor: 데이터베이스 커서
        :param table_name: 레코드를 업데이트할 테이블 이름
        :param dataclass_instance: 업데이트할 데이터를 포함하는 데이터클래스 인스턴스
        :param identifier_field: 업데이트할 레코드를 식별할 필드 이름
        """
        # 데이터클래스 필드 목록을 가져옵니다.
        dataclass_fields = fields(dataclass_instance)

        # 업데이트할 컬럼과 값 준비
        update_columns = []
        update_values = []

        identifier_value = None

        for field in dataclass_fields:
            value = getattr(dataclass_instance, field.name)

            if field.name == identifier_field:
                identifier_value = value
                continue  # 식별자 필드는 업데이트 대상에서 제외

            # 필드 타입에 따라 처리
            if isinstance(value, (list, dict)):
                update_values.append(json.dumps(value))  # 복잡한 타입은 JSON 문자열로 변환
            elif is_dataclass(value):
                update_values.append(json.dumps(asdict(value)))  # 데이터클래스 타입은 JSON으로 변환
            elif hasattr(value, 'value'):  # Enum 처리
                update_values.append(value.value)
            else:
                update_values.append(value)  # 그 외 타입은 직접 값을 사용

            update_columns.append(f"{field.name} = ?")

        # 식별자 값 추가
        update_values.append(identifier_value)

        # SQL 쿼리 문자열 구성
        update_columns_str = ', '.join(update_columns)
        sql_query = f"UPDATE {table_name} SET {update_columns_str} WHERE {identifier_field} = ?"

        # 쿼리 실행
        db_cursor.execute(sql_query, update_values)

    def player_exists(self, normalized_id: str = None, player_name: str = None) -> bool:
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

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        cursor.close()

        return count > 0

    def player_match_stats_exists(self, match_id: str) -> bool:
        if not match_id:
            raise ValueError("match_id must be provided.")

        query = "SELECT COUNT(*) FROM player_match_stats WHERE match_id = ?"
        params = (match_id,)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        cursor.close()

        return count > 0

    def get_player(self, normalized_id: str = None, player_name: str = None) -> Player | Error_Balancer:
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

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()

        if row:
            player_data = {field[0]: row[idx] for idx, field in enumerate(cursor.description) if field[0] in Player.__annotations__}
            player = Player(**player_data)
            player.match_list = json.loads(player.match_list)['data']
            return player
        else:
            return PlayerNotFoundError_Balancer(f"Player not found: {normalized_id or player_name}")

    def get_player_update_date(self, normalized_id: str = None, player_name: str = None) -> datetime | Error_Balancer:
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

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()

        if row:
            return parse_utc_to_datetime(row[0], Timezone.KST)
        else:
            return PlayerNotFoundError_Balancer(f"Player not found: {normalized_id or player_name}")

    def is_player_data_outdated(
        self, normalized_id: str = None, player_name: str = None, update_interval: timedelta = timedelta(days=7)
    ) -> bool | Error_Balancer:
        last_update = self.get_player_update_date(normalized_id, player_name)
        if isinstance(last_update, Error_Balancer):
            return last_update

        if last_update is None:
            return True
        else:
            return datetime.now(tz=Timezone.KST.to_pytz_timezone()) - last_update > update_interval

    def get_player_match_stats(self, match_id: str) -> PlayerMatchStats | Error_Balancer:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM player_match_stats WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        cursor.close()

        if row:
            match_stats_data = {field[0]: row[idx] for idx, field in enumerate(cursor.description) if field[0] in PlayerMatchStats.__annotations__}
            player_match_stats = PlayerMatchStats(**match_stats_data)
            player_match_stats.is_custom_match = True if player_match_stats.is_custom_match == '1' else False
            player_match_stats.game_mode = GameMode(player_match_stats.game_mode)
            player_match_stats.match_type = MatchType(player_match_stats.match_type)
            return player_match_stats
        else:
            return PlayerMatchStatsNotFoundError_Balancer(f"Player match stats not found: {match_id}")

    def insert_player(self, player: Player) -> None:
        updated_date = datetime.now(tz=Timezone.KST.to_pytz_timezone())
        player.match_list = json.dumps(dict(data=player.match_list))

        cursor = self.conn.cursor()
        self.insert_dataclass(cursor, 'players', player)
        self._execute_query("UPDATE players SET updated_date = ?", (updated_date,))
        self.conn.commit()
        cursor.close()

    def insert_player_match_stats(self, player_match_stats: PlayerMatchStats) -> None:
        updated_date = datetime.now(tz=Timezone.KST.to_pytz_timezone())

        cursor = self.conn.cursor()
        self.insert_dataclass(cursor, 'player_match_stats', player_match_stats)
        self._execute_query("UPDATE player_match_stats SET updated_date = ?", (updated_date,))
        self.conn.commit()
        cursor.close()

    def update_player(self, player: Player) -> None:
        updated_date = datetime.now(tz=Timezone.KST.to_pytz_timezone())

        cursor = self.conn.cursor()
        self.update_dataclass(cursor, 'players', player, 'normalized_id')
        self._execute_query("UPDATE players SET updated_date = ?", (updated_date,))
        self.conn.commit()
        cursor.close()

    def update_player_match_stats(self, player_match_stats: PlayerMatchStats) -> None:
        updated_date = datetime.now(tz=Timezone.KST.to_pytz_timezone())

        cursor = self.conn.cursor()
        self.update_dataclass(cursor, 'player_match_stats', player_match_stats, 'player_name')
        self._execute_query("UPDATE player_match_stats SET updated_date = ?", (updated_date,))
        self.conn.commit()
        cursor.close()


if __name__ == '__main__':
    db = SQLiteDBHandler()
    db.init()
    db.insert_player()
    db.close()
