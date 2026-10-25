"""Settings from the environment, migrations and transactions."""

from __future__ import annotations

import sqlite3

import pytest

from app.config import Settings
from app.db import connect, iso, migrate, parse_iso, transaction


def test_settings_defaults_are_safe():
    s = Settings.from_env({})
    assert s.backend == "mock" and s.https is False and s.session_ttl_hours == 168 and s.invite_ttl_days == 7
    assert s.scrypt_n >= 2 ** 14 and s.min_password_length == 12 and s.max_note_chars == 6_000
    assert s.db_path.name == "familycare.sqlite3" and len(s.secret_key) >= 32


def test_settings_read_the_environment():
    s = Settings.from_env({"APP_BACKEND": "llama_cpp", "APP_HTTPS": "1", "APP_DB_PATH": "/tmp/x.db",
                           "APP_SECRET_KEY": "abc", "APP_SESSION_TTL_HOURS": "2", "APP_INVITE_TTL_DAYS": "3"})
    assert (s.backend, s.https, str(s.db_path), s.secret_key, s.session_ttl_hours, s.invite_ttl_days) == (
        "llama_cpp", True, "/tmp/x.db", b"abc", 2, 3)


def test_unknown_backend_is_refused():
    with pytest.raises(ValueError):
        Settings.from_env({"APP_BACKEND": "openai"})


def test_each_process_gets_a_fresh_random_secret_when_none_is_configured():
    assert Settings.from_env({}).secret_key != Settings.from_env({}).secret_key


def test_migrate_is_idempotent_and_records_versions(settings):
    from app.migrations import MIGRATIONS
    versions = [v for v, _ in MIGRATIONS]
    assert versions == sorted(set(versions))                        # strictly increasing, no duplicates
    c = connect(settings.db_path)
    assert migrate(c) == versions and migrate(c) == []
    assert [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version")] == versions


def test_foreign_keys_and_wal_are_on(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES ('h',999,'t','t')")


def test_transaction_commits_and_rolls_back(conn):
    with transaction(conn):
        conn.execute("INSERT INTO users(email,display_name,password_hash,created_at) VALUES ('a@x.test','A','h','t')")
    with pytest.raises(RuntimeError):
        with transaction(conn):
            conn.execute("INSERT INTO users(email,display_name,password_hash,created_at) VALUES ('b@x.test','B','h','t')")
            raise RuntimeError("boom")
    assert [r[0] for r in conn.execute("SELECT email FROM users")] == ["a@x.test"]


def test_email_uniqueness_is_case_insensitive_in_the_database(conn):
    conn.execute("INSERT INTO users(email,display_name,password_hash,created_at) VALUES ('a@x.test','A','h','t')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users(email,display_name,password_hash,created_at) VALUES ('A@X.TEST','A','h','t')")


def test_sql_injection_strings_are_data_not_code(conn, ctx, world):
    from app import accounts
    evil = "x'); DROP TABLE users; --"
    u = accounts.signup(conn, ctx, email="inj@example.test", display_name=evil, password="a long enough password")
    assert u["display_name"] == evil
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    for token in (evil, "' OR '1'='1"):
        assert accounts.resolve_session(conn, ctx, token) is None


def test_timestamps_round_trip():
    from datetime import datetime, timezone
    dt = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
    assert iso(dt) == "2026-03-04T05:06:07Z" and parse_iso(iso(dt)) == dt
