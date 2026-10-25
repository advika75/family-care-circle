# PROPOSED HUMAN APPROVAL CHECKLIST

**For review by the project owner. Every rule below is a proposal and requires your approval before it is used to change existing gold annotations.** This checklist is based on `adjudication_guide_proposal.md` and `diagnostic_report.md`. It uses only the existing labels: `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

For each item, select exactly one choice. If you reject a proposal, record the replacement rule; if you choose “Needs discussion,” leave affected gold unresolved until the policy is agreed. These choices do not themselves change any annotation.

## Label decisions

### 1. CONDITION scope: diagnoses and abnormal findings

- **Example:** The echocardiogram gold contains `Normal size right and left ventricle` and `Normal LV diastolic function`, as well as `Mild mitral and tricuspid regurgitation`. The proposal also calls out regurgitation, stenosis, and masses as scope questions.
- **Proposed rule:** Label explicitly stated diseases, disorders, injuries, and diagnoses. Exclude normal findings, tests, anatomy alone, and measurements. Include an interpreted abnormal finding only if you approve extending CONDITION beyond named diagnoses.
- **Consistency effect:** One scope rule prevents annotators from labeling some imaging findings but not comparable findings, and makes it possible to distinguish extractor misses from differences in what counts as a CONDITION.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 2. CONDITION versus SYMPTOM: chest pain

- **Example:** In `mtsamples_Acute_Inferior_Myocardial_Infarction`, `Chest pain` at `[19,29)` is gold CONDITION and predicted SYMPTOM; the proposal also cites `PRN chest pain`.
- **Proposed rule:** Label `chest pain` as SYMPTOM even when it appears under a diagnosis heading, as a chief complaint, or as a medication indication. A phrase cannot receive both labels.
- **Consistency effect:** This resolves a direct cross-label disagreement and prevents identical mentions from changing labels based only on section placement.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 3. Diagnostic shorthand such as “diabetic”

- **Example:** `diabetic` is a gold CONDITION mention in the acute myocardial infarction note; the proposal says not to expand it to an unstated full disease name.
- **Proposed rule:** Treat an adjective as CONDITION only when it clearly asserts a diagnosis or disease state. Preserve only the stated span; do not convert it to a longer diagnosis.
- **Consistency effect:** A rule for abbreviated or adjectival diagnoses keeps annotators from inferring different unstated disease names from the same wording.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 4. Coordinated mentions: split or combine

- **Example:** `shortness of breath & diaphoresis` and `fever or chills`.
- **Proposed rule:** Create separate SYMPTOM spans for each independent mention: `shortness of breath` plus `diaphoresis`; `fever` plus `chills`. Apply the same one-mention-per-span rule to coordinated conditions when they name separate conditions.
- **Consistency effect:** Consistent segmentation avoids one annotator labeling a whole list as one entity while another labels each mention separately.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 5. Conjunctions, whitespace, and surrounding punctuation

- **Example:** In source text `fever or chills`, the gold FN slice `[669,683)` is `ever or chills`; the proposal identifies the missing initial `f`. It also cites `x 10 days` and internal punctuation in `b.i.d.`.
- **Proposed rule:** Exclude conjunctions (`and`, `or`, `&`), list markers, leading/trailing whitespace, and sentence punctuation. Preserve punctuation that belongs inside a token such as `b.i.d.`. Keep entity text exactly equal to the source slice at its offsets; do not normalize text.
- **Consistency effect:** A shared edge rule prevents boundary drift and exact-span mismatches while retaining genuine abbreviation characters.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 6. Minimal complete span and meaningful modifiers

- **Example:** The proposal uses `I-131-induced hypothyroidism` and `Diabetes mellitus type II` as complete names; it contrasts complete findings with fragments such as `vomiting` versus `episodes of vomiting`.
- **Proposed rule:** Use the shortest complete span that identifies the entity. Include modifiers that form part of the named concept or distinguish it; exclude unrelated surrounding sentence text.
- **Consistency effect:** A common span granularity reduces exact-match differences caused by one annotator choosing a head word and another choosing the full phrase.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 7. SYMPTOM mentions, negation, and procedural text

- **Example:** The proposal contrasts the operative phrase `small bleeding vessels were identified and bipolared` with patient symptom mentions, and cites `denies chest pain` plus the diagnostic report’s frequent unmatched predictions `pain` and `bleeding`.
- **Proposed rule:** Label patient-experienced symptoms and symptoms the patient is told to watch for, including explicit negated and historical mentions. Do not label objective findings or procedural events that are not patient symptoms.
- **Consistency effect:** This separates mention detection from assertion status while reducing inconsistent labeling of the same word when it refers to a patient complaint in one context and an operative finding in another.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

## Time, dosage, and medication boundaries

### 8. DURATION scope

- **Example:** The proposal contrasts a treatment course (`continue medication for 10 days`) with symptom duration (`pain for 2 days`), follow-up timing (`follow up in one week`), and elapsed procedure time (`stood on the tilt table for 20 minutes`).
- **Proposed rule:** Label the interval for which a medication, treatment, or care instruction continues. Exclude symptom timelines, follow-up intervals, and procedure/test elapsed time.
- **Consistency effect:** This prevents similar number-plus-unit strings from receiving different labels based on annotator preference, and clarifies why some diagnostic FNs such as `20 minutes` may be outside the approved scope.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 9. DURATION wording and context-only intervals

- **Example:** `x 10 days`, `three additional days`, `15-day course`, and `one-hour` describing a symptom episode.
- **Proposed rule:** Capture the exact amount and time unit, including number words/modifiers that belong to the treatment interval; exclude framing `for`, marker `x`, and the noun `course`. Do not label `one-hour` when it describes a symptom episode. If the treatment target is not explicit, use context only if the rule you approve permits it; otherwise send it for human adjudication.
- **Consistency effect:** This aligns span boundaries and avoids inconsistent inclusion of symptom or follow-up time as treatment duration.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 10. DOSAGE rates versus FREQUENCY

- **Example:** Predicted `3 units` overlaps gold `3 units per hour`.
- **Proposed rule:** Treat the complete stated administration rate as one DOSAGE span (`3 units per hour`); do not also label `per hour` as FREQUENCY. Keep medication, DOSAGE, FREQUENCY, and DURATION spans adjacent and non-overlapping when they are distinct.
- **Consistency effect:** A single boundary convention prevents partial DOSAGE matches and conflicting assignment of a rate component to DOSAGE or FREQUENCY.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 11. DOSAGE concentrations

- **Example:** `1%` is a frequent FN surface; the proposal says to include a concentration only when it specifies the administered medication, not when it is a lab or other percentage.
- **Proposed rule:** Label a medication concentration such as `1%` as DOSAGE only in medication administration context. Exclude unrelated measurements, labs, weights, and percentages.
- **Consistency effect:** This gives annotators a common test for concentration strings that otherwise look like ordinary numeric values.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 12. MEDICATION names, generics, and broad classes

- **Example:** The proposal names `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid`; it raises `insulin`, `cortisone`, and `antibiotics` as context-sensitive examples.
- **Proposed rule:** Label a specific product, generic drug name, or ingredient when used as a medication. Exclude broad therapeutic classes; include salt/formulation words only when they form part of the medication name.
- **Consistency effect:** A shared distinction prevents annotators from alternately labeling a class as a medication or omitting an actual generic medication.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 13. MEDICATION boundary: “Humulin N insulin”

- **Example:** The prediction `insulin` overlaps gold `Humulin N. insulin`.
- **Proposed rule:** If `insulin` is only a descriptor after the specific name, label `Humulin N` and exclude the descriptor and following punctuation. Label standalone `insulin` only when it is the medication named in context. Do not create overlapping nested spans.
- **Consistency effect:** This defines whether annotators capture the specific product alone or include a generic descriptor, reducing partial exact-match disagreements.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 14. FREQUENCY abbreviation punctuation and scope

- **Example:** Frequent FN forms include `b.i.d.`, `q.d.`, and `QDay`; `daily` is a frequent unmatched prediction; `PO` is a route example.
- **Proposed rule:** Label cadence expressions including `BID`, `b.i.d.`, `q.d.`, `QDay`, `daily`, `every 4 hours`, `nightly`, `PRN`, and `as needed`. Preserve internal abbreviation periods, exclude a terminal sentence period, and exclude routes such as `PO`. Apply FREQUENCY to non-medication instructions only if approved.
- **Consistency effect:** This standardizes abbreviation edges and avoids inconsistent treatment of routes or cadence phrases outside medication directions.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 15. Quoted complaints and possible future symptoms

- **Example:** The proposal calls out quoted complaints and risks/complications phrased as possible future symptoms as unresolved; it also says to label a symptom the patient is instructed to watch for.
- **Proposed rule:** Include patient-experienced symptoms and explicit watch-for symptoms, including quoted or negated mentions; do not infer a symptom from a possible complication unless it is actually stated as a symptom mention.
- **Consistency effect:** A shared rule prevents annotators from treating quoted or prospective wording differently without regard to whether it names an actual symptom.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

## Non-overlap and unresolved cases

### 16. Flat, non-overlapping spans and human tie-breaks

- **Example:** `Chest pain` competing between CONDITION and SYMPTOM; `Humulin N insulin`; and `3 units per hour` competing between a complete dosage rate and a shorter amount span.
- **Proposed rule:** Keep entities non-overlapping. For competing labels, apply the approved semantic rule; for independent medication/dosage/frequency/duration entities, use adjacent spans. If the approved rules do not resolve a case, record it for human adjudication rather than automatically choosing a label or span.
- **Consistency effect:** This matches the existing flat annotation tool/schema and prevents arbitrary overlap resolution from changing exact-match counts.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

### 17. Human adjudication and sign-off

- **Example:** The proposal leaves CONDITION findings, duration without an explicit treatment target, generic medication words, quoted/future symptoms, and overlapping candidates for human review.
- **Proposed rule:** Keep unresolved cases out of any automatic decision. Record the source span, candidate label(s), and rationale in a separate review log; require human sign-off before any approved decision is applied to gold.
- **Consistency effect:** A recorded, reviewable decision lets all annotators apply the same precedent and preserves the current gold/evaluation snapshot until approval.
- **Approval:** [ ] Approve  [ ] Reject  [ ] Needs discussion
- **Your notes / replacement rule:** ______________________________________________

## Approval summary

Please confirm any alternative rule in the notes for each rejected item. Items marked “Needs discussion” remain unresolved and must not be applied to gold. This checklist is a policy proposal only; approving it does not authorize automatic annotation or silently alter any existing judgment.
