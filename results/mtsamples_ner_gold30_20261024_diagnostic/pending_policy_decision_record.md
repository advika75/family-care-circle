# MTSamples Pending Policy Decision Record — Approval Update

**APPROVED — HUMAN SIGN-OFF RECORDED**
**Approver:** Advika Mishra
**Approval date:** 2026-10-24
**Approved policy:** [`annotation_policy_v1.0.md`](annotation_policy_v1.0.md)

This record documents the project owner's explicit approval of all 12 recommended ADOPT decisions previously listed as pending checklist items 3–5, 7, 9, and 11–17. These decisions join the five previously approved areas in MTSamples Annotation Policy v1.0. The approved schema remains exactly `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

Approval settles the general rules described below; it does not adjudicate any existing entity span. Context-dependent examples remain for source-level human review. Do not automatically relabel annotations.

## Approved decision record

### Checklist item 3 — CONDITION shorthand (`diabetic`)

**Decision: ADOPT.** Label the exact word `diabetic` as CONDITION when the source clearly asserts the patient's diagnosed disease state. Do not expand it to an unstated diagnosis; send ambiguous adjectival uses to human review.

**Example:** AMI gold CONDITION `[169,177)` is `diabetic`; the discharge-summary `diabetic gastroparesis` span `[1062,1084)` is an explicit diagnosis example. The exact threshold for ambiguous adjectival contexts remains a case-level question.

### Checklist item 4 — Coordinated entities

**Decision: ADOPT.** Split independently meaningful entities into separate spans. Keep coordinated locations together when they modify one diagnosis. Apply this consistently across all six labels, subject to the label definitions.

**Example:** AMI SYMPTOM `[550,583)` currently combines `shortness of breath & diaphoresis`; Escharotomy CONDITION `[54,122)` describes one burn diagnosis across several locations. The span example is evidence for future review, not a relabel instruction.

### Checklist item 5 — Conjunctions, whitespace, and punctuation

**Decision: ADOPT.** Exclude conjunctions, leading/trailing whitespace, and external punctuation. Preserve punctuation belonging to abbreviations such as `b.i.d.`. Apply a consistent terminal-period convention and refer ambiguous boundaries for review.

**Examples:** AMI SYMPTOM `[669,683)` is `ever or chills`; AMI `[622,643)` includes leading whitespace; Bunionectomy FREQUENCY `[5934,5940)` is `b.i.d.`. Existing spans are unchanged pending individual review.

### Checklist item 7 — Negated, historical, and procedural symptoms

**Decision: ADOPT.** Include explicit symptoms when negated or historical. Exclude procedural events and objective findings unless they independently describe a patient symptom. Do not infer unstated symptoms.

**Examples:** The AMI source says “He denies any fever or chills”; the gold span `[669,683)` is a negated mention with a separate boundary issue. The thyroid source phrase “small bleeding vessels were identified and bipolared” has no corresponding gold SYMPTOM span and remains a context example.

### Checklist item 9 — DURATION boundaries and context

**Decision: ADOPT.** Include treatment and care-instruction intervals with meaningful modifiers; exclude separate framing markers/nouns when not part of the interval. Require clear context identifying the treatment or care instruction. Retain the already approved exclusions for symptom timelines, follow-up intervals, and procedure/test elapsed time.

**Examples:** Discharge-summary `three additional days` spans `[3145,3166)` and `[3202,3223)` are treatment examples. AMI `one-hour.` `[1123,1132)` and Tilt Table Test `20 minutes` `[297,307)` / `[405,415)` are review candidates under the approved exclusions. Do not change them automatically.

### Checklist item 11 — Medication concentrations as DOSAGE

**Decision: ADOPT.** Label a percentage as DOSAGE only when source context explicitly identifies it as a medication concentration, such as administered Lidocaine `1%`. Exclude unrelated measurements such as LVEF `51%`; do not infer a medication relation from the percentage alone.

**Examples:** Gold `1%` appears in injected Lidocaine `[1554,1556)` and local anesthetic context `[644,646)`. Ambiguous concentration contexts require human review.

