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
import re
import sqlite3
from typing import Any

from app import dose_check, permissions as perm, safety
from app.clinical_safety import unsupported_claims, unsupported_recovery_sentence
from app.context import Ctx
from app.db import iso, transaction
from app.errors import NotAllowed, NotFound

DISCLAIMER = "Generated text may be inaccurate. Not a substitute for professional medical advice. Check doses and instructions with the care team."
MISSING_PATIENT_MESSAGE = "We could not prepare this summary. Please ask your care team to review the note with you."
MISSING_CAREGIVER_ITEM = "Review this note's care steps with the care team."
MISSING_OUTPUT_WARNING = "Some saved text was unavailable, so a general message is shown. Ask the care team to review the note."
UNCONFIRMED_OUTPUT_WARNING = "Some generated details could not be confirmed. Please review the note with the care team."
PATIENT_REVIEW_FALLBACK = "Some details in this summary could not be checked against the note. Please ask the care team to review it."
CAREGIVER_REVIEW_FALLBACK = "Ask the care team to review this note before acting on these steps."
# Shown instead of the research retry loop's fallback text, which can append mislabelled "missing" facts.
PATIENT_UNAVAILABLE_MESSAGE = "Summary unavailable. Please ask your care team to go over the visit notes with you."
DOSE_MISMATCH_WARNING = "A detail was removed because it did not match the note. Please check doses with your care team."
_APPENDIX_LINE = re.compile(r"^Confirm with the care team: (.+) \((?:medication|dosage|frequency|duration)\)\.?$", re.I)
PATIENT_REVIEW_WARNING = ("Some details in this summary could not be checked against the note. "
                          "Please go over it with your care team.")
PATIENT_UNAVAILABLE_WARNING = ("This summary could not be prepared from the note, so no details are shown. "
                               "Please ask the care team to go over the visit notes with you.")
# Bump when a gate that decides what may be displayed changes. Outputs saved under an older (or no) version were not
# checked by the current gates, so they are shown with the safe child text and a review warning (see _present).
# 2: patient-failure message, child_as_patient / generic_fallback child checks, lab-measurement extractor filter.
# 3: dose-to-drug check, recovery sentences removed instead of whole texts, caregiver appendix rendered.
GATE_VERSION = 3
_CARE_ACTION = re.compile(
    r"^(?:give|check|watch(?:\s+for)?|call|schedule|review|confirm|record|track|ask|follow|monitor|keep|contact|return|seek|bring|write|read|share|prepare|make)\b",
    re.I,
)


def _disclaimer_for_backend(_flags: dict[str, Any]) -> str:
    """Keep API consumers on the same concise safety notice regardless of backend."""
    return DISCLAIMER


def _caregiver_fallback(source_text: str, regimens: Any) -> list[str]:
    """Build conservative adult review steps from extracted note facts or explicit note instructions."""
    items: list[str] = []
    if isinstance(regimens, list):
        for regimen in regimens:
            if not isinstance(regimen, dict):
                continue
            details = []
            medication = regimen.get("medication")
            if isinstance(medication, str) and medication.strip():
                details.append(medication.strip())
            for key in ("dosages", "frequencies", "durations"):
                values = regimen.get(key, [])
                if isinstance(values, list):
                    details.extend(value.strip() for value in values if isinstance(value, str) and value.strip())
            if details:
                items.append("Review the note's listed medicine plan with the care team: " + ", ".join(details) + ".")
    if items:
        return items

    # Use only complete source sentences that explicitly instruct an action. Never invent monitoring or follow-up.
    action = re.compile(r"\b(?:call|contact|return|follow[- ]?up|schedule|monitor|watch for|seek care|come back)\b", re.I)
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", source_text):
        sentence = sentence.strip()
        if sentence and action.search(sentence):
            items.append("Follow this instruction from the note: " + sentence)
        if len(items) == 5:
            break
    return items or ["Ask the care team to review the next steps stated in this note."]


