# Original baseline vs gold v1.1 vs gold v1.2 — comparison report

**This is a PARTIAL adjudication.** 26 of the 79 queue candidates have been reviewed; 53 have not. Treat these numbers as a diagnostic of how the gold changed, not as a final benchmark.

**Metric changes come from changed gold, not from any change to the extractor.** All three runs use the same rule-based extractor (`extract_rule_based`) and the same matching code (`match_entities` / `ner_scores` in `src/evaluator.py`). No code under `src/` was changed for this report. No claim of improved extractor quality is made or supported.

## The three gold versions

| Version | Directory | Gold spans |
|---|---|---:|
| Original baseline | `data/public/mtsamples/gold_adjudication_v1_20261024/` (protected snapshot) | 529 |
| v1.1 | `data/public/mtsamples/gold_adjudicated_v1_1_20261024/` (Batches 01–03) | 520 |
| v1.2 | `data/public/mtsamples/gold_adjudicated_v1_2_20261025/` (v1.1 plus Batch 04) | 518 |

Gold spans per label:

| Label | Original | v1.1 | v1.2 |
|---|---:|---:|---:|
| CONDITION | 225 | 218 | 216 |
| DOSAGE | 75 | 75 | 75 |
| DURATION | 31 | 26 | 23 |
| FREQUENCY | 42 | 42 | 42 |
| MEDICATION | 112 | 112 | 111 |
| SYMPTOM | 44 | 47 | 51 |
| **Total** | **529** | **520** | **518** |

Changes from v1.1 to v1.2 (listed in `gold_change_manifest_v1_1_to_v1_2.csv`): 2 relabels (`Dyspnea` and `chest pain` [141,151), CONDITION → SYMPTOM), 4 removals (`over the past 1 hour`, `for 26 years`, `24-48 hours`, `prophylactic antibiotics`), 1 shrink (`Humulin N. insulin` → `Humulin N`), 1 trim (` Nitroglycerin` → `Nitroglycerin`), and 2 additions (`chest pain` at [275,285) and [1800,1810), SYMPTOM). One ADOPT, D04 `approximately 10 days`, retains its span and changes nothing. Net 520 − 4 + 2 = 518.

## Exact-span matching (start, end, label)

Counts:

| Label | Original TP/FP/FN | v1.1 TP/FP/FN | v1.2 TP/FP/FN |
|---|---:|---:|---:|
| CONDITION | 16/11/209 | 16/11/202 | 16/11/200 |
| DOSAGE | 36/10/39 | 36/10/39 | 36/10/39 |
| DURATION | 0/4/31 | 0/4/26 | 0/4/23 |
| FREQUENCY | 15/2/27 | 15/2/27 | 15/2/27 |
| MEDICATION | 15/10/97 | 15/10/97 | 15/10/96 |
| SYMPTOM | 9/67/35 | 14/62/33 | 17/59/34 |
| **MICRO** | 91/104/438 | 96/99/424 | 99/96/419 |

Precision / recall / F1:

| Label | Orig P | Orig R | Orig F1 | v1.1 P | v1.1 R | v1.1 F1 | v1.2 P | v1.2 R | v1.2 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CONDITION | 59.3% | 7.1% | 12.7% | 59.3% | 7.3% | 13.1% | 59.3% | 7.4% | 13.2% |
| DOSAGE | 78.3% | 48.0% | 59.5% | 78.3% | 48.0% | 59.5% | 78.3% | 48.0% | 59.5% |
| DURATION | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| FREQUENCY | 88.2% | 35.7% | 50.8% | 88.2% | 35.7% | 50.8% | 88.2% | 35.7% | 50.8% |
| MEDICATION | 60.0% | 13.4% | 21.9% | 60.0% | 13.4% | 21.9% | 60.0% | 13.5% | 22.1% |
| SYMPTOM | 11.8% | 20.5% | 15.0% | 18.4% | 29.8% | 22.8% | 22.4% | 33.3% | 26.8% |
| **MICRO** | 46.7% | 17.2% | 25.1% | 49.2% | 18.5% | 26.9% | 50.8% | 19.1% | 27.8% |

## Relaxed matching (same label, overlapping spans)

Relaxed scores use the project's existing `relaxed` mode in `src/evaluator.py`. `scripts/evaluate_mtsamples_ner.py` writes only exact scores, so these tables come from `compare_gold_versions_3way.py` in this directory. The exact v1.2 counts from that script were cross-checked against the evaluator's own CSV and agree for every label.

