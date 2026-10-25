"""Dashboard, summaries, checklist, care-circle management, notes and settings: behaviour and states."""

from __future__ import annotations

import re
import threading

import pytest

from app import circle, notes, permissions as P
from conftest import Site
from fcc_testlib import (CLEAN_CHILD, PASSWORD, PATIENT_NAME, SOURCE_MARK, SOURCE_TEXT, TITLE, FakePipeline, assert_clean_page,
                         csrf_from, make_record)

DISCLAIMER = "Research prototype. Not medical advice. Check doses and instructions with the care team."


def token_of(site: Site, pid: str | None = None) -> str:
    return csrf_from(site.get("/settings").text)


def post(site: Site, url: str, data: dict | None = None, **kw):
    return site.post(url, {**(data or {}), "csrf_token": token_of(site)}, **kw)


def banner_text(html: str, kind: str) -> str:
    m = re.search(rf'<div class="banner banner-{kind}".*?</div>\s*</div>', html, re.S)
    return re.sub(r"<[^>]+>|\s+", " ", m.group(0)).strip() if m else ""


# =================================================================================================== dashboard
def test_dashboard_shows_role_limited_cards_and_the_disclaimer_everywhere(full):
    owner = full.site["owner"].get(f"/p/{full.pid}").text
    assert "Patient summary" in owner and "Caregiver checklist" in owner and "Child explanation" in owner
    patient = full.site["patient"].get(f"/p/{full.pid}").text
    assert "Patient summary" in patient and "Caregiver checklist" not in patient and "Child explanation" not in patient
    child = full.site["child"].get(f"/p/{full.pid}").text
    assert "What is happening" in child and "Hi! This is about Grandma" in child and "tiny helpers" in child
    for who in ("owner", "caregiver", "patient", "child"):
        html = full.site[who].get(f"/p/{full.pid}").text
        assert html.count(DISCLAIMER) >= 2                                   # in the output card(s) and in the footer


def test_dashboard_shows_updated_time_and_note_title_to_adults_only(full):
    adult = full.site["caregiver"].get(f"/p/{full.pid}").text
    assert re.search(r"Updated 15 Jan 2026, 12:00 UTC from note “Clinic visit”", adult)
    kid = full.site["child"].get(f"/p/{full.pid}").text
    assert "Updated 15 Jan 2026, 12:00 UTC" in kid and "Clinic visit" not in kid


def test_dashboard_has_circle_snapshot_checklist_progress_and_latest_note(full):
    html = full.site["owner"].get(f"/p/{full.pid}").text
    assert "0 of 3 done" in html and "5 people in this circle" in html and "member-creator" in html
    assert "Latest note" in html and "Ready" in html and "Clinic visit" in html
    kid = full.site["child"].get(f"/p/{full.pid}").text
    assert "People helping:" in kid and "Olivia" in kid and "Owner" not in kid


def test_empty_state_has_an_action_only_for_people_who_can_add_notes(world, app, ctx):
    owner = world.user("Owner"); p = world.profile(owner, "Empty One")
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    pt, _ = world.member(p, owner, "patient", "Pat")
    for user, action in ((owner, True), (cg, False), (pt, False)):
        s = Site(app); s.login(user["email"])
        html = s.get(f"/p/{p['patient_id']}").text
        assert "No note has been added yet" in html
        assert (f'href="/p/{p["patient_id"]}/notes"' in html.split("<main")[1]) == action
        assert_clean_page(html)


def test_a_note_in_progress_shows_a_polling_skeleton_and_keeps_old_outputs(full, conn, ctx, runner):
    notes.add_note(conn, ctx, runner, full.users["owner"], full.p, title="Next", text="more")        # queued
    html = full.site["patient"].get(f"/p/{full.pid}").text
    assert f'data-poll-url="/api/p/{full.pid}/status"' in html and 'data-poll-state="queued"' in html
    assert 'class="skeleton"' in html and "A new note is being prepared" in html and "Refresh now" in html
    assert "strep throat" in html                                          # the previous summary stays visible
    assert "Next" not in html                                              # the patient is not told the note's title
    assert "Next" in full.site["owner"].get(f"/p/{full.pid}").text


