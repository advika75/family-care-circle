"""Notes (validation, permissions, deletion) and the single-worker job queue."""

from __future__ import annotations

import logging
import sqlite3
import threading

import pytest

from app import notes, outputs, permissions as P
from app.db import connect
from app.errors import NotAllowed, NotFound, ValidationFailed
from app.jobs import MSG_FAILED, MSG_UNAVAILABLE, JobRunner
from fcc_testlib import CLEAN_CHILD, SOURCE_TEXT, FakePipeline, make_record


def add(conn, ctx, runner, actor, profile, text=SOURCE_TEXT, title=None):
    return notes.add_note(conn, ctx, runner, actor, profile, title=title, text=text)


def status(conn, note_id):
    return conn.execute("SELECT status FROM notes WHERE id = ?", (note_id,)).fetchone()[0]


# --- who may add / delete -----------------------------------------------------------------------------
def test_add_note_permissions_by_role(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    allowed, _ = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    denied, _ = world.member(p, owner, "caregiver", "Dan", can_add_notes=False)
    pt, _ = world.member(p, owner, "patient", "Pat")
    ch, _ = world.member(p, owner, "child", "Kid")
    pending, _ = world.member(p, owner, "caregiver", "Waiting", active=False)
    stranger = world.user("Stranger")
    for u in (owner, allowed):
        assert add(conn, ctx, runner, u, p)["status"] == "queued"
    for u in (denied, pt, ch, pending, stranger):
        with pytest.raises(NotAllowed):
            add(conn, ctx, runner, u, p)
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 2


def test_note_records_who_added_it_and_default_titles(conn, ctx, runner, world):
    owner = world.user("Olivia Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara Carer", can_add_notes=True)
    a = add(conn, ctx, runner, owner, p)
    b = add(conn, ctx, runner, cg, p, title="  Clinic visit  ")
    assert (a["title"], a["added_by"]) == ("Note 1", owner["id"])
    assert (b["title"], b["added_by"]) == ("Clinic visit", cg["id"])
    listing = notes.list_notes(conn, owner, p)
    assert [(n["title"], n["added_by_name"]) for n in listing] == [("Clinic visit", "Cara Carer"), ("Note 1", "Olivia Owner")]
    assert all("text" not in n for n in listing)                      # the list never contains the source text


def test_only_the_creator_deletes_notes_and_it_cascades(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    n = add(conn, ctx, runner, cg, p)
    runner.drain()
    outputs.set_tick(conn, ctx, owner, p, n["id"], 0, True)
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM checklist_ticks").fetchone()[0] == 1
    with pytest.raises(NotAllowed):
        notes.delete_note(conn, cg, p, n["id"])                      # even the caregiver who added it
    notes.delete_note(conn, owner, p, n["id"])
    for table in ("notes", "outputs", "checklist_ticks"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    with pytest.raises(NotFound):
        notes.delete_note(conn, owner, p, n["id"])


def test_cannot_delete_a_note_of_another_circle(conn, ctx, runner, world):
    a, b = world.user("A"), world.user("B")
    pa, pb = world.profile(a, "Alpha"), world.profile(b, "Beta")
    nb = add(conn, ctx, runner, b, pb)
    with pytest.raises(NotFound):
        notes.delete_note(conn, a, pa, nb["id"])
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_source_note_is_visible_only_to_creator_and_caregivers(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    pt, _ = world.member(p, owner, "patient", "Pat")
    ch, _ = world.member(p, owner, "child", "Kid")
    n = add(conn, ctx, runner, owner, p)
    for u in (owner, cg):
        assert notes.get_note_source(conn, u, p, n["id"])["text"] == SOURCE_TEXT.strip()
    for u in (pt, ch):
        with pytest.raises(NotAllowed):
            notes.get_note_source(conn, u, p, n["id"])
        with pytest.raises(NotAllowed):
            notes.list_notes(conn, u, p)


# --- validation ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,field", [("", "text"), ("   \n ", "text"), ("bad\x00byte", "text"), ("x" * 20_001, "text")])
def test_bad_note_text_is_rejected_with_a_clear_message(conn, ctx, runner, world, text, field):
    owner = world.user("Owner"); p = world.profile(owner)
    with pytest.raises(ValidationFailed) as e:
        add(conn, ctx, runner, owner, p, text=text)
    assert field in e.value.errors and e.value.errors[field]
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_length_limit_is_6000_characters_inclusive_and_message_has_counts(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    add(conn, ctx, runner, owner, p, text="a" * 6_000)
    with pytest.raises(ValidationFailed) as e:
        add(conn, ctx, runner, owner, p, text="a" * 20_001)
    assert "too long for the local model" in e.value.errors["text"] and "6,000" in e.value.errors["text"]


def test_text_is_normalised_but_not_rewritten(ctx):
    assert notes.clean_note_text("  line1\r\nline2\tx\rline3  ", ctx.settings) == "line1\nline2\tx\nline3"


def test_title_validation(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    with pytest.raises(ValidationFailed) as e:
        add(conn, ctx, runner, owner, p, title="t" * 81)
    assert "title" in e.value.errors


@pytest.mark.parametrize("name,data,field", [
    ("note.pdf", b"%PDF-1.4", "file"), ("note", b"hello", "file"), (None, b"hello", "file"),
    ("note.txt", b"\xff\xfe\x00bad", "file"), ("note.txt", b"x" * 90_000, "file"), ("note.txt", b"", "text"),
])
def test_bad_uploads_are_rejected(ctx, name, data, field):
    with pytest.raises(ValidationFailed) as e:
        notes.decode_upload(name, data, ctx.settings)
    assert field in e.value.errors


def test_good_txt_upload_is_decoded_including_bom_and_uppercase_extension(ctx):
    assert notes.decode_upload("NOTE.TXT", "﻿Hello café\r\n".encode("utf-8"), ctx.settings) == "Hello café"


# --- the job queue --------------------------------------------------------------------------------------
def test_jobs_run_fifo_one_at_a_time_in_a_worker_thread(conn, ctx, runner, pipeline, world):
    pipeline.delay = 0.03
    seen = {}
    pipeline.on_run = lambda doc: seen.setdefault(doc, connect(ctx.settings.db_path).execute(
        "SELECT GROUP_CONCAT(id || ':' || status) FROM notes ORDER BY id").fetchone()[0])
    owner = world.user("Owner"); p = world.profile(owner)
    ids_ = [add(conn, ctx, runner, owner, p)["id"] for _ in range(5)]
    runner.start()
    try:
        assert runner.wait_idle(10)
    finally:
        runner.stop()
    assert pipeline.calls == [f"note-{i}" for i in ids_]                      # first in, first out
    assert pipeline.max_active == 1                                           # never two at once
    assert [status(conn, i) for i in ids_] == ["done"] * 5
    # while note 2 was running: 1 done, 2 running, 3-5 still queued
    assert seen[f"note-{ids_[1]}"] == f"{ids_[0]}:done,{ids_[1]}:running," + ",".join(f"{i}:queued" for i in ids_[2:])


def test_two_runners_threads_cannot_enter_the_pipeline_together(conn, ctx, settings, pipeline, world):
    """Belt and braces: even if process() is called from two threads, the pipeline lock serialises them."""
    pipeline.delay = 0.05
    r = JobRunner(settings, ctx, pipeline_factory=lambda: pipeline)
    owner = world.user("Owner"); p = world.profile(owner)
    ids_ = [add(conn, ctx, None, owner, p)["id"] for _ in range(4)]
    threads = [threading.Thread(target=r.process, args=(i,)) for i in ids_]
    [t.start() for t in threads]; [t.join(10) for t in threads]
    assert pipeline.max_active == 1 and [status(conn, i) for i in ids_] == ["done"] * 4


def test_a_job_stores_outputs_and_flags(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    n = add(conn, ctx, runner, owner, p)
    assert runner.drain() == 1
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (n["id"],)).fetchone()
    assert row["status"] == "done" and row["started_at"] and row["finished_at"] and row["error_message"] is None
    out = outputs.latest_outputs(conn, owner, p)
    assert out["available"] and out["patient_summary"].startswith("You have strep throat")
    flags = out["flags"]
    assert flags["retries"]["patient_summary"] == 1 and flags["fallback_used"]["patient_summary"] is False
    assert flags["model_id"] == "fake-model" and flags["model_hash"] == "sha256:abc"
    assert flags["pipeline_created_at"] == "2026-01-15T12:00:00+00:00" and flags["validation_errors"] == []
    assert flags["retention"]["patient_summary"]["n_required"] >= 1
    assert flags["child_gate"] == {"fired": False, "reasons": []}


def test_a_failing_job_is_marked_failed_with_a_safe_message_and_the_worker_survives(conn, ctx, runner, pipeline, world, caplog):
    caplog.set_level(logging.DEBUG)
    secret = "Jane Roe SSN 123-45-6789 secret note text"
    pipeline.fail_with = RuntimeError(secret)
    owner = world.user("Owner"); p = world.profile(owner)
    bad = add(conn, ctx, runner, owner, p)
    runner.drain()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (bad["id"],)).fetchone()
    assert row["status"] == "failed" and row["error_message"] == MSG_FAILED
    assert secret not in row["error_message"] and "Traceback" not in row["error_message"] and "RuntimeError" not in row["error_message"]
    assert secret not in "\n".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in "\n".join(r.getMessage() for r in caplog.records)          # only the class name is logged
    pipeline.fail_with = None
    good = add(conn, ctx, runner, owner, p)
    runner.drain()
    assert status(conn, good["id"]) == "done"
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 1


def test_failed_state_is_visible_with_message_to_adults_only(conn, ctx, runner, pipeline, world):
    pipeline.fail_with = ValueError("boom")
    owner = world.user("Owner"); p = world.profile(owner)
    pt, _ = world.member(p, owner, "patient", "Pat")
    add(conn, ctx, runner, owner, p)
    runner.drain()
    adult, patient = outputs.generation_state(conn, owner, p), outputs.generation_state(conn, pt, p)
    assert adult["state"] == "failed" and adult["message"] == MSG_FAILED and adult["note"]["title"] == "Note 1"
    assert patient["state"] == "failed" and "message" not in patient and "note" not in patient


def test_invalid_pipeline_output_fails_the_job(conn, ctx, runner, pipeline, world):
    pipeline.record_factory = lambda text: make_record(valid=False)
    owner = world.user("Owner"); p = world.profile(owner)
    n = add(conn, ctx, runner, owner, p)
    runner.drain()
    assert status(conn, n["id"]) == "failed" and conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0


def test_pipeline_that_cannot_be_built_fails_jobs_safely(conn, ctx, settings, world, caplog):
    caplog.set_level(logging.DEBUG)
    def broken():
        raise FileNotFoundError("/secret/path/model.gguf")
    r = JobRunner(settings, ctx, pipeline_factory=broken)
    owner = world.user("Owner"); p = world.profile(owner)
    a, b = add(conn, ctx, r, owner, p), add(conn, ctx, r, owner, p)
    assert r.drain() == 2
    for n in (a, b):
        assert conn.execute("SELECT status, error_message FROM notes WHERE id = ?", (n["id"],)).fetchone()[:] == ("failed", MSG_UNAVAILABLE)
    assert "/secret/path" not in "\n".join(rec.getMessage() for rec in caplog.records)


def test_pipeline_is_built_once_and_lazily(conn, ctx, settings, world):
    built = []
    r = JobRunner(settings, ctx, pipeline_factory=lambda: built.append(1) or FakePipeline())
    assert built == []
    owner = world.user("Owner"); p = world.profile(owner)
    for _ in range(3):
        add(conn, ctx, r, owner, p)
    r.drain()
    assert built == [1]


def test_deleting_a_note_while_it_is_being_generated_leaves_no_trace(conn, ctx, runner, pipeline, world):
    owner = world.user("Owner"); p = world.profile(owner)
    n = add(conn, ctx, runner, owner, p)
    pipeline.on_run = lambda doc: notes.delete_note(connect(ctx.settings.db_path), owner, p, n["id"])
    runner.drain()
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0


def test_a_deleted_queued_note_is_skipped(conn, ctx, runner, pipeline, world):
    owner = world.user("Owner"); p = world.profile(owner)
    a, b = add(conn, ctx, runner, owner, p), add(conn, ctx, runner, owner, p)
    notes.delete_note(conn, owner, p, a["id"])
    runner.drain()
    assert pipeline.calls == [f"note-{b['id']}"]


def test_duplicate_enqueue_runs_once(conn, ctx, runner, pipeline, world):
    owner = world.user("Owner"); p = world.profile(owner)
    n = add(conn, ctx, runner, owner, p)
    runner.enqueue(n["id"]); runner.enqueue(n["id"])
    runner.drain()
    assert pipeline.calls == [f"note-{n['id']}"]


def test_restart_recovery_requeues_queued_and_running_notes_in_order(conn, ctx, settings, pipeline, world):
    owner = world.user("Owner"); p = world.profile(owner)
    a, b, c = (add(conn, ctx, None, owner, p) for _ in range(3))
    conn.execute("UPDATE notes SET status = 'running' WHERE id = ?", (b["id"],))     # crashed mid-job
    conn.execute("UPDATE notes SET status = 'failed' WHERE id = ?", (c["id"],))       # already settled: not retried
    fresh = JobRunner(settings, ctx, pipeline_factory=lambda: pipeline)
    assert fresh.recover(conn) == 2
    fresh.drain()
    assert pipeline.calls == [f"note-{a['id']}", f"note-{b['id']}"]
    assert [status(conn, i) for i in (a["id"], b["id"], c["id"])] == ["done", "done", "failed"]


def test_end_to_end_with_the_real_pipeline_on_the_mock_backend(conn, ctx, settings, world):
    """No fakes: build_pipeline() -> FamilyCarePipeline(mock) on a synthetic note from data/raw."""
    from app.pipeline_adapter import build_pipeline
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "data" / "raw" / "note_01.txt").read_text(encoding="utf-8")
    real = JobRunner(settings, ctx, pipeline_factory=lambda: build_pipeline(settings))
    owner = world.user("Owner"); p = world.profile(owner)
    n = add(conn, ctx, real, owner, p, text=text)
    real.drain()
    assert status(conn, n["id"]) == "done"
    out = outputs.latest_outputs(conn, owner, p)
    assert out["patient_summary"] and out["caregiver_checklist"] and out["child_explanation"]
    assert out["flags"]["model_id"] == "mock" and out["flags"]["validation_errors"] == []
    # The deterministic child output uses only the approved general message.
    assert out["child_withheld"] is False and out["flags"]["child_gate"]["reasons"] == []
    assert out["child_explanation"] == outputs.safety.SAFE_CHILD_MESSAGE


def test_source_text_is_stored_only_in_the_notes_table(conn, ctx, runner, world):
    owner = world.user("Owner"); p = world.profile(owner)
    add(conn, ctx, runner, owner, p)
    runner.drain()
    marker = "ZEBRA-SOURCE-TOKEN visit note"
    hits = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for row in conn.execute(f"SELECT * FROM {table}"):
            if any(isinstance(v, str) and marker in v for v in tuple(row)):
                hits.append(table)
    assert hits == ["notes"]


# --- child gate through the whole path ---------------------------------------------------------------------
@pytest.mark.parametrize("child,reason", [
    ("You will take it for 3 days. Rest well.", "digit"),
    ("Your Amoxicillin will help you. Rest well.", "medication_name"),
    (" ".join(["Rest is good."] * 9), "too_long"),
])
def test_child_gate_withholds_and_records_why_for_adults_only(conn, ctx, runner, pipeline, world, child, reason):
    pipeline.record_factory = lambda text: make_record(child=child)
    owner = world.user("Owner"); p = world.profile(owner)
    ch, _ = world.member(p, owner, "child", "Kid")
    add(conn, ctx, runner, owner, p)
    runner.drain()
    adult, kid = outputs.latest_outputs(conn, owner, p), outputs.latest_outputs(conn, ch, p)
    assert adult["child_explanation"] == kid["child_explanation"] == outputs.safety.SAFE_CHILD_MESSAGE
    assert adult["child_withheld"] is True and adult["flags"]["child_gate"] == {"fired": True, "reasons": [reason]}
    assert "flags" not in kid and "child_withheld" not in kid
    assert child not in str(kid) and child not in str(adult)


def test_clean_child_text_is_stored_and_the_patient_text_is_never_gated(conn, ctx, runner, pipeline, world):
    owner = world.user("Owner"); p = world.profile(owner)
    pt, _ = world.member(p, owner, "patient", "Pat")
    ch, _ = world.member(p, owner, "child", "Kid")
    add(conn, ctx, runner, owner, p)
    runner.drain()
    assert outputs.latest_outputs(conn, ch, p)["child_explanation"] == CLEAN_CHILD
    summary = outputs.latest_outputs(conn, pt, p)["patient_summary"]
    assert "Amoxicillin" in summary and "500 mg" in summary and "10 days" in summary      # doses and names stay for patients


def test_model_output_with_unsupported_serious_child_claim_is_withheld(conn, ctx, runner, pipeline, world):
    pipeline.record_factory = lambda _text: make_record(
        child="You had a heart attack. Doctors put a tiny helper in your heart.")
    owner = world.user("Owner"); p = world.profile(owner)
    child, _ = world.member(p, owner, "child", "Kid")
    note = "Patient reports a mild cough. The note says nothing about a heart attack or heart procedure."
    created = add(conn, ctx, runner, owner, p, text=note)
    runner.drain()

    assert status(conn, created["id"]) == "done"
    adult = outputs.latest_outputs(conn, owner, p)
    kid = outputs.latest_outputs(conn, child, p)
    assert adult["child_explanation"] == kid["child_explanation"] == outputs.safety.SAFE_CHILD_MESSAGE
    assert adult["child_withheld"] is True
    assert adult["flags"]["clinical_claim_gate"]["child"]
    assert "heart attack" not in kid["child_explanation"].casefold()
