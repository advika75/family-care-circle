"""Ollama timeout budget and the persona/attempt logged when a generation job fails (synthetic notes only)."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pytest

from app import notes
from app.config import Settings
from app.jobs import MSG_TIMEOUT, JobRunner
from app.pipeline_adapter import _AppPromptGuard, model_call_budget, timeout_budget_problem
from fcc_testlib import ProgressPipelineFactory

ROOT = Path(__file__).resolve().parents[2]


# ---- (a) startup check ------------------------------------------------------------------------------------------
def test_budget_is_personas_times_attempts_from_the_research_config():
    from src.prompts import PERSONAS
    from src.utils import load_config

    assert model_call_budget() == len(PERSONAS) * (int(load_config("config.yaml")["max_retries"]) + 1) == 9


def test_job_timeout_below_nine_request_timeouts_is_reported_for_ollama_only():
    short = Settings(backend="ollama", ollama_timeout_seconds=120, job_timeout_seconds=900)
    problem = timeout_budget_problem(short)
    assert problem and "900" in problem and "1080" in problem and "120" in problem
    assert timeout_budget_problem(replace(short, job_timeout_seconds=1080)) is None
    assert timeout_budget_problem(replace(short, job_timeout_seconds=1200)) is None
    assert timeout_budget_problem(replace(short, backend="mock")) is None


def test_ollama_demo_preflight_fails_loudly_before_contacting_ollama(monkeypatch, capsys):
    from app import ollama_demo

    monkeypatch.setenv("APP_BACKEND", "ollama")
    monkeypatch.setenv("APP_OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("APP_OLLAMA_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("APP_JOB_TIMEOUT_SECONDS", "900")
    monkeypatch.setattr(ollama_demo, "build_pipeline", lambda _s: pytest.fail("Ollama was contacted"))
    assert ollama_demo.main() == 2
    err = capsys.readouterr().err
    assert "APP_JOB_TIMEOUT_SECONDS" in err and "1080" in err


def test_web_app_logs_a_clear_warning_when_the_budget_is_short(settings, caplog):
    from app.web.main import create_app

    with caplog.at_level(logging.WARNING, logger="app.web"):
        create_app(replace(settings, backend="ollama", ollama_timeout_seconds=120, job_timeout_seconds=900),
                   start_worker=False)
    assert any("APP_JOB_TIMEOUT_SECONDS" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


# ---- (b) Makefile ------------------------------------------------------------------------------------------------
def test_only_the_ollama_demo_target_uses_the_1200_second_job_timeout():
    makefile = (ROOT / "Makefile").read_text()
    assert "APP_JOB_TIMEOUT_SECONDS ?= 1200" in makefile
    users = [line for line in makefile.splitlines() if "APP_JOB_TIMEOUT_SECONDS" in line and "?=" not in line]
    assert users == ["app-demo-ollama: export APP_JOB_TIMEOUT_SECONDS := $(APP_JOB_TIMEOUT_SECONDS)"]
    assert timeout_budget_problem(Settings(backend="ollama", ollama_timeout_seconds=120, job_timeout_seconds=1200)) is None


# ---- (c) persona and attempt on failure -------------------------------------------------------------------------
def test_prompt_guard_records_persona_and_attempt_only():
    seen = []
    guard = _AppPromptGuard(type("G", (), {"generate": lambda self, m, **o: "x"})())
    guard.on_attempt = lambda persona, attempt: seen.append((persona, attempt))
    first = [{"role": "user", "content": "AUDIENCE: child\nPRIVATE NOTE TEXT"}]
    guard.generate(first)
    guard.generate([*first, {"role": "assistant", "content": "x"}, {"role": "user", "content": "again"},
                    {"role": "assistant", "content": "x"}, {"role": "user", "content": "again"}])
    guard.generate([{"role": "user", "content": "AUDIENCE: somebody-else"}])
    assert seen == [("child", 1), ("child", 3), ("unknown", 1)]
    assert guard.progress == ("unknown", 1)


def _failure_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.jobs" and r.levelno >= logging.ERROR]


def test_process_timeout_logs_the_running_persona_and_attempt_without_note_text(conn, ctx, settings, world, caplog):
    owner = world.user("Owner"); p = world.profile(owner)
    runner = JobRunner(settings, ctx, pipeline_factory=ProgressPipelineFactory(), isolation="process", job_timeout=3)
    try:
        with caplog.at_level(logging.INFO, logger="app.jobs"):
            note = notes.add_note(conn, ctx, runner, owner, p, title="hang", text="hang SECRET-NOTE-WORDS")
            runner.drain()
        row = conn.execute("SELECT status, error_message FROM notes WHERE id = ?", (note["id"],)).fetchone()
        assert row["status"] == "failed" and row["error_message"] == MSG_TIMEOUT
        logs = _failure_logs(caplog)
        assert any("persona=caregiver attempt=2" in line for line in logs), logs
        assert not any("SECRET" in r.getMessage() for r in caplog.records)
    finally:
        runner.shutdown()


@pytest.mark.parametrize("isolation", ["thread", "process"])
def test_worker_exception_logs_persona_attempt_and_class_name_only(conn, ctx, settings, world, caplog, isolation):
    owner = world.user("Owner"); p = world.profile(owner)
    runner = JobRunner(settings, ctx, pipeline_factory=ProgressPipelineFactory(), isolation=isolation, job_timeout=20)
    try:
        with caplog.at_level(logging.INFO, logger="app.jobs"):
            notes.add_note(conn, ctx, runner, owner, p, title="boom", text="boom SECRET-NOTE-WORDS")
            runner.drain()
        logs = _failure_logs(caplog)
        assert any("persona=caregiver attempt=2" in line and "RuntimeError" in line for line in logs), logs
        assert not any("SECRET" in r.getMessage() or "PRIVATE-FRAGMENT" in r.getMessage() for r in caplog.records)
    finally:
        runner.shutdown()


def test_progress_from_a_previous_job_is_not_reported_for_the_next(conn, ctx, settings, world, caplog):
    owner = world.user("Owner"); p = world.profile(owner)
    runner = JobRunner(settings, ctx, pipeline_factory=ProgressPipelineFactory(), isolation="thread")
    notes.add_note(conn, ctx, runner, owner, p, title="ok", text="a normal note")
    runner.drain()
    assert runner._pipeline.generator.progress == ("caregiver", 2)
    runner._pipeline.generator.progress = ("child", 3)       # stale value left by an earlier job
    runner._reset_progress()
    assert runner._running_step() == "persona=unknown attempt=unknown"
