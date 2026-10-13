"""Tests for src/limitations.py: the limitations.md draft builder."""

from __future__ import annotations

from src.limitations import LimitationsContext, build_limitations


def test_unmeasured_numbers_say_so_instead_of_a_placeholder():
    md = build_limitations(LimitationsContext())
    assert "an unmeasured number of synthetic notes" in md
    assert "0" not in md.split("## 2.")[1].split("## 3.")[0]  # no fabricated zero where nothing was measured


def test_measured_numbers_are_rendered_and_floats_are_rounded():
    ctx = LimitationsContext(
        n_synthetic_notes=12, n_synthetic_gold_notes=6, n_synthetic_gold_entities=146,
        n_mtsamples_notes=100, n_mtsamples_gold_total=30, n_mtsamples_gold_complete=0,
        child_fkgl_synthetic=2.6457575757575, child_fkgl_mtsamples=2.7703579615936,
        unsupported_content_failures=208, unsupported_content_notes_affected=81,
        unsupported_content_notes_total=100,
    )
    md = build_limitations(ctx)
    assert "12 synthetic notes" in md and "6 with hand-annotated gold entities (146 entities" in md
    assert "2.65" in md and "2.77" in md
    assert "2.6457575757575" not in md  # not a raw unrounded float
    assert "208 instances across 81 notes" in md


def test_ner_miss_examples_are_named_when_provided():
    ctx = LimitationsContext(ner_miss_examples=('"81 milligrams" (note_a)', '"One mL" (note_b)'))
    md = build_limitations(ctx)
    assert '"81 milligrams" (note_a)' in md and '"One mL" (note_b)' in md


def test_zero_raters_is_stated_plainly_not_hidden():
    md = build_limitations(LimitationsContext(n_human_eval_raters=0))
    assert "0 rater(s)" in md and "predates any real human evaluation" in md


def test_nonzero_raters_changes_the_framing():
    md = build_limitations(LimitationsContext(n_human_eval_raters=2))
    assert "2 rater(s)" in md and "not enough for reliable" in md
    assert "predates any real human evaluation" not in md
