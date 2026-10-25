"""The three AI-generated outputs: building them from a pipeline record, storing them, and presenting them.

PRESENTATION IS FILTERED ON THE SERVER. Every field that goes into a response is added only after
``permissions.can`` says the viewer's role may see it, so a role's response simply does not contain the other
roles' fields (nothing is hidden by CSS):

* patient    -> patient_summary only
* child      -> child_explanation only
* caregiver / creator -> all three, the source note title, review flags, checklist progress, history

Source text is not copied here: ``flags`` holds counts, retention numbers and the model's own flagged tokens,
never the note text.
"""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

from app import permissions as perm, safety
from app.context import Ctx
from app.db import iso, transaction
from app.errors import NotAllowed, NotFound

DISCLAIMER = "Research prototype. Not medical advice. Check doses and instructions with the care team."


def _num(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def build_output(record: dict[str, Any], source_text: str) -> dict[str, Any]:
    """Turn a pipeline record into the columns of an ``outputs`` row (pure; runs the child safety gate)."""
    from src.evaluator import entity_retention, unsupported_meds, unsupported_numbers  # research code, called not edited

    meta = record.get("metadata", {})
    entities = record.get("entities", [])
    checklist = [str(i) for i in record["caregiver_checklist"]]
    texts = {"patient_summary": record["patient_summary"], "caregiver_checklist": "\n".join(checklist)}

    retention, unsupported = {}, {}
    for persona, text in texts.items():
        ret = entity_retention(entities, text)
        retention[persona] = {"overall": _num(ret["overall"]), "n_required": ret["n"]}
        unsupported[persona] = {
            "medications": list(unsupported_meds(text, source_text, entities)["unsupported"]),
            "numbers": list(unsupported_numbers(text, source_text, entities)["unsupported"]),
        }

    reasons = safety.check_child_text(record["child_explanation"], safety.medication_names(entities, record.get("regimens", [])))
    withheld = bool(reasons)
    child_text = safety.SAFE_CHILD_MESSAGE if withheld else record["child_explanation"]

    flags = {
        "retries": meta.get("retries", {}),
        "fallback_used": meta.get("fallback_used", {}),
        "truncated": meta.get("truncated", {}),
        "redacted_dosages": meta.get("redacted_dosages", {}),
        "missing_first_attempt_count": {k: len(v) for k, v in meta.get("missing_first_attempt", {}).items()},
        "appended_by_fallback": meta.get("missing_after_retries", {}),
        "retention": retention,
        "unsupported": unsupported,
        "validation_errors": meta.get("validation_errors", []),
        "child_gate": {"fired": withheld, "reasons": reasons},
        "model_id": meta.get("model_id"),
        "model_hash": meta.get("model_hash"),
        "pipeline_created_at": meta.get("created_at"),
    }
    return {"patient_summary": record["patient_summary"], "caregiver_checklist": checklist,
            "child_explanation": child_text, "child_withheld": withheld, "flags": flags}


def store_output(conn: sqlite3.Connection, ctx: Ctx, note_id: int, profile_id: int, built: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO outputs(note_id, profile_id, patient_summary, caregiver_checklist, child_explanation, child_withheld, "
        "flags, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (note_id, profile_id, built["patient_summary"], json.dumps(built["caregiver_checklist"]), built["child_explanation"],
         1 if built["child_withheld"] else 0, json.dumps(built["flags"]), iso(ctx.now())))


# ------------------------------------------------------------------------------------ presentation
def _require(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, action: str) -> None:
    if not perm.can(conn, actor, profile, action):
        raise NotAllowed()


def generation_state(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> dict[str, Any]:
    """State of the most recent note: none | queued | running | done | failed. Every active member may see it.

    Only creators and caregivers also get the note title and the (safe) failure message.
    """
    _require(conn, actor, profile, perm.VIEW_DASHBOARD)
    n = conn.execute("SELECT id, title, status, error_message, created_at, finished_at FROM notes WHERE profile_id = ? "
                     "ORDER BY id DESC LIMIT 1", (profile["id"],)).fetchone()
    if n is None:
        return {"state": "none"}
    out: dict[str, Any] = {"state": n["status"], "created_at": n["created_at"]}
    if n["finished_at"]:
        out["finished_at"] = n["finished_at"]
    if perm.can(conn, actor, profile, perm.VIEW_SOURCE_NOTE):
        out["note"] = {"id": n["id"], "title": n["title"]}
        if n["status"] == "failed":
            out["message"] = n["error_message"]
    return out


def _ticks(conn: sqlite3.Connection, note_id: int) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "SELECT t.item_index, t.ticked_at, u.display_name FROM checklist_ticks t LEFT JOIN users u ON u.id = t.ticked_by "
        "WHERE t.note_id = ?", (note_id,)).fetchall()
    return {r["item_index"]: {"ticked_by": r["display_name"] or "A former member", "ticked_at": r["ticked_at"]} for r in rows}


def _present(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, row: sqlite3.Row) -> dict[str, Any]:
    data: dict[str, Any] = {"available": True, "output_id": row["id"], "updated_at": row["created_at"], "disclaimer": DISCLAIMER}
    if perm.can(conn, actor, profile, perm.VIEW_PATIENT_SUMMARY):
        data["patient_summary"] = row["patient_summary"]
    if perm.can(conn, actor, profile, perm.VIEW_CHILD_EXPLANATION):
        data["child_explanation"] = row["child_explanation"]
    if perm.can(conn, actor, profile, perm.VIEW_CAREGIVER_CHECKLIST):
        items = json.loads(row["caregiver_checklist"])
        ticks = _ticks(conn, row["note_id"]) if perm.can(conn, actor, profile, perm.VIEW_CHECKLIST_PROGRESS) else {}
        data["caregiver_checklist"] = [{"index": i, "text": t, "ticked": i in ticks, **ticks.get(i, {})} for i, t in enumerate(items)]
        data["checklist_progress"] = {"done": len(ticks), "total": len(items)}
    if perm.can(conn, actor, profile, perm.VIEW_SOURCE_NOTE):
        data["note"] = {"id": row["note_id"], "title": row["title"]}
    if perm.can(conn, actor, profile, perm.VIEW_FLAGS):
        data["flags"] = json.loads(row["flags"])
        data["child_withheld"] = bool(row["child_withheld"])
    return data


_SELECT = ("SELECT o.*, n.title AS title FROM outputs o JOIN notes n ON n.id = o.note_id WHERE o.profile_id = ? ")


def latest_outputs(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> dict[str, Any]:
    """The newest finished outputs the viewer may see, plus the generation state (for 'being prepared' banners)."""
    _require(conn, actor, profile, perm.VIEW_DASHBOARD)
    row = conn.execute(_SELECT + "ORDER BY o.id DESC LIMIT 1", (profile["id"],)).fetchone()
    gen = generation_state(conn, actor, profile)
    if row is None:
        return {"available": False, "generation": gen, "disclaimer": DISCLAIMER}
    data = _present(conn, actor, profile, row)
    data["generation"] = gen
    return data


def outputs_for_note(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, note_id: int) -> dict[str, Any]:
    """An earlier note's outputs (history). Creators and caregivers only."""
    _require(conn, actor, profile, perm.VIEW_OUTPUT_HISTORY)
    row = conn.execute(_SELECT + "AND o.note_id = ?", (profile["id"], note_id)).fetchone()
    if row is None:
        raise NotFound()
    return _present(conn, actor, profile, row)


def history(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> list[dict[str, Any]]:
    _require(conn, actor, profile, perm.VIEW_OUTPUT_HISTORY)
    rows = conn.execute(
        "SELECT o.id AS output_id, o.note_id, o.created_at AS updated_at, o.child_withheld, n.title FROM outputs o "
        "JOIN notes n ON n.id = o.note_id WHERE o.profile_id = ? ORDER BY o.id DESC", (profile["id"],)).fetchall()
    return [{**dict(r), "child_withheld": bool(r["child_withheld"])} for r in rows]


# ---------------------------------------------------------------------------------------- checklist
def set_tick(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, note_id: int, index: int,
             ticked: bool) -> dict[str, Any]:
    """Tick (or untick) one checklist item. Records who ticked it and when. Creators and caregivers only."""
    _require(conn, actor, profile, perm.TICK_CHECKLIST)
    row = conn.execute("SELECT caregiver_checklist FROM outputs WHERE note_id = ? AND profile_id = ?",
                       (note_id, profile["id"])).fetchone()
    if row is None:
        raise NotFound()
    items = json.loads(row["caregiver_checklist"])
    if not isinstance(index, int) or not 0 <= index < len(items):
        raise NotFound()
    with transaction(conn):
        if ticked:
            conn.execute(
                "INSERT INTO checklist_ticks(profile_id, note_id, item_index, ticked_by, ticked_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(note_id, item_index) DO UPDATE SET ticked_by = excluded.ticked_by, ticked_at = excluded.ticked_at",
                (profile["id"], note_id, index, actor["id"], iso(ctx.now())))
        else:
            conn.execute("DELETE FROM checklist_ticks WHERE note_id = ? AND item_index = ?", (note_id, index))
    t = _ticks(conn, note_id)
    return {"index": index, "ticked": index in t, "done": len(t), "total": len(items), **t.get(index, {})}
