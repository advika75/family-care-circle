# MTSamples gold NER diagnostic

## Scope and headline

Read-only diagnostic of the completed evaluation in `results/mtsamples_ner_gold30_20261024_v2/`. No annotations, source notes, extractor code, or evaluation artifacts were changed; no inference or evaluation rerun was performed. The saved summary reports 30 evaluated notes, 0 skipped, 529 gold entities, and 195 predicted entities. Exact matching gives 91 TP, 104 FP, and 438 FN (micro P/R/F1 0.467/0.172/0.251).

## Per-label results

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| CONDITION | 0.593 | 0.071 | 0.127 | 16 | 11 | 209 |
| DOSAGE | 0.783 | 0.480 | 0.595 | 36 | 10 | 39 |
| DURATION | 0.000 | 0.000 | 0.000 | 0 | 4 | 31 |
| FREQUENCY | 0.882 | 0.357 | 0.508 | 15 | 2 | 27 |
| MEDICATION | 0.600 | 0.134 | 0.219 | 15 | 10 | 97 |
| SYMPTOM | 0.118 | 0.205 | 0.150 | 9 | 67 | 35 |
| MICRO | 0.467 | 0.172 | 0.251 | 91 | 104 | 438 |

## Most frequent unmatched spans

Counts below are exact surface forms sliced from the source note using the error CSV offsets. “FN” is a gold span with no exact predicted `(start, end, label)` match; “FP” is a predicted span with no exact gold match. An unmatched span is not automatically a gold or extractor error.

| Label | Frequent FN spans | Frequent FP spans |
|---|---|---|
| CONDITION | `anemia` ×4; `MGUS` ×3; `dehydration` ×3 | `heart failure` ×2; `hypothyroidism` ×2; `pneumonia` ×2 |
| DOSAGE | `1%` ×6; `1 cc` ×4; `one tablet` ×3 | `0.2 units` ×1; `0.3 mg` ×1; `0.5 mL` ×1 |
| DURATION | `20 minutes` ×2; `one week` ×2; `three additional days` ×2 | `15-day` ×2; `3 days` ×2 |
| FREQUENCY | `b.i.d.` ×5; `q.d.` ×4; `QDay` ×2 | `daily` ×2 |
| MEDICATION | `Marcaine` ×4; `Lamictal` ×3; `Levaquin` ×3 | `insulin` ×8; `Penicillin` ×1; `dexamethasone` ×1 |
| SYMPTOM | ` episodes of vomiting` ×1; `25-pound weight gain` ×1; `bilateral knee pain` ×1 | `pain` ×18; `bleeding` ×15; `chest pain` ×5 |

## Source and gold examples

- **Cross-label convention / disagreement:** In `data/public/mtsamples/notes/mtsamples_Acute_Inferior_Myocardial_Infarction.txt`, “Chest pain” at offsets `[19,29)` is gold `CONDITION` and appears as an FN; the same source span is predicted `SYMPTOM` and appears as an FP. The shared label guide describes symptoms separately from diagnoses. This is evidence of a label-definition or annotation inconsistency for that occurrence; it does not establish which label a reviewer should choose.
- **Semantic boundary issue despite structurally valid offsets:** The same note contains “fever or chills” around offsets 665–683, but the gold FN span is `[669,683)` with stored text “ever or chills”. That text exactly equals the source slice, so the offset validator passes, while the entity boundary appears to omit the initial “f”. This is a boundary/content review candidate, not a global offset shift.
- **Long clinical finding coverage:** In `data/public/mtsamples/notes/mtsamples_2-D_Echocardiogram_-_1.txt`, gold CONDITION spans include full findings such as “Normal size right and left ventricle” and “Mild mitral and tricuspid regurgitation”; these appear as FNs. The shared guide defines CONDITION as diagnoses and excludes tests, but does not clearly state whether normal imaging findings or regurgitation findings count. This convention needs adjudication before attributing all of these FNs to extractor coverage.
- **Generic symptom matches:** In `data/public/mtsamples/notes/mtsamples_Total_Thyroid_Lumpectomy.txt`, predicted SYMPTOM “bleeding” occurs in the operative description “small bleeding vessels were identified and bipolared”; this looks like a procedural finding rather than a patient symptom under the guide. Separately, the error CSV has 18 unmatched predicted “pain” spans and 15 “bleeding” spans overall. Some may be missed gold mentions (including negated mentions, which the guide says to annotate); context must be reviewed case by case.
- **Exact-span boundary matching:** A read-only comparison of error-row intervals found 32 same-note, same-label FP/FN overlap pairs, including predictor “vomiting” vs gold “episodes of vomiting”, predicted “insulin” vs gold “Humulin N. insulin”, and predicted “3 units” vs gold “3 units per hour”. These are consistent with boundary disagreements under exact matching. They should be separated from true missed entities in any follow-up analysis.

