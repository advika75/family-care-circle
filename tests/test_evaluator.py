"""Tests for src/evaluator.py: readability, ROUGE, retention, NER scoring, hallucination,
repetition, truncation and child-rule metrics."""

from __future__ import annotations

import copy
import math

import pandas as pd
import pytest

from src.evaluator import (
    child_rule_checks,
    entity_retention,
    evaluate_record,
    match_entities,
    medication_mentions,
    ner_scores,
    readability,
    repeated_units,
    rouge,
    summarize,
    unsupported_meds,
    unsupported_numbers,
)
from src.ner import extract_entities
from src.pipeline import FamilyCarePipeline


def test_readability_simple_text_is_easier():
    hard = "Pharmacological intervention necessitates continuous administration of antimicrobial therapeutics."
    easy = "Take your pill. It helps you feel good. Drink lots of water."
    assert readability(easy)["fkgl"] < readability(hard)["fkgl"]
    assert readability(easy)["fre"] > readability(hard)["fre"]
    assert math.isnan(readability("")["fkgl"])


def test_rouge_bounds():
    same = rouge("take amoxicillin twice a day", "take amoxicillin twice a day")
    assert same["rouge1"] == pytest.approx(1.0)
    assert 0 <= rouge("hello", "take amoxicillin")["rougeL"] <= 1


def test_entity_retention_per_label():
    entities = [
        {"text": "Amoxicillin", "label": "MEDICATION"}, {"text": "500 mg", "label": "DOSAGE"},
        {"text": "BID", "label": "FREQUENCY"}, {"text": "10 days", "label": "DURATION"},
        {"text": "500 mg", "label": "DOSAGE"},  # duplicate counted once
        {"text": "fever", "label": "SYMPTOM"},  # not a retention label
    ]
    ret = entity_retention(entities, "Take amoxicillin 500mg twice a day.")
    assert ret["n"] == 4
    assert ret["overall"] == pytest.approx(0.75)
    assert ret["per_label"]["DURATION"] == 0.0 and ret["per_label"]["DOSAGE"] == 1.0
    assert ret["missing"] == ["10 days"]


def test_entity_retention_empty_is_nan():
    assert math.isnan(entity_retention([], "anything")["overall"])


def _ent(label, start, end):
    return {"text": "x", "label": label, "start": start, "end": end}


def test_ner_exact_vs_relaxed():
    gold = [_ent("MEDICATION", 0, 20), _ent("DOSAGE", 25, 31), _ent("SYMPTOM", 40, 45)]
    pred = [_ent("MEDICATION", 0, 10), _ent("DOSAGE", 25, 31), _ent("CONDITION", 40, 45), _ent("DURATION", 50, 55)]
    exact = ner_scores([(pred, gold)], "exact")
    relaxed = ner_scores([(pred, gold)], "relaxed")
    assert exact["MICRO"]["tp"] == 1 and relaxed["MICRO"]["tp"] == 2
    assert exact["MICRO"]["precision"] == pytest.approx(1 / 4)
    assert relaxed["MICRO"]["recall"] == pytest.approx(2 / 3)
    assert exact["DOSAGE"]["f1"] == 1.0 and exact["SYMPTOM"]["recall"] == 0.0


def test_match_entities_is_one_to_one():
    gold = [_ent("DOSAGE", 0, 10)]
    pred = [_ent("DOSAGE", 0, 5), _ent("DOSAGE", 5, 10)]
    assert len(match_entities(pred, gold, "relaxed")) == 1


