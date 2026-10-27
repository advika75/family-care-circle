"""Application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app import errors
from app.config import Settings
from app.context import Ctx
from app.db import connect, migrate
from app.jobs import JobRunner
from app.web import api, pages, pages_circle, pages_settings
from app.web.render import APP_DIR, CsrfFailed, LoginRequired, StatusPage, redirect, render
from app.web.middleware import BodyLimitMiddleware, SecurityHeadersMiddleware

log = logging.getLogger("app.web")

_STATUS = {
    errors.ValidationFailed: 422, errors.InvalidCredentials: 401, errors.AccountNotCreated: 400, errors.Throttled: 429,
    errors.NotAllowed: 403, errors.NotFound: 404, errors.InvalidIdOrCode: 400, errors.InvitationExpired: 400,
    errors.InvitationUsed: 400, errors.AlreadyMember: 409, errors.QueueFull: 429, errors.MembershipPending: 403, errors.MembershipRevoked: 403,
}


def _error_response(exc: errors.AppError) -> JSONResponse:
    body: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if isinstance(exc, errors.ValidationFailed):
        body["fields"] = exc.errors
    return JSONResponse({"error": body}, status_code=_STATUS.get(type(exc), 400))


def create_app(settings: Settings | None = None, *, ctx: Ctx | None = None, runner: JobRunner | None = None,
               start_worker: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    ctx = ctx or Ctx(settings=settings)
    runner = runner or JobRunner(settings, ctx)

    from app.pipeline_adapter import timeout_budget_problem

    budget_problem = timeout_budget_problem(settings)
    if budget_problem:
        log.warning("Generation timeout budget: %s", budget_problem)    # settings values only

    conn = connect(settings.db_path)
    try:
        migrate(conn)
        recovered = runner.recover(conn)
    finally:
        conn.close()
    if recovered:
        log.info("re-queued %d unfinished note(s)", recovered)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_worker:
            runner.start()
        yield
        runner.shutdown()

    app = FastAPI(title="Family Care Circle", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings, app.state.ctx, app.state.runner = settings, ctx, runner
    app.add_middleware(BodyLimitMiddleware, max_bytes=256 * 1024)
    app.add_middleware(SecurityHeadersMiddleware, https=settings.https)   # added last = outermost: wraps every response

    def wants_json(request: Request) -> bool:
        return request.url.path.startswith("/api")

    def error_page(request: Request, status_code: int, title: str, message: str) -> Response:
        user = None
        try:
            from app import accounts
            from app.web.deps import SESSION_COOKIE
            conn = connect(settings.db_path)
            try:
                user = accounts.resolve_session(conn, ctx, request.cookies.get(SESSION_COOKIE))
                return render(request, "error.html", conn=conn, user=user, status_code=status_code, title=title, message=message)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 - an error page must never raise
            return Response("Something went wrong.", status_code=status_code, media_type="text/plain")

    @app.exception_handler(errors.AppError)
    async def _app_error(request: Request, exc: errors.AppError) -> Response:
        if wants_json(request):
            return _error_response(exc)
        status = _STATUS.get(type(exc), 400)
        titles = {404: "We could not find that page", 403: "You do not have access to that", 429: "Too many attempts"}
        return error_page(request, status, titles.get(status, "Something went wrong"), exc.message)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> Response:
        if wants_json(request):
            return JSONResponse({"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)}}, status_code=exc.status_code)
        titles = {404: "We could not find that page", 403: "You do not have access to that", 405: "That is not allowed here"}
        message = "That page does not exist, or you do not have access to it." if exc.status_code == 404 else str(exc.detail)
        return error_page(request, exc.status_code, titles.get(exc.status_code, "Something went wrong"), message)

    @app.exception_handler(RequestValidationError)
    async def _bad_request(request: Request, exc: RequestValidationError) -> Response:
        if wants_json(request):
            return JSONResponse({"error": {"code": "bad_request", "message": "That request was not understood."}}, status_code=422)
        return error_page(request, 422, "That request was not understood", "Please go back and try again.")

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired) -> Response:
        nxt = request.url.path if request.url.path in ("/profiles/new", "/join") else ""
        return redirect("/login" + (f"?next={nxt}" if nxt else ""))

    @app.exception_handler(StatusPage)
    async def _status_page(request: Request, exc: StatusPage) -> Response:
        conn = connect(settings.db_path)
        try:
            from app import accounts
            from app.web.deps import SESSION_COOKIE
            user = accounts.resolve_session(conn, ctx, request.cookies.get(SESSION_COOKIE))
            # Deliberately no patient name: pending/revoked members may see nothing about the patient.
            return render(request, "membership_status.html", conn=conn, user=user, status=exc.membership["status"],
                          role=exc.membership["role"], patient_id=exc.profile["patient_id"])
        finally:
            conn.close()

    @app.exception_handler(CsrfFailed)
    async def _csrf_failed(request: Request, exc: CsrfFailed) -> Response:
        return error_page(request, 403, "Your session could not be verified", "Please go back, reload the page and try again.")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> Response:
        log.error("unhandled error: %s", type(exc).__name__)               # class name only: messages may hold note text
        if wants_json(request):
            return JSONResponse({"error": {"code": "server_error", "message": "Something went wrong on our side."}}, status_code=500)
        return error_page(request, 500, "Something went wrong", "Something went wrong on our side. Please try again.")

    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
    app.include_router(api.router)
    app.include_router(pages.router)
    app.include_router(pages_circle.router)
    app.include_router(pages_settings.router)
    return app