Counts:

| Label | Original TP/FP/FN | v1.1 TP/FP/FN | v1.2 TP/FP/FN |
|---|---:|---:|---:|
| CONDITION | 26/1/199 | 26/1/192 | 26/1/190 |
| DOSAGE | 42/4/33 | 42/4/33 | 42/4/33 |
| DURATION | 2/2/29 | 2/2/24 | 2/2/21 |
| FREQUENCY | 15/2/27 | 15/2/27 | 15/2/27 |
| MEDICATION | 18/7/94 | 18/7/94 | 17/8/94 |
| SYMPTOM | 18/58/26 | 20/56/27 | 23/53/28 |
| **MICRO** | 121/74/408 | 123/72/397 | 125/70/393 |

Precision / recall / F1:

| Label | Orig P | Orig R | Orig F1 | v1.1 P | v1.1 R | v1.1 F1 | v1.2 P | v1.2 R | v1.2 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CONDITION | 96.3% | 11.6% | 20.6% | 96.3% | 11.9% | 21.2% | 96.3% | 12.0% | 21.4% |
| DOSAGE | 91.3% | 56.0% | 69.4% | 91.3% | 56.0% | 69.4% | 91.3% | 56.0% | 69.4% |
| DURATION | 50.0% | 6.5% | 11.4% | 50.0% | 7.7% | 13.3% | 50.0% | 8.7% | 14.8% |
| FREQUENCY | 88.2% | 35.7% | 50.8% | 88.2% | 35.7% | 50.8% | 88.2% | 35.7% | 50.8% |
| MEDICATION | 72.0% | 16.1% | 26.3% | 72.0% | 16.1% | 26.3% | 68.0% | 15.3% | 25.0% |
| SYMPTOM | 23.7% | 40.9% | 30.0% | 26.3% | 42.6% | 32.5% | 30.3% | 45.1% | 36.2% |
| **MICRO** | 62.1% | 22.9% | 33.4% | 63.1% | 23.7% | 34.4% | 64.1% | 24.1% | 35.1% |

## Why the numbers moved from v1.1 to v1.2

- **Exact TP 96 → 99 (+3).** The three new matches are the three `chest pain` SYMPTOM spans: [141,151) (relabelled from CONDITION) and [275,285) and [1800,1810) (added). The extractor already predicted SYMPTOM at all three places, so they were counted as false positives or as a label mismatch before. Nothing that matched in v1.1 stopped matching.
- **Exact FP 99 → 96 (−3).** Those same three predictions.
- **Exact FN 424 → 419 (−5).** FN equals gold spans minus true positives: gold fell by 2 (520 → 518) and TP rose by 3. By label, CONDITION FN fell by 2 (the two relabels leave CONDITION), DURATION FN fell by 3 (three removals), MEDICATION FN fell by 1 (the `prophylactic antibiotics` removal), and SYMPTOM FN rose by 1 (gold gained 4 SYMPTOM spans: two relabels and two additions; TP rose by 3, so one relabelled span, `Dyspnea`, is a new SYMPTOM miss).
- **Removed spans that the extractor never matched** lower FN without any extractor change.
- **Relaxed MEDICATION TP fell 18 → 17 (FP 7 → 8).** The extractor predicts `insulin` at [1719,1726). In v1.1 it overlapped the gold span `Humulin N. insulin` [1708,1726). After the shrink to `Humulin N` [1708,1717), the prediction overlaps no gold span. This is a side effect of the new gold boundary, not a regression in the extractor.
- **The ` Nitroglycerin` trim changes no score.** The extractor makes no MEDICATION prediction near that span.

## Review status (partial adjudication)

- **Queue size:** 79 unique candidates.
- **Reviewed:** 26 of 79. **Not yet reviewed:** 53 (36 CONDITION-scope, 15 DURATION, 1 MEDICATION `M04`, 1 punctuation/coordination `PC04`).
- **ADOPT (25):** C01, C02, C03, C04, C05, C06, C09, SC01, SC02, SC03, D01, D02, D03, D04, D05, D08, D09, D10, D15, M01, M02, M03, PC01, PC02, PC03. Of these, C01 and D04 retain their span unchanged, so 23 change gold.
- **Still DISCUSS, unresolved (1):** SC04, `Edema` [98,103) in `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064` (currently CONDITION in v1.2).
- **Resolved in Batch 04:** SC02 `Dyspnea` is now SYMPTOM.
- **Not queue candidates:** the two `chest pain` additions were explicitly approved and are recorded as two new rows in `gold_adjudication_log.csv`.
- **Known open items in v1.2.** These are unreviewed and unchanged: `Calcium and vitamin D combination` [4565,4598) (M04), and `mouth or jaws are still sensitive` [993,1026) (PC04). Further adjudication could move these numbers in either direction.

