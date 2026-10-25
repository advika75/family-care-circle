import json

import pandas as pd
import pytest

from scripts.compare_paired_mtsamples import compare_runs, validate_pair
from src.ablations import ablation_dirs, ablations_root, build_ablation_config


def _run(results_dir, inject, ids, metrics, model_hashes=None):
    results_dir.mkdir()
    pd.DataFrame(metrics).to_csv(results_dir / "metrics.csv", index=False)
    config = {"dataset": "mtsamples", "backend": "llama_cpp", "model": "model.gguf",
              "generation_seed": 42, "child_variant": "v2",
              "effective_config": {"prompts": {"inject_entities": inject}, "max_retries": 2},
              "source_note_ids": ids, "model_hashes": model_hashes or ["sha256:model"]}
    (results_dir / "run_info.json").write_text(json.dumps(config), encoding="utf-8")


def test_paired_analysis_reports_paired_differences_mcnemar_and_missing_ids(tmp_path):
    baseline_dir, no_injection_dir = tmp_path / "baseline", tmp_path / "no_injection"
    expected = ["n1", "n2", "n3", "n4"]
    _run(baseline_dir, True, expected, [
        {"id": "n1", "patient_summary_retention_first": 0.5,
         "patient_summary_retention_first_evidence_available": 1, "valid": True,
         "patient_summary_fallback": 0, "patient_summary_unsupported_numbers": 0},
        {"id": "n2", "patient_summary_retention_first": 0.8,
         "patient_summary_retention_first_evidence_available": 1, "valid": True,
         "patient_summary_fallback": 1, "patient_summary_unsupported_numbers": 1},
        {"id": "n3", "patient_summary_retention_first": 0.7,
         "patient_summary_retention_first_evidence_available": 0, "valid": True,
         "patient_summary_fallback": 0, "patient_summary_unsupported_numbers": 0},
    ])
    _run(no_injection_dir, False, expected, [
        {"id": "n2", "patient_summary_retention_first": 0.6,
         "patient_summary_retention_first_evidence_available": 1, "valid": True,
         "patient_summary_fallback": 0, "patient_summary_unsupported_numbers": 0},
        {"id": "n3", "patient_summary_retention_first": 0.4,
         "patient_summary_retention_first_evidence_available": 1, "valid": False,
         "patient_summary_fallback": 1, "patient_summary_unsupported_numbers": 1},
        {"id": "n4", "patient_summary_retention_first": 0.4,
         "patient_summary_retention_first_evidence_available": 1, "valid": False,
         "patient_summary_fallback": 1, "patient_summary_unsupported_numbers": 1},
    ])

    out_dir = tmp_path / "analysis"
    summary = compare_runs(baseline_dir, no_injection_dir, out_dir, bootstrap_samples=100, seed=3)
    retention = summary.set_index("metric").loc["patient_summary_retention_first"]
    fallback = summary.set_index("metric").loc["patient_summary_fallback"]
    assert retention["n_paired"] == 1
    assert retention["n_missing_first_attempt_evidence"] == 1
    assert retention["mean_difference_no_injection_minus_baseline"] == pytest.approx(-0.2)
    assert retention["paired_test"] == "exact sign test"
    assert fallback["baseline_only"] == 1 and fallback["no_injection_only"] == 1
    assert fallback["paired_test"] == "exact McNemar"
    missing = pd.read_csv(out_dir / "unpaired_ids.csv").set_index("id")
    assert set(missing.index) == {"n1", "n4"}
    assert (out_dir / "paired_metrics.csv").is_file()
    assert "not a clinical safety assessment" in (out_dir / "summary.md").read_text()
    before = (out_dir / "paired_metrics.csv").read_bytes()
    with pytest.raises(FileExistsError, match="Refusing to replace existing paired analysis directory"):
        compare_runs(baseline_dir, no_injection_dir, out_dir, bootstrap_samples=100, seed=3)
    assert (out_dir / "paired_metrics.csv").read_bytes() == before


def test_paired_analysis_does_not_trust_legacy_first_retention_without_evidence(tmp_path):
    baseline_dir, no_injection_dir = tmp_path / "baseline", tmp_path / "no_injection"
    _run(baseline_dir, True, ["n1"], [{"id": "n1", "patient_summary_retention_first": 0.9}])
    _run(no_injection_dir, False, ["n1"], [{"id": "n1", "patient_summary_retention_first": 0.2}])
    summary = compare_runs(baseline_dir, no_injection_dir, tmp_path / "analysis", bootstrap_samples=10)
    first = summary.set_index("metric").loc["patient_summary_retention_first"]
    assert first["n_paired"] == 0
    assert first["n_missing_first_attempt_evidence"] == 1
    assert first["n_inapplicable_retention"] == 0


def test_first_retention_counts_captured_but_inapplicable_notes_separately(tmp_path):
    baseline_dir, no_injection_dir = tmp_path / "baseline", tmp_path / "no_injection"
    ids = ["eligible", "inapplicable"]
    _run(baseline_dir, True, ids, [
        {"id": "eligible", "patient_summary_retention_first": 0.5,
         "patient_summary_retention_first_evidence_available": 1},
        {"id": "inapplicable", "patient_summary_retention_first": float("nan"),
         "patient_summary_retention_first_evidence_available": 1},
    ])
    _run(no_injection_dir, False, ids, [
        {"id": "eligible", "patient_summary_retention_first": 0.7,
         "patient_summary_retention_first_evidence_available": 1},
        {"id": "inapplicable", "patient_summary_retention_first": float("nan"),
         "patient_summary_retention_first_evidence_available": 1},
    ])
    summary = compare_runs(baseline_dir, no_injection_dir, tmp_path / "analysis", bootstrap_samples=10)
    first = summary.set_index("metric").loc["patient_summary_retention_first"]
    assert first["n_paired"] == 1
    assert first["n_missing_first_attempt_evidence"] == 0
    assert first["n_inapplicable_retention"] == 1


