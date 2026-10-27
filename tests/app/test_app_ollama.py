"""Ollama adapter tests use a fake loopback HTTP server and no model download."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.config import Settings
from app import notes
from app.jobs import JobRunner
from app.ollama_generator import (
    OllamaBadResponse,
    OllamaGenerator,
    OllamaHTTPFailure,
    OllamaModelMissing,
    OllamaModelRequired,
    OllamaRemoteRefused,
    OllamaTimeout,
    OllamaUnavailable,
)
from app.outputs import _disclaimer_for_backend, build_output
from app.pipeline_adapter import build_pipeline


TAG = "qwen2.5:3b"
DIGEST = "a" * 64


class FakeOllama:
    def __init__(self):
        self.tags_status = 200
        self.tags_body: bytes | dict = {"models": [{"name": TAG, "model": TAG, "digest": DIGEST}]}
        self.tags_redirect = False
        self.chat_status = 200
        self.chat_body: bytes | dict = {"message": {"role": "assistant", "content": "Local reply."},
                                        "done": True, "done_reason": "stop"}
        self.delay = 0
        self.chat_request = None
        self.chat_requests = []
        state = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/api/tags":
                    self.send_error(404)
                    return
                if state.tags_redirect:
                    self.send_response(302)
                    self.send_header("Location", "http://ollama.example.invalid/api/tags")
                    self.end_headers()
                    return
                time.sleep(state.delay)
                self._respond(state.tags_status, state.tags_body)

            def do_POST(self):
                if self.path != "/api/chat":
                    self.send_error(404)
                    return
                state.chat_request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                state.chat_requests.append(state.chat_request)
                time.sleep(state.delay)
                self._respond(state.chat_status, state.chat_body)

            def _respond(self, status, value):
                data = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, _format, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


@pytest.fixture
def fake_ollama():
    server = FakeOllama()
    try:
        yield server
    finally:
        server.close()


def make_generator(server, *, model=TAG, timeout=1):
    return OllamaGenerator({"temperature": 0.2, "top_p": 0.9, "seed": 42}, url=server.url,
                           model=model, timeout_seconds=timeout, context_size=4096)


def test_settings_add_ollama_environment_with_safe_defaults():
    s = Settings.from_env({"APP_BACKEND": "ollama"})
    assert s.backend == "ollama"
    assert s.ollama_url == "http://127.0.0.1:11434"
    assert s.ollama_model is None
    assert s.ollama_timeout_seconds == 120
    assert not s.ollama_allow_remote
    assert s.effective_job_isolation == "process"


@pytest.mark.parametrize("value", ["0", "nan", "inf", "-1"])
def test_ollama_timeout_must_be_finite_and_positive(value):
    with pytest.raises(ValueError, match="APP_OLLAMA_TIMEOUT_SECONDS"):
        Settings.from_env({"APP_OLLAMA_TIMEOUT_SECONDS": value})


def test_chat_success_passes_configured_sampling_and_records_model_identity(fake_ollama):
    generator = make_generator(fake_ollama)
    messages = [{"role": "system", "content": "System prompt."}, {"role": "user", "content": "Synthetic test."}]
    assert generator.generate(messages, max_new_tokens=17, temperature=0.4) == "Local reply."
    assert generator.backend == "ollama"
    assert generator.model_id == TAG
    assert generator.model_hash == f"ollama_digest:{DIGEST}"
    assert generator.seed == 42 and generator.last_truncated is False
    assert fake_ollama.chat_request == {
        "model": TAG, "messages": messages, "stream": False,
        "options": {"temperature": 0.4, "top_p": 0.9, "seed": 42, "num_predict": 17, "num_ctx": 4096},
    }


def test_app_pipeline_injects_ollama_and_records_metadata(fake_ollama):
    settings = Settings(backend="ollama", ollama_url=fake_ollama.url, ollama_model=TAG,
                        ollama_timeout_seconds=1, job_isolation="thread")
    record = build_pipeline(settings).run("Synthetic test note only.", doc_id="synthetic-test")
    assert record["metadata"]["backend"] == "ollama"
    assert record["metadata"]["model_id"] == TAG
    assert record["metadata"]["model_hash"] == f"ollama_digest:{DIGEST}"
    assert len(fake_ollama.chat_requests) == 3
    assert all(request["options"]["num_ctx"] == 4096 for request in fake_ollama.chat_requests)
    child_prompt = next(request["messages"][-1]["content"] for request in fake_ollama.chat_requests
                        if "AUDIENCE: child" in request["messages"][-1]["content"])
    assert "may be a different person from the patient" in child_prompt
    assert "Do not infer a diagnosis, procedure, device, hospital event, recovery" in child_prompt


def test_model_tag_is_required_and_installed_tags_are_reported(fake_ollama):
    with pytest.raises(OllamaModelRequired, match="APP_OLLAMA_MODEL is not set") as error:
        make_generator(fake_ollama, model=None)
    assert TAG in error.value.safe_message


def test_missing_model_tag_is_reported_without_chat_call(fake_ollama):
    with pytest.raises(OllamaModelMissing, match="is not installed"):
        make_generator(fake_ollama, model="missing:tag")
    assert fake_ollama.chat_request is None


def test_connection_refused_is_a_safe_unavailable_error():
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    with pytest.raises(OllamaUnavailable, match="Ollama is not responding"):
        OllamaGenerator({}, url=f"http://127.0.0.1:{port}", model=TAG,
                        timeout_seconds=0.2, context_size=4096)


def test_loopback_requests_ignore_configured_http_proxy(fake_ollama, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.invalid:8080")
    monkeypatch.setenv("http_proxy", "http://proxy.example.invalid:8080")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    generator = make_generator(fake_ollama)
    assert generator.generate([{"role": "user", "content": "Synthetic."}]) == "Local reply."


def test_http_redirect_is_not_followed_to_an_unapproved_host(fake_ollama):
    fake_ollama.tags_redirect = True
    with pytest.raises(OllamaHTTPFailure) as error:
        make_generator(fake_ollama)
    assert "HTTP error (302)" in error.value.safe_message


def test_timeout_has_a_safe_message(fake_ollama):
    fake_ollama.delay = 0.08
    with pytest.raises(OllamaTimeout, match="too long"):
        make_generator(fake_ollama, timeout=0.01)


def test_bad_json_is_rejected_without_exposing_response_body(fake_ollama):
    fake_ollama.tags_body = b"not-json-private-body"
    with pytest.raises(OllamaBadResponse, match="invalid response") as error:
        make_generator(fake_ollama)
    assert "not-json-private-body" not in error.value.safe_message


def test_bad_chat_json_is_rejected(fake_ollama):
    generator = make_generator(fake_ollama)
    fake_ollama.chat_body = b"invalid-chat-json"
    with pytest.raises(OllamaBadResponse, match="invalid response"):
        generator.generate([{"role": "user", "content": "Synthetic."}])


def test_http_failure_is_safe_and_does_not_include_server_body(fake_ollama):
    fake_ollama.tags_status = 500
    fake_ollama.tags_body = b"private response body"
    with pytest.raises(OllamaHTTPFailure, match=r"HTTP error \(500\)") as error:
        make_generator(fake_ollama)
    assert "private response body" not in error.value.safe_message


def test_non_loopback_url_is_refused_without_opt_in():
    with pytest.raises(OllamaRemoteRefused) as error:
        OllamaGenerator({}, url="http://ollama.example.invalid:11434", model=TAG,
                        timeout_seconds=0.2, context_size=4096)
    assert "Remote Ollama URLs are disabled" in error.value.safe_message


def test_ollama_backend_is_recorded_and_labelled_outside_research_outputs():
    record = {
        "patient_summary": "A short synthetic summary.", "caregiver_checklist": ["Review the synthetic care plan."],
        "child_explanation": "A safe synthetic explanation.", "entities": [], "regimens": [],
        "metadata": {"backend": "ollama", "model_id": TAG, "model_hash": f"ollama_digest:{DIGEST}"},
    }
    built = build_output(record, "Synthetic source.")
    assert built["flags"]["backend"] == "ollama"
    assert built["flags"]["model_id"] == TAG
    assert built["flags"]["model_hash"] == f"ollama_digest:{DIGEST}"
    assert _disclaimer_for_backend(built["flags"]) == _disclaimer_for_backend({"backend": "llama_cpp"})
    assert "Ollama" not in _disclaimer_for_backend(built["flags"])


def test_ollama_failure_marks_job_failed_with_safe_message_and_no_exception_details(conn, ctx, settings, world, caplog):
    owner = world.user("Synthetic Owner")
    profile = world.profile(owner)
    class FailingPipeline:
        def run(self, *_args, **_kwargs):
            raise OllamaTimeout()

    runner = JobRunner(settings, ctx, pipeline_factory=FailingPipeline, isolation="thread")
    try:
        note = notes.add_note(conn, ctx, None, owner, profile, title="Synthetic", text="Synthetic test note.")
        runner.process(note["id"])
        failed = conn.execute("SELECT status,error_message FROM notes WHERE id = ?", (note["id"],)).fetchone()
        assert failed["status"] == "failed"
        assert failed["error_message"] == OllamaTimeout.safe_message
        assert "Synthetic test note" not in caplog.text
        assert "Traceback" not in caplog.text
    finally:
        runner.shutdown()


def test_ollama_uses_bounded_process_isolation_by_default():
    from app.jobs import JobRunner

    runner = JobRunner(Settings(backend="ollama", job_timeout_seconds=17), pipeline_factory=lambda: None)
    assert runner.isolation == "process"
    assert runner.job_timeout == 17


def test_ollama_demo_preflight_selects_model_and_launches_fixed_port(monkeypatch, capsys):
    import app.ollama_demo as demo

    settings = Settings(backend="ollama", ollama_model=TAG, ollama_url="http://127.0.0.1:11434",
                        ollama_timeout_seconds=120, job_timeout_seconds=1200)   # the demo's budget-safe values
    monkeypatch.setattr(demo.Settings, "from_env", classmethod(lambda cls: settings))
    seen = []
    monkeypatch.setattr(demo, "build_pipeline", lambda value: seen.append(value) or object())
    launches = []

    class Launched(Exception):
        pass

    def execvpe(executable, args, env):
        launches.append((executable, args, env))
        raise Launched()

    monkeypatch.setattr(demo.os, "execvpe", execvpe)
    with pytest.raises(Launched):
        demo.main()
    assert seen == [settings]
    assert launches[0][1][-5:] == ["--host", "127.0.0.1", "--port", "8001", "--no-server-header"]
    assert "Preflight checked connectivity and model availability only" in capsys.readouterr().out


def test_ollama_demo_preflight_stops_on_model_error_without_launching(monkeypatch, capsys):
    import app.ollama_demo as demo

    settings = Settings(backend="ollama", ollama_model=TAG, job_timeout_seconds=1200)   # passes the budget check
    monkeypatch.setattr(demo.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(demo, "build_pipeline", lambda _settings: (_ for _ in ()).throw(OllamaModelMissing(TAG, [])))
    monkeypatch.setattr(demo.os, "execvpe", lambda *_args: pytest.fail("must not launch"))
    assert demo.main() == 2
    assert TAG in capsys.readouterr().err


@pytest.mark.slow
def test_real_ollama_is_available_only_when_opted_in():
    if os.environ.get("APP_RUN_SLOW") != "1":
        pytest.skip("set APP_RUN_SLOW=1 to use a real local Ollama service")
    url = os.environ.get("APP_OLLAMA_URL", "http://127.0.0.1:11434")
    model = os.environ.get("APP_OLLAMA_MODEL")
    if not model:
        pytest.skip("set APP_OLLAMA_MODEL to an installed Ollama tag")
    try:
        generator = OllamaGenerator({"temperature": 0, "top_p": 0.9, "seed": 42}, url=url,
                                    model=model, timeout_seconds=float(os.environ.get("APP_OLLAMA_TIMEOUT_SECONDS", "120")),
                                    context_size=4096)
    except Exception as exc:
        pytest.skip(f"real Ollama is not reachable or the configured model is unavailable ({type(exc).__name__})")
    assert generator.generate([{"role": "user", "content": "Reply with one word: ready"}], max_new_tokens=8)
