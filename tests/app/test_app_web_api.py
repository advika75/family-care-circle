"""HTTP behaviour: CSRF, security headers, uploads, size limits, checklist ticking, polling."""

from __future__ import annotations

import threading

import pytest

from app import csrf, notes, security
from fcc_testlib import FakePipeline, SOURCE_TEXT


@pytest.fixture
def circle_world(conn, ctx, runner, world, browser):
    owner = world.user("Olivia Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara Carer", can_add_notes=True)
    cg2, _ = world.member(p, owner, "caregiver", "Dan Carer", can_add_notes=False)
    pt, _ = world.member(p, owner, "patient", "Pat Patient")
    ch, _ = world.member(p, owner, "child", "Kid Kidson")

    class W:
        pass
    w = W()
    w.p, w.pid = p, p["patient_id"]
    w.users = dict(owner=owner, caregiver=cg, caregiver_no_notes=cg2, patient=pt, child=ch)
    w.b = {k: browser(u) for k, u in w.users.items()}
    w.url = f"/api/p/{w.pid}/notes"
    return w


# --- CSRF ---------------------------------------------------------------------------------------------------
def test_post_without_a_csrf_token_is_rejected_and_changes_nothing(conn, circle_world):
    r = circle_world.b["owner"].post(circle_world.url, data={"title": "t", "text": SOURCE_TEXT}, token=None)
    assert r.status_code == 403 and "verified" in r.json()["error"]["message"]
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_wrong_forged_and_other_sessions_csrf_tokens_are_rejected(conn, settings, circle_world):
    owner, cg = circle_world.b["owner"], circle_world.b["caregiver"]
    forged = csrf.make_token(b"z" * 32, security.hash_token(owner.token))            # right session, wrong server key
    for token in ("garbage", forged, cg.csrf):                                         # cg.csrf belongs to another session
        r = owner.post(circle_world.url, data={"title": "t", "text": SOURCE_TEXT}, token=token)
        assert r.status_code == 403, token
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_csrf_token_as_a_form_field_is_accepted(conn, circle_world):
    owner = circle_world.b["owner"]
    r = owner.post(circle_world.url, data={"title": "t", "text": SOURCE_TEXT, "csrf_token": owner.csrf}, token=None)
    assert r.status_code == 201 and conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_every_state_changing_endpoint_requires_csrf(conn, ctx, runner, circle_world):
    owner = circle_world.b["owner"]
    n = notes.add_note(conn, ctx, runner, circle_world.users["owner"], circle_world.p, title="x", text="t")
    runner.drain()
    for url in (circle_world.url, f"{circle_world.url}/{n['id']}/delete", f"/api/p/{circle_world.pid}/checklist/{n['id']}/0"):
        assert owner.post(url, data={"text": "x"}, token=None).status_code == 403, url
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_state_changing_requests_need_a_session_first(circle_world, browser):
    anon = browser(circle_world.users["owner"], login=False)
    assert anon.post(circle_world.url, data={"text": "x"}, token=None).status_code == 401


def test_get_requests_never_change_state(conn, circle_world):
    for url in (f"/api/p/{circle_world.pid}/outputs", circle_world.url):
        circle_world.b["owner"].get(url)
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


# --- security headers ---------------------------------------------------------------------------------------
def test_security_headers_on_success_and_error_responses(circle_world):
    for r in (circle_world.b["owner"].get(f"/api/p/{circle_world.pid}/outputs"),
              circle_world.b["owner"].get("/api/p/FCC-AAAA-AAAA/outputs"),
              circle_world.b["owner"].get("/definitely/not/here")):
        h = r.headers
        csp = h["content-security-policy"]
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp and "default-src 'self'" in csp and "object-src 'none'" in csp
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer" and h["cache-control"] == "no-store"
        assert "strict-transport-security" not in h                                     # only when APP_HTTPS=1


def test_hsts_only_when_https_is_enabled(settings, ctx, runner, conn, world, browser):
    from dataclasses import replace
    from app.web.main import create_app
    https = replace(settings, https=True)
    from fastapi.testclient import TestClient
    r = TestClient(create_app(https, ctx=ctx, runner=runner, start_worker=False)).get("/nope")
    assert "max-age=" in r.headers["strict-transport-security"]


def test_api_docs_are_not_exposed(circle_world):
    for url in ("/docs", "/redoc", "/openapi.json"):
        assert circle_world.b["owner"].get(url).status_code == 404


