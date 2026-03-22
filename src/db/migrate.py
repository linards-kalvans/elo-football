#!/usr/bin/env python3
"""Schema migration runner for the Elo database.

Tracks applied migrations in a `schema_migrations` table and applies
pending numbered SQL files from `src/db/migrations/` in order.

Idempotent — safe to run multiple times. Uses aiosqlite (async).

Usage:
    uv run python src/db/migrate.py           # Apply pending migrations
    uv run python src/db/migrate.py --status   # Show migration status
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import aiosqlite

from src.db.connection import get_db_path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def _ensure_migrations_table(conn: aiosqlite.Connection) -> None:
    """Create the schema_migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    await conn.commit()


async def _get_applied_versions(conn: aiosqlite.Connection) -> set[str]:
    """Return the set of already-applied migration version strings."""
    cursor = await conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    )
    rows = await cursor.fetchall()
    return {row[0] for row in rows}


def _discover_migrations() -> list[tuple[str, str, Path]]:
    """Scan the migrations directory for numbered SQL files.

    Returns:
        Sorted list of (version, filename, path) tuples.
        Version is the numeric prefix (e.g., "001").
    """
    if not _MIGRATIONS_DIR.exists():
        return []

    migrations = []
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        # Extract version from filename like "001_initial_schema.sql"
        parts = sql_file.stem.split("_", 1)
        if not parts[0].isdigit():
            continue
        version = parts[0]
        migrations.append((version, sql_file.name, sql_file))

    return migrations


async def get_migration_status(
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return status of all migrations (applied or pending).

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.

    Returns:
        List of dicts with keys: version, filename, status, applied_at.
    """
    resolved = get_db_path(db_path)
    conn = await aiosqlite.connect(str(resolved))
    conn.row_factory = aiosqlite.Row
    try:
        await _ensure_migrations_table(conn)
        applied = await _get_applied_versions(conn)

        # Get applied_at timestamps
        cursor = await conn.execute(
            "SELECT version, applied_at FROM schema_migrations"
        )
        rows = await cursor.fetchall()
        applied_at_map = {row["version"]: row["applied_at"] for row in rows}

        all_migrations = _discover_migrations()
        result = []
        for version, filename, _path in all_migrations:
            result.append({
                "version": version,
                "filename": filename,
                "status": "applied" if version in applied else "pending",
                "applied_at": applied_at_map.get(version),
            })
        return result
    finally:
        await conn.close()


async def run_migrations(
    db_path: str | Path | None = None,
    verbose: bool = True,
) -> list[str]:
    """Apply all pending migrations in order.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        verbose: Print progress to stdout.

    Returns:
        List of applied migration filenames.
    """
    resolved = get_db_path(db_path)
    conn = await aiosqlite.connect(str(resolved))
    conn.row_factory = aiosqlite.Row

    try:
        # Enable WAL mode and foreign keys
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")

        await _ensure_migrations_table(conn)
        applied = await _get_applied_versions(conn)
        all_migrations = _discover_migrations()

        pending = [
            (v, f, p) for v, f, p in all_migrations if v not in applied
        ]

        if not pending:
            if verbose:
                print("No pending migrations.")
            return []

        if verbose:
            print(f"Found {len(pending)} pending migration(s).")

        applied_filenames = []
        for version, filename, path in pending:
            if verbose:
                print(f"  Applying {filename}...")

            sql = path.read_text()
            # executescript handles multi-statement SQL including triggers
            # (which contain semicolons inside BEGIN...END blocks).
            # It implicitly commits any open transaction before running.
            try:
                await conn.executescript(sql)
                await conn.commit()
            except sqlite3.OperationalError as e:
                # Tolerate "duplicate column name" — means the column was
                # already added outside the migration runner (e.g. by a
                # partially-applied migration where executescript committed
                # but the schema_migrations INSERT failed).
                if "duplicate column name" not in str(e):
                    raise
                if verbose:
                    print(f"    Warning: {e} — column already exists, marking migration as applied.")

            await conn.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES (?, ?)",
                (version, filename),
            )
            await conn.commit()
            applied_filenames.append(filename)

            if verbose:
                print(f"    Done.")

        if verbose:
            print(f"Applied {len(applied_filenames)} migration(s).")

        return applied_filenames

    finally:
        await conn.close()


async def _main() -> None:
    """CLI entry point."""
    show_status = "--status" in sys.argv

    if show_status:
        statuses = await get_migration_status()
        if not statuses:
            print("No migrations found.")
            return
        print(f"{'Version':<10} {'Filename':<40} {'Status':<10} {'Applied At'}")
        print("-" * 80)
        for m in statuses:
            print(
                f"{m['version']:<10} {m['filename']:<40} "
                f"{m['status']:<10} {m['applied_at'] or ''}"
            )
    else:
        applied = await run_migrations()
        if not applied:
            print("Database is up to date.")


if __name__ == "__main__":
    asyncio.run(_main())
