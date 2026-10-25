# MTSamples Annotation Policy v1.0

**PROPOSED — HUMAN SIGN-OFF REQUIRED**
**Version:** 1.0 proposed for sign-off
**Scope:** Future manual adjudication of the selected MTSamples gold NER set.
**Status:** No human approval is claimed. This policy is not authorization to automatically relabel data.

This document resolves policy conflicts for future MTSamples adjudication while leaving the shared guide and setup instructions unchanged. If approved, it will govern the MTSamples set where this document explicitly differs from the shared guide. The shared guide remains unchanged for other datasets. The MTSamples setup instructions should be aligned only after final sign-off.

The manifest was checked while preparing this version: it declares 30 notes, has 30 entries, and all 30 currently have status `complete`. This policy is for future adjudication and does not change those statuses or assert that any current annotation has been reviewed under this policy. Any change to existing annotations must be separately reviewed, recorded, and evaluated as a new gold version; never silently replace the current judgments or their evaluation snapshot.

## 1. Existing label schema

Use exactly these six labels:

- `MEDICATION`
- `DOSAGE`
- `FREQUENCY`
- `DURATION`
- `CONDITION`
- `SYMPTOM`

Do not introduce additional labels or infer an entity that is not stated in the source.

## 2. Shared mention, boundary, and overlap rules

### 2.1 Mentions and offsets

Annotate each stated occurrence. Include repeated, historical, and explicitly negated mentions; the task is mention detection, not assertion classification. Include an explicit symptom the patient is instructed to watch for. Do not infer a symptom from an unstated or hypothetical complication.

Store the exact source substring with zero-based Python character offsets and an exclusive end: `text == source[start:end]`. Preserve the source spelling, case, abbreviation, and number form. Do not include leading/trailing whitespace, list markers, sentence punctuation, or conjunctions. Preserve punctuation that belongs inside an abbreviation, such as `b.i.d.`.

### 2.2 Span length: shortest complete meaningful span

**MTSamples precedence rule:** Use the **shortest complete, semantically meaningful span**, retaining modifiers necessary to identify the entity or its subtype. Exclude unrelated sentence context and framing words. Split independent coordinated mentions; do not include `and`, `or`, or `&` in entity spans.

This rule explicitly **supersedes the shared guide’s “Longest span wins” rule for future MTSamples adjudication wherever the two rules conflict**. The shared guide is not changed by this document. For example, preserve `Essential hypertension` when `Essential` specifies the diagnosis subtype; use `vomiting` rather than the surrounding phrase `episodes of vomiting` when `episodes of` is only framing. Retain a modifier such as `I-131-induced` in `I-131-induced hypothyroidism` because it specifies the condition.

Examples of splitting coordinated SYMPTOM mentions:

- `shortness of breath & diaphoresis` → `shortness of breath` and `diaphoresis`
- `fever or chills` → `fever` and `chills`

The source substring `ever or chills` is not an acceptable span for the source phrase `fever or chills`: include the initial `f` in `fever` and exclude `or`.

### 2.3 No overlapping spans

Use flat, non-overlapping spans; do not duplicate characters under multiple labels. For separate medication-related mentions, use adjacent spans. Resolve competing labels using the rules below. If they do not settle the case, send it for human adjudication rather than selecting automatically. This matches the existing annotation tool’s overlap constraint.

## 3. Label definitions and examples

### MEDICATION

**Include:** A specific medication product, generic drug name, or ingredient when used as medication. Include a salt or formulation word when it is part of the medication name. Examples include `metoprolol succinate`, `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid`.

**Exclude:** Broad therapeutic classes such as `antibiotics`, `NSAIDs`, and `oral steroid`; dosage, route, frequency, and surrounding prose.

**Boundary example:** In `Humulin N insulin`, label `Humulin N` if `insulin` is only a trailing generic descriptor. Exclude following punctuation. Label standalone `insulin` when it is itself the medication named in context. Do not make overlapping nested spans.

**Unresolved cases:** Whether standalone `insulin` or `cortisone` denotes a named medication/ingredient or a broader class depends on context. Where that distinction is unclear, refer the example for human adjudication. Confirm whether a trailing word is part of the drug name or a descriptor; do not decide from a word list alone.

### DOSAGE

**Include:** An explicit medication amount and unit, such as `500 mg`, `90 mcg`, `2 puffs`, `1 cc`, `one tablet`, or a medication concentration such as `1%` when it specifies an administered medication. A stated amount-per-time administration rate is one DOSAGE span, for example `3 units per hour`.

**Exclude:** Unrelated vitals, lab results, weights, dates, and percentages, such as `101.8 F`, `8.9%`, and `10 lbs`. Exclude medication names, routes, and separately stated cadence.

