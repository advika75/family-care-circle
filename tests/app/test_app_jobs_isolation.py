"""F-01: a generation that never returns must be stopped, the note failed, and the queue must keep moving."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import replace
from pathlib import Path

import pytest

from app import notes
from app.config import Settings
from app.jobs import MSG_FAILED, MSG_TIMEOUT, JobRunner
from fcc_testlib import TestPipelineFactory


def runner_for(settings, ctx, **kw):
    return JobRunner(settings, ctx, pipeline_factory=TestPipelineFactory(), isolation="process", job_timeout=kw.pop("job_timeout", 3), **kw)


def status(conn, note_id):
    return conn.execute("SELECT status, error_message FROM notes WHERE id = ?", (note_id,)).fetchone()


def test_a_hung_generation_is_stopped_and_the_note_fails(conn, ctx, settings, world):
    owner = world.user("Owner"); p = world.profile(owner)
    r = runner_for(settings, ctx)
    try:
        hang = notes.add_note(conn, ctx, r, owner, p, title="hang", text="hang forever")
        t0 = time.monotonic()
        r.drain()
        elapsed = time.monotonic() - t0
        row = status(conn, hang["id"])
        assert row["status"] == "failed" and row["error_message"] == MSG_TIMEOUT
        assert elapsed < 20, f"took {elapsed:.0f}s: the timeout did not stop the job"
        assert "try adding it again" not in row["error_message"].lower()     # retrying the same note cannot help
    finally:
        r.shutdown()


def test_the_queue_keeps_moving_after_a_timeout_and_the_stuck_process_is_gone(conn, ctx, settings, world):
    owner = world.user("Owner"); p = world.profile(owner)
    r = runner_for(settings, ctx)
    try:
        hang = notes.add_note(conn, ctx, r, owner, p, title="hang", text="hang")
        ok = notes.add_note(conn, ctx, r, owner, p, title="ok", text="a normal note")
        r.drain()
        assert status(conn, hang["id"])["status"] == "failed" and status(conn, ok["id"])["status"] == "done"
        assert r.killed_pids and not any(_alive(pid) for pid in r.killed_pids), "the hung worker process is still alive"
    finally:
        r.shutdown()


def test_an_exception_in_the_worker_process_fails_the_note_without_leaking_its_text(conn, ctx, settings, world, caplog):
    owner = world.user("Owner"); p = world.profile(owner)
    r = runner_for(settings, ctx)
    try:
        boom = notes.add_note(conn, ctx, r, owner, p, title="boom", text="boom now")
        after = notes.add_note(conn, ctx, r, owner, p, title="after", text="fine")
        r.drain()
        row = status(conn, boom["id"])
        assert row["status"] == "failed" and row["error_message"] == MSG_FAILED and "PRIVATE" not in row["error_message"]
        assert "PRIVATE" not in caplog.text
        assert status(conn, after["id"])["status"] == "done"                 # the same worker process is reused
    finally:
        r.shutdown()


def test_ollama_safe_failure_message_survives_process_boundary(conn, ctx, settings, world):
    from fcc_testlib import OllamaTimeoutPipelineFactory
    from app.ollama_generator import OllamaTimeout

    owner = world.user("Owner"); profile = world.profile(owner)
    r = JobRunner(settings, ctx, pipeline_factory=OllamaTimeoutPipelineFactory(), isolation="process", job_timeout=10)
    try:
        note = notes.add_note(conn, ctx, r, owner, profile, title="synthetic", text="synthetic note")
        r.drain()
        row = status(conn, note["id"])
        assert row["status"] == "failed"
        assert row["error_message"] == OllamaTimeout.safe_message
    finally:
        r.shutdown()


def test_process_mode_produces_the_same_outputs_with_the_real_mock_pipeline(conn, ctx, settings, world):
    from functools import partial
    from app.pipeline_adapter import build_pipeline
    owner = world.user("Owner"); p = world.profile(owner)
    r = JobRunner(settings, ctx, pipeline_factory=partial(build_pipeline, settings), isolation="process", job_timeout=60)
    try:
        text = (Path(__file__).resolve().parents[2] / "data" / "raw" / "note_01.txt").read_text(encoding="utf-8")
        n = notes.add_note(conn, ctx, r, owner, p, title="real mock pipeline", text=text)
        r.drain()
        assert status(conn, n["id"])["status"] == "done"
        from app import outputs
        out = outputs.latest_outputs(conn, owner, p)
        assert out["patient_summary"] and out["caregiver_checklist"] and out["flags"]["model_id"] == "mock"
    finally:
        r.shutdown()


def test_defaults_isolate_the_real_model_and_not_the_mock():
    assert Settings(backend="llama_cpp").effective_job_isolation == "process"
    assert Settings(backend="ollama").effective_job_isolation == "process"
    assert Settings(backend="mock").effective_job_isolation == "thread"
    assert Settings(backend="mock", job_isolation="process").effective_job_isolation == "process"
    assert Settings().job_timeout_seconds == 900
    s = Settings.from_env({"APP_JOB_TIMEOUT_SECONDS": "120", "APP_JOB_ISOLATION": "process"})
    assert (s.job_timeout_seconds, s.effective_job_isolation) == (120, "process")
    with pytest.raises(ValueError):
        Settings.from_env({"APP_JOB_ISOLATION": "magic"})
    with pytest.raises(ValueError):
        Settings.from_env({"APP_JOB_TIMEOUT_SECONDS": "0"})


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.mark.slow
def test_the_worker_process_exits_when_its_parent_is_killed(tmp_path):
    """kill -9 on the web process must not leave an orphaned worker holding a 2 GB model.

    The worker exits through two independent mechanisms: end-of-file on the pipe (which closes when the parent
    dies) and the explicit parent-pid check. Either alone satisfies this test; it verifies the outcome, not one line.
    """
    db = tmp_path / "orphan.sqlite3"
    code = textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, "."); sys.path.insert(0, "tests/app")
        from pathlib import Path
        from app.config import Settings; from app.context import Ctx; from app.jobs import JobRunner
        from app.db import connect, migrate
        from fcc_testlib import TestPipelineFactory
        s = Settings(db_path=Path({str(db)!r}), scrypt_n=16, secret_key=b"k" * 32); ctx = Ctx(s)
        conn = connect(s.db_path); migrate(conn)
        r = JobRunner(s, ctx, pipeline_factory=TestPipelineFactory(), isolation="process", job_timeout=600)
        pid = r.start_worker_process_for_test()
        r._pipeline.run("warm up", "w")        # round-trip: the worker is now fully started and sitting in its loop
        print(pid, flush=True)
        time.sleep(600)
    """)
    parent = subprocess.Popen([sys.executable, "-W", "ignore", "-c", code], stdout=subprocess.PIPE, text=True)
    child_pid = int(parent.stdout.readline())
    assert _alive(child_pid)
    time.sleep(0.5)
    assert _alive(child_pid), "the worker must still be running while its parent is alive"
    os.kill(parent.pid, signal.SIGKILL); parent.wait()
    for _ in range(100):
        if not _alive(child_pid):
            break
        time.sleep(0.2)
    assert not _alive(child_pid), "orphaned worker process is still running"
