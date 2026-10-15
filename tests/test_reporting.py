"""Tests for src/reporting.py: evaluating an outputs folder end to end."""

from __future__ import annotations

import pandas as pd
import pytest

from src.ner import extract_entities
from src.reporting import evaluate_outputs, load_records, markdown_table
from src.utils import write_json


@pytest.fixture
def outputs_dir(tmp_path, mock_records):
    folder = tmp_path / "outputs"
    for record in mock_records["baseline"]:
        write_json(record, folder / f"{record['id']}.json")
    (folder / "broken.json").write_text("{not json")
    return folder


def test_load_records_counts_unparseable_files(outputs_dir):
    records, broken = load_records(outputs_dir)
    assert len(records) == 3 and broken == 1


def test_evaluate_outputs_writes_all_artifacts(outputs_dir, tmp_path):
    config = {"paths": {"gold_dir": "data/gold", "raw_dir": "data/raw"}}
    result = evaluate_outputs(outputs_dir, tmp_path / "res", config, extract_fn=extract_entities)
    for name in ("metrics.csv", "summary.csv", "summary.md", "ner_metrics.csv",
                 "figures/readability_before_after.png", "figures/entity_retention.png"):
        assert (tmp_path / "res" / name).exists(), name
    assert result["n_records"] == 3
    summary = pd.read_csv(tmp_path / "res" / "summary.csv", index_col="metric")
    assert summary.loc["json_parse_rate", "mean"] == pytest.approx(0.75)   # 3 of 4 files parsed
    for row in ("patient_summary_retention_first", "caregiver_checklist_repetition",
                "patient_summary_truncation_rate", "patient_summary_unsupported_numbers"):
        assert row in result["key"].index, row


def test_evaluate_outputs_without_ner_and_empty_folder(outputs_dir, tmp_path):
    assert evaluate_outputs(outputs_dir, tmp_path / "r", {})["ner"] is None
    with pytest.raises(FileNotFoundError):
        evaluate_outputs(tmp_path / "empty", tmp_path / "r2", {})


def test_evaluate_outputs_allows_public_set_without_gold(outputs_dir, tmp_path):
    raw_dir, gold_dir = tmp_path / "notes", tmp_path / "gold"
    raw_dir.mkdir()
    gold_dir.mkdir()
    config = {"dataset": "mtsamples", "datasets": {"mtsamples": {
        "raw_dir": str(raw_dir), "gold_dir": str(gold_dir)}}}
    result = evaluate_outputs(outputs_dir, tmp_path / "results", config, extract_fn=extract_entities)
    assert result["ner"] is None


def test_public_incomplete_gold_is_not_scored_and_results_stay_isolated(outputs_dir, tmp_path):
    raw_dir, gold_dir = tmp_path / "notes", tmp_path / "gold"
    raw_dir.mkdir()
    gold_dir.mkdir()
    (gold_dir / "annotation_manifest.json").write_text(
        '{"annotations":[{"id":"sample","source_file":"sample.txt","status":"pending"}]}',
        encoding="utf-8",
    )
    public_results = tmp_path / "results" / "mtsamples"
    config = {"dataset": "mtsamples", "datasets": {"mtsamples": {
        "raw_dir": str(raw_dir), "gold_dir": str(gold_dir), "results_dir": str(public_results)}}}
    result = evaluate_outputs(outputs_dir, public_results, config, extract_fn=extract_entities)
    assert result["ner"].empty
    assert (public_results / "metrics.csv").is_file()
    assert (public_results / "ner_metrics.csv").is_file()
    assert not (tmp_path / "results" / "metrics.csv").is_file()


def test_markdown_table():
    md = markdown_table(pd.DataFrame({"x": [1.23456]}, index=pd.Index(["a"], name="metric")))
    assert md.splitlines() == ["| metric | x |", "|---|---|", "| a | 1.235 |"]
