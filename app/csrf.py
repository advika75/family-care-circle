"""CSRF tokens (signed, bound to a session).

A token is ``HMAC-SHA256(secret_key, binder)`` where ``binder`` is the SHA-256 digest of the session token
(for logged-in users) or the value of a random anonymous cookie (for the login/signup forms). A cross-site
page can neither read the token (same-origin policy) nor forge it (it does not know the server key), and a
token for one session is useless for another. The same check is used for every state-changing request.
SameSite=Lax cookies are an additional, independent layer.
"""

from __future__ import annotations

import hashlib
import hmac


def make_token(secret_key: bytes, binder: str) -> str:
    return hmac.new(secret_key, b"csrf-v1|" + binder.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token(secret_key: bytes, binder: str, token: str | None) -> bool:
    if not binder or not token:
        return False
    return hmac.compare_digest(make_token(secret_key, binder), token)
