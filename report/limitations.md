# Limitations (draft)

> Draft assembled from measured evidence in this repository's result files plus known structural caveats of the method. Not a substitute for clinician or domain-expert review before any real use.

## 1. Entity retention can overstate true factual coverage

Retention (Table 2 / `results/ablations/*/summary.csv`) measures whether a required fact appears in the generated text, where "required fact" means a MEDICATION/DOSAGE/FREQUENCY/DURATION span the **rule-based extractor** (`src/ner.py`) found in the source note — not everything actually stated in the note. If the extractor misses a genuine entity, neither the model's output nor the deterministic fallback is ever checked against it, so a retention number can be 100% while a real fact the note contains is simply never surfaced to the reader.

This is not hypothetical: implementing the dosage-directive hard-validation fix for the MTSamples evaluation (see `results/mtsamples_summary.md`) first checked a generated dose only against NER-extracted DOSAGE entities. That version would have redacted two genuinely correct facts, because the extractor misses spelled-out doses that are, nonetheless, right there in the source text: "81 milligrams" (mtsamples_Acute_Inferior_Myocardial_Infarction), "One mL" (mtsamples_Carpal_Ligament_Release_-_2).

## 2. The synthetic dataset is tiny

12 synthetic notes, 6 with hand-annotated gold entities (146 entities total, annotated by the project team, not clinicians). Every synthetic-dataset number in this report rests on this very small N; the per-seed standard deviations in the ablation table are often comparable in size to the effect being measured, and the dataset was authored specifically to exercise this pipeline, not sampled from real clinical variation.

## 3. Flesch-Kincaid grade level is a weak comprehension proxy

FKGL scores syllables-per-word and words-per-sentence; it does not know whether a short sentence uses an unfamiliar clinical term ("edema", "ejection fraction") that a 1st-grader would not understand even though the sentence is short. The child persona averages FKGL 2.65 (synthetic) and 2.77 (MTSamples) against a ~1st-grade target (`results/tables/figures/fkgl_vs_child_target.png`); neither dataset reaches the literal target, and even a text that did would not thereby be shown to be actually comprehensible to a 1st-grader — only shorter and simpler-worded by this one formula.

## 4. The hallucination checks are narrow, lexical heuristics

`unsupported_numbers`/`unsupported_meds` (`src/evaluator.py`) only catch a number or drug name that does not appear anywhere in the source text at all. An invented instruction that reuses a real number from the note in the wrong context (e.g. "follow up in 10 days" when the note's 10-day span describes an antibiotic course) is not caught, and a hallucinated fact that happens to restate a number already elsewhere in the note is invisible to this check. On the 100-note MTSamples run, these checks flagged 208 instances across 81 notes (`results/mtsamples/error_analysis.md`) — a useful upper bound and source of concrete examples, not a verified hallucination count.

## 5. The human evaluation sample is small (and not yet collected)

`scripts/build_rating_set.py` defaults to sampling 6 notes per condition. As of this writing, 0 rater(s) have completed ratings in `results/human_eval/` — this draft predates any real human evaluation. Even once collected, a handful of non-clinician raters judging a handful of notes is informative but not a substitute for clinician review or a larger-scale study before any real deployment.

