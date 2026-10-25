# MTSamples Annotation Policy Consistency Review

**Scope:** Read-only comparison of `annotation_policy_v1.0_draft.md`, `data/gold/README.md` (shared annotation guide), and `data/public/mtsamples/gold/README.md` (MTSamples setup instructions). The policy remains a draft. No annotations, documentation, code, manifest statuses, or evaluation artifacts were changed; inference and evaluation were not run.

## Direct contradictions and operational conflicts

### 1. “Longest span wins” versus “shortest complete span” — direct rule conflict

- **Existing shared guide:** “Longest span wins,” with `Essential hypertension` rather than `hypertension` inside it.
- **Draft:** Use the “shortest complete span that identifies the entity”; include meaningful modifiers only when part of the named concept or needed to distinguish it.
- **Decisions that could change:** Nested or modifier-bearing gold spans may be shortened or expanded depending on which rule governs. This can move exact boundaries and alter exact-span TP/FN counts even when the label stays the same. The shared example itself (`Essential hypertension`) may still be the shortest complete entity; the conflict is how the general rule handles other nested candidates.
- **Recommended resolution:** Adopt one explicit precedence rule for MTSamples. A workable reconciliation is “choose the shortest span that fully identifies the entity; where a shorter span is only a nested substring of a longer complete entity name, retain the longest complete name.” Confirm this is the intended reconciliation; it is not currently stated consistently in the two documents. Then update the shared guide or explicitly state the approved MTSamples exception and its precedence.

### 2. MTSamples instruction to use the shared guide versus a MTSamples-specific override — conditional operational conflict

- **Existing setup instructions:** Annotators are told to identify all six labels “using the shared guide” and to “Reuse the format and annotation guidelines” in `data/gold/README.md`.
- **Draft:** Defines MTSamples-specific interpretations, including the span-length rule, dosage rates, medication ingredients, and procedural durations.
- **Decisions that could change:** If the draft is treated as active while setup instructions still direct annotators to the shared guide, annotators may apply different boundaries and labels to the same note. It is an operational conflict upon adoption, not an active contradiction while the draft is unapproved.
- **Recommended resolution:** After final approval, update the MTSamples setup instructions to identify the controlling MTSamples policy and state which rules override or refine the shared guide. Until then, use the existing guide and do not apply the draft to gold.

### 3. `3 units per hour`: DOSAGE versus FREQUENCY — direct boundary assignment conflict

- **Existing shared guide:** DOSAGE is “Amount + unit”; FREQUENCY is “How often,” with `every 4 hours` as an example.
- **Draft:** Makes the entire `3 units per hour` one DOSAGE span and says not to also label `per hour` as FREQUENCY.
- **Decisions that could change:** The same rate phrase could be a DOSAGE boundary under the draft or be divided between DOSAGE and FREQUENCY under a literal application of the two broad shared definitions. The diagnostic includes predicted `3 units` overlapping gold `3 units per hour`; choosing a different boundary can change exact TP/FP/FN counts.
- **Recommended resolution:** Explicitly define a rate as an amount-per-time DOSAGE and exclude that same rate component from FREQUENCY, if that is the approved interpretation. Add the distinction to the controlling guide; separately stated administration cadence can remain FREQUENCY. Do not create overlapping spans.

## Important differences that are clarifications or conditional extensions

These are not direct contradictions between the written label definitions, though they can change annotation decisions if adopted.

### CONDITION versus SYMPTOM