def test_failed_generation_is_explained_to_adults_and_generic_for_others(world, app, ctx, conn, runner, pipeline):
    pipeline.fail_with = RuntimeError("secret detail")
    owner = world.user("Owner"); p = world.profile(owner, "Failing One")
    ch, _ = world.member(p, owner, "child", "Kid")
    notes.add_note(conn, ctx, runner, owner, p, title="Bad", text="text"); runner.drain()
    o = Site(app); o.login(owner["email"]); k = Site(app); k.login(ch["email"])
    adult = banner_text(o.get(f"/p/{p['patient_id']}").text, "error")
    assert "could not be prepared" in adult and "Please try adding it again" in adult and "secret detail" not in adult
    child = k.get(f"/p/{p['patient_id']}").text
    assert "Please ask the person who manages the care circle" in child and "Bad" not in child and "Please try adding it again" not in child


# ================================================================================================== summaries
def test_tabs_are_limited_to_the_versions_a_role_may_see(full):
    owner = full.site["owner"].get(f"/p/{full.pid}/summaries").text
    assert 'aria-label="Choose a version"' in owner
    for label in ("Patient", "Caregiver", "Child"):
        assert re.search(rf'<a href="[^"]*tab={label.lower()}[^"]*"[^>]*>.*?{label}', owner, re.S)
    assert owner.count('aria-current="page"') >= 2                            # nav item and the active tab
    for who in ("patient", "child"):
        assert 'aria-label="Choose a version"' not in full.site[who].get(f"/p/{full.pid}/summaries").text


def test_each_tab_shows_its_own_output_with_disclaimer_and_provenance(full):
    s = full.site["caregiver"]
    p = s.get(f"/p/{full.pid}/summaries?tab=patient").text
    assert "You have strep throat" in p and "tiny helpers" not in p and DISCLAIMER in p.split("<footer")[0]
    assert "from note “Clinic visit”" in p
    c = s.get(f"/p/{full.pid}/summaries?tab=caregiver").text
    assert "Give Amoxicillin 500 mg twice a day" in c and "0 of 3 done" in c
    k = s.get(f"/p/{full.pid}/summaries?tab=child").text
    assert "tiny helpers" in k and "persona-child" in k
    assert "You have strep throat" in s.get(f"/p/{full.pid}/summaries?tab=nonsense").text          # unknown tab -> first tab


def test_flags_source_and_history_are_for_adults_only(full, conn, ctx, runner, pipeline):
    pipeline.record_factory = lambda text: make_record(patient="Second summary.")
    notes.add_note(conn, ctx, runner, full.users["owner"], full.p, title="Follow-up", text=SOURCE_MARK + " second"); runner.drain()
    adult = full.site["caregiver"].get(f"/p/{full.pid}/summaries?tab=patient").text
    assert "Review flags" in adult and "Source note: Follow-up" in adult and SOURCE_MARK in adult
    assert "Earlier notes" in adult and "Clinic visit" in adult
    older = full.site["caregiver"].get(f"/p/{full.pid}/summaries?tab=patient&note=1").text
    assert "You are looking at an earlier note" in older and "You have strep throat" in older and "Second summary." not in older.split("persona-body")[1].split("</section>")[0]
    for who in ("patient", "child"):
        html = full.site[who].get(f"/p/{full.pid}/summaries").text
        assert "Review flags" not in html and "Source note" not in html and "Earlier notes" not in html and SOURCE_MARK not in html


def test_review_flags_explain_what_to_check(world, app, ctx, conn, runner, pipeline):
    rec = make_record(child="You will take it for 3 days. Rest well.")
    rec["metadata"]["fallback_used"]["patient_summary"] = True
    rec["metadata"]["missing_after_retries"]["patient_summary"] = ["10 days"]
    rec["metadata"]["truncated"]["caregiver_checklist"] = True
    rec["metadata"]["redacted_dosages"]["patient_summary"] = ["900 mg"]
    pipeline.record_factory = lambda text: rec
    owner = world.user("Owner"); p = world.profile(owner, "Flagged One")
    notes.add_note(conn, ctx, runner, owner, p, title="Flagged", text=SOURCE_TEXT); runner.drain()
    s = Site(app); s.login(owner["email"])
    html = s.get(f"/p/{p['patient_id']}/summaries?tab=child").text
    assert "to check)" in html and "added automatically" in html and "10 days" in html and "cut off" in html
    assert "900 mg" in html and "withheld by the safety check" in html and "it contained a number" in html
    assert "The safety check held back the generated child explanation" in html
    assert "A grown-up will help explain what the doctor said." in html and "3 days" not in html.split("Review flags")[0]


