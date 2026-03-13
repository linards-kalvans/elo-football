"""Database connection helpers for sync (sqlite3) and async (aiosqlite)."""

import sqlite3
from pathlib import Path

import aiosqlite

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "elo.db"


def get_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve database file path."""
    if db_path is None:
        return _DEFAULT_DB_PATH
    return Path(db_path)


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create a sync SQLite connection with WAL mode and foreign keys.

    Args:
        db_path: Path to SQLite database file. Defaults to data/elo.db.
            Use ":memory:" for in-memory database.

    Returns:
        Configured sqlite3.Connection.
    """
    path = str(db_path) if db_path == ":memory:" else str(get_db_path(db_path))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def get_async_connection(
    db_path: str | Path | None = None,
) -> aiosqlite.Connection:
    """Create an async SQLite connection with WAL mode and foreign keys.

    Args:
        db_path: Path to SQLite database file. Defaults to data/elo.db.

    Returns:
        Configured aiosqlite.Connection.
    """
    path = str(get_db_path(db_path))
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Initialize database schema and return connection.

    Creates all tables if they don't exist. Safe to call multiple times.

    Args:
        db_path: Path to SQLite database file. Use ":memory:" for tests.

    Returns:
        Configured sqlite3.Connection with schema applied.
    """
    conn = get_connection(db_path)
    schema_sql = _SCHEMA_PATH.read_text()

    # Execute schema statements individually (executescript commits implicitly)
    # We split on semicolons but handle the PRAGMA and trigger statements
    conn.executescript(schema_sql)
    return conn