def test_evaluate_record_and_summary(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t1")
    row = evaluate_record(record)
    assert row["patient_summary_retention"] == 1.0
    assert row["caregiver_checklist_retention"] == 1.0
    assert row["child_explanation_fkgl"] < row["source_fkgl"]
    assert row["valid"] is True
    summary = summarize(pd.DataFrame([row, row]))
    assert summary.loc["format_validity_rate", "mean"] == 1.0
    assert summary.loc["patient_summary_retention", "std"] == 0.0


def test_model_retention_excludes_fallback(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t1")
    record["metadata"]["missing_after_retries"]["patient_summary"] = ["10 days"]
    row = evaluate_record(record)
    assert row["patient_summary_retention"] == 1.0
    assert row["patient_summary_retention_model"] < 1.0


# --------------------------------------------------------------------------- unsupported content


SOURCE = (
    "1. Amoxicillin 500 mg PO BID x 10 days.\n"
    "2. Ibuprofen 200 mg PO q6h PRN fever. Fever to 101.8 F. Recheck in 48-72 hours.\n"
)


ENTS = extract_entities(SOURCE)


def _nums(text):
    return unsupported_numbers(text, SOURCE, ENTS)["unsupported"]


def test_supported_numbers_pass():
    text = ("Take amoxicillin 500mg two times a day for ten days. Ibuprofen 200 milligrams every 6 hours "
            "if needed. Your fever was 101.8 degrees. We will check again in 48 hours.")
    assert _nums(text) == []


def test_invented_numbers_are_flagged():
    assert _nums("Take ibuprofen every 6 to 8 hours.") == ["8 hour"]
    assert _nums("Take amoxicillin 250 mg for 14 days.") == ["250 mg", "14 day"]


def test_counting_words_list_markers_and_911_are_ignored():
    text = "One of your medicines is amoxicillin.\n1. Take it with food.\n2. Call 911 if you cannot breathe."
    assert _nums(text) == []
    assert _nums("Take three tablets.") == ["3 tablet"]  # number word attached to a unit is checked


def test_medication_mentions_and_support():
    text = "Keep taking amoxicillin. Tylenol 325 mg helps. Do not start azithromycin or Zorblax 10 mg."
    mentions = medication_mentions(text)
    assert {"amoxicillin", "tylenol", "azithromycin", "zorblax"} <= set(mentions)
    res = unsupported_meds(text, SOURCE + "Acetaminophen 325 mg if needed.", ENTS)
    assert set(res["unsupported"]) == {"azithromycin", "zorblax"}  # Tylenol maps to acetaminophen


def test_common_words_are_not_medications():
    assert medication_mentions("In April we checked your cholesterol. The problem is getting better.") == []


def test_metrics_in_evaluate_record(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t1")
    record["patient_summary"] += "\nAlso take metoprolol 25 mg every 3 hours."
    row = evaluate_record(record)
    assert row["patient_summary_unsupported_meds"] == 1 and "metoprolol" in row["patient_summary_unsupported_meds_list"]
    assert row["patient_summary_unsupported_numbers"] == 2  # 25 mg, 3 hour
    assert 0 < row["patient_summary_unsupported_numbers_rate"] <= 1
    assert row["caregiver_checklist_unsupported_numbers"] == 0
    assert row["child_explanation_unsupported_numbers"] == 0
    assert math.isnan(row["child_explanation_unsupported_numbers_rate"])  # mock child text has no numbers


# --------------------------------------------------------------------------- repetition


def test_repeated_units_flags_synthetic_repeated_bullet():
    checklist = "\n".join([
        "Give amoxicillin 500 mg twice a day for 10 days.",
        "Watch for nausea and take ondansetron 4 mg every 8 hours as needed.",
        "Call the care team if the fever returns.",
        "Watch for signs of nausea and take ondansetron 4 mg every 8 hours as needed.",   # near-duplicate
        "give AMOXICILLIN 500 mg   twice a day for 10 days",                             # exact, other case/spacing
    ])
    repeats = repeated_units(checklist, "caregiver_checklist")
    assert [(r["index"], r["earlier_index"]) for r in repeats] == [(3, 1), (4, 0)]
    assert repeats[1]["overlap"] == 1.0 and 0.9 < repeats[0]["overlap"] < 1.0


def test_repetition_ignores_different_doses_and_short_sentences():
    from src.evaluator import repeated_units

    checklist = "- Give 500 mg metformin twice a day with meals.\n- Give 1000 mg metformin twice a day with meals."
    assert repeated_units(checklist, "caregiver_checklist") == []   # dose differs: overlap 0.875
    assert repeated_units("Rest now. Rest now. You will feel better soon.", "child_explanation") == []
    text = "You will take your medicine every day. It helps a lot. You will take your medicine every day."
    assert len(repeated_units(text, "patient_summary")) == 1


def test_repetition_ignores_parallel_sentences_about_different_facts():
    from src.evaluator import repeated_units

    for a, b in [
        ("You'll take it twice a day, the same as the other medicines.",
         "You'll take it once a day, the same as the other medicines."),
        ("Each time, you will take 2 puffs of the medicine, and each puff contains 90 mcg of the medicine.",
         "Each time, you will take 2 puffs of the medicine, and each puff contains 44 mcg of the medicine."),
    ]:
        assert repeated_units(f"{a} {b}", "patient_summary") == [], (a, b)
    same = "Take it with food if your tummy hurts. Rest. Take it with food if your tummy hurts."
    assert len(repeated_units(same, "patient_summary")) == 1


def test_repetition_metric_in_evaluate_record(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t")
    record["caregiver_checklist"] = record["caregiver_checklist"] + [record["caregiver_checklist"][0]]
    row = evaluate_record(record)
    assert row["caregiver_checklist_repetition"] == 1.0 and row["patient_summary_repetition"] == 0.0


# --------------------------------------------------------------------------- truncation & child rules


def test_truncation_rate_metric(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t")
    record["metadata"]["truncated"]["patient_summary"] = True
    row = evaluate_record(record)
    assert row["patient_summary_truncation_rate"] == 1.0 and row["caregiver_checklist_truncation_rate"] == 0.0


def test_old_outputs_without_flags_give_nan(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t")
    del record["metadata"]["truncated"]
    assert pd.isna(evaluate_record(record)["patient_summary_truncation_rate"])


def test_child_rule_checks():
    good = child_rule_checks("You feel sick. Medicine helps you. It is like tiny helpers. Rest a few days.")
    assert good == {"long_sentence_rate": 0.0, "med_names": 0.0, "numbers": 0.0}
    bad = child_rule_checks("You will take amoxicillin 500 mg two times every single day for ten whole days. Rest.")
    assert bad["long_sentence_rate"] == 0.5 and bad["med_names"] == 1.0 and bad["numbers"] >= 2
