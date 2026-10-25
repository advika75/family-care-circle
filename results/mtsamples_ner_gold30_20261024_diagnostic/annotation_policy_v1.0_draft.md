# MTSamples Annotation Policy v1.0 — Draft

**Status: Proposed policy; final human sign-off required before use to adjudicate or change any gold annotation.**  
**Version:** 1.0-draft  
**Scope:** The selected MTSamples gold annotation set. This draft preserves the existing six-label schema only: `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

This draft records the recommendations approved in principle in `adjudication_approval_checklist.md`, including the clarifications supplied for items 1, 7, and 15. It does not change the current annotations or claim that any existing span is correct or incorrect. Examples below come from that checklist, the diagnostic report, or the existing shared label guide.

## Cross-label and span policy

### Decisions 4–6: mention segmentation and exact boundaries

**Proposed decision.** Annotate every stated occurrence as a mention, including repeated, historical, and explicitly negated mentions. Use the exact source substring with zero-based Python character offsets and exclusive end (`text == source[start:end]`). Do not normalize spelling, case, abbreviation, or number words. Use the shortest complete span that identifies the entity; include meaningful modifiers that form part of the named concept, and exclude unrelated context, list markers, surrounding whitespace, sentence punctuation, and conjunctions. Preserve punctuation internal to an abbreviation such as `b.i.d.`.

Split coordinated independent mentions into separate spans. For example, label `shortness of breath` and `diaphoresis` separately in `shortness of breath & diaphoresis`; label `fever` and `chills` separately in `fever or chills`. Do not include `&`, `or`, or `and`. A span containing only `ever or chills` at source phrase `fever or chills` is incomplete; include the `f` in `fever`.

**Rationale.** One mention and boundary convention prevents long list spans, clipped spans, punctuation differences, and inconsistent treatment of conjunctions from producing avoidable exact-span disagreement. The current evaluator matches exact `(start, end, label)` tuples.

**Unresolved edge cases.** This shortest-complete-span decision conflicts in wording with the shared guide's “Longest span wins” example, `Essential hypertension` rather than `hypertension`. This draft proposes the shortest complete entity span, but how that principle applies to nested candidate phrases must be confirmed at final sign-off (see conflicts below). Review edge cases where a modifier may or may not be part of the entity name; do not silently choose a boundary precedent.

### Decision 16: overlaps and human tie-breaks

**Proposed decision.** The annotation remains flat and non-overlapping. Do not duplicate the same characters under two labels. For distinct medication-related entities, use adjacent non-overlapping spans. Where approved semantic rules do not resolve a candidate label or boundary, route it for human adjudication rather than choosing automatically.

**Examples.** `Chest pain` competes between CONDITION and SYMPTOM; predicted `insulin` overlaps gold `Humulin N. insulin`; predicted `3 units` overlaps gold `3 units per hour`.

**Rationale.** This follows the existing annotation tool's no-overlap constraint and avoids detector-driven or arbitrary tie-breaking.

**Unresolved edge cases.** Whether a construction contains one complete entity or a medication plus descriptor, and whether a numeric phrase is an amount or a rate, are governed by the label rules below. If those rules remain ambiguous, preserve the case for human review.

## Label decisions

### Decision 1: CONDITION scope, with clarification

**Proposed decision.** Include explicitly stated diagnoses. Exclude normal findings. An interpreted abnormal finding is not included by default: it can be included only after the project documents a scope rule and applies that rule consistently across notes. Tests, anatomy alone, and measurements are excluded.

**Examples.** Diagnostic-report examples include `anemia`, `MGUS`, and `dehydration` as missed CONDITION spans. The echocardiogram gold includes `Normal size right and left ventricle`, `Normal LV diastolic function`, and `Mild mitral and tricuspid regurgitation`. The acute myocardial infarction note labels `Chest pain` as CONDITION, which this draft instead assigns to SYMPTOM under Decision 2.

**Rationale.** Explicit diagnoses give a consistent core definition. The abnormal-finding clarification avoids treating normal findings and interpreted abnormalities alike without a written scope decision.

**Unresolved edge cases.** Whether interpreted findings such as regurgitation, stenosis, and masses qualify as CONDITION requires a documented, consistently applied decision. The label for diagnostic shorthand such as `diabetic` is handled under Decision 3. Do not label the full echocardiogram text as one entity; adjudicate individual abnormal findings only after the scope rule is approved.

### Decision 2: CONDITION versus SYMPTOM

**Proposed decision.** Label `chest pain` as SYMPTOM, including when it appears under a diagnosis heading, as a chief complaint, or in `PRN chest pain`. A single span cannot be both CONDITION and SYMPTOM. CONDITION is for explicitly stated diagnoses under Decision 1; SYMPTOM is for patient-experienced complaints.

**Example.** In `mtsamples_Acute_Inferior_Myocardial_Infarction`, `Chest pain` at `[19,29)` is currently gold CONDITION and predicted SYMPTOM. This draft proposes SYMPTOM consistently for that mention.

**Rationale.** Section placement or medication indication should not change the label for the same patient complaint.

**Unresolved edge cases.** A mention that is used as a diagnosis in one note and a complaint in another should be decided by what the phrase denotes in context. A phrase that remains genuinely ambiguous must receive human review; do not assign both labels.

### Decision 3: diagnostic shorthand such as `diabetic`

**Proposed decision.** Label an adjective such as `diabetic` as CONDITION only when it clearly asserts a diagnosis or disease state. Preserve the stated word and do not expand it to an unstated diagnosis name.

**Example.** `diabetic` appears as a gold CONDITION in the acute myocardial infarction note.

**Rationale.** This avoids inventing a more specific diagnosis while still capturing explicit shorthand when it functions as a diagnosis.

**Unresolved edge cases.** If the sentence does not make clear whether the adjective asserts a diagnosis or merely describes a person, mark the span for human adjudication.

### Decision 7: SYMPTOM mentions, negation, and procedural text, with clarification

**Proposed decision.** Explicit negated and historical symptom mentions remain eligible as SYMPTOM mentions. A procedural event is excluded unless the wording independently describes a patient symptom. Include symptoms that the patient is explicitly instructed to watch for; do not infer a symptom merely from a procedure or its possible complication.

**Examples.** `denies chest pain` remains a SYMPTOM mention. The thyroid-surgery phrase `small bleeding vessels were identified and bipolared` is a procedural finding, not a patient symptom by itself.

**Rationale.** This preserves mention detection for negated/historical wording while separating patient symptoms from operative events.

**Unresolved edge cases.** Determine from the wording whether a quoted complaint, a possible future complication, or operative-prose use of `pain` or `bleeding` independently describes an actual patient symptom. Keep hypothetical complications out unless they are explicitly stated as symptoms the patient is told to watch for.

### Decision 15: future symptoms

**Proposed decision.** Include explicitly stated symptoms that a patient is instructed to watch for. Do not infer or annotate a symptom from a hypothetical complication alone.

**Example.** The shared guide's SYMPTOM definition includes symptoms the patient is told to watch for; the checklist identifies risks/complications phrased as possible future symptoms as unresolved.

**Rationale.** Explicit watch-for instructions are stated symptom mentions; hypothetical complications do not license annotators to add unstated symptoms.

**Unresolved edge cases.** If an instruction names a risk without naming its symptom, do not infer the symptom. If the wording could be either an explicit watch-for symptom or a hypothetical complication, human adjudication is required.

### Decision 12: MEDICATION names, generics, and classes

**Proposed decision.** Label specific products, generic drug names, or ingredients when used as medication. Exclude broad therapeutic classes. Include salt/formulation words only when they are part of the medication name; exclude route, dosage, frequency, and surrounding prose.

**Examples.** The diagnostic report identifies `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid` among frequent FN surfaces. The checklist also raises `insulin`, `cortisone`, and `antibiotics` as context-sensitive terms.

**Rationale.** Using context to distinguish a medication from a therapeutic class avoids treating every class word as a named medication while allowing a generic drug name where the text uses it as medication.

**Unresolved edge cases.** Whether standalone `insulin` or `cortisone` denotes a generic medication versus a broader class must be decided in context. The distinction between ingredient and therapeutic class needs human adjudication when wording alone does not resolve it.

### Decision 13: `Humulin N insulin` span boundary

**Proposed decision.** In `Humulin N insulin`, label `Humulin N` if `insulin` is only a trailing generic descriptor; do not include the descriptor or following punctuation. Label standalone `insulin` when it is itself the medication named in context. Do not create overlapping nested spans.

**Example.** The diagnostic report records predicted `insulin` overlapping gold `Humulin N. insulin`.

**Rationale.** A consistent boundary distinguishes a specific name from a following descriptor and avoids partial/overlapping mentions.

**Unresolved edge cases.** Human review is required when the text does not show whether the trailing word is part of the medication name or a descriptor. Confirm whether punctuation after `N` is sentence punctuation in the source before applying the boundary.

### Decision 11: DOSAGE concentrations

**Proposed decision.** Label a concentration such as `1%` as DOSAGE only when it specifies an administered medication. Exclude unrelated percentages, vitals, lab results, weights, and dates.

**Examples.** `1%` and `1 cc` are frequent FN surfaces in the diagnostic report; the shared guide excludes vitals, labs, and weights such as `8.9%` and `10 lbs`.

**Rationale.** Requiring medication-administration context separates a medication concentration from an unrelated numeric measurement.

**Unresolved edge cases.** Where the percentage's relationship to medication administration is not explicit, human adjudication is required. Do not infer that every percentage is DOSAGE.

### Decision 10: DOSAGE rates versus FREQUENCY

**Proposed decision.** Treat a complete stated administration rate as one DOSAGE span, including its rate component: `3 units per hour`. Do not also label `per hour` as FREQUENCY. Keep distinct medication, DOSAGE, FREQUENCY, and DURATION spans adjacent and non-overlapping.

**Example.** The error report shows predicted `3 units` overlapping gold `3 units per hour`.

**Rationale.** The full quantity/rate is captured consistently and avoids assigning the same rate component to both DOSAGE and FREQUENCY.

**Unresolved edge cases.** Human review is required when it is unclear whether a time expression modifies the amount as a rate or independently states cadence. This proposed assignment narrows the otherwise broad FREQUENCY concept for rate phrases.

### Decision 14: FREQUENCY abbreviations and scope

**Proposed decision.** Label cadence expressions including `BID`, `b.i.d.`, `q.d.`, `QDay`, `daily`, `every 4 hours`, `nightly`, `PRN`, and `as needed`. Exclude routes such as `PO`. Preserve abbreviation punctuation that belongs to the abbreviation; exclude a separate terminal sentence period. Apply FREQUENCY to non-medication instructions only if the phrase states cadence and the same rule is used consistently.

**Rationale.** This handles both abbreviated and written cadence without confusing route with frequency.

**Unresolved edge cases.** If an abbreviation-ending period cannot be distinguished from a sentence period, retain the exact token boundary established by human review. Decide whether a non-medication instruction uses FREQUENCY before labeling such cases.

### Decision 8: DURATION scope

**Proposed decision.** Label how long a medication, treatment, or care instruction is to continue. Exclude symptom timelines, follow-up intervals, and procedure/test elapsed time.

**Examples.** Include an explicit treatment interval in `continue medication for 10 days`. Exclude symptom duration in `pain for 2 days`, appointment timing in `follow up in one week`, and test elapsed time in `stood on the tilt table for 20 minutes`.

**Rationale.** A time interval receives DURATION because it describes treatment/instruction duration, not merely because it contains a number and unit.

**Unresolved edge cases.** If context does not make the treatment target clear, do not infer it; adjudicate the interval. The procedure/test exclusion is more explicit than the shared guide and should be applied consistently if approved.

### Decision 9: DURATION boundaries and context

**Proposed decision.** Capture the exact interval amount and unit, including number words and meaningful modifiers. Exclude framing words such as `for`, the marker `x`, and the noun `course`; thus `x 10 days` yields `10 days`, and `15-day course` yields `15-day` when it names a treatment interval. Exclude `one-hour` when it describes a symptom episode.

**Examples.** The diagnostic report includes `three additional days`, `20 minutes`, and `one week` as frequent FN surfaces; their status depends on the scope rule above.

**Rationale.** Stable boundaries keep the interval itself while avoiding sentence scaffolding and non-DURATION temporal phrases.

**Unresolved edge cases.** A time interval with no explicit treatment target may use context only if that context rule is approved. Do not label ambiguous cases automatically.

### Decision 17: adjudication and sign-off

**Proposed decision.** Keep unresolved label/boundary cases out of automatic decisions. Record the source span, candidate label(s) from the existing six-label schema, and rationale in a separate review log; require human sign-off before applying a decision to gold.

**Examples.** The checklist names CONDITION findings, DURATION without an explicit treatment target, generic medication words, quoted/future symptoms, and overlapping candidates as human-review cases.

**Rationale.** A documented precedent supports consistent annotation while keeping current gold and evaluation snapshots intact until review is complete.

**Unresolved edge cases.** The team still needs to choose the review-log location, reviewer/sign-off convention, and how unresolved notes will be held from final completion/evaluation.

## Conflicts with existing project guidelines

These are conflicts or clarifications to resolve at final human sign-off; this draft does not edit the shared guide or silently claim precedence over it.

1. **Span length:** `data/gold/README.md` says “Longest span wins” and gives `Essential hypertension` rather than `hypertension`. Checklist item 6 approves “shortest complete span.” These are not equivalent in every nested or modifier case. This draft records shortest complete span as the proposed MTSamples rule; the owner must explicitly decide whether it supersedes the shared longest-span rule for this dataset or should be reconciled into one rule.
2. **MEDICATION scope:** The shared guide says “Specific drug names” and excludes drug classes (`antibiotics`, `NSAIDs`, `oral steroid`). This draft explicitly includes generic drug names/ingredients when used as medication. That may clarify the existing wording, but words such as `insulin` can denote either a medication or a broader class; confirm the intended boundary.
3. **DOSAGE scope:** The shared guide specifies amount plus unit and excludes unrelated vitals/labs/weights. This draft extends the span to a medication administration rate (`3 units per hour`) and makes medication concentration (`1%`) eligible in administration context. Confirm this extension and keep it distinct from FREQUENCY.
4. **CONDITION scope:** The shared guide says diagnoses and excludes tests; this draft explicitly excludes normal findings and makes interpreted abnormal findings conditional on a separately documented scope rule. This clarifies the core diagnosis rule but leaves abnormal findings unresolved by design.
5. **DURATION scope:** The shared guide excludes symptom duration and follow-up timing and defines treatment/instruction duration. This draft additionally states that procedure/test elapsed time is excluded. This appears consistent with the treatment-duration scope but is more explicit than the existing text.
6. **SYMPTOM scope:** The shared guide includes symptoms reported or watched for and excludes exam findings/labs. This draft clarifies that procedural events are excluded unless they independently describe a patient symptom, and that hypothetical complications do not create inferred symptoms. This is intended as a clarification, not a new label.
7. **Evaluation and annotation mechanics:** The policy preserves the current exact six labels, exact source-character offsets, and flat non-overlapping schema. It does not alter the evaluator's exact `(start, end, label)` metric or authorize automatic labels.
8. **MTSamples setup instructions:** `data/public/mtsamples/gold/README.md` currently tells annotators to use the shared guide. If this MTSamples-specific policy is approved, that instruction will need a later documentation update so annotators do not have to choose between the shared rule and the approved MTSamples rule. No documentation was changed as part of this draft.

## Final sign-off record

- Project owner: ____________________
- Version approved: ____________________
- Date: ____________________
- Span-length conflict resolved as: ____________________
- Remaining unresolved cases or exceptions: ____________________

**Until final sign-off, v1.0-draft is advisory only. Do not use it to modify existing gold annotations.**
