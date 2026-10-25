# MTSamples Pending Annotation Decisions — Human Decision Form

**Status: FOR HUMAN DECISION — NO NEW DECISIONS APPROVED**  
This form gathers the still-pending items identified in `annotation_policy_v1.0.md`. Recommendations below reflect the existing review documents; they are not approvals. Choose one option per item and record any replacement rule. No gold span should be changed based on this form alone.

Use exactly the six labels: `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`.

**For each item:** `[ ] Adopt recommendation` `[ ] Reject; record replacement` `[ ] Needs discussion`

## Approved decisions that remain in force

This form does not reopen the five approved areas: shortest complete meaningful spans supersede “Longest span wins” for MTSamples only; `3 units per hour` is one DOSAGE span; interpreted abnormal findings are excluded from CONDITION unless a precise, consistently applied inclusion rule is separately approved; `chest pain` is SYMPTOM; and DURATION includes treatment/care-instruction intervals while excluding symptom timelines, follow-up intervals, and procedure/test elapsed time.

## Pending decisions

### 3. CONDITION shorthand: `diabetic`

**Recommendation:** Label the exact word `diabetic` as CONDITION when the source clearly asserts a diagnosed disease state; do not expand it. Refer unclear adjectival uses for review.

**Verified example:** In `mtsamples_Acute_Inferior_Myocardial_Infarction`, CONDITION `[169,177)` is `diabetic` in “The patient is diabetic…”. Contrast `diabetic gastroparesis`, verified CONDITION `[1062,1084)` in `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`.

**Open question:** Is “The patient is diabetic” sufficient evidence of an explicitly stated diagnosis? Do not infer a longer disease name.

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 4. Coordinated entities

**Recommendation:** Split coordinated mentions when each part independently names an entity; retain a single span when coordinated words describe one entity (for example, one diagnosis across multiple sites). Exclude the conjunction from split spans. Apply the rule consistently across labels if adopted.

**Verified examples:** The AMI note has one SYMPTOM span `[550,583)` `shortness of breath & diaphoresis`. In `mtsamples_Escharotomy`, CONDITION `[54,122)` is `burn to the bilateral upper extremities and neck and anterior thorax`, describing one burn diagnosis across locations.

**Open question:** Does the split rule apply to all six labels, and what test distinguishes independent entities from one coordinated diagnosis?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 5. Conjunction, whitespace, and punctuation boundaries

**Recommendation:** Exclude separate conjunctions and outer whitespace/punctuation; retain punctuation that belongs to an abbreviation. Decide consistently when an abbreviation period coincides with sentence-final punctuation.

**Verified examples:** AMI SYMPTOM `[669,683)` is `ever or chills` (clipped initial `f`, includes `or`); AMI SYMPTOM `[622,643)` includes a leading space before `episodes of vomiting`; Bunionectomy FREQUENCY `[5934,5940)` is `b.i.d.` with abbreviation periods.

**Open question:** How should an ambiguous terminal period be treated? The approved shortest-span rule favors `vomiting` over framing `episodes of vomiting`, but any existing annotation change needs separate review.

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 7. Negated, historical, and procedural SYMPTOM mentions

**Recommendation:** Include explicit symptom mentions even when negated or historical. Exclude procedural/objective wording unless it independently describes a patient symptom.

**Verified/source examples:** The AMI note says “He denies any fever or chills”; its SYMPTOM `[669,683)` is a verified negated mention with a separate boundary issue. In `mtsamples_Total_Thyroid_Lumpectomy`, “the small bleeding vessels were identified and bipolared” is source text; no matching gold SYMPTOM span was identified.

**Open question:** How should quotations, historical mentions, and operative wording be handled when it is unclear whether the text reports a patient symptom?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 9. DURATION span boundaries and context

**Recommendation:** Capture the interval with meaningful number/modifier, excluding separate markers such as `x` and framing nouns such as `course`. Require context to identify a treatment/care-instruction target; do not infer one from a bare interval. The approved scope exclusions remain in force.

**Verified examples:** Discharge-summary DURATION spans `[3145,3166)` and `[3202,3223)` are `three additional days` for medication courses. AMI `[1123,1132)` is `one-hour.` in a symptom timeline; Tilt Table Test `[297,307)` and `[405,415)` are `20 minutes` of procedure/test elapsed time. These latter spans are review candidates under the already approved exclusions, not automatic edits.

**Open question:** What context is enough to identify the treatment target, and how should number forms, modifiers, hyphens, and punctuation be bounded?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 11. Medication concentrations as DOSAGE

**Recommendation:** Include a percentage as DOSAGE only when source context identifies it as an administered medication concentration; exclude unrelated measurements and do not infer an unclear relationship.

**Verified examples:** `1%` is gold DOSAGE `[1554,1556)` in `mtsamples_Bunionectomy_Osteotomy` (“1% Lidocaine…was injected”) and `[644,646)` in `mtsamples_Carotid_Cerebral_Arteriograms` (“Lidocaine 1%…used as local anesthetic”). Echo LVEF `51%` is a source-only measurement example, not a gold DOSAGE span.

