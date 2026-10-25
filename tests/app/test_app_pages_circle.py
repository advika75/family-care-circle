"""Create-profile stepper, profile-created page, join page and the pending/removed pages."""

from __future__ import annotations

import re

import pytest

from app import circle, ids, permissions as P
from conftest import Site
from fcc_testlib import PASSWORD, assert_clean_page, csrf_from

VALID = {"display_name": "Pat Example", "preferred_name": "Grandma", "year_of_birth": "1948",
         "care_notes": "Likes tea. Hard of hearing on the left.", "relationship_label": "Daughter"}


@pytest.fixture
def me(app):
    s = Site(app)
    assert s.signup(name="Olivia Owner", email="olivia@example.test").status_code == 303
    return s


def step(me, n, data, action="next"):
    token = csrf_from(me.get("/profiles/new").text)
    return me.post("/profiles/new", {**data, "step": str(n), "action": action, "csrf_token": token})


def current_step(html):
    m = re.search(r'aria-label="Progress: step (\d) of 4"', html)
    return int(m.group(1)) if m else None


# --- stepper ------------------------------------------------------------------------------------------------
def test_stepper_starts_at_step_one_with_four_labelled_steps(me):
    r = me.get("/profiles/new")
    assert r.status_code == 200 and current_step(r.text) == 1
    for label in ("Patient basics", "Care information", "Your details", "Review"):
        assert label in r.text
    assert 'aria-current="step"' in r.text
    assert_clean_page(r.text)


def test_step_one_validates_before_moving_on(me):
    r = step(me, 1, {"display_name": " ", "year_of_birth": "19x0", "preferred_name": ""})
    assert r.status_code == 422 and current_step(r.text) == 1
    assert "Please enter a name." in r.text and "Enter a year between 1900" in r.text
    assert 'aria-invalid="true"' in r.text
    ok = step(me, 1, {"display_name": "Pat", "year_of_birth": "", "preferred_name": ""})
    assert ok.status_code == 200 and current_step(ok.text) == 2


def test_step_two_enforces_the_care_notes_limit_and_warns_about_identifiers(me):
    page = step(me, 1, VALID).text
    assert "Do not enter identifiers" in page
    r = step(me, 2, {**VALID, "care_notes": "n" * 2001})
    assert r.status_code == 422 and current_step(r.text) == 2 and "at most 2000" in r.text


def test_step_three_requires_a_relationship_from_the_list(me):
    r = step(me, 3, {**VALID, "relationship_label": ""})
    assert r.status_code == 422 and current_step(r.text) == 3 and "Choose how you are related" in r.text
    r = step(me, 3, {**VALID, "relationship_label": "Overlord"})
    assert r.status_code == 422
    for label in circle.RELATIONSHIP_LABELS:
        assert f'<option value="{label}"' in step(me, 2, VALID).text
    assert current_step(step(me, 3, VALID).text) == 4


def test_review_shows_everything_and_values_carry_between_steps(me):
    r = step(me, 3, VALID)
    for v in ("Pat Example", "Grandma", "1948", "Likes tea.", "Daughter"):
        assert v in r.text
    assert "not a password" in r.text
    back = step(me, 4, VALID, action="back")
    assert current_step(back.text) == 3 and 'value="Pat Example"' in back.text and 'selected' in back.text


def test_back_button_works_without_validating(me):
    r = step(me, 2, {**VALID, "care_notes": "n" * 5000}, action="back")
    assert r.status_code == 200 and current_step(r.text) == 1


def test_create_makes_the_profile_membership_and_redirects_to_the_confirmation(me, conn):
    r = step(me, 4, VALID, action="create")
    assert r.status_code == 303
    pid = r.headers["location"].removeprefix("/p/").removesuffix("/created")
    assert ids.PATIENT_ID_RE.match(pid)
    p = conn.execute("SELECT * FROM profiles").fetchone()
    assert p["patient_id"] == pid and (p["display_name"], p["preferred_name"], p["year_of_birth"]) == ("Pat Example", "Grandma", 1948)
    m = conn.execute("SELECT * FROM memberships").fetchone()
    assert (m["role"], m["status"], m["can_add_notes"], m["relationship_label"]) == ("creator", "active", 1, "Daughter")


