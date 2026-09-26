# Gold NER annotations

Hand-annotated entity spans for `data/raw/note_01.txt` … `note_06.txt` (all notes are **synthetic**).
Each file: `{"id", "source_file", "annotator", "entities": [{text, label, start, end}]}` with
character offsets into the raw file (`text == raw[start:end]`).

## Guidelines

| Label | Annotate | Do not annotate |
|---|---|---|
| MEDICATION | Specific drug names, including salt/formulation words that are part of the name (`metoprolol succinate`) | Drug classes (`antibiotics`, `NSAIDs`, `oral steroid`) |
| DOSAGE | Amount + unit of a medication (`500 mg`, `90 mcg`, `2 puffs`) | Vitals, labs, weights (`101.8 F`, `8.9%`, `10 lbs`) |
| FREQUENCY | How often (`BID`, `q4-6h`, `once daily`, `every 4 hours`, `nightly`); `PRN`/`as needed` is its own FREQUENCY span | Routes (`PO`) |
| DURATION | How long a treatment or instruction lasts, number + unit only (`10 days` in "x 10 days", `4 more days`) | How long a symptom has lasted (`2 days of dysuria`), follow-up timing (`follow up in 2 weeks`) |
| SYMPTOM | Symptoms the patient reports or is told to watch for | Exam findings, lab results |
| CONDITION | Diagnoses (`strep throat`, `type 2 diabetes mellitus`) | Tests (`rapid strep test`) |

Every occurrence is annotated, including negated mentions ("No cough"): the task is mention detection, not assertion status.
Longest span wins (`Essential hypertension` rather than `hypertension` inside it).
