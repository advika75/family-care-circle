"""Configuration from environment variables. Secrets never live in the repository.

Environment variables
---------------------
APP_BACKEND          mock | llama_cpp | ollama (default mock)
APP_OLLAMA_URL        Ollama base URL (default http://127.0.0.1:11434)
APP_OLLAMA_MODEL      installed Ollama tag (required for generation)
APP_OLLAMA_TIMEOUT_SECONDS  per-request timeout (default 120)
APP_OLLAMA_ALLOW_REMOTE     1 permits a non-loopback Ollama host (default 0)
APP_DB_PATH          SQLite file (default app/var/familycare.sqlite3)
APP_HTTPS            1 marks the session cookie ``Secure`` (set it when served over HTTPS)
APP_SECRET_KEY       key for CSRF tokens. If unset a random key is generated per process (anonymous CSRF
                     tokens then stop working after a restart; sessions are in the database and are unaffected)
APP_SESSION_TTL_HOURS  absolute session lifetime (default 168 = 7 days)
APP_INVITE_TTL_DAYS    invitation lifetime (default 7)
APP_JOB_TIMEOUT_SECONDS  a note's generation is stopped after this long (default 900)
APP_TRUSTED_PROXIES    comma-separated proxy addresses whose X-Forwarded-For is trusted (default none)
APP_MAX_PENDING_PER_CIRCLE / APP_MAX_PENDING_TOTAL  queue caps (default 3 / 20)
APP_JOB_ISOLATION      auto | thread | process (default auto: process for llama_cpp and ollama, thread for mock)
"""

from __future__ import annotations

import math
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKENDS = ("mock", "llama_cpp", "ollama")
# scrypt cost: the defaults below (N=2**15, r=8, p=1) are used in production. Tests build Settings
# directly with a tiny N for speed; the parameters are stored inside every hash, so verification always
# uses the parameters the hash was created with.


@dataclass(frozen=True)
class Settings:
    db_path: Path = REPO_ROOT / "app" / "var" / "familycare.sqlite3"
    backend: str = "mock"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str | None = None
    ollama_timeout_seconds: float = 120.0
    ollama_allow_remote: bool = False
    https: bool = False
    secret_key: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)
    session_ttl_hours: int = 168
    invite_ttl_days: int = 7
    scrypt_n: int = 2 ** 15
    scrypt_r: int = 8
    scrypt_p: int = 1
    min_password_length: int = 12
    max_password_length: int = 1024
    max_note_chars: int = 6_000   # F-02: measured cut-off is ~8,000 chars (retry prompt); see README
    job_timeout_seconds: int = 900      # a generation running longer than this is killed (process mode)
    trusted_proxies: tuple[str, ...] = ()   # exact addresses of reverse proxies whose X-Forwarded-For may be trusted
    max_pending_per_circle: int = 3     # notes one care circle may have waiting or running at once
    max_pending_total: int = 20         # notes waiting or running across the whole app (the single worker's queue)
    job_isolation: str = "auto"         # auto | thread | process; auto = process for real model backends, thread for mock

    @property
    def effective_job_isolation(self) -> str:
        if self.job_isolation == "auto":
            return "process" if self.backend in ("llama_cpp", "ollama") else "thread"
        return self.job_isolation

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        backend = e.get("APP_BACKEND", "mock").strip() or "mock"
        if backend not in BACKENDS:
            raise ValueError(f"APP_BACKEND must be one of {BACKENDS}, got {backend!r}")
        key = e.get("APP_SECRET_KEY")
        kwargs: dict = {}
        if key:
            kwargs["secret_key"] = key.encode("utf-8")
        isolation = e.get("APP_JOB_ISOLATION", "auto").strip() or "auto"
        if isolation not in ("auto", "thread", "process"):
            raise ValueError(f"APP_JOB_ISOLATION must be auto, thread or process, got {isolation!r}")
        timeout = int(e.get("APP_JOB_TIMEOUT_SECONDS", "900"))
        if timeout < 1:
            raise ValueError("APP_JOB_TIMEOUT_SECONDS must be at least 1")
        session_ttl = int(e.get("APP_SESSION_TTL_HOURS", "168"))
        if session_ttl < 1:
            raise ValueError("APP_SESSION_TTL_HOURS must be at least 1")
        ollama_timeout = float(e.get("APP_OLLAMA_TIMEOUT_SECONDS", "120"))
        if not math.isfinite(ollama_timeout) or ollama_timeout <= 0:
            raise ValueError("APP_OLLAMA_TIMEOUT_SECONDS must be greater than 0")
        caps = {}
        for env_name, field_name, default in (("APP_MAX_PENDING_PER_CIRCLE", "max_pending_per_circle", "3"),
                                              ("APP_MAX_PENDING_TOTAL", "max_pending_total", "20")):
            caps[field_name] = int(e.get(env_name, default))
            if caps[field_name] < 1:
                raise ValueError(f"{env_name} must be at least 1")
        proxies = tuple(p.strip() for p in e.get("APP_TRUSTED_PROXIES", "").split(",") if p.strip())
        return cls(
            trusted_proxies=proxies, **caps, job_timeout_seconds=timeout, job_isolation=isolation,
            db_path=Path(e.get("APP_DB_PATH") or (REPO_ROOT / "app" / "var" / "familycare.sqlite3")),
            backend=backend,
            ollama_url=e.get("APP_OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/"),
            ollama_model=(e.get("APP_OLLAMA_MODEL", "").strip() or None),
            ollama_timeout_seconds=ollama_timeout,
            ollama_allow_remote=e.get("APP_OLLAMA_ALLOW_REMOTE", "0") == "1",
            https=e.get("APP_HTTPS", "0") == "1",
            session_ttl_hours=session_ttl,
            invite_ttl_days=int(e.get("APP_INVITE_TTL_DAYS", "7")),
            **kwargs,
        )
