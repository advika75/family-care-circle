"""Accounts and server-side sessions.

Sessions: a random 256-bit token is given to the browser (cookie set by the web layer); only its SHA-256
digest is stored. Sessions have an absolute expiry and are removed on logout, on "log out of all sessions",
on password change (all other sessions) and on account deletion.

Error messages are generic: a wrong password and an unknown email give the same message, and the unknown-email
path spends comparable time (``dummy_verify``). Signup with an existing email returns a generic refusal; with
no email delivery this cannot be made fully enumeration-proof (documented limitation).
"""

from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from datetime import timedelta

from app import security
from app.context import (Ctx, LOGIN_ATTEMPTS_PER_IP, LOGIN_FAILURES_PER_EMAIL, LOGIN_FAILURES_PER_IP,
                         LOGIN_FAILURES_PER_PAIR, SIGNUPS_PER_IP)
from app.db import iso, parse_iso, transaction
from app.errors import AccountNotCreated, InvalidCredentials, NotAllowed, Throttled, ValidationFailed

log = logging.getLogger("app.accounts")  # never log emails, passwords, tokens or note text

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
PUBLIC_USER_COLUMNS = "id, email, display_name, created_at"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def name_key(name: str) -> str:
    """Case-, spacing- and compatibility-insensitive form of a name, used only to notice members who share a name."""
    return " ".join(unicodedata.normalize("NFKC", name or "").casefold().split())


def clean_name(name: str, field: str = "display_name", maximum: int = 80) -> str:
    name = (name or "").strip()
    errors = {}
    if not name:
        errors[field] = "Please enter a name."
    elif len(name) > maximum:
        errors[field] = f"Use at most {maximum} characters."
    elif _CONTROL.search(name) or any(unicodedata.category(c) in ("Cf", "Zl", "Zp", "Co", "Cs") for c in name):
        # F-12: control, bidi-override, zero-width and other invisible "format" characters can make one name look like
        # another or reorder surrounding text, so they are refused.
        errors[field] = "That name contains characters that are not allowed."
    if errors:
        raise ValidationFailed(errors)
    return name


