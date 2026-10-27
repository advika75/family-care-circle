"""Synthetic regression coverage for the app's persona-specific output path."""

from __future__ import annotations

import json

import pytest

from app import outputs, safety
from app.clinical_safety import unsupported_claims
from app.config import Settings
from app.pipeline_adapter import build_pipeline


NOTE = (
    "Patient has strep throat. Amoxicillin 500 mg PO BID x 10 days. "
    "Call the care team if the fever returns."
)


def test_app_mock_builds_three_nonempty_distinct_persona_outputs_with_source_details():
    record = build_pipeline(Settings(backend="mock")).run(NOTE, doc_id="synthetic-persona-check")

    assert record["metadata"]["valid"] is True
    patient = record["patient_summary"]
    caregiver = record["caregiver_checklist"]
    child = record["child_explanation"]
    assert patient and caregiver and child
    assert "It can be a lot to take in" in patient
    assert "strep throat" in patient and "Amoxicillin" in patient and "500 mg" in patient
    assert "BID" in patient and "10 days" in patient
    assert all(item.startswith("Follow ") for item in caregiver)
    assert any("Amoxicillin" in item and "500 mg" in item and "BID" in item and "10 days" in item for item in caregiver)
    assert any("Call the care team if the fever returns" in item for item in caregiver)
    assert not any("Schedule and keep all follow-up visits" in item for item in caregiver)
    assert patient.casefold() != " ".join(caregiver).casefold()
    assert child == safety.SAFE_CHILD_MESSAGE and len(child.split()) < 50
    assert not safety.check_child_text(child, safety.medication_names(record["entities"], record["regimens"]))


def test_app_mock_does_not_invent_monitoring_or_followup_when_note_has_none():
    record = build_pipeline(Settings(backend="mock")).run("Patient reports a mild cough.", doc_id="synthetic-no-plan")
    caregiver = record["caregiver_checklist"]
    assert caregiver == ["Review the note's care steps with the care team."]
    assert not any(word in " ".join(caregiver).casefold() for word in ("schedule", "watch for", "dose log"))


def test_safety_gate_and_empty_child_text_use_the_approved_safe_fallback():
    from fcc_testlib import make_record

    for child in ("Your medicine is 5 mg.", ""):
        built = outputs.build_output(make_record(child=child), NOTE)
        assert built["child_withheld"] is True
        assert built["child_explanation"] == safety.SAFE_CHILD_MESSAGE


def test_child_fallback_does_not_add_unsupported_heart_event_or_procedure():
    from fcc_testlib import make_record

    note = "Patient reports a mild cough. No heart attack or heart procedure is described."
    record = make_record(child="You had a heart attack. Doctors put a tiny helper in your heart. "
                                "You should ask the doctor about stopping medicine.")
    built = outputs.build_output(record, note)
    assert built["child_withheld"] is True
    assert built["child_explanation"] == safety.SAFE_CHILD_MESSAGE
    assert not any(term in built["child_explanation"].casefold() for term in ("heart attack", "stent", "procedure"))
    assert "unsupported_clinical_claim" in built["flags"]["child_gate"]["reasons"]
    assert unsupported_claims("The note describes a heart attack.", "No heart attack was found.", persona="patient")


def test_unsupported_serious_claims_replace_patient_and_caregiver_text():
    from fcc_testlib import make_record

    record = make_record(patient="The note says the patient had a heart attack.",
                         checklist=["Call the clinic about the heart attack."])
    built = outputs.build_output(record, "Patient reports a mild cough.")
    assert built["patient_summary"].startswith("Some details in this summary could not be checked")
    assert built["caregiver_checklist"] == [outputs.CAREGIVER_REVIEW_FALLBACK]
    assert built["flags"]["clinical_claim_gate"]["fired"] is True


