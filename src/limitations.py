"""Builds limitations.md from measured evidence plus known, structural caveats.

The prose for each caveat is fixed (these are properties of the method, not of any one run), but
every number inside it is a parameter pulled from the actual result files by the caller
(scripts/build_limitations.py), never hardcoded here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LimitationsContext:
    """Measured facts the limitations draft is built from. ``None`` means "not measured yet"."""

    n_synthetic_notes: int | None = None
    n_synthetic_gold_notes: int | None = None
    n_synthetic_gold_entities: int | None = None
    n_mtsamples_notes: int | None = None
    n_mtsamples_gold_total: int | None = None
    n_mtsamples_gold_complete: int | None = None
    ner_miss_examples: tuple[str, ...] = ()  # concrete "entity in source, missed by rule-based NER" cases
    unsupported_content_failures: int | None = None
    unsupported_content_notes_affected: int | None = None
    unsupported_content_notes_total: int | None = None
    child_fkgl_synthetic: float | None = None
    child_fkgl_mtsamples: float | None = None
    child_target_grade: float = 1.0
    n_human_eval_raters: int = 0
    n_human_eval_samples: int | None = None  # configured sample size (build_rating_set.py --n default)


def _n(value: int | float | None, fallback: str = "an unmeasured number of") -> str:
    if value is None:
        return fallback
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def build_limitations(ctx: LimitationsContext) -> str:
    """Render the limitations draft as markdown."""
    sections = [
        "# Limitations (draft)",
        "",
        "> Draft assembled from measured evidence in this repository's result files plus known structural "
        "caveats of the method. Not a substitute for clinician or domain-expert review before any real use.",
        "",
        "## 1. Entity retention can overstate true factual coverage",
        "",
        f"Retention (Table 2 / `results/ablations/*/summary.csv`) measures whether a required fact appears in "
        f"the generated text, where \"required fact\" means a MEDICATION/DOSAGE/FREQUENCY/DURATION span the "
        f"**rule-based extractor** (`src/ner.py`) found in the source note — not everything actually "
        f"stated in the note. If the extractor misses a genuine entity, neither the model's output nor the "
        f"deterministic fallback is ever checked against it, so a retention number can be 100% while a real "
        f"fact the note contains is simply never surfaced to the reader.",
        "",
        "This is not hypothetical: implementing the dosage-directive hard-validation fix for the MTSamples "
        "evaluation (see `results/mtsamples_summary.md`) first checked a generated dose only against "
        "NER-extracted DOSAGE entities. That version would have redacted two genuinely correct facts, because "
        "the extractor misses spelled-out doses that are, nonetheless, right there in the source text"
        + (f": {', '.join(ctx.ner_miss_examples)}." if ctx.ner_miss_examples else "."),
        "",
        "## 2. The synthetic dataset is tiny",
        "",
        f"{_n(ctx.n_synthetic_notes)} synthetic notes, {_n(ctx.n_synthetic_gold_notes)} with hand-annotated "
        f"gold entities ({_n(ctx.n_synthetic_gold_entities)} entities total, annotated by the project team, "
        f"not clinicians). Every synthetic-dataset number in this report rests on this very small N; the "
        f"per-seed standard deviations in the ablation table are often comparable in size to the effect being "
        f"measured, and the dataset was authored specifically to exercise this pipeline, not sampled from "
        f"real clinical variation.",
        "",
        "## 3. Flesch-Kincaid grade level is a weak comprehension proxy",
        "",
        f"FKGL scores syllables-per-word and words-per-sentence; it does not know whether a short sentence "
        f"uses an unfamiliar clinical term (\"edema\", \"ejection fraction\") that a 1st-grader would not "
        f"understand even though the sentence is short. The child persona averages FKGL "
        f"{_n(ctx.child_fkgl_synthetic, 'an unmeasured grade')} (synthetic) and "
        f"{_n(ctx.child_fkgl_mtsamples, 'an unmeasured grade')} (MTSamples) against a "
        f"~{ctx.child_target_grade:.0f}st-grade target (`results/tables/figures/fkgl_vs_child_target.png`); "
        f"neither dataset reaches the literal target, and even a text that did would not thereby be shown to "
        f"be actually comprehensible to a 1st-grader — only shorter and simpler-worded by this one formula.",
        "",
        "## 4. The hallucination checks are narrow, lexical heuristics",
        "",
        "`unsupported_numbers`/`unsupported_meds` (`src/evaluator.py`) only catch a number or drug name that "
        "does not appear anywhere in the source text at all. An invented instruction that reuses a real "
        "number from the note in the wrong context (e.g. \"follow up in 10 days\" when the note's 10-day span "
        "describes an antibiotic course) is not caught, and a hallucinated fact that happens to restate a "
        "number already elsewhere in the note is invisible to this check."
        + (f" On the {_n(ctx.unsupported_content_notes_total)}-note MTSamples run, these checks flagged "
           f"{_n(ctx.unsupported_content_failures)} instances across {_n(ctx.unsupported_content_notes_affected)} "
           f"notes (`results/mtsamples/error_analysis.md`) — a useful upper bound and source of concrete "
           "examples, not a verified hallucination count." if ctx.unsupported_content_failures is not None else ""),
        "",
        "## 5. The human evaluation sample is small (and not yet collected)",
        "",
        f"`scripts/build_rating_set.py` defaults to sampling {_n(ctx.n_human_eval_samples, '6')} notes per "
        f"condition. As of this writing, {ctx.n_human_eval_raters} rater(s) have completed ratings in "
        f"`results/human_eval/`" + (" — this draft predates any real human evaluation." if not
                                     ctx.n_human_eval_raters else ", which is not enough for reliable "
                                     "inter-rater statistics.") + " Even once collected, a handful of "
        "non-clinician raters judging a handful of notes is informative but not a substitute for clinician "
        "review or a larger-scale study before any real deployment.",
        "",
    ]
    return "\n".join(sections)
