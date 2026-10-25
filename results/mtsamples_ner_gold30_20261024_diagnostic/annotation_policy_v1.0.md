# MTSamples Annotation Policy v1.0

**APPROVED — HUMAN SIGN-OFF RECORDED**
**Version:** 1.0
**Approver:** Advika Mishra
**Approval date:** 2026-10-24
**Scope:** Future manual annotation and adjudication for the selected MTSamples NER set.
**Exceptions:** Context-dependent cases listed below remain subject to individual human review.

This version records the five previously approved decision areas and the 12 pending decisions explicitly approved on 2026-10-24. It governs MTSamples only. It does not change the shared annotation guide for other datasets. Policy approval does not mean existing annotations were reviewed under these rules, and it does not authorize automatic relabeling. Any change to existing gold must be individually reviewed, logged, and preserved as a separate gold version.

## 1. Label schema

Use exactly these six labels:

- `MEDICATION`
- `DOSAGE`
- `FREQUENCY`
- `DURATION`
- `CONDITION`
- `SYMPTOM`

Do not add labels or infer entities that are not stated in the source.

## 2. Mention, span, and offset rules

### 2.1 Exact source offsets

Store the exact source substring with zero-based Python character offsets and an exclusive end: `entity.text == source[start:end]`. Preserve source spelling, case, abbreviation, and number form. Do not include leading/trailing whitespace, list markers, external punctuation, or conjunctions. Preserve punctuation that belongs to an abbreviation, such as `b.i.d.`. If a terminal period could be either abbreviation punctuation or sentence punctuation, apply a consistent convention; send unclear cases for human review and record the decision.

Annotate each explicit occurrence. For SYMPTOM, include repeated, negated, and historical mentions, as well as an explicitly named symptom in a patient instruction to watch for. Quotation marks alone do not make a symptom ineligible. Do not infer symptoms from hypothetical complications that do not name a symptom.

### 2.2 Span boundaries and coordination

Use the **shortest complete, semantically meaningful span**, retaining modifiers necessary to identify the entity or subtype and excluding unrelated framing. This rule **supersedes “Longest span wins” for MTSamples adjudication only** wherever the rules conflict. The shared guide remains unchanged for other datasets.

Split coordinated mentions into separate spans when each part independently names a meaningful entity. Keep coordinated words together when they jointly describe one entity, such as one diagnosis with multiple locations. Apply this rule consistently across all six labels. Exclude conjunctions such as `and`, `or`, and `&` from entity spans.

Examples:

- `shortness of breath & diaphoresis` → `shortness of breath`; `diaphoresis`
- `fever or chills` → `fever`; `chills`
- `burn to the bilateral upper extremities and neck and anterior thorax` remains one CONDITION span when it describes one burn diagnosis across sites.
- Retain subtype modifiers in `Essential hypertension` and `I-131-induced hypothyroidism`; use `vomiting` rather than framing such as `episodes of vomiting` when the framing adds no part of the symptom identity.

### 2.3 Flat, non-overlapping annotations

Use flat, non-overlapping spans. Do not assign duplicate characters to multiple labels. Use adjacent spans for separate entities. Apply the label and boundary rules below to resolve conflicts; if context does not settle a conflict, record the candidate labels and refer it to a human reviewer rather than choosing automatically. This matches the current annotation tool's overlap constraint.

## 3. Label definitions

### MEDICATION

Include a specific medication product, generic drug name, or ingredient when the source uses it as medication. Include a salt or formulation word when it is part of the medication name. Examples include `metoprolol succinate`, `Marcaine`, `Lamictal`, `Levaquin`, and `Synthroid`.

Exclude broad therapeutic classes, such as `antibiotics`, `NSAIDs`, and `oral steroid`, when used as class references. Exclude dosage, route, frequency, and surrounding prose.

For a specific product followed by a generic descriptor, label the product name alone when the descriptor is not part of the name. For example, label `Humulin N` in `Humulin N insulin` when `insulin` is only a trailing descriptor; do not include external punctuation. Label a generic term separately when context clearly uses it as a medication mention. Do not decide from a word list alone.

**Human review required:** Context may leave unclear whether `insulin`, `cortisone`, or `antibiotics` is being used as a medication/ingredient or as a broader class; whether `insulin` after `Humulin N` is part of the name or a descriptor; or whether a nearby period belongs to the entity. Review the source context and record the decision. The verified `prophylactic antibiotics` span is a review example, not an automatic exception to the broad-class rule.