def test_hostile_text_is_escaped_in_titles_names_notes_and_labels(world, app, ctx, conn, runner, pipeline):
    evil = "<script>alert(1)</script><img src=x onerror=alert(2)>{{ 7*7 }}{% raw %}\"'&"
    pipeline.record_factory = lambda text: make_record(patient=evil, child=CLEAN_CHILD, checklist=[evil, "ok"])
    owner = world.user(evil[:60], email="evil@example.test"); p = world.profile(owner, evil[:80], preferred_name=evil[:40], care_notes=evil)
    notes.add_note(conn, ctx, runner, owner, p, title=evil[:80], text=evil); runner.drain()
    s = Site(app); s.login("evil@example.test")
    for url in ("", "/summaries?tab=patient", "/summaries?tab=caregiver", "/info", "/circle", "/notes"):
        html = s.get(f"/p/{p['patient_id']}{url}").text
        assert "<script>alert" not in html and "<img src=x" not in html, url
        assert_clean_page(html)
    assert "&lt;script&gt;" in s.get(f"/p/{p['patient_id']}/info").text
    assert "{{ 7*7 }}" in s.get(f"/p/{p['patient_id']}/info").text                       # template syntax stays literal text
    assert "49" not in re.sub(r"\d{2,}", "", s.get(f"/p/{p['patient_id']}/info").text.split("<main")[1].split("Patient ID")[0])


# =================================================================================================== checklist
def tick_url(full, i, note=1):
    return f"/p/{full.pid}/checklist/{note}/{i}"


def test_adults_tick_and_untick_with_who_and_when(full):
    cg = full.site["caregiver"]
    r = post(cg, tick_url(full, 1), {"ticked": "1", "back": f"/p/{full.pid}/summaries?tab=caregiver"})
    assert r.status_code == 303 and r.headers["location"] == f"/p/{full.pid}/summaries?tab=caregiver#item-1"
    html = full.site["owner"].get(f"/p/{full.pid}/summaries?tab=caregiver").text
    assert "1 of 3 done" in html and "Done by Cara Carer, 15 Jan 2026, 12:00 UTC" in html and "Mark not done" in html
    post(full.site["owner"], tick_url(full, 1), {"ticked": "0"})
    assert "0 of 3 done" in full.site["owner"].get(f"/p/{full.pid}/summaries?tab=caregiver").text


def test_each_checklist_item_is_an_accessible_form_that_works_without_javascript(full):
    html = full.site["owner"].get(f"/p/{full.pid}/summaries?tab=caregiver").text
    assert html.count("Mark done") == 3 and html.count(f'action="/p/{full.pid}/checklist/1/') == 3
    assert 'class="visually-hidden">: Give Amoxicillin' in html                     # the button's accessible name names the item


@pytest.mark.parametrize("who,status", [("patient", 403), ("child", 403), ("pending", 200), ("stranger", 404)])
def test_others_cannot_tick(full, conn, who, status):
    r = full.site[who].post(tick_url(full, 0), {"ticked": "1", "csrf_token": token_of(full.site[who])})
    assert r.status_code == status                       # pending members only get their status page (200), nothing is saved
    assert conn.execute("SELECT COUNT(*) FROM checklist_ticks").fetchone()[0] == 0


def test_tick_redirect_cannot_be_hijacked(full):
    r = post(full.site["owner"], tick_url(full, 0), {"back": "https://evil.example/x"})
    assert r.headers["location"].startswith(f"/p/{full.pid}/summaries")
    r = post(full.site["owner"], tick_url(full, 0), {"back": f"/p/{full.pid}/summaries//evil.example"})
    assert r.headers["location"].startswith(f"/p/{full.pid}/summaries?tab=caregiver")


def test_tick_requires_csrf(full):
    assert full.site["owner"].post(tick_url(full, 0), {"ticked": "1"}).status_code == 403
    assert "0 of 3 done" in full.site["owner"].get(f"/p/{full.pid}/summaries?tab=caregiver").text


def test_empty_checklist_state(world, app, ctx, conn, runner, pipeline):
    pipeline.record_factory = lambda text: {**make_record(), "caregiver_checklist": []}
    owner = world.user("Owner"); p = world.profile(owner, "Empty List")
    notes.add_note(conn, ctx, runner, owner, p, title="x", text="t"); runner.drain()
    s = Site(app); s.login(owner["email"])
    assert conn.execute("SELECT COUNT(*) FROM outputs WHERE profile_id = ?", (p["id"],)).fetchone()[0] == 1
    html = s.get(f"/p/{p['patient_id']}/summaries?tab=caregiver").text
    assert "This checklist has no items" in html and "Mark done" not in html


