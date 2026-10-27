"""Regressions found in the local Ollama demo, reproduced with a SYNTHETIC diabetes follow-up note (no real patient)."""

from __future__ import annotations

import json

from src.prompts import format_must_include

from app import outputs
from app.config import Settings
from app.pipeline_adapter import AppEntityExtractor, build_pipeline


MEERA_NOTE = """**Title: Diabetes Follow-up Visit**

Patient: Meera Sharma, age 58.

Meera has type 2 diabetes mellitus and hypertension. She reports feeling dizzy when standing up, especially in the morning. Her blood pressure at today's visit is 94/62 mmHg. Her fasting blood glucose is 168 mg/dL, and her HbA1c is 7.8%.

Her current medication list records metformin 500 mg twice daily and amlodipine 5 mg once daily. She reports taking her prescribed medications regularly. No medication changes were documented during today's visit.

Meera is advised to maintain a record of her blood glucose and blood pressure readings, rise slowly from sitting or lying positions, and arrange a follow-up with her healthcare professional regarding dizziness and low blood pressure. She should not change or stop any medication without consulting her healthcare professional.

Follow-up: Review blood pressure readings, dizziness, and blood glucose records with the healthcare professional.
"""
REQUIRED = ["MEDICATION", "DOSAGE", "FREQUENCY", "DURATION"]


def _dosages(text: str) -> list[str]:
    return [e["text"] for e in AppEntityExtractor().extract(text) if e["label"] == "DOSAGE"]


def test_lab_measurement_is_not_extracted_as_a_dose_but_medicine_doses_are_kept():
    from src.ner import group_regimens

    entities = AppEntityExtractor().extract(MEERA_NOTE)
    assert [e["text"] for e in entities if e["label"] == "DOSAGE"] == ["500 mg", "5 mg"]
    assert group_regimens(entities, MEERA_NOTE) == [
        {"medication": "metformin", "dosages": ["500 mg"], "frequencies": ["twice daily"], "durations": []},
        {"medication": "amlodipine", "dosages": ["5 mg"], "frequencies": ["once daily"], "durations": []},
    ]
    block = format_must_include(entities, group_regimens(entities, MEERA_NOTE), REQUIRED)
    assert "168 mg" not in block and "Other dosage" not in block
    assert "- Medication: metformin | dose: 500 mg" in block and "- Medication: amlodipine | dose: 5 mg" in block


def test_measurement_filter_covers_concentration_units_and_keeps_dose_rates():
    assert _dosages("Hemoglobin 13.5 g/dL. Sodium 140 mEq/L. ALT 40 IU/L. Glucose 168 mg per dL.") == []
    assert _dosages("Potassium 4.1 mmol/L. Glucose 9.3 mmol/l.") == []            # never a DOSAGE match to begin with
    assert _dosages("Amoxicillin 250 mg/5 mL. Give 10 mg/kg. Insulin 2 units/hr.") == ["250 mg", "5 mL", "10 mg", "2 units"]
    assert _dosages("Ceftriaxone 1 g IV daily. Potassium chloride 20 mEq PO daily.") == ["1 g", "20 mEq"]


def test_every_app_backend_uses_the_measurement_filter_but_research_default_does_not():
    from src.ner import EntityExtractor
    from src.pipeline import FamilyCarePipeline
    from src.utils import load_config

    assert isinstance(build_pipeline(Settings(backend="mock")).extractor, AppEntityExtractor)
    research = FamilyCarePipeline(load_config("config.yaml", {"backend": "mock"}))
    assert type(research.extractor) is EntityExtractor
    assert "168 mg" in [e["text"] for e in research.extractor.extract(MEERA_NOTE)]   # research behaviour unchanged


def test_mock_run_of_synthetic_note_has_no_lab_value_in_required_or_appended_facts():
    record = build_pipeline(Settings(backend="mock")).run(MEERA_NOTE, doc_id="synthetic-meera")
    assert "168 mg" not in [e["text"] for e in record["entities"]]
    assert all("168 mg" not in missing for missing in record["metadata"]["missing_after_retries"].values())


# ---- honest patient failure -----------------------------------------------------------------------------------
# What the research retry loop returned for the Meera note: its empty-output text plus the appended "missing" fact.
FAILED_PATIENT_TEXT = ("We could not create a summary. Please ask your care team to go over your visit notes with you."
                       "\n\nImportant details from your care team's note: 168 mg (dosage).")


