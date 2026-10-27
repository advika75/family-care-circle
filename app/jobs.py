"""Background generation: ONE worker thread, ONE job at a time, first in first out.

Why one at a time: the research pipeline (and its generator) keep per-instance state (``last_truncated``,
global RNG seeding) and the real model is slow (~75 s per note), so the pipeline is built once per process and
only ever used from this single worker, under a lock as a second guard.

Job states live on the note row: queued -> running -> done | failed. A failed job stores a SAFE, fixed message;
exception text and stack traces are never stored or shown (they could contain note text), and only the
exception CLASS name is logged. After a crash, notes left ``queued`` or ``running`` are re-queued by
:meth:`JobRunner.recover` at startup (outputs are written in one transaction, so a half-finished job leaves nothing).
"""

from __future__ import annotations

import logging
import queue
from functools import partial
import sqlite3
import threading
import time
from typing import Any, Callable

from app import outputs as outputs_mod
from app.config import Settings
from app.context import Ctx
from app.db import connect, is_database_error, iso, transaction
from app.pipeline_adapter import build_pipeline
from app.worker_process import JobTimeout, ProcessPipeline, WorkerError, is_context_overflow
from app.ollama_generator import OllamaError

log = logging.getLogger("app.jobs")

MSG_FAILED = "We could not prepare this note. Please try adding it again."
MSG_UNAVAILABLE = "The text generator is not available right now. Please try again later."
MSG_TIMEOUT = ("This note took too long to prepare and was stopped. Try a shorter note, "
               "or ask whoever runs the app to check the text generator.")