### DOSAGE

Include an explicit medication amount and unit, such as `500 mg`, `90 mcg`, `2 puffs`, `1 cc`, or `one tablet`.

Include a percentage as DOSAGE only when the source context explicitly identifies it as a medication concentration, such as administered Lidocaine `1%`. Exclude unrelated measurements and percentages, such as LVEF `51%`, `8.9%`, `101.8 F`, and `10 lbs`. Do not infer a medication relationship from a percentage alone.

For the approved amount-per-time rate, annotate `3 units per hour` as one DOSAGE span. Do not separately label `per hour` as FREQUENCY. A different expression whose relation between amount and cadence is unclear requires human review.

### FREQUENCY

Include explicit cadence: how often medication or an instruction is repeated. Examples include `BID`, `b.i.d.`, `q4-6h`, `once daily`, `every 4 hours`, `nightly`, `QDay`, `PRN`, `daily`, and `as needed`.

Exclude routes such as `PO` and `p.o.`, dosage amounts, and the `per hour` portion of the approved `3 units per hour` DOSAGE span. A non-medication instruction is FREQUENCY only when it clearly states how often an action occurs. Preserve abbreviation-internal punctuation and distinguish a separate sentence-final period; refer ambiguous boundaries for human review.

### DURATION

Include how long a medication, treatment, or care instruction is to continue. Capture the interval with meaningful number words and modifiers, while excluding separate framing markers and nouns that are not part of the interval. Examples include `10 days` in `x 10 days`, `4 more days`, and `15-day` in `15-day course`; exclude `x` and `course` in those examples.

Exclude symptom timelines (`2 days of dysuria`, `pain for 2 days`), follow-up timing (`follow up in 2 weeks`), and procedure/test elapsed time (`stood on the tilt table for 20 minutes`). A `one-hour` symptom episode is not DURATION. Do not infer a treatment target from a bare interval; if context does not clearly identify a treatment or care instruction, refer the case for human review.

### CONDITION

Include explicitly stated diagnoses, diseases, disorders, and injuries. Examples include `strep throat`, `type 2 diabetes mellitus`, `anemia`, `MGUS`, `dehydration`, `Essential hypertension`, and `I-131-induced hypothyroidism`. Use the shortest complete span while retaining meaningful subtype modifiers.

Exclude normal findings, tests such as `rapid strep test`, anatomy alone, and measurements. Do not label a symptom as CONDITION merely because it appears under a diagnosis heading. Label `diabetic` as CONDITION when the text clearly asserts the patient's diagnosed disease state; retain the exact word and do not expand it to an unstated diagnosis. Refer ambiguous adjectival uses for human review.

Exclude interpreted abnormal findings by default. They may be included only if a precise scope rule is documented, approved, and applied consistently across notes; do not make case-by-case exceptions. Examples such as regurgitation, stenosis, and masses remain excluded unless such a separate rule is approved.

### SYMPTOM

Include symptoms the patient experiences or reports, including explicit negated and historical mentions. Include an explicitly named symptom in an instruction telling the patient to watch for it. Quotation alone does not disqualify a symptom. Do not infer a symptom from a hypothetical complication that does not name one.

Exclude objective findings and procedural events unless the wording independently describes a patient symptom. For example, `small bleeding vessels were identified and bipolared` is a procedural finding absent independent symptom context. `Chest pain` is SYMPTOM, including under a diagnosis heading, as a chief complaint, or in `PRN chest pain`; do not assign CONDITION to the same span.

## 4. Conflict-resolution and adjudication procedure

1. Apply the six label definitions and MTSamples boundary rules above. The shortest-complete-span precedence is specific to MTSamples.
2. Split coordinated mentions only when each part independently names an entity; retain coordinated modifiers or sites that describe one entity.
3. Keep spans flat and non-overlapping. For `chest pain`, use SYMPTOM. For `3 units per hour`, use one DOSAGE span.
4. Use source context, not section headings or word lists alone, to determine what a phrase denotes. Do not expand shorthand or infer unstated concepts.
5. For unresolved contextual cases, record note ID, source filename, exact text and offsets, existing and proposed label/span, rationale/evidence, reviewer, decision/date, and gold-version reference. Retain the case for human review; do not silently choose or automatically relabel.
6. Preserve the pre-adjudication snapshot. Any revised annotation must be reviewed individually, validated against the source and manifest, recorded in a separate gold version, and evaluated only under a separately authorized evaluation step. Mark a review complete only after the human decision and validation are complete.