### Checklist item 12 — Medication names, ingredients, and classes

**Decision: ADOPT.** Include specific products, generic drug names, or ingredients when used as medication; exclude broad therapeutic classes. Use source context to distinguish a medication mention from a class reference.

**Examples for source-level review:** `prophylactic antibiotics` `[2648,2672)`, standalone `insulin` `[480,487)`, and `cortisone` `[1198,1207)`. Their existing labels are not changed by this policy update.

### Checklist item 13 — Product name versus descriptor (`Humulin N insulin`)

**Decision: ADOPT.** Label the specific product alone when a following generic term is merely a descriptor. Include the generic term only if it is part of the actual medication name or independently used as a medication mention. Preserve the exact source span and resolve punctuation consistently.

**Example:** AMI gold MEDICATION `[1708,1726)` is `Humulin N. insulin`. Whether `insulin` is a descriptor and how the period is bounded requires source-level human review.

### Checklist item 14 — FREQUENCY expressions and route exclusions

**Decision: ADOPT.** Label explicit cadence expressions such as `b.i.d.`, `QDay`, `PRN`, `daily`, and `every 4 hours` as FREQUENCY. Exclude routes such as `PO` and `p.o.`. Preserve abbreviation-internal punctuation and distinguish sentence punctuation. Include non-medication cadence only when it clearly expresses how often an action occurs.

**Examples:** Verified gold includes `b.i.d.` `[5934,5940)`, `QDay` `[1701,1705)`, and `PRN` `[1796,1799)`. Ambiguous terminal punctuation or cadence remains for review.

### Checklist item 15 — Quoted and explicit watch-for symptoms

**Decision: ADOPT.** Include explicitly named symptoms in care instructions telling a patient to watch for them. Quotation alone does not disqualify a symptom. Do not infer symptoms from hypothetical complications; hold ambiguous quoted wording for review.

**Example:** The source-only Well-Child note instructs calling if the patient has “fever, feeding problems or breathing problems.” No selected gold annotation for that note was identified, so this example does not establish a gold change.

### Checklist item 16 — Non-overlapping spans and tie-breaks

**Decision: ADOPT.** Keep annotations flat and non-overlapping under the six-label schema. Apply approved semantic rules first; record and refer unresolved label conflicts to a human reviewer.

**Evidence:** The verified pre-adjudication snapshot has 0 overlaps among 529 gold entities. This rule does not itself change any existing gold span.

### Checklist item 17 — Adjudication log, review, and sign-off workflow

**Decision: ADOPT.** For every adjudication, record note ID and source filename; exact source text and character offsets; existing and proposed label/span; rationale and evidence; reviewer and decision date; final decision; and gold-version reference. Preserve the current snapshot. Put revised annotations in a separate gold version, validate source slices and offsets, and mark review complete only after the required human decision and validation.

**Operational item still to establish:** The authoritative adjudication-log location must be selected before annotation begins. This approval does not itself start adjudication or evaluation.

## Remaining case-level review

The rules are approved, while individual applications remain open where context is ambiguous. Review, without assuming an answer, the identified `Humulin N. insulin`, `prophylactic antibiotics`, standalone `insulin`, `cortisone`, unclear medication concentrations, unclear rate-versus-cadence expressions, abbreviation terminal periods, ambiguous quoted or operative symptoms, and intervals without a clear treatment/care target. Record source evidence and human decisions in the adjudication log once its location is established.

## Snapshot and research-integrity status

The pre-adjudication snapshot is documented at [`gold_snapshot_verification.md`](gold_snapshot_verification.md) and located at `data/public/mtsamples/gold_adjudication_v1_20261024/`. It contains the current-working-tree manifest and all 30 annotation JSON files; verification recorded 529 entities, no invalid offsets or source-slice mismatches, and no overlaps. This approval update does not modify that snapshot, the original gold annotations, the manifest, source notes, code, inference outputs, or experiment/evaluation results. No adjudication or evaluation has been performed as part of this approval update.
