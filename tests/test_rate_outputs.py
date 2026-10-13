"""Tests for the RatingStore backing scripts/rate_outputs.py (blinded local rating UI)."""

from __future__ import annotations

import json

import pytest

from scripts.rate_outputs import RatingStore


def _store(tmp_path):
    items = [
        {"sample_id": "S001", "persona": "patient_summary", "source_note": "Note A", "text": "Summary A"},
        {"sample_id": "S002", "persona": "caregiver_checklist", "source_note": "Note A", "text": ["Do X", "Do Y"]},
    ]
    set_path = tmp_path / "rating_set.json"
    set_path.write_text(json.dumps(items))
    return RatingStore(set_path, tmp_path, "alice"), tmp_path


def test_rating_store_rejects_missing_set_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        RatingStore(tmp_path / "missing.json", tmp_path, "alice")


def test_rating_store_state_and_item_before_any_rating(tmp_path):
    store, _ = _store(tmp_path)
    state = store.state()
    assert state["rater"] == "alice" and state["count"] == 2
    assert all(not item["rated"] for item in state["items"])
    item = store.item("S002")
    assert item["text"] == ["Do X", "Do Y"] and item["rating"] is None


def test_rating_store_item_never_exposes_a_condition_label(tmp_path):
    store, _ = _store(tmp_path)
    item = store.item("S001")
    assert "system" not in item and "note_id" not in item


def test_rating_store_save_then_item_reflects_it_and_marks_done(tmp_path):
    store, _ = _store(tmp_path)
    result = store.save({"sample_id": "S001",
                          "scores": {"factual_accuracy": 5, "completeness": 4, "readability": 5,
                                     "persona_suitability": 4},
                          "missing_or_wrong_fact": True, "missing_or_wrong_fact_note": "wrong dose"})
    assert result == {"ok": True, "sample_id": "S001"}
    item = store.item("S001")
    assert item["rating"]["scores"]["factual_accuracy"] == 5
    assert item["rating"]["missing_or_wrong_fact_note"] == "wrong dose"
    assert store.state()["items"][0]["rated"] is True
    assert store.state()["items"][1]["rated"] is False


def test_rating_store_save_rejects_unknown_sample_and_bad_score(tmp_path):
    store, _ = _store(tmp_path)
    with pytest.raises(ValueError, match="Unknown sample"):
        store.save({"sample_id": "S999", "scores": {}})
    with pytest.raises(ValueError, match="between 1 and 5"):
        store.save({"sample_id": "S001", "scores": {"factual_accuracy": 9}})


def test_rating_store_partial_scores_are_allowed(tmp_path):
    """A rater can save after filling only some dimensions; unfilled ones are simply absent."""
    store, _ = _store(tmp_path)
    store.save({"sample_id": "S001", "scores": {"factual_accuracy": 3}})
    assert store.item("S001")["rating"]["scores"] == {"factual_accuracy": 3}