## 5. Approval decision log

The decisions below were explicitly approved by Advika Mishra on 2026-10-24. “Approved” applies to the written rule; it does not mean any existing span has been adjudicated under that rule.

| Checklist item | Approved rule | Status / limits |
|---|---|---|
| 3 — CONDITION shorthand | Label exact `diabetic` as CONDITION when it clearly asserts diagnosed disease state; do not expand it; review ambiguous use. | Approved; context-dependent cases require human review. |
| 4 — Coordination | Split independent entities; keep coordinated sites/modifiers together when they describe one entity; apply across six labels. | Approved. |
| 5 — Conjunction and boundaries | Exclude conjunctions, outer whitespace, and external punctuation; retain abbreviation punctuation; use a consistent terminal-period convention and review unclear cases. | Approved; ambiguous punctuation still requires case review. |
| 7 — Negated, historical, procedural symptoms | Include explicit negated/historical symptoms; exclude procedural/objective wording unless it independently describes a patient symptom; do not infer unstated symptoms. | Approved. |
| 9 — DURATION boundaries | Capture treatment/care-instruction intervals and meaningful modifiers; exclude framing; require clear context; retain approved exclusions for symptom, follow-up, and procedure/test intervals. | Approved; ambiguous target remains for case review. |
| 11 — Concentrations | Include medication concentration percentages as DOSAGE only when source context explicitly establishes that relation; exclude unrelated measurements. | Approved; unclear relations require review. |
| 12 — Medication names/classes | Include specific products, generics, and ingredients used as medication; exclude broad therapeutic classes; decide by context. | Approved; ambiguous instances such as `prophylactic antibiotics`, standalone `insulin`, and `cortisone` require source review. |
| 13 — Product/descriptor boundary | Label the specific product alone when a following generic term is only a descriptor; include that term only if part of the name or independently used as a medication mention; resolve period boundaries consistently. | Approved; `Humulin N. insulin` remains a case for source-level boundary review. |
| 14 — FREQUENCY/routes | Label explicit cadence, including clear non-medication cadence; exclude routes; preserve abbreviation punctuation and distinguish sentence punctuation. | Approved; unclear cadence and terminal-period cases require review. |
| 15 — Quoted/watch-for symptoms | Include explicit named watch-for symptoms; quotation alone does not disqualify; do not infer symptoms from hypothetical complications; review ambiguous quotations. | Approved. |
| 16 — Overlap/tie-breaks | Use flat, non-overlapping spans; apply semantic rules first; defer unresolved conflicts to human review. | Approved. |
| 17 — Adjudication workflow | Maintain an auditable decision record; preserve the existing snapshot; revise only in a separate gold version; validate before marking review complete. | Approved; the project must identify the operational log location before annotation begins. |

The previously approved decisions remain in force: MTSamples shortest-complete spans supersede “Longest span wins” for MTSamples only; `3 units per hour` is one DOSAGE span; interpreted abnormal findings default to excluded from CONDITION absent a separately approved precise scope rule; `chest pain` is SYMPTOM; and DURATION includes treatment/care-instruction durations while excluding symptom timelines, follow-up intervals, and procedure/test elapsed time.

## 6. Remaining case-level questions

Policy decisions are approved, but context-dependent applications still require source-level human review. Examples include `Humulin N. insulin` (descriptor and punctuation boundary), whether `prophylactic antibiotics`, standalone `insulin`, or `cortisone` denotes a medication/ingredient versus a class in context, an unclear medication-concentration relationship, a time expression that may be rate or separate cadence, ambiguous non-medication cadence, terminal abbreviation punctuation, quoted/operative wording that may or may not describe a patient symptom, and intervals without a clear treatment/care target.

These case-level questions do not suspend the approved general rules and do not authorize automatic resolution. The adjudication log location must be established before the review workflow starts. Policy approval alone does not change the 30-note gold snapshot or its manifest statuses.

## 7. Approval record

- Human approver: Advika Mishra
- Approved version: MTSamples Annotation Policy v1.0, including checklist items 3–5, 7, 9, and 11–17
- Approval date: 2026-10-24
- Decision: Explicitly approved all 12 recommended ADOPT decisions
- Exceptions: Context-dependent case questions listed in Section 6 remain for individual human review
- Adjudication log location: To be established before annotation begins
