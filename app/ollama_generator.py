"""Optional Ollama generator for the web app only.

Uses Ollama's non-streaming chat API and the standard library. Request and response bodies are never logged.
Ollama applies the installed model's own chat template, which may differ from llama.cpp's GGUF template.
"""

from __future__ import annotations

import ipaddress
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from typing import Any

from src.generator import Generator, Messages


class OllamaError(RuntimeError):
    """Safe, user-displayable Ollama failure; never contains request or response bodies."""

    safe_message = "The Ollama model could not prepare this note. Please check the local Ollama service."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.safe_message)


class OllamaUnavailable(OllamaError):
    safe_message = "Ollama is not responding. Start Ollama and try adding this note again."


class OllamaTimeout(OllamaError):
    safe_message = "Ollama took too long to respond. Try again or ask whoever runs the app to check the model."


class OllamaHTTPFailure(OllamaError):
    def __init__(self, status: int):
        self.safe_message = f"Ollama returned an HTTP error ({status}). Check the Ollama service and model."
        super().__init__(self.safe_message)


class OllamaBadResponse(OllamaError):
    safe_message = "Ollama returned an invalid response. Check the Ollama service and try again."


class OllamaModelMissing(OllamaError):
    def __init__(self, tag: str, installed: list[str]):
        listing = ", ".join(installed) if installed else "none"
        self.safe_message = f"Ollama model '{tag}' is not installed. Installed model tags: {listing}. Pull the model and retry."
        super().__init__(self.safe_message)


class OllamaModelRequired(OllamaError):
    def __init__(self, installed: list[str]):
        listing = ", ".join(installed) if installed else "none"
        self.safe_message = ("APP_OLLAMA_MODEL is not set. Installed Ollama model tags: "
                             f"{listing}. Set APP_OLLAMA_MODEL to one of these tags and restart the app.")
        super().__init__(self.safe_message)


class OllamaRemoteRefused(OllamaError):
    safe_message = "Remote Ollama URLs are disabled. Use a loopback URL or explicitly set APP_OLLAMA_ALLOW_REMOTE=1."


class OllamaConfigurationError(OllamaError):
    safe_message = "APP_OLLAMA_URL must be a valid HTTP(S) URL without embedded credentials."


class _NoRedirect(HTTPRedirectHandler):
    """Keep the configured loopback/remote boundary from being bypassed by a server redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _checked_base_url(url: str, allow_remote: bool) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if parts.scheme not in {"http", "https"} or not host or parts.username or parts.password:
            raise ValueError
        if parts.query or parts.fragment:
            raise ValueError
        loopback = host.lower().rstrip(".") == "localhost"
        if not loopback:
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = False
        if not loopback and not allow_remote:
            raise OllamaRemoteRefused()
        return url.rstrip("/")
    except OllamaError:
        raise
    except (TypeError, ValueError):
        raise OllamaConfigurationError() from None


class OllamaGenerator(Generator):
    """Generator-compatible adapter for a locally served Ollama model."""

    backend = "ollama"

    def __init__(self, generation_cfg: dict[str, Any], *, url: str, model: str | None,
                 timeout_seconds: float, context_size: int, allow_remote: bool = False) -> None:
        self.base_url = _checked_base_url(url, allow_remote)
        self.timeout_seconds = float(timeout_seconds)
        self.context_size = int(context_size)
        tags = self._list_tags()
        names = [str(item.get("name") or item.get("model")) for item in tags
                 if isinstance(item, dict) and (item.get("name") or item.get("model"))]
        if not model:
            raise OllamaModelRequired(names)
        selected = next((item for item in tags if isinstance(item, dict)
                         and model in (item.get("name"), item.get("model"))), None)
        if selected is None:
            raise OllamaModelMissing(model, names)
        digest = selected.get("digest")
        if not isinstance(digest, str) or not digest:
            raise OllamaBadResponse()
        super().__init__(model, generation_cfg)
        self.model_hash = f"ollama_digest:{digest}"

    def _request_json(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers={"Accept": "application/json", **(
            {"Content-Type": "application/json"} if body is not None else {})},
                          method="GET" if body is None else "POST")
        try:
            opener = build_opener(ProxyHandler({}), _NoRedirect())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise OllamaHTTPFailure(status) from None
        except (TimeoutError, URLError) as exc:
            if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError):
                raise OllamaTimeout() from None
            raise OllamaUnavailable() from None
        except OSError:
            raise OllamaUnavailable() from None
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OllamaBadResponse() from None
        if not isinstance(value, dict):
            raise OllamaBadResponse()
        return value

    def _list_tags(self) -> list[dict[str, Any]]:
        response = self._request_json("/api/tags")
        models = response.get("models")
        if not isinstance(models, list) or any(not isinstance(item, dict) for item in models):
            raise OllamaBadResponse()
        return models

    def generate(self, messages: Messages, **overrides: Any) -> str:
        p = self.params(**overrides)
        response = self._request_json("/api/chat", {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": p["temperature"],
                "top_p": p["top_p"],
                "seed": self.seed,
                "num_predict": p["max_new_tokens"],
                "num_ctx": self.context_size,
            },
        })
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OllamaBadResponse()
        self.last_truncated = response.get("done_reason") == "length"
        return content
