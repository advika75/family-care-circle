import csv
import json

import pytest

from scripts.audit_mtsamples import (
    RETENTION_CATEGORIES,
    generate,
    regimen_candidates,
    score_unsupported,
    stratified_sample,
)


def test_stratified_sample_is_seeded_and_covers_persona_label_strata():
    rows = [{"persona": persona, "label": label, "note_id": f"{i:03}",
             "entity": str(i), "first_attempt_missing_entity": str(i)}
            for persona in ("patient_summary", "caregiver_checklist")
            for label in ("DOSAGE", "FREQUENCY") for i in range(30)]
    a = stratified_sample(rows, 40, 42)
    assert a == stratified_sample(rows, 40, 42)
    assert len(a) == 40
    assert {(r["persona"], r["label"]) for r in a} == {
        ("patient_summary", "DOSAGE"), ("patient_summary", "FREQUENCY"),
        ("caregiver_checklist", "DOSAGE"), ("caregiver_checklist", "FREQUENCY"),
    }


def test_regimen_candidates_are_only_unmatched_candidate_forms():
    record = {"id": "note-1", "source_text": "Take one milligram every four hours for several weeks."}
    rows = regimen_candidates([record])
    forms = {row["candidate_form"].lower() for row in rows}
    assert "one milligram" in forms
    assert "every four hours" in forms
    assert "for several weeks" in forms
    assert all(row["interpretation"].endswith("not recall") for row in rows)


def test_generate_creates_blank_review_audits_and_refuses_overwrite(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    record = {
        "id": "n1", "source_text": "Take aspirin 5 mg daily.",
        "patient_summary": "Take 77 mg daily.", "caregiver_checklist": ["Take aspirin daily."],
        "child_explanation": "Take aspirin daily.",
        "entities": [{"text": "aspirin", "label": "MEDICATION", "start": 5, "end": 12},
                     {"text": "5 mg", "label": "DOSAGE", "start": 13, "end": 17}],
        "metadata": {"missing_first_attempt": {"patient_summary": ["aspirin", "5 mg"],
                                                "caregiver_checklist": ["5 mg"]}},
    }
    (outputs / "n1.json").write_text(json.dumps(record), encoding="utf-8")
    audit = tmp_path / "audits"
    result = generate(outputs, audit, 42)
    assert result[:3] == (1, 3, 1)
    assert result[3] >= 0
    with (audit / "retention_audit.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3 and all(row["human_label"] == "" for row in rows)
    with (audit / "audit_category_counts.csv").open(encoding="utf-8", newline="") as stream:
        counts = list(csv.DictReader(stream))
    assert next(row for row in counts if row["kind"] == "retention" and
                row["category"] == "pending / blank")["count"] == "3"
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        generate(outputs, audit, 42)


def test_unsupported_number_precision_uses_only_filled_human_labels(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("human_label\ntrue fabrication\nequivalent\n\n", encoding="utf-8")
    tp, n, precision = score_unsupported(path)
    assert (tp, n, precision) == (1, 2, 0.5)
    path.write_text("human_label\n\n", encoding="utf-8")
    assert score_unsupported(path) == (0, 0, None)


def test_retention_categories_are_explicit():
    assert RETENTION_CATEGORIES == ("true omission", "matcher failure", "extraction error", "unclear")
