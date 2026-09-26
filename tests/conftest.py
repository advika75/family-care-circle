"""Shared pytest fixtures (no model downloads: everything uses the mock backend)."""

from __future__ import annotations

import copy

import pytest

SAMPLE_NOTE = (
    "Assessment: Streptococcal pharyngitis (strep throat). Fever and sore throat.\n"
    "1. Amoxicillin 500 mg PO BID x 10 days.\n"
    "2. Ibuprofen 200 mg PO q6h PRN pain.\n"
)


@pytest.fixture
def sample_note() -> str:
    return SAMPLE_NOTE


@pytest.fixture
def mock_config() -> dict:
    return {
        "backend": "mock",
        "model_id": "mock",
        "generation": {"max_new_tokens": 100, "temperature": 0.2, "top_p": 0.9, "seed": 0},
        "personas": {
            "patient_summary": {"required_labels": ["MEDICATION", "DOSAGE", "FREQUENCY", "DURATION"]},
            "caregiver_checklist": {"required_labels": ["MEDICATION", "DOSAGE", "FREQUENCY", "DURATION"]},
            "child_explanation": {"required_labels": []},
        },
        "max_retries": 2,
        "ner": {"use_hf_model": False},
        "mock": {"fail_first": 0},
    }


@pytest.fixture
def mock_records(mock_config):
    """Mock pipeline outputs for three real notes: {"baseline": [...], "no_injection": [...]}."""
    import copy

    from src.pipeline import FamilyCarePipeline
    from src.utils import read_text

    notes = {f"note_0{i}": read_text(f"data/raw/note_0{i}.txt") for i in (1, 2, 4)}
    out = {}
    for name, inject in (("baseline", True), ("no_injection", False)):
        cfg = copy.deepcopy(mock_config)
        cfg["prompts"] = {"inject_entities": inject}
        pipeline = FamilyCarePipeline(cfg)
        out[name] = [pipeline.run(text, doc_id) for doc_id, text in notes.items()]
    return out


@pytest.fixture
def seeded_runs(tmp_path, mock_config, monkeypatch):
    """Run two ablations x two seeds with the mock backend inside tmp_path; returns the ablation names."""
    import src.ablations as ab
    from src.ablations import GeneratorCache, ablation_dirs, build_ablation_config, run_ablation

    monkeypatch.setattr(ab, "resolve_path", lambda p: tmp_path / p)
    base = copy.deepcopy(mock_config)
    base.update(prompts={"inject_entities": True, "child_variant": "v2"},
                paths={"raw_dir": "data/raw", "gold_dir": "data/gold"})
    notes = []
    for i in (1, 2):
        note = tmp_path / f"n{i}.txt"
        note.write_text(open(f"data/raw/note_0{i}.txt").read())
        notes.append(note)
    ablations = {"baseline": {}, "no_inj": {"prompts.inject_entities": False}}
    cache = GeneratorCache()
    for name, overrides in ablations.items():
        for seed in (0, 1):
            cfg = build_ablation_config(base, overrides, mock=True, seed=seed)
            out, res = ablation_dirs(name, True, seed)
            info = run_ablation(name, cfg, overrides, notes, out, res, cache)
            assert info["status"] == "ok", info["error"]
    return list(ablations)