def test_family_member_diagnosis_is_not_attributed_to_the_patient():
    assert unsupported_claims("The patient had a heart attack.",
                              "Patient reports a cough. Family history: father had a heart attack.",
                              persona="patient") == ["heart_attack"]


def test_malformed_or_non_action_caregiver_output_uses_grounded_review_fallback():
    from fcc_testlib import make_record

    built = outputs.build_output(make_record(checklist=["A duplicate paragraph."]), NOTE)
    assert built["caregiver_checklist"] == [
        "Review the note's listed medicine plan with the care team: Amoxicillin, 500 mg, BID, 10 days.",
        "Review the note's listed medicine plan with the care team: Ibuprofen, 200 mg, q6h.",
    ]
    assert built["flags"]["caregiver_fallback"] is True


def test_caregiver_fallback_uses_only_explicit_source_instructions_or_general_review():
    from fcc_testlib import make_record

    no_plan_record = make_record()
    no_plan_record["caregiver_checklist"] = []
    no_plan_record["regimens"] = []
    no_plan = outputs.build_output(no_plan_record, "Patient reports a mild cough.")
    assert no_plan["caregiver_checklist"] == ["Ask the care team to review the next steps stated in this note."]
    action_note = "Patient reports a mild cough. Call the clinic if symptoms worsen."
    action_record = make_record()
    action_record["caregiver_checklist"] = []
    action_record["regimens"] = []
    action = outputs.build_output(action_record, action_note)
    assert action["caregiver_checklist"] == ["Follow this instruction from the note: Call the clinic if symptoms worsen."]


def test_saved_empty_sections_are_replaced_with_visible_safe_fallbacks(full, conn):
    conn.execute("UPDATE outputs SET patient_summary = '', caregiver_checklist = ?, child_explanation = ''",
                 (json.dumps([]),))
    conn.commit()

    adult = outputs.latest_outputs(conn, full.users["owner"], full.p)
    child = outputs.latest_outputs(conn, full.users["child"], full.p)
    assert adult["patient_summary"].startswith("We could not prepare this summary")
    assert adult["caregiver_checklist"][0]["text"].startswith("Review this note's care steps")
    assert child["child_explanation"] == safety.SAFE_CHILD_MESSAGE
    assert adult["output_warning"] and child["output_warning"]

    adult_page = full.site["owner"].get(f"/p/{full.pid}/summaries?tab=caregiver").text
    child_page = full.site["child"].get(f"/p/{full.pid}/summaries?tab=child").text
    assert "Some saved text is unavailable" in adult_page and "Some saved text is unavailable" in child_page
    assert "The note has information about someone&#39;s health." in child_page


def test_output_is_not_returned_under_a_different_profile_than_its_note(conn, ctx, runner, world):
    from app import notes

    owner = world.user("Synthetic owner")
    source_profile = world.profile(owner, "Source profile")
    other_profile = world.profile(owner, "Other profile")
    note = notes.add_note(conn, ctx, runner, owner, source_profile, title="Synthetic", text=NOTE)
    runner.drain()
    conn.execute("UPDATE outputs SET profile_id = ? WHERE note_id = ?", (other_profile["id"], note["id"]))
    conn.commit()

    assert outputs.latest_outputs(conn, owner, source_profile)["available"] is False
    assert outputs.latest_outputs(conn, owner, other_profile)["available"] is False
    assert outputs.history(conn, owner, other_profile) == []


def test_user_facing_pages_keep_product_branding_and_the_prototype_notice(full, app):
    from conftest import Site

    public = Site(app)
    pages = [(public, url) for url in ("/", "/login", "/signup")]
    pages.extend((full.site["owner"], url) for url in
                 ("/profiles", f"/p/{full.pid}", f"/p/{full.pid}/notes", f"/p/{full.pid}/summaries"))
    for site, url in pages:
        page = site.get(url)
        assert page.status_code == 200
        assert "Family Care Circle" in page.text
        assert "Not for real patient data. Not medical advice." in page.text
