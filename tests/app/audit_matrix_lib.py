"""Authorization matrix and leak hunt (from the Phase A audit, A1/A2), kept as a regression library.

Calls the real app (mock backend) as nine kinds of actor against every route and checks: no forbidden string in any
response, headers or log; GETs never change the database; no actor changes state who is not allowed to.
Throw-away databases in a temp directory. Used by test_app_audit_regression.py.
"""
import hashlib, json, logging, re, sys, tempfile, io
from pathlib import Path
import warnings; warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient
from app import accounts, circle, notes, permissions as P
from app.config import Settings
from app.context import Ctx
from app.db import connect, migrate
from app.jobs import JobRunner
from app.pipeline_adapter import build_pipeline
from app.web import render as render_mod
from app.web.main import create_app

PW = "an audit passphrase 123"
SOURCE = ("ZEBRA-SOURCE-TOKEN visit note. Patient has strep throat.\n"
          "1. Amoxicillin 500 mg PO BID x 10 days.\n2. Ibuprofen 200 mg PO q6h PRN pain.\n")
TITLE = "Audit clinic visit"
PATIENT_NAME = "Peggy Auditpatient"
ACTORS = ["anonymous", "stranger", "pending", "revoked", "child", "patient", "caregiver_no_notes", "caregiver", "creator"]

# one real pipeline (mock backend) shared by every throw-away world
_SETTINGS0 = Settings(db_path=Path("unused.db"), scrypt_n=16, secret_key=b"a" * 32)
_PIPELINE = build_pipeline(_SETTINGS0)

LOG = io.StringIO()


class Client:
    def __init__(self, app):
        self.c = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        self.pages = []

    def req(self, method, url, **kw):
        r = self.c.request(method, url, **kw)
        return r

    def csrf(self):
        r = self.c.get("/settings")
        m = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', r.text)
        return m.group(1) if m else None


def world(tmp):
    settings = Settings(db_path=Path(tmp) / "a.sqlite3", scrypt_n=16, secret_key=b"a" * 32)
    ctx = Ctx(settings)
    runner = JobRunner(settings, ctx, pipeline_factory=lambda: _PIPELINE)
    app = create_app(settings, ctx=ctx, runner=runner, start_worker=False)
    conn = connect(settings.db_path)
    n = [0]

    def user(name):
        n[0] += 1
        return accounts.signup(conn, ctx, email=f"{name.lower().replace(' ', '.')}{n[0]}@audit.example", display_name=name, password=PW)

    def member(p, owner, role, name, active=True, notes_ok=False):
        u = user(name)
        _, code = circle.create_invitation(conn, ctx, owner, p, role=role)
        m = circle.join(conn, ctx, u, patient_id=p["patient_id"], code=code, relationship_label="Other relative")
        if active:
            circle.approve_member(conn, ctx, owner, p, m["id"])
            if notes_ok:
                circle.set_can_add_notes(conn, ctx, owner, p, m["id"], True)
        return u, m
    owner = user("Olivia Auditowner")
    p = circle.create_profile(conn, ctx, owner, display_name=PATIENT_NAME, preferred_name="Granny", relationship_label="Daughter")
    users = {"creator": owner}
    users["caregiver"], _ = member(p, owner, "caregiver", "Cara Auditcarer", notes_ok=True)
    users["caregiver_no_notes"], cg2m = member(p, owner, "caregiver", "Dan Auditdan")
    users["patient"], _ = member(p, owner, "patient", "Pat Auditpat")
    users["child"], _ = member(p, owner, "child", "Kid Auditkid")
    users["pending"], pend_m = member(p, owner, "caregiver", "Wendy Auditwait", active=False)
    pc_user, pc_m = member(p, owner, "child", "Pip Auditpendingchild", active=False)         # target for approve
    users["revoked"], rm = member(p, owner, "caregiver", "Rex Auditrex")
    circle.revoke_member(conn, ctx, owner, p, rm["id"])
    users["stranger"] = user("Sam Auditstranger")
    note = notes.add_note(conn, ctx, runner, owner, p, title=TITLE, text=SOURCE)
    runner.drain()
    inv, code = circle.create_invitation(conn, ctx, owner, p, role="child")                    # an open invitation + its code
    clients = {}
    for a in ACTORS:
        c = Client(app)
        if a != "anonymous":
            _, tok = accounts.login(conn, ctx, email=users[a]["email"], password=PW)
            c.c.cookies.set("fcc_session", tok)
        clients[a] = c
    return dict(app=app, conn=conn, ctx=ctx, p=p, pid=p["patient_id"], note=note["id"], users=users, clients=clients,
                cg2m=cg2m["id"], pend_child_m=pc_m["id"], inv=inv["id"], code=code, owner=owner, db=settings.db_path)