# ============================================================================================ circle management
def circle_url(full, suffix=""):
    return f"/p/{full.pid}/circle{suffix}"


def mid(conn, user, full):
    return conn.execute("SELECT id FROM memberships WHERE user_id = ? AND profile_id = ?", (user["id"], full.p["id"])).fetchone()[0]


def test_creator_is_visually_distinct_and_sees_management_controls(full):
    html = full.site["owner"].get(circle_url(full)).text
    assert 'class="member member-creator"' in html and "Creator of this care circle" in html
    for text in ("Invite someone", "Invitations", "Delete this care circle", "Approve", "Decline", "Remove access", "Change role",
                 "Allow adding notes", "Stop allowing notes", "olivia@example.test"):
        assert text in html, text
    assert html.count("member-creator") >= 1 and "Remove access" in html


def test_caregiver_can_only_approve_pending_children(full):
    html = full.site["caregiver"].get(circle_url(full)).text
    assert "Approve this child" in html and html.count("Approve this child") == 1 and "Pip" in html
    for absent in ("Invite someone", "Delete this care circle", "Decline", "Remove access", "Change role", "@example.test", "Wendy"):
        assert absent not in html, absent


def test_patient_and_child_circle_pages_are_read_only(full):
    for who in ("patient", "child"):
        html = full.site[who].get(circle_url(full)).text
        for absent in ("Approve", "Invite someone", "Delete", "Remove access", "Change role", "<form method=\"post\" action=\"/p/"):
            assert absent not in html.split("</header>")[1].split("<footer")[0] or absent == "<form method=\"post\" action=\"/p/", (who, absent)
        assert "action=\"/p/" not in html.split("</header>")[1].split("<footer")[0]


def test_inviting_shows_the_code_once_and_only_in_that_response(full, conn, app):
    s = full.site["owner"]
    r = post(s, circle_url(full, "/invite"), {"role": "patient", "note": "for Pat"})
    assert r.status_code == 200 and "shown only once" in r.text
    code = re.search(r'id="invite-code">([A-Z0-9-]{19})<', r.text).group(1)
    assert "Nothing is emailed" in r.text and 'data-copy-target="invite-code"' in r.text and full.pid in r.text
    assert code not in s.get(circle_url(full)).text                                  # gone on the next visit
    assert code not in str([dict(r) for r in conn.execute("SELECT * FROM invitations")])   # and never stored in clear
    joiner = Site(app); joiner.signup(name="New Person", email="newperson@example.test")
    jr = joiner.post("/join", {"patient_id": full.pid, "code": code, "relationship_label": "Friend or paid carer",
                               "csrf_token": csrf_from(joiner.get("/join").text)})
    assert jr.status_code == 303
    html = s.get(circle_url(full)).text
    assert "New Person" in html and "Pending approval" in html and "Used" in html and "for Pat" in html
    mid_ = conn.execute("SELECT id FROM memberships WHERE role = 'patient' AND status = 'pending'").fetchone()[0]
    assert post(s, circle_url(full, f"/members/{mid_}/approve")).status_code == 200
    assert joiner.get(f"/p/{full.pid}").status_code == 200 and "Peggy" in joiner.get(f"/p/{full.pid}").text


def test_invite_validation_and_revoke_invitation(full, conn):
    s = full.site["owner"]
    bad = post(s, circle_url(full, "/invite"), {"role": "creator"})
    assert bad.status_code == 422 and "Choose caregiver, patient or child" in bad.text
    post(s, circle_url(full, "/invite"), {"role": "child"})
    inv_id = conn.execute("SELECT id FROM invitations WHERE revoked_at IS NULL AND used_at IS NULL").fetchone()[0]
    r = post(s, circle_url(full, f"/invitations/{inv_id}/revoke"))
    assert r.status_code == 200 and "Invitation cancelled" in r.text and "Cancelled" in r.text
    assert post(s, circle_url(full, f"/invitations/{inv_id}/revoke")).status_code == 404


