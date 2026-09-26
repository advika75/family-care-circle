"""Tests for src/utils.py."""

from __future__ import annotations

import random

import pytest

from src.utils import PROJECT_ROOT, list_files, load_config, read_json, resolve_path, set_seed, write_json


def test_load_config_applies_non_none_overrides():
    cfg = load_config("config.yaml", {"backend": "mock", "model_id": None})
    assert cfg["backend"] == "mock"
    assert cfg["model_id"] == load_config("config.yaml")["model_id"]   # None does not override
    assert {"generation", "personas", "prompts", "ablations", "paths"} <= set(cfg)


def test_resolve_path_is_relative_to_project_root(tmp_path):
    assert resolve_path("data/raw") == PROJECT_ROOT / "data/raw"
    assert resolve_path(tmp_path) == tmp_path


def test_json_roundtrip_and_list_files(tmp_path):
    path = write_json({"a": [1, "é"]}, tmp_path / "sub" / "x.json")
    assert read_json(path) == {"a": [1, "é"]}
    (tmp_path / "sub" / "note.txt").write_text("hi")
    (tmp_path / "sub" / "skip.md").write_text("no")
    assert [p.name for p in list_files(tmp_path / "sub")] == ["note.txt"]
    assert [p.name for p in list_files(tmp_path / "sub", (".json",))] == ["x.json"]
    assert list_files(tmp_path / "sub" / "note.txt")[0].name == "note.txt"
    with pytest.raises(FileNotFoundError):
        list_files(tmp_path / "missing")


def test_set_seed_is_reproducible():
    set_seed(7)
    a = random.random()
    set_seed(7)
    assert random.random() == a