def test_rouge_comparison_pairs_by_note_id_and_reports_ci(tmp_path):
    baseline_dir, no_injection_dir = tmp_path / "baseline", tmp_path / "no_injection"
    expected = ["n1", "n2", "n3", "n4"]
    _run(baseline_dir, True, expected, [
        {"id": "n1", "patient_summary_rouge1": 0.1, "patient_summary_rougeL": 0.2},
        {"id": "n2", "patient_summary_rouge1": 0.4, "patient_summary_rougeL": 0.5},
        {"id": "n3", "patient_summary_rouge1": 0.8, "patient_summary_rougeL": 0.7},
    ])
    _run(no_injection_dir, False, expected, [
        {"id": "n2", "patient_summary_rouge1": 0.6, "patient_summary_rougeL": 0.7},
        {"id": "n4", "patient_summary_rouge1": 0.9, "patient_summary_rougeL": 0.9},
        {"id": "n1", "patient_summary_rouge1": 0.2, "patient_summary_rougeL": 0.4},
    ])
    summary = compare_runs(baseline_dir, no_injection_dir, tmp_path / "analysis", bootstrap_samples=100, seed=3)
    metrics = summary.set_index("metric")
    for name, expected_difference in (("patient_summary_rouge1", 0.15),
                                      ("patient_summary_rougeL", 0.2)):
        row = metrics.loc[name]
        assert row["n_paired"] == 2
        assert row["mean_difference_no_injection_minus_baseline"] == pytest.approx(expected_difference)
        assert row["bootstrap_95_ci_low"] <= expected_difference <= row["bootstrap_95_ci_high"]
        assert row["paired_test"] == "exact sign test"


def test_pair_validation_rejects_non_injection_configuration_differences():
    baseline, no_injection = _pair_info()
    baseline["effective_config"]["max_retries"] = 2
    no_injection["effective_config"]["max_retries"] = 0
    with pytest.raises(ValueError, match="differ beyond prompts.inject_entities"):
        validate_pair(baseline, no_injection)


def test_pair_validation_rejects_different_model_hashes():
    baseline, no_injection = _pair_info()
    baseline["model_hashes"] = ["sha256:a"]
    no_injection["model_hashes"] = ["sha256:b"]
    with pytest.raises(ValueError, match="different model hashes"):
        validate_pair(baseline, no_injection)


def test_pair_validation_rejects_non_mtsamples_runs():
    baseline, no_injection = _pair_info()
    baseline["dataset"] = "synthetic"
    no_injection["dataset"] = "synthetic"
    with pytest.raises(ValueError, match="Expected MTSamples"):
        validate_pair(baseline, no_injection)


def _pair_info():
    common = {"dataset": "mtsamples", "backend": "llama_cpp", "model": "model.gguf",
              "generation_seed": 42, "child_variant": "v2", "source_note_ids": ["n1"],
              "model_hashes": ["sha256:model"], "effective_config": {"prompts": {"inject_entities": True},
                                                                        "max_retries": 2}}
    baseline = json.loads(json.dumps(common))
    no_injection = json.loads(json.dumps(common))
    no_injection["effective_config"]["prompts"]["inject_entities"] = False
    return baseline, no_injection


def test_pair_validation_requires_recorded_parity_metadata():
    with pytest.raises(ValueError, match="run_info.json"):
        validate_pair(None, None)


def test_mtsamples_run_tag_paths_are_isolated_and_validated():
    baseline_out, baseline_results = ablation_dirs("baseline", dataset="mtsamples", run_tag="first_attempt_v1")
    inject_out, inject_results = ablation_dirs("no_ner_injection", dataset="mtsamples", run_tag="first_attempt_v1")
    assert baseline_out.name == "outputs_baseline_first_attempt_v1"
    assert inject_out.name == "outputs_no_injection_first_attempt_v1"
    assert baseline_results.name == "baseline_first_attempt_v1"
    assert inject_results.name == "no_injection_first_attempt_v1"
    assert ablations_root(dataset="mtsamples", run_tag="first_attempt_v1").name == "ablation_summary_first_attempt_v1"
    assert baseline_out != inject_out and baseline_results != inject_results
    with pytest.raises(ValueError, match="run tag"):
        ablation_dirs("baseline", dataset="mtsamples", run_tag="../existing")


def test_mtsamples_configs_differ_only_by_entity_injection():
    from src.utils import load_config

    base = load_config("config.yaml", {"dataset": "mtsamples"})
    baseline = build_ablation_config(base, base["ablations"]["baseline"])
    no_injection = build_ablation_config(base, base["ablations"]["no_ner_injection"])
    assert baseline["prompts"]["inject_entities"] is True
    assert no_injection["prompts"]["inject_entities"] is False
    from scripts.compare_paired_mtsamples import _without_injection
    assert _without_injection(baseline) == _without_injection(no_injection)
