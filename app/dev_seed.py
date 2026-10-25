"""SYNTHETIC DEMO DATA ONLY - for local development, never for real patient data.

Creates one demo care circle with four demo accounts (creator, caregiver, patient, child) and a couple of notes
taken from ``data/raw/`` (the project's synthetic note set), then runs the generation jobs with the configured
backend (``APP_BACKEND``, default ``mock``).

    APP_DB_PATH=/path/to/demo.sqlite3 python -m app.dev_seed        # or:  make app-seed

Passwords: set ``APP_SEED_PASSWORD`` (at least 12 characters) to use one password for every demo account;
otherwise a random password is generated per account. Passwords are printed ONCE, to this terminal, and are never
stored anywhere except as scrypt hashes in the database.

Safety: it refuses to run unless the database has no users at all, so it can never mix demo accounts into a
database that holds real accounts. Use a fresh ``APP_DB_PATH`` for demos.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import Callable, Mapping

from app import accounts, circle, notes, permissions as perm
from app.config import REPO_ROOT, Settings
from app.context import Ctx
from app.db import connect, migrate
from app.errors import ValidationFailed
from app.jobs import JobRunner

DEMO_ROLES = ("creator", "caregiver", "patient", "child")
DEMO_NAMES = {"creator": "Demo Creator", "caregiver": "Demo Caregiver", "patient": "Demo Patient Member", "child": "Demo Child"}
RAW_DIR = REPO_ROOT / "data" / "raw"


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Create SYNTHETIC demo accounts and notes (local development only).")
    parser.add_argument("--notes", type=int, default=2, help="how many synthetic notes from data/raw to add (default 2)")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env

    settings = Settings.from_env(dict(env))
    shared = env.get("APP_SEED_PASSWORD")
    if shared is not None and len(shared) < settings.min_password_length:
        out(f"APP_SEED_PASSWORD must be at least {settings.min_password_length} characters.")
        return 2
    raw_notes = sorted(RAW_DIR.glob("*.txt"))[: max(args.notes, 0)]
    if args.notes > 0 and not raw_notes:
        out(f"No synthetic notes found in {RAW_DIR}.")
        return 2

    conn = connect(settings.db_path)
    try:
        migrate(conn)
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing:
            out(f"Refusing to seed: {settings.db_path} already has {existing} user(s). "
                "Demo seeding only runs on an empty database. Point APP_DB_PATH at a fresh file.")
            return 1
        ctx = Ctx(settings=settings)
        passwords: dict[str, str] = {}
        users = {}
        try:
            for role in DEMO_ROLES:
                passwords[role] = shared or secrets.token_urlsafe(12)
                users[role] = accounts.signup(conn, ctx, email=f"demo-{role}@example.test", display_name=DEMO_NAMES[role],
                                              password=passwords[role])
            profile = circle.create_profile(conn, ctx, users["creator"], display_name="Demo Patient (synthetic)",
                                            preferred_name="Demo Grandma", relationship_label="Daughter",
                                            care_notes="Synthetic demo profile. Not a real person.")
            for role in DEMO_ROLES[1:]:
                _, code = circle.create_invitation(conn, ctx, users["creator"], profile, role=role)
                m = circle.join(conn, ctx, users[role], patient_id=profile["patient_id"], code=code,
                                relationship_label="Other relative")
                circle.approve_member(conn, ctx, users["creator"], profile, m["id"])
                if role == "caregiver":
                    circle.set_can_add_notes(conn, ctx, users["creator"], profile, m["id"], True)
        except ValidationFailed as exc:
            out("Could not create the demo accounts: " + "; ".join(exc.errors.values()))
            return 2

        runner = JobRunner(settings, ctx)
        for path in raw_notes:
            notes.add_note(conn, ctx, runner, users["creator"], profile, title=path.stem.replace("_", " ").title(),
                           text=path.read_text(encoding="utf-8"))
        runner.drain()
        states = [r[0] for r in conn.execute("SELECT status FROM notes ORDER BY id")]
    finally:
        conn.close()

    out("SYNTHETIC DEMO DATA - not real people, not real patient data.")
    out(f"Database : {settings.db_path}")
    out(f"Backend  : {settings.backend}")
    out(f"Patient ID: {profile['patient_id']}   (an identifier only, not a password)")
    out(f"Notes    : {len(states)} added from data/raw, states: {', '.join(states) or 'none'}")
    out("")
    out("Demo accounts (passwords are shown ONCE and are not stored anywhere in readable form):")
    for role in DEMO_ROLES:
        out(f"  {role:<10} demo-{role}@example.test   password: {passwords[role]}")
    out("")
    out("Start the app with:  make app-run   (same APP_DB_PATH), then open http://127.0.0.1:8000/login")
    return 0


if __name__ == "__main__":
    sys.exit(main())
