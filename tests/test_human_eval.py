"""Tests for the human-evaluation kit."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.human_eval import (
    RATING_METRICS,
    SHEET_COLUMNS,
    agreement,
    load_ratings,
    make_rating_sheet,
    ratings_markdown,
    summarize_ratings,
)


@pytest.fixture
def kit(mock_records):
    return make_rating_sheet({"baseline": mock_records["baseline"]}, n_notes=2, seed=1)


def test_sheet_is_blinded_and_matches_key(kit):
    sheet, key = kit
    assert list(sheet.columns) == SHEET_COLUMNS
    assert len(sheet) == 6 and len(key) == 6                      # 2 notes x 3 personas
    assert "system" not in sheet.columns and "note_id" not in sheet.columns
    assert list(sheet["sample_id"]) == list(key["sample_id"])
    assert (sheet[list(RATING_METRICS)] == "").all().all()
    assert sheet["text"].str.len().min() > 0


def test_sampling_is_reproducible_and_capped(mock_records):
    a, _ = make_rating_sheet({"x": mock_records["baseline"]}, n_notes=10, seed=3)
    b, _ = make_rating_sheet({"x": mock_records["baseline"]}, n_notes=10, seed=3)
    assert a.equals(b) and len(a) == 9                           # only 3 notes exist


def test_multiple_systems_are_mixed(mock_records):
    _, key = make_rating_sheet(mock_records, n_notes=2)
    assert set(key["system"]) == {"baseline", "no_injection"} and len(key) == 12


def _fill(sheet, path, scores, concern=""):
    done = sheet.copy()
    for m in RATING_METRICS:
        done[m] = scores
    done["safety_concerns"] = [concern] + [""] * (len(done) - 1)
    done.to_csv(path, index=False)
    return path


def test_aggregate_two_raters(kit, tmp_path):
    sheet, key = kit
    a = _fill(sheet, tmp_path / "ratings_alice.csv", [5, 4, 3, 5, 2, 4], "dose looks wrong")
    b = _fill(sheet, tmp_path / "ratings_bob.csv", [5, 4, 3, 4, 2, 4])
    ratings, concerns = load_ratings([a, b], key)
    assert set(ratings["rater"]) == {"alice", "bob"} and len(ratings) == 36 and len(concerns) == 1
    summary = summarize_ratings(ratings)
    assert set(summary["metric"]) == set(RATING_METRICS) and summary["n"].sum() == 36
    agree = agreement(ratings)
    assert (agree["method"] == "Cohen's κ (quadratic)").all()
    assert agree["kappa"].between(0.8, 1.0).all()
    md = ratings_markdown(summary, agree, concerns, 2)
    assert "| Persona | Clarity |" in md and "Cohen's κ" in md


def test_three_raters_use_mean_pairwise_and_bad_values_are_dropped(kit, tmp_path):
    sheet, key = kit
    paths = [_fill(sheet, tmp_path / f"ratings_r{i}.csv", s) for i, s in
             enumerate(([5, 4, 3, 5, 2, 4], [5, 4, 3, 4, 2, 4], [4, 4, 3, 5, 1, 9]))]
    ratings, _ = load_ratings(paths, key)
    assert len(ratings) == 3 * 6 * 3 - 3                          # the three "9"s are dropped
    agree = agreement(ratings)
    assert agree["method"].str.startswith("mean pairwise").all()


def test_single_rater_has_no_agreement(kit, tmp_path):
    sheet, key = kit
    ratings, _ = load_ratings([_fill(sheet, tmp_path / "ratings_solo.csv", [3] * 6)], key)
    assert math.isnan(agreement(ratings)["kappa"].iloc[0])


def test_unknown_sample_ids_are_rejected(kit, tmp_path):
    sheet, key = kit
    bad = sheet.copy()
    bad.loc[0, "sample_id"] = "S999"
    bad.to_csv(tmp_path / "ratings_x.csv", index=False)
    with pytest.raises(ValueError, match="S999"):
        load_ratings([tmp_path / "ratings_x.csv"], key)