def signup(conn: sqlite3.Connection, ctx: Ctx, *, email: str, display_name: str, password: str,
           client_ip: str = "") -> sqlite3.Row:
    if client_ip:                                       # every attempt counts, accepted or not (F-07)
        key = f"signup:ip:{client_ip}"
        ctx.throttle.record_failure(key)
        if ctx.throttle.blocked(key, SIGNUPS_PER_IP + 1):
            raise Throttled()
    email = normalize_email(email)
    errors: dict[str, str] = {}
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    try:
        display_name = clean_name(display_name)
    except ValidationFailed as exc:
        errors.update(exc.errors)
    try:
        security.validate_password(password, ctx.settings)
    except ValidationFailed as exc:
        errors.update(exc.errors)
    if errors:
        raise ValidationFailed(errors)
    pw_hash = security.hash_password(password, ctx.settings)
    try:
        with transaction(conn):
            cur = conn.execute(
                "INSERT INTO users(email, display_name, password_hash, created_at) VALUES (?,?,?,?)",
                (email, display_name, pw_hash, iso(ctx.now())))
    except sqlite3.IntegrityError:
        raise AccountNotCreated() from None
    log.info("account created user_id=%s", cur.lastrowid)
    return conn.execute(f"SELECT {PUBLIC_USER_COLUMNS} FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def _create_session(conn: sqlite3.Connection, ctx: Ctx, user_id: int) -> str:
    token = security.new_token()
    now = ctx.now()
    conn.execute(
        "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (security.hash_token(token), user_id, iso(now), iso(now + timedelta(hours=ctx.settings.session_ttl_hours))))
    return token


def start_session(conn: sqlite3.Connection, ctx: Ctx, user_id: int) -> str:
    """Create a session for an already-authenticated user (used right after signup). Returns the cookie token."""
    with transaction(conn):
        return _create_session(conn, ctx, user_id)


def login(conn: sqlite3.Connection, ctx: Ctx, *, email: str, password: str, client_ip: str = "") -> tuple[sqlite3.Row, str]:
    """Return (user, session_token). Raises InvalidCredentials (generic) or Throttled."""
    email = normalize_email(email)
    # Throttle keys (F-04/F-07): wrong passwords are counted per (account, address), per account across all addresses,
    # and per address; every attempt from an address is also counted because each costs real CPU.
    pair_key, email_key = f"login:pair:{email}|{client_ip}", f"login:email:{email}"
    ip_key, attempt_key = f"login:ip:{client_ip}", f"login:attempts:{client_ip}"
    if client_ip:
        ctx.throttle.record_failure(attempt_key)
        if ctx.throttle.blocked(attempt_key, LOGIN_ATTEMPTS_PER_IP + 1):
            raise Throttled()
    if (ctx.throttle.blocked(pair_key, LOGIN_FAILURES_PER_PAIR) or ctx.throttle.blocked(email_key, LOGIN_FAILURES_PER_EMAIL)
            or (client_ip and ctx.throttle.blocked(ip_key, LOGIN_FAILURES_PER_IP))):
        raise Throttled()
    row = conn.execute(
        "SELECT id, email, display_name, created_at, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        security.dummy_verify(password or "", ctx.settings)
        ok = False
    else:
        ok = security.verify_password(password or "", row["password_hash"])
    if not ok:
        ctx.throttle.record_failure(pair_key, email_key, *([ip_key] if client_ip else []))
        raise InvalidCredentials()
    ctx.throttle.reset(pair_key)
    with transaction(conn):
        purge_expired_sessions(conn, ctx)                       # F-08: housekeeping on every successful login
        token = _create_session(conn, ctx, row["id"])
    log.info("login user_id=%s", row["id"])
    user = conn.execute(f"SELECT {PUBLIC_USER_COLUMNS} FROM users WHERE id = ?", (row["id"],)).fetchone()
    return user, token


def resolve_session(conn: sqlite3.Connection, ctx: Ctx, token: str | None) -> sqlite3.Row | None:
    """The user for a session token, or None if the token is unknown, expired or logged out."""
    if not token:
        return None
    th = security.hash_token(token)
    row = conn.execute(
        "SELECT s.id AS sid, s.expires_at AS expires_at, u.id AS id, u.email AS email, u.display_name AS display_name, "
        "u.created_at AS created_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (th,)).fetchone()
    if row is None:
        return None
    if parse_iso(row["expires_at"]) <= ctx.now():
        conn.execute("DELETE FROM sessions WHERE id = ?", (row["sid"],))
        return None
    return row


def logout(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (security.hash_token(token),))


def logout_all(conn: sqlite3.Connection, user_id: int, keep_token: str | None = None) -> int:
    """Delete every session of the user (optionally keeping the current one). Returns how many were removed."""
    if keep_token:
        cur = conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                           (user_id, security.hash_token(keep_token)))
    else:
        cur = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return cur.rowcount


def purge_expired_sessions(conn: sqlite3.Connection, ctx: Ctx) -> int:
    return conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (iso(ctx.now()),)).rowcount


def _password_ok(conn: sqlite3.Connection, user_id: int, password: str) -> bool:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None and security.verify_password(password or "", row["password_hash"])


def change_password(conn: sqlite3.Connection, ctx: Ctx, user: sqlite3.Row, *, current_password: str,
                    new_password: str, keep_token: str | None = None) -> str | None:
    """Change the password and end every session; return a FRESH session token when ``keep_token`` was given (F-09).

    The session used for the change is not kept: a new token is issued so a token that leaked earlier stops working.
    Wrong current password -> InvalidCredentials."""
    key = f"pwchange:user:{user['id']}"
    if ctx.throttle.blocked(key, LOGIN_FAILURES_PER_PAIR):
        raise Throttled()
    if not _password_ok(conn, user["id"], current_password):
        ctx.throttle.record_failure(key)
        raise InvalidCredentials("Your current password is not correct.")
    security.validate_password(new_password, ctx.settings)
    ctx.throttle.reset(key)
    new_hash = security.hash_password(new_password, ctx.settings)
    with transaction(conn):
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        logout_all(conn, user["id"])
        fresh = _create_session(conn, ctx, user["id"]) if keep_token else None
    log.info("password changed user_id=%s", user["id"])
    return fresh


def delete_account(conn: sqlite3.Connection, ctx: Ctx, user: sqlite3.Row, *, password: str) -> None:
    """Delete the account after re-entering the password. Refused while the user is the creator of any care
    circle (they must delete those first); memberships and sessions are removed by foreign-key cascade."""
    key = f"pwchange:user:{user['id']}"
    if ctx.throttle.blocked(key, LOGIN_FAILURES_PER_PAIR):
        raise Throttled()
    if not _password_ok(conn, user["id"], password):
        ctx.throttle.record_failure(key)
        raise InvalidCredentials("Your password is not correct.")
    owns = conn.execute(
        "SELECT 1 FROM memberships WHERE user_id = ? AND role = 'creator' LIMIT 1", (user["id"],)).fetchone()
    if owns:
        raise NotAllowed("You created at least one care circle. Delete it first (or it would be left with no owner).")
    with transaction(conn):
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    log.info("account deleted user_id=%s", user["id"])