def test_tampered_hidden_fields_at_the_end_send_you_back_to_the_bad_step_and_create_nothing(me, conn):
    r = step(me, 4, {**VALID, "display_name": ""}, action="create")
    assert r.status_code == 422 and current_step(r.text) == 1 and "Please enter a name." in r.text
    r = step(me, 4, {**VALID, "year_of_birth": "3000"}, action="create")
    assert r.status_code == 422 and current_step(r.text) == 1
    r = step(me, 4, {**VALID, "relationship_label": "Nobody"}, action="create")
    assert r.status_code == 422 and current_step(r.text) == 3
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


def test_the_stepper_post_needs_csrf_and_a_login(me, app, conn):
    assert me.post("/profiles/new", {**VALID, "step": "4", "action": "create"}).status_code == 403
    anon = Site(app)
    assert anon.post("/profiles/new", {**VALID, "step": "4", "action": "create"}).status_code == 303   # to /login
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


HOSTILE = "<script>alert(1)</script>{{ 7*7 }}{% raw %}'\"&<img src=x onerror=alert(2)>"


def test_hostile_values_are_escaped_on_every_step_and_never_executed(me):
    data = {**VALID, "display_name": HOSTILE, "preferred_name": HOSTILE, "care_notes": HOSTILE}
    pages = [step(me, 1, data).text, step(me, 2, data).text, step(me, 3, data).text]
    for html in pages:
        assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
        assert "49" not in re.sub(r"\d{3,}", "", html.split("<main")[1]) or "{{ 7*7 }}" in html or "&#" in html
        assert_clean_page(html)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in pages[2]               # the review page, escaped
    assert "{{ 7*7 }}" in pages[2] or "{{ 7*7 }}".replace("{", "&#123;") in pages[2]   # template syntax stays literal text


def test_a_very_long_name_is_rejected_not_truncated_silently(me):
    r = step(me, 1, {**VALID, "display_name": "x" * 500})
    assert r.status_code == 422 and "at most 80" in r.text


# --- profile created ----------------------------------------------------------------------------------------
@pytest.fixture
def created(me, conn):
    r = step(me, 4, VALID, action="create")
    return r.headers["location"], conn.execute("SELECT * FROM profiles").fetchone()


def test_created_page_shows_id_copy_button_role_and_how_to_invite(me, created):
    url, p = created
    r = me.get(url)
    assert r.status_code == 200
    assert f'<span class="code-box" id="patient-id">{p["patient_id"]}</span>' in r.text
    assert 'data-copy-target="patient-id"' in r.text and "data-needs-js" in r.text and "hidden" in r.text.split("data-needs-js")[1][:20]
    assert 'id="patient-id-status"' in r.text and 'aria-live="polite"' in r.text and 'role="status"' in r.text
    assert "not a password" in r.text and "Creator" in r.text
    assert f'href="/p/{p["patient_id"]}/circle"' in r.text and "Nothing is emailed" in r.text
    assert "code" in r.text.lower() and "invitation" in r.text.lower()
    assert_clean_page(r.text)


def test_created_page_is_only_for_the_creator(me, created, app, world, conn, ctx):
    url, p = created
    stranger = Site(app); stranger.signup(name="Sam Stranger", email="sam@example.test")
    assert stranger.get(url).status_code == 404
    assert stranger.get("/p/FCC-AAAA-AAAA/created").status_code == 404
    owner = conn.execute("SELECT * FROM users WHERE email = 'olivia@example.test'").fetchone()
    cg, _ = world.member(p, owner, "caregiver", "Cara Carer")
    cs = Site(app); cs.login(cg["email"])
    assert cs.get(url).status_code == 404                                # members who are not the creator