- **Existing shared guide:** CONDITION is diagnoses (example `strep throat`); SYMPTOM is symptoms the patient reports or is told to watch for. Tests are excluded as CONDITION; exam findings and lab results are excluded as SYMPTOM.
- **Draft:** Explicitly puts `chest pain` in SYMPTOM regardless of diagnosis heading, chief-complaint, or `PRN chest pain` context; explicitly excludes normal findings. Interpreted abnormal findings are excluded by default and eligible only after a documented, consistently applied scope rule.
- **Assessment:** The chest-pain rule is a clarification consistent with the guide’s symptom/diagnosis distinction, not a contradiction in the guide. However, it conflicts with an existing gold judgment: `Chest pain` at `[19,29)` in `mtsamples_Acute_Inferior_Myocardial_Infarction` is currently CONDITION. The normal-finding exclusion is also consistent with the guide’s exclusion of exam findings, but makes the scope more explicit. Including interpreted abnormalities would be a conditional expansion beyond diagnoses, and should not happen until the separate scope rule is approved.
- **Recommended resolution:** Approve CONDITION as explicitly stated diagnoses only by default; keep normal findings out. Resolve `Chest pain` as SYMPTOM if approved. Do not include abnormal findings until a written inclusion rule and examples are consistently applied.

### MEDICATION names, classes, and ingredients

- **Existing shared guide:** Annotate “Specific drug names,” including salt/formulation words that are part of the name; exclude drug classes such as `antibiotics`, `NSAIDs`, and `oral steroid`.
- **Draft:** Includes generic drug names or ingredients when used as medication, while excluding broad therapeutic classes.
- **Assessment:** This is mostly a clarification: a generic drug name can be a specific medication name. “Ingredient” may extend the scope if it includes class terms or components that are not themselves named medications. `insulin` and `cortisone` are left context-sensitive by the draft; the shared examples do not settle their treatment.
- **Recommended resolution:** Define inclusion by use in context: include a named medication/generic ingredient used as medication, exclude broad classes. Explicitly adjudicate `insulin`, `cortisone`, and `antibiotics` where their role is unclear. This will affect boundaries/counts if missed or extra medication mentions are added or removed.

### DURATION versus symptom, follow-up, and procedure/test time

- **Existing shared guide:** DURATION is how long a treatment or instruction lasts; it explicitly excludes symptom duration (`2 days of dysuria`) and follow-up timing (`follow up in 2 weeks`).
- **Draft:** Keeps those exclusions and additionally excludes procedure/test elapsed time, e.g. `stood on the tilt table for 20 minutes`.
- **Assessment:** Symptom and follow-up rules agree. Excluding procedure/test elapsed time is a clarification of the treatment/instruction scope, not a direct contradiction, though the shared guide does not call it out explicitly.
- **Recommended resolution:** Explicitly adopt or reject the procedure/test exclusion. The diagnostic report lists `20 minutes` twice among duration FNs; if those gold mentions describe procedure time, adopting the draft would remove them from gold and change the gold count and exact-match metrics. Review the source contexts before changing any span. A `one-hour` symptom episode remains excluded under both the shared duration definition and draft.

### Negated, historical, and future symptoms

- **Existing shared guide:** “Every occurrence is annotated, including negated mentions”; SYMPTOM includes symptoms reported or that the patient is told to watch for.
- **Draft:** Explicitly preserves negated and historical symptom mentions, includes explicit watch-for symptoms, excludes procedural events unless they independently describe a patient symptom, and forbids inferring symptoms from hypothetical complications.
- **Assessment:** Negated mentions and explicit watch-for symptoms are consistent. “Historical” makes the all-occurrences rule explicit. Excluding procedural events unless independently a patient symptom is consistent with excluding exam findings. Not inferring a symptom from a hypothetical complication is also consistent with mention-level annotation, but it narrows any ambiguous reading of “told to watch for.” No direct contradiction is present.
- **Recommended resolution:** Keep the draft clarification. Apply it contextually: an explicitly named watch-for symptom is eligible; a possible complication with no named symptom does not create a new mention. This does not require removing negated or historical mentions.

### Coordinated mentions, conjunctions, and punctuation

