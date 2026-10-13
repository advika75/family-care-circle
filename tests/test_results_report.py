"""Tests for src/results_report.py: report-ready tables and figures from existing result files."""

from __future__ import annotations

import math

import pandas as pd

from src.results_report import (
    ablations_synthetic_table,
    entity_retention_figure,
    fallback_rate_figure,
    fkgl_vs_child_target_figure,
    mtsamples_generation_table,
    mtsamples_ner_status,
    ner_table_for,
    not_available_markdown,
    not_available_table,
    write_table,
)


def test_not_available_table_and_markdown_name_the_reason():
    df = not_available_table("results/mtsamples/metrics.csv not found.")
    assert df.iloc[0]["status"] == "not available" and "not found" in df.iloc[0]["reason"]
    md = not_available_markdown("MTSamples generation metrics", "results/mtsamples/metrics.csv not found.")
    assert md.startswith("**MTSamples generation metrics: not available.**") and "not found" in md


def test_write_table_produces_csv_md_and_tex(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    write_table(tmp_path, "demo", df, "| a | b |\n|---|---|\n| 1 | x |")
    assert (tmp_path / "demo.csv").exists() and (tmp_path / "demo.md").exists() and (tmp_path / "demo.tex").exists()
    assert "a,b" in (tmp_path / "demo.csv").read_text()
    assert "\\begin{tabular}" in (tmp_path / "demo.tex").read_text()


def _ablation_summary():
    return pd.DataFrame([
        {"ablation": "baseline", "status": "ok", "n_notes": 12, "n_seeds": 3,
         "fkgl_delta_patient_summary": -2.69, "fkgl_delta_child_explanation": -4.89,
         "retention_patient_overall": 0.963, "retention_caregiver_overall": 0.998,
         "retention_patient_first_attempt": 0.81, "unsupported_numbers_patient_summary": 0.14,
         "fallback_rate": 0.13, "fallback_rate_std": 0.07, "truncation_rate_patient_summary": 0.0,
         "json_validity_rate": 1.0, "mean_retries": 2.14, "mean_latency_sec": 98.6,
         "retention_patient_overall_std": 0.019, "retention_caregiver_overall_std": 0.004},
        {"ablation": "no_ner_injection", "status": "ok", "n_notes": 12, "n_seeds": 3,
         "fkgl_delta_patient_summary": -2.58, "fkgl_delta_child_explanation": -4.99,
         "retention_patient_overall": 0.883, "retention_caregiver_overall": 0.910,
         "retention_patient_first_attempt": 0.693, "unsupported_numbers_patient_summary": 0.28,
         "fallback_rate": 0.306, "fallback_rate_std": 0.056, "truncation_rate_patient_summary": 0.028,
         "json_validity_rate": 1.0, "mean_retries": 3.42, "mean_latency_sec": 86.1,
         "retention_patient_overall_std": 0.023, "retention_caregiver_overall_std": 0.028},
    ])


def test_ablations_synthetic_table_states_dataset_and_n_notes():
    df, md = ablations_synthetic_table(_ablation_summary())
    assert (df["dataset"] == "Synthetic (12 notes x 3 seeds)").all()
    assert "synthetic, 12 notes x 3 seeds" in md
    assert "baseline" in md and "no_ner_injection" in md


def _mtsamples_metrics(n=3):
    rows = []
    for i in range(n):
        rows.append({
            "id": f"note_{i}", "backend": "llama_cpp", "source_fkgl": 9.0, "source_fre": 45.0,
            "patient_summary_fkgl": 5.0, "patient_summary_fre": 80.0, "patient_summary_rouge1": 0.25,
            "patient_summary_rougeL": 0.14, "caregiver_checklist_fkgl": 8.0, "caregiver_checklist_fre": 59.0,
            "caregiver_checklist_rouge1": 0.2, "caregiver_checklist_rougeL": 0.11, "child_explanation_fkgl": 2.8,
            "child_explanation_fre": 92.0, "child_explanation_rouge1": 0.1, "child_explanation_rougeL": 0.07,
        })
    return pd.DataFrame(rows)


def test_mtsamples_generation_table_states_dataset_and_note_count():
    df, md = mtsamples_generation_table(_mtsamples_metrics(n=5))
    assert (df["dataset"] == "MTSamples (5 real clinical notes)").all()
    assert "MTSamples, 5 real clinical notes" in md and "llama_cpp" in md
    assert len(df) == 4  # source + 3 personas


def test_ner_table_for_labels_dataset():
    ner = pd.DataFrame([{"label": "MEDICATION", "mode": "exact", "precision": 1.0, "recall": 1.0, "f1": 1.0,
                         "n_docs": 6}])
    df, md = ner_table_for(ner, "Synthetic (6 hand-annotated notes)")
    assert (df["dataset"] == "Synthetic (6 hand-annotated notes)").all()
    assert "Synthetic (6 hand-annotated notes)" in md


def test_mtsamples_ner_status_not_available_when_zero_evaluated():
    result = mtsamples_ner_status({"evaluated_note_count": 0, "skipped_note_count": 30})
    assert result is not None
    df, md = result
    assert df.iloc[0]["status"] == "not available" and "30" in df.iloc[0]["reason"]
    assert "complete" in md


def test_mtsamples_ner_status_none_when_notes_evaluated():
    assert mtsamples_ner_status({"evaluated_note_count": 5, "skipped_note_count": 25}) is None


def test_entity_retention_figure_writes_a_file(tmp_path):
    out = tmp_path / "retention.png"
    entity_retention_figure(_ablation_summary(), out)
    assert out.stat().st_size > 1000


def test_fallback_rate_figure_writes_a_file(tmp_path):
    out = tmp_path / "fallback.png"
    fallback_rate_figure(_ablation_summary(), out)
    assert out.stat().st_size > 1000


def test_fkgl_vs_child_target_figure_handles_both_one_and_no_datasets(tmp_path):
    synthetic = _mtsamples_metrics(n=3)
    mtsamples = _mtsamples_metrics(n=5)
    both = tmp_path / "both.png"
    fkgl_vs_child_target_figure(synthetic, mtsamples, both)
    assert both.stat().st_size > 1000

    one = tmp_path / "one.png"
    fkgl_vs_child_target_figure(synthetic, None, one)
    assert one.stat().st_size > 1000

    none = tmp_path / "none.png"
    fkgl_vs_child_target_figure(None, None, none)
    assert none.stat().st_size > 1000
