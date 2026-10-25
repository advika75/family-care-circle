"""Template rendering, anonymous CSRF, session cookies and navigation context for HTML pages."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import circle, csrf, permissions as perm, security
from app.web import present
from app.web.deps import SESSION_COOKIE

APP_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))   # autoescape is on for .html templates

ANON_COOKIE = "fcc_anon"
SAFE_NEXT = ("/profiles", "/profiles/new", "/join")   # the only places a login/signup may send you on


class CsrfFailed(Exception):
    """A form was submitted without a valid CSRF token."""


class StatusPage(Exception):
    """The viewer's membership is pending or revoked: show only the status page."""

    def __init__(self, profile: sqlite3.Row, membership: sqlite3.Row) -> None:
        self.profile, self.membership = profile, membership


class LoginRequired(Exception):
    """A page needs a logged-in user."""

    def __init__(self, next_path: str = "") -> None:
        self.next_path = next_path


def safe_next(value: str | None) -> str:
    """Allow-list, never an arbitrary URL: prevents open redirects."""
    return value if value in SAFE_NEXT else "/profiles"


def human_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return value
    return dt.strftime("%-d %b %Y, %H:%M UTC")


templates.env.filters["human_time"] = human_time
templates.env.filters["paragraphs"] = present.paragraphs


# ---------------------------------------------------------------------------------------------- CSRF
def _anon_value(request: Request) -> tuple[str, bool]:
    existing = request.cookies.get(ANON_COOKIE)
    if existing and len(existing) >= 20:
        return existing, False
    return secrets.token_urlsafe(24), True


def page_csrf_token(request: Request, authenticated: bool) -> tuple[str, str | None]:
    """(token to embed in a form, new anonymous cookie value to set or None)."""
    key = request.app.state.settings.secret_key
    if authenticated:
        session = request.cookies.get(SESSION_COOKIE, "")
        return csrf.make_token(key, security.hash_token(session)), None
    value, is_new = _anon_value(request)
    return csrf.make_token(key, "anon:" + value), (value if is_new else None)


def verify_page_csrf(request: Request, supplied: str | None, authenticated: bool) -> None:
    key = request.app.state.settings.secret_key
    if authenticated:
        session = request.cookies.get(SESSION_COOKIE, "")
        ok = bool(session) and csrf.verify_token(key, security.hash_token(session), supplied)
    else:
        value = request.cookies.get(ANON_COOKIE, "")
        ok = bool(value) and csrf.verify_token(key, "anon:" + value, supplied)
    if not ok:
        raise CsrfFailed()


# ------------------------------------------------------------------------------------------- cookies
def set_session_cookie(response: Response, request: Request, token: str) -> None:
    s = request.app.state.settings
    response.set_cookie(SESSION_COOKIE, token, max_age=s.session_ttl_hours * 3600, httponly=True, samesite="lax",
                        secure=s.https, path="/")


def clear_session_cookie(response: Response, request: Request) -> None:
    s = request.app.state.settings
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=s.https)


# ------------------------------------------------------------------------------------------ rendering
def nav_context(conn: sqlite3.Connection | None, user: sqlite3.Row | None, path: str,
                circle_info: tuple[sqlite3.Row, sqlite3.Row] | None = None) -> dict[str, Any]:
    """Navigation for the current page. Links inside a care circle are chosen with ``permissions.decide`` so a role
    is only ever offered pages it may open."""
    if user is None or conn is None:
        return {"links": [], "circles": [], "circle": None, "current": path.strip("/")}
    circles = circle.list_profiles_for_user(conn, user["id"])
    info = None
    items: list[dict[str, Any]] = []
    if circle_info is not None:
        profile, m = circle_info
        base = f"/p/{profile['patient_id']}"
        info = {"name": circle.patient_label(profile, m["role"]), "patient_id": profile["patient_id"], "role": m["role"]}

        def allowed(action: str) -> bool:
            return perm.decide(m["role"], m["status"], bool(m["can_add_notes"]), action)
        items = [{"href": base, "label": "Dashboard", "icon": "home", "current": path == base},
                 {"href": f"{base}/summaries", "label": "Summaries", "icon": "sparkle", "current": path.startswith(f"{base}/summaries")},
                 {"href": f"{base}/circle", "label": "Care circle", "icon": "users", "current": path.startswith(f"{base}/circle")}]
        if allowed(perm.ADD_NOTE):
            items.append({"href": f"{base}/notes", "label": "Notes", "icon": "file-text", "current": path.startswith(f"{base}/notes")})
        if allowed(perm.VIEW_INFO):
            items.append({"href": f"{base}/info", "label": "Info", "icon": "info", "current": path.startswith(f"{base}/info")})
    else:
        items.append({"href": "/profiles", "label": "My care circles", "icon": "home", "current": path == "/profiles"})
        items.append({"href": "/join", "label": "Join", "icon": "key", "current": path == "/join"})
    items.append({"href": "/settings", "label": "Settings", "icon": "settings", "current": path == "/settings"})
    return {"links": items, "circles": circles, "circle": info, "current": path.strip("/")}


def render(request: Request, name: str, *, conn: sqlite3.Connection | None = None, user: sqlite3.Row | None = None,
           status_code: int = 200, circle_info: tuple[sqlite3.Row, sqlite3.Row] | None = None, **context: Any) -> Response:
    token, new_anon = page_csrf_token(request, authenticated=user is not None)
    context.update(request=request, user=user, csrf_token=token, status_code=status_code,
                   nav=nav_context(conn, user, request.url.path, circle_info))
    response = templates.TemplateResponse(request, name, context, status_code=status_code)
    if new_anon:
        response.set_cookie(ANON_COOKIE, new_anon, httponly=True, samesite="lax", secure=request.app.state.settings.https,
                            path="/", max_age=3600)
    return response


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)       # 303: the browser follows with GET after a POST