class JobRunner:
    def __init__(self, settings: Settings, ctx: Ctx | None = None,
                 pipeline_factory: Callable[[], Any] | None = None, isolation: str | None = None,
                 job_timeout: float | None = None) -> None:
        self.settings = settings
        self.ctx = ctx or Ctx(settings=settings)
        # `partial` (not a lambda) so the factory can be sent to a spawned worker process
        self._factory = pipeline_factory or partial(build_pipeline, settings)
        self.isolation = isolation or settings.effective_job_isolation
        self.job_timeout = float(job_timeout if job_timeout is not None else settings.job_timeout_seconds)
        self._pipeline: Any = None
        self._build_error = False
        self._build_error_message = MSG_UNAVAILABLE
        self._queue: queue.Queue[int] = queue.Queue()
        self._pipeline_lock = threading.Lock()      # the pipeline is never entered by two threads
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # -- queue ---------------------------------------------------------------------------------------
    def enqueue(self, note_id: int) -> None:
        self._queue.put(note_id)

    def pending(self) -> int:
        return self._queue.unfinished_tasks

    def recover(self, conn: sqlite3.Connection) -> int:
        """Re-queue notes that were queued or running when the process stopped (oldest first)."""
        rows = conn.execute("SELECT id FROM notes WHERE status IN ('queued','running') ORDER BY id").fetchall()
        for r in rows:
            self.enqueue(r["id"])
        return len(rows)

    # -- worker --------------------------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="fcc-generation-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                note_id = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.process(note_id)
            finally:
                self._queue.task_done()

    def drain(self) -> int:
        """Process everything currently queued in the calling thread (used by tests and one-off scripts)."""
        n = 0
        while True:
            try:
                note_id = self._queue.get_nowait()
            except queue.Empty:
                return n
            try:
                self.process(note_id)
                n += 1
            finally:
                self._queue.task_done()

    def wait_idle(self, timeout: float = 10.0) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0

    # -- one job -------------------------------------------------------------------------------------
    @property
    def killed_pids(self) -> list[int]:
        return list(getattr(self._pipeline, "killed_pids", []))

    def start_worker_process_for_test(self) -> int:
        """Start the isolated worker process now and return its pid (used by the orphan-process test)."""
        self._pipeline = self._pipeline or ProcessPipeline(self._factory, self.job_timeout)
        return self._pipeline.ensure_started()

    def shutdown(self) -> None:
        """Stop the worker thread and any isolated worker process."""
        self.stop()
        if isinstance(self._pipeline, ProcessPipeline):
            self._pipeline.shutdown()

    def _too_long_message(self) -> str:
        return (f"This note is too long for the local model. Shorten it to about "
                f"{self.settings.max_note_chars:,} characters.")

    def _get_pipeline(self) -> Any:
        if self._pipeline is None and not self._build_error:
            try:
                self._pipeline = (ProcessPipeline(self._factory, self.job_timeout) if self.isolation == "process"
                                  else self._factory())
            except Exception as exc:  # noqa: BLE001 - reported safely below
                self._build_error = True
                log.error("pipeline could not be built: %s", type(exc).__name__)
                if isinstance(exc, OllamaError):
                    self._build_error_message = exc.safe_message
        return self._pipeline

    def _reset_progress(self) -> None:
        if isinstance(self._pipeline, ProcessPipeline):
            self._pipeline.last_progress = None
        elif hasattr(getattr(self._pipeline, "generator", None), "progress"):
            self._pipeline.generator.progress = None

    def _running_step(self) -> str:
        """Persona and attempt that was being generated (fixed names and a count; never note text)."""
        if isinstance(self._pipeline, ProcessPipeline):
            step = self._pipeline.last_progress
        else:
            step = getattr(getattr(self._pipeline, "generator", None), "progress", None)
        if (isinstance(step, tuple) and len(step) == 2 and step[0] in ("patient", "caregiver", "child", "unknown")
                and isinstance(step[1], int)):
            return f"persona={step[0]} attempt={step[1]}"
        return "persona=unknown attempt=unknown"

    def _set_failed(self, conn: sqlite3.Connection, note_id: int, message: str) -> None:
        conn.execute("UPDATE notes SET status = 'failed', error_message = ?, finished_at = ? WHERE id = ?",
                     (message, iso(self.ctx.now()), note_id))

    def _fail_quietly(self, conn: sqlite3.Connection, note_id: int, message: str) -> None:
        try:
            self._set_failed(conn, note_id, message)
        except Exception as exc:
            if not is_database_error(exc):
                raise

    def process(self, note_id: int) -> None:
        conn = connect(self.settings.db_path)
        try:
            note = conn.execute("SELECT id, profile_id, text, status FROM notes WHERE id = ?", (note_id,)).fetchone()
            if note is None or note["status"] not in ("queued", "running"):
                return                                   # deleted meanwhile, or a duplicate enqueue
            conn.execute("UPDATE notes SET status = 'running', started_at = ?, error_message = NULL WHERE id = ?",
                         (iso(self.ctx.now()), note_id))
            try:
                with self._pipeline_lock:
                    pipeline = self._get_pipeline()
                    if pipeline is None:
                        self._set_failed(conn, note_id, self._build_error_message)
                        return
                    self._reset_progress()
                    record = pipeline.run(note["text"], doc_id=f"note-{note_id}")
                if not record.get("metadata", {}).get("valid", False):
                    log.warning("note_id=%s pipeline output failed validation", note_id)
                    self._set_failed(conn, note_id, MSG_FAILED)
                    return
                built = outputs_mod.build_output(record, note["text"])
                with transaction(conn):
                    still_there = conn.execute("SELECT 1 FROM notes WHERE id = ?", (note_id,)).fetchone()
                    if still_there:                      # the note may have been deleted while the model ran
                        outputs_mod.store_output(conn, self.ctx, note_id, note["profile_id"], built)
                        conn.execute("UPDATE notes SET status = 'done', finished_at = ? WHERE id = ?",
                                     (iso(self.ctx.now()), note_id))
            except JobTimeout:
                log.error("note_id=%s generation exceeded %ss at %s and its worker process was killed", note_id,
                          int(self.job_timeout), self._running_step())
                self._fail_quietly(conn, note_id, MSG_TIMEOUT)
            except WorkerError as exc:
                log.error("note_id=%s generation failed at %s: %s", note_id, self._running_step(), exc.kind)
                message = exc.safe_message or (self._too_long_message() if exc.too_long else MSG_FAILED)
                self._fail_quietly(conn, note_id, message)
            except OllamaError as exc:
                log.error("note_id=%s generation failed at %s: %s", note_id, self._running_step(), type(exc).__name__)
                self._fail_quietly(conn, note_id, exc.safe_message)
            except Exception as exc:  # noqa: BLE001 - never surface exception text (it could contain note text)
                log.error("note_id=%s generation failed at %s: %s", note_id, self._running_step(), type(exc).__name__)
                self._fail_quietly(conn, note_id, self._too_long_message() if is_context_overflow(exc) else MSG_FAILED)
        finally:
            conn.close()
