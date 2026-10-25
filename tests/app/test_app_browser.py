"""Real-browser checks (Playwright + Chromium) against a real uvicorn process on a scratch database.

Marked ``browser``: skipped unless ``APP_RUN_SLOW=1`` (``make app-test-slow``). Needs ``requirements-app-dev.txt`` and
``python -m playwright install chromium``. Screenshots (360 / 768 / 1280 px) are written to ``app/audit/screenshots/``.
All data is synthetic and created in a temporary database.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
pw_sync = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "app" / "audit" / "screenshots"
WIDTHS = (360, 768, 1280)
PW = "a browser test passphrase 1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "tests" / "app"))
    from app import accounts, circle, notes, outputs
    from app.config import Settings
    from app.context import Ctx
    from app.db import connect, migrate
    from fcc_testlib import make_record, SOURCE_TEXT

    tmp = tmp_path_factory.mktemp("browser")
    db = tmp / "b.sqlite3"
    settings = Settings(db_path=db, scrypt_n=2 ** 14, secret_key=b"k" * 32)
    ctx = Ctx(settings)
    conn = connect(db)
    migrate(conn)

    def user(name, email):
        return accounts.signup(conn, ctx, email=email, display_name=name, password=PW)

    creator = user("Olivia Owner", "olivia@example.test")
    profile = circle.create_profile(conn, ctx, creator, display_name="Pat Example", preferred_name="Grandma",
                                    year_of_birth=1948, care_notes="Likes tea.", relationship_label="Daughter")
    people = {"creator": creator}
    for role, name in (("caregiver", "Carla Carer"), ("patient", "Pat Patient"), ("child", "Sam Child")):
        u = user(name, f"{role}@example.test")
        _, code = circle.create_invitation(conn, ctx, creator, profile, role=role, note=f"for {name}")
        m = circle.join(conn, ctx, u, patient_id=profile["patient_id"], code=code, relationship_label="Other relative")
        circle.approve_member(conn, ctx, creator, profile, m["id"])
        if role == "caregiver":
            circle.set_can_add_notes(conn, ctx, creator, profile, m["id"], True)
        people[role] = u
    pending = user("Penny Pending", "pending@example.test")
    _, code = circle.create_invitation(conn, ctx, creator, profile, role="child")
    circle.join(conn, ctx, pending, patient_id=profile["patient_id"], code=code, relationship_label="Other relative")

    class _Runner:                                    # notes are stored 'queued'; the browser server's own worker is idle
        def enqueue(self, _id): pass
    note = notes.add_note(conn, ctx, _Runner(), creator, profile, title="Clinic visit", text=SOURCE_TEXT)
    built = outputs.build_output(make_record(), SOURCE_TEXT)
    outputs.store_output(conn, ctx, note["id"], profile["id"], built)
    conn.execute("UPDATE notes SET status='done', finished_at='2026-01-15T12:00:00+00:00' WHERE id=?", (note["id"],))
    conn.commit()

    port = _free_port()
    env = {**os.environ, "APP_DB_PATH": str(db), "APP_BACKEND": "mock", "APP_SECRET_KEY": "k" * 64,
           "APP_JOB_ISOLATION": "thread"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.web.main:create_app", "--factory", "--host", "127.0.0.1",
                             "--port", str(port), "--no-server-header", "--log-level", "warning"], cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield {"base": base, "conn": conn, "profile": profile, "pid": profile["patient_id"], "note_id": note["id"],
           "ctx": ctx, "creator": creator}
    proc.terminate()
    proc.wait(10)


@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _shot(page, name: str, width: int) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)


def _page(browser, world, width, email=None):
    ctxb = browser.new_context(viewport={"width": width, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    page = ctxb.new_page()
    if email:
        page.goto(world["base"] + "/login")
        page.fill("input[name=email]", email)
        page.fill("input[name=password]", PW)
        page.click("button[type=submit]")
        page.wait_for_url(re.compile(r"/profiles|/p/"))
    return ctxb, page


def _set_state(world, status, message=None):
    c = world["conn"]
    c.execute("UPDATE notes SET status=?, error_message=? WHERE id=?", (status, message, world["note_id"]))
    c.commit()


# ------------------------------------------------------------------------------------------- screenshots
@pytest.mark.parametrize("width", WIDTHS)
def test_screenshots_public_pages(browser, world, width):
    ctxb, page = _page(browser, world, width)
    for name, path in (("welcome", "/"), ("signup", "/signup"), ("login", "/login"), ("not-found", "/no-such-page")):
        page.goto(world["base"] + path)
        _shot(page, name, width)
    page.goto(world["base"] + "/unauthorized")
    _shot(page, "unauthorized-loggedout", width)
    ctxb.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_screenshots_signed_in_pages(browser, world, width):
    pid = world["pid"]
    # a brand-new account: empty profiles list, stepper, join
    ctxb, page = _page(browser, world, width)
    page.goto(world["base"] + "/signup")
    page.fill("input[name=display_name]", "Nina Newcomer")
    page.fill("input[name=email]", f"nina{width}@example.test")
    page.fill("input[name=password]", PW)
    page.click("button[type=submit]")
    page.wait_for_url(re.compile(r"/profiles"))
    _shot(page, "profiles-empty", width)
    page.goto(world["base"] + "/join")
    _shot(page, "join", width)
    page.goto(world["base"] + "/profiles/new")
    _shot(page, "stepper-1", width)
    page.fill("input[name=display_name]", "Pat Example")
    page.click("button[value=next]")
    _shot(page, "stepper-2", width)
    page.fill("textarea[name=care_notes]", "Likes tea.")
    page.click("button[value=next]")
    _shot(page, "stepper-3", width)
    page.select_option("select[name=relationship_label]", "Daughter")
    page.click("button[value=next]")
    _shot(page, "stepper-4", width)
    page.click("button[value=create]")
    page.wait_for_url(re.compile(r"/created"))
    _shot(page, "profile-created", width)
    page.goto(world["base"] + "/settings")
    _shot(page, "settings", width)
    ctxb.close()

    for role in ("creator", "caregiver", "patient", "child"):
        ctxb, page = _page(browser, world, width, f"{'olivia' if role == 'creator' else role}@example.test")
        page.goto(world["base"] + f"/p/{pid}")
        _shot(page, f"dashboard-{role}", width)
        if role in ("creator", "caregiver"):
            page.goto(world["base"] + f"/p/{pid}/circle")
            _shot(page, f"circle-{role}", width)
            page.goto(world["base"] + f"/p/{pid}/summaries")
            _shot(page, f"summaries-{role}", width)
        if role == "creator":
            page.goto(world["base"] + f"/p/{pid}/notes")
            for state, msg in (("queued", None), ("running", None), ("failed", "We could not prepare this note."), ("done", None)):
                _set_state(world, state, msg)
                page.goto(world["base"] + f"/p/{pid}/notes")
                _shot(page, f"notes-{state}", width)
                page.goto(world["base"] + f"/p/{pid}")
                _shot(page, f"dashboard-creator-{state}", width)
        if role == "child":
            page.goto(world["base"] + f"/p/{pid}/circle")
            _shot(page, "unauthorized-child-circle", width)
        ctxb.close()


# ---------------------------------------------------------------------------------- F-20 behaviour checks
def test_menu_fits_a_360px_screen(browser, world):
    ctxb, page = _page(browser, world, 360, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}")
    page.click("nav details summary")
    box = page.locator(".menu-panel").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 360, box
    assert page.evaluate("document.documentElement.scrollWidth") <= 360          # no sideways scrolling anywhere
    ctxb.close()


def test_menu_closes_on_escape_and_on_outside_click(browser, world):
    ctxb, page = _page(browser, world, 1280, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}")
    d = page.locator("nav details")
    page.click("nav details summary")
    assert d.evaluate("e => e.open")
    page.keyboard.press("Escape")
    assert not d.evaluate("e => e.open")
    assert page.evaluate("document.activeElement && document.activeElement.tagName") == "SUMMARY"   # focus returns
    page.click("nav details summary")
    page.click("main", position={"x": 5, "y": 300})
    assert not d.evaluate("e => e.open")
    ctxb.close()


def test_copy_button_says_copied(browser, world):
    ctxb, page = _page(browser, world, 1280, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}/circle")
    page.select_option("form[action$='/circle/invite'] select[name=role]", "caregiver")
    with page.expect_navigation():
        page.click("form[action$='/circle/invite'] button[type=submit]")
    page.click("[data-copy-target='invite-code']")
    pw_sync.expect(page.locator("#invite-code-status")).to_have_text("Copied")
    assert re.fullmatch(r"[A-Z0-9-]{19}", page.evaluate("navigator.clipboard.readText()"))
    ctxb.close()


def test_polling_refreshes_when_the_note_finishes(browser, world):
    _set_state(world, "queued")
    ctxb, page = _page(browser, world, 1280, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}")
    assert page.locator("[data-poll-url]").count() == 1
    _set_state(world, "done")
    page.wait_for_selector("[data-poll-url]", state="detached", timeout=20_000)       # page reloaded by itself
    ctxb.close()


def test_tabs_work_with_the_keyboard(browser, world):
    ctxb, page = _page(browser, world, 1280, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}/summaries")
    tabs = page.locator(".tabs a")
    assert tabs.count() >= 2
    tabs.nth(1).focus()
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"tab="))
    assert "tab=" in page.url
    ctxb.close()


def test_stepper_is_usable_with_the_keyboard_only(browser, world):
    ctxb, page = _page(browser, world, 360, "olivia@example.test")
    page.goto(world["base"] + "/profiles/new")
    page.focus("input[name=display_name]")
    page.keyboard.type("Keyboard Pat")
    page.keyboard.press("Enter")                      # Enter in a field must go FORWARD (F-18)
    page.wait_for_selector("[aria-label='Progress: step 2 of 4']")
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.name || document.activeElement.tagName")
    assert focused
    ctxb.close()


def test_important_inline_links_are_44px_tall(browser, world):
    _set_state(world, "queued")
    ctxb, page = _page(browser, world, 360, "olivia@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}")
    h = page.locator(".refresh-link").bounding_box()["height"]
    assert h >= 44, h
    _set_state(world, "done")
    ctxb.close()


def test_bigger_words_toggle_changes_size_and_is_remembered(browser, world):
    ctxb, page = _page(browser, world, 360, "child@example.test")
    page.goto(world["base"] + f"/p/{world['pid']}")
    text = page.locator(".persona-child .persona-body p").first
    before = text.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
    btn = page.locator("[data-bigger-words]")
    btn.click()
    after = text.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
    assert after > before and btn.get_attribute("aria-pressed") == "true"
    _shot(page, "dashboard-child-bigger", 360)
    page.reload()
    assert text.evaluate("e => parseFloat(getComputedStyle(e).fontSize)") == after       # remembered in this browser
    page.locator("[data-bigger-words]").click()
    assert text.evaluate("e => parseFloat(getComputedStyle(e).fontSize)") == before
    ctxb.close()
