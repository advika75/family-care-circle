"""Schema migrations, applied in order and recorded in ``schema_migrations``.

All SQL is static; user data only ever reaches the database through bound parameters.
Timestamps are ISO-8601 UTC strings (``YYYY-MM-DDTHH:MM:SSZ``), which sort chronologically as text.
"""

from __future__ import annotations

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY,
    token_hash  TEXT NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

CREATE TABLE profiles (
    id             INTEGER PRIMARY KEY,
    patient_id     TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL,
    preferred_name TEXT,
    year_of_birth  INTEGER,
    care_notes     TEXT,
    created_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE memberships (
    id                 INTEGER PRIMARY KEY,
    profile_id         INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role               TEXT NOT NULL CHECK (role IN ('creator','caregiver','patient','child')),
    status             TEXT NOT NULL CHECK (status IN ('pending','active','revoked')),
    can_add_notes      INTEGER NOT NULL DEFAULT 0 CHECK (can_add_notes IN (0,1)),
    relationship_label TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    UNIQUE (profile_id, user_id),
    CHECK (can_add_notes = 0 OR role IN ('creator','caregiver')),
    CHECK (role != 'creator' OR (status = 'active' AND can_add_notes = 1))
);
CREATE UNIQUE INDEX idx_one_creator_per_profile ON memberships(profile_id) WHERE role = 'creator';
CREATE INDEX idx_memberships_user ON memberships(user_id);

CREATE TABLE invitations (
    id          INTEGER PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('caregiver','patient','child')),
    code_hash   TEXT NOT NULL UNIQUE,
    email_label TEXT,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    used_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    revoked_at  TEXT
);
CREATE INDEX idx_invitations_profile ON invitations(profile_id);
"""),
    (2, """
CREATE TABLE notes (
    id            INTEGER PRIMARY KEY,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    text          TEXT NOT NULL,
    added_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
    error_message TEXT,
    created_at    TEXT NOT NULL,
    started_at    TEXT,
    finished_at   TEXT
);
CREATE INDEX idx_notes_profile ON notes(profile_id, id);

CREATE TABLE outputs (
    id                  INTEGER PRIMARY KEY,
    note_id             INTEGER NOT NULL UNIQUE REFERENCES notes(id) ON DELETE CASCADE,
    profile_id          INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    patient_summary     TEXT NOT NULL,
    caregiver_checklist TEXT NOT NULL,
    child_explanation   TEXT NOT NULL,
    child_withheld      INTEGER NOT NULL DEFAULT 0 CHECK (child_withheld IN (0,1)),
    flags               TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
CREATE INDEX idx_outputs_profile ON outputs(profile_id, id);

CREATE TABLE checklist_ticks (
    id          INTEGER PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    note_id     INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    item_index  INTEGER NOT NULL CHECK (item_index >= 0),
    ticked_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ticked_at   TEXT NOT NULL,
    UNIQUE (note_id, item_index)
);
"""),
    (3, """
-- F-11: the invitation "email label" was never enforced; it is a private note for the inviter.
ALTER TABLE invitations RENAME COLUMN email_label TO note;
"""),
    (4, """
-- optional: the creator can pause new invitations for a circle (codes already issued stop working until resumed)
ALTER TABLE profiles ADD COLUMN invitations_paused INTEGER NOT NULL DEFAULT 0 CHECK (invitations_paused IN (0,1));
"""),
]
