"""Mechanical security review of app/: route inventory, CSRF on every state-changing route, SQL and logging hygiene,
autoescape, session fixation, file permissions, and 'no fake data' in the UI."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
from pathlib import Path

import pytest

from app import ids
from conftest import Site
from fcc_testlib import PASSWORD

APP = Path(__file__).resolve().parents[2] / "app"


def routes_of(app):
    """[(method, path)] for every real route, including those nested in included routers."""
    out = []

    def visit(routes):
        for r in routes:
            if hasattr(r, "original_router"):
                visit(r.original_router.routes)
            elif hasattr(r, "methods"):
                for m in sorted(r.methods - {"HEAD"}):
                    out.append((m, r.path))
    visit(app.routes)
    return sorted(out)


EXPECTED_ROUTES = sorted([
    # API (JSON)
    ("GET", "/api/p/{patient_id}/outputs"), ("GET", "/api/p/{patient_id}/status"), ("GET", "/api/p/{patient_id}/history"),
    ("GET", "/api/p/{patient_id}/notes/{note_id}/outputs"), ("GET", "/api/p/{patient_id}/notes"),
    ("GET", "/api/p/{patient_id}/notes/{note_id}/source"), ("GET", "/api/p/{patient_id}/circle"),
    ("POST", "/api/p/{patient_id}/notes"), ("POST", "/api/p/{patient_id}/notes/{note_id}/delete"),
    ("POST", "/api/p/{patient_id}/checklist/{note_id}/{index}"),
    # public pages and accounts
    ("GET", "/"), ("GET", "/signup"), ("POST", "/signup"), ("GET", "/login"), ("POST", "/login"), ("POST", "/logout"),
    # profiles and joining
    ("GET", "/profiles"), ("GET", "/profiles/new"), ("POST", "/profiles/new"), ("GET", "/p/{patient_id}/created"),
    ("GET", "/join"), ("POST", "/join"),
    # inside a care circle
    ("GET", "/p/{patient_id}"), ("GET", "/p/{patient_id}/info"), ("GET", "/p/{patient_id}/circle"),
    ("POST", "/p/{patient_id}/circle/invite"), ("POST", "/p/{patient_id}/circle/invitations/{invitation_id}/revoke"),
    ("POST", "/p/{patient_id}/circle/members/{membership_id}/approve"), ("POST", "/p/{patient_id}/circle/members/{membership_id}/revoke"),
    ("POST", "/p/{patient_id}/circle/members/{membership_id}/role"), ("POST", "/p/{patient_id}/circle/members/{membership_id}/notes"),
    ("POST", "/p/{patient_id}/circle/pause"), ("POST", "/p/{patient_id}/delete"), ("GET", "/p/{patient_id}/summaries"), ("POST", "/p/{patient_id}/checklist/{note_id}/{index}"),
    ("GET", "/p/{patient_id}/notes"), ("POST", "/p/{patient_id}/notes"), ("POST", "/p/{patient_id}/notes/{note_id}/delete"),
    # settings
    ("GET", "/settings"), ("POST", "/settings/password"), ("POST", "/settings/logout-all"), ("POST", "/settings/delete"),
    ("GET", "/unauthorized"),
])


def test_the_route_inventory_is_exactly_what_was_built(app):
    got = routes_of(app)
    assert got == EXPECTED_ROUTES, (set(got) ^ set(EXPECTED_ROUTES))


def test_only_get_and_post_exist(app):
    assert {m for m, _ in routes_of(app)} == {"GET", "POST"}


def fill(path: str, pid: str) -> str:
    return (path.replace("{patient_id}", pid).replace("{note_id}", "1").replace("{index}", "0")
            .replace("{membership_id}", "1").replace("{invitation_id}", "1"))


def snapshot(conn) -> str:
    h = hashlib.sha256()
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        for row in conn.execute(f"SELECT * FROM {name} ORDER BY 1"):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def test_no_state_changing_route_works_without_a_csrf_token(app, full, conn):
    """Every POST route, called by a logged-in creator (or anonymously for /login and /signup) with NO token,
    is refused and changes nothing."""
    before = snapshot(conn)
    owner = full.site["owner"]
    posts = [(m, p) for m, p in routes_of(app) if m == "POST"]
    assert len(posts) == 22
    for _, path in posts:
        url = fill(path, full.pid)
        if path in ("/login", "/signup"):
            r = Site(app).post(url, {"email": "x@example.test", "password": PASSWORD, "display_name": "X"})
        else:
            r = owner.post(url, {"confirm": full.pid, "role": "child", "text": "x", "ticked": "1", "allowed": "1"})
        assert r.status_code == 403, (path, r.status_code)
    assert snapshot(conn) == before


def test_logout_without_a_session_does_nothing_harmful(app, conn):
    before = snapshot(conn)
    r = Site(app).post("/logout", {})
    assert r.status_code == 303 and snapshot(conn) == before


def test_get_requests_never_change_the_database(app, full, conn):
    before = snapshot(conn)
    for who in ("owner", "caregiver", "child", "pending"):
        for m, path in routes_of(app):
            if m == "GET":
                full.site[who].get(fill(path, full.pid))
    assert snapshot(conn) == before


# --- SQL hygiene ------------------------------------------------------------------------------------------------
SAFE_INTERPOLATIONS = {"PUBLIC_USER_COLUMNS"}      # a module constant (fixed column list), never user input


def _sql_calls():
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany", "executescript"):
                yield path, node


def _unsafe(arg: ast.AST) -> str | None:
    if isinstance(arg, ast.Constant):
        return None
    if isinstance(arg, ast.JoinedStr):
        holes = [v.value for v in arg.values if isinstance(v, ast.FormattedValue)]
        if all(isinstance(h, ast.Name) and h.id in SAFE_INTERPOLATIONS for h in holes):
            return None
        return ast.unparse(arg)
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
        return _unsafe(arg.left) or _unsafe(arg.right)
    if isinstance(arg, ast.Name) and arg.id.isupper() or (isinstance(arg, ast.Name) and arg.id == "_SELECT"):
        return None                                                                            # a module-level constant
    return ast.unparse(arg)


def test_every_sql_statement_is_a_literal_or_a_reviewed_constant_with_bound_parameters():
    seen = 0
    for path, call in _sql_calls():
        seen += 1
        if path.name == "db.py" and ast.unparse(call.args[0]).startswith("'BEGIN;"):
            continue                                                                           # migrate(): version int + our own timestamp
        bad = _unsafe(call.args[0])
        assert bad is None, f"{path.relative_to(APP.parent)}:{call.lineno} builds SQL dynamically: {bad}"
    assert seen > 60                                                                           # the scan really looked at the code


def test_migration_script_only_interpolates_an_int_and_our_own_timestamp():
    src = (APP / "db.py").read_text()
    assert "int(version)" in src and "iso(datetime.now(timezone.utc))" in src


# --- logging hygiene -------------------------------------------------------------------------------------------
SENSITIVE = {"text", "password", "new_password", "current_password", "token", "code", "note_text", "email", "body", "secret_key",
             "password_hash", "title", "care_notes", "display_name", "invite_code"}


def test_log_calls_never_mention_sensitive_values():
    checked = 0
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in
                    ("debug", "info", "warning", "error", "exception", "critical") and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ("log", "logger", "LOGGER")):
                checked += 1
                for arg in node.args[1:]:
                    # len(x) logs only a character count, never the content
                    lens = {id(n.args[0]) for n in ast.walk(arg) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "len" and n.args}
                    for n in ast.walk(arg):
                        if id(n) in lens:
                            continue
                        names = ({n.id} if isinstance(n, ast.Name) else {n.attr} if isinstance(n, ast.Attribute) else
                                 {n.slice.value} if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) else set())
                        assert not (names & SENSITIVE), f"{path.name}:{node.lineno} logs {names & SENSITIVE}"
    assert checked >= 12


# --- templates ------------------------------------------------------------------------------------------------
def test_autoescape_is_on_and_never_switched_off():
    from app.web.render import templates
    assert templates.env.autoescape("page.html") is True
    for t in (APP / "templates").rglob("*.html"):
        text = t.read_text()
        assert "|safe" not in text and "autoescape false" not in text and "Markup(" not in text, t
    for py in APP.rglob("*.py"):
        assert "Markup(" not in py.read_text() and "mark_safe" not in py.read_text(), py


def _string_literals(path: Path):
    """String constants in a Python file, excluding docstrings (which never reach a page)."""
    tree = ast.parse(path.read_text())
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                doc_nodes.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_nodes:
            yield node.value


def test_the_ui_never_shows_example_ids_or_codes_that_could_be_real():
    """'No fake data in the UI': placeholder text must not look like an ID or code that could actually exist."""
    id_like = re.compile(rf"FCC-[{ids.ALPHABET}]{{4}}-[{ids.ALPHABET}]{{4}}")
    code_like = re.compile(rf"\b(?:[{ids.ALPHABET}]{{4}}-){{3}}[{ids.ALPHABET}]{{4}}\b")
    scanned = 0
    for f in list((APP / "templates").rglob("*.html")) + list((APP / "static").rglob("*")):
        if f.is_file():
            scanned += 1
            text = f.read_text(errors="ignore")
            assert not id_like.search(text), (f, id_like.search(text).group(0))
            assert not code_like.search(text), (f, code_like.search(text).group(0))
    for py in list(APP.glob("*.py")) + list((APP / "web").glob("*.py")):
        for s in _string_literals(py):
            scanned += 1
            assert not id_like.search(s) and not code_like.search(s), (py.name, s[:80])
    assert scanned > 200


def test_no_credentials_or_secret_keys_are_hardcoded():
    for py in APP.rglob("*.py"):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or "environ" in s or "token_bytes" in s or "get(" in s:
                continue
            assert not re.search(r"""(password|passwd|secret|api_key)\w*\s*=\s*["'][^"']{6,}["']""", s, re.I), (py.name, i, s)
            assert not re.search(r"""sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,}""", s), (py.name, i)


def test_only_ollama_adapter_imports_the_standard_library_http_client():
    banned = {"requests", "httpx", "urllib3", "aiohttp", "socket", "smtplib", "ftplib", "http.client", "urllib.request", "openai", "anthropic"}
    for py in APP.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for m in mods:
                if m == "urllib.request":
                    assert py == APP / "ollama_generator.py", (py.name, m)
                    continue
                assert m not in banned and m.split(".")[0] not in {"requests", "httpx", "aiohttp", "openai", "anthropic", "smtplib"}, (py.name, m)


# --- sessions ------------------------------------------------------------------------------------------------------
def test_login_never_adopts_a_session_id_chosen_by_someone_else(app, world, conn):
    world.user("Victim", email="victim@example.test")
    s = Site(app)
    s.client.cookies.set("fcc_session", "attacker-chosen-session-value-0123456789abcdef")           # fixation attempt
    r = s.login("victim@example.test")
    assert r.status_code == 303
    issued = [c for c in r.headers.get_list("set-cookie") if c.startswith("fcc_session=")][0].split(";")[0].split("=", 1)[1]
    assert issued != "attacker-chosen-session-value-0123456789abcdef" and len(issued) >= 40
    attacker = Site(app)
    attacker.client.cookies.set("fcc_session", "attacker-chosen-session-value-0123456789abcdef")
    assert attacker.get("/profiles").status_code == 303                                              # the planted value is worthless


def test_every_login_gets_a_new_unpredictable_token(app, world):
    world.user("Multi", email="multi@example.test")
    tokens = set()
    for _ in range(5):
        r = Site(app).login("multi@example.test")
        tokens.add([c for c in r.headers.get_list("set-cookie") if c.startswith("fcc_session=")][0].split(";")[0])
    assert len(tokens) == 5


def test_the_session_token_is_never_stored_or_visible_in_the_database(app, world, conn):
    world.user("Tok", email="tok@example.test")
    s = Site(app); r = s.login("tok@example.test")
    token = s.client.cookies.get("fcc_session")
    dump = " ".join(repr(tuple(row)) for t in ("sessions", "users") for row in conn.execute(f"SELECT * FROM {t}"))
    assert token not in dump and hashlib.sha256(token.encode()).hexdigest() in dump


# --- file permissions -------------------------------------------------------------------------------------------
def test_the_database_file_is_readable_only_by_its_owner(settings, ctx, runner):
    from app.web.main import create_app
    create_app(settings, ctx=ctx, runner=runner, start_worker=False)
    mode = stat.S_IMODE(os.stat(settings.db_path).st_mode)
    assert mode & 0o077 == 0, oct(mode)
    for suffix in ("-wal", "-shm"):
        p = Path(str(settings.db_path) + suffix)
        if p.exists():
            assert stat.S_IMODE(os.stat(p).st_mode) & 0o077 == 0, (p, oct(stat.S_IMODE(os.stat(p).st_mode)))