def _patient_fallback_kind(text: Any, fallback_used: bool) -> tuple[bool, bool]:
    """(unavailable, needs_review) for a patient summary whose pipeline record says ``fallback_used``.

    The research loop sets ``fallback_used`` both when its generic empty-output text replaced the whole draft (all
    attempts empty, or the best one still named an unsupported medicine) and when it kept a real draft but appended
    still-missing facts or redacted a dose. Its metadata does not record which, so the text is compared with the
    research ``EMPTY_FALLBACK`` it starts with in the first case. Generic text is not a summary: show "unavailable".
    A real draft is shown with a review warning."""
    from src.postprocess import EMPTY_FALLBACK   # research constant, read not edited

    if not fallback_used:
        return False, False
    generic = isinstance(text, str) and text.strip().startswith(EMPTY_FALLBACK["patient_summary"])
    return generic, not generic


def _render_appendix(items: list[str], regimens: Any) -> tuple[list[str], int]:
    """Replace the research loop's "Confirm with the care team: 30 mg (dosage)" lines, which lose the medicine name.

    Each such fact is rendered from every extracted regimen that contains it ("Confirm with the care team:
    Prednisolone, 30 mg, daily, 4 more days."); a fact that matches no regimen is dropped. Returns the new list and
    the number of appended lines handled."""
    out, handled = [], 0
    for item in items:
        match = _APPENDIX_LINE.match(item.strip())
        if not match:
            out.append(item)
            continue
        handled += 1
        fact = match.group(1).strip().casefold()
        for reg in regimens if isinstance(regimens, list) else []:
            if not isinstance(reg, dict):
                continue
            values = [str(v).strip() for v in [reg.get("medication", ""), *reg.get("dosages", []),
                                               *reg.get("frequencies", []), *reg.get("durations", [])] if str(v).strip()]
            if fact in (v.casefold() for v in values):
                line = "Confirm with the care team: " + ", ".join(values) + "."
                if line not in out:
                    out.append(line)
    return out, handled


