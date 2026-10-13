"""Tests for the human-evaluation kit."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.human_eval import (
    RATING_DIMENSIONS,
    RATING_METRICS,
    SHEET_COLUMNS,
    agreement,
    build_condition_rating_set,
    condition_ratings_markdown,
    load_condition_ratings,
    load_ratings,
    make_rating_sheet,
    rater_json_path,
    ratings_markdown,
    read_rater_ratings,
    summarize_ratings,
    write_rater_rating,
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


# --------------------------------------------------------------------------- condition rating set (UI-based)

@pytest.fixture
def condition_set(mock_records):
    return build_condition_rating_set(mock_records, n_notes=2, seed=1)


def test_condition_set_is_blinded_and_matches_key(condition_set):
    items, key = condition_set
    assert len(items) == 12 and len(key) == 12                     # 2 notes x 2 conditions x 3 personas
    assert {"sample_id", "persona", "source_note", "text"} == set(items[0])
    assert set(key["system"]) == {"baseline", "no_injection"}
    assert [i["sample_id"] for i in items] == list(key["sample_id"])


def test_condition_set_sampling_is_reproducible(mock_records):
    a, _ = build_condition_rating_set(mock_records, n_notes=2, seed=7)
    b, _ = build_condition_rating_set(mock_records, n_notes=2, seed=7)
    assert a == b


def _fake_rating(scores: dict[str, int], flagged: bool = False, note: str = "") -> dict:
    return {"scores": scores, "missing_or_wrong_fact": flagged, "missing_or_wrong_fact_note": note}


def test_rater_json_round_trips_and_merges(tmp_path):
    path = rater_json_path(tmp_path, "alice")
    assert read_rater_ratings(path) == {}
    write_rater_rating(path, "S001", _fake_rating({"factual_accuracy": 5}))
    write_rater_rating(path, "S002", _fake_rating({"factual_accuracy": 3}, flagged=True, note="wrong dose"))
    data = read_rater_ratings(path)
    assert data["S001"]["scores"]["factual_accuracy"] == 5
    assert data["S002"]["missing_or_wrong_fact"] and data["S002"]["missing_or_wrong_fact_note"] == "wrong dose"
    # merging a second write to an existing sample must not drop the other sample
    write_rater_rating(path, "S001", _fake_rating({"factual_accuracy": 4}))
    assert set(read_rater_ratings(path)) == {"S001", "S002"}


def test_load_condition_ratings_builds_long_format_and_flags(condition_set, tmp_path):
    items, key = condition_set
    path = rater_json_path(tmp_path, "alice")
    for i, item in enumerate(items):
        scores = {dim: (i % 5) + 1 for dim in RATING_DIMENSIONS}
        write_rater_rating(path, item["sample_id"], _fake_rating(scores, flagged=(i == 0), note="bad dose" if i == 0 else ""))
    ratings, flags = load_condition_ratings([path], key)
    assert len(ratings) == len(items) * len(RATING_DIMENSIONS)
    assert set(ratings["metric"]) == set(RATING_DIMENSIONS)
    assert len(flags) == 1 and flags.iloc[0]["flagged"] and flags.iloc[0]["note"] == "bad dose"


def test_load_condition_ratings_skips_unrated_and_out_of_range(condition_set, tmp_path):
    items, key = condition_set
    path = rater_json_path(tmp_path, "alice")
    write_rater_rating(path, items[0]["sample_id"], _fake_rating({"factual_accuracy": 9}))     # out of range
    write_rater_rating(path, items[1]["sample_id"], _fake_rating({"factual_accuracy": 4}))      # only 1 of 4 dims
    ratings, _ = load_condition_ratings([path], key)
    assert len(ratings) == 1 and ratings.iloc[0]["score"] == 4


def test_condition_ratings_two_raters_agreement_and_markdown(condition_set, tmp_path):
    items, key = condition_set
    paths = []
    for rater, base in (("alice", 3), ("bob", 3)):
        path = rater_json_path(tmp_path, rater)
        for i, item in enumerate(items):
            scores = {dim: min(5, max(1, base + (i % 2))) for dim in RATING_DIMENSIONS}
            write_rater_rating(path, item["sample_id"], _fake_rating(scores))
        paths.append(path)
    ratings, flags = load_condition_ratings(paths, key)
    summary = summarize_ratings(ratings)
    agree = agreement(ratings, RATING_DIMENSIONS)
    assert (agree["method"] == "Cohen's κ (quadratic)").all()
    md = condition_ratings_markdown(summary, agree, flags, 2)
    assert "Persona suitability" in md and "Cohen's κ" in md


def test_condition_ratings_handle_one_rater_and_no_flags(condition_set, tmp_path):
    items, key = condition_set
    path = rater_json_path(tmp_path, "solo")
    for item in items:
        write_rater_rating(path, item["sample_id"], _fake_rating({dim: 4 for dim in RATING_DIMENSIONS}))
    ratings, flags = load_condition_ratings([path], key)
    assert flags.empty
    agree = agreement(ratings, RATING_DIMENSIONS)
    assert agree["method"].eq("n/a (needs 2+ raters)").all() and agree["kappa"].isna().all()
    md = condition_ratings_markdown(summarize_ratings(ratings), agree, flags, 1)
    assert "n/a" in md