def snapshot(conn):
    h = hashlib.sha256()
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sessions','schema_migrations') ORDER BY name").fetchall():
        for row in conn.execute(f"SELECT * FROM {name} ORDER BY 1"):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------------------- forbidden strings
MEDS = ["Amoxicillin", "Ibuprofen", "500 mg", "200 mg"]
FORBID = {
    "anonymous": ["ZEBRA", TITLE, PATIENT_NAME, "Granny"] + MEDS + ["audit.example", "strep throat", "Cara", "Olivia"],
    "stranger": ["ZEBRA", TITLE, PATIENT_NAME, "Granny"] + MEDS + ["strep throat", "Cara", "Olivia", "Wendy", "Rex"],
    "pending": ["ZEBRA", TITLE, PATIENT_NAME, "Granny"] + MEDS + ["strep throat", "Cara", "Olivia", "Wendy", "Rex"],
    "revoked": ["ZEBRA", TITLE, PATIENT_NAME, "Granny"] + MEDS + ["strep throat", "Cara", "Olivia", "Wendy"],
    "child": ["ZEBRA", TITLE, PATIENT_NAME] + MEDS + ["audit.example", "Review flags", "strep throat", "retention", "Auditowner", "Auditcarer",
              "Auditdan", "Auditpat", "Auditkid", "Auditwait", "Auditrex", "Auditpendingchild", "caregiver_checklist", "patient_summary"],
    "patient": ["ZEBRA", TITLE, "audit.example", "Review flags", "retention", "Auditwait", "Auditrex", "Auditpendingchild",
                "Give Amoxicillin", "caregiver_checklist", "child_explanation"],
    "caregiver_no_notes": ["audit.example", "Auditwait", "Auditrex"],
    "caregiver": ["audit.example", "Auditwait", "Auditrex"],
    "creator": [],
}


def leaks(actor, resp, w=None):
    hay = resp.text + "\n" + "\n".join(f"{k}: {v}" for k, v in resp.headers.multi_items())
    if w is not None and actor in w["users"]:                 # a user's OWN name and email are theirs to see
        me = w["users"][actor]
        hay = hay.replace(me["email"], "").replace(me["display_name"], "")
    # the mandated disclaimer legitimately contains the word "doses"; the viewer's own name/email are theirs
    found = [s for s in FORBID[actor] if s in hay]
    return found


def route_urls(w):
    pid, n = w["pid"], w["note"]
    return [
        ("GET", "/", None), ("GET", "/signup", None), ("GET", "/login", None), ("GET", "/profiles", None), ("GET", "/profiles/new", None),
        ("GET", "/join", None), ("GET", "/settings", None), ("GET", "/unauthorized", None),
        ("GET", f"/p/{pid}", None), ("GET", f"/p/{pid}/created", None), ("GET", f"/p/{pid}/info", None), ("GET", f"/p/{pid}/circle", None),
        ("GET", f"/p/{pid}/summaries", None), ("GET", f"/p/{pid}/summaries?tab=caregiver", None), ("GET", f"/p/{pid}/summaries?tab=child", None),
        ("GET", f"/p/{pid}/summaries?note={n}", None), ("GET", f"/p/{pid}/notes", None),
        ("GET", f"/api/p/{pid}/outputs", None), ("GET", f"/api/p/{pid}/status", None), ("GET", f"/api/p/{pid}/history", None),
        ("GET", f"/api/p/{pid}/notes", None), ("GET", f"/api/p/{pid}/circle", None),
        ("GET", f"/api/p/{pid}/notes/{n}/outputs", None), ("GET", f"/api/p/{pid}/notes/{n}/source", None),
    ]