def test_unexpected_errors_return_a_generic_message(circle_world, app, conn, monkeypatch):
    from app import outputs
    monkeypatch.setattr(outputs, "latest_outputs", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret note text 123-45-6789")))
    r = circle_world.b["owner"].get(f"/api/p/{circle_world.pid}/outputs")
    assert r.status_code == 500 and r.json()["error"]["code"] == "server_error"
    assert "secret" not in r.text and "123-45" not in r.text and "Traceback" not in r.text


# --- adding notes over HTTP ---------------------------------------------------------------------------------
def test_creator_and_permitted_caregiver_can_add_notes_others_cannot(conn, circle_world):
    url = circle_world.url
    for who, code in (("owner", 201), ("caregiver", 201), ("caregiver_no_notes", 403), ("patient", 403), ("child", 403)):
        r = circle_world.b[who].post(url, data={"title": who, "text": SOURCE_TEXT})
        assert r.status_code == code, who
    assert [n["title"] for n in conn.execute("SELECT title FROM notes ORDER BY id")] == ["owner", "caregiver"]


def test_created_note_is_queued_and_enqueued(conn, circle_world, runner):
    r = circle_world.b["owner"].post(circle_world.url, data={"text": SOURCE_TEXT})
    assert r.status_code == 201 and r.json()["status"] == "queued" and r.json()["title"] == "Note 1"
    assert runner.pending() == 1


def test_txt_upload_works_and_uses_the_filename_as_the_title(conn, circle_world):
    r = circle_world.b["owner"].post(circle_world.url, files={"file": ("clinic_visit.txt", SOURCE_TEXT.encode(), "text/plain")})
    assert r.status_code == 201 and r.json()["title"] == "clinic_visit"
    assert conn.execute("SELECT text FROM notes").fetchone()[0] == SOURCE_TEXT.strip()


@pytest.mark.parametrize("files,data,field", [
    ({"file": ("scan.pdf", b"%PDF-1.4 binary", "application/pdf")}, {}, "file"),
    ({"file": ("notes.txt", b"\xff\xfe\x00\x00broken", "text/plain")}, {}, "file"),
    ({"file": ("notes.txt", SOURCE_TEXT.encode(), "text/plain")}, {"text": "and pasted text too"}, "text"),
    (None, {"text": ""}, "text"), (None, {"text": "x" * 20_001}, "text"),
])
def test_bad_submissions_get_422_with_a_field_message(conn, circle_world, files, data, field):
    r = circle_world.b["owner"].post(circle_world.url, data=data, files=files)
    assert r.status_code == 422 and r.json()["error"]["fields"][field]
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_oversized_request_bodies_are_rejected_before_parsing(conn, circle_world):
    big = b"a" * (300 * 1024)
    r = circle_world.b["owner"].post(circle_world.url, files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_hostile_text_is_stored_verbatim_and_returned_as_json_not_html(conn, ctx, runner, circle_world):
    evil = "<script>alert(1)</script> \"quote\" 'apos' & <img src=x onerror=alert(2)>"
    circle_world.b["owner"].post(circle_world.url, data={"title": "<b>bold</b>", "text": evil})
    runner.drain()
    r = circle_world.b["owner"].get(f"/api/p/{circle_world.pid}/notes/1/source")
    assert r.headers["content-type"].startswith("application/json") and r.json()["text"] == evil and r.json()["title"] == "<b>bold</b>"


# --- checklist ----------------------------------------------------------------------------------------------
@pytest.fixture
def with_note(conn, ctx, runner, circle_world):
    n = notes.add_note(conn, ctx, runner, circle_world.users["owner"], circle_world.p, title="Visit", text=SOURCE_TEXT)
    runner.drain()
    circle_world.nid = n["id"]
    circle_world.tick = lambda who, i, ticked="1": circle_world.b[who].post(
        f"/api/p/{circle_world.pid}/checklist/{n['id']}/{i}", data={"ticked": ticked})
    return circle_world


def test_adults_can_tick_and_everyone_with_checklist_access_sees_who_and_when(with_note):
    w = with_note
    r = w.tick("caregiver", 1)
    assert r.status_code == 200 and r.json()["ticked"] is True and r.json()["ticked_by"] == "Cara Carer"
    assert r.json()["ticked_at"] == "2026-01-15T12:00:00Z" and (r.json()["done"], r.json()["total"]) == (1, 3)
    for who in ("owner", "caregiver", "caregiver_no_notes"):
        items = w.b[who].get(f"/api/p/{w.pid}/outputs").json()["caregiver_checklist"]
        assert items[1]["ticked"] and items[1]["ticked_by"] == "Cara Carer" and not items[0]["ticked"]
    assert w.b["owner"].get(f"/api/p/{w.pid}/outputs").json()["checklist_progress"] == {"done": 1, "total": 3}


def test_unticking_removes_the_record(conn, with_note):
    with_note.tick("owner", 0)
    r = with_note.tick("owner", 0, ticked="0")
    assert r.json()["ticked"] is False and r.json()["done"] == 0
    assert conn.execute("SELECT COUNT(*) FROM checklist_ticks").fetchone()[0] == 0


def test_ticking_again_updates_who_ticked(with_note):
    with_note.tick("owner", 0)
    r = with_note.tick("caregiver", 0)
    assert r.json()["ticked_by"] == "Cara Carer" and r.json()["done"] == 1


@pytest.mark.parametrize("who", ["patient", "child"])
def test_patient_and_child_cannot_tick_or_see_progress(with_note, who):
    r = with_note.tick(who, 0)
    assert r.status_code == 403
    assert "checklist" not in with_note.b[who].get(f"/api/p/{with_note.pid}/outputs").text


@pytest.mark.parametrize("index", [3, 99, -1])
def test_out_of_range_items_are_404(with_note, index):
    assert with_note.tick("owner", index).status_code == 404


def test_progress_is_per_circle(conn, ctx, runner, world, browser, with_note):
    other_owner = world.user("Other Owner"); other = world.profile(other_owner, "Other")
    n2 = notes.add_note(conn, ctx, runner, other_owner, other, title="Theirs", text="t"); runner.drain()
    with_note.tick("owner", 0)
    r = browser(other_owner).get(f"/api/p/{other['patient_id']}/outputs").json()
    assert r["checklist_progress"] == {"done": 0, "total": 3}
    cross = with_note.b["owner"].post(f"/api/p/{with_note.pid}/checklist/{n2['id']}/0", data={})
    assert cross.status_code == 404                                                    # a note from another circle


# --- polling with the real worker thread ---------------------------------------------------------------------
def test_status_endpoint_shows_queued_running_done_while_the_worker_runs(conn, ctx, settings, pipeline, runner, circle_world):
    gate = threading.Event()
    pipeline.gate = gate
    owner = circle_world.b["owner"]
    owner.post(circle_world.url, data={"title": "Visit", "text": SOURCE_TEXT})
    status_url = f"/api/p/{circle_world.pid}/status"
    assert owner.get(status_url).json()["state"] == "queued"
    runner.start()
    try:
        for _ in range(200):
            if owner.get(status_url).json()["state"] == "running":
                break
            threading.Event().wait(0.01)
        assert owner.get(status_url).json()["state"] == "running"
        assert circle_world.b["patient"].get(status_url).json()["state"] == "running"        # patients see "being prepared"
        assert circle_world.b["patient"].get(f"/api/p/{circle_world.pid}/outputs").json()["available"] is False
        gate.set()
        assert runner.wait_idle(10)
    finally:
        gate.set()
        runner.stop()
    assert owner.get(status_url).json()["state"] == "done"
    assert circle_world.b["patient"].get(f"/api/p/{circle_world.pid}/outputs").json()["available"] is True


def test_app_lifespan_starts_and_stops_the_worker(settings, ctx, pipeline, conn, world):
    from fastapi.testclient import TestClient
    from app.jobs import JobRunner
    from app.web.main import create_app
    r = JobRunner(settings, ctx, pipeline_factory=lambda: pipeline)
    owner = world.user("Owner"); p = world.profile(owner)
    n = notes.add_note(conn, ctx, None, owner, p, title="x", text="t")          # left 'queued' in the database
    with TestClient(create_app(settings, ctx=ctx, runner=r, start_worker=True)):      # startup: recover() + worker thread
        assert r.wait_idle(10)
    assert conn.execute("SELECT status FROM notes WHERE id = ?", (n["id"],)).fetchone()[0] == "done"
    assert r._thread is not None and not r._thread.is_alive()
