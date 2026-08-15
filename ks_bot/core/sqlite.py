"""SQLite 저장소 공통 기반.

연결 관리와 스키마 마이그레이션은 저장소마다 똑같이 필요하므로 여기에 모은다.
스키마는 하위 클래스가 `TABLES`/`INDEXES`로 선언한다.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import Any, TypeVar

import aiosqlite

from ks_bot.logging_config import get_logger

__all__ = ['SqliteRepository']

logger = get_logger(__name__)

_T = TypeVar('_T', bound='SqliteRepository')


def _split_top_level(body: str) -> list[str]:
    """괄호 깊이를 고려해 최상위 콤마 기준으로 분리한다."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
            continue
        current.append(char)
    parts.append(''.join(current))
    return parts


def parse_column_definitions(create_sql: str) -> list[tuple[str, str]]:
    """CREATE TABLE 문에서 (컬럼명, 컬럼 타입) 목록을 추출한다.

    PRIMARY KEY/FOREIGN KEY 등 테이블 제약 조건 행은 제외한다.
    """
    body = create_sql[create_sql.index('(') + 1 : create_sql.rindex(')')]
    definitions: list[tuple[str, str]] = []
    for raw in _split_top_level(body):
        tokens = raw.split()
        if not tokens:
            continue
        name = tokens[0]
        if name.upper() in {'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT'}:
            continue
        column_type = tokens[1] if len(tokens) > 1 else 'TEXT'
        definitions.append((name, column_type))
    return definitions


class SqliteRepository:
    """연결/스키마 관리를 담당하는 저장소 기반 클래스.

    하위 클래스는 `TABLES`에 (테이블명, CREATE 문) 쌍을, `INDEXES`에 CREATE INDEX 문을 선언한다.
    """

    TABLES: tuple[tuple[str, str], ...] = ()
    INDEXES: tuple[str, ...] = ()

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self._conn: aiosqlite.Connection | None = None

    # ---------- 연결 관리 ----------

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError('DB에 연결되어 있지 않습니다. connect() 를 먼저 호출하세요.')
        return self._conn

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    async def __aenter__(self: _T) -> _T:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self: _T, *, reset: bool = False) -> _T:
        """DB에 연결하고 스키마를 준비한다.

        Args:
            reset: True면 기존 테이블을 지우고 새로 만든다(테스트/초기화용).
        """
        if self._conn is not None:
            return self

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute('PRAGMA foreign_keys = ON;')
        await self._conn.execute('PRAGMA journal_mode = WAL;')

        if reset:
            # 참조 방향의 역순으로 지운다.
            for table, _ in reversed(self.TABLES):
                await self._conn.execute(f'DROP TABLE IF EXISTS {table};')

        for _, create_sql in self.TABLES:
            await self._conn.execute(create_sql)
        await self._conn.commit()

        # 인덱스는 마이그레이션으로 컬럼이 모두 채워진 뒤에 만들어야 한다.
        for table, create_sql in self.TABLES:
            await self._migrate_missing_columns(table, create_sql)

        for index_sql in self.INDEXES:
            await self._conn.execute(index_sql)
        await self._conn.commit()

        logger.info('SQLite DB에 연결했습니다: %s', self.db_path)
        return self

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info('SQLite DB 연결을 종료했습니다.')

    async def _migrate_missing_columns(self, table: str, create_sql: str) -> None:
        """스키마에는 있는데 기존 테이블에 없는 컬럼을 추가한다.

        SQLite의 `ADD COLUMN`은 UNIQUE/PRIMARY KEY/기본값 없는 NOT NULL 제약을 허용하지 않으므로,
        컬럼명과 타입만 남겨 추가한다.
        """
        existing = {row['name'] for row in await self._fetch_all(f'PRAGMA table_info({table})')}
        for name, column_type in parse_column_definitions(create_sql):
            if name not in existing:
                logger.info('테이블 %s에 컬럼 %s을(를) 추가합니다.', table, name)
                await self.conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {column_type}')
        await self.conn.commit()

    # ---------- 저수준 헬퍼 ----------

    async def _fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(query, tuple(params)) as cursor:
            return list(await cursor.fetchall())

    async def _fetch_one(self, query: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(query, tuple(params)) as cursor:
            return await cursor.fetchone()

    async def _execute(self, query: str, params: Iterable[Any] = ()) -> None:
        await self.conn.execute(query, tuple(params))
        await self.conn.commit()