**Rate boundary rule:** In `3 units per hour`, annotate the whole rate as DOSAGE. Do not separately annotate `per hour` as FREQUENCY. Do not split the amount and its rate into overlapping spans.

**Unresolved cases:** If a percentage’s medication-administration context is unclear, do not infer DOSAGE. If a time phrase could be either part of a rate or a separate cadence, adjudicate it before annotation.

### FREQUENCY

**Include:** How often medication or an instruction is repeated. Examples include `BID`, `q4-6h`, `once daily`, `every 4 hours`, `nightly`, `PRN`, and `as needed`. Preserve abbreviation characters such as the internal periods in `b.i.d.` and `q.d.`.

**Exclude:** Routes such as `PO`; dosage amounts; and the `per hour` component of a DOSAGE rate such as `3 units per hour`.

**Unresolved cases:** A separate cadence remains FREQUENCY. Whether an instruction unrelated to medication uses FREQUENCY depends on whether it clearly expresses cadence; if context does not settle it, request human adjudication. Preserve a period belonging to an abbreviation and exclude only a separate sentence-final period; when those cannot be distinguished, document the reviewed token boundary.

### DURATION

**Include:** How long a medication, treatment, or care instruction is to continue. Capture the interval itself, including number words or modifiers that are part of it: `10 days` in `x 10 days`, or `4 more days`. In `15-day course`, use `15-day` when it expresses the treatment interval; exclude `course`.

**Exclude:** Symptom timelines, such as `2 days of dysuria` or `pain for 2 days`; follow-up timing, such as `follow up in 2 weeks`; and procedure/test elapsed time, such as `stood on the tilt table for 20 minutes`. A `one-hour` interval describing a symptom episode is not DURATION.

Exclude framing words such as `for` and the marker `x`; preserve the source’s number form. Do not treat every number-plus-time-unit phrase as DURATION.

**Unresolved cases:** If the note does not make the treatment/care-instruction target clear, do not infer one from a bare interval; refer it for human adjudication. A procedure/test duration stays excluded even when the interval is explicit.

### CONDITION

**Include:** Explicitly stated diagnoses, diseases, disorders, or injuries. Examples from the shared guide include `strep throat` and `type 2 diabetes mellitus`; other diagnostic examples include `anemia`, `MGUS`, and `dehydration`. Include meaningful subtype modifiers such as `Essential` in `Essential hypertension` and `I-131-induced` in `I-131-induced hypothyroidism`.

**Exclude:** Normal findings, tests such as `rapid strep test`, anatomy alone, and measurements. Do not label a symptom as CONDITION merely because it appears under a diagnosis heading.

**Abnormal findings:** Interpreted abnormal findings are excluded by default unless a separate scope rule is documented, approved, and consistently applied across notes. Do not make case-by-case exceptions. Examples needing a scope decision include `Mild mitral and tricuspid regurgitation`, stenosis, and masses. Normal examples such as `Normal size right and left ventricle` and `Normal LV diastolic function` are excluded.

**Shorthand:** Label `diabetic` as CONDITION only when it clearly asserts a diagnosis or disease state. Preserve the actual span; do not expand it to an unstated diagnosis name. Ambiguous adjectival use requires human adjudication.

### SYMPTOM

**Include:** A symptom the patient experiences or reports, or is explicitly instructed to watch for. Include repeated, historical, quoted, and negated mentions; for example, `denies chest pain` still contains a SYMPTOM mention. Label `chest pain` as SYMPTOM, including when it appears as a chief complaint, under a diagnosis heading, or in `PRN chest pain`.

**Exclude:** Objective exam findings, lab results, anatomy, and procedural events unless the wording independently describes a patient symptom. For example, `small bleeding vessels were identified and bipolared` describes a procedural finding, not a patient symptom. Do not infer symptoms from hypothetical complications that do not explicitly state a symptom.

**Boundary examples:** In `shortness of breath & diaphoresis`, label the two symptoms separately. In `fever or chills`, label `fever` and `chills` separately, not `ever or chills`. Use the shortest complete meaningful symptom span; for example, `vomiting` rather than the framing phrase `episodes of vomiting` where that phrase adds no part of the symptom identity.

**Unresolved cases:** Human review is required when it is unclear whether quoted or operative wording independently describes a patient symptom, or whether a risk statement explicitly instructs the patient to watch for a named symptom. Include explicit watch-for symptoms; do not infer a symptom from a possible complication alone.

## 4. Conflict-resolution procedure