def test_profiles_list_shows_the_new_circle_with_role_and_status(me, created):
    html = me.get("/profiles").text
    assert "Pat Example" in html and "Creator" in html and "Active" in html
    assert 'class="card empty"' not in html
    assert f'href="/p/{html.split("/p/")[1].split(chr(34))[0]}"' in html          # the circle links to its dashboard


def test_nav_shows_the_open_circle_and_role_on_the_created_page(me, created):
    html = me.get(created[0]).text
    assert "Care circle:" in html and "Pat Example" in html and "chip-role-creator" in html


# --- join ---------------------------------------------------------------------------------------------------
@pytest.fixture
def circle_with_invite(conn, ctx, world, app):
    owner = world.user("Olivia Owner", email="owner2@example.test"); p = world.profile(owner, "Hidden Patient Name")
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    joiner = Site(app); joiner.signup(name="Jo Joiner", email="jo@example.test")
    return owner, p, code, joiner


def join(site, pid, code, label="Son"):
    token = csrf_from(site.get("/join").text)
    return site.post("/join", {"patient_id": pid, "code": code, "relationship_label": label, "csrf_token": token})


def test_join_page_explains_the_id_is_not_a_password(circle_with_invite):
    r = circle_with_invite[3].get("/join")
    assert r.status_code == 200 and "not a password" in r.text and "invitation code" in r.text.lower()
    assert 'name="patient_id"' in r.text and 'name="code"' in r.text and 'name="relationship_label"' in r.text
    assert_clean_page(r.text)


def test_successful_join_lands_on_the_pending_page_without_revealing_the_patient(circle_with_invite, conn):
    owner, p, code, jo = circle_with_invite
    r = join(jo, p["patient_id"].lower(), code.lower())
    assert r.status_code == 303 and r.headers["location"] == f"/p/{p['patient_id']}"
    page = jo.get(r.headers["location"])
    assert page.status_code == 200 and "Waiting for approval" in page.text and "Pending approval" in page.text
    assert "Hidden Patient Name" not in page.text and "Olivia" not in page.text          # nothing about the patient or circle
    assert_clean_page(page.text)
    m = conn.execute("SELECT * FROM memberships WHERE role = 'caregiver'").fetchone()
    assert (m["status"], m["can_add_notes"], m["relationship_label"]) == ("pending", 0, "Son")


def test_join_error_states_are_distinct_but_never_reveal_whether_an_id_exists(circle_with_invite, ctx, clock):
    owner, p, code, jo = circle_with_invite
    unknown_id = join(jo, "FCC-AAAA-AAAA", code)
    bad_code = join(jo, p["patient_id"], "AAAA-AAAA-AAAA-AAAA")
    garbage = join(jo, "nonsense", "also nonsense")
    def msg(r):
        return re.search(r'<div class="banner banner-error".*?</div>\s*</div>', r.text, re.S).group(0)
    assert unknown_id.status_code == bad_code.status_code == garbage.status_code == 400
    assert msg(unknown_id) == msg(bad_code) == msg(garbage)                  # same words: cannot tell the cases apart
    assert "do not match" in msg(bad_code)


def test_expired_and_used_invitations_have_their_own_messages(circle_with_invite, conn, ctx, clock, world, app):
    owner, p, code, jo = circle_with_invite
    _, code2 = circle.create_invitation(conn, ctx, owner, p, role="patient")
    _, code3 = circle.create_invitation(conn, ctx, owner, p, role="child")
    clock.advance(days=8)                                   # also ends the joiner's 7-day session
    assert jo.get("/join").status_code == 303
    jo.login("jo@example.test")
    r = join(jo, p["patient_id"], code2)
    assert r.status_code == 400 and "This invitation has expired" in r.text
    clock.advance(days=-8)
    other = Site(app); other.signup(name="Other Person", email="other@example.test")
    assert join(other, p["patient_id"], code3).status_code == 303
    third = Site(app); third.signup(name="Third Person", email="third@example.test")
    r = join(third, p["patient_id"], code3)
    assert r.status_code == 400 and "already been used" in r.text


