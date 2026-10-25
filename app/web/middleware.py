"""Pure-ASGI middleware: security headers and a request body size limit.

Security headers
  * Content-Security-Policy without 'unsafe-inline': no inline scripts or styles anywhere (templates must use
    external files). frame-ancestors 'none' and X-Frame-Options DENY stop framing.
  * X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer (patient IDs appear in URLs, so referrers
    must not leak them), Cache-Control: no-store (pages and API responses contain health information).
  * Strict-Transport-Security only when APP_HTTPS=1 (the app does not terminate TLS itself).

Body limit
  Rejects request bodies above ``max_bytes`` with 413 while streaming, before the framework buffers or spools
  them, so an oversized upload cannot fill the disk.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class SecurityHeadersMiddleware:
    def __init__(self, app: Callable, https: bool = False) -> None:
        self.app, self.https = app, https

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in {
                    b"content-security-policy", b"x-content-type-options", b"x-frame-options", b"referrer-policy",
                    b"cache-control", b"permissions-policy"}]
                is_static = scope.get("path", "").startswith("/static/")
                headers += [
                    (b"content-security-policy", CSP.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
                    (b"cache-control", b"no-cache" if is_static else b"no-store"),
                ]
                if self.https:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    def __init__(self, app: Callable, max_bytes: int = 256 * 1024) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return
        seen = 0
        too_big = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal seen, too_big
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    too_big = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        started = False

        async def guarded_send(message: dict[str, Any]) -> None:
            nonlocal started
            if too_big and not started:
                started = True
                await self._reject(send)
                return
            if message["type"] == "http.response.start":
                started = True
            if too_big and started and message["type"] == "http.response.body" and message.get("_rejected"):
                return
            await send(message)

        await self.app(scope, limited_receive, guarded_send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps({"error": {"code": "too_large", "message": "That upload is too large."}}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
