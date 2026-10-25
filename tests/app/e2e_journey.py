"""End-to-end journey against a REAL running server with the REAL model, on a brand-new empty database.

    .venv/bin/python tests/app/e2e_journey.py

Everything goes through HTTP (httpx) except the screenshots (Playwright, also through the login form). Nothing writes to the
database directly. The note is SYNTHETIC text from data/raw/. The transcript records status codes and field names only,
never note text, cookies, CSRF tokens, passwords or invitation codes.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "app" / "audit"
SHOTS = OUT / "screenshots" / "e2e"
NOTE_FILE = ROOT / "data" / "raw" / "note_01.txt"
LINES: list[str] = []
FAILS: list[str] = []
PID = ""


def log(line: str = "") -> None:
    LINES.append(line)
    print(line)


def rec(step: str, method: str, path: str, status: int, keys=None) -> None:
    path = path.replace(PID, "{id}") if PID else path
    extra = f" fields: {', '.join(sorted(keys))}" if keys else ""
    log(f"- {step} `{method} {path}` -> {status}{extra}")


def check(label: str, ok: bool) -> None:
    log(f"  - {'PASS' if ok else 'FAIL'}: {label}")
    if not ok:
        FAILS.append(label)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class User:
    def __init__(self, base: str, name: str, role: str) -> None:
        self.name, self.role = name, role
        self.email = f"{role}.{secrets.token_hex(3)}@example.test"
        self.password = secrets.token_urlsafe(18)
        self.c = httpx.Client(base_url=base, follow_redirects=False, timeout=60)

    def csrf(self, page: str) -> str:
        r = self.c.get(page)
        m = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', r.text)
        assert m, f"no csrf token on {page} ({r.status_code})"
        return m.group(1)

    def form(self, path: str, data: dict, page: str) -> httpx.Response:
        return self.c.post(path, data={**data, "csrf_token": self.csrf(page)})

    def api(self, method: str, path: str, data: dict | None = None) -> httpx.Response:
        if method == "GET":
            return self.c.get(path)
        return self.c.post(path, data=data or {}, headers={"x-csrf-token": self.csrf("/settings")})


def main() -> int:
    global PID
    tmp = Path(tempfile.mkdtemp(prefix="fcc-e2e-"))
    db = tmp / "data" / "e2e.sqlite3"
    assert not db.exists()
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "APP_DB_PATH": str(db), "APP_BACKEND": "llama_cpp", "APP_SECRET_KEY": secrets.token_hex(32)}
    env.pop("APP_JOB_ISOLATION", None)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.web.main:create_app", "--factory", "--host", "127.0.0.1",
                               "--port", str(port), "--no-server-header", "--log-level", "warning"], cwd=ROOT, env=env)
    try:
        for _ in range(150):
            try:
                httpx.get(base + "/", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("server did not start")
        source = NOTE_FILE.read_text(encoding="utf-8")
        log("# End-to-end transcript (real model, brand-new database)")
        log()
        log("Status codes and field names only. No note text, cookies, CSRF tokens, passwords or invitation codes are recorded.")
        log(f"\nBackend: llama_cpp (real model). Database: new, empty, in a fresh temporary directory ({db.name}). "
            f"Synthetic note: `data/raw/{NOTE_FILE.name}` ({len(source)} characters).\n")

        users = {r: User(base, n, r) for r, n in (("creator", "Alice Creator"), ("caregiver", "Bea Caregiver"),
                                                  ("patient", "Cy Patient"), ("child", "Dee Child"))}
        A, B, C, D = (users[k] for k in ("creator", "caregiver", "patient", "child"))

        log("## a. Sign up A, create the profile through the stepper")
        r = A.c.post("/signup", data={"display_name": A.name, "email": A.email, "password": A.password, "csrf_token": A.csrf("/signup")})
        rec("a", "POST", "/signup", r.status_code)
        check("A signed up (303 to a page)", r.status_code == 303)
        data = {"display_name": "Pat Example", "preferred_name": "Grandma", "year_of_birth": "1948", "care_notes": "Likes tea.",
                "relationship_label": "Daughter"}
        for step, act in ((1, "next"), (2, "next"), (3, "next")):
            r = A.form("/profiles/new", {**data, "step": str(step), "action": act}, "/profiles/new")
            rec("a", "POST", f"/profiles/new (step {step})", r.status_code)
            check(f"stepper step {step} -> 200", r.status_code == 200)
        r = A.form("/profiles/new", {**data, "step": "4", "action": "create"}, "/profiles/new")
        loc = r.headers.get("location", "")
        m = re.fullmatch(r"/p/(FCC-[A-Z0-9]{4}-[A-Z0-9]{4})/created", loc)
        rec("a", "POST", "/profiles/new (create)", r.status_code)
        check("server returned a patient ID in the redirect (not hardcoded)", bool(m))
        PID = m.group(1)
        r = A.c.get(f"/p/{PID}/created")
        rec("a", "GET", f"/p/{PID}/created", r.status_code)
        check("created page shows the same ID", PID in r.text)
        r = A.api("GET", f"/api/p/{PID}/circle")
        members = r.json()
        rec("a", "GET", f"/api/p/{PID}/circle", r.status_code, members[0].keys())
        check("A is the only member and is the creator", len(members) == 1 and members[0]["role"] == "creator" and members[0]["status"] == "active")

        log("\n## b. B, C, D sign up, are invited, join (pending), A approves")
        for u in (B, C, D):
            r = u.c.post("/signup", data={"display_name": u.name, "email": u.email, "password": u.password, "csrf_token": u.csrf("/signup")})
            rec("b", "POST", "/signup", r.status_code)
        codes = {}
        for u in (B, C, D):
            r = A.form(f"/p/{PID}/circle/invite", {"role": u.role, "note": f"for {u.role}"}, f"/p/{PID}/circle")
            m = re.search(r'id="invite-code">([A-Z0-9-]{19})<', r.text)
            rec("b", "POST", f"/p/{PID}/circle/invite (role={u.role})", r.status_code)
            check(f"invitation for {u.role} created, code shown once", bool(m))
            codes[u.role] = m.group(1)
        for u in (B, C, D):
            r = u.form("/join", {"patient_id": PID, "code": codes[u.role], "relationship_label": "Other relative"}, "/join")
            rec("b", "POST", "/join", r.status_code)
            r1 = u.api("GET", f"/api/p/{PID}/outputs")
            r2 = u.c.get(f"/p/{PID}")
            rec("b", "GET", f"/api/p/{PID}/outputs (pending {u.role})", r1.status_code)
            check(f"{u.role} is pending and sees no data (API refused: {r1.status_code}; page does not show the profile name)",
                  r1.status_code in (401, 403, 404) and "Pat Example" not in r2.text and "Grandma" not in r2.text)
        members = {m["display_name"]: m for m in A.api("GET", f"/api/p/{PID}/circle").json()}
        for u in (B, C, D):
            check(f"A sees {u.role} as pending", members[u.name]["status"] == "pending")
            r = A.form(f"/p/{PID}/circle/members/{members[u.name]['membership_id']}/approve", {}, f"/p/{PID}/circle")
            rec("b", "POST", f"/p/{PID}/circle/members/{{n}}/approve", r.status_code)
            check(f"A approved {u.role}", r.status_code == 200)
        members = {m["display_name"]: m for m in A.api("GET", f"/api/p/{PID}/circle").json()}
        check("all three are active", all(members[u.name]["status"] == "active" for u in (B, C, D)))
        r = A.form(f"/p/{PID}/circle/members/{members[B.name]['membership_id']}/notes", {"allowed": "1"}, f"/p/{PID}/circle")
        rec("b", "POST", f"/p/{PID}/circle/members/{{n}}/notes", r.status_code)

        log("\n## c. A adds the synthetic note and waits for the real model")
        t0 = time.time()
        r = A.api("POST", f"/api/p/{PID}/notes", {"title": "Synthetic clinic visit", "text": source})
        rec("c", "POST", f"/api/p/{PID}/notes", r.status_code, r.json().keys())
        check("note accepted (201, queued)", r.status_code == 201)
        note_id = r.json()["id"]
        state = "queued"
        while time.time() - t0 < 900:
            s = A.api("GET", f"/api/p/{PID}/status").json()
            state = s["state"]
            if state in ("done", "failed"):
                break
            time.sleep(3)
        wait = time.time() - t0
        rec("c", "GET", f"/api/p/{PID}/status (polled)", 200, s.keys())
        log(f"  - **real-model wait time: {wait:.0f} s**, final state: {state}")
        check("generation finished as done", state == "done")
        if state != "done":
            raise SystemExit("generation did not finish")

        log("\n## d. Each user's view")
        from src.ner import EntityExtractor
        from src.utils import load_config
        cfg = load_config(str(ROOT / "config.yaml"))
        meds = sorted({e["text"] for e in EntityExtractor(cfg.get("ner", {})).extract(source) if e["label"] == "MEDICATION"})
        log(f"  - (extractor found {len(meds)} medication name(s) in the source; names not recorded here)")
        fragments = [ln.strip() for ln in source.splitlines() if len(ln.strip()) > 25][:6]
        views = {}
        for u in (A, B, C, D):
            o = u.api("GET", f"/api/p/{PID}/outputs")
            src = u.api("GET", f"/api/p/{PID}/notes/{note_id}/source")
            pages = [u.c.get(p) for p in (f"/p/{PID}", f"/p/{PID}/summaries")]
            for tab in ("patient", "caregiver", "child"):
                pages.append(u.c.get(f"/p/{PID}/summaries?tab={tab}"))
            views[u.role] = (o, src, pages)
            rec("d", "GET", f"/api/p/{PID}/outputs ({u.role})", o.status_code, o.json().keys() if o.status_code == 200 else None)
            rec("d", "GET", f"/api/p/{PID}/notes/{{n}}/source ({u.role})", src.status_code)
        for role in ("creator", "caregiver"):
            o, src, _ = views[role]
            j = o.json()
            check(f"{role} sees all three outputs", all(k in j for k in ("patient_summary", "caregiver_checklist", "child_explanation")))
            check(f"{role} sees the source note", src.status_code == 200)
            check(f"{role} sees flags", "flags" in j or "flags" in json.dumps(j))
        o, src, pages = views["patient"]
        j = o.json()
        check("patient gets only the patient summary", "patient_summary" in j and "caregiver_checklist" not in j and "child_explanation" not in j)
        check("patient is refused the source note", src.status_code in (403, 404))
        o, src, pages_d = views["child"]
        jd = o.json()
        check("child gets only the child explanation", "child_explanation" in jd and "patient_summary" not in jd and "caregiver_checklist" not in jd)
        check("child is refused the source note", src.status_code in (403, 404))
        unit = re.compile(r"\d\s*(?:mg|mcg|ml|g|iu|units?|tablets?|capsules?|pills?|days?|hours?|times?)\b", re.I)
        for role in ("patient", "child"):
            o, src, pages = views[role]
            blob = o.text + "\n".join(p.text for p in pages) + src.text
            check(f"{role}: no source-note text in any response", not any(f in blob for f in fragments))
            check(f"{role}: no flags / retention data in any response", not re.search(r"retention|child_gate|unsupported|model_hash", blob))
            if role == "child":
                check("child: no medication name in any response", not any(m.lower() in blob.lower() for m in meds))
                check("child: no digit followed by a unit (API body)", not unit.search(o.text))
            else:
                check("patient: no checklist/child text keys", "child_explanation" not in o.text and "caregiver_checklist" not in o.text)
        gate_withheld = "grown-up will help explain" in jd["child_explanation"]
        log(f"  - child output: **{'WITHHELD by the safety gate (safe message shown)' if gate_withheld else 'PASSED the gate (generated text shown)'}**")

        log("\n## e. B ticks a checklist item; A sees who and when")
        jb = views["caregiver"][0].json()
        items = jb["caregiver_checklist"]
        items = items if isinstance(items, list) else items.get("items", [])
        r = B.api("POST", f"/api/p/{PID}/checklist/{note_id}/0", {"ticked": "1"})
        rec("e", "POST", f"/api/p/{PID}/checklist/{{n}}/0", r.status_code, r.json().keys() if r.status_code == 200 else None)
        check("B's tick accepted", r.status_code == 200)
        ja = A.api("GET", f"/api/p/{PID}/outputs").json()
        it = (ja["caregiver_checklist"] if isinstance(ja["caregiver_checklist"], list) else ja["caregiver_checklist"].get("items", []))[0]
        rec("e", "GET", f"/api/p/{PID}/outputs (A, after tick)", 200, it.keys())
        check("A sees ticked_by = B and a ticked_at time", it.get("ticked") and it.get("ticked_by") == B.name and bool(it.get("ticked_at")))

        log("\n## screenshots (1280 px, each role's dashboard, via the login form)")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch()
            for u in (A, B, C, D):
                ctx = br.new_context(viewport={"width": 1280, "height": 900})
                pg = ctx.new_page()
                pg.goto(base + "/login")
                pg.fill("input[name=email]", u.email); pg.fill("input[name=password]", u.password)
                pg.click("button[type=submit]")
                pg.wait_for_url(re.compile(r"/profiles|/p/"))
                pg.goto(base + f"/p/{PID}")
                pg.screenshot(path=str(SHOTS / f"dashboard-{u.role}-1280.png"), full_page=True)
                ctx.close()
            br.close()
        log("  - 4 screenshots written to `app/audit/screenshots/e2e/` (they show synthetic generated text)")

        log("\n## f. A revokes B; B is locked out; A deletes the note")
        mid = {m["display_name"]: m for m in A.api("GET", f"/api/p/{PID}/circle").json()}[B.name]["membership_id"]
        r = A.form(f"/p/{PID}/circle/members/{mid}/revoke", {}, f"/p/{PID}/circle")
        rec("f", "POST", f"/p/{PID}/circle/members/{{n}}/revoke", r.status_code)
        r1 = B.api("GET", f"/api/p/{PID}/outputs")
        r2 = B.c.get(f"/p/{PID}")
        rec("f", "GET", f"/api/p/{PID}/outputs (B after revoke)", r1.status_code)
        rec("f", "GET", f"/p/{PID} (B after revoke)", r2.status_code)
        check("B's next API request is refused", r1.status_code in (401, 403, 404))
        check("B's next page request shows only the 'Access removed' page, with no profile name, note title or generated text",
              "Access removed" in r2.text and not any(s in r2.text for s in ("Pat Example", "Grandma", "Synthetic clinic visit", "Care checklist")))
        r = A.api("POST", f"/api/p/{PID}/notes/{note_id}/delete")
        rec("f", "POST", f"/api/p/{PID}/notes/{{n}}/delete", r.status_code)
        check("note deleted", r.status_code == 200)
        r1 = A.api("GET", f"/api/p/{PID}/notes/{note_id}/outputs")
        r2 = A.api("GET", f"/api/p/{PID}/outputs")
        rec("f", "GET", f"/api/p/{PID}/notes/{{n}}/outputs (after delete)", r1.status_code)
        rec("f", "GET", f"/api/p/{PID}/outputs (after delete)", r2.status_code, r2.json().keys() if r2.status_code == 200 else None)
        check("deleted note's outputs are gone (404)", r1.status_code == 404)
        check("latest outputs no longer contain any generated text", "patient_summary" not in r2.text or r2.status_code != 200)
        check("note list is empty", A.api("GET", f"/api/p/{PID}/notes").json() == [])

        log(f"\n## Result\n\n{'ALL CHECKS PASSED' if not FAILS else 'FAILED: ' + '; '.join(FAILS)}. Real-model wait: {wait:.0f} s.")
    finally:
        server.terminate()
        try:
            server.wait(15)
        except Exception:
            server.kill()
        shutil.rmtree(tmp, ignore_errors=True)
        (OUT / "e2e_transcript.md").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