def test_approve_decline_role_notes_and_remove(full, conn):
    s, p = full.site["owner"], full.users
    pend = mid(conn, p["pending"], full)
    assert "Request approved" in post(s, circle_url(full, f"/members/{pend}/approve")).text
    assert P.get_membership(conn, p["pending"]["id"], full.p["id"])["status"] == "active"
    r = post(s, circle_url(full, f"/members/{pend}/role"), {"role": "patient"})
    assert "Role changed" in r.text and P.get_membership(conn, p["pending"]["id"], full.p["id"])["role"] == "patient"
    cg2 = mid(conn, p["caregiver_no_notes"], full)
    assert "Permission updated" in post(s, circle_url(full, f"/members/{cg2}/notes"), {"allowed": "1"}).text
    assert P.get_membership(conn, p["caregiver_no_notes"]["id"], full.p["id"])["can_add_notes"] == 1
    assert Site.get(full.site["caregiver_no_notes"], f"/p/{full.pid}/notes").status_code == 200       # now allowed
    post(s, circle_url(full, f"/members/{cg2}/notes"), {"allowed": "0"})
    assert full.site["caregiver_no_notes"].get(f"/p/{full.pid}/notes").status_code == 403
    pc = mid(conn, p["pending_child"], full)
    assert "Access removed" in post(s, circle_url(full, f"/members/{pc}/revoke")).text
    assert P.get_membership(conn, p["pending_child"]["id"], full.p["id"])["status"] == "revoked"
    assert "Access removed" in full.site["pending_child"].get(f"/p/{full.pid}").text


def test_a_removed_member_loses_access_immediately(full, conn):
    s = full.site["owner"]
    m = mid(conn, full.users["patient"], full)
    assert full.site["patient"].get(f"/p/{full.pid}/summaries").status_code == 200
    post(s, circle_url(full, f"/members/{m}/revoke"))
    r = full.site["patient"].get(f"/p/{full.pid}/summaries")
    assert r.status_code == 200 and "Access removed" in r.text and "strep throat" not in r.text
    assert full.site["patient"].get(f"/api/p/{full.pid}/outputs").status_code == 403


def test_caregiver_approves_a_child_but_not_other_roles_through_the_page(full, conn):
    cg = full.site["caregiver"]
    child_m = mid(conn, full.users["pending_child"], full)
    caregiver_m = mid(conn, full.users["pending"], full)
    assert "Request approved" in post(cg, circle_url(full, f"/members/{child_m}/approve")).text
    r = post(cg, circle_url(full, f"/members/{caregiver_m}/approve"))
    assert r.status_code == 403 and P.get_membership(conn, full.users["pending"]["id"], full.p["id"])["status"] == "pending"


@pytest.mark.parametrize("action", ["approve", "revoke", "role", "notes"])
@pytest.mark.parametrize("who", ["caregiver", "patient", "child"])
def test_non_creators_cannot_manage_members_even_by_forging_requests(full, conn, who, action):
    target = mid(conn, full.users["caregiver_no_notes"], full)
    before = dict(P.get_membership(conn, full.users["caregiver_no_notes"]["id"], full.p["id"]))
    r = post(full.site[who], circle_url(full, f"/members/{target}/{action}"), {"role": "child", "allowed": "1"})
    assert r.status_code in (403, 404)
    assert dict(P.get_membership(conn, full.users["caregiver_no_notes"]["id"], full.p["id"])) == before


def test_non_creators_cannot_invite_or_delete(full, conn):
    invitations_before = conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0]
    for who in ("caregiver", "patient", "child"):
        assert post(full.site[who], circle_url(full, "/invite"), {"role": "caregiver"}).status_code == 403
        assert post(full.site[who], f"/p/{full.pid}/delete", {"confirm": full.pid}).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0] == invitations_before
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1


def test_management_posts_require_csrf(full, conn):
    s = full.site["owner"]
    target = mid(conn, full.users["pending"], full)
    for url in (circle_url(full, f"/members/{target}/approve"), circle_url(full, "/invite"), f"/p/{full.pid}/delete"):
        assert s.post(url, {"role": "child", "confirm": full.pid}).status_code == 403
    assert P.get_membership(conn, full.users["pending"]["id"], full.p["id"])["status"] == "pending"


