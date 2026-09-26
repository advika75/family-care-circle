"""Tests for src/report_tables.py and the table-building script."""

from __future__ import annotations

import pandas as pd

from src.ablations import summarize_ablations
from src.evaluator import evaluate_record
from src.report_tables import (
    ablation_table,
    fill_marker,
    main_results_table,
    ner_table,
    retention_table,
)


def _metrics(records):
    return pd.DataFrame([evaluate_record(r) for r in records])


def test_main_and_retention_tables(mock_records):
    metrics = _metrics(mock_records["baseline"])
    main = main_results_table(metrics, mock=True)
    assert main.startswith("> ⚠️ **Mock data**")
    assert "| Source note |" in main and "| Child |" in main and " ± " in main
    ret = retention_table(metrics)
    assert "| Patient | 100.0% |" in ret and "Final (with fallback)" in ret


def test_ablation_table_shows_differences_from_baseline():
    summary = pd.DataFrame([
        {"ablation": "baseline", "n_notes": 12, "retention_patient_overall": 0.90, "mean_retries": 1.0},
        {"ablation": "no_retry", "n_notes": 12, "retention_patient_overall": 0.80, "mean_retries": 0.0},
        {"ablation": "model_1.5b", "status": "failed"},
    ])
    table = ablation_table(summary)
    assert "| **baseline** |" in table
    assert "80.0% (-10.0 pp)" in table and "0.00 (-1.00)" in table
    assert "model_1.5b (failed)" in table


def test_ner_table_orders_micro_last():
    ner = pd.DataFrame([
        {"mode": m, "label": lbl, "precision": 0.9, "recall": 0.8, "f1": 0.85, "n_docs": 6}
        for m in ("exact", "relaxed") for lbl in ("MICRO", "DOSAGE")
    ])
    table = ner_table(ner)
    lines = [l for l in table.splitlines() if l.startswith("| ")]
    assert lines[1].startswith("| DOSAGE") and lines[2].startswith("| **MICRO**")


def test_fill_marker_is_idempotent():
    report = "intro\n<!-- TABLE:main -->\nplaceholder\n<!-- /TABLE:main -->\nend\n"
    once, found = fill_marker(report, "main", "| a |\n|---|")
    twice, _ = fill_marker(once, "main", "| a |\n|---|")
    assert found and once == twice and "placeholder" not in once and once.count("| a |") == 1
    updated, _ = fill_marker(twice, "main", "| b |")
    assert "| b |" in updated and "| a |" not in updated
    assert fill_marker(report, "missing", "x") == (report, False)


def test_report_has_all_markers():
    from src.report_tables import TABLE_NAMES
    text = open("report/project_report.md", encoding="utf-8").read()
    for name in TABLE_NAMES:
        assert f"<!-- TABLE:{name} -->" in text and f"<!-- /TABLE:{name} -->" in text


def test_ablation_table_mean_std_and_fallback_rate():
    summary = pd.DataFrame([
        {"ablation": "baseline", "n_notes": 12, "n_seeds": 3, "retention_patient_overall": 0.90,
         "retention_patient_overall_std": 0.02, "fallback_rate": 0.20, "fallback_rate_std": 0.05},
        {"ablation": "child_v1", "n_notes": 12, "n_seeds": 3, "retention_patient_overall": 0.88,
         "retention_patient_overall_std": 0.01, "fallback_rate": 0.25, "fallback_rate_std": 0.0},
    ])
    table = ablation_table(summary)
    assert "Fallback rate" in table and "90.0% ± 2.0" in table and "20.0% ± 5.0" in table
    assert "88.0% ± 1.0 (-2.0 pp)" in table and "across 3 seeds" in table
    single = ablation_table(summary.assign(n_seeds=1))
    assert " ± " not in single.split("\n\n")[0] and "single seed" in single


def test_report_tables_pool_baseline_seeds(seeded_runs, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("brt", "scripts/build_report_tables.py")
    brt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brt)
    from src.report_tables import main_results_table
    summary, _ = summarize_ablations(seeded_runs, mock=True, seeds=[0, 1])
    root = tmp_path / "results/ablations_mock"
    dirs = brt.baseline_run_dirs(root / "baseline", summary, "baseline")
    assert [d.name for d in dirs] == ["seed0", "seed1"]
    assert brt.baseline_run_dirs(root / "baseline", None, "baseline") == []     # no single-seed run exists
    metrics = pd.concat([pd.read_csv(d / "metrics.csv") for d in dirs])
    assert "4 outputs (2 notes × 2 seeds)" in main_results_table(metrics, pooled="2 notes × 2 seeds")