1. Apply the six label definitions and the MTSamples shortest-complete-span precedence above.
2. Never assign both CONDITION and SYMPTOM to the same span. A patient complaint such as `chest pain` is SYMPTOM; a stated diagnosis is CONDITION.
3. Keep separate entities adjacent and non-overlapping. A complete dosage rate such as `3 units per hour` is DOSAGE, not a DOSAGE/FREQUENCY overlap.
4. If two rules appear to apply, use source context to determine what the phrase denotes. Do not use section headings alone to relabel a symptom as a diagnosis, and do not infer unstated concepts.
5. If an approved rule still does not resolve the label or boundary, log the source span, candidate labels from the six-label schema, and rationale for human adjudication. Do not change gold until the decision is reviewed and documented.

## 5. Decision log linked to the consistency review

This log records how the draft resolves or classifies the findings in [`policy_consistency_review.md`](policy_consistency_review.md). “Resolved” means this proposed policy states a precedence for future MTSamples adjudication; it does not mean the policy has human approval or that existing annotations were changed.

| Consistency-review finding | Proposed v1.0 resolution | Status |
|---|---|---|
| Direct contradiction 1: “Longest span wins” vs “shortest complete span” | Shortest complete, semantically meaningful span controls future MTSamples adjudication when rules conflict; the shared guide remains unchanged. | Proposed resolution; final sign-off required. |
| Direct/operational conflict 2: setup instructions direct annotators to shared guide | This policy is intended to govern future MTSamples adjudication if signed off. The setup README is not changed here and must be aligned after approval before the next annotation pass. | Policy precedence stated; documentation update pending. |
| Direct boundary conflict 3: `3 units per hour` DOSAGE vs FREQUENCY | The complete amount-per-time rate is one DOSAGE span; do not separately label `per hour` as FREQUENCY in that rate expression. | Proposed resolution; final sign-off required. |
| CONDITION/SYMPTOM examples, including gold `Chest pain` | `chest pain` is SYMPTOM even under a diagnosis heading or as chief complaint; one span cannot have both labels. | Proposed resolution; existing gold remains untouched. |
| CONDITION abnormal findings | Explicit diagnoses included; normal findings excluded; interpreted abnormal findings require a separately documented, consistently applied approved scope rule. | Default scope stated; abnormal scope unresolved until approved. |
| MEDICATION names, classes, and ingredients | Specific products/generics/ingredients used as medication included; broad classes excluded; context-sensitive examples remain adjudication cases. | Rule stated; named edge cases unresolved. |
| DURATION scope | Include treatment/care-instruction intervals; exclude symptom timelines, follow-up intervals, and procedure/test elapsed time. | Proposed resolution; final sign-off required. |
| Negated, historical, and future symptoms | Negated/historical mentions remain eligible; explicit watch-for symptoms included; hypothetical complications do not create inferred symptoms. | Preserved and clarified. |
| Coordinated spans and punctuation | Split independent coordinated mentions; exclude conjunctions and surrounding punctuation/space; preserve punctuation belonging to abbreviations. | Proposed resolution; sentence-final abbreviation punctuation remains a review edge case. |
| Overlapping spans | Keep spans flat and non-overlapping; route unresolved conflicts to human review. | Consistent with current tool constraint. |

## 6. Unresolved edge cases for human adjudication

The following are intentionally not guessed or converted into automatic decisions:

- Whether interpreted abnormalities such as regurgitation, stenosis, or masses should ever be included as CONDITION; this requires a written, approved scope applied consistently.
- Whether context identifies `diabetic`, standalone `insulin`, `cortisone`, or `antibiotics` as an explicit diagnosis, named medication/ingredient, or broader class.
- Whether `insulin` after `Humulin N` is part of the name or a descriptor, and whether the punctuation after `N` belongs in the entity span.
- Whether a time expression modifies a dosage amount as a rate or separately states cadence, except the specified `3 units per hour` rate rule.
- Whether `1%` is a medication concentration in an administration context when that relationship is not explicit.
- Whether cadence in a non-medication instruction uses FREQUENCY, and how an abbreviation’s period is bounded when it coincides with sentence-final punctuation.
- Whether a quoted complaint or operative use of `pain` or `bleeding` independently describes a patient symptom; whether a possible complication explicitly names a watch-for symptom.
- How to resolve a time interval with no clear treatment/care-instruction target. Do not infer DURATION from the number and unit alone.
- The project’s adjudication-log location, reviewer/sign-off practice, and the process for revising existing gold as a separately versioned annotation set.

Until a human approves this policy and these unresolved workflow choices are handled, continue to treat it as proposed. The existing 30 completed manifest entries and their judgments remain as they are.

## 7. Sign-off record

- Human approver: ______________________________
- Approved version: _____________________________
- Approval date: ________________________________
- Exceptions or revisions: _______________________
- Adjudication log location: _____________________

**No sign-off is recorded in this draft. Any changes to existing annotation spans must be individually reviewed, documented, and kept as a new version; this policy does not authorize automatic relabeling.**
