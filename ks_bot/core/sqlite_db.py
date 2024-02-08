import sqlite3
from sqlite3 import Error


class SQLiteDB:
    SQL_CREATE_PLAYERS_TABLE = '''
        CREATE TABLE IF NOT EXISTS players (
            id integer PRIMARY KEY,
            name text NOT NULL UNIQUE,
        );'''
    SQL_CREATE_MATCHES_TABLE = '''
        CREATE TABLE IF NOT EXISTS matches (
            id integer PRIMARY KEY,
            match_id text NOT NULL UNIQUE,
            player_id test NOT NULL,
            date text NOT NULL,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        );'''

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

    def init(self):
        self._create_connection('res/history.db')
        self._execute_query(SQLiteDB.SQL_CREATE_PLAYERS_TABLE)
        self._execute_query(SQLiteDB.SQL_CREATE_MATCHES_TABLE)

    def close(self):
        self._close_connection()

    def create_member(self, name: str):
        insert_sql = '''INSERT INTO members(name) VALUES(?)'''
        self._execute_query(insert_sql, (name,))

    def create_match(self, match_id: str, member_id: int, date: str):
        insert_sql = '''INSERT INTO matches(match_id, member_id, date) VALUES(?, ?, ?)'''
        self._execute_query(insert_sql, (match_id, member_id, date))


if __name__ == '__main__':
    db = SQLiteDB()
    db.init()
    db.close()