## Offset and schema checks

All 529 saved entity text values matched their original source slices at the stored character offsets; there were no out-of-range spans or source-slice mismatches. The annotation tool also validates label membership, offsets, note ID/source-file agreement, and overlapping spans when it reads saved notes. Thus this run does not show a systematic character-offset shift. Structurally valid offsets do not guarantee that the selected span is semantically complete, as the “ever or chills” example illustrates.

The active six-label schema is `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`. Gold spans can still use inconsistent label choices, granularity, punctuation, or inclusion criteria while satisfying the schema. The guide says every occurrence should be annotated (including negated mentions), MEDICATION should be a specific drug name, and DURATION is for treatment/instruction duration rather than symptom duration or follow-up timing. Several observed candidates warrant a human convention check against these definitions; this report does not relabel them.

## Accepted-suggestion provenance

`src/public_ner_evaluation.py` computes `gold_entities_with_known_provenance` by counting entities whose `annotation_source` is one of `accepted_suggestion`, `edited_suggestion`, or `manual`; it counts exact `accepted_suggestion` values separately and divides that count by known-provenance entities. In this artifact: known provenance = 529, unknown = 0, accepted suggestions = 0, so **0/529 (0%)** means every gold entity is explicitly marked `manual`, and none is marked as directly accepted from a visible suggestion. It does not mean provenance was absent or that there were zero gold entities.

`AnnotationStore.save` records `manual` for direct span selection and `accepted_suggestion` only when the annotator explicitly adds a suggestion. Blind mode hides suggestions and therefore naturally yields manual provenance. The schema loader in `src/datasets.py` permits missing `annotation_source` for compatibility and does not validate its enum, while the annotation UI enforces provenance values. The evaluator treats missing/unrecognized values as unknown rather than failing. That is a validation asymmetry, but it did not affect this run: all 529 entities had the recognized `manual` value.

## Highest-priority next action

Before changing the extractor or interpreting its recall as a stable benchmark, conduct a targeted human adjudication pass on the gold conventions and exact spans, starting with CONDITION/SYMPTOM cross-label cases, long imaging findings, duration inclusion criteria, and the 32 overlap pairs. Preserve the current gold and evaluation artifacts; record any adjudication separately. After the gold protocol is consistent, classify remaining FNs by true extractor coverage gap versus unsupported span form. No extractor tuning is recommended from this diagnostic alone.

## Files inspected

- `results/mtsamples_ner_gold30_20261024_v2/mtsamples_ner_summary.json`
- `results/mtsamples_ner_gold30_20261024_v2/mtsamples_ner_metrics.csv`
- `results/mtsamples_ner_gold30_20261024_v2/mtsamples_ner_errors.csv`
- `data/public/mtsamples/gold/annotation_manifest.json` and the 30 corresponding gold JSON files
- `data/public/mtsamples/notes/` source notes referenced by the error rows
- `data/gold/README.md`, `scripts/annotate_mtsamples.py`, `src/datasets.py`, and `src/public_ner_evaluation.py`
