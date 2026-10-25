"""The synthetic demo seeder: what it creates, what it refuses to do, and that secrets are not kept."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app import dev_seed, permissions as P
from app.db import connect
from conftest import Site

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def run(tmp_path, **extra):
    env = {"APP_DB_PATH": str(tmp_path / "demo.sqlite3"), "APP_BACKEND": "mock", **extra}
    lines: list[str] = []
    code = dev_seed.main([], env=env, out=lines.append)
    return code, "\n".join(lines), env


def test_seeds_four_demo_accounts_one_circle_and_synthetic_notes(tmp_path):
    code, output, env = run(tmp_path)
    assert code == 0 and "SYNTHETIC DEMO DATA" in output
    conn = connect(env["APP_DB_PATH"])
    emails = sorted(r[0] for r in conn.execute("SELECT email FROM users"))
    assert emails == [f"demo-{r}@example.test" for r in sorted(dev_seed.DEMO_ROLES)]
    roles = {r["role"]: (r["status"], r["can_add_notes"]) for r in conn.execute("SELECT role, status, can_add_notes FROM memberships")}
    assert roles == {"creator": ("active", 1), "caregiver": ("active", 1), "patient": ("active", 0), "child": ("active", 0)}
    texts = sorted(r[0] for r in conn.execute("SELECT text FROM notes"))
    expected = sorted(p.read_text(encoding="utf-8").replace("\r\n", "\n").strip() for p in sorted(RAW.glob("*.txt"))[:2])
    assert texts == expected                                              # exactly the project's synthetic notes
    assert [r[0] for r in conn.execute("SELECT status FROM notes")] == ["done", "done"]
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 2
    assert re.search(r"Patient ID: FCC-[A-Z0-9]{4}-[A-Z0-9]{4}", output)


def test_every_printed_password_works_and_is_printed_exactly_once_and_stored_only_hashed(tmp_path):
    code, output, env = run(tmp_path)
    pw = dict(re.findall(r"^\s+(\w+)\s+demo-\w+@example\.test\s+password: (\S+)$", output, re.M))
    assert set(pw) == set(dev_seed.DEMO_ROLES) and len(set(pw.values())) == 4 and all(len(v) >= 12 for v in pw.values())
    for password in pw.values():
        assert output.count(password) == 1                                # printed once
    conn = connect(env["APP_DB_PATH"])
    dump = " ".join(repr(tuple(r)) for t in ("users", "sessions", "profiles", "notes", "outputs") for r in conn.execute(f"SELECT * FROM {t}"))
    assert all(p not in dump for p in pw.values()) and dump.count("scrypt$") == 4
    from app.config import Settings
    from app.context import Ctx
    from app.jobs import JobRunner
    from app.web.main import create_app
    settings = Settings.from_env(env)
    app = create_app(settings, ctx=Ctx(settings), runner=JobRunner(settings), start_worker=False)
    for role, password in pw.items():
        s = Site(app)
        r = s.login(f"demo-{role}@example.test", password)
        assert r.status_code == 303, role


def test_a_shared_password_can_come_from_the_environment_and_is_length_checked(tmp_path):
    code, output, _ = run(tmp_path, APP_SEED_PASSWORD="a shared demo passphrase")
    assert code == 0 and output.count("a shared demo passphrase") == 4
    code, output, _ = run(tmp_path / "other", APP_SEED_PASSWORD="short")
    assert code == 2 and "at least 12" in output and not (tmp_path / "other" / "demo.sqlite3").exists()


def test_it_refuses_to_run_twice_or_on_a_database_with_real_accounts(tmp_path):
    code, _, env = run(tmp_path)
    before = connect(env["APP_DB_PATH"]).execute("SELECT COUNT(*) FROM users").fetchone()[0]
    code2, output, _ = run(tmp_path)
    assert code2 == 1 and "Refusing to seed" in output and "empty database" in output
    assert connect(env["APP_DB_PATH"]).execute("SELECT COUNT(*) FROM users").fetchone()[0] == before == 4
    # a database that already has a "real" account is protected too
    real = tmp_path / "real" / "db.sqlite3"
    from app import accounts
    from app.config import Settings
    from app.context import Ctx
    from app.db import migrate
    c = connect(real); migrate(c)
    accounts.signup(c, Ctx(Settings(scrypt_n=16)), email="someone@real-domain.org", display_name="Real Person", password="a real password here")
    lines: list[str] = []
    assert dev_seed.main([], env={"APP_DB_PATH": str(real)}, out=lines.append) == 1
    assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_it_never_modifies_the_synthetic_source_data(tmp_path):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.glob("*")}
    run(tmp_path)
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.glob("*")} == before


def test_notes_flag_controls_how_many_notes_are_added(tmp_path):
    env = {"APP_DB_PATH": str(tmp_path / "d.sqlite3")}
    assert dev_seed.main(["--notes", "0"], env=env, out=lambda s: None) == 0
    assert connect(env["APP_DB_PATH"]).execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_the_script_is_clearly_labelled_and_makefile_has_the_target():
    assert "SYNTHETIC DEMO DATA ONLY" in dev_seed.__doc__ and "never for real patient data" in dev_seed.__doc__
    assert "app-seed:" in (Path(__file__).resolve().parents[2] / "Makefile").read_text()