def _failed_patient_record() -> dict:
    from fcc_testlib import make_record

    record = make_record(patient=FAILED_PATIENT_TEXT)
    record["metadata"]["fallback_used"]["patient_summary"] = True
    record["metadata"]["missing_after_retries"]["patient_summary"] = ["168 mg"]
    return record


def test_failed_patient_summary_is_stored_as_unavailable_without_appended_details():
    built = outputs.build_output(_failed_patient_record(), MEERA_NOTE)
    assert built["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE
    assert built["patient_summary"] == ("Summary unavailable. Please ask your care team to go over the visit notes "
                                        "with you.")
    assert "Important details" not in built["patient_summary"] and "(dosage)" not in built["patient_summary"]
    assert built["flags"]["patient_summary_unavailable"] is True


def test_patient_summary_without_fallback_is_kept():
    from fcc_testlib import SOURCE_TEXT, make_record

    built = outputs.build_output(make_record(), SOURCE_TEXT)
    assert built["patient_summary"].startswith("You have strep throat.")
    assert built["flags"]["patient_summary_unavailable"] is False


def _store_failed_patient_output(conn) -> None:
    built = outputs.build_output(_failed_patient_record(), MEERA_NOTE)
    conn.execute("UPDATE outputs SET patient_summary = ?, flags = ?",
                 (built["patient_summary"], json.dumps(built["flags"])))
    conn.commit()


def test_patient_role_sees_unavailable_warning_and_never_the_dosage_label(full, conn):
    _store_failed_patient_output(conn)

    patient = outputs.latest_outputs(conn, full.users["patient"], full.p)
    assert patient["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE
    assert patient["patient_warning"] == outputs.PATIENT_UNAVAILABLE_WARNING
    assert "flags" not in patient and "note" not in patient          # the warning exposes no restricted data
    for path in (f"/p/{full.pid}/summaries?tab=patient", f"/p/{full.pid}"):
        page = full.site["patient"].get(path).text
        assert "Summary unavailable" in page and "This summary could not be prepared" in page
        assert "(dosage)" not in page and "168 mg" not in page and "Important details" not in page


def test_child_role_does_not_get_the_patient_summary_warning(full, conn):
    _store_failed_patient_output(conn)

    child = outputs.latest_outputs(conn, full.users["child"], full.p)
    assert "patient_warning" not in child and "patient_summary" not in child


# ---- child perspective in the prompt ----------------------------------------------------------------------------
class _Recorder:
    """Stands in for a model generator and records the messages it was sent."""

    backend, model_id, model_hash, seed, last_truncated = "fake", "fake", "fake", 1, False

    def __init__(self) -> None:
        self.sent: list[list[dict[str, str]]] = []

    def generate(self, messages, **overrides):
        self.sent.append(messages)
        return "draft"


def _guarded(persona: str, note: str = MEERA_NOTE, retry: bool = False) -> tuple[list[dict], list[dict]]:
    from src.ner import group_regimens
    from src.prompts import build_messages, build_retry_messages

    from app.pipeline_adapter import _AppPromptGuard

    entities = AppEntityExtractor().extract(note)
    required = [] if persona == "child_explanation" else REQUIRED      # as in config.yaml
    messages = build_messages(persona, note, entities, group_regimens(entities, note), required, True, "v2")
    if retry:
        messages = build_retry_messages(messages, "You have diabetes.", [], [])
    recorder = _Recorder()
    _AppPromptGuard(recorder).generate(messages)
    return messages, recorder.sent[0]


def test_research_child_prompt_still_has_the_line_the_app_replaces():
    from src.prompts import CHILD_INSTRUCTIONS

    from app.pipeline_adapter import _CHILD_YOU_RULE

    assert _CHILD_YOU_RULE in CHILD_INSTRUCTIONS["v2"]


def test_child_prompt_uses_third_person_with_first_name_from_patient_line():
    original, sent = _guarded("child_explanation")
    user = sent[-1]["content"]
    assert 'Talk to the child as "you"' not in user
    assert "Talk to the child about Meera in the third person" in user
    assert "taking care of Meera." in user and "Refer to the patient as Meera." in user
    assert "Sharma" not in user.split('"""')[-1]                    # first name only, outside the quoted note
    assert 'Talk to the child as "you"' in original[-1]["content"]   # the pipeline's own messages are not mutated


def test_child_prompt_uses_the_person_without_an_explicit_name_line():
    for note in ("Meera has type 2 diabetes. Metformin 500 mg twice daily.",
                 "Patient: 58-year-old woman with type 2 diabetes.",
                 "Name: Female, age 58. Type 2 diabetes.",
                 "Patient: Mr. Lee. Type 2 diabetes.",
                 "History: Patient: unknown. Type 2 diabetes."):
        user = _guarded("child_explanation", note)[1][-1]["content"]
        assert "Talk to the child about the person in the third person" in user, note
        assert "Refer to the patient as the person." in user, note


def test_child_prompt_rewrite_survives_retries_exactly_once():
    original, sent = _guarded("child_explanation", retry=True)
    first_user = sent[1]["content"]
    assert first_user.count("Talk to the child about Meera in the third person") == 1
    assert first_user.count("Additional child-output safety rules") == 1
    assert 'Talk to the child as "you"' not in first_user
    assert sent[-1] == original[-1]                                  # the retry feedback message is untouched


def test_patient_and_caregiver_prompts_are_not_rewritten():
    for persona in ("patient_summary", "caregiver_checklist"):
        original, sent = _guarded(persona)
        assert sent == original


# ---- child perspective in the gate ------------------------------------------------------------------------------
OBSERVED_CHILD_TEXT = (  # what the qwen2.5:3b demo showed for the synthetic Meera note
    "You have diabetes. You take medicine to help your body use sugar better.\n"
    "Your doctor checked your blood sugar and found it was a bit high.\n"
    "You're dizzy sometimes, especially when you stand up quickly.\n"
    "The doctors are helping you feel better and keep your numbers in check.\n"
    "You need to be gentle when you move to avoid feeling dizzy.\n"
    "Remember to tell your doctor if you have any more dizziness or high sugar.")
MEDS = ["metformin", "amlodipine"]


def test_child_gate_rejects_text_that_treats_the_child_as_the_patient():
    from app import safety

    for text in (OBSERVED_CHILD_TEXT, "You have diabetes.", "You feel dizzy sometimes.", "You're sick right now.",
                 "Your body needs help with sugar.", "The doctors are taking care of you.",
                 "You have type 2 diabetes mellitus and hypertension."):
        assert safety.REASON_CHILD_AS_PATIENT in safety.check_child_text(text, MEDS), text
        assert safety.REASON_CHILD_AS_PATIENT in safety.check_child_text(text, MEDS, MEERA_NOTE), text


def test_child_gate_passes_third_person_text_and_harmless_second_person_lines():
    from fcc_testlib import CLEAN_CHILD

    from app import safety

    for text in ("Meera has diabetes. Doctors are helping her.", safety.SAFE_CHILD_MESSAGE, CLEAN_CHILD,
                 "You are loved. You can give Meera a hug.", "If you have questions, ask a grown-up.",
                 "The person in the note has diabetes. The grown-ups are taking care of her. You can help her."):
        assert safety.check_child_text(text, MEDS, MEERA_NOTE) == [], text


def test_research_empty_child_fallback_is_replaced_with_the_safe_message():
    from fcc_testlib import make_record
    from src.postprocess import EMPTY_FALLBACK

    from app import safety

    built = outputs.build_output(make_record(child=EMPTY_FALLBACK["child_explanation"]), MEERA_NOTE)
    assert built["child_withheld"] is True
    assert built["child_explanation"] == safety.SAFE_CHILD_MESSAGE
    assert safety.REASON_GENERIC_FALLBACK in built["flags"]["child_gate"]["reasons"]


def test_observed_child_text_is_withheld_by_build_output():
    from fcc_testlib import make_record

    from app import safety

    built = outputs.build_output(make_record(child=OBSERVED_CHILD_TEXT), MEERA_NOTE)
    assert built["child_explanation"] == safety.SAFE_CHILD_MESSAGE
    assert safety.REASON_CHILD_AS_PATIENT in built["flags"]["child_gate"]["reasons"]


# ---- outputs saved before the current gates -----------------------------------------------------------------------
def _store_legacy_output(conn, gate_version=None) -> None:
    """Mimic the stored Meera output: saved by an older build, so its flags carry no (or an older) gate version."""
    from fcc_testlib import make_record

    flags = outputs.build_output(make_record(), MEERA_NOTE)["flags"]
    flags.pop("gate_version")
    flags.pop("patient_summary_unavailable")
    flags.pop("clinical_claim_gate")
    flags["fallback_used"]["patient_summary"] = True
    if gate_version is not None:
        flags["gate_version"] = gate_version
    conn.execute("UPDATE outputs SET patient_summary = ?, child_explanation = ?, child_withheld = 0, flags = ?",
                 (FAILED_PATIENT_TEXT, OBSERVED_CHILD_TEXT, json.dumps(flags)))
    conn.commit()


def test_new_outputs_record_the_current_gate_version():
    from fcc_testlib import make_record

    assert outputs.build_output(make_record(), MEERA_NOTE)["flags"]["gate_version"] == outputs.GATE_VERSION


def test_output_saved_without_gate_version_shows_safe_child_message_and_review_warning(full, conn):
    from app import safety

    _store_legacy_output(conn)

    child = outputs.latest_outputs(conn, full.users["child"], full.p)
    assert child["child_explanation"] == safety.SAFE_CHILD_MESSAGE
    assert child["review_message"] == outputs.UNCONFIRMED_OUTPUT_WARNING and "flags" not in child
    patient = outputs.latest_outputs(conn, full.users["patient"], full.p)
    assert patient["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE
    assert patient["patient_warning"] == outputs.PATIENT_UNAVAILABLE_WARNING
    assert patient["review_message"] == outputs.UNCONFIRMED_OUTPUT_WARNING and "flags" not in patient
    owner = outputs.latest_outputs(conn, full.users["owner"], full.p)
    assert owner["child_explanation"] == safety.SAFE_CHILD_MESSAGE and owner["child_withheld"] is True
    assert owner["review_message"] == outputs.UNCONFIRMED_OUTPUT_WARNING

    child_page = full.site["child"].get(f"/p/{full.pid}/summaries?tab=child").text
    assert "You have diabetes" not in child_page and "Please review the note" in child_page
    patient_page = full.site["patient"].get(f"/p/{full.pid}/summaries?tab=patient").text
    assert "(dosage)" not in patient_page and "168 mg" not in patient_page
    note_id = conn.execute("SELECT note_id FROM outputs").fetchone()["note_id"]
    history = full.site["owner"].get(f"/p/{full.pid}/summaries?tab=child&note={note_id}")
    assert history.status_code == 200
    assert "Their care team can explain what it means" in history.text and "You have diabetes" not in history.text


def test_output_with_older_gate_version_is_treated_as_legacy(full, conn):
    from app import safety

    _store_legacy_output(conn, gate_version=outputs.GATE_VERSION - 1)
    assert outputs.latest_outputs(conn, full.users["child"], full.p)["child_explanation"] == safety.SAFE_CHILD_MESSAGE


def test_current_version_output_is_shown_as_stored(full, conn):
    stored = conn.execute("SELECT child_explanation, flags FROM outputs").fetchone()
    assert json.loads(stored["flags"])["gate_version"] == outputs.GATE_VERSION
    child = outputs.latest_outputs(conn, full.users["child"], full.p)
    assert child["child_explanation"] == stored["child_explanation"]


# ---- context-aware invented-medication check (app reference implementation) ---------------------------------------
INSULIN_EXPLANATION = (  # from the real qwen2.5:3b draft for the Meera note
    "You have diabetes, which is a condition where your body doesn't make enough of a hormone called insulin. "
    "This can make your blood sugar levels too high. You take 500 milligrams of metformin twice a day.")


def test_explaining_insulin_is_not_an_invented_medication():
    from app.medication_check import invented_medications

    for draft in (INSULIN_EXPLANATION, "Your body makes insulin to use sugar.", "The body's insulin helps with sugar.",
                  "There is less insulin in your body than before."):
        assert invented_medications(draft, MEERA_NOTE) == [], draft


def test_dosing_insulin_absent_from_the_note_is_still_an_invented_medication():
    from app.medication_check import invented_medications

    for draft in ("Take insulin 10 units daily.", "Your body makes insulin. Take insulin 10 units daily.",
                  "Your doctor will start insulin.", "A hormone called insulin is given as an injection daily."):
        assert invented_medications(draft, MEERA_NOTE) == ["insulin"], draft


def test_other_invented_medications_are_unchanged():
    from app.medication_check import invented_medications

    assert invented_medications("Take lisinopril every morning.", MEERA_NOTE) == ["lisinopril"]
    assert invented_medications("You take metformin twice a day.", MEERA_NOTE) == []


def test_research_retry_check_still_counts_the_explanation_known_limitation():
    """Pins the limitation: the pipeline's retry loop uses the research check, which the app cannot replace."""
    from src.evaluator import unsupported_meds

    assert unsupported_meds(INSULIN_EXPLANATION, MEERA_NOTE)["unsupported"] == ["insulin"]


# ---- refined patient failure: generic replacement vs. a real draft with additions ----------------------------------
REAL_DRAFT = ("You have type 2 diabetes and high blood pressure. You take metformin 500 mg and amlodipine 5 mg once a "
              "day. Stand up slowly if you feel dizzy.")


def _patient_record(text: str, missing=(), redacted=()) -> dict:
    from fcc_testlib import make_record

    record = make_record(patient=text)
    record["metadata"]["fallback_used"]["patient_summary"] = True
    record["metadata"]["missing_after_retries"]["patient_summary"] = list(missing)
    record["metadata"]["redacted_dosages"]["patient_summary"] = list(redacted)
    return record


def test_real_draft_with_appended_missing_facts_is_kept_with_a_review_warning_flag():
    text = REAL_DRAFT + "\n\nImportant details from your care team's note: twice daily (frequency)."
    built = outputs.build_output(_patient_record(text, missing=["twice daily"]), MEERA_NOTE)
    assert built["patient_summary"] == text
    assert built["flags"]["patient_summary_unavailable"] is False
    assert built["flags"]["patient_summary_needs_review"] is True


def test_real_draft_with_a_redacted_dose_is_kept_with_a_review_warning_flag():
    text = "Give metformin the dose your care team prescribed twice a day."
    built = outputs.build_output(_patient_record(text, redacted=["850 mg"]), MEERA_NOTE)
    assert built["patient_summary"] == text
    assert built["flags"]["patient_summary_needs_review"] is True and built["flags"]["patient_summary_unavailable"] is False


def test_generic_text_that_replaced_every_attempt_is_unavailable_even_with_appended_facts():
    from src.postprocess import EMPTY_FALLBACK

    all_empty = (EMPTY_FALLBACK["patient_summary"] + "\n\nImportant details from your care team's note: metformin "
                 "(medication); 500 mg (dosage).")
    for text in (all_empty, FAILED_PATIENT_TEXT, EMPTY_FALLBACK["patient_summary"]):
        built = outputs.build_output(_patient_record(text, missing=["metformin", "500 mg"]), MEERA_NOTE)
        assert built["patient_summary"] == outputs.PATIENT_UNAVAILABLE_MESSAGE
        assert built["flags"]["patient_summary_unavailable"] is True
        assert built["flags"]["patient_summary_needs_review"] is False


def test_patient_role_sees_the_draft_and_the_review_warning(full, conn):
    text = REAL_DRAFT + "\n\nImportant details from your care team's note: twice daily (frequency)."
    built = outputs.build_output(_patient_record(text, missing=["twice daily"]), MEERA_NOTE)
    conn.execute("UPDATE outputs SET patient_summary = ?, flags = ?", (built["patient_summary"], json.dumps(built["flags"])))
    conn.commit()

    patient = outputs.latest_outputs(conn, full.users["patient"], full.p)
    assert patient["patient_summary"] == text
    assert patient["patient_warning"] == outputs.PATIENT_REVIEW_WARNING and "flags" not in patient
    page = full.site["patient"].get(f"/p/{full.pid}/summaries?tab=patient").text
    assert "You have type 2 diabetes" in page and "could not be checked against the note" in page
    assert "Summary unavailable" not in page


def test_legacy_output_with_a_real_draft_keeps_the_draft_and_warns(full, conn):
    _store_legacy_output(conn)
    conn.execute("UPDATE outputs SET patient_summary = ?", (REAL_DRAFT,))
    conn.commit()

    patient = outputs.latest_outputs(conn, full.users["patient"], full.p)
    assert patient["patient_summary"] == REAL_DRAFT
    assert patient["patient_warning"] == outputs.PATIENT_REVIEW_WARNING