def test_pending_then_member_and_revoked_states(circle_with_invite, conn, ctx, world):
    owner, p, code, jo = circle_with_invite
    join(jo, p["patient_id"], code)
    _, c2 = circle.create_invitation(conn, ctx, owner, p, role="patient")
    again = join(jo, p["patient_id"], c2)
    assert again.status_code == 200 and "waiting for approval" in again.text.lower() and f'href="/p/{p["patient_id"]}"' in again.text
    jou = conn.execute("SELECT * FROM users WHERE email = 'jo@example.test'").fetchone()
    m = P.get_membership(conn, jou["id"], p["id"])
    circle.approve_member(conn, ctx, owner, p, m["id"])
    assert "already a member" in join(jo, p["patient_id"], c2).text
    circle.revoke_member(conn, ctx, owner, p, m["id"])
    r = join(jo, p["patient_id"], c2)
    assert r.status_code == 403 and "do not have permission" in r.text and "removed" in r.text
    assert "Access removed" in jo.get(f"/p/{p['patient_id']}").text


def test_join_field_validation(circle_with_invite):
    jo = circle_with_invite[3]
    r = join(jo, "", "", label="")
    assert r.status_code == 422
    for m in ("Enter the patient ID.", "Enter the invitation code.", "Choose how you are related"):
        assert m in r.text
    assert join(jo, "FCC-AAAA-AAAA", "AAAA-AAAA-AAAA-AAAA", label="Overlord").status_code == 422


def test_join_attempts_are_throttled(circle_with_invite):
    jo = circle_with_invite[3]
    codes = [join(jo, "FCC-AAAA-AAAA", "AAAA-AAAA-AAAA-AAAA") for _ in range(5)]
    assert all(r.status_code == 400 for r in codes)
    r = join(jo, circle_with_invite[1]["patient_id"], circle_with_invite[2])
    assert r.status_code == 429 and "Too many attempts" in r.text


def test_join_has_no_role_field_and_ignores_a_forged_one(circle_with_invite, conn):
    owner, p, code, jo = circle_with_invite
    assert 'name="role"' not in jo.get("/join").text
    token = csrf_from(jo.get("/join").text)
    jo.post("/join", {"patient_id": p["patient_id"], "code": code, "relationship_label": "Son", "role": "creator",
                      "can_add_notes": "1", "status": "active", "csrf_token": token})
    m = conn.execute("SELECT * FROM memberships WHERE role != 'creator' OR status = 'pending'").fetchone()
    assert (m["role"], m["status"], m["can_add_notes"]) == ("caregiver", "pending", 0)


def test_circle_front_door_for_each_kind_of_visitor(circle_with_invite, app, conn, ctx):
    owner, p, code, jo = circle_with_invite
    stranger = Site(app); stranger.signup(name="Sam Stranger", email="sam@example.test")
    known, unknown = stranger.get(f"/p/{p['patient_id']}"), stranger.get("/p/FCC-AAAA-AAAA")
    assert known.status_code == unknown.status_code == 404
    strip = lambda t: re.sub(r'value="[0-9a-f]{64}"', "", t)
    assert strip(known.text) == strip(unknown.text)                           # a real ID changes nothing for a non-member
    assert "Hidden Patient Name" not in known.text


def test_the_patient_id_in_a_url_never_works_for_a_non_member(circle_with_invite, app):
    owner, p, code, jo = circle_with_invite
    stranger = Site(app); stranger.signup(name="Sam Stranger", email="sam@example.test")
    for suffix in ("", "/created", "/circle", "/summaries", "/notes", "/info"):
        r = stranger.get(f"/p/{p['patient_id']}{suffix}")
        assert r.status_code == 404 and "Hidden Patient Name" not in r.text, suffix
