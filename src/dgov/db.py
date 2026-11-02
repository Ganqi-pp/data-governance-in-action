# -*- coding: utf-8 -*-
"""SQLite 连接与元数据读取工具。"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .config import DB_PATH, SQL_DIR, DATA_DIR


def _regexp(pattern: str, value) -> int:
    if value is None:
        return 0
    try:
        return 1 if re.search(pattern, str(value)) else 0
    except re.error:
        return 0


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.create_function("REGEXP", 2, _regexp)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def run_sql_file(conn: sqlite3.Connection, filename: str) -> None:
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def table_columns(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [
        {
            "name": r["name"],
            "type": (r["type"] or "TEXT").upper(),
            "notnull": bool(r["notnull"]),
            "pk": bool(r["pk"]),
        }
        for r in rows
    ]


def row_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def scalar(conn: sqlite3.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None