def post_specs(w):
    pid, n = w["pid"], w["note"]
    return [
        ("POST", "/logout", {}), ("POST", "/profiles/new", {"step": "4", "action": "create", "display_name": "New One", "relationship_label": "Son"}),
        ("POST", "/join", {"patient_id": pid, "code": w["code"], "relationship_label": "Son"}),
        ("POST", f"/p/{pid}/circle/invite", {"role": "patient"}),
        ("POST", f"/p/{pid}/circle/pause", {"paused": "1"}),
        ("POST", f"/p/{pid}/circle/invitations/{w['inv']}/revoke", {}),
        ("POST", f"/p/{pid}/circle/members/{w['pend_child_m']}/approve", {}),
        ("POST", f"/p/{pid}/circle/members/{w['cg2m']}/revoke", {}),
        ("POST", f"/p/{pid}/circle/members/{w['cg2m']}/role", {"role": "child"}),
        ("POST", f"/p/{pid}/circle/members/{w['cg2m']}/notes", {"allowed": "1"}),
        ("POST", f"/p/{pid}/delete", {"confirm": pid}),
        ("POST", f"/p/{pid}/notes", {"title": "Extra", "text": "Extra note text."}),
        ("POST", f"/p/{pid}/notes/{n}/delete", {}),
        ("POST", f"/p/{pid}/checklist/{n}/0", {"ticked": "1"}),
        ("POST", "/settings/password", {"current_password": "wrong wrong wrong", "new_password": "another audit passphrase"}),
        ("POST", "/settings/logout-all", {}),
        ("POST", "/settings/delete", {"password": "wrong wrong wrong", "confirm": "yes"}),
        ("POST", f"/api/p/{pid}/notes", {"title": "Api", "text": "Api note text."}),
        ("POST", f"/api/p/{pid}/notes/{n}/delete", {}),
        ("POST", f"/api/p/{pid}/checklist/{n}/0", {"ticked": "1"}),
    ]


def cell(r):
    loc = r.headers.get("location")
    if r.status_code in (301, 302, 303, 307):
        return f"{r.status_code}→{loc.split('127.0.0.1')[-1].replace('http://testserver','') if loc else ''}"
    return str(r.status_code)


def run_matrix(write_to=None):
    h = logging.StreamHandler(LOG); h.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(h); old = logging.getLogger().level; logging.getLogger().setLevel(logging.DEBUG)
    try:
        return _run_matrix()
    finally:
        logging.getLogger().removeHandler(h); logging.getLogger().setLevel(old)


