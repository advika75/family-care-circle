"""Password hashing and secret tokens, using only the standard library.

What this module does
---------------------
* Passwords: ``hashlib.scrypt`` with a random 16-byte per-user salt. The cost parameters and salt are stored
  in the encoded hash (``scrypt$N$r$p$salt$hash``), so parameters can be raised later without breaking old
  hashes. Comparison is constant-time (``hmac.compare_digest``). Minimum length 12, no composition rules.
* Tokens (session tokens, invitation codes): generated with ``secrets``; only a SHA-256 digest is stored in
  the database, never the token itself. Tokens are high-entropy random values, so a plain digest is
  sufficient (no salt or slow hash is needed for values that cannot be guessed or looked up in a wordlist).

What it does not do
-------------------
No home-made crypto, no password strength meter, no breached-password check (that needs network access).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.config import Settings
from app.errors import ValidationFailed

_SCRYPT_MAXMEM = 128 * 1024 * 1024  # N=2**15, r=8 needs ~32 MiB; leave headroom (OpenSSL default cap is 32 MiB)
_DKLEN = 32
_SALT_BYTES = 16


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def validate_password(password: str, settings: Settings) -> None:
    """Raise ValidationFailed unless the password meets the length rule (and nothing else)."""
    if not isinstance(password, str) or len(password) < settings.min_password_length:
        raise ValidationFailed({"password": f"Use at least {settings.min_password_length} characters."})
    if len(password) > settings.max_password_length:
        raise ValidationFailed({"password": f"Use at most {settings.max_password_length} characters."})


def hash_password(password: str, settings: Settings) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=settings.scrypt_n, r=settings.scrypt_r, p=settings.scrypt_p,
        maxmem=_SCRYPT_MAXMEM, dklen=_DKLEN,
    )
    return f"scrypt${settings.scrypt_n}${settings.scrypt_r}${settings.scrypt_p}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check against an encoded hash. Malformed hashes simply fail."""
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
            maxmem=_SCRYPT_MAXMEM, dklen=_DKLEN,
        )
        return hmac.compare_digest(digest, _unb64(expected))
    except (ValueError, TypeError):
        return False


def dummy_verify(password: str, settings: Settings) -> None:
    """Spend roughly the time of a real verification, for logins with an unknown email (timing parity)."""
    verify_password(password, _dummy_hash(settings))


_DUMMY: dict[tuple[int, int, int], str] = {}


def _dummy_hash(settings: Settings) -> str:
    key = (settings.scrypt_n, settings.scrypt_r, settings.scrypt_p)
    if key not in _DUMMY:
        _DUMMY[key] = hash_password(secrets.token_urlsafe(16), settings)
    return _DUMMY[key]


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token (256 bits by default)."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 hex digest used to store session tokens and invitation codes."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