## Remaining error sources (from the evaluator's output only)

These are descriptions of the v1.2 error file `mtsamples_ner_errors.csv` with spans sliced from the source notes. They state counts and surface forms, not causes. The script that produces them is `error_source_summary.py`.

- **CONDITION:** 200 exact false negatives out of 216 gold spans (TP 16, FP 11), the largest share of the 419 total. Under relaxed matching FN falls only to 190. The most frequent missed surface forms are `anemia` ×4, `MGUS` ×3, `dehydration` ×3 and `impending compartment syndrome of the right upper extremity` ×3. Of the 11 false positives, 10 overlap a CONDITION gold span with different boundaries; the most frequent are `pneumonia`, `heart failure` and `hypothyroidism`, each ×2.
- **MEDICATION:** 96 exact FN out of 111 gold spans (TP 15, FP 10); relaxed FN is 94. The most frequent missed forms are `Marcaine` ×4, and `Lamictal`, `Levaquin` and `Synthroid` ×3 each. Eight of the 10 false positives are `insulin`; the others are `dexamethasone` and `Penicillin`.
- **DURATION:** **0 exact matches** (FP 4, FN 23 of 23 gold spans). The four false positives are `3 days` ×2 and `15-day` ×2; two of them overlap a DURATION gold span with different boundaries, which is why relaxed TP is 2. Missed forms include `three additional days` ×2, `x3 days` ×2 and `one week` ×2.
- **SYMPTOM:** the most false positives of any label: 59 (TP 17, FN 34). The most frequent predicted forms are `pain` ×18 and `bleeding` ×15, then `fever`, `vomiting` and `swelling` ×3 each. Only 8 of the 59 overlap any gold span (6 a SYMPTOM span, 2 a CONDITION span), so 51 overlap no gold span. Relaxed FP is 53.
- **DOSAGE and FREQUENCY:** 39 and 27 exact FN. Frequent misses are `1%` ×6 and `1 cc` ×4 (DOSAGE), and `b.i.d.` ×5 and `q.d.` ×4 (FREQUENCY). No adjudication decision so far touched either label, so their counts are identical across all three versions.

## Reproducibility

- **v1.2 evaluation command:** `python3 scripts/evaluate_mtsamples_ner.py --gold-dir data/public/mtsamples/gold_adjudicated_v1_2_20261025 --notes-dir data/public/mtsamples/notes --results-dir results/mtsamples_ner_gold30_adjudicated_v1_2_20261025`
- **Git commit:** `54b77683323f564dbbf4cb7ddbdbb4b26b1e59ac`, with uncommitted changes under `src/` and `scripts/`. The commit identifies the base only. The baseline reproduction below is what shows the code matches the earlier runs.
- **Baseline reproduction:** I re-ran the same command on the protected snapshot into scratch space. The metrics and error CSVs were byte-identical to the saved baseline in `results/mtsamples_ner_gold30_20261024_v2/` (exact P/R/F1 46.7% / 17.2% / 25.1%).
- **Integrity:** the SHA-256 hashes of the protected snapshot and of v1.1 were identical before and after the v1.2 build.
- **Files in this directory:** the evaluator's three result files, this report, `gold_change_manifest_v1_1_to_v1_2.csv`, `gold_version_comparison_3way.json`, and the scripts `build_gold_v1_2.py`, `record_batch04.py`, `compare_gold_versions_3way.py` and `error_source_summary.py`.

## Caveats

- The v1.1 results in `results/mtsamples_ner_gold30_adjudicated_v1_1_20261024/` and the original results in `results/mtsamples_ner_gold30_20261024_v2/` are untouched.
- The relaxed numbers for the baseline and v1.1 were computed fresh by `compare_gold_versions_3way.py`; they were not saved by earlier runs.
- With 53 queue candidates unreviewed, the gold is still changing. These numbers describe gold v1.2 only.
