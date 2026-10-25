# Adjudication Batch 04 — Open Items (DISCUSS, boundary and label carry-overs)

**Human decision record.** The decisions below were confirmed by Advika Mishra on 2026-10-25. ADOPT records the review decision only; it does not itself change the protected snapshot or any existing gold directory. Candidate 2 (Edema) remains DISCUSS. Candidate 3 (D04) is an ADOPT that retains the span, so it changes no gold.

Decision options:

- **ADOPT** — accept an action listed under the options below (name which one).
- **REJECT** — reject the proposed action; record the alternative and rationale.
- **DISCUSS** — defer the decision for further review.

## Batch selection

This batch carries forward the eight items recorded DISCUSS in Batches 01–03 (SC02, SC04, D04, D05, D10, D15, M01, M02) plus two unreviewed queue items that remained in the partially adjudicated gold (M03 and SC03). The queue placed M03 and SC03 at priority P3, “apply settled convention”.

Current spans and offsets are those in `data/public/mtsamples/gold_adjudicated_v1_1_20261024/`. None of the ten candidates was changed by that version, so each span, offset and label is identical in the protected snapshot `gold_adjudication_v1_20261024/`. Offsets are zero-based Python character offsets with an exclusive end.

Policy quotations are from `annotation_policy_v1.0.md`. Each excerpt is about 300 characters of the source note centred on the span, taken verbatim from `data/public/mtsamples/notes/`.

| # | Queue | Span (current) | Current label | Source settles it? |
|---|---|---|---|---|
| 1 | SC02 | `Dyspnea` [85,92) | CONDITION | No |
| 2 | SC04 | `Edema` [98,103) | CONDITION | No |
| 3 | D04 | `approximately 10 days` [5294,5315) | DURATION | No |
| 4 | D05 | `over the past 1 hour` [948,968) | DURATION | No |
| 5 | D10 | `for 26 years` [488,500) | DURATION | No |
| 6 | D15 | `24-48 hours` [3495,3506) | DURATION | No |
| 7 | M01 | `Humulin N. insulin` [1708,1726) | MEDICATION | No |
| 8 | M02 | `prophylactic antibiotics` [2648,2672) | MEDICATION | No |
| 9 | M03 | ` Nitroglycerin` [1762,1776) | MEDICATION | Yes (boundary); label not in question |
| 10 | SC03 | `chest pain` [141,151) | CONDITION | Policy text settles it |

## Candidate 1 — Dyspnea in admission diagnoses (queue SC02)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
ADMISSION DIAGNOSES:,1.  Seizure.,2.  Hypoglycemia.,3.  Anemia.,4.  Hypotension.,5.  Dyspnea.,6.  Edema.,DISCHARGE DIAGNOSES:,1.  Colon cancer, status post right hemicolectomy.,2.  Anemia.,3.  Hospital-acquired pneumonia.,4.  Hypertension
```
- **Current annotation (gold v1.1):** `Dyspnea` — `[85,92)` — `CONDITION`
- **Original label (protected snapshot):** `CONDITION` (unchanged)
- **Approved policy (quoted):**
  - §3 CONDITION: “Do not label a symptom as CONDITION merely because it appears under a diagnosis heading.”
  - §3 SYMPTOM: “Include symptoms the patient experiences or reports, including explicit negated and historical mentions.” and “Exclude objective findings and procedural events unless the wording independently describes a patient symptom.”
  - §4 item 4: “Use source context, not section headings or word lists alone, to determine what a phrase denotes. Do not expand shorthand or infer unstated concepts.”
- **Options and what each would change:**
  - **ADOPT — relabel to SYMPTOM** keeping `Dyspnea` at [85,92). Changes: 1 gold span moves CONDITION → SYMPTOM.
  - **ADOPT — retain as CONDITION** (documented rationale that the diagnosis-list entry is an explicit diagnosis). Changes: nothing in gold.
  - **REJECT** — record a different action and rationale (for example, remove the span). Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** `Dyspnea` occurs exactly once in the note, as list item 5 under `ADMISSION DIAGNOSES`. The note contains no narrative sentence describing the patient experiencing or reporting breathlessness (no other mention of `dyspnea` or `shortness of breath` anywhere in the note), so neither a patient-reported symptom nor a clinician-asserted diagnosis is stated beyond the heading placement.
- **Considerations (not a recommendation):**
  - The policy says the heading alone is not enough to make a symptom a CONDITION, and equally says not to infer.
  - Neighbouring list entries (`Seizure`, `Hypoglycemia`, `Anemia`, `Hypotension`) are presented in the same list form; the list itself does not distinguish diagnoses from symptoms.
  - The word ordinarily names a symptom, but the policy requires the decision to rest on the note, not on a word list.
  - Whatever is decided for `Dyspnea` is likely to be applied to `Edema` (Candidate 2) in the same list, though the policy treats each as an individual decision.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Relabel `Dyspnea` [85,92) from CONDITION to SYMPTOM; keep the same span.
- **Recorded rationale:** Policy v1.0 §3 CONDITION: a symptom is not labelled CONDITION merely because it appears under a diagnosis heading.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 2 — Edema in admission diagnoses (queue SC04)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
ADMISSION DIAGNOSES:,1.  Seizure.,2.  Hypoglycemia.,3.  Anemia.,4.  Hypotension.,5.  Dyspnea.,6.  Edema.,DISCHARGE DIAGNOSES:,1.  Colon cancer, status post right hemicolectomy.,2.  Anemia.,3.  Hospital-acquired pneumonia.,4.  Hypertension.,5.  Conges
```
- **Current annotation (gold v1.1):** `Edema` — `[98,103)` — `CONDITION`
- **Original label (protected snapshot):** `CONDITION` (unchanged)
- **Approved policy (quoted):**
  - §3 CONDITION: “Include explicitly stated diagnoses, diseases, disorders, and injuries.” and “Exclude interpreted abnormal findings by default. They may be included only if a precise scope rule is documented, approved, and applied consistently across notes; do not make case-by-case exceptions.”
  - §3 SYMPTOM: “Exclude objective findings and procedural events unless the wording independently describes a patient symptom.”
  - §3 CONDITION: “Do not label a symptom as CONDITION merely because it appears under a diagnosis heading.”
- **Options and what each would change:**
  - **ADOPT — relabel to SYMPTOM** keeping `Edema` at [98,103). Changes: 1 gold span moves CONDITION → SYMPTOM.
  - **ADOPT — retain as CONDITION** (documented rationale that it is an explicitly stated diagnosis). Changes: nothing in gold.
  - **ADOPT — remove, no label** (documented rationale that it is an objective or interpreted finding). Changes: 1 CONDITION span removed.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** `Edema` occurs once in the note, as list item 6 under `ADMISSION DIAGNOSES`, with no site, cause, severity, or patient-reported complaint. It could be read as a stated diagnosis, a patient-reported symptom, or an objective finding; the text supports none of these over the others.
- **Considerations (not a recommendation):**
  - Unlike `Dyspnea`, `Edema` is more often an examiner-observed sign than a patient-experienced sensation, which is why the SYMPTOM definition's objective-finding exclusion is relevant; the note does not say who observed it.
  - The CONDITION default exclusion of interpreted abnormal findings (regurgitation, stenosis and masses are the policy's named examples) may or may not be meant to cover edema; the policy does not name it.
  - Batch 01 recorded DISCUSS for this item with the rationale that no cause or clinical relationship is inferred; that still holds.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** none; remains DISCUSS. No gold change.
- **Recorded rationale:** The note does not settle whether `Edema` is a stated diagnosis, a symptom or an objective finding (Policy v1.0 §3 CONDITION and SYMPTOM; §4 item 4).
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 3 — approximately 10 days (queue D04)

- **Note ID:** `mtsamples_Pectoralis_Tendon_Repair`
- **Source filename:** `mtsamples_Pectoralis_Tendon_Repair.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
he arm adducted and internally rotated.,Plan for this patient, the patient will remain in the shoulder immobilizer until followup visit in approximately 10 days.  We will then start a gentle Codman type exercises and having limited motion until the 4-6 week point based on the patient's progression.
```
- **Current annotation (gold v1.1):** `approximately 10 days` — `[5294,5315)` — `DURATION`
- **Original label (protected snapshot):** `DURATION` (unchanged)
- **Approved policy (quoted):**
  - §3 DURATION: “Include how long a medication, treatment, or care instruction is to continue. Capture the interval with meaningful number words and modifiers, while excluding separate framing markers and nouns that are not part of the interval.”
  - §3 DURATION: “Exclude symptom timelines (`2 days of dysuria`, `pain for 2 days`), follow-up timing (`follow up in 2 weeks`), and procedure/test elapsed time (`stood on the tilt table for 20 minutes`).”
- **Options and what each would change:**
  - **ADOPT — retain as is** (the interval is how long the shoulder-immobilizer care instruction continues). Changes: nothing in gold.
  - **ADOPT — shrink** to `10 days` at [5308,5315) (if `approximately` is judged a framing word rather than a meaningful modifier). Changes: 1 span replaced by a shorter one.
  - **ADOPT — remove** from DURATION (if the interval is judged follow-up timing). Changes: 1 DURATION span removed.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** The sentence ties two things together: the patient “will remain in the shoulder immobilizer until followup visit in approximately 10 days.” The 10-day interval is both the time until the follow-up visit (excluded follow-up timing) and, implicitly, how long the immobilizer care instruction runs (included care-instruction duration). The text does not say which reading is intended.
- **Considerations (not a recommendation):**
  - A clear care target exists (the shoulder immobilizer), which the policy requires.
  - The interval is expressed as time until a visit, and the policy’s own exclusion example is `follow up in 2 weeks`.
  - `approximately` qualifies the number; the policy asks to keep “meaningful number words and modifiers” and exclude “separate framing markers” — whether it is one or the other is a judgment.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Retain `approximately 10 days` [5294,5315) as DURATION. No gold change.
- **Recorded rationale:** Policy v1.0 §3 DURATION includes how long a care instruction continues; the sentence ties the interval to remaining in the shoulder immobilizer.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 4 — over the past 1 hour (queue D05)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
 seems to be relieved with rest.  There is no change in pain with positioning.  He states that he took 3 nitroglycerin tablets sublingually over the past 1 hour, which he states has partially relieved his pain.  The patient ranks his present pain a 4 on a scale of 1-10.  The most recent episode of p
```
- **Current annotation (gold v1.1):** `over the past 1 hour` — `[948,968)` — `DURATION`
- **Original label (protected snapshot):** `DURATION` (unchanged)
- **Approved policy (quoted):**
  - §3 DURATION: “Include how long a medication, treatment, or care instruction is to continue. Capture the interval with meaningful number words and modifiers, while excluding separate framing markers and nouns that are not part of the interval.”
  - §3 DURATION: “Do not infer a treatment target from a bare interval; if context does not clearly identify a treatment or care instruction, refer the case for human review.”
  - §3 DURATION: “Exclude symptom timelines (`2 days of dysuria`, `pain for 2 days`), follow-up timing (`follow up in 2 weeks`), and procedure/test elapsed time (`stood on the tilt table for 20 minutes`).”
- **Options and what each would change:**
  - **ADOPT — retain as is** (the interval is the period over which the patient took the medication). Changes: nothing in gold.
  - **ADOPT — shrink** to `1 hour` at [962,968) (if `over the past` is judged a framing marker). Changes: 1 span replaced by a shorter one.
  - **ADOPT — remove** from DURATION. Changes: 1 DURATION span removed.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** The interval belongs to the patient’s own report of taking medication: “He states that he took 3 nitroglycerin tablets sublingually over the past 1 hour, which he states has partially relieved his pain.” It attaches to a medication (so it is not a pain timeline), but it is a retrospective window of use, not a statement of how long a treatment is to continue. The policy’s inclusion wording is forward-looking and its exclusion list does not name retrospective medication windows.
- **Considerations (not a recommendation):**
  - Same note, same interval kind: the later “has lasted one-hour” (D01) was recorded ADOPT-removal as a pain-episode timeline; this item differs because its subject is the medication taking.
  - Batch 02 D08 `one month ago` was removed as an event timestamp (`ago`), which is a different construction from a span such as `over the past 1 hour`; it is not direct precedent.
  - No treatment target should be inferred beyond the nitroglycerin the sentence names.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove `over the past 1 hour` [948,968) from DURATION; assign no other label.
- **Recorded rationale:** Policy v1.0 §3 DURATION covers how long treatment continues; this span is a retrospective window of nitroglycerin use.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 5 — for 26 years (queue D10)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
icolectomy.,HOSPITAL COURSE: , The patient is a 59-year-old female with multiple medical problems including diabetes mellitus requiring insulin for 26 years, previous MI and coronary artery disease, history of seizure disorder, GERD, bipolar disorder, and anemia.  She was admitted due to a seizure a
```
- **Current annotation (gold v1.1):** `for 26 years` — `[488,500)` — `DURATION`
- **Original label (protected snapshot):** `DURATION` (unchanged)
- **Approved policy (quoted):**
  - §3 DURATION: “Include how long a medication, treatment, or care instruction is to continue. Capture the interval with meaningful number words and modifiers, while excluding separate framing markers and nouns that are not part of the interval. Examples include `10 days` in `x 10 days`, `4 more days`, and `15-day` in `15-day course`; exclude `x` and `course` in those examples.”
  - §3 DURATION: “Do not infer a treatment target from a bare interval; if context does not clearly identify a treatment or care instruction, refer the case for human review.”
- **Options and what each would change:**
  - **ADOPT — retain as is** (interval of insulin therapy). Changes: nothing in gold.
  - **ADOPT — shrink** to `26 years` at [492,500) (if `for` is judged a framing marker, as `x` is in the policy example). Changes: 1 span replaced by a shorter one.
  - **ADOPT — remove** from DURATION. Changes: 1 DURATION span removed.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** The text is “diabetes mellitus requiring insulin for 26 years”, in the hospital-course history. It is clear that the interval attaches to insulin use, but it is a historical length of therapy, not a prescribed or planned continuation. The note does not say whether that therapy is ongoing as a current order. Do not read the interval as the age or duration of the diabetes itself; the sentence does not say that.
- **Considerations (not a recommendation):**
  - A clear medication target exists (`insulin`, which is currently annotated MEDICATION at [480,487)).
  - The policy’s included examples are forward-looking courses; this is history.
  - If the span is kept, `for` versus `26 years` is a separate boundary choice (see the shrink option).
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove `for 26 years` [488,500) from DURATION; assign no other label. `insulin` [480,487) stays MEDICATION.
- **Recorded rationale:** Policy v1.0 §3 DURATION covers how long treatment continues; this span is the historical length of insulin use.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 6 — 24-48 hours (queue D15)

- **Note ID:** `mtsamples_Tenosynovectomy_Cortisone_Injection`
- **Source filename:** `mtsamples_Tenosynovectomy_Cortisone_Injection.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
00, 30 tablets, one to two PO q.4h. p.r.n.  Patient asked to begin gentle active flexion, extension and passive nerve glide exercises beginning 24-48 hours after surgery.  She was asked to keep the dressings clean, dry and intact and follow up in my office.
```
- **Current annotation (gold v1.1):** `24-48 hours` — `[3495,3506)` — `DURATION`
- **Original label (protected snapshot):** `DURATION` (unchanged)
- **Approved policy (quoted):**
  - §3 DURATION: “Include how long a medication, treatment, or care instruction is to continue. Capture the interval with meaningful number words and modifiers, while excluding separate framing markers and nouns that are not part of the interval.”
  - §3 DURATION: “Exclude symptom timelines (`2 days of dysuria`, `pain for 2 days`), follow-up timing (`follow up in 2 weeks`), and procedure/test elapsed time (`stood on the tilt table for 20 minutes`). … Do not infer a treatment target from a bare interval; if context does not clearly identify a treatment or care instruction, refer the case for human review.”
- **Options and what each would change:**
  - **ADOPT — retain as is** (interval belonging to the exercise instruction). Changes: nothing in gold.
  - **ADOPT — remove** from DURATION. Changes: 1 DURATION span removed.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** The care instruction is clear (“begin gentle active flexion, extension and passive nerve glide exercises beginning 24-48 hours after surgery”), but the interval says **when the exercises start**, not how long they continue. The policy’s DURATION definition is about how long something continues; it names no rule for start-delay intervals, and `after surgery` is outside the interval in any case.
- **Considerations (not a recommendation):**
  - A clear care target exists (the exercises), so the “bare interval” caution does not apply the way it does elsewhere.
  - The interval is an onset delay, not a continuation length, and is not a symptom timeline or follow-up interval; it also is not obviously procedure elapsed time.
  - The same note’s `follow up in my office` has no interval, so there is no follow-up-timing ambiguity here.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove `24-48 hours` [3495,3506) from DURATION; assign no other label.
- **Recorded rationale:** Policy v1.0 §3 DURATION covers how long a care instruction continues; this span states when the exercises begin.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 7 — Humulin N. insulin (queue M01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
.  Works as a banker.,FAMILY HISTORY: , Positive for coronary artery disease (father & brother).,MEDICATIONS: , Aspirin 81 milligrams QDay.  Humulin N. insulin 50 units in a.m.  HCTZ 50 mg QDay.  Nitroglycerin 1/150 sublingually PRN chest pain.,ALLERGIES: , Penicillin.,PHYSICAL EXAM: , The patient i
```
- **Current annotation (gold v1.1):** `Humulin N. insulin` — `[1708,1726)` — `MEDICATION`
- **Original label (protected snapshot):** `MEDICATION` (unchanged)
- **Approved policy (quoted):**
  - §3 MEDICATION: “For a specific product followed by a generic descriptor, label the product name alone when the descriptor is not part of the name. For example, label `Humulin N` in `Humulin N insulin` when `insulin` is only a trailing descriptor; do not include external punctuation. Label a generic term separately when context clearly uses it as a medication mention. Do not decide from a word list alone.”
  - §3 MEDICATION, human review: “… whether `insulin` after `Humulin N` is part of the name or a descriptor; or whether a nearby period belongs to the entity.”
  - §2.1: “Do not include leading/trailing whitespace, list markers, external punctuation, or conjunctions.”
- **Options and what each would change:**
  - **ADOPT — shrink** to `Humulin N` at [1708,1717), MEDICATION. Changes: 1 span replaced by a shorter one; `insulin` and the period are left unlabelled.
  - **ADOPT — split**: `Humulin N` at [1708,1717) plus a separate `insulin` at [1719,1726), both MEDICATION (if `insulin` is judged an independent medication mention). Changes: 1 span replaced by 2.
  - **ADOPT — retain as is** (if `Humulin N. insulin` is judged the written product name). Changes: nothing in gold.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** In “Humulin N. insulin 50 units in a.m.” the period after `N` is either a stray sentence-style period or part of how the product is written, and `insulin` is either a trailing descriptor or part of the name. The note gives no further clue; `insulin` occurs only here in this note.
- **Considerations (not a recommendation):**
  - The policy example resolves the descriptor question toward the product name alone only “when `insulin` is only a trailing descriptor”, which is the judgment being asked.
  - A period inside the span (between `N` and `insulin`) is internal to the current span, not trailing; the “external punctuation” wording applies once the span ends at `N`.
  - Related, same list: `Nitroglycerin` (Candidate 9) has its own whitespace boundary question.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Shrink to `Humulin N` [1708,1717), MEDICATION; `insulin` stays unlabelled.
- **Recorded rationale:** Policy v1.0 §3 MEDICATION: label the product name alone when the following generic term is only a descriptor; §2.1 excludes external punctuation.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 8 — prophylactic antibiotics (queue M02)

- **Note ID:** `mtsamples_Pectoralis_Tendon_Repair`
- **Source filename:** `mtsamples_Pectoralis_Tendon_Repair.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
e was transferred to the operative table in supine position and placed under general anesthesia by anesthesiology team.  He then received prophylactic antibiotics.  A time-out was then undertaken verifying the correct patient, extremity, surgery performed, administration of antibiotics, and the avai
```
- **Current annotation (gold v1.1):** `prophylactic antibiotics` — `[2648,2672)` — `MEDICATION`
- **Original label (protected snapshot):** `MEDICATION` (unchanged)
- **Approved policy (quoted):**
  - §3 MEDICATION: “Include a specific medication product, generic drug name, or ingredient when the source uses it as medication.” and “Exclude broad therapeutic classes, such as `antibiotics`, `NSAIDs`, and `oral steroid`, when used as class references.”
  - §3 MEDICATION, human review: “The verified `prophylactic antibiotics` span is a review example, not an automatic exception to the broad-class rule.”
- **Options and what each would change:**
  - **ADOPT — remove**, no other label (class reference). Changes: 1 MEDICATION span removed.
  - **ADOPT — retain as is** (documented rationale that it is a medication mention as used). Changes: nothing in gold.
  - **REJECT** — record a different action and rationale. Changes: depends on the alternative recorded.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source cannot settle this.** The note states that the patient “received prophylactic antibiotics”, so administration is stated, but it names no drug, so it is a class reference. Whether a class reference that is clearly administered counts as a “medication mention as used” is the policy question; the policy text excludes class references but also says the decision rests on context.
- **Considerations (not a recommendation):**
  - The only other mention, `antibiotics` at [2785,2796) (in “administration of antibiotics”), is not annotated in gold; a decision here would be easiest to apply consistently if the two mentions are treated alike (that one would be a separate candidate).
  - `prophylactic` states purpose, not a drug identity.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove `prophylactic antibiotics` [2648,2672) from MEDICATION; assign no other label. The unannotated `antibiotics` at [2785,2796) stays unannotated.
- **Recorded rationale:** Policy v1.0 §3 MEDICATION excludes broad therapeutic classes used as class references; the span names no specific drug.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 9 — Leading space in ' Nitroglycerin' (queue M03)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
 coronary artery disease (father & brother).,MEDICATIONS: , Aspirin 81 milligrams QDay.  Humulin N. insulin 50 units in a.m.  HCTZ 50 mg QDay.  Nitroglycerin 1/150 sublingually PRN chest pain.,ALLERGIES: , Penicillin.,PHYSICAL EXAM: , The patient is a 40-year-old white male.,General:  The patient is
```
- **Current annotation (gold v1.1):** ` Nitroglycerin` — `[1762,1776)` — `MEDICATION`
- **Original label (protected snapshot):** `MEDICATION` (unchanged)
- **Approved policy (quoted):**
  - §2.1: “Store the exact source substring … `entity.text == source[start:end]`. … Do not include leading/trailing whitespace, list markers, external punctuation, or conjunctions.”
  - §3 MEDICATION: “Include a specific medication product, generic drug name, or ingredient when the source uses it as medication.”
- **Options and what each would change:**
  - **ADOPT — trim the leading space**, giving `Nitroglycerin` at [1763,1776), MEDICATION. Changes: 1 span replaced by one starting one character later; same label.
  - **REJECT** — keep the leading space (this would conflict with §2.1 as written; record the rationale). Changes: nothing in gold.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The source settles the boundary question.** `Nitroglycerin` begins at offset 1763; offset 1762 is a space. The word is a generic drug name listed under `MEDICATIONS`, so the label is not in question. §2.1 states the whitespace rule directly, so this item is a policy-directed boundary fix rather than a judgment call; it still needs your recorded decision.
- **Considerations (not a recommendation):**
  - The trimmed span is an exact source slice, so it also satisfies the project validator’s `text == source[start:end]` check.
  - Only the start offset changes; the end offset 1776 and the label stay the same.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Trim to `Nitroglycerin` [1763,1776), MEDICATION.
- **Recorded rationale:** Policy v1.0 §2.1 excludes leading and trailing whitespace.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Candidate 10 — chest pain in the chief-complaint sentence (queue SC03)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt, about 300 characters):**

```text
CHIEF COMPLAINT: , Chest pain.,HISTORY OF PRESENT ILLNESS:,  The patient is a 40-year-old white male who presents with a chief complaint of "chest pain".,The patient is diabetic and has a prior history of coronary artery disease.  The patient presents today stating that his chest pain started ye
```
- **Current annotation (gold v1.1):** `chest pain` — `[141,151)` — `CONDITION`
- **Original label (protected snapshot):** `CONDITION` (unchanged)
- **Approved policy (quoted):**
  - §3 SYMPTOM: “`Chest pain` is SYMPTOM, including under a diagnosis heading, as a chief complaint, or in `PRN chest pain`; do not assign CONDITION to the same span.”
  - §3 SYMPTOM: “Quotation alone does not disqualify a symptom.”
  - §4 item 3: “For `chest pain`, use SYMPTOM.”
- **Options and what each would change:**
  - **ADOPT — relabel to SYMPTOM** keeping `chest pain` at [141,151). Changes: 1 gold span moves CONDITION → SYMPTOM, matching the Batch 01 C8 decision for `Chest pain` at [19,29) in the same note.
  - **REJECT** — keep as CONDITION (this would conflict with §3 SYMPTOM as written; record the rationale). Changes: nothing in gold.
  - **DISCUSS** — keep unresolved. Changes: nothing.
- **Where the source can and cannot decide:** **The policy text settles this; the source adds no complication.** The phrase is the patient’s chief complaint quoted in the sentence “presents with a chief complaint of "chest pain"”, which the policy names as SYMPTOM. It needs your recorded decision because it is a gold change.
- **Considerations (not a recommendation):**
  - The same note has two other `chest pain` mentions that have **no gold span at all** in v1.1: [275,285) in “his chest pain started yesterday evening” and [1800,1810) in “PRN chest pain”. They are not candidates in this batch; §2.1 says each explicit symptom occurrence is annotated, so they would be separate additions to review.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Relabel `chest pain` [141,151) from CONDITION to SYMPTOM; keep the same span.
- **Recorded rationale:** Policy v1.0 §3 SYMPTOM and §4 item 3: chest pain is SYMPTOM, including as a chief complaint, and quotation alone does not disqualify a symptom.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-25

## Batch record

Decisions recorded by Advika Mishra on 2026-10-25.

- **ADOPT, changes gold (8):** Candidate 1 (SC02, relabel to SYMPTOM), 4 (D05, remove), 5 (D10, remove), 6 (D15, remove), 7 (M01, shrink to `Humulin N`), 8 (M02, remove), 9 (M03, trim leading space), 10 (SC03, relabel to SYMPTOM).
- **ADOPT, no gold change (1):** Candidate 3 (D04, retain as DURATION).
- **DISCUSS, unresolved (1):** Candidate 2 (SC04, `Edema`).
- **Additional approved additions (not worksheet candidates):** `chest pain` at [275,285) and `chest pain` at [1800,1810) in `mtsamples_Acute_Inferior_Myocardial_Infarction`, both to be added as SYMPTOM (Policy v1.0 §2.1: annotate each explicit occurrence; §3 SYMPTOM). They are recorded as two new rows in `gold_adjudication_log.csv`.

The protected snapshot, `gold_adjudicated_v1_1_20261024`, the approved policy and all existing results remain unchanged. Gold version reference for these log entries: `gold_adjudicated_v1_1_20261024`.
