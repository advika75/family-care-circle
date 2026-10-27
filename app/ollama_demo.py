"""Preflight and launch the fixed-port local Ollama web demo."""

from __future__ import annotations

import os
import sys

from app.config import Settings
from app.ollama_generator import OllamaError
from app.pipeline_adapter import build_pipeline, timeout_budget_problem


HOST = "127.0.0.1"
PORT = 8001


def main() -> int:
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Ollama demo configuration is invalid ({type(exc).__name__}). Check APP_* settings.", file=sys.stderr)
        return 2
    if settings.backend != "ollama":
        print("Ollama demo preflight requires APP_BACKEND=ollama.", file=sys.stderr)
        return 2
    budget_problem = timeout_budget_problem(settings)
    if budget_problem:   # fail loudly: the demo should never stop a note that is still within its per-call limits
        print(f"Ollama demo preflight stopped: {budget_problem}", file=sys.stderr)
        return 2
    try:
        # Pipeline construction queries /api/tags and confirms the exact configured model tag. It sends no note
        # and makes no generation request. Do not continue with a mock backend if this check fails.
        pipeline = build_pipeline(settings)
        del pipeline
    except OllamaError as exc:
        print(exc.safe_message, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - keep startup diagnostics free of URLs or request data
        # Never print exception strings: configuration or library errors can include sensitive values.
        print(f"Ollama demo preflight failed ({type(exc).__name__}). Check the local app configuration.", file=sys.stderr)
        return 2

    print(f"Verified Ollama service/model tag: {settings.ollama_model}")
    print(f"Backend: ollama | URL: {settings.ollama_url} | Web app: http://{HOST}:{PORT}")
    print(f"Per-request timeout: {settings.ollama_timeout_seconds:g}s | Whole-job timeout: {settings.job_timeout_seconds}s")
    print("Preflight checked connectivity and model availability only; it did not generate text.", flush=True)
    os.execvpe(sys.executable, [sys.executable, "-m", "uvicorn", "app.web.main:create_app", "--factory",
                               "--host", HOST, "--port", str(PORT), "--no-server-header"], os.environ.copy())
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a CLI target
    raise SystemExit(main())
