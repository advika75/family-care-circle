import csv
import json

import pytest

from scripts.audit_mtsamples import (
    MANUAL_JUDGMENTS,
    generate,
    regimen_candidates,
    safety_candidates,
    export_case_evidence,
    literal_spans,
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
    assert len(rows) == 3 and all(row["manual_judgment"] == "" for row in rows)
    assert all(row["source_ref"] and row["output_ref"] and row["detector_decision"] and row["reason"] == ""
               for row in rows)
    with (audit / "audit_category_counts.csv").open(encoding="utf-8", newline="") as stream:
        counts = list(csv.DictReader(stream))
    assert next(row for row in counts if row["kind"] == "retention" and
                row["category"] == "pending / blank")["count"] == "3"
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        generate(outputs, audit, 42)


def test_unsupported_number_precision_excludes_uncertain_rows(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("manual_judgment\ntrue_issue\nfalse_positive\nuncertain\n\n", encoding="utf-8")
    tp, fp, uncertain, reviewed, precision = score_unsupported(path)
    assert (tp, fp, uncertain, reviewed, precision) == (1, 1, 1, 3, pytest.approx(1 / 2))
    path.write_text("manual_judgment\n\n", encoding="utf-8")
    assert score_unsupported(path) == (0, 0, 0, 0, None)


def test_manual_judgments_are_explicit():
    assert MANUAL_JUDGMENTS == ("true_issue", "false_positive", "uncertain")


def test_literal_spans_report_exact_case_insensitive_offsets():
    assert literal_spans("Dose 10 MG, then 10 mg", "10 mg") == [
        {"start": 5, "end": 10, "text": "10 MG"},
        {"start": 17, "end": 22, "text": "10 mg"},
    ]


def test_case_evidence_export_preserves_labels_and_proposes_without_relabeling(tmp_path):
    import json

    audits, outputs = tmp_path / "audits", tmp_path / "outputs"
    audits.mkdir(); outputs.mkdir()
    (audits / "retention_audit.csv").write_text(
        "note_id,persona,label,entity,source_ref,output_ref,source_context,first_attempt_missing_entity,final_output,detector_decision,manual_judgment,reason\n"
        "n1,caregiver_checklist,DOSAGE,5 mg,s,o,5 mg source,5 mg,Keep 5 mg,missed,uncertain,\n", encoding="utf-8")
    (audits / "unsupported_numbers_sample.csv").write_text(
        "note_id,persona,flagged_item,source_ref,output_ref,source_context,output_context,detector_decision,manual_judgment,reason\n"
        "mtsamples_Weight_Gain_and_Edema,caregiver_checklist,10 mg,s,o,source,10 mg output,flagged,false_positive,old label\n", encoding="utf-8")
    (audits / "safety_audit.csv").write_text(
        "note_id,persona,flag_type,flagged_item,source_ref,output_ref,postfix_output_ref,detector_decision,manual_judgment,reason\n", encoding="utf-8")
    (outputs / "n1.json").write_text(json.dumps({
        "id": "n1", "source_text": "Medication 5 mg.",
        "caregiver_checklist": ["Keep 5 mg."], "entities": [], "metadata": {},
    }), encoding="utf-8")
    (outputs / "mtsamples_Weight_Gain_and_Edema.json").write_text(json.dumps({
        "id": "mtsamples_Weight_Gain_and_Edema", "source_text": "Lisinopril is on hold.",
        "caregiver_checklist": ["Medication: lisinopril | dose: 10 mg | how often: daily"],
        "entities": [], "metadata": {},
    }), encoding="utf-8")
    target = tmp_path / "evidence.csv"
    assert export_case_evidence(audits, outputs, target) == 2
    with target.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["existing_judgment"] == "uncertain"
    assert rows[0]["proposed_judgment"] == ""
    assert rows[0]["first_attempt_prose_available"] == "false"
    assert json.loads(rows[0]["source_entity_offsets"]) == [{"start": 11, "end": 15, "text": "5 mg"}]
    assert rows[1]["existing_judgment"] == "false_positive"
    assert rows[1]["proposed_judgment"] == "true_issue"
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        export_case_evidence(audits, outputs, target)


def test_safety_candidates_record_existing_flags_without_judging():
    before = {
        "id": "mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit",
        "source_text": "The note mentions Celesta 40 mg.",
        "entities": [],
        "caregiver_checklist": ["Give 20 mg of aspirin."],
    }
    after = {**before, "caregiver_checklist": ["Give 40 mg of Celesta."]}
    rows = safety_candidates([before], [after])
    assert {row["flag_type"] for row in rows} == {"unsupported medication", "contradicted directive dose"}
    assert all(row["manual_judgment"] == "" and row["reason"] == "" for row in rows)
    assert all(row["source_ref"] and row["output_ref"] and row["postfix_output_ref"] and row["detector_decision"]
               for row in rows)
    assert all("before: flagged" in row["detector_decision"] and "after: not flagged" in row["detector_decision"]
               for row in rows)
