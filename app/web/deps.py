"""Request dependencies: database connection, current user, CSRF check, and circle scope."""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import Depends, HTTPException, Request

from app import accounts, circle, csrf, permissions as perm, security
from app.db import connect
from app.errors import MembershipPending, MembershipRevoked, NotFound

SESSION_COOKIE = "fcc_session"
CSRF_HEADER = "x-csrf-token"
CSRF_FIELD = "csrf_token"


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE)
    request.state.session_token = token
    return accounts.resolve_session(conn, request.app.state.ctx, token)


def require_user(user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


def csrf_token_for(request: Request) -> str | None:
    """The CSRF token for the current session (what a page would embed in its forms)."""
    token = getattr(request.state, "session_token", None) or request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return csrf.make_token(request.app.state.settings.secret_key, security.hash_token(token))


async def require_csrf(request: Request, user: sqlite3.Row = Depends(require_user)) -> sqlite3.Row:
    """State-changing requests must carry the session's CSRF token (header or form field)."""
    supplied = request.headers.get(CSRF_HEADER)
    if supplied is None and request.headers.get("content-type", "").split(";")[0] in (
            "application/x-www-form-urlencoded", "multipart/form-data"):
        form = await request.form()
        supplied = form.get(CSRF_FIELD)
        if not isinstance(supplied, str):
            supplied = None
    token = request.cookies.get(SESSION_COOKIE) or ""
    if not csrf.verify_token(request.app.state.settings.secret_key, security.hash_token(token) if token else "", supplied):
        raise HTTPException(status_code=403, detail="Your session could not be verified. Reload the page and try again.")
    return user


def circle_scope(patient_id: str, user: sqlite3.Row, conn: sqlite3.Connection) -> tuple[sqlite3.Row, sqlite3.Row]:
    """(profile, membership) for an ACTIVE member. Unknown ID and non-member are indistinguishable (404)."""
    profile = circle.get_profile(conn, patient_id)
    membership = perm.get_membership(conn, user["id"], profile["id"]) if profile is not None else None
    if profile is None or membership is None:
        raise NotFound()
    if membership["status"] == perm.PENDING:
        raise MembershipPending()
    if membership["status"] == perm.REVOKED:
        raise MembershipRevoked()
    return profile, membership
