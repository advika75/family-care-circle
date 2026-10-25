"""SQLite access: one connection per request/thread, foreign keys on, explicit transactions."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.migrations import MIGRATIONS


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection in autocommit mode; use :func:`transaction` for atomic multi-statement changes.

    A new database file is created readable and writable by its owner only (0600) and its new parent directory
    0700; SQLite gives the -wal/-shm side files the same permissions. (This is access control, not encryption.)
    """
    if str(path) != ":memory:":
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not p.exists():
            os.close(os.open(p, os.O_CREAT | os.O_RDWR, 0o600))
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, or ROLLBACK if the block raises. Not re-entrant."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply any migrations that have not run yet. Returns the versions applied."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for version, sql in MIGRATIONS:
        if version in done:
            continue
        # executescript commits any open transaction first, so the BEGIN/COMMIT live inside the script.
        conn.executescript("BEGIN;\n" + sql + f"\nINSERT INTO schema_migrations(version, applied_at) VALUES ({int(version)}, "
                           f"'{iso(datetime.now(timezone.utc))}');\nCOMMIT;")
        applied.append(version)
    return applied


def iso(dt: datetime) -> str:
    """UTC timestamp string with second precision."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