- **Existing shared guide:** Requires every occurrence and gives a longest-span example, but does not specify whether coordinated mentions should be one span or separate spans, or whether conjunctions/punctuation belong in spans. Setup instructions require character offsets into the source note.
- **Draft:** Splits independent coordinated mentions (`shortness of breath & diaphoresis`; `fever or chills`), excludes conjunctions and surrounding punctuation/whitespace, preserves punctuation within abbreviations such as `b.i.d.`, and requires exact source substring offsets.
- **Assessment:** Splitting coordinated mentions and edge punctuation are clarifications, not direct contradictions, except for the separate longest-versus-shortest conflict. The current gold `ever or chills` is a clipped/content-boundary candidate even though its saved text matches its source slice; structural offset validity alone does not resolve the semantic boundary.
- **Recommended resolution:** Approve one entity per independent mention and exclude conjunctions/outer punctuation; retain internal abbreviation punctuation. Record how to handle an abbreviation's final period when it is also sentence-final.

### Whether spans may overlap

- **Draft:** Requires flat, non-overlapping spans and human review where the label/boundary remains unresolved.
- **Shared guide:** “Longest span wins” implies choosing one span from nested candidates rather than annotating both. It does not say overlapping labels should be retained.
- **Setup instructions:** Do not define overlap behavior. The existing annotation tool rejects overlapping spans.
- **Assessment:** No direct contradiction: the draft, longest-span convention, and current tool all point to non-overlapping gold. The longest-versus-shortest choice affects which boundary wins, not whether both overlapping spans are kept.
- **Recommended resolution:** Retain the non-overlap rule and have human adjudication resolve cross-label/boundary candidates before saving. This is consistent with the tool’s current constraint.

## Potential impact on the 529 entities and reported metrics

The saved evaluation is exact-match by `(start, end, label)`. Any adopted decision that changes a label, boundary, or number of spans can change per-label or micro precision, recall, and F1; this review does not recalculate those results.

- **Known label change candidate:** The gold `Chest pain` span currently labeled CONDITION would become SYMPTOM under the draft. Its entity count may remain one, but the per-label counts and exact match against the saved prediction can change.
- **Known boundary/segmentation candidates:** Splitting or trimming coordinated spans, resolving `ever or chills`, applying shortest-complete versus longest-span, changing `Humulin N. insulin`, or changing `3 units per hour` can alter boundaries or entity counts. The report identifies overlaps and examples but does not provide a complete adjudication count.
- **Potential removals or scope changes:** Excluding normal findings or procedure/test times could remove existing CONDITION or DURATION gold entities. The report identifies long normal echocardiogram findings and two `20 minutes` DURATION FN surfaces; source-by-source review is required to determine which existing spans meet a final policy.
- **Potential additions/omissions:** Decisions about generic medication ingredients, concentrations, rates, historical/negated/future symptoms, and abnormal findings may add or remove spans. The policy-consistent rules for negated and explicit watch-for symptoms match the existing guide and should not by themselves change those judgments.
- **No numerical update is warranted here:** The current report remains the result for the existing gold snapshot. Any adjudicated gold revision requires a separately versioned annotation set and a new evaluation; do not overwrite the saved evaluation to present revised metrics as the original run.

## Highest-priority resolutions

1. Resolve the direct **Longest span wins / shortest complete span** conflict, including whether the MTSamples policy overrides the shared guide.
2. Approve **`3 units per hour` as DOSAGE** versus any DOSAGE/FREQUENCY split, and document the rule in the controlling guide.
3. Confirm **CONDITION scope** (explicit diagnoses by default; abnormal findings only under a separate written rule) and **`chest pain` as SYMPTOM**, recognizing that this changes an existing gold judgment.
4. Decide whether to formalize exclusion of **procedure/test elapsed time** from DURATION and review affected gold spans such as `20 minutes`.
5. After policy approval, update the MTSamples setup instructions so annotators have one controlling guide. Until then, keep the draft advisory and do not alter the 529 annotated spans.

## Files reviewed

- `results/mtsamples_ner_gold30_20261024_diagnostic/annotation_policy_v1.0_draft.md`
- `data/gold/README.md`
- `data/public/mtsamples/gold/README.md`
- `results/mtsamples_ner_gold30_20261024_diagnostic/diagnostic_report.md` (for the referenced existing examples)
