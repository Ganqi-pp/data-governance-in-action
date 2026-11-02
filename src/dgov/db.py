"""SQLite 治理沙箱：贴源表装载、参考码表、通用查询。"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from .paths import DB_PATH, RAW_DIR, REFERENCE_DIR

RAW_TABLES = {
    "market_register": ("ods_market_register", RAW_DIR / "market_register.csv"),
    "credit_rating": ("ods_credit_rating", RAW_DIR / "credit_rating.csv"),
    "complaint_case": ("ods_complaint_case", RAW_DIR / "complaint_case.csv"),
}

REFERENCE_TABLES = {
    "administrative_divisions": REFERENCE_DIR / "administrative_divisions.csv",
    "industry_codes": REFERENCE_DIR / "industry_codes.csv",
    "market_status_codes": REFERENCE_DIR / "market_status_codes.csv",
    "credit_levels": REFERENCE_DIR / "credit_levels.csv",
}

DWD_TABLES = {
    "market_register": "dwd_market_register",
    "credit_rating": "dwd_credit_rating",
    "complaint_case": "dwd_complaint_case",
}


def connect(reset: bool = False) -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh))


def _load_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    header = _read_header(path)
    quoted = ", ".join(f'"{col}" TEXT' for col in header)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({quoted})')
    placeholders = ", ".join("?" for _ in header)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [tuple((row.get(col) or "") for col in header) for row in reader]
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    conn.commit()
    return len(rows)


def load_reference(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, path in REFERENCE_TABLES.items():
        counts[name] = _load_csv(conn, f"ref_{name}", path)
    return counts


def load_raw(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for logical, (table, path) in RAW_TABLES.items():
        counts[logical] = _load_csv(conn, table, path)
    return counts


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def row_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"])


def fetch_all(conn: sqlite3.Connection, sql: str, params: Iterable | dict | None = None) -> list[dict]:
    args = params if isinstance(params, dict) else tuple(params or ())
    cur = conn.execute(sql, args)
    return [dict(row) for row in cur.fetchall()]


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable | dict | None = None) -> dict | None:
    args = params if isinstance(params, dict) else tuple(params or ())
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def preview(conn: sqlite3.Connection, table: str, limit: int = 3) -> list[dict]:
    return fetch_all(conn, f'SELECT * FROM "{table}" LIMIT ?', (limit,))
