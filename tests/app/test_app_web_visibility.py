"""What each role actually receives over HTTP. Enforcement is on the server: forbidden fields are ABSENT from the
response body (these tests inspect the raw JSON text, not a rendered page)."""

from __future__ import annotations

import json

import pytest

from app import notes
from fcc_testlib import CLEAN_CHILD, make_record

SECRETS_FOR_CHILD_AND_PATIENT = ["ZEBRA-SOURCE-TOKEN", "Note 1", "Clinic visit"]
DISCLAIMER = "Research prototype. Not medical advice. Check doses and instructions with the care team."


@pytest.fixture
def circle_world(conn, ctx, runner, world, browser):
    """Owner + caregiver + patient + child (all active), pending + revoked members, a stranger, one finished note."""
    owner = world.user("Olivia Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara Carer", can_add_notes=True)
    pt, _ = world.member(p, owner, "patient", "Pat Patient")
    ch, _ = world.member(p, owner, "child", "Kid Kidson")
    pending, _ = world.member(p, owner, "caregiver", "Wendy Waiting", active=False)
    revoked, rm = world.member(p, owner, "caregiver", "Rex Revoked")
    from app import circle
    circle.revoke_member(conn, ctx, owner, p, rm["id"])
    stranger = world.user("Sam Stranger")
    n = notes.add_note(conn, ctx, runner, owner, p, title="Clinic visit", text="ZEBRA-SOURCE-TOKEN visit note. Amoxicillin 500 mg BID x 10 days.")
    runner.drain()

    class W:
        pass
    w = W()
    w.p, w.pid, w.note_id = p, p["patient_id"], n["id"]
    w.users = dict(owner=owner, caregiver=cg, patient=pt, child=ch, pending=pending, revoked=revoked, stranger=stranger)
    w.b = {k: browser(u) for k, u in w.users.items()}
    return w


def body(resp) -> str:
    return resp.text


def test_patient_receives_only_the_patient_summary(circle_world):
    r = circle_world.b["patient"].get(f"/api/p/{circle_world.pid}/outputs")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"available", "output_id", "updated_at", "disclaimer", "patient_summary", "generation"}
    assert data["disclaimer"] == DISCLAIMER and data["patient_summary"].startswith("You have strep throat")
    assert set(data["generation"]) == {"state", "created_at", "finished_at"}            # state only: no title, no message
    for leak in SECRETS_FOR_CHILD_AND_PATIENT + ["caregiver_checklist", "child_explanation", "flags", "retention", "model_id", "note"]:
        assert leak not in body(r), leak


def test_child_receives_only_the_child_explanation_and_no_clinical_detail(circle_world):
    r = circle_world.b["child"].get(f"/api/p/{circle_world.pid}/outputs")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"available", "output_id", "updated_at", "disclaimer", "child_explanation", "generation"}
    assert data["child_explanation"] == CLEAN_CHILD and data["disclaimer"] == DISCLAIMER
    text = body(r).replace(DISCLAIMER, "")          # the mandated disclaimer itself says "doses": not a dose value
    for leak in SECRETS_FOR_CHILD_AND_PATIENT + ["Amoxicillin", "Ibuprofen", "500", "mg", "10 days", "patient_summary",
                                                 "caregiver_checklist", "flags", "retention", "entities", "dose", "model_id", "note"]:
        assert leak not in text, leak
    assert not any(ch.isdigit() for ch in data["child_explanation"])


@pytest.mark.parametrize("who", ["caregiver", "owner"])
def test_adults_receive_all_three_outputs_flags_and_the_note_title(circle_world, who):
    data = circle_world.b[who].get(f"/api/p/{circle_world.pid}/outputs").json()
    assert {"patient_summary", "caregiver_checklist", "child_explanation", "flags", "note", "child_withheld",
            "checklist_progress", "generation", "disclaimer"} <= set(data)
    assert data["note"] == {"id": circle_world.note_id, "title": "Clinic visit"}
    assert [i["text"] for i in data["caregiver_checklist"]][0].startswith("Give Amoxicillin")
    assert data["checklist_progress"] == {"done": 0, "total": 3} and data["flags"]["child_gate"]["fired"] is False
    assert "ZEBRA-SOURCE-TOKEN" not in json.dumps(data)                # outputs never carry the source text itself


