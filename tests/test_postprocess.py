"""Tests for src/postprocess.py: cleaning, retries, fallback and validation."""

from __future__ import annotations

from src.postprocess import (
    add_fallback,
    clean_output,
    find_contradicted_dosages,
    generate_with_retries,
    parse_checklist,
    redact_contradicted_dosages,
    validate_output,
)


REQUIRED = [
    {"text": "Amoxicillin", "label": "MEDICATION"},
    {"text": "500 mg", "label": "DOSAGE"},
    {"text": "BID", "label": "FREQUENCY"},
    {"text": "10 days", "label": "DURATION"},
]


def test_clean_strips_fences_and_preamble():
    raw = "Sure! Here is the summary:\n```markdown\nTake amoxicillin 500 mg.\n```\nHope this helps"
    assert clean_output(raw) == "Take amoxicillin 500 mg."


def test_clean_strips_preamble_without_fences():
    assert clean_output("Here is the checklist:\n- Give medicine\n") == "- Give medicine"


def test_clean_strips_special_tokens_and_role_prefix():
    assert clean_output("assistant: Hello there.<|im_end|>") == "Hello there."


def test_clean_unwraps_json():
    raw = '{"patient_summary": "You have strep throat."}'
    assert clean_output(raw, "patient_summary") == "You have strep throat."


def test_clean_empty():
    assert clean_output(None) == "" and clean_output("   ") == ""


def test_parse_checklist_handles_markers_and_headings():
    text = "Medicines:\n- Give amoxicillin\n* Check temperature\n1. Call doctor\n[ ] Book follow-up\n\n"
    assert parse_checklist(text) == ["Give amoxicillin", "Check temperature", "Call doctor", "Book follow-up"]


def test_retry_until_complete():
    outputs = iter(["", "Take amoxicillin.", "Take amoxicillin 500mg twice a day for 10 days."])
    seen = []

    def fake(messages):
        seen.append(messages)
        return next(outputs)

    result = generate_with_retries(fake, [{"role": "user", "content": "x"}], REQUIRED, "patient_summary", 3)
    assert result.retries == 2 and not result.fallback_used and not result.missing
    # the retry after a partial answer tells the model what was missing
    assert "500 mg" in seen[2][-1]["content"]


def test_fallback_lists_missing_entities():
    result = generate_with_retries(lambda m: "Take amoxicillin.", [], REQUIRED, "patient_summary", max_retries=1)
    assert result.fallback_used and result.attempts == 2
    assert {m["text"] for m in result.missing} == {"500 mg", "BID", "10 days"}
    assert "500 mg" in result.text and "10 days" in result.text


def test_fallback_for_all_empty_outputs():
    result = generate_with_retries(lambda m: "", [], [], "child_explanation", max_retries=1)
    assert result.fallback_used and result.text.strip()


def test_add_fallback_checklist_adds_bullets():
    text = add_fallback("- Give amoxicillin", [REQUIRED[1]], "caregiver_checklist")
    assert parse_checklist(text)[-1].startswith("Confirm with the care team: 500 mg")


def test_validate_output():
    good = {"patient_summary": "a", "caregiver_checklist": ["b"], "child_explanation": "c"}
    assert validate_output(good) == []
    bad = {"patient_summary": "", "caregiver_checklist": [], "child_explanation": "c"}
    assert len(validate_output(bad)) == 2


def test_retry_feedback_names_hallucinated_medication():
    """Regression for mtsamples_Carotid_Cerebral_Arteriograms / mtsamples_Aortobifemoral_Bypass_-_1 /
    mtsamples_Arterial_Imaging: the caregiver draft invented "aspirin" as a post-procedure instruction
    though no medication was mentioned in the source note."""
    source = "PROCEDURE: Carotid cerebral arteriogram. No medications were administered during the procedure."
    outputs = iter([
        "- Take aspirin daily to prevent clots.",
        "- Watch the puncture site for bleeding or swelling.",
    ])
    seen = []

    def fake(messages):
        seen.append(messages)
        return next(outputs)

    result = generate_with_retries(fake, [{"role": "user", "content": "x"}], [], "caregiver_checklist",
                                    max_retries=1, source=source, entities=[])
    assert "aspirin" in seen[1][-1]["content"].lower()  # retry feedback names the invented drug
    assert not result.fallback_used and "aspirin" not in result.text.lower()


def test_hallucination_check_is_skipped_without_source():
    """Backward compatibility: callers that don't pass ``source`` see the old missing-only behavior."""
    result = generate_with_retries(lambda m: "Take aspirin.", [], [], "caregiver_checklist", max_retries=0)
    assert not result.fallback_used and result.retries == 0


def test_find_contradicted_dosages_flags_wrong_directive_dose():
    """Regression for mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit: the source says Celesta
    tablets are 40 mg each, but the caregiver draft instructed "give the patient 20 mg"."""
    source = "Patient ingested two to three tablets of Celesta 40 mg per tablet."
    text = "Give the patient 20 mg of Celesta in the morning, as prescribed by the doctor."
    found = find_contradicted_dosages(text, source)
    assert len(found) == 1 and found[0]["dose"] == "20 mg"


def test_find_contradicted_dosages_accepts_matching_dose():
    source = "Patient ingested two to three tablets of Celesta 40 mg per tablet."
    text = "Give the patient 40 mg of Celesta in the morning."
    assert find_contradicted_dosages(text, source) == []


def test_find_contradicted_dosages_accepts_spelled_out_source_dose():
    """A dose the rule-based NER would miss (spelled-out number, no digit) must still count as
    supported, so a real fact is never redacted just because the extractor has a lexicon gap
    (regression guard: this bit the first version of the check, see mtsamples_Carpal_Ligament_Release_-_2
    and mtsamples_Acute_Inferior_Myocardial_Infarction, where "One mL" and "81 milligrams" are genuinely
    in the source but were not extracted as DOSAGE entities)."""
    source = "One mL of Celestone was introduced into the carpal tunnel."
    text = "Give the patient 1 mL of Celestone."
    assert find_contradicted_dosages(text, source) == []


def test_find_contradicted_dosages_noop_without_source():
    text = "Give the patient 20 mg of Celesta in the morning."
    assert find_contradicted_dosages(text, "") == []


def test_redact_contradicted_dosages_replaces_wrong_dose():
    source = "Patient ingested two to three tablets of Celesta 40 mg per tablet."
    text = "Give the patient 20 mg of Celesta in the morning, as prescribed by the doctor."
    fixed, redacted = redact_contradicted_dosages(text, source)
    assert redacted == ["20 mg"]
    assert "20 mg" not in fixed and "the dose your care team prescribed" in fixed


def test_redact_contradicted_dosages_leaves_correct_dose_alone():
    source = "Patient ingested two to three tablets of Celesta 40 mg per tablet."
    text = "Give the patient 40 mg of Celesta in the morning."
    fixed, redacted = redact_contradicted_dosages(text, source)
    assert redacted == [] and fixed == text


def test_truncation_flag_follows_the_kept_attempt():
    outputs = iter([("Take amoxicillin 500 mg", True), ("Take amoxicillin 500 mg twice a day for 10 days.", False)])
    flags = []

    def fake(_messages):
        text, cut = next(outputs)
        flags.append(cut)
        return text

    required = [{"text": "Amoxicillin", "label": "MEDICATION"}, {"text": "10 days", "label": "DURATION"}]
    result = generate_with_retries(fake, [{"role": "user", "content": "x"}], required, "patient_summary", 2)
    assert result.used_attempt == 1 and flags[result.used_attempt] is False
