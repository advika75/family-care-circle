"""Dose-to-drug check, sentence-level recovery-phrase removal and caregiver appendix rendering (synthetic notes only)."""

from __future__ import annotations

import json
from pathlib import Path

from app import outputs, safety
from app.pipeline_adapter import AppEntityExtractor

ROOT = Path(__file__).resolve().parents[2]

# Synthetic excerpt modelled on the fictional NSTEMI test note: numbered medicine list.
NSTEMI_NOTE = """[Fictional example for software testing. Not a real patient.]
Diagnosis: non-ST-elevation myocardial infarction (heart attack).
Medications on discharge:
1. Aspirin 75 mg once daily, long term.
2. Clopidogrel 75 mg once daily for 12 months.
5. Ramipril 2.5 mg once daily.
7. Glyceryl trinitrate 0.5 mg tablet under the tongue if chest pain occurs; may repeat once after 5 minutes.
"""
BAD_GTN = ("The 75 mg dose of aspirin you took and the 2.5 mg dose of glyceryl trinitrate you take daily are "
           "important.")


def _record(note: str, patient: str, checklist: list[str] | None = None, child: str | None = None) -> dict:
    from fcc_testlib import make_record
    from src.ner import group_regimens

    entities = AppEntityExtractor().extract(note)
    record = make_record(patient=patient, checklist=checklist or ["Call the care team with any questions."],
                         child=child or "The person is resting. Grown-ups help.")
    record["entities"], record["regimens"] = entities, group_regimens(entities, note)
    return record


# ---- item 3: dose-to-drug consistency --------------------------------------------------------------------------
def test_nstemi_wrong_drug_dose_sentence_is_removed_and_correct_sentences_kept():
    patient = f"You had a heart attack. Take ramipril 2.5 mg once a day. {BAD_GTN} Take aspirin 75 mg every day."
    built = outputs.build_output(_record(NSTEMI_NOTE, patient), NSTEMI_NOTE)
    assert "glyceryl trinitrate you take daily" not in built["patient_summary"]
    assert "Take ramipril 2.5 mg once a day." in built["patient_summary"]
    assert "Take aspirin 75 mg every day." in built["patient_summary"]
    assert built["flags"]["dose_mismatch"]["patient_summary"] == [{"medication": "glyceryl trinitrate", "dose": "2.5 mg"}]


def test_correct_dose_for_the_named_medicine_is_kept_without_a_flag():
    patient = "Take ramipril 2.5 mg once a day. Use glyceryl trinitrate 0.5 mg under the tongue for chest pain."
    built = outputs.build_output(_record(NSTEMI_NOTE, patient), NSTEMI_NOTE)
    assert built["patient_summary"] == patient
    assert built["flags"]["dose_mismatch"] == {}


def test_dose_for_a_medicine_not_in_the_note_is_removed():
    patient = "Take ramipril 2.5 mg once a day. Take lisinopril 10 mg every morning."
    built = outputs.build_output(_record(NSTEMI_NOTE, patient), NSTEMI_NOTE)
    assert built["patient_summary"] == "Take ramipril 2.5 mg once a day."
    assert built["flags"]["dose_mismatch"]["patient_summary"] == [{"medication": "lisinopril", "dose": "10 mg"}]


def test_dose_for_a_note_medicine_that_has_no_dose_in_the_note_is_removed():
    note = "Patient has a headache.\n- Aspirin once daily as needed.\n"
    built = outputs.build_output(_record(note, "Rest at home. Take aspirin 300 mg daily."), note)
    assert built["patient_summary"] == "Rest at home."


def test_dose_with_no_nearby_medicine_name_is_left_alone():
    patient = ("Your medicine list has glyceryl trinitrate for chest pain. You will take 0.5 mg of this medicine under "
               "your tongue if you feel chest pain.")
    built = outputs.build_output(_record(NSTEMI_NOTE, patient), NSTEMI_NOTE)
    assert built["patient_summary"] == patient and built["flags"]["dose_mismatch"] == {}


