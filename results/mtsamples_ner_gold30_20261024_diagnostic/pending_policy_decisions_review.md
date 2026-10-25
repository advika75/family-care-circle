# Pending MTSamples Policy Decisions Review

**Status: Recommendations for human review only. Nothing in this report approves a pending checklist item or changes the approved MTSamples policy.** The current approved policy explicitly leaves checklist items 3–5, 7, 9, and 11–17 pending. This report preserves the six-label schema: `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

The proposed recommendations below are intended to make future annotation consistent. They must be reviewed and approved before being used to resolve disputed gold. Existing annotations and evaluation metrics remain as recorded.

## Item 3 — Diagnostic shorthand such as “diabetic”

- **Decision:** Whether an adjectival form is a CONDITION, and whether to retain only the stated word or expand it to an implied diagnosis.
- **Examples in the documents:** Positive candidate: `diabetic`, identified as a gold CONDITION in `mtsamples_Acute_Inferior_Myocardial_Infarction`. The draft proposes labeling it only when it clearly asserts a diagnosis or disease state, preserving the word without expansion. No explicit negative phrase example is supplied; the draft's negative principle is not to infer an unstated diagnosis.
- **Possible gold impact:** This named `diabetic` span could be affected if its context does not clearly assert a diagnosis. The consistency review does not report a count of shorthand spans affected.
- **Recommendation (not approved):** Label the exact word `diabetic` as CONDITION only when the sentence asserts the patient's diagnosis or disease state. Do not expand it to an unstated condition. If the grammar/context is ambiguous, hold for adjudication rather than infer.
- **Human decision needed:** Confirm the semantic threshold for “clearly asserts” and whether the cited gold context meets it.

## Item 4 — Coordinated mentions: split or combine

- **Decision:** Whether independent entities joined in a list or coordination receive separate spans, including coordinated conditions.
- **Examples in the documents:** `shortness of breath & diaphoresis` → proposed separate SYMPTOM spans; `fever or chills` → proposed `fever` and `chills`. The checklist proposes the same one-mention-per-span approach for coordinated conditions but supplies no CONDITION example. No explicit negative example of a single entity that should remain combined is supplied.
- **Possible gold impact:** The diagnostic report identifies the gold slice `ever or chills` in `mtsamples_Acute_Inferior_Myocardial_Infarction` as a clipped boundary candidate. It does not provide a full inventory of coordinated gold spans or say how many would be segmented differently.
- **Recommendation (not approved):** Split only when the coordinated terms independently name separate entities; exclude the conjunction. Keep a phrase together when its parts jointly form one entity name. The latter distinction needs examples approved by a reviewer before use.
- **Human decision needed:** Confirm whether the same coordination rule applies across all six labels, and supply a CONDITION example if intended.

## Item 5 — Conjunctions, whitespace, and surrounding punctuation

- **Decision:** Which neighboring characters belong in an entity span, including conjunctions, list punctuation, and periods in abbreviations.
- **Examples in the documents:** The gold FN slice `[669,683)` is `ever or chills` for source phrase `fever or chills`; the draft identifies the missing initial `f`. `x 10 days` illustrates a duration marker, and `b.i.d.` illustrates punctuation internal to an abbreviation. The shared schema requires exact source-slice offsets; the shared guide does not define these edge boundaries.
- **Possible gold impact:** The `ever or chills` span is a directly identified gold boundary candidate. The consistency review notes that exact-boundary changes can alter exact-span metrics. The listed duration and abbreviation examples are examples for adjudication; no additional affected gold IDs are identified in these documents.
- **Recommendation (not approved):** Prefer the entity text itself, excluding a separate conjunction and outer whitespace/punctuation; retain punctuation that is part of an abbreviation token. Keep the saved text exactly equal to the source slice. When the final period of an abbreviation is also sentence-final, require a documented boundary decision rather than applying a guess.
- **Human decision needed:** Approve a punctuation convention, particularly the sentence-final abbreviation case, and decide whether/how to revise the clipped gold span in a separately reviewed gold version.

## Item 7 — SYMPTOM mentions, negation, and procedural text

- **Decision:** Whether the task includes historical, negated, or patient-directed watch-for mentions, and how to distinguish patient symptoms from procedural/objective wording.
- **Examples in the documents:** `denies chest pain` is a negated mention; `small bleeding vessels were identified and bipolared` is the operative example proposed as a procedural finding rather than a patient symptom. The shared guide says every occurrence is annotated, including negated mentions, and SYMPTOM covers symptoms reported or that the patient is told to watch for; it excludes exam findings and lab results. The diagnostic report also records unmatched predicted `pain` (18) and `bleeding` (15), and a `bleeding` prediction in the operative passage. These counts are not judgments that each span is or is not gold.
- **Possible gold impact:** The diagnostic report does not identify specific existing gold spans whose inclusion turns on negation/history/procedural context, apart from the broader symptom disagreements. The operative `bleeding` example is an identified prediction/context case, not an identified gold annotation to remove.
- **Recommendation (not approved):** Treat mention status separately from assertion status: include an explicitly stated patient symptom even if negated or historical; include an explicitly named symptom the patient is told to watch for; do not label a procedural/objective finding unless it independently describes a patient symptom. Review each context before classifying `pain` or `bleeding`.
- **Human decision needed:** Confirm the historical and negated scope and adjudicate quoted, operative, and prospective contexts. Chest pain's SYMPTOM label is already approved; this pending item concerns broader eligibility and context rules, not a reversal of that approved label.

## Item 9 — DURATION wording and context-only intervals

- **Decision:** Exact boundaries for treatment-duration phrases and whether context can supply an unstated treatment target.
- **Examples in the documents:** Proposed positive forms: `x 10 days`, `three additional days`, and `15-day course` (capture the interval, not `x` or `course`). Proposed negative: `one-hour` when it describes a symptom episode. The shared guide gives `10 days` in “x 10 days” and `4 more days` as treatment/instruction duration, while excluding `2 days of dysuria` and `follow up in 2 weeks`.
- **Possible gold impact:** The diagnostic report lists `three additional days` twice and `one week` twice among DURATION FNs; it lists `15-day` twice and `3 days` twice among DURATION FPs. The consistency review also identifies two `20 minutes` FN surfaces as possible procedure-time cases under the approved item 8 scope. The artifacts summarized here do not assign all these rows to item 9 or give their note IDs, so those are review candidates rather than confirmed relabels.
- **Recommendation (not approved):** Capture the complete interval expression, including number words and modifiers that belong to the interval; exclude separate framing such as `for`/`x` and the noun `course`. Do not infer the target from a bare interval unless the surrounding instruction unambiguously identifies treatment/care. If not clear, adjudicate. The approved scope exclusions from item 8 remain in force independently.
- **Human decision needed:** Decide what contextual evidence is enough to identify a treatment target and confirm the exact boundary examples.

## Item 11 — DOSAGE concentrations

- **Decision:** Whether a percentage is a medication concentration and therefore DOSAGE, rather than a lab/measurement percentage.
- **Examples in the documents:** Proposed positive: `1%` when it specifies an administered medication. Negative examples in the shared guide include unrelated `8.9%`, vitals `101.8 F`, and weight `10 lbs`; the draft also says not to infer a concentration relationship when context is unclear.
- **Possible gold impact:** `1%` is listed six times among DOSAGE FN surface forms. The diagnostic report does not provide note IDs or source contexts for these six occurrences, so it cannot establish that all six are medication concentrations.
- **Recommendation (not approved):** Label a percentage DOSAGE only when the source context explicitly connects it to the administered medication as concentration. Otherwise do not infer; send ambiguous cases to human review. Keep unrelated measurement/lab percentages out.
- **Human decision needed:** Confirm what wording is sufficient evidence of medication concentration, then review the six source contexts before changing any gold.

## Item 12 — MEDICATION names, generics, and broad classes

- **Decision:** Distinguish named products/generic medications or ingredients from therapeutic classes and context-dependent terms.
- **Examples in the documents:** Positive named examples: `Marcaine`, `Lamictal`, `Levaquin`, `Synthroid`, and shared-guide `metoprolol succinate`. Negative class examples: `antibiotics`, `NSAIDs`, and `oral steroid`. Context-sensitive terms named in the documents: `insulin` and `cortisone` (the checklist also flags `antibiotics` by context).
- **Possible gold impact:** The diagnostic report lists `Marcaine` ×4, `Lamictal` ×3, and `Levaquin` ×3 as MEDICATION FNs, and `insulin` ×8 as MEDICATION FPs. These are detector/gold mismatches, not evidence by themselves that the gold labels should change. No specific `cortisone` gold occurrence is identified.
- **Recommendation (not approved):** Include a specific product or generic drug name when it denotes medication in context; exclude a broad class. Treat ingredient status contextually and do not classify by a word list alone. Preserve the exact source span.
- **Human decision needed:** Define what contextual evidence distinguishes a medication ingredient from a class, particularly for `insulin`, `cortisone`, and `antibiotics`; review source contexts before adjudicating identified mismatches.

## Item 13 — MEDICATION boundary: “Humulin N insulin”

- **Decision:** Whether a generic descriptor after a specific product name belongs in the MEDICATION span.
- **Examples in the documents:** The diagnostic report gives predicted `insulin` versus gold `Humulin N. insulin`; the checklist describes the prediction as overlapping that gold span. Proposed rule: when `insulin` is only a descriptor, label `Humulin N`, excluding descriptor and following punctuation; label standalone `insulin` when it is the medication named in context. No separate negative phrase is given.
- **Possible gold impact:** The `Humulin N. insulin` gold boundary is directly identified as an overlap/boundary disagreement. The documents do not state whether the period is source punctuation or part of the gold string beyond showing it in the span.
- **Recommendation (not approved):** Prefer the complete specific product name alone when the following generic noun is merely a descriptor; include a word only when it is part of the product name or is itself a separate medication mention. Do not create nested overlapping spans.
- **Human decision needed:** Inspect the source substring and determine both whether `insulin` is descriptor versus name and whether the period belongs to the entity. Do not adjudicate from the artifact surface alone.

## Item 14 — FREQUENCY abbreviation punctuation and scope

- **Decision:** Which cadence forms are FREQUENCY, how abbreviation periods are bounded, and whether non-medication instructions can receive FREQUENCY.
- **Examples in the documents:** Proposed positive forms: `BID`, `b.i.d.`, `q.d.`, `QDay`, `daily`, `every 4 hours`, `nightly`, `PRN`, and `as needed`. Negative: route `PO`. The shared guide includes `BID`, `q4-6h`, `once daily`, `every 4 hours`, `nightly`, and `PRN`/`as needed`, and excludes routes.
- **Possible gold impact:** The diagnostic report lists `b.i.d.` ×5, `q.d.` ×4, and `QDay` ×2 among FREQUENCY FNs, and `daily` ×2 among FREQUENCY FPs. It does not identify the underlying notes or establish that the proposed extension caused each mismatch.
- **Recommendation (not approved):** Retain the shared-guide cadence/route distinction. Preserve punctuation intrinsic to a recognized abbreviation; exclude a separate sentence-final period. Apply FREQUENCY to non-medication instructions only when the instruction clearly expresses repeated cadence, and send ambiguous scope to review.
- **Human decision needed:** Approve the exact abbreviation inventory and sentence-final-period rule, and decide the non-medication instruction scope.

## Item 15 — Quoted complaints and possible future symptoms

- **Decision:** Whether quoted or prospective language counts as SYMPTOM, and when a possible complication names a symptom rather than merely implying one.
- **Examples in the documents:** The checklist identifies quoted complaints and risks/complications as unresolved, and cites explicit watch-for symptoms. The draft says not to infer a symptom from a hypothetical complication. No specific quoted source phrase or note ID is supplied; `denies chest pain` is separately cited for negation under item 7.
- **Possible gold impact:** No specific current gold span is identified in the reviewed documents as a quoted or future-symptom annotation. The SYMPTOM FP counts for `pain` and `bleeding` are aggregate forms and cannot resolve this question without their individual contexts.
- **Recommendation (not approved):** Include a named symptom explicitly stated as something to watch for; do not infer a symptom from a complication when no symptom is named. Treat quoted language according to whether it actually reports/describes a patient symptom in context; hold ambiguous quotations for review.
- **Human decision needed:** Confirm quotation scope and the threshold for an explicit watch-for instruction; adjudicate actual note contexts rather than hypothetical phrasings.

## Item 16 — Flat, non-overlapping spans and human tie-breaks

- **Decision:** Whether gold spans are strictly flat/non-overlapping and what to do when candidate labels or boundaries compete.
- **Examples in the documents:** Competing cases listed are `Chest pain` (CONDITION versus SYMPTOM), `Humulin N insulin`, and `3 units per hour`. The current annotation tool rejects overlapping spans. The diagnostic report identifies 32 same-note, same-label FP/FN interval-overlap pairs, including predicted `vomiting` vs gold `episodes of vomiting`, `insulin` vs gold `Humulin N. insulin`, and `3 units` vs gold `3 units per hour`.
- **Possible gold impact:** The three examples are exact boundary/label review candidates, but two subdecisions are already approved: `chest pain` is SYMPTOM and `3 units per hour` is one DOSAGE span. The general overlap/tie-break rule remains pending. The 32 interval overlaps describe prediction-versus-gold errors, not necessarily overlapping gold annotations.
- **Recommendation (not approved):** Keep each gold mention represented by a single non-overlapping span; use approved label/boundary decisions where applicable and send unresolved conflicts to human review. Tool rejection is an implementation constraint, not sufficient evidence that every policy aspect has approval.
- **Human decision needed:** Confirm flat spans as the project-wide MTSamples convention and define a review-log/tie-break process for conflicts not settled by approved rules.

## Item 17 — Human adjudication and sign-off

- **Decision:** What to do with unresolved examples, how to document a precedent, and what approval is required before existing gold changes.
- **Examples in the documents:** The policy lists unresolved interpreted abnormalities, `diabetic`, `insulin`/`cortisone`/`antibiotics`, `Humulin N insulin`, ambiguous rate/cadence, `1%`, abbreviation punctuation, quoted/procedural symptoms, and unclear treatment targets. The checklist proposes recording source span, candidate labels, and rationale in a separate review log. It provides no positive/negative entity pair for this process item.
- **Possible gold impact:** This is a workflow decision that governs whether any affected existing annotation can be changed; the policy says no existing annotations have been reviewed under v1.0. No individual annotation is authorized for modification by this item.
- **Recommendation (not approved):** Hold unresolved spans; record note ID, exact source text and offsets, candidate labels from the six-label schema, rationale, reviewer, and decision. Require explicit human sign-off and preserve changes as a separately versioned gold set. Do not automatically apply recommendations.
- **Human decision needed:** Choose the authoritative review-log location, required reviewer/sign-off fields, and versioning/evaluation procedure before gold adjudication begins.

## Human decisions still required

Review and record decisions for checklist items **3–5, 7, 9, and 11–17**. The examples and impact notes above are evidence for deliberation, not approvals. In particular, source-level review is needed for the `diabetic`, `ever or chills`, duration, `1%`, and `Humulin N. insulin` candidates; aggregated error counts alone cannot establish gold correctness. Items 4, 5, 7, 9, 11–17 must not be treated as approved based on this report. The already approved rules for chest pain, the specified `3 units per hour` rate, the MTSamples shortest-complete-span precedence, the CONDITION abnormal-finding default, and DURATION scope remain in force.

## Sources reviewed

- `results/mtsamples_ner_gold30_20261024_diagnostic/annotation_policy_v1.0.md`
- `results/mtsamples_ner_gold30_20261024_diagnostic/annotation_policy_v1.0_proposed_for_signoff.md`
- `results/mtsamples_ner_gold30_20261024_diagnostic/adjudication_approval_checklist.md`
- `results/mtsamples_ner_gold30_20261024_diagnostic/policy_consistency_review.md`
- `results/mtsamples_ner_gold30_20261024_diagnostic/diagnostic_report.md` (for the specific saved-evaluation examples cited by the review)
- `data/gold/README.md`
- `data/public/mtsamples/gold/README.md`
