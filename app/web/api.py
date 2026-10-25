"""JSON API (used by the pages' small scripts and by the tests). Every response is built by a service function
that filters by role on the server; this module adds no permission logic of its own beyond requiring a session."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app import circle, notes, outputs
from app.errors import ValidationFailed
from app.web.deps import circle_scope, get_db, require_csrf, require_user

router = APIRouter(prefix="/api")


def _scope(patient_id: str, user: sqlite3.Row = Depends(require_user), conn: sqlite3.Connection = Depends(get_db)):
    profile, membership = circle_scope(patient_id, user, conn)
    return user, profile, membership, conn


@router.get("/p/{patient_id}/outputs")
def get_outputs(scope=Depends(_scope)) -> dict[str, Any]:
    user, profile, _, conn = scope
    return outputs.latest_outputs(conn, user, profile)


@router.get("/p/{patient_id}/status")
def get_status(scope=Depends(_scope)) -> dict[str, Any]:
    user, profile, _, conn = scope
    return outputs.generation_state(conn, user, profile)


@router.get("/p/{patient_id}/history")
def get_history(scope=Depends(_scope)) -> list[dict[str, Any]]:
    user, profile, _, conn = scope
    return outputs.history(conn, user, profile)


@router.get("/p/{patient_id}/notes/{note_id}/outputs")
def get_note_outputs(note_id: int, scope=Depends(_scope)) -> dict[str, Any]:
    user, profile, _, conn = scope
    return outputs.outputs_for_note(conn, user, profile, note_id)


@router.get("/p/{patient_id}/notes")
def get_notes(scope=Depends(_scope)) -> list[dict[str, Any]]:
    user, profile, _, conn = scope
    return notes.list_notes(conn, user, profile)


@router.get("/p/{patient_id}/notes/{note_id}/source")
def get_source(note_id: int, scope=Depends(_scope)) -> dict[str, Any]:
    user, profile, _, conn = scope
    return notes.get_note_source(conn, user, profile, note_id)


@router.get("/p/{patient_id}/circle")
def get_circle(scope=Depends(_scope)) -> list[dict[str, Any]]:
    user, profile, _, conn = scope
    return circle.list_members(conn, user, profile)


@router.post("/p/{patient_id}/notes", status_code=201)
async def post_note(request: Request, patient_id: str, title: str = Form(""), text: str = Form(""),
                    file: UploadFile | None = File(None), user: sqlite3.Row = Depends(require_csrf),
                    conn: sqlite3.Connection = Depends(get_db)) -> JSONResponse:
    profile, _ = circle_scope(patient_id, user, conn)
    settings = request.app.state.settings
    data = await file.read(settings.max_note_chars * 4 + 1) if file is not None and file.filename else None
    title, text = notes.resolve_submission(settings, title=title, text=text, filename=file.filename if file is not None else None, data=data)
    note = notes.add_note(conn, request.app.state.ctx, request.app.state.runner, user, profile, title=title, text=text)
    return JSONResponse({"id": note["id"], "title": note["title"], "status": note["status"]}, status_code=201)


@router.post("/p/{patient_id}/notes/{note_id}/delete")
def post_delete_note(note_id: int, patient_id: str, user: sqlite3.Row = Depends(require_csrf),
                     conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    profile, _ = circle_scope(patient_id, user, conn)
    notes.delete_note(conn, user, profile, note_id)
    return {"deleted": note_id}


@router.post("/p/{patient_id}/checklist/{note_id}/{index}")
def post_tick(request: Request, note_id: int, index: int, patient_id: str, ticked: str = Form("1"),
              user: sqlite3.Row = Depends(require_csrf), conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    profile, _ = circle_scope(patient_id, user, conn)
    return outputs.set_tick(conn, request.app.state.ctx, user, profile, note_id, index, ticked == "1")