@pytest.mark.parametrize("who,endpoint", [
    ("patient", "history"), ("child", "history"), ("patient", "notes"), ("child", "notes"),
    ("patient", "notes/{n}/source"), ("child", "notes/{n}/source"), ("patient", "notes/{n}/outputs"), ("child", "notes/{n}/outputs"),
])
def test_patient_and_child_cannot_reach_adult_endpoints(circle_world, who, endpoint):
    r = circle_world.b[who].get(f"/api/p/{circle_world.pid}/" + endpoint.format(n=circle_world.note_id))
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_allowed"
    assert "ZEBRA" not in r.text and "Amoxicillin" not in r.text


@pytest.mark.parametrize("who", ["caregiver", "owner"])
def test_adults_can_read_source_notes_history_and_note_list(circle_world, who):
    b, pid, n = circle_world.b[who], circle_world.pid, circle_world.note_id
    assert "ZEBRA-SOURCE-TOKEN" in b.get(f"/api/p/{pid}/notes/{n}/source").json()["text"]
    assert [h["title"] for h in b.get(f"/api/p/{pid}/history").json()] == ["Clinic visit"]
    listing = b.get(f"/api/p/{pid}/notes").json()
    assert listing[0]["title"] == "Clinic visit" and "text" not in listing[0]
    assert b.get(f"/api/p/{pid}/notes/{n}/outputs").json()["patient_summary"]


def test_member_list_is_filtered_per_role_over_http(circle_world):
    pid = circle_world.pid
    child = circle_world.b["child"].get(f"/api/p/{pid}/circle")
    assert child.json() == [{"first_name": "Olivia"}, {"first_name": "Cara"}, {"first_name": "Pat"}, {"first_name": "Kid"}]
    for leak in ("Owner", "Carer", "Patient", "Kidson", "@", "email", "role", "Waiting", "Revoked"):
        assert leak not in child.text
    patient = circle_world.b["patient"].get(f"/api/p/{pid}/circle")
    assert "@" not in patient.text and "Waiting" not in patient.text and "Revoked" not in patient.text
    caregiver = circle_world.b["caregiver"].get(f"/api/p/{pid}/circle")
    assert "@" not in caregiver.text and "Waiting" not in caregiver.text           # a pending *caregiver* is not theirs to see
    owner = circle_world.b["owner"].get(f"/api/p/{pid}/circle")
    assert "@" in owner.text and "Waiting" in owner.text and "Revoked" in owner.text


# --- access without an active membership -----------------------------------------------------------------
ENDPOINTS = ["outputs", "status", "history", "notes", "circle", "notes/{n}/source", "notes/{n}/outputs"]


def test_unauthenticated_requests_get_401(circle_world, browser):
    anon = browser(circle_world.users["owner"], login=False)
    for ep in ENDPOINTS:
        r = anon.get(f"/api/p/{circle_world.pid}/" + ep.format(n=circle_world.note_id))
        assert r.status_code == 401, ep
        assert "ZEBRA" not in r.text


def test_the_patient_id_alone_grants_nothing_and_unknown_ids_look_identical(circle_world):
    stranger = circle_world.b["stranger"]
    known = stranger.get(f"/api/p/{circle_world.pid}/outputs")
    unknown = stranger.get("/api/p/FCC-AAAA-AAAA/outputs")
    garbage = stranger.get("/api/p/not-an-id/outputs")
    assert known.status_code == unknown.status_code == garbage.status_code == 404
    assert known.json() == unknown.json() == garbage.json()                    # cannot tell a real circle from a fake ID
    for ep in ENDPOINTS:
        assert stranger.get(f"/api/p/{circle_world.pid}/" + ep.format(n=circle_world.note_id)).status_code == 404, ep


def test_pending_members_get_nothing_but_a_pending_status(circle_world):
    for ep in ENDPOINTS:
        r = circle_world.b["pending"].get(f"/api/p/{circle_world.pid}/" + ep.format(n=circle_world.note_id))
        assert r.status_code == 403 and r.json()["error"]["code"] == "membership_pending", ep
        assert "ZEBRA" not in r.text and "Amoxicillin" not in r.text and "patient_summary" not in r.text


def test_revoked_members_get_nothing_but_an_access_removed_status(circle_world):
    for ep in ENDPOINTS:
        r = circle_world.b["revoked"].get(f"/api/p/{circle_world.pid}/" + ep.format(n=circle_world.note_id))
        assert r.status_code == 403 and r.json()["error"]["code"] == "membership_revoked", ep
        assert "ZEBRA" not in r.text and "Amoxicillin" not in r.text