def _run_matrix():
    out = {"get": {}, "post": {}, "leaks": [], "unexpected": []}
    contexts = []
    original = render_mod.templates.TemplateResponse

    def spy(request, name, context=None, *a, **kw):
        contexts.append((request.url.path, name, dict(context or {})))
        return original(request, name, context, *a, **kw)
    render_mod.templates.TemplateResponse = spy

    # ---------------------------------------------------------------- GET matrix (one world; GETs do not mutate)
    with tempfile.TemporaryDirectory() as tmp:
        w = world(tmp)
        before = snapshot(w["conn"])
        for method, url, _ in route_urls(w):
            row = {}
            for a in ACTORS:
                r = w["clients"][a].req("GET", url)
                row[a] = cell(r)
                lk = leaks(a, r, w)
                if lk:
                    row[a] += " ⚠LEAK"
                    out["leaks"].append((a, url, lk))
            out["get"][url.replace(w["pid"], "{id}").replace(f"note={w['note']}", "note={n}").replace(f"/{w['note']}/", "/{n}/")] = row
        out["get_mutated_db"] = snapshot(w["conn"]) != before
        # template contexts for the low-privilege actors, re-requested so each context is attributable
        ctx_leaks = []
        for a in ("child", "patient", "pending", "revoked", "stranger", "anonymous"):
            for method, url, _ in route_urls(w):
                contexts.clear()
                w["clients"][a].req("GET", url)
                for path, name, c in contexts:
                    blob = []
                    def flat(o, d=0):
                        if d > 6: return
                        if isinstance(o, dict):
                            for k, v in o.items():
                                if k in ("request",): continue
                                blob.append(str(k)); flat(v, d + 1)
                        elif isinstance(o, (list, tuple, set)):
                            for v in o: flat(v, d + 1)
                        elif hasattr(o, "keys"):
                            for k in o.keys(): blob.append(str(k)); flat(o[k], d + 1)
                        else: blob.append(str(o))
                    flat({k: v for k, v in c.items() if k != "user"})
                    text = " ".join(blob)
                    bad = [s for s in FORBID[a] + ["password_hash", "token_hash"] if s in text and s not in ("Granny",)]
                    if a == "child":
                        bad = [s for s in bad if s not in ("Granny",)]
                    if bad: ctx_leaks.append((a, url.replace(w["pid"], "{id}"), name, bad))
        out["context_leaks"] = ctx_leaks

    # ---------------------------------------------------------------- POST matrix (fresh world per cell)
    base_specs = None
    with tempfile.TemporaryDirectory() as tmp0:
        base_specs = [(m, re.sub(r"FCC-[A-Z0-9]{4}-[A-Z0-9]{4}", "{id}", u), d) for m, u, d in post_specs(world(tmp0))]
    ALLOWED_CHANGE = {
        "/p/{id}/circle/invite": {"creator"}, "/p/{id}/circle/pause": {"creator"}, "/p/{id}/circle/invitations/": {"creator"}, "/p/{id}/circle/members/*/approve": {"creator", "caregiver", "caregiver_no_notes"},
        "/p/{id}/circle/members/*/revoke": {"creator"}, "/p/{id}/circle/members/*/role": {"creator"}, "/p/{id}/circle/members/*/notes": {"creator"},
        "/p/{id}/delete": {"creator"}, "/p/{id}/notes": {"creator", "caregiver"}, "/p/{id}/notes/*/delete": {"creator"},
        "/p/{id}/checklist/*": {"creator", "caregiver", "caregiver_no_notes"}, "/api/p/{id}/notes": {"creator", "caregiver"},
        "/api/p/{id}/notes/*/delete": {"creator"}, "/api/p/{id}/checklist/*": {"creator", "caregiver", "caregiver_no_notes"},
    }
    def allowed(url):
        for k, v in ALLOWED_CHANGE.items():
            pat = re.escape(k).replace(r"\*", r"[^/]+")
            if re.fullmatch(pat + (r".*" if k.endswith("/") else ""), url):
                return v
        return None
    for idx, (m, tmpl, _) in enumerate(base_specs):
        row = {}
        for a in ACTORS:
            with tempfile.TemporaryDirectory() as tmp:
                w = world(tmp)
                _, url, data = post_specs(w)[idx]
                c = w["clients"][a]
                before = snapshot(w["conn"])
                token = None
                if a != "anonymous":
                    token = c.csrf()
                headers = {"x-csrf-token": token} if token else {}
                payload = dict(data)
                if token and not url.startswith("/api"):
                    payload["csrf_token"] = token
                if a == "anonymous" and url in ("/login", "/signup"):
                    pass
                r = c.req("POST", url, data=payload, headers=headers)
                changed = snapshot(w["conn"]) != before
                s = cell(r) + (" Δ" if changed else "")
                lk = leaks(a, r, w)
                if lk:
                    s += " ⚠LEAK"; out["leaks"].append((a, "POST " + tmpl, lk))
                ok = allowed(tmpl)
                if changed and ok is not None and a not in ok:
                    out["unexpected"].append((a, "POST " + tmpl, "state changed but actor is not allowed to"))
                row[a] = s
        out["post"][tmpl] = row

    # ---------------------------------------------------------------- logs
    log_text = LOG.getvalue()
    out["log_leaks"] = [s for s in ["ZEBRA", "Amoxicillin", PW, "wrong wrong wrong", "audit.example", "Extra note text", "Api note text"] if s in log_text]
    out["log_lines"] = len(log_text.splitlines())

    return out
