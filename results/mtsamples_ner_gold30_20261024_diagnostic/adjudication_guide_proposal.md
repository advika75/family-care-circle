# PROPOSAL — MTSamples Gold NER Adjudication Guide

**Status: Draft for human review and approval. Do not apply this proposal to the existing gold annotations until the decisions at the end are approved.**

This proposal responds to examples in `diagnostic_report.md`. It changes no annotation, manifest, extractor, metric, or experiment output. Existing labels remain `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

## Shared mention and span rules

1. Annotate each distinct mention in the source note, including repeated, historical, and negated mentions, consistent with the current mention-detection guide. Do not infer an entity that is not stated.
2. Save the exact source substring with zero-based Python character offsets and an exclusive end: `text == source[start:end]`. Never normalize spelling, case, abbreviation, or number words.
3. Use the shortest complete span that identifies the entity. Include a modifier only when it is part of the named concept or needed to distinguish it (for example, `I-131-induced hypothyroidism`). Exclude leading/trailing spaces, list numbers, sentence punctuation, and conjunctions. Keep punctuation that belongs inside a token/abbreviation (for example, the internal periods in `b.i.d.`).
4. Split coordinated independent mentions into separate entities. For example, propose separate SYMPTOM spans for `shortness of breath` and `diaphoresis` in `shortness of breath & diaphoresis`, and separate spans for `fever` and `chills` in `fever or chills`. Do not include `and`, `or`, or `&` in either span.
5. The annotation format/tool is flat and rejects overlapping spans. Use adjacent, non-overlapping spans for distinct entities such as a medication and its dosage. Do not create duplicate spans. When a phrase appears to fit two labels, apply the label decision rules below rather than recording the same characters twice. If the text cannot be resolved under an approved rule, send it for human adjudication and do not guess.

## Label proposals

### MEDICATION

**Proposed rule:** Label a named medication mention: a specific product, generic drug name, or ingredient used as a medication. Include a multiword name and a salt/formulation word when it is part of the name. Exclude dose, route, frequency, and broad therapeutic classes. Capture each occurrence.

**Diagnostic examples:** `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid` were frequent FN surfaces. In the overlap example, the prediction `insulin` overlaps gold `Humulin N. insulin`.

**Proposed boundaries and ambiguities:** For `Humulin N insulin`, label `Humulin N` if `insulin` is only a generic descriptor following the specific name; label standalone `insulin` when it is itself the named generic medication in context. Exclude punctuation after a name. Whether words such as `insulin`, `cortisone`, or `antibiotics` name an actual drug versus a class depends on context; do not resolve from a word list alone.

**Human adjudication needed:** Approve whether standalone generic substances such as `insulin` count as MEDICATION under this study, and whether the suffix in constructions like `Humulin N insulin` is included. Agree how to handle broad classes versus generic active ingredients.

### DOSAGE

**Proposed rule:** Label an explicit medication amount with its unit (for example, `500 mg`, `2 puffs`, `1 cc`, or a concentration such as `1%` when it specifies the administered medication). Exclude unrelated vitals, lab results, weights, and dates. Keep DOSAGE separate from the medication and frequency spans.

**Diagnostic examples:** Frequent FN spans include `1%`, `1 cc`, and `one tablet`. An overlap pair has predicted `3 units` against gold `3 units per hour`.

**Proposed boundaries and ambiguities:** Include the complete amount and unit. For a stated infusion/administration rate, this proposal includes the rate component as part of DOSAGE (for example, `3 units per hour`), rather than splitting `per hour` into FREQUENCY. Exclude introductory words such as `take` or `give`; preserve a spelled-out amount exactly. A percentage should count only when it is a medication concentration in administration context, not a lab or other percentage.

**Human adjudication needed:** Confirm the proposed treatment of rate phrases (`3 units per hour`) and concentrations (`1%`). In particular, decide whether rate/time belongs in DOSAGE or whether the schema should represent it another way before annotators encounter these cases.

### FREQUENCY

**Proposed rule:** Label the phrase that states how often a medication or instruction is repeated: `BID`, `b.i.d.`, `q.d.`, `QDay`, `daily`, `every 4 hours`, `nightly`, `PRN`, and `as needed`. Include the full frequency expression, but not a route such as `PO` or the dosage amount.

**Diagnostic examples:** Frequent FN forms include `b.i.d.`, `q.d.`, and `QDay`; `daily` is a frequent unmatched prediction.

**Proposed boundaries and ambiguities:** Preserve the source abbreviation and its internal periods; exclude a terminal sentence period if it is not part of the abbreviation. Label `daily` only when it expresses administration cadence, not merely a general temporal adjective. Keep `PRN` and `as needed` as FREQUENCY under the existing guide.

**Human adjudication needed:** Confirm punctuation conventions for abbreviations at sentence boundaries and whether non-medication instructions with a cadence use the same label. Route/frequency combinations must remain non-overlapping.

### DURATION

**Proposed rule:** Label the exact time interval for which a medication, treatment, or care instruction is to continue. Use the amount plus time unit; exclude framing words such as `for` and the marker `x` (so `x 10 days` yields `10 days`). Preserve number words and modifiers that are part of the interval (for example, `three additional days`).

**Diagnostic examples:** Frequent FN spans include `three additional days`, `20 minutes`, and `one week`; FPs include `3 days` and `15-day`. The existing shared guide already excludes symptom duration and follow-up timing.

**Proposed boundaries and ambiguities:** Continue excluding how long a symptom has lasted (for example, `pain for 2 days`), appointment timing (`follow up in one week`), and elapsed procedure/test time (`stood on the tilt table for 20 minutes`). Do include an explicit treatment course (`continue medication for 10 days`). For hyphenated forms such as `15-day course`, include `15-day` only if it expresses the treatment interval; exclude the noun `course`.

**Human adjudication needed:** Confirm exclusion of procedure/test duration and follow-up intervals; diagnostic examples show these may have been mixed into gold. Decide if a time phrase without an explicit treatment target can be included from context alone. Decide whether `one-hour` is a duration when it describes a symptom episode (proposal: no).

### CONDITION

**Proposed rule:** Label an explicitly stated disease, disorder, injury, or diagnosis. Include the complete disease name and qualifiers that identify it, such as `Diabetes mellitus type II` or `I-131-induced hypothyroidism`. Include repeated diagnosis mentions. Do not label tests, anatomy alone, measurements, or normal findings as conditions.

**Diagnostic examples:** `anemia`, `MGUS`, and `dehydration` are frequent FN surfaces. `Chest pain` at `[19,29)` in the acute myocardial infarction note is gold CONDITION while the same text is predicted as SYMPTOM. The echocardiogram note has gold spans such as `Normal size right and left ventricle` and `Normal LV diastolic function`, as well as `Mild mitral and tricuspid regurgitation`.

**Proposed boundaries and ambiguities:** Do not label a symptom (for example, chest pain) as CONDITION merely because it appears under a diagnosis heading or alongside a disease. Label the explicit diagnosis, not the entire sentence. This proposal would exclude normal findings and measurements. It would include an explicitly interpreted abnormality (for example, diagnosed regurgitation or stenosis) only if the team approves expanding CONDITION beyond diagnoses to abnormal clinical findings. An adjective such as `diabetic` is a condition only when it clearly asserts a diagnosis/state; do not expand it to an unstated full disease name.

**Human adjudication needed:** Decide whether CONDITION includes abnormal imaging/exam findings or only named diagnoses; decide how to label abnormalities like regurgitation, stenosis, and masses; decide whether diagnosis headings affect borderline terms. Review the report's echocardiogram findings and `Chest pain` cross-label case before applying this rule.

### SYMPTOM

**Proposed rule:** Label a patient-experienced symptom or a symptom the patient is instructed to watch for. Include explicit negated and historical mentions as mentions, consistent with the current guide. Do not label objective exam findings, lab results, anatomy, or procedural events that are not patient symptoms.

**Diagnostic examples:** Frequent unmatched predictions include `pain` and `bleeding`. The thyroid surgery note's phrase `small bleeding vessels were identified and bipolared` is a procedural finding, not a patient-reported bleeding symptom under this proposal. The acute myocardial infarction note's `Chest pain` is a SYMPTOM, even when it appears as the chief complaint or medication indication.

**Proposed boundaries and ambiguities:** Use the complete symptom phrase without attached conjunctions: split `shortness of breath & diaphoresis` into two spans; split `fever or chills` into two. In the source phrase `fever or chills`, `fever` must include its initial `f`; a span `ever or chills` is not an acceptable boundary. Do not tag a generic word such as `pain` in a procedure description unless it refers to a patient symptom or a symptom being discussed. Tag negated mentions such as `denies chest pain` because the task is mention detection, not assertion classification.

**Human adjudication needed:** Confirm how to handle risks/complications phrased as possible future symptoms, quoted complaints, symptom lists joined by conjunctions, and generic symptom words in operative prose. Resolve the cross-label `Chest pain` example as SYMPTOM if the proposed definition is approved.

## Overlap and disagreement resolution

Apply this precedence by meaning, not by which detector produced the span:

1. A disease/diagnosis is CONDITION; a patient-experienced complaint is SYMPTOM. A phrase cannot be both. Under the proposal, `chest pain` is SYMPTOM, including when repeated in `PRN chest pain`.
2. Keep MEDICATION, DOSAGE, FREQUENCY, and DURATION as distinct spans when adjacent. A dosage span must not absorb the medication name or cadence. Under the proposal, an explicit amount plus administration rate is one DOSAGE span (`3 units per hour`); do not also label `per hour` as FREQUENCY.
3. Use the minimal complete named span. Prefer the complete gold concept over a nested generic fragment: e.g., `Humulin N` rather than a separate overlapping `insulin`, subject to the medication decision above. Do not create both a broad span and a contained span for the same concept.
4. Split independent coordinated mentions; do not span across conjunctions. Overlapping candidate labels or uncertain boundaries go to the adjudication log for a human decision. Do not force an automatic tie-break or modify existing gold in place.

## Decisions requiring approval before use

1. **CONDITION scope:** diagnoses only, or diagnoses plus interpreted abnormal findings? Exclude normal findings either way?
2. **CONDITION vs SYMPTOM:** approve `chest pain` as SYMPTOM regardless of section/indication context; define the treatment of diagnostic shorthand such as `diabetic`.
3. **Granularity:** split coordinated symptoms/conditions into one entity per mention; approve minimal-complete spans and exclusion of conjunctions/punctuation.
4. **DURATION scope:** approve exclusion of symptom duration, follow-up timing, and procedure/test elapsed time; decide ambiguous intervals supported only by context.
5. **DOSAGE rates/concentrations:** approve including `/per hour` in DOSAGE and whether medication concentration forms such as `1%` qualify.
6. **MEDICATION identity:** approve generic drug substances versus broad classes, and whether a suffix such as `insulin` is excluded after a specific name (`Humulin N`).
7. **Manual adjudication workflow:** decide where unresolved span/label cases will be recorded and how a second reviewer will sign off before any gold changes.

Until these decisions are approved, this document is advisory only. Any subsequent changes to gold should be made by a human reviewer in a separately reviewed workflow, preserving the current annotation and evaluation snapshot.
