"""Tests for src/error_analysis.py on mock outputs."""

from __future__ import annotations

import copy

from src.error_analysis import CATEGORIES, analyze, excerpt, source_line, to_markdown
from src.pipeline import FamilyCarePipeline


def test_clean_baseline_has_no_content_failures(mock_records):
    result = analyze(mock_records["baseline"], max_child_grade=10)
    assert result["n_records"] == 3
    for cat in ("missing_entity", "fallback_used", "unsupported_content", "child_reading_level"):
        assert result["counts"][cat] == 0, cat


def test_no_injection_triggers_fallback_and_retries(mock_records):
    result = analyze(mock_records["no_injection"])
    assert result["counts"]["fallback_used"] == 6          # patient + caregiver on 3 notes
    assert result["counts"]["format_or_retries"] >= 6      # retries used up
    ex = result["examples"]["fallback_used"][0]
    assert ex["id"] == "note_01" and "omitted" in ex["problem"]
    assert "Important details" in ex["output_excerpt"] or "Confirm with the care team" in ex["output_excerpt"]


def test_detects_each_category(mock_records):
    rec = copy.deepcopy(mock_records["baseline"][0])
    rec["patient_summary"] = "Take amoxicillin 750 mg twice a day."          # missing + unsupported + short
    rec["caregiver_checklist"] = []
    rec["metadata"]["valid"] = False
    rec["metadata"]["validation_errors"] = ["caregiver_checklist must be a non-empty list"]
    rec["child_explanation"] = ("Pharmacological antimicrobial intervention necessitates meticulous adherence "
                                "to the prescribed administration schedule.")
    result = analyze([rec], max_child_grade=3, min_words=20)
    for cat in ("missing_entity", "unsupported_content", "child_reading_level", "empty_or_short", "format_or_retries"):
        assert result["counts"][cat] >= 1, cat
    unsupported = [f for f in result["failures"] if f["category"] == "unsupported_content"]
    assert "750 mg" in unsupported[0]["problem"] and "750" in unsupported[0]["output_excerpt"]
    missing = [f for f in result["failures"] if f["category"] == "missing_entity"][0]
    assert "10 days" in missing["problem"] and "Amoxicillin" in missing["source_excerpt"]


def test_examples_are_capped_and_prefer_distinct_notes(mock_records):
    result = analyze(mock_records["no_injection"], max_examples=2)
    examples = result["examples"]["fallback_used"]
    assert len(examples) == 2 and examples[0]["id"] != examples[1]["id"]


def test_markdown_and_excerpts(mock_records):
    result = analyze(mock_records["no_injection"])
    md = to_markdown(result, "data/outputs_x")
    assert md.startswith("# Error analysis") and "mock" in md
    for cat in CATEGORIES:
        assert f"## {cat} (" in md
    assert len(excerpt("word " * 200)) <= 225
    assert source_line("line one\nNo lifting for 2 weeks.\n2. other", "2 weeks") == "No lifting for 2 weeks."


def test_repetition_detects_repeated_bullet(mock_records):
    from src.evaluator import evaluate_record, repeated_units

    rec = copy.deepcopy(mock_records["baseline"][0])
    rec["caregiver_checklist"] = [
        "Give amoxicillin 500 mg twice a day for 10 days.",
        "Watch for nausea and take ondansetron 4 mg every 8 hours as needed.",
        "Call the care team if the fever returns.",
        "Watch for signs of nausea and take ondansetron 4 mg every 8 hours as needed.",   # near-duplicate
        "give AMOXICILLIN 500 mg   twice a day for 10 days",                             # exact, other case/spacing
    ]
    repeats = repeated_units("\n".join(rec["caregiver_checklist"]), "caregiver_checklist")
    assert [(r["index"], r["earlier_index"]) for r in repeats] == [(3, 1), (4, 0)]
    assert repeats[1]["overlap"] == 1.0 and 0.9 < repeats[0]["overlap"] < 1.0

    result = analyze([rec])
    assert result["counts"]["repetition"] == 1                       # one output, counted once
    ex = result["examples"]["repetition"][0]
    assert ex["persona"] == "caregiver_checklist" and "2 repeated bullet(s)" in ex["problem"]
    assert "ondansetron" in ex["output_excerpt"].lower()
    row = evaluate_record(rec)
    assert row["caregiver_checklist_repetition"] == 1.0 and row["patient_summary_repetition"] == 0.0


def test_truncated_category(sample_note, mock_config):
    cfg = copy.deepcopy(mock_config)
    cfg["personas"]["patient_summary"]["max_new_tokens"] = 10
    record = FamilyCarePipeline(cfg).run(sample_note, "t")
    trunc = [f for f in analyze([record])["failures"] if f["category"] == "truncated"]
    assert len(trunc) == 1 and trunc[0]["persona"] == "patient_summary"
    assert "max_new_tokens (10)" in trunc[0]["problem"]