def test_caregiver_line_with_a_wrong_drug_dose_is_removed():
    checklist = ["Give glyceryl trinitrate 2.5 mg every day.", "Give ramipril 2.5 mg once daily.",
                 "Call the clinic if chest pain lasts."]
    built = outputs.build_output(_record(NSTEMI_NOTE, "Take ramipril 2.5 mg once a day.", checklist), NSTEMI_NOTE)
    assert built["caregiver_checklist"] == ["Give ramipril 2.5 mg once daily.", "Call the clinic if chest pain lasts."]
    assert built["flags"]["dose_mismatch"]["caregiver_checklist"] == [{"medication": "glyceryl trinitrate", "dose": "2.5 mg"}]


def test_every_patient_sentence_removed_means_summary_unavailable():
    built = outputs.build_output(_record(NSTEMI_NOTE, BAD_GTN), NSTEMI_NOTE)
    assert built["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE
    assert built["flags"]["patient_summary_unavailable"] is True


def test_child_text_is_not_dose_checked_and_still_gated_as_before():
    child = "The person had a heart problem. Doctors are helping him."
    built = outputs.build_output(_record(NSTEMI_NOTE, f"Take ramipril 2.5 mg once a day. {BAD_GTN}", child=child),
                                 NSTEMI_NOTE)
    assert "child_explanation" not in built["flags"]["dose_mismatch"]
    assert built["child_explanation"] == child and built["flags"]["child_gate"]["reasons"] == []
    gated = outputs.build_output(_record(NSTEMI_NOTE, "Take ramipril 2.5 mg.", child="Take 2.5 mg of medicine."),
                                 NSTEMI_NOTE)
    assert gated["child_explanation"] == safety.SAFE_CHILD_MESSAGE and "digit" in gated["flags"]["child_gate"]["reasons"]


def _store(conn, built) -> None:
    conn.execute("UPDATE outputs SET patient_summary = ?, caregiver_checklist = ?, child_explanation = ?, "
                 "child_withheld = ?, flags = ?",
                 (built["patient_summary"], json.dumps(built["caregiver_checklist"]), built["child_explanation"],
                  1 if built["child_withheld"] else 0, json.dumps(built["flags"])))
    conn.commit()


def test_dose_warning_is_shown_to_patient_and_caregiver_but_not_child(full, conn):
    patient = f"Take ramipril 2.5 mg once a day. {BAD_GTN}"
    _store(conn, outputs.build_output(_record(NSTEMI_NOTE, patient), NSTEMI_NOTE))
    for role in ("patient", "caregiver", "owner"):
        data = outputs.latest_outputs(conn, full.users[role], full.p)
        assert data["dose_warning"] == outputs.DOSE_MISMATCH_WARNING, role
    assert "dose_warning" not in outputs.latest_outputs(conn, full.users["child"], full.p)
    page = full.site["patient"].get(f"/p/{full.pid}/summaries?tab=patient").text
    assert "A detail was removed because it did not match the note" in page and "glyceryl" not in page
    assert "2.5 mg" in page                                     # the kept ramipril sentence


# ---- item 4: recovery phrases remove a sentence, not the whole text ------------------------------------------------
MIGRAINE_NOTE = "Patient has migraines.\n- Propranolol 40 mg twice daily.\nReturn if headaches get worse.\n"


def test_patient_recovery_sentence_is_removed_and_the_rest_kept():
    patient = ("You have migraines. Propranolol will help you feel better soon. Take propranolol 40 mg twice a day.")
    built = outputs.build_output(_record(MIGRAINE_NOTE, patient), MIGRAINE_NOTE)
    assert built["patient_summary"] == "You have migraines. Take propranolol 40 mg twice a day."
    assert built["flags"]["recovery_removed"] == {"patient_summary": 1}
    assert built["flags"]["patient_summary_needs_review"] is True
    assert "unsupported_recovery" in built["flags"]["clinical_claim_gate"]["patient"]


def test_caregiver_recovery_line_is_removed_and_the_rest_kept():
    checklist = ["Give propranolol 40 mg twice a day.", "Watch for signs that the headaches are getting better.",
                 "Call if headaches get worse."]
    built = outputs.build_output(_record(MIGRAINE_NOTE, "Take propranolol 40 mg twice a day.", checklist), MIGRAINE_NOTE)
    assert built["caregiver_checklist"] == ["Give propranolol 40 mg twice a day.", "Call if headaches get worse."]
    assert built["flags"]["recovery_removed"] == {"caregiver_checklist": 1}
    assert built["flags"]["caregiver_fallback"] is False


def test_only_recovery_sentences_means_summary_unavailable():
    built = outputs.build_output(_record(MIGRAINE_NOTE, "You will feel better soon. You are recovering well."),
                                 MIGRAINE_NOTE)
    assert built["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE


def test_recovery_sentence_is_kept_when_the_note_states_improvement():
    note = MIGRAINE_NOTE + "Headaches have improved since the last visit.\n"
    patient = "Your headaches have improved. Take propranolol 40 mg twice a day."
    built = outputs.build_output(_record(note, patient), note)
    assert built["patient_summary"] == patient and built["flags"]["recovery_removed"] == {}


def test_other_unsupported_claims_still_replace_the_whole_patient_text():
    built = outputs.build_output(_record(MIGRAINE_NOTE, "You had a heart attack. Take propranolol 40 mg twice a day."),
                                 MIGRAINE_NOTE)
    assert built["patient_summary"] == outputs.PATIENT_REVIEW_FALLBACK


def test_child_text_with_a_recovery_phrase_is_still_withheld_whole():
    built = outputs.build_output(_record(MIGRAINE_NOTE, "Take propranolol 40 mg twice a day.",
                                         child="The person has headaches. The person will feel better soon."),
                                 MIGRAINE_NOTE)
    assert built["child_explanation"] == safety.SAFE_CHILD_MESSAGE


def test_recovery_category_names_the_matched_rule_only():
    from app.clinical_safety import recovery_category

    assert recovery_category("This will help you feel better.") == "feel better"
    assert recovery_category("She is recovering at home.") == "recover"
    assert recovery_category("Breathing improved.") == "improve"
    assert recovery_category("Take the medicine.") is None


# ---- item 5: caregiver appended fact lines are rendered from the regimen ---------------------------------------------
ASTHMA_NOTE = (ROOT / "data" / "raw" / "note_04.txt").read_text()
RESEARCH_APPENDIX = ["Ask the care team to review the treatment plan and medicines with you.",
                     "Confirm with the care team: 30 mg (dosage)", "Confirm with the care team: daily (frequency)",
                     "Confirm with the care team: 44 mcg (dosage)", "Confirm with the care team: BID (frequency)"]


def test_appended_fact_lines_are_rendered_with_their_medicine():
    built = outputs.build_output(_record(ASTHMA_NOTE, "Use albuterol when you wheeze.", RESEARCH_APPENDIX), ASTHMA_NOTE)
    assert built["caregiver_checklist"] == [
        "Ask the care team to review the treatment plan and medicines with you.",
        "Confirm with the care team: Prednisolone, 30 mg, daily, 4 more days.",
        "Confirm with the care team: Fluticasone, 44 mcg, 2 puffs, BID.",
    ]
    assert not any(line.endswith(("(dosage)", "(frequency)")) for line in built["caregiver_checklist"])
    assert built["flags"]["caregiver_appendix_rendered"] == 4


def test_appended_fact_matching_two_medicines_renders_both_and_unmatched_facts_are_dropped():
    checklist = ["Give albuterol when wheezing.", "Confirm with the care team: 2 puffs (dosage)",
                 "Confirm with the care team: 75 mg (dosage)"]
    built = outputs.build_output(_record(ASTHMA_NOTE, "Use albuterol when you wheeze.", checklist), ASTHMA_NOTE)
    assert built["caregiver_checklist"] == [
        "Give albuterol when wheezing.",
        "Confirm with the care team: Albuterol, 90 mcg, 2 puffs, every 4 hours, as needed.",
        "Confirm with the care team: Fluticasone, 44 mcg, 2 puffs, BID.",
    ]
