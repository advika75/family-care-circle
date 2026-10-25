"""Server-rendered HTML pages: public pages, accounts, care-circle creation and joining.

Permissions are decided by the service layer (``app.permissions.can`` and the service functions); these routes
only translate form posts and errors into pages. Every state-changing form carries a CSRF token.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response

from app import accounts, circle, ids, permissions as perm
from app.clientip import resolve_client_ip
from app.errors import (AccountNotCreated, AlreadyMember, InvalidCredentials, InvalidIdOrCode, InvitationExpired,
                        InvitationUsed, MembershipPending, MembershipRevoked, NotFound, Throttled, ValidationFailed)
from app.web.deps import SESSION_COOKIE, current_user, get_db
from app.web.render import (LoginRequired, clear_session_cookie, redirect, render, safe_next, set_session_cookie,
                            verify_page_csrf)

router = APIRouter()


def client_ip(request: Request) -> str:
    """The client's address; X-Forwarded-For counts only behind a proxy listed in APP_TRUSTED_PROXIES (F-05)."""
    return resolve_client_ip(request.client.host if request.client else "", request.headers.get("x-forwarded-for"),
                             request.app.state.settings.trusted_proxies)


def need_user(user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    if user is None:
        raise LoginRequired()
    return user


# ------------------------------------------------------------------------------------------- public
@router.get("/")
def welcome(request: Request, conn: sqlite3.Connection = Depends(get_db), user=Depends(current_user)) -> Response:
    return render(request, "welcome.html", conn=conn, user=user)


def _auth_form(request: Request, template: str, *, values=None, errors=None, form_error="", status_code=200,
               next_value="") -> Response:
    nxt = safe_next(next_value) if next_value else ""
    return render(request, template, values=values or {}, errors=errors or {}, form_error=form_error,
                  next=nxt, next_param=nxt if nxt in ("/profiles/new", "/join") else "", status_code=status_code)


@router.get("/signup")
def signup_form(request: Request, next: str = "", conn=Depends(get_db), user=Depends(current_user)) -> Response:
    if user:
        return redirect("/profiles")
    return _auth_form(request, "signup.html", next_value=next)


@router.post("/signup")
def signup_submit(request: Request, display_name: str = Form(""), email: str = Form(""), password: str = Form(""),
                  next: str = Form(""), csrf_token: str = Form(""), conn=Depends(get_db)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=False)
    values = {"display_name": display_name, "email": email}
    try:
        user = accounts.signup(conn, request.app.state.ctx, email=email, display_name=display_name, password=password,
                               client_ip=client_ip(request))
    except Throttled as exc:
        return _auth_form(request, "signup.html", values=values, form_error=exc.message, status_code=429, next_value=next)
    except ValidationFailed as exc:
        return _auth_form(request, "signup.html", values=values, errors=exc.errors, status_code=422, next_value=next)
    except AccountNotCreated as exc:
        return _auth_form(request, "signup.html", values=values, form_error=exc.message, status_code=400, next_value=next)
    token = accounts.start_session(conn, request.app.state.ctx, user["id"])
    response = redirect(safe_next(next))
    set_session_cookie(response, request, token)
    return response


@router.get("/login")
def login_form(request: Request, next: str = "", conn=Depends(get_db), user=Depends(current_user)) -> Response:
    if user:
        return redirect("/profiles")
    return _auth_form(request, "login.html", next_value=next)


@router.post("/login")
def login_submit(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form(""),
                 csrf_token: str = Form(""), conn=Depends(get_db)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=False)
    try:
        _, token = accounts.login(conn, request.app.state.ctx, email=email, password=password, client_ip=client_ip(request))
    except (InvalidCredentials, Throttled) as exc:
        return _auth_form(request, "login.html", values={"email": email}, form_error=exc.message,
                          status_code=429 if isinstance(exc, Throttled) else 401, next_value=next)
    response = redirect(safe_next(next))
    set_session_cookie(response, request, token)
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(""), conn=Depends(get_db), user=Depends(current_user)) -> Response:
    if user is not None:
        verify_page_csrf(request, csrf_token, authenticated=True)
        accounts.logout(conn, request.cookies.get(SESSION_COOKIE))
    response = redirect("/")
    clear_session_cookie(response, request)
    return response


# --------------------------------------------------------------------------------------- my circles
@router.get("/profiles")
def my_circles(request: Request, conn=Depends(get_db), user=Depends(need_user)) -> Response:
    return render(request, "profiles.html", conn=conn, user=user, circles=circle.list_profiles_for_user(conn, user["id"]))


# Fields shown on each step of the create-profile form, in order.
STEP_FIELDS = {1: ("display_name", "preferred_name", "year_of_birth"), 2: ("care_notes",), 3: ("relationship_label",)}


def _step_of(field: str) -> int:
    return next(s for s, fs in STEP_FIELDS.items() if field in fs)


def _profile_form(request: Request, conn, user, step: int, values: dict, errors: dict | None = None, status_code: int = 200,
                  form_error: str = "") -> Response:
    return render(request, "profile_new.html", conn=conn, user=user, step=step, values=values, errors=errors or {},
                  relationship_labels=circle.RELATIONSHIP_LABELS, status_code=status_code, form_error=form_error)


