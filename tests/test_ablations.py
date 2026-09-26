"""Tests for src/ablations.py (mock backend, temporary folders)."""

from __future__ import annotations

import pytest

import src.ablations as ab
from src.ablations import (
    GeneratorCache,
    ablation_dirs,
    build_ablation_config,
    fingerprint,
    fingerprint_state,
    pending_notes,
    run_ablation,
    set_by_path,
    shadowed_overrides,
    summarize_ablations,
)


@pytest.fixture
def base_config(mock_config):
    cfg = dict(mock_config)
    cfg["prompts"] = {"inject_entities": True}
    cfg["paths"] = {"raw_dir": "data/raw", "gold_dir": "data/gold"}
    cfg["ablations"] = {"baseline": {}}
    return cfg


def test_set_by_path_and_unknown_key(base_config):
    set_by_path(base_config, "generation.temperature", 0.7)
    assert base_config["generation"]["temperature"] == 0.7
    with pytest.raises(KeyError, match="generation.temprature"):
        set_by_path(base_config, "generation.temprature", 0.7)


def test_build_ablation_config_copies_and_forces_mock(base_config):
    cfg = build_ablation_config(base_config, {"max_retries": 0, "prompts.inject_entities": False},
                                backend="transformers", mock=True)
    assert cfg["backend"] == "mock" and cfg["max_retries"] == 0 and cfg["prompts"]["inject_entities"] is False
    assert base_config["max_retries"] == 2 and base_config["prompts"]["inject_entities"] is True
    assert "ablations" not in cfg


def test_fingerprint_ignores_paths(base_config):
    a = build_ablation_config(base_config, {})
    b = build_ablation_config(base_config, {})
    b["paths"] = {"raw_dir": "elsewhere"}
    assert fingerprint(a) == fingerprint(b)
    b["max_retries"] = 0
    assert fingerprint(a) != fingerprint(b)


@pytest.fixture
def notes(tmp_path, sample_note):
    folder = tmp_path / "raw"
    folder.mkdir()
    paths = []
    for i in (1, 2):
        p = folder / f"n{i}.txt"
        p.write_text(sample_note)
        paths.append(p)
    return paths


def test_run_ablation_resumes_and_detects_config_change(tmp_path, notes, base_config, monkeypatch):
    monkeypatch.setattr(ab, "evaluate_outputs", lambda *a, **k: None)  # evaluation is tested separately
    cfg = build_ablation_config(base_config, {}, mock=True)
    out, res = tmp_path / "out", tmp_path / "res"

    info = run_ablation("baseline", cfg, {}, notes, out, res, GeneratorCache())
    assert info["status"] == "ok" and info["notes_generated"] == 2
    assert pending_notes(notes, out) == [] and fingerprint_state(out, fingerprint(cfg)) == "match"

    (out / "n2.json").unlink()  # simulate an interrupted run
    info = run_ablation("baseline", cfg, {}, notes, out, res, GeneratorCache())
    assert info["notes_generated"] == 1 and info["notes_skipped"] == 1

    changed = build_ablation_config(base_config, {"max_retries": 0}, mock=True)
    assert fingerprint_state(out, fingerprint(changed)) == "mismatch"


def test_no_injection_lowers_first_attempt_retention(tmp_path, notes, base_config, monkeypatch):
    monkeypatch.setattr(ab, "evaluate_outputs", lambda *a, **k: None)
    from src.evaluator import evaluate_record
    from src.utils import read_json

    rows = {}
    for name, overrides in {"baseline": {}, "no_inj": {"prompts.inject_entities": False}}.items():
        cfg = build_ablation_config(base_config, overrides, mock=True)
        run_ablation(name, cfg, overrides, notes[:1], tmp_path / name, tmp_path / f"r_{name}", GeneratorCache())
        rows[name] = evaluate_record(read_json(tmp_path / name / "n1.json"))
    assert rows["baseline"]["patient_summary_retention_first"] == 1.0
    assert rows["no_inj"]["patient_summary_retention_first"] < 1.0
    assert rows["no_inj"]["patient_summary_retention"] == 1.0  # fallback restores the final text


def test_shadowed_persona_settings_are_reported(base_config):
    base_config["personas"]["child_explanation"]["temperature"] = 0.3
    assert shadowed_overrides(base_config, {"generation.temperature": 0.7}) == ["personas.child_explanation.temperature"]
    assert shadowed_overrides(base_config, {"generation.temperature": 0.7,
                                            "personas.child_explanation.temperature": 0.7}) == []


def test_config_temp_ablation_covers_all_personas():
    from src.utils import load_config
    cfg = load_config()
    overrides = cfg["ablations"]["temp_0.7"]
    assert shadowed_overrides(cfg, overrides) == []
    built = build_ablation_config(cfg, overrides)
    assert built["generation"]["temperature"] == 0.7
    assert all(p.get("temperature", 0.7) == 0.7 for p in built["personas"].values())


def test_config_has_child_v1_ablation():
    from src.utils import load_config
    cfg = load_config()
    assert cfg["prompts"]["child_variant"] == "v2"
    assert build_ablation_config(cfg, cfg["ablations"]["child_v1"])["prompts"]["child_variant"] == "v1"
    assert cfg["personas"]["patient_summary"]["max_new_tokens"] >= 512


def test_seed_dirs_and_config():
    out, res = ablation_dirs("baseline", mock=True, seed=2)
    assert out.name == "outputs_mock_baseline_seed2" and res.parts[-2:] == ("baseline", "seed2")
    out, res = ablation_dirs("baseline", mock=False)
    assert out.name == "outputs_baseline" and res.name == "baseline"
    cfg = build_ablation_config({"generation": {"seed": 42}}, {}, seed=1)
    assert cfg["generation"]["seed"] == 1


def test_multi_seed_summary(seeded_runs):
    summary, by_seed = summarize_ablations(seeded_runs, mock=True, seeds=[0, 1])
    assert len(summary) == 2 and len(by_seed) == 4
    base = summary.set_index("ablation").loc["baseline"]
    assert base["n_seeds"] == 2 and base["seeds"] == "0 1" and base["status"] == "ok"
    assert base["retention_patient_overall_std"] == 0.0             # mock output does not depend on the seed
    no_inj = summary.set_index("ablation").loc["no_inj"]
    assert no_inj["fallback_rate"] == pytest.approx(2 / 3)          # patient + caregiver of 3 personas
    assert base["fallback_rate"] == 0.0 and "truncation_rate_patient_summary" in summary
    assert base["repetition_rate"] == 0.0 and "repetition_rate_caregiver_checklist" in summary
    missing, _ = summarize_ablations(seeded_runs, mock=True, seeds=[0, 5])
    assert missing.set_index("ablation").loc["baseline", "status"] == "partial (1/2 seeds)"


def test_multi_seed_figures(seeded_runs, tmp_path):
    summary, _ = summarize_ablations(seeded_runs, mock=True, seeds=[0, 1])
    written = ab.plot_ablation_summary(summary, tmp_path / "figs")
    assert {p.name for p in written} == {"readability_delta.png", "rouge.png", "retention.png", "reliability.png"}