**Open question:** How explicit must the medication-concentration relation be? The reported six detector false negatives require source-level review and do not establish annotation errors.

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 12. MEDICATION products, generics, ingredients, and classes

**Recommendation:** Include a specific product, generic medication, or ingredient when context uses it as medication; exclude broad therapeutic classes. Decide from context, not a word list.

**Verified examples:** Gold includes `regular insulin` in `mtsamples_Fat_Harvesting` `[786,801)`, standalone `insulin` in the discharge summary `[480,487)`, and `cortisone` in `mtsamples_Total_Knee_Replacement` `[1198,1207)`. `prophylactic antibiotics` is verified gold `[2648,2672)` in `mtsamples_Pectoralis_Tendon_Repair` and needs review against the shared guide’s class exclusion. Named products such as `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid` are positive examples.

**Open question:** When does an ingredient word denote a medication versus a class, and how should `antibiotics` be treated in this source context?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 13. Product name versus trailing descriptor: `Humulin N insulin`

**Recommendation:** Annotate a specific product alone when the following generic word is only a descriptor; include it only if it is part of the name or a separately named medication. Exclude punctuation not belonging to the entity.

**Verified example:** AMI MEDICATION `[1708,1726)` is `Humulin N. insulin` in “Humulin N. insulin 50 units in a.m.”

**Open question:** Is `insulin` part of the medication mention or a trailing descriptor, and does the period after `N` belong to the source name or sentence punctuation?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 14. FREQUENCY expressions, abbreviation punctuation, and route exclusions

**Recommendation:** Label cadence as FREQUENCY and routes such as `PO`/`p.o.` as unlabelled route text. Preserve abbreviation-internal punctuation; distinguish a separate sentence period. Include non-medication cadence only when it clearly expresses repetition.

**Verified examples:** Bunionectomy FREQUENCY `[5934,5940)` is `b.i.d.`; AMI FREQUENCY `[1701,1705)` is `QDay` and `[1796,1799)` is `PRN`. The nearby `p.o.` is route text, not frequency.

**Open question:** Which abbreviation forms are included, how to handle a terminal period, and whether clearly repetitive non-medication instructions count?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 15. Quoted and explicit watch-for symptoms

**Recommendation:** Include a named symptom the patient is explicitly told to watch for; do not infer one from a hypothetical complication. Treat quoted wording according to whether it actually reports or describes a patient symptom; hold ambiguous cases.

**Source example:** `mtsamples_Well-Child_Check_-_5.txt` instructs calling if the patient has “fever, feeding problems or breathing problems.” The checklist reports no selected gold annotation file for this note, so this is not an existing gold example.

**Open question:** What wording qualifies as a direct watch-for instruction rather than a hypothetical complication, and do quotation marks change eligibility?

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 16. Non-overlapping spans and tie-breaks

**Recommendation:** Keep spans flat and non-overlapping. Apply approved label decisions first; record unresolved candidates for human review rather than choosing automatically.

**Evidence/examples:** `chest pain`, `Humulin N insulin`, and `3 units per hour` illustrate potential label/boundary conflicts; the first and the specified rate already have approved decisions. Snapshot verification found 0 overlapping spans among 529 entities. The diagnostic report’s prediction/gold interval overlaps are not overlapping gold annotations.

**Open question:** Confirm flat spans as the annotation policy, beyond the existing tool’s overlap restriction. Nested labels would need a separate schema/tool decision.

**Choice:** [ ] Adopt [ ] Reject; replacement: ____________________ [ ] Discuss

### 17. Adjudication record, review, and sign-off workflow

**Recommendation:** Before changing gold, establish an auditable log with note ID, exact source span and offsets, candidate labels, rationale, reviewer, decision/date, and gold-version reference. Require human review; preserve the existing snapshot and make edits only in a separately versioned copy.

**Evidence:** Policy v1.0 §§4–7 requires individual review and a separately versioned gold set for changes. The snapshot verification report documents a 30-note, 529-entity snapshot at `data/public/mtsamples/gold_adjudication_v1_20261024/`. The prior decision record notes the log location and sign-off practice are not yet established.

**Open question:** Where is the authoritative log, who must review/sign, what versioning convention applies, and when may a copied manifest entry be marked complete?

**Choice:** [ ] Adopt [ ] Reject; replacement process: ____________________ [ ] Discuss

## Human record

- Project-owner decision date: ____________________
- Decision record location: ____________________
- Notes or replacement rules: ____________________

Until these choices are explicitly recorded, the recommendations above remain unapproved. Do not modify annotations or manifest statuses based solely on this form. Preserve the verified snapshot as the pre-adjudication copy; any later changes require individual human review and documentation. No inference or evaluation is requested or authorized by this form.
