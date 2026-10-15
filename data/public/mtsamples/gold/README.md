# Optional MTSamples gold annotations

The annotation subset contains 30 notes selected from the prepared 100-note subset with Python's deterministic `random.Random(42)` sampling. `annotation_manifest.json` records each selected note and its `pending` status. The files below are blank templates and require manual annotation.

For each note, manually identify `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM` mentions using the shared guide in `data/gold/README.md`. Do not fill entities automatically.

Launch the local review tool with `python scripts/annotate_mtsamples.py`, then open
`http://127.0.0.1:8765/`. Rule-based NER entries are suggestions only; an annotator must review
and explicitly add them before saving. The tool writes this same JSON schema and marks saved notes
as `annotated` in `annotation_manifest.json`.

Place manually reviewed annotations here as `<note-stem>.json`. Reuse the format and annotation
guidelines in `data/gold/README.md`; offsets are character offsets into the matching note in
`data/public/mtsamples/notes/`. Public generation and evaluation can run while these templates remain
blank, with NER scoring enabled after manual annotation.

After a note is fully reviewed, set its manifest status to `complete` and run
`python scripts/evaluate_mtsamples_ner.py`. Only `complete` entries are evaluated; pending and
in-progress entries are skipped. A prediction is correct only when its `(start, end, label)` exactly
matches a gold entity. Results are written to `results/mtsamples_ner_summary.json`,
`results/mtsamples_ner_metrics.csv`, and `results/mtsamples_ner_errors.csv`; error rows contain note
IDs and offsets but no note text. Metrics are micro-averaged across entities and reported per label.
For a label with no predicted or gold entities, precision/recall/F1 follow the existing zero
convention. With no completed notes, metric values are null. Results describe only the completed
subset and may not represent all 30 selected notes.
