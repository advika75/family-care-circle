import json

import pytest

from scripts import evaluate_mtsamples_ner
from src.public_ner_evaluation import evaluate_mtsamples, write_results


def setup_data(tmp_path, monkeypatch, status="complete", entities=None, predicted=None):
    gold = tmp_path / "gold"
    notes = tmp_path / "notes"
    gold.mkdir()
    notes.mkdir()
    note_id = "mtsamples_test"
    text = "aspirin pain"
    (notes / f"{note_id}.txt").write_text(text, encoding="utf-8")
    annotation = {"id": note_id, "entities": entities if entities is not None else [
        {"text": "aspirin", "label": "MEDICATION", "start": 0, "end": 7}
    ]}
    (gold / f"{note_id}.json").write_text(json.dumps(annotation), encoding="utf-8")
    (gold / "annotation_manifest.json").write_text(json.dumps({"annotations": [
        {"id": note_id, "source_file": f"{note_id}.txt", "status": status}
    ]}), encoding="utf-8")
    if predicted is not None:
        monkeypatch.setattr("src.public_ner_evaluation.extract_rule_based", lambda text: predicted)
    return gold, notes, note_id


def test_exact_span_label_match(monkeypatch, tmp_path):
    entity = {"text": "aspirin", "label": "MEDICATION", "start": 0, "end": 7}
    gold, notes, _ = setup_data(tmp_path, monkeypatch, predicted=[entity])
    summary, metrics, errors = evaluate_mtsamples(gold, notes)
    assert summary["metrics"]["MICRO"]["tp"] == 1
    assert summary["metrics"]["MICRO"]["fp"] == summary["metrics"]["MICRO"]["fn"] == 0
    assert errors.empty
    assert set(metrics.label) >= {"MEDICATION", "SYMPTOM", "MICRO"}


def test_summary_reports_accepted_suggestion_share_and_unknown_provenance(tmp_path):
    gold, notes, note_id = setup_data(tmp_path, None, entities=[
        {"text": "aspirin", "label": "MEDICATION", "start": 0, "end": 7,
         "annotation_source": "accepted_suggestion"},
        {"text": "pain", "label": "SYMPTOM", "start": 8, "end": 12},
    ])
    summary, _, _ = evaluate_mtsamples(gold, notes)
    assert summary["accepted_suggestion_count"] == 1
    assert summary["gold_entities_with_known_provenance"] == 1
    assert summary["gold_entities_with_unknown_provenance"] == 1
    assert summary["accepted_suggestion_share"] == 1.0


def test_zero_complete_notes_has_unavailable_provenance_share(tmp_path):
    gold, notes, _ = setup_data(tmp_path, None, status="pending")
    summary, _, _ = evaluate_mtsamples(gold, notes)
    assert summary["accepted_suggestion_share"] is None


def test_write_results_refuses_existing_results_directory(tmp_path):
    gold, notes, _ = setup_data(tmp_path, None)
    summary, metrics, errors = evaluate_mtsamples(gold, notes)
    out = tmp_path / "results"
    write_results(summary, metrics, errors, out)
    with pytest.raises(FileExistsError, match="Refusing to write"):
        write_results(summary, metrics, errors, out)


@pytest.mark.parametrize("pred", [
    {"text": "aspirin", "label": "SYMPTOM", "start": 0, "end": 7},
    {"text": "spirin ", "label": "MEDICATION", "start": 1, "end": 8},
])
def test_wrong_label_or_offsets_are_fp_and_fn(monkeypatch, tmp_path, pred):
    gold, notes, _ = setup_data(tmp_path, monkeypatch, predicted=[pred])
    summary, _, errors = evaluate_mtsamples(gold, notes)
    assert summary["metrics"]["MICRO"]["tp"] == 0
    assert summary["metrics"]["MICRO"]["fp"] == summary["metrics"]["MICRO"]["fn"] == 1
    assert set(errors.error_type) == {"FP", "FN"}


def test_per_label_counts_and_metrics(monkeypatch, tmp_path):
    pred = [{"text": "pain", "label": "SYMPTOM", "start": 8, "end": 12}]
    gold, notes, _ = setup_data(tmp_path, monkeypatch, predicted=pred)
    summary, metrics, _ = evaluate_mtsamples(gold, notes)
    assert summary["metrics"]["MEDICATION"]["fn"] == 1
    assert summary["metrics"]["SYMPTOM"]["fp"] == 1
    assert set(metrics.label) == {"MEDICATION", "DOSAGE", "FREQUENCY", "DURATION", "CONDITION", "SYMPTOM", "MICRO"}


@pytest.mark.parametrize("status", ["pending", "in_progress"])
def test_unfinished_notes_are_skipped(monkeypatch, tmp_path, status):
    gold, notes, _ = setup_data(tmp_path, monkeypatch, status=status)
    summary, _, _ = evaluate_mtsamples(gold, notes)
    assert summary["evaluated_note_count"] == 0
    assert summary["skipped_note_count"] == 1
    assert summary["metrics"]["MICRO"]["f1"] is None


def test_malformed_completed_annotation_has_clear_error(monkeypatch, tmp_path):
    gold, notes, note_id = setup_data(tmp_path, monkeypatch)
    (gold / f"{note_id}.json").write_text('{"id":')
    with pytest.raises(ValueError, match="Completed note .*invalid or missing"):
        evaluate_mtsamples(gold, notes)


def test_duplicate_completed_gold_entities_are_rejected(monkeypatch, tmp_path):
    entity = {"text": "aspirin", "label": "MEDICATION", "start": 0, "end": 7}
    gold, notes, _ = setup_data(tmp_path, monkeypatch, entities=[entity, dict(entity)])
    with pytest.raises(ValueError, match="duplicate gold entity"):
        evaluate_mtsamples(gold, notes)


def test_zero_completed_notes_and_result_files(monkeypatch, tmp_path):
    gold, notes, _ = setup_data(tmp_path, monkeypatch, status="pending")
    summary, metrics, errors = evaluate_mtsamples(gold, notes)
    out = tmp_path / "results"
    write_results(summary, metrics, errors, out)
    assert summary["metrics"]["MICRO"]["precision"] is None
    assert (out / "mtsamples_ner_summary.json").is_file()
    assert (out / "mtsamples_ner_metrics.csv").is_file()
    assert (out / "mtsamples_ner_errors.csv").is_file()
    assert "No completed" not in (out / "mtsamples_ner_summary.json").read_text()


def test_cli_prints_message_when_no_annotations_are_complete(monkeypatch, tmp_path, capsys):
    gold, notes, _ = setup_data(tmp_path, monkeypatch, status="in_progress")
    monkeypatch.setattr("sys.argv", ["evaluate_mtsamples_ner.py", "--gold-dir", str(gold),
                                      "--notes-dir", str(notes), "--results-dir", str(tmp_path / "out")])
    assert evaluate_mtsamples_ner.main() == 0
    assert "No completed gold annotations; metrics unavailable." in capsys.readouterr().out
