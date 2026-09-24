"""SQLite connection helpers used by the API."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "nifty100.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a row-producing SQLite connection to the canonical database."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    """Yield a request-scoped SQLite connection and close it afterwards."""
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()
