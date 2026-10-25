"""Fixtures for the web-app tests. Synthetic, in-memory/tmp databases only; tiny scrypt cost for speed."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import accounts, circle
from app.config import Settings
from app.context import Ctx
from app.db import connect, migrate
from fcc_testlib import PASSWORD, FakeClock


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # generous queue caps here so older tests may queue many notes; the cap tests build their own Settings
    return Settings(db_path=tmp_path / "t.sqlite3", scrypt_n=2 ** 4, secret_key=b"k" * 32,
                    max_pending_per_circle=10_000, max_pending_total=100_000)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def ctx(settings: Settings, clock: FakeClock) -> Ctx:
    return Ctx(settings=settings, clock=clock)


@pytest.fixture
def conn(settings: Settings):
    c = connect(settings.db_path)
    migrate(c)
    yield c
    c.close()


class World:
    """Helpers that build real rows through the real service functions (no hand-inserted shortcuts)."""

    def __init__(self, conn, ctx) -> None:
        self.conn, self.ctx = conn, ctx
        self._n = 0

    def user(self, name: str = "Test User", email: str | None = None):
        self._n += 1
        return accounts.signup(self.conn, self.ctx, email=email or f"user{self._n}@example.test",
                               display_name=name, password=PASSWORD)

    def profile(self, creator, display_name: str = "Pat Example", **kw):
        kw.setdefault("relationship_label", "Daughter")
        return circle.create_profile(self.conn, self.ctx, creator, display_name=display_name, **kw)

    def member(self, profile, creator, role: str, name: str, *, active: bool = True, can_add_notes: bool = False):
        """Create a user, invite them with ``role``, let them join, and (optionally) activate them."""
        u = self.user(name)
        _, code = circle.create_invitation(self.conn, self.ctx, creator, profile, role=role)
        m = circle.join(self.conn, self.ctx, u, patient_id=profile["patient_id"], code=code, relationship_label="Other relative")
        if active:
            circle.approve_member(self.conn, self.ctx, creator, profile, m["id"])
            if can_add_notes:
                circle.set_can_add_notes(self.conn, self.ctx, creator, profile, m["id"], True)
        return u, self.conn.execute("SELECT * FROM memberships WHERE id = ?", (m["id"],)).fetchone()


@pytest.fixture
def world(conn, ctx) -> World:
    return World(conn, ctx)


# ---- web-layer fixtures --------------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402

from app import accounts, csrf, security  # noqa: E402
from app.jobs import JobRunner  # noqa: E402
from app.web.deps import CSRF_HEADER, SESSION_COOKIE  # noqa: E402
from app.web.main import create_app  # noqa: E402
from fcc_testlib import FakePipeline  # noqa: E402


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def runner(settings, ctx, pipeline) -> JobRunner:
    return JobRunner(settings, ctx, pipeline_factory=lambda: pipeline)


@pytest.fixture
def app(settings, ctx, runner):
    return create_app(settings, ctx=ctx, runner=runner, start_worker=False)


class Browser:
    """A test client acting as one logged-in user (own cookie jar), with a ready CSRF token."""

    def __init__(self, app, conn, ctx, settings, user, *, login: bool = True) -> None:
        self.client = TestClient(app, base_url="http://testserver", raise_server_exceptions=False)
        self.user, self.settings = user, settings
        self.token = None
        self.csrf = None
        if login:
            _, self.token = accounts.login(conn, ctx, email=user["email"], password=PASSWORD)
            self.client.cookies.set(SESSION_COOKIE, self.token)
            self.csrf = csrf.make_token(settings.secret_key, security.hash_token(self.token))

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, *, data=None, files=None, token="auto", headers=None):
        headers = dict(headers or {})
        if token == "auto":
            token = self.csrf
        if token:
            headers[CSRF_HEADER] = token
        return self.client.post(url, data=data or {}, files=files, headers=headers)


@pytest.fixture
def browser(app, conn, ctx, settings):
    def make(user, *, login: bool = True) -> Browser:
        return Browser(app, conn, ctx, settings, user, login=login)
    return make


class Site:
    """A browser-like client for server-rendered pages: keeps cookies, reads CSRF tokens out of the HTML."""

    def __init__(self, app, *, https: bool = False, ip: str = "203.0.113.5") -> None:
        self.client = TestClient(app, base_url=("https" if https else "http") + "://testserver",
                                 raise_server_exceptions=False, follow_redirects=False,
                                 headers={"x-test-client": ip})
        self.pages: list[str] = []

    def get(self, url, **kw):
        r = self.client.get(url, **kw)
        if r.headers.get("content-type", "").startswith("text/html"):
            self.pages.append(r.text)
        return r

    def post(self, url, data=None, **kw):
        r = self.client.post(url, data=data or {}, **kw)
        if r.headers.get("content-type", "").startswith("text/html"):
            self.pages.append(r.text)
        return r

    def submit(self, form_url, post_url, data):
        """GET the form (to obtain the cookie + token), then POST it with the token, like a browser."""
        from fcc_testlib import csrf_from
        page = self.get(form_url)
        assert page.status_code == 200, (form_url, page.status_code)
        return self.post(post_url, {**data, "csrf_token": csrf_from(page.text)})

    def signup(self, name="Sam Site", email="sam@example.test", password=PASSWORD, next_=""):
        return self.submit("/signup", "/signup", {"display_name": name, "email": email, "password": password, "next": next_})

    def login(self, email, password=PASSWORD, next_=""):
        return self.submit("/login", "/login", {"email": email, "password": password, "next": next_})


@pytest.fixture
def site(app):
    return Site(app)


# ---- a complete care circle shared by the page tests -------------------------------------------------------
from app import circle as _circle, notes as _notes  # noqa: E402
from fcc_testlib import PATIENT_NAME, SOURCE_TEXT, TITLE  # noqa: E402

@pytest.fixture
def full(conn, ctx, runner, world, app):
    owner = world.user("Olivia Owner", email="olivia@example.test")
    p = world.profile(owner, PATIENT_NAME, preferred_name="Grandma")
    users = {"owner": owner}
    users["caregiver"], _ = world.member(p, owner, "caregiver", "Cara Carer", can_add_notes=True)
    users["caregiver_no_notes"], _ = world.member(p, owner, "caregiver", "Dan Danielson")
    users["patient"], _ = world.member(p, owner, "patient", "Pat Patientson")
    users["child"], _ = world.member(p, owner, "child", "Kid Kidson")
    users["pending"], pm = world.member(p, owner, "caregiver", "Wendy Waitson", active=False)
    users["pending_child"], pcm = world.member(p, owner, "child", "Pip Pendingchild", active=False)
    users["revoked"], rm = world.member(p, owner, "caregiver", "Rex Removedson")
    _circle.revoke_member(conn, ctx, owner, p, rm["id"])
    users["stranger"] = world.user("Sam Stranger")
    _notes.add_note(conn, ctx, runner, owner, p, title=TITLE, text=SOURCE_TEXT)
    runner.drain()

    class W:
        pass
    w = W()
    w.p, w.pid, w.users, w.pending_membership, w.pending_child_membership = p, p["patient_id"], users, pm, pcm
    w.site = {}
    for name, u in users.items():
        s = Site(app)
        assert s.login(u["email"]).status_code == 303, name
        w.site[name] = s
    w.anon = Site(app)
    return w




# ---- slow / browser / real-model tests are skipped unless asked for -----------------------------------------------
# Run them with:  APP_RUN_SLOW=1 python -m pytest tests/app        (or: make app-test-slow)
def pytest_configure(config):
    for name, text in (("slow", "slow test (seconds to minutes): skipped unless APP_RUN_SLOW=1"),
                       ("browser", "needs Playwright + Chromium: skipped unless APP_RUN_SLOW=1"),
                       ("realmodel", "needs the 2 GB local GGUF model: skipped unless APP_RUN_SLOW=1")):
        config.addinivalue_line("markers", f"{name}: {text}")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("APP_RUN_SLOW") == "1":
        return
    skip = pytest.mark.skip(reason="slow/browser/real-model test: set APP_RUN_SLOW=1 to run")
    for item in items:
        if any(m in item.keywords for m in ("slow", "browser", "realmodel")):
            item.add_marker(skip)
