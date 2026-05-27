import os
import sqlite3

from ifinmail.db.schema import SCHEMA

DEFAULT_DB_PATH = os.path.expanduser("~/.ifinmail/admin.db")


def get_db(path: str | None = None) -> sqlite3.Connection:
    db_path = path or os.environ.get("IFINMAIL_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: str | None = None) -> sqlite3.Connection:
    conn = get_db(path)
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn
