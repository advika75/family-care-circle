# Adjudication Batch 03 — MEDICATION and SYMPTOM Boundaries

**Human decision record.** Candidates 3–5 (PC01–PC03) are recorded ADOPT and Candidates 1–2 (M01, M02) are recorded DISCUSS by Advika Mishra on 2026-10-24. "Recommended action" text is the assistant suggestion that preceded the decision. ADOPT records the review decision only; it does not itself change the protected snapshot.

Decision options:

- **ADOPT** — accept the recommended action for this candidate.
- **REJECT** — reject it; record the alternative and rationale.
- **DISCUSS** — defer for further review.

## Batch selection

This batch covers the five Phase 1 queue items that have no recorded decision: two MEDICATION boundary cases (M01, M02) and three SYMPTOM punctuation/coordination cases (PC01–PC03). All five have existing pending rows in `gold_adjudication_log.csv` (rows 8, 24, 4, 6 and 5) with no decision.

Offsets are zero-based Python character offsets with an exclusive end. For each candidate, the saved span text, offsets and label were checked against `source[start:end]` in `data/public/mtsamples/notes/` and against the protected snapshot `gold_adjudication_v1_20261024/`. All five matched exactly. Proposed sub-span offsets were computed from the same source text.

## Candidate 1 — Humulin N. insulin (queue M01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
MEDICATIONS: , Aspirin 81 milligrams QDay.  Humulin N. insulin 50 units in a.m.  HCTZ 50 mg QDay.  Nitroglycerin 1/150 sublingually PRN chest pain.,
```
- **Original annotation:** `Humulin N. insulin` — `[1708,1726)` — `MEDICATION`
- **Approved rule:** Policy v1.0 §3 MEDICATION: for a specific product followed by a generic descriptor, label the product name alone when the descriptor is not part of the name; do not include external punctuation. §2.1 excludes external punctuation. §5 item 13 and §6 keep `Humulin N. insulin` as a source-level boundary case.
- **Possible issue:** The saved span includes the period after `N` and the word `insulin`. In this source, `Humulin N` occupies `[1708,1717)`, the period is at 1717, and `insulin` occupies `[1719,1726)`. It is the only occurrence of `insulin` in the note. The source supplies no other medication mention of `insulin`.
- **Recommended action (not approved):** Replace with `Humulin N` at `[1708,1717)`, label MEDICATION, if you confirm `insulin` is only a trailing descriptor and the period is external punctuation. The alternative is to keep `insulin` as part of the name, or to label it as a separate medication mention. Both would be your call.
- **Clarity / edge case:** The period after `N` could be a stray sentence period or part of the written product name. The source does not settle this, so the boundary needs your judgment.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** none; remains DISCUSS.
- **Recorded rationale:** Unresolved; deferred for further review. No annotation change is recorded.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 2 — prophylactic antibiotics (queue M02)

- **Note ID:** `mtsamples_Pectoralis_Tendon_Repair`
- **Source filename:** `mtsamples_Pectoralis_Tendon_Repair.txt`
- **Relevant source context (verbatim excerpt):**

```text
He then received prophylactic antibiotics.  A time-out was then undertaken verifying the correct patient, extremity, surgery performed, administration of antibiotics, and the availability of equipment.
```
- **Original annotation:** `prophylactic antibiotics` — `[2648,2672)` — `MEDICATION`
- **Approved rule:** Policy v1.0 §3 MEDICATION: exclude broad therapeutic classes, such as `antibiotics`, when used as class references. §3 and §6 name `prophylactic antibiotics` as a review example, not an automatic exclusion. §4 item 4: decide from source context, not word lists.
- **Possible issue:** The span is an exact source slice, but no specific drug, generic name or ingredient is named. The word `antibiotics` appears in the note only twice, here and in "administration of antibiotics" at offset 2785. Neither names a product.
- **Recommended action (not approved):** Remove the span from MEDICATION and assign no other label, because the source uses `antibiotics` only as a class. The alternative is to retain it as an administered medication mention, which would need a documented rationale.
- **Clarity / edge case:** The source says the patient received the antibiotics, so administration is stated. The open question is only whether a class-level mention counts under §3, which excludes broad classes.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** none; remains DISCUSS.
- **Recorded rationale:** Unresolved; deferred for further review. No annotation change is recorded.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 3 — shortness of breath & diaphoresis (queue PC01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
He ranks the pain a 7 on a scale of 1-10.  He admits some shortness of breath & diaphoresis.  He states that he has had nausea & 3 episodes of vomiting tonight.
```
- **Original annotation:** `shortness of breath & diaphoresis` — `[550,583)` — `SYMPTOM`
- **Approved rule:** Policy v1.0 §2.2: split coordinated mentions when each part independently names a meaningful entity, and exclude `&`. The policy example gives this exact phrase as `shortness of breath`; `diaphoresis`.
- **Possible issue:** One span covers two independent symptoms joined by `&`.
- **Recommended action (not approved):** Replace with two SYMPTOM spans: `shortness of breath` at `[550,569)` and `diaphoresis` at `[572,583)`. The `&` and surrounding spaces are excluded. The two spans do not overlap.
- **Clarity / edge case:** Low ambiguity. Both parts are patient-reported ("He admits"), and the policy example matches this span directly.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Replace with two SYMPTOM spans: `shortness of breath` at [550,569) and `diaphoresis` at [572,583); exclude `&` and surrounding spaces.
- **Recorded rationale:** Policy v1.0 §2.2 splits coordinated mentions that each independently name a symptom and excludes `&`.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 4 — episodes of vomiting (queue PC02)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
He states that he has had nausea & 3 episodes of vomiting tonight.  He denies any fever or chills.
```
- **Original annotation:** ` episodes of vomiting` — `[622,643)` — `SYMPTOM` (the saved text begins with a space)
- **Approved rule:** Policy v1.0 §2.1 excludes leading and trailing whitespace. §2.2 uses the shortest complete span and gives `vomiting` rather than `episodes of vomiting` as the example when the framing adds no part of the symptom identity.
- **Possible issue:** The saved span has a leading space and the framing words `episodes of`. The neighbouring `nausea` is already a separate SYMPTOM span at `[612,618)` in the snapshot, so the replacement would not overlap it.
- **Recommended action (not approved):** Replace with `vomiting` at `[635,643)`, label SYMPTOM.
- **Clarity / edge case:** Low ambiguity. The policy gives this exact example.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Replace with `vomiting` at [635,643), label SYMPTOM.
- **Recorded rationale:** Policy v1.0 §2.1 excludes leading whitespace; §2.2 uses the shortest complete span and gives `vomiting` rather than `episodes of vomiting`.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 5 — fever or chills, clipped (queue PC03)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
He states that he has had nausea & 3 episodes of vomiting tonight.  He denies any fever or chills.  He admits prior episodes of similar pain prior to his PTCA in 1995.
```
- **Original annotation:** `ever or chills` — `[669,683)` — `SYMPTOM` (the first letter `f` at offset 668 is missing)
- **Approved rule:** Policy v1.0 §2.2: split coordinated mentions and exclude `or`; the policy example gives `fever or chills` as `fever`; `chills`. §2.1 requires exact source substrings. §2.1 and §3 SYMPTOM include explicit negated mentions.
- **Possible issue:** The saved span starts one character late, so it is not a whole-word mention, and it joins two symptoms with `or`. Both symptoms are negated ("He denies any").
- **Recommended action (not approved):** Replace with two SYMPTOM spans: `fever` at `[668,673)` and `chills` at `[677,683)`. The negation is carried by the source, not by the span, so the spans stay as the bare symptom words.
- **Clarity / edge case:** Low ambiguity. Negated symptoms are explicitly in scope under Policy §3 SYMPTOM, and the policy example matches this phrase.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Replace with two SYMPTOM spans: `fever` at [668,673) and `chills` at [677,683).
- **Recorded rationale:** Policy v1.0 §2.2 splits coordinated mentions and excludes `or`; §2.1 requires an exact source substring; §3 SYMPTOM includes negated mentions.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Batch record

Candidates 3–5 (PC01, PC02, PC03) are recorded **ADOPT** and Candidates 1–2 (M01 `Humulin N. insulin`, M02 `prophylactic antibiotics`) remain **DISCUSS**, all by Advika Mishra on 2026-10-24. M01 and M02 change nothing. The protected snapshot, manifest and approved policy remain unchanged. Gold version reference for these log entries: `gold_adjudication_v1_20261024`.
