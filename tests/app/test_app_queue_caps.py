"""F-03: one circle (or user) must not be able to fill the single worker's queue."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app import notes
from app.context import Ctx
from app.errors import QueueFull
from app.jobs import JobRunner
from conftest import Site
from fcc_testlib import FakePipeline, csrf_from


@pytest.fixture
def capped(settings):
    return replace(settings, max_pending_per_circle=3, max_pending_total=5)


@pytest.fixture
def cctx(capped, clock):
    return Ctx(settings=capped, clock=clock)


def add(conn, ctx, runner, user, profile, title="n"):
    return notes.add_note(conn, ctx, runner, user, profile, title=title, text="some note text")


def test_defaults_are_small_but_usable():
    from app.config import Settings
    s = Settings()
    assert (s.max_pending_per_circle, s.max_pending_total) == (3, 20)
    e = Settings.from_env({"APP_MAX_PENDING_PER_CIRCLE": "7", "APP_MAX_PENDING_TOTAL": "40"})
    assert (e.max_pending_per_circle, e.max_pending_total) == (7, 40)
    with pytest.raises(ValueError):
        Settings.from_env({"APP_MAX_PENDING_PER_CIRCLE": "0"})


def test_a_circle_cannot_queue_more_than_its_cap(conn, cctx, world):
    runner = JobRunner(cctx.settings, cctx, pipeline_factory=FakePipeline)
    world.ctx = cctx
    owner = world.user("Owner"); p = world.profile(owner)
    for i in range(3):
        add(conn, cctx, runner, owner, p, f"n{i}")
    with pytest.raises(QueueFull) as e:
        add(conn, cctx, runner, owner, p, "one too many")
    assert "already waiting" in e.value.message and "try again" not in e.value.message.lower() or "Wait" in e.value.message
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 3 and runner.pending() == 3       # nothing stored or queued


def test_finished_and_failed_notes_free_the_slot(conn, cctx, world, capped):
    pipe = FakePipeline()
    runner = JobRunner(capped, cctx, pipeline_factory=lambda: pipe)
    owner = world.user("Owner"); p = world.profile(owner)
    ids = [add(conn, cctx, runner, owner, p, f"n{i}")["id"] for i in range(3)]
    runner.drain()
    add(conn, cctx, runner, owner, p, "after the first three finished")
    pipe.fail_with = RuntimeError("x")
    runner.drain()                                                        # the 4th fails: failed notes do not count
    for i in range(3):                                                    # the failed note freed its slot: three more fit
        add(conn, cctx, runner, owner, p, f"again{i}")
    with pytest.raises(QueueFull):                                        # ... and the fourth does not
        add(conn, cctx, runner, owner, p, "too many again")
    assert conn.execute("SELECT COUNT(*) FROM notes WHERE status IN ('queued','running')").fetchone()[0] == 3


def test_the_cap_is_per_circle_so_other_circles_are_unaffected(conn, cctx, world):
    runner = JobRunner(cctx.settings, cctx, pipeline_factory=FakePipeline)
    a, b = world.user("A"), world.user("B")
    pa, pb = world.profile(a, "Alpha"), world.profile(b, "Beta")
    for i in range(3):
        add(conn, cctx, runner, a, pa)
    with pytest.raises(QueueFull):
        add(conn, cctx, runner, a, pa)
    add(conn, cctx, runner, b, pb)                                        # circle B still gets its turn


def test_a_global_cap_protects_the_worker_from_many_circles(conn, cctx, world):
    runner = JobRunner(cctx.settings, cctx, pipeline_factory=FakePipeline)
    owners = [world.user(f"O{i}") for i in range(4)]
    profiles = [world.profile(o, f"P{i}") for i, o in enumerate(owners)]
    for o, p in zip(owners[:2], profiles[:2]):
        add(conn, cctx, runner, o, p); add(conn, cctx, runner, o, p)
    add(conn, cctx, runner, owners[2], profiles[2])                       # 5 pending in total = the global cap
    with pytest.raises(QueueFull) as e:
        add(conn, cctx, runner, owners[3], profiles[3])
    assert "busy" in e.value.message.lower()


def test_over_http_the_page_and_the_api_answer_429_with_a_clear_message(app, capped, ctx, runner, world, conn, clock):
    from app.web.main import create_app
    from app.jobs import JobRunner as JR
    cctx = Ctx(settings=capped, clock=clock)
    r2 = JR(capped, cctx, pipeline_factory=FakePipeline)
    capped_app = create_app(capped, ctx=cctx, runner=r2, start_worker=False)
    owner = world.user("Owner", email="cap-owner@example.test"); p = world.profile(owner)
    site = Site(capped_app); assert site.login("cap-owner@example.test").status_code == 303
    token = csrf_from(site.get("/settings").text)
    for i in range(3):
        assert site.post(f"/p/{p['patient_id']}/notes", {"title": f"n{i}", "text": "note text", "csrf_token": token}).status_code == 303
    page = site.post(f"/p/{p['patient_id']}/notes", {"title": "x", "text": "note text", "csrf_token": token})
    assert page.status_code == 429 and "already waiting" in page.text
    api = site.client.post(f"/api/p/{p['patient_id']}/notes", data={"title": "x", "text": "t"}, headers={"x-csrf-token": token})
    assert api.status_code == 429 and api.json()["error"]["code"] == "queue_full"
