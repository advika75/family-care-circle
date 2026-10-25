"""Runs the research pipeline in a separate, killable process (F-01).

Why: a thread cannot be stopped. If the model hangs, a thread-based worker would block every care circle forever.
A child process can be terminated: after ``timeout`` seconds the parent kills it, the note is marked failed, and
the next job starts a fresh process (the model is reloaded then).

Safety properties
* Only plain, JSON-like data crosses the pipe (the pipeline already returns such a record).
* Errors cross the pipe as an exception CLASS name plus one boolean, never the message (which can contain note text).
* If the web process dies abruptly (kill -9), the child notices its parent changed and exits, so no orphan is left
  holding the model in memory.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from typing import Any, Callable


class JobTimeout(Exception):
    """The pipeline did not finish within the time limit; its process was killed."""


class WorkerError(Exception):
    """The pipeline raised inside the worker process. ``kind`` is the exception class name only."""

    def __init__(self, kind: str, too_long: bool = False) -> None:
        super().__init__(kind)
        self.kind, self.too_long = kind, too_long


def is_context_overflow(exc: BaseException) -> bool:
    """True if a (llama.cpp) exception means the prompt did not fit the model's context window."""
    text = str(exc).lower()
    return "context window" in text or ("exceed" in text and "token" in text) or "context length" in text


def _child_main(conn: Any, factory: Callable[[], Any], parent_pid: int) -> None:
    pipeline = None
    try:
        while True:
            if not conn.poll(1.0):
                if os.getppid() != parent_pid:      # the web process is gone: do not linger holding the model
                    return
                continue
            message = conn.recv()
            if message[0] == "stop":
                return
            _, text, doc_id = message
            try:
                if pipeline is None:
                    pipeline = factory()
                conn.send(("ok", pipeline.run(text, doc_id=doc_id)))
            except Exception as exc:  # noqa: BLE001 - class name only crosses the pipe
                conn.send(("err", type(exc).__name__, is_context_overflow(exc)))
    except (EOFError, BrokenPipeError, KeyboardInterrupt, OSError):
        return


class ProcessPipeline:
    """Presents the same ``run(text, doc_id=...)`` interface as the pipeline, executed in a child process."""

    def __init__(self, factory: Callable[[], Any], timeout: float) -> None:
        self._factory, self._timeout = factory, timeout
        self._proc: Any = None
        self._conn: Any = None
        self.killed_pids: list[int] = []

    def ensure_started(self) -> int:
        if self._proc is None or not self._proc.is_alive():
            context = mp.get_context("spawn")
            parent_conn, child_conn = context.Pipe()
            self._proc = context.Process(target=_child_main, args=(child_conn, self._factory, os.getpid()), daemon=True)
            self._proc.start()
            child_conn.close()
            self._conn = parent_conn
        return self._proc.pid

    def run(self, text: str, doc_id: str = "doc") -> dict[str, Any]:
        self.ensure_started()
        try:
            self._conn.send(("run", text, doc_id))
            if not self._conn.poll(self._timeout):
                self.kill()
                raise JobTimeout()
            message = self._conn.recv()
        except (EOFError, BrokenPipeError, OSError):
            self.kill()
            raise WorkerError("WorkerDied") from None
        if message[0] == "ok":
            return message[1]
        raise WorkerError(message[1], too_long=bool(message[2]))

    def kill(self) -> None:
        proc, self._proc = self._proc, None
        conn, self._conn = self._conn, None
        if proc is not None:
            pid = proc.pid
            proc.terminate()
            proc.join(3)
            if proc.is_alive():
                proc.kill()
                proc.join(3)
            self.killed_pids.append(pid)
        if conn is not None:
            conn.close()

    def shutdown(self) -> None:
        if self._proc is not None and self._proc.is_alive():
            try:
                self._conn.send(("stop",))
                self._proc.join(3)
            except (BrokenPipeError, OSError):
                pass
        self.kill()
