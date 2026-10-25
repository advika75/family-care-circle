# Optional MTSamples gold annotations

The MTSamples annotation subset contains 30 notes selected from the prepared 100-note subset with Python's deterministic `random.Random(42)` sampling. The current `annotation_manifest.json` declares all 30 entries `complete`. This status describes the existing annotation set; it does not assert that those annotations have been adjudicated under the policy below. Do not reset manifest statuses, replace existing judgments, or assume completed notes need re-annotation.

## Controlling annotation policy

For MTSamples, use [`annotation_policy_v1.0.md`](../../../../results/mtsamples_ner_gold30_20261024_diagnostic/annotation_policy_v1.0.md) as the dataset-specific policy. The shared guide at [`data/gold/README.md`](../../../gold/README.md) remains useful for general schema and label context and remains unchanged for other datasets. Where the approved MTSamples policy explicitly differs, it takes precedence for MTSamples only. In particular, its shortest-complete-span rule supersedes the shared guide's “Longest span wins” rule for MTSamples adjudication only.

The approved policy contains five explicitly approved decision areas and separately identifies items still pending final human review. Follow approved rules for future manual MTSamples adjudication. Do not resolve a pending or unresolved case by treating retained draft wording as approved; record it for human adjudication. Policy approval does not mean existing gold annotations have been reviewed under the policy.

## Annotation workflow

For any separately authorized future annotation or adjudication pass, open the local review tool with:

```bash
python scripts/annotate_mtsamples.py
```

Then open `http://127.0.0.1:8765/`. Rule-based NER entries are suggestions only; an annotator must review and explicitly add them before saving. Verify each span against the matching source note and confirm exact character offsets and label under the six-label schema. Do not automatically mark notes complete or overwrite existing annotations as part of policy adoption.

Gold files use `<note-stem>.json` and the existing schema. Offsets are character offsets into the matching note in `data/public/mtsamples/notes/`. The current manifest and completed annotation files are preserved. Any revision to existing spans must be reviewed and documented as a new gold version before a new evaluation is run.

## Evaluation reference

The evaluator uses only manifest entries marked `complete` and exact `(start, end, label)` matches. The historical evaluation outputs describe the gold snapshot used when they were produced. Do not rerun evaluation as part of adopting this policy; if a separately versioned gold set is later completed and approved, use the project's documented evaluation workflow for that new set and preserve prior outputs.
