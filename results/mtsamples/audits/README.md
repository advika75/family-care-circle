# MTSamples audits

Reviewed evidence from the existing MTSamples outputs. No inference was rerun and no model judge or automatic labels were used. Each reviewed row records the source/output file, detector decision, `manual_judgment` (`true_issue`, `false_positive`, or `uncertain`), and a short reason.

- `retention_audit.csv` contains the seeded 40-row sample. The 25 caregiver rows are marked `uncertain`: the source note confirms the extracted entity, but saved outputs preserve the first-attempt miss list and final persona output, not the first-attempt prose needed to judge whether the matcher missed an equivalent mention. The 15 patient-summary rows remain pending because they are outside this review scope.
- `unsupported_numbers_sample.csv` contains the seeded 60-row sample, manually compared against each referenced note and output. Ambiguous timing/count flags remain uncertain.
- `safety_audit.csv` contains the 12 original unsupported medication mentions and 6 contradicted dose directives from the 11-note safety experiment. Each row links the original and post-fix outputs and records the before/after detector decision. The 18 original flags were compared against their source notes; one unsupported medication mention remains flagged after the fix. No inference was rerun.
- `audit_category_counts.csv` summarizes judgments by category.
- `regimen_candidate_patterns.csv` remains an unreviewed regex candidate list, not a recall estimate.

## Reviewed counts

- Unsupported numbers: 26 `true_issue`, 8 `false_positive`, and 26 `uncertain` among 60 flagged cases. Precision among decisive reviewed flags is 26/34 (76.5%); false negatives are not measurable from this flagged-only sample.
- Invented medications: 12 original flagged cases, all manually judged `true_issue`; 11 are no longer flagged in the post-fix outputs and one remains. This sample does not measure false negatives outside the flagged cases.
- Dosage contradictions: 6 original flagged cases, all manually judged `true_issue`; all 6 are no longer flagged in the post-fix outputs. This sample does not measure false negatives outside the flagged cases.
- Caregiver retention: 25 sampled first-attempt misses remain `uncertain`; 15 patient-summary rows are blank/pending. The saved outputs lack first-attempt prose, so neither error counts nor recall can be established for the matcher.

The unsupported-number manual precision is a flagged-case audit result, not a detector recall estimate or a measure of model quality.

## Audit integrity hold

The `mtsamples_Weight_Gain_and_Edema` row for `10 mg` is recorded as `false_positive`, but its reason says the source contains lisinopril 10 mg. The referenced source says lisinopril is on hold and does not state a dose, while the generated checklist adds 10 mg. This label/reason conflict needs human re-review. The counts above reflect the CSV as currently entered and should be treated as provisional until that row is resolved; I left its manual judgment unchanged.

The unsupported-number detector now canonicalizes audited source forms `q.4-6h`, `q.12h`, dotted `t.i.d.`, and `gm`/`grams` when checking their expanded generated forms. Rechecking the existing saved outputs (no inference) changes the count of caregiver outputs with at least one detector flag from 73/100 to 70/100. This is a detector normalization change developed from audited MTSamples cases; it is evaluation-set-specific and is not evidence of improved generation quality. Other audited false-positive cases remain for review.

To generate fresh blank templates, run `python scripts/audit_mtsamples.py --output-dir <new-directory>`. Generation refuses to overwrite an existing audit directory. The workflow records evidence and leaves all manual judgments blank.


## Evidence export for manual review

Create a read-only case evidence CSV (the target must not already exist):

```sh
python scripts/audit_mtsamples.py --export-case-evidence results/mtsamples/audits/manual_review_evidence.csv
```

It includes uncertain and blank retention rows, the documented Weight Gain and Edema `10 mg` conflict, and all safety audit rows. The export includes full source/output text, exact literal match offsets, existing judgment, a separate proposed-judgment field, and whether first-attempt prose exists in the saved record. It never edits the source audit CSVs or assigns a judgment automatically. Use a new output path for a fresh export.