def test_cannot_manage_members_of_another_circle(full, world, conn, ctx, app):
    other_owner = world.user("Other Owner", email="other@example.test"); other = world.profile(other_owner, "Other One")
    ou, om = world.member(other, other_owner, "caregiver", "Other Cg")
    r = post(full.site["owner"], circle_url(full, f"/members/{om['id']}/revoke"))
    assert r.status_code == 404 and P.get_membership(conn, ou["id"], other["id"])["status"] == "active"


def test_deleting_a_care_circle_needs_the_exact_id_and_removes_everything(full, conn):
    s = full.site["owner"]
    wrong = post(s, f"/p/{full.pid}/delete", {"confirm": "no"})
    assert wrong.status_code == 422 and "Type the patient ID exactly" in wrong.text
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1
    ok = post(s, f"/p/{full.pid}/delete", {"confirm": full.pid.lower()})
    assert ok.status_code == 303 and ok.headers["location"] == "/profiles"
    for table in ("profiles", "memberships", "notes", "outputs", "invitations", "checklist_ticks"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert full.site["child"].get(f"/p/{full.pid}").status_code == 404


# ======================================================================================================== notes
def test_notes_page_lists_notes_and_validates(full):
    s = full.site["caregiver"]
    html = s.get(f"/p/{full.pid}/notes").text
    assert "Add a note" in html and "Clinic visit" in html and "Ready" in html and "Added by Olivia Owner" in html
    assert 'enctype="multipart/form-data"' in html and 'accept=".txt,text/plain"' in html and "6,000" in html
    assert "Delete" not in html                                                    # only the creator deletes
    r = post(s, f"/p/{full.pid}/notes", {"title": "t", "text": ""})
    assert r.status_code == 422 and "Please paste the note text" in r.text and 'value="t"' in r.text
    r = post(s, f"/p/{full.pid}/notes", {"text": "x" * 20_001})
    assert r.status_code == 422 and "20,001" in r.text


def test_adding_a_note_redirects_queues_it_and_shows_progress(full, conn, runner, pipeline):
    s = full.site["caregiver"]
    r = post(s, f"/p/{full.pid}/notes", {"title": "Second", "text": "Some note text."})
    assert r.status_code == 303 and r.headers["location"].endswith("/notes?added=1")
    page = s.get(r.headers["location"]).text
    assert "Note added" in page and 'data-poll-state="queued"' in page and "Second" in page and "Waiting in line" in page
    assert conn.execute("SELECT added_by FROM notes WHERE title = 'Second'").fetchone()[0] == full.users["caregiver"]["id"]
    runner.drain()
    assert "Ready" in s.get(f"/p/{full.pid}/notes").text and 'data-poll-url' not in s.get(f"/p/{full.pid}/notes").text


def test_txt_upload_through_the_page(full, conn):
    s = full.site["owner"]
    r = s.post(f"/p/{full.pid}/notes", {"csrf_token": token_of(s)}, files={"file": ("visit.txt", b"Uploaded note text.", "text/plain")})
    assert r.status_code == 303
    assert conn.execute("SELECT title, text FROM notes WHERE title = 'visit'").fetchone()[:] == ("visit", "Uploaded note text.")
    bad = s.post(f"/p/{full.pid}/notes", {"csrf_token": token_of(s)}, files={"file": ("scan.pdf", b"%PDF", "application/pdf")})
    assert bad.status_code == 422 and "not a .txt file" in bad.text


def test_only_permitted_people_can_post_notes_and_only_the_creator_deletes(full, conn):
    for who in ("caregiver_no_notes", "patient", "child"):
        assert post(full.site[who], f"/p/{full.pid}/notes", {"text": "sneaky"}).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM notes WHERE text = 'sneaky'").fetchone()[0] == 0
    assert post(full.site["caregiver"], f"/p/{full.pid}/notes/1/delete").status_code == 403
    html = full.site["owner"].get(f"/p/{full.pid}/notes").text
    assert "Delete" in html and "and its explanations" in html
    r = post(full.site["owner"], f"/p/{full.pid}/notes/1/delete")
    assert r.status_code == 303
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0
    assert "No note has been added yet" in full.site["owner"].get(f"/p/{full.pid}").text


def test_note_posts_require_csrf(full, conn):
    assert full.site["owner"].post(f"/p/{full.pid}/notes", {"text": "x"}).status_code == 403
    assert full.site["owner"].post(f"/p/{full.pid}/notes/1/delete", {}).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


# ====================================================================================================== settings
def test_change_password_logs_out_other_devices_but_not_this_one(world, app):
    u = world.user("Pw Person", email="pw@example.test")
    a, b = Site(app), Site(app)
    a.login("pw@example.test"); b.login("pw@example.test")
    old_cookie = a.client.cookies.get("fcc_session")
    r = post(a, "/settings/password", {"current_password": PASSWORD, "new_password": "a brand new passphrase"})
    assert r.status_code == 303 and "Password changed" in a.get("/settings?password_changed=1").text      # F-09: PRG, fresh cookie
    assert a.client.cookies.get("fcc_session") != old_cookie                            # F-09: token rotated
    assert a.get("/settings").status_code == 200 and b.get("/settings").status_code == 303
    assert Site(app).login("pw@example.test", "a brand new passphrase").status_code == 303
    assert Site(app).login("pw@example.test", PASSWORD).status_code == 401


def test_change_password_errors(world, app):
    world.user("Pw Person", email="pw@example.test")
    a = Site(app); a.login("pw@example.test")
    r = post(a, "/settings/password", {"current_password": "not my password", "new_password": "a brand new passphrase"})
    assert r.status_code == 401 and "current password is not correct" in r.text.lower()
    r = post(a, "/settings/password", {"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422 and "at least 12" in r.text
    assert PASSWORD not in r.text and "a brand new passphrase" not in r.text            # passwords are never echoed back
    assert 'type="password"' in r.text and 'value="' not in r.text.split('id="f-current_password"')[1].split(">")[0]


def test_log_out_of_all_sessions(world, app):
    world.user("Multi", email="multi@example.test")
    a, b = Site(app), Site(app)
    a.login("multi@example.test"); b.login("multi@example.test")
    r = post(a, "/settings/logout-all")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert a.get("/settings").status_code == 303 and b.get("/settings").status_code == 303


def test_delete_account_flow(world, app, conn):
    world.user("Doomed", email="doomed@example.test")
    s = Site(app); s.login("doomed@example.test")
    r = post(s, "/settings/delete", {"password": PASSWORD})
    assert r.status_code == 422 and "Tick the box" in r.text
    r = post(s, "/settings/delete", {"password": "wrong password", "confirm": "yes"})
    assert r.status_code == 401
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email = 'doomed@example.test'").fetchone()[0] == 1
    r = post(s, "/settings/delete", {"password": PASSWORD, "confirm": "yes"})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email = 'doomed@example.test'").fetchone()[0] == 0
    assert s.get("/settings").status_code == 303


def test_creators_cannot_delete_their_account_while_they_own_a_circle(full, conn):
    r = post(full.site["owner"], "/settings/delete", {"password": PASSWORD, "confirm": "yes"})
    assert r.status_code == 403 and "Delete it first" in r.text
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email = 'olivia@example.test'").fetchone()[0] == 1


def test_settings_posts_require_csrf(world, app):
    world.user("Csrf", email="csrf@example.test")
    s = Site(app); s.login("csrf@example.test")
    for url, data in (("/settings/password", {"current_password": PASSWORD, "new_password": "another passphrase!"}),
                      ("/settings/logout-all", {}), ("/settings/delete", {"password": PASSWORD, "confirm": "yes"})):
        assert s.post(url, data).status_code == 403
    assert s.get("/settings").status_code == 200


def test_pause_new_invitations_from_the_circle_page(full, app, conn):
    """Optional item: the creator pauses invitations in the UI; others have no button and cannot post it."""
    s = full.site["owner"]
    assert "Pause new invitations" in s.get(circle_url(full)).text
    r = post(s, circle_url(full, "/pause"), {"paused": "1"})
    assert r.status_code == 200 and "New invitations are paused" in r.text and "Resume invitations" in r.text
    assert 'action="/p/' + full.pid + '/circle/invite"' not in r.text                       # the create form is gone
    assert conn.execute("SELECT invitations_paused FROM profiles").fetchone()[0] == 1
    r = post(s, circle_url(full, "/pause"), {"paused": "0"})
    assert "Pause new invitations" in r.text and conn.execute("SELECT invitations_paused FROM profiles").fetchone()[0] == 0
    cg = full.site["caregiver"]
    assert "Pause new invitations" not in cg.get(circle_url(full)).text
    assert post(cg, circle_url(full, "/pause"), {"paused": "1"}).status_code == 403
    assert conn.execute("SELECT invitations_paused FROM profiles").fetchone()[0] == 0