def _num(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def build_output(record: dict[str, Any], source_text: str) -> dict[str, Any]:
    """Turn a pipeline record into the columns of an ``outputs`` row (pure; runs the child safety gate)."""
    from src.evaluator import entity_retention, unsupported_meds, unsupported_numbers  # research code, called not edited

    patient_text = record.get("patient_summary")
    if not isinstance(patient_text, str) or not patient_text.strip():
        raise ValueError("Patient summary is empty or missing")
    meta = record.get("metadata", {})
    patient_unavailable, patient_needs_review = _patient_fallback_kind(
        patient_text, bool((meta.get("fallback_used") or {}).get("patient_summary")))
    entities = record.get("entities", [])
    dose_map = dose_check.note_dose_map(source_text, record.get("regimens", []))
    dose_mismatch: dict[str, list[dict[str, str]]] = {}
    recovery_removed: dict[str, int] = {}

    def remove_segment(persona: str, segment: str) -> bool:
        """Sentence- or line-level removal: an unsupported recovery claim, or a dose that is not that medicine's."""
        if unsupported_recovery_sentence(segment, source_text):
            recovery_removed[persona] = recovery_removed.get(persona, 0) + 1
            return True
        bad = dose_check.segment_mismatches(segment, dose_map, source_text, entities)
        if bad:
            dose_mismatch.setdefault(persona, []).extend(bad)
            return True
        return False

    if patient_unavailable:
        patient_text = PATIENT_UNAVAILABLE_MESSAGE
    else:
        kept, removed = dose_check.remove_sentences(patient_text, lambda s: remove_segment("patient_summary", s))
        if removed:
            patient_needs_review = bool(kept.strip())
            patient_unavailable = not patient_needs_review
            patient_text = kept if kept.strip() else PATIENT_UNAVAILABLE_MESSAGE
    patient_claims = unsupported_claims(patient_text, source_text, persona="patient")
    if patient_claims:
        patient_text = PATIENT_REVIEW_FALLBACK
    if recovery_removed.get("patient_summary"):
        patient_claims = ["unsupported_recovery", *patient_claims]
    checklist_raw = record.get("caregiver_checklist")
    appendix_rendered = 0
    if isinstance(checklist_raw, list) and all(isinstance(item, str) for item in checklist_raw):
        checklist_raw, appendix_rendered = _render_appendix(checklist_raw, record.get("regimens", []))
        before = len(checklist_raw)
        checklist_raw = [item for item in checklist_raw if not remove_segment("caregiver_checklist", item)]
        if before and not checklist_raw:
            checklist_raw = None                                  # everything removed: grounded fallback below
    checklist_text = "\n".join(item for item in checklist_raw if isinstance(item, str)) if isinstance(checklist_raw, list) else ""
    caregiver_claims = unsupported_claims(checklist_text, source_text, persona="caregiver")
    caregiver_fallback = False
    recorded_caregiver_claims = (["unsupported_recovery"] if recovery_removed.get("caregiver_checklist") else []) + caregiver_claims
    if (not isinstance(checklist_raw, list) or not checklist_raw
            or not all(isinstance(item, str) and item.strip() for item in checklist_raw)
            or not all(_CARE_ACTION.match(item.strip()) for item in checklist_raw)
            or " ".join(patient_text.casefold().split()) == " ".join(" ".join(checklist_raw).casefold().split())
            or caregiver_claims):
        checklist_raw = ([CAREGIVER_REVIEW_FALLBACK] if caregiver_claims else
                         _caregiver_fallback(source_text, record.get("regimens", [])))
        caregiver_fallback = True
    checklist = [i.strip() for i in checklist_raw]
    texts = {"patient_summary": patient_text, "caregiver_checklist": "\n".join(checklist)}

    retention, unsupported = {}, {}
    for persona, text in texts.items():
        ret = entity_retention(entities, text)
        retention[persona] = {"overall": _num(ret["overall"]), "n_required": ret["n"]}
        unsupported[persona] = {
            "medications": list(unsupported_meds(text, source_text, entities)["unsupported"]),
            "numbers": list(unsupported_numbers(text, source_text, entities)["unsupported"]),
        }

    child_draft = record.get("child_explanation")
    reasons = safety.check_child_text(child_draft or "", safety.medication_names(entities, record.get("regimens", [])),
                                      source_text)
    withheld = bool(reasons)
    child_text = safety.SAFE_CHILD_MESSAGE if withheld else child_draft

    flags = {
        "gate_version": GATE_VERSION,
        "backend": meta.get("backend"),
        "caregiver_fallback": caregiver_fallback,
        "patient_summary_unavailable": patient_unavailable,
        "patient_summary_needs_review": patient_needs_review,
        "dose_mismatch": dose_mismatch,
        "recovery_removed": recovery_removed,
        "caregiver_appendix_rendered": appendix_rendered,
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
        "clinical_claim_gate": {
            "fired": bool(patient_claims or recorded_caregiver_claims or safety.REASON_UNSUPPORTED_CLAIM in reasons),
            "patient": patient_claims,
            "caregiver": recorded_caregiver_claims,
            "child": (unsupported_claims(child_draft or "", source_text, persona="child")
                      if isinstance(child_draft, str) else []),
        },
        "model_id": meta.get("model_id"),
        "model_hash": meta.get("model_hash"),
        "pipeline_created_at": meta.get("created_at"),
    }
    return {"patient_summary": patient_text, "caregiver_checklist": checklist,
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


def _has_flagged_values(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_flagged_values(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return bool(value)


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
    saved_flags = json.loads(row["flags"])
    disclaimer = _disclaimer_for_backend(saved_flags)
    data: dict[str, Any] = {"available": True, "output_id": row["id"], "updated_at": row["created_at"], "disclaimer": disclaimer}
    recovered = False
    child_recovered = False
    version = saved_flags.get("gate_version")
    legacy = not isinstance(version, int) or version < GATE_VERSION
    if legacy:
        patient_unavailable, patient_needs_review = _patient_fallback_kind(
            row["patient_summary"], bool((saved_flags.get("fallback_used") or {}).get("patient_summary")))
    else:
        patient_unavailable = bool(saved_flags.get("patient_summary_unavailable"))
        patient_needs_review = bool(saved_flags.get("patient_summary_needs_review"))
    if perm.can(conn, actor, profile, perm.VIEW_PATIENT_SUMMARY):
        value = row["patient_summary"]
        if patient_unavailable:
            value = PATIENT_UNAVAILABLE_MESSAGE
        elif not isinstance(value, str) or not value.strip():
            value = MISSING_PATIENT_MESSAGE
            recovered = True
        data["patient_summary"] = value
        if patient_unavailable:                                      # fixed texts: no note, dose or flag details
            data["patient_warning"], data["patient_warning_title"] = PATIENT_UNAVAILABLE_WARNING, "Summary unavailable"
        elif patient_needs_review:
            data["patient_warning"], data["patient_warning_title"] = PATIENT_REVIEW_WARNING, "Please check this summary"
        if (saved_flags.get("dose_mismatch") or {}).get("patient_summary"):
            data["dose_warning"] = DOSE_MISMATCH_WARNING                 # fixed text: no medicine or dose named
    if perm.can(conn, actor, profile, perm.VIEW_CHILD_EXPLANATION):
        value = row["child_explanation"]
        if legacy:
            value = safety.SAFE_CHILD_MESSAGE                        # never re-show text the current gate did not check
            child_recovered = True
        elif not isinstance(value, str) or not value.strip():
            value = safety.SAFE_CHILD_MESSAGE
            recovered = True
            child_recovered = True
        data["child_explanation"] = value
    if perm.can(conn, actor, profile, perm.VIEW_CAREGIVER_CHECKLIST):
        try:
            items = json.loads(row["caregiver_checklist"])
        except (TypeError, json.JSONDecodeError):
            items = []
        if not isinstance(items, list) or not items or not all(isinstance(item, str) and item.strip() for item in items):
            items = [MISSING_CAREGIVER_ITEM]
            recovered = True
        ticks = _ticks(conn, row["note_id"]) if perm.can(conn, actor, profile, perm.VIEW_CHECKLIST_PROGRESS) else {}
        data["caregiver_checklist"] = [{"index": i, "text": t, "ticked": i in ticks, **ticks.get(i, {})} for i, t in enumerate(items)]
        data["checklist_progress"] = {"done": len(ticks), "total": len(items)}
        if (saved_flags.get("dose_mismatch") or {}).get("caregiver_checklist"):
            data["dose_warning"] = DOSE_MISMATCH_WARNING
    if perm.can(conn, actor, profile, perm.VIEW_SOURCE_NOTE):
        data["note"] = {"id": row["note_id"], "title": row["title"]}
    if perm.can(conn, actor, profile, perm.VIEW_FLAGS):
        data["flags"] = saved_flags
        data["child_withheld"] = bool(row["child_withheld"]) or child_recovered
        claim_gate = saved_flags.get("clinical_claim_gate") or {}
        if (claim_gate.get("fired") or saved_flags.get("caregiver_fallback")
                or (saved_flags.get("child_gate") or {}).get("fired")
                or any(_has_flagged_values(saved_flags.get(key)) for key in
                       ("fallback_used", "truncated", "redacted_dosages", "unsupported", "dose_mismatch", "recovery_removed"))):
            data["review_message"] = UNCONFIRMED_OUTPUT_WARNING
    if legacy:
        data["review_message"] = UNCONFIRMED_OUTPUT_WARNING           # fixed text, so every role may see it
    if recovered:
        data["output_warning"] = MISSING_OUTPUT_WARNING
    return data


_SELECT = ("SELECT o.*, n.title AS title FROM outputs o JOIN notes n ON n.id = o.note_id AND n.profile_id = o.profile_id "
           "WHERE o.profile_id = ? ")


def latest_outputs(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> dict[str, Any]:
    """The newest finished outputs the viewer may see, plus the generation state (for 'being prepared' banners)."""
    _require(conn, actor, profile, perm.VIEW_DASHBOARD)
    row = conn.execute(_SELECT + "ORDER BY o.id DESC LIMIT 1", (profile["id"],)).fetchone()
    gen = generation_state(conn, actor, profile)
    latest_note = conn.execute("SELECT id, status FROM notes WHERE profile_id = ? ORDER BY id DESC LIMIT 1",
                               (profile["id"],)).fetchone()
    # A previous note's output must not look like the result of a newer queued, running, failed, or
    # unexpectedly output-less job. Older results remain available through the explicit history link.
    if latest_note is not None and (latest_note["status"] != "done" or row is None or row["note_id"] != latest_note["id"]):
        data = {"available": False, "generation": gen, "disclaimer": DISCLAIMER}
        if latest_note["status"] == "done":
            data["output_warning"] = MISSING_OUTPUT_WARNING
        return data
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
        "JOIN notes n ON n.id = o.note_id AND n.profile_id = o.profile_id "
        "WHERE o.profile_id = ? ORDER BY o.id DESC", (profile["id"],)).fetchall()
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
