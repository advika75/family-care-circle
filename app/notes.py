"""Clinical notes belonging to a care circle (pasted text or a .txt upload only).

Notes are stored in the ``notes`` table, which is the ONLY place the source text lives (outputs never copy it).
Deleting a note deletes its outputs and checklist ticks (foreign-key cascade).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

from app import permissions as perm
from app.accounts import clean_name
from app.config import Settings
from app.context import Ctx
from app.db import iso, transaction
from app.errors import NotAllowed, NotFound, QueueFull, ValidationFailed

log = logging.getLogger("app.notes")  # note text is never logged

_BAD_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # tabs and newlines are fine
MAX_TITLE = 80


def clean_note_text(text: str, settings: Settings) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValidationFailed({"text": "Please paste the note text or upload a .txt file."})
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if _BAD_CONTROL.search(text):
        raise ValidationFailed({"text": "That text contains characters that are not allowed. Use plain text only."})
    if len(text) > settings.max_note_chars:
        raise ValidationFailed({"text": f"This note is too long for the local model ({len(text):,} characters). Shorten it to about {settings.max_note_chars:,} characters."})
    return text


def decode_upload(filename: str | None, data: bytes, settings: Settings) -> str:
    """Turn an uploaded file into note text, or raise ValidationFailed with a clear message."""
    if not filename or not filename.lower().endswith(".txt"):
        raise ValidationFailed({"file": "That file is not a .txt file. Paste the text, or upload a plain-text (.txt) file."})
    if len(data) > settings.max_note_chars * 4:        # UTF-8 uses at most 4 bytes per character
        raise ValidationFailed({"file": f"That file is too large for the local model. Shorten the note to about {settings.max_note_chars:,} characters."})
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed({"file": "We could not read that file as UTF-8 text. Save it as plain text and try again."}) from None
    return clean_note_text(text, settings)


def add_note(conn: sqlite3.Connection, ctx: Ctx, runner: Any, actor: sqlite3.Row, profile: sqlite3.Row, *,
             title: str | None, text: str) -> sqlite3.Row:
    """Store a note (status ``queued``) and hand it to the job runner. Creator always; caregiver only with permission."""
    if not perm.can(conn, actor, profile, perm.ADD_NOTE):
        raise NotAllowed()
    errors: dict[str, str] = {}
    try:
        text = clean_note_text(text, ctx.settings)
    except ValidationFailed as exc:
        errors.update(exc.errors)
    title = (title or "").strip()
    if title:
        try:
            title = clean_name(title, "title", MAX_TITLE)
        except ValidationFailed as exc:
            errors.update(exc.errors)
    if errors:
        raise ValidationFailed(errors)
    with transaction(conn):
        # Queue caps (F-03): the single worker is shared by every care circle, so nobody may fill it.
        total_waiting = conn.execute("SELECT COUNT(*) FROM notes WHERE status IN ('queued','running')").fetchone()[0]
        if total_waiting >= ctx.settings.max_pending_total:
            raise QueueFull("The app is busy preparing other notes right now. Please try again in a few minutes.")
        circle_waiting = conn.execute(
            "SELECT COUNT(*) FROM notes WHERE profile_id = ? AND status IN ('queued','running')", (profile["id"],)).fetchone()[0]
        if circle_waiting >= ctx.settings.max_pending_per_circle:
            raise QueueFull()
        if not title:
            n = conn.execute("SELECT COUNT(*) FROM notes WHERE profile_id = ?", (profile["id"],)).fetchone()[0]
            title = f"Note {n + 1}"
        cur = conn.execute(
            "INSERT INTO notes(profile_id, title, text, added_by, status, created_at) VALUES (?,?,?,?, 'queued', ?)",
            (profile["id"], title, text, actor["id"], iso(ctx.now())))
    log.info("note added note_id=%s profile_id=%s by user_id=%s chars=%d", cur.lastrowid, profile["id"], actor["id"], len(text))
    if runner is not None:
        runner.enqueue(cur.lastrowid)
    return conn.execute("SELECT id, profile_id, title, added_by, status, created_at FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()


def delete_note(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, note_id: int) -> None:
    if not perm.can(conn, actor, profile, perm.DELETE_NOTE):
        raise NotAllowed()
    with transaction(conn):
        cur = conn.execute("DELETE FROM notes WHERE id = ? AND profile_id = ?", (note_id, profile["id"]))
    if cur.rowcount != 1:
        raise NotFound()
    log.info("note deleted note_id=%s profile_id=%s by user_id=%s", note_id, profile["id"], actor["id"])


def list_notes(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> list[dict[str, Any]]:
    """Note metadata (never the text) for creators and caregivers."""
    if not perm.can(conn, actor, profile, perm.VIEW_OUTPUT_HISTORY):
        raise NotAllowed()
    rows = conn.execute(
        "SELECT n.id, n.title, n.status, n.error_message, n.created_at, n.finished_at, u.display_name AS added_by_name "
        "FROM notes n LEFT JOIN users u ON u.id = n.added_by WHERE n.profile_id = ? ORDER BY n.id DESC",
        (profile["id"],)).fetchall()
    return [{**dict(r), "added_by_name": r["added_by_name"] or "A former member"} for r in rows]


def get_note_source(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, note_id: int) -> dict[str, Any]:
    if not perm.can(conn, actor, profile, perm.VIEW_SOURCE_NOTE):
        raise NotAllowed()
    r = conn.execute("SELECT id, title, text, created_at FROM notes WHERE id = ? AND profile_id = ?",
                     (note_id, profile["id"])).fetchone()
    if r is None:
        raise NotFound()
    return dict(r)


def resolve_submission(settings: Settings, *, title: str | None, text: str | None, filename: str | None,
                       data: bytes | None) -> tuple[str, str]:
    """Pasted text OR a .txt upload (never both) -> (title, text). Used by both the pages and the JSON API."""
    title, text = (title or "").strip(), text or ""
    if filename:
        if text.strip():
            raise ValidationFailed({"text": "Paste the text or upload a file, not both."})
        text = decode_upload(filename, data or b"", settings)
        title = title or filename.rsplit(".", 1)[0][:MAX_TITLE]
    return title, text
