# Baseline vs partially adjudicated gold — comparison report

**This is a PARTIAL adjudication.** Only 16 of 79 queue candidates have an ADOPT decision applied here. Treat these numbers as a diagnostic of how the gold changed, not as a final benchmark.

## What changed, and what did not

- **The extractor did not change.** Both runs use the same rule-based extractor (`extract_rule_based`) and the same matching code (`match_entities` / `ner_scores` in `src/evaluator.py`) at commit `54b77683323f564dbbf4cb7ddbdbb4b26b1e59ac` plus the uncommitted working tree. I re-ran that code on the protected snapshot and it reproduced the saved baseline's metrics and error rows exactly.
- **Every metric difference below comes from changed gold, not from a better extractor.** No claim of improved extractor quality is made or supported.
- **Baseline:** `data/public/mtsamples/gold_adjudication_v1_20261024/` (529 gold spans; saved results in `results/mtsamples_ner_gold30_20261024_v2/`).
- **Adjudicated:** `data/public/mtsamples/gold_adjudicated_v1_1_20261024/` (520 gold spans), built by applying only ADOPT rows from Batches 01–03. Span-level changes are in `gold_change_manifest.csv`.

Gold changes: 11 spans removed, 4 modified, 2 added, and 1 ADOPT that retains a span unchanged (`diabetic`). Net 529 − 11 + 2 = 520.

## Exact-span matching (start, end, label)

| Label | Base P | Base R | Base F1 | Base TP/FP/FN | Adj P | Adj R | Adj F1 | Adj TP/FP/FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CONDITION | 59.3% | 7.1% | 12.7% | 16/11/209 | 59.3% | 7.3% | 13.1% | 16/11/202 |
| DOSAGE | 78.3% | 48.0% | 59.5% | 36/10/39 | 78.3% | 48.0% | 59.5% | 36/10/39 |
| DURATION | 0.0% | 0.0% | 0.0% | 0/4/31 | 0.0% | 0.0% | 0.0% | 0/4/26 |
| FREQUENCY | 88.2% | 35.7% | 50.8% | 15/2/27 | 88.2% | 35.7% | 50.8% | 15/2/27 |
| MEDICATION | 60.0% | 13.4% | 21.9% | 15/10/97 | 60.0% | 13.4% | 21.9% | 15/10/97 |
| SYMPTOM | 11.8% | 20.5% | 15.0% | 9/67/35 | 18.4% | 29.8% | 22.8% | 14/62/33 |
| **MICRO** | 46.7% | 17.2% | 25.1% | 91/104/438 | 49.2% | 18.5% | 26.9% | 96/99/424 |

## Relaxed matching (same label, overlapping spans)

Relaxed scores use the project's existing `relaxed` mode in `src/evaluator.py`. `scripts/evaluate_mtsamples_ner.py` writes only exact scores, so this table comes from `compare_gold_versions.py` in this directory. The baseline relaxed numbers were not saved before.

| Label | Base P | Base R | Base F1 | Base TP/FP/FN | Adj P | Adj R | Adj F1 | Adj TP/FP/FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CONDITION | 96.3% | 11.6% | 20.6% | 26/1/199 | 96.3% | 11.9% | 21.2% | 26/1/192 |
| DOSAGE | 91.3% | 56.0% | 69.4% | 42/4/33 | 91.3% | 56.0% | 69.4% | 42/4/33 |
| DURATION | 50.0% | 6.5% | 11.4% | 2/2/29 | 50.0% | 7.7% | 13.3% | 2/2/24 |
| FREQUENCY | 88.2% | 35.7% | 50.8% | 15/2/27 | 88.2% | 35.7% | 50.8% | 15/2/27 |
| MEDICATION | 72.0% | 16.1% | 26.3% | 18/7/94 | 72.0% | 16.1% | 26.3% | 18/7/94 |
| SYMPTOM | 23.7% | 40.9% | 30.0% | 18/58/26 | 26.3% | 42.6% | 32.5% | 20/56/27 |
| **MICRO** | 62.1% | 22.9% | 33.4% | 121/74/408 | 63.1% | 23.7% | 34.4% | 123/72/397 |

## Why the numbers moved

- **Exact TP 91 → 96 (+5).** The new matches are `Chest pain` (relabelled SYMPTOM), `shortness of breath`, `vomiting`, `fever` and `chills`. In each case the extractor's prediction already existed, and the gold boundary or label now agrees with it.
- **Exact FP 104 → 99 (−5).** Those same five predictions were previously counted as false positives.
- **FN 438 → 424 (−14).** FN equals gold spans minus true positives: gold fell by 9 (529 → 520) and TP rose by 5. By label, CONDITION FN falls by 7 (6 removed spans plus the `Chest pain` relabel), DURATION FN falls by 5 (5 removed spans), and SYMPTOM FN falls by only 2 (gold gained 3 SYMPTOM spans: `Chest pain`, `diaphoresis`, `chills`; TP rose by 5). Removing a gold span that the extractor never matched lowers FN without any extractor change.
- **Unchanged labels.** DOSAGE, FREQUENCY and MEDICATION are identical in both runs, because no ADOPT decision touched them.
- **DURATION** is still 0 exact TP. Removing five gold spans lowers FN but creates no match.

## Review status (partial)

- **Queue size:** 79 unique candidates.
- **Reviewed:** 24 of 79.
- **ADOPT, applied (16):** C01 (retains `diabetic` unchanged), C02, C03, C04, C05, C06, C09, SC01, D01, D02, D03, D08, D09, PC01, PC02, PC03. Fifteen of these change gold spans; the candidate-to-queue mapping is in `gold_change_manifest.csv`.
- **Still DISCUSS, nothing applied (8):** SC02 `Dyspnea`, SC04 `Edema`, D04 `approximately 10 days`, D05 `over the past 1 hour`, D10 `for 26 years`, D15 `24-48 hours`, M01 `Humulin N. insulin`, M02 `prophylactic antibiotics`.
- **Not yet reviewed (55):** 36 CONDITION-scope, 15 DURATION, 2 MEDICATION, 1 symptom/condition (SC03), 1 punctuation (PC04).
- **Known open items in the adjudicated gold.** These are unreviewed and unchanged: ` Nitroglycerin` [1762,1776) has a leading space (M03), and `chest pain` [141,151) is still CONDITION (SC03). Both still affect the scores.

## Caveats

- The working tree has uncommitted changes under `src/` and `scripts/`. The commit hash identifies the base only; the reproduction check above is what shows the code matches the baseline.
- With 24 of 79 candidates reviewed, further adjudication could move these numbers in either direction.
- The adjudicated gold is a derived working version. The pre-adjudication results in `results/mtsamples_ner_gold30_20261024_v2/` are untouched.