@router.get("/profiles/new")
def new_profile_form(request: Request, conn=Depends(get_db), user=Depends(need_user)) -> Response:
    return _profile_form(request, conn, user, 1, {})


@router.post("/profiles/new")
def new_profile_submit(request: Request, step: int = Form(1), action: str = Form("next"), display_name: str = Form(""),
                       preferred_name: str = Form(""), year_of_birth: str = Form(""), care_notes: str = Form(""),
                       relationship_label: str = Form(""), csrf_token: str = Form(""), conn=Depends(get_db),
                       user=Depends(need_user)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=True)
    ctx = request.app.state.ctx
    values = {"display_name": display_name.strip(), "preferred_name": preferred_name.strip(),
              "year_of_birth": year_of_birth.strip(), "care_notes": care_notes.strip(), "relationship_label": relationship_label}
    step = step if step in (1, 2, 3, 4) else 1
    if action == "back":
        return _profile_form(request, conn, user, max(1, step - 1), values)
    if action == "next" and step in STEP_FIELDS:
        errors = circle.check_profile_fields(ctx, values, STEP_FIELDS[step])
        if errors:
            return _profile_form(request, conn, user, step, values, errors, 422)
        return _profile_form(request, conn, user, step + 1, values)
    if action == "create" and step == 4:
        try:
            profile = circle.create_profile(conn, ctx, user, **values)
        except ValidationFailed as exc:               # tampered or stale hidden fields: send them to the first bad step
            first = min(_step_of(f) for f in exc.errors)
            return _profile_form(request, conn, user, first, values, exc.errors, 422)
        return redirect(f"/p/{profile['patient_id']}/created")
    return _profile_form(request, conn, user, 1, values)


@router.get("/p/{patient_id}/created")
def profile_created(patient_id: str, request: Request, conn=Depends(get_db), user=Depends(need_user)) -> Response:
    profile = circle.get_profile(conn, patient_id)
    m = perm.get_membership(conn, user["id"], profile["id"]) if profile else None
    if profile is None or m is None or m["role"] != perm.CREATOR or m["status"] != perm.ACTIVE:
        raise NotFound()
    return render(request, "profile_created.html", conn=conn, user=user, profile=profile, circle_info=(profile, m))


# ------------------------------------------------------------------------------------------------ join
def _join_form(request, conn, user, *, values=None, errors=None, result=None, status_code=200) -> Response:
    return render(request, "join.html", conn=conn, user=user, values=values or {}, errors=errors or {}, result=result,
                  relationship_labels=circle.RELATIONSHIP_LABELS, status_code=status_code)


@router.get("/join")
def join_form(request: Request, conn=Depends(get_db), user=Depends(need_user)) -> Response:
    return _join_form(request, conn, user)


@router.post("/join")
def join_submit(request: Request, patient_id: str = Form(""), code: str = Form(""), relationship_label: str = Form(""),
                csrf_token: str = Form(""), conn=Depends(get_db), user=Depends(need_user)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=True)
    values = {"patient_id": patient_id, "code": code, "relationship_label": relationship_label}
    errors = {}
    if not patient_id.strip():
        errors["patient_id"] = "Enter the patient ID."
    if not code.strip():
        errors["code"] = "Enter the invitation code."
    if relationship_label not in circle.RELATIONSHIP_LABELS:
        errors["relationship_label"] = "Choose how you are related to the patient."
    if errors:
        return _join_form(request, conn, user, values=values, errors=errors, status_code=422)
    pid = ids.normalize_patient_id(patient_id) or ""
    try:
        circle.join(conn, request.app.state.ctx, user, patient_id=patient_id, code=code,
                    relationship_label=relationship_label, client_ip=client_ip(request))
    except InvalidIdOrCode as exc:
        return _join_form(request, conn, user, values={**values, "code": ""}, status_code=400,
                          result={"kind": "error", "title": "That ID and code do not match", "message": exc.message})
    except InvitationExpired as exc:
        return _join_form(request, conn, user, values={**values, "code": ""}, status_code=400,
                          result={"kind": "error", "title": "This invitation has expired", "message": exc.message})
    except InvitationUsed as exc:
        return _join_form(request, conn, user, values={**values, "code": ""}, status_code=400,
                          result={"kind": "error", "title": "This invitation has already been used", "message": exc.message})
    except Throttled as exc:
        return _join_form(request, conn, user, values={**values, "code": ""}, status_code=429,
                          result={"kind": "error", "title": "Too many attempts", "message": exc.message})
    except MembershipPending:
        return _join_form(request, conn, user, values={}, result={"kind": "pending", "patient_id": pid})
    except AlreadyMember as exc:
        return _join_form(request, conn, user, values={}, result={"kind": "member", "message": exc.message, "patient_id": pid})
    except MembershipRevoked as exc:
        return _join_form(request, conn, user, values={}, status_code=403, result={"kind": "revoked", "message": exc.message})
    except ValidationFailed as exc:
        return _join_form(request, conn, user, values=values, errors=exc.errors, status_code=422)
    return redirect(f"/p/{pid}")