def test_membership_in_another_circle_gives_no_access_here(conn, ctx, runner, world, browser, circle_world):
    other_owner = world.user("Other Owner"); other = world.profile(other_owner, "Someone Else")
    r = browser(other_owner).get(f"/api/p/{circle_world.pid}/outputs")
    assert r.status_code == 404


def test_a_note_id_from_another_circle_is_not_reachable(conn, ctx, runner, world, browser, circle_world):
    other_owner = world.user("Other Owner"); other = world.profile(other_owner, "Someone Else")
    foreign = notes.add_note(conn, ctx, runner, other_owner, other, title="Foreign", text="FOREIGN-TOKEN note")
    runner.drain()
    b = circle_world.b["owner"]
    for ep in ("notes/{n}/source", "notes/{n}/outputs"):
        r = b.get(f"/api/p/{circle_world.pid}/" + ep.format(n=foreign["id"]))
        assert r.status_code == 404 and "FOREIGN" not in r.text


# --- refresh and history -----------------------------------------------------------------------------------
def test_a_newer_note_replaces_the_latest_view_and_keeps_history_for_adults(conn, ctx, runner, pipeline, circle_world):
    pipeline.record_factory = lambda text: make_record(patient="Second summary only.", child=CLEAN_CHILD)
    owner = circle_world.users["owner"]
    notes.add_note(conn, ctx, runner, owner, circle_world.p, title="Follow-up", text="ZEBRA-SOURCE-TOKEN second")
    runner.drain()
    for who in ("patient", "caregiver"):
        assert circle_world.b[who].get(f"/api/p/{circle_world.pid}/outputs").json()["patient_summary"] == "Second summary only."
    adult = circle_world.b["caregiver"].get(f"/api/p/{circle_world.pid}/outputs").json()
    assert adult["note"]["title"] == "Follow-up"
    assert [h["title"] for h in circle_world.b["owner"].get(f"/api/p/{circle_world.pid}/history").json()] == ["Follow-up", "Clinic visit"]
    older = circle_world.b["caregiver"].get(f"/api/p/{circle_world.pid}/notes/{circle_world.note_id}/outputs").json()
    assert older["patient_summary"].startswith("You have strep throat")


def test_previous_output_stays_visible_while_a_newer_note_is_being_prepared(conn, ctx, runner, circle_world):
    notes.add_note(conn, ctx, runner, circle_world.users["owner"], circle_world.p, title="Next", text="more text")       # queued, not run
    for who in ("owner", "patient", "child"):
        data = circle_world.b[who].get(f"/api/p/{circle_world.pid}/outputs").json()
        assert data["available"] and data["generation"]["state"] == "queued", who
    patient = circle_world.b["patient"].get(f"/api/p/{circle_world.pid}/status").json()
    assert patient["state"] == "queued" and "note" not in patient
    assert circle_world.b["owner"].get(f"/api/p/{circle_world.pid}/status").json()["note"]["title"] == "Next"


def test_empty_states(conn, ctx, world, browser):
    owner = world.user("Owner"); p = world.profile(owner)
    pt, _ = world.member(p, owner, "patient", "Pat")
    for u in (owner, pt):
        r = browser(u).get(f"/api/p/{p['patient_id']}/outputs").json()
        assert r["available"] is False and r["generation"] == {"state": "none"} and r["disclaimer"] == DISCLAIMER
        assert "patient_summary" not in r and "flags" not in r
    assert browser(owner).get(f"/api/p/{p['patient_id']}/history").json() == []


def test_deleting_the_latest_note_falls_back_to_the_previous_outputs(conn, ctx, runner, pipeline, circle_world):
    pipeline.record_factory = lambda text: make_record(patient="Second summary only.")
    owner = circle_world.users["owner"]
    second = notes.add_note(conn, ctx, runner, owner, circle_world.p, title="Follow-up", text="second")
    runner.drain()
    r = circle_world.b["owner"].post(f"/api/p/{circle_world.pid}/notes/{second['id']}/delete")
    assert r.status_code == 200
    data = circle_world.b["patient"].get(f"/api/p/{circle_world.pid}/outputs").json()
    assert data["patient_summary"].startswith("You have strep throat")


def test_every_output_response_carries_the_disclaimer(circle_world):
    for who in ("patient", "child", "caregiver", "owner"):
        assert circle_world.b[who].get(f"/api/p/{circle_world.pid}/outputs").json()["disclaimer"] == DISCLAIMER
