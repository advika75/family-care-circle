"""Account settings and the /unauthorized page."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response

from app import accounts
from app.errors import AppError, InvalidCredentials, NotAllowed, Throttled, ValidationFailed
from app.web.deps import SESSION_COOKIE, current_user, get_db
from app.web.pages import need_user
from app.web.render import clear_session_cookie, redirect, render, set_session_cookie, verify_page_csrf

router = APIRouter()


def _settings_page(request, conn, user, *, notice=None, errors=None, status_code=200, open_section=""):
    return render(request, "settings.html", conn=conn, user=user, notice=notice, errors=errors or {},
                  status_code=status_code, open_section=open_section)


@router.get("/settings")
def settings_page(request: Request, conn=Depends(get_db), user=Depends(need_user)) -> Response:
    notice = (("success", "Password changed", "You stay logged in here. Every other device has been logged out.")
              if request.query_params.get("password_changed") == "1" else None)
    return _settings_page(request, conn, user, notice=notice)


@router.post("/settings/password")
def change_password(request: Request, current_password: str = Form(""), new_password: str = Form(""),
                    csrf_token: str = Form(""), conn=Depends(get_db), user=Depends(need_user)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=True)
    try:
        fresh = accounts.change_password(conn, request.app.state.ctx, user, current_password=current_password,
                                         new_password=new_password, keep_token=request.cookies.get(SESSION_COOKIE) or "x")
    except ValidationFailed as exc:
        return _settings_page(request, conn, user, errors={"new_password": exc.errors.get("password", "")}, status_code=422,
                              open_section="password")
    except (InvalidCredentials, Throttled) as exc:
        return _settings_page(request, conn, user, errors={"current_password": exc.message},
                              status_code=429 if isinstance(exc, Throttled) else 401, open_section="password")
    response = redirect("/settings?password_changed=1")        # new cookie, so redirect and let the next page use it
    set_session_cookie(response, request, fresh)
    return response


@router.post("/settings/logout-all")
def logout_everywhere(request: Request, csrf_token: str = Form(""), conn=Depends(get_db), user=Depends(need_user)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=True)
    accounts.logout_all(conn, user["id"])
    response = redirect("/login")
    clear_session_cookie(response, request)
    return response


@router.post("/settings/delete")
def delete_account(request: Request, password: str = Form(""), confirm: str = Form(""), csrf_token: str = Form(""),
                   conn=Depends(get_db), user=Depends(need_user)) -> Response:
    verify_page_csrf(request, csrf_token, authenticated=True)
    if confirm != "yes":
        return _settings_page(request, conn, user, errors={"confirm": "Tick the box to confirm."}, status_code=422, open_section="delete")
    try:
        accounts.delete_account(conn, request.app.state.ctx, user, password=password)
    except (InvalidCredentials, Throttled) as exc:
        return _settings_page(request, conn, user, errors={"password": exc.message},
                              status_code=429 if isinstance(exc, Throttled) else 401, open_section="delete")
    except NotAllowed as exc:
        return _settings_page(request, conn, user, notice=("error", "Your account was not deleted", exc.message), status_code=403,
                              open_section="delete")
    response = redirect("/")
    clear_session_cookie(response, request)
    return response


@router.get("/unauthorized")
def unauthorized(request: Request, conn=Depends(get_db), user=Depends(current_user)) -> Response:
    return render(request, "error.html", conn=conn, user=user, status_code=403, title="You do not have access to that",
                  message="Your role in this care circle does not include that page. If you think it should, ask the person who manages the circle.")
