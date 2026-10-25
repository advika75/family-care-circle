# Adjudication Batch 02 — DURATION Context

**Human decision record.** The decisions below were confirmed by Advika Mishra on 2026-10-24. ADOPT records the review decision only; it does not apply annotation changes. The protected snapshot remains unchanged.

## Batch selection

This batch reviews nine unreviewed DURATION candidates from the prioritized queue. It starts with the queue’s DURATION representatives and samples symptom timelines, procedure/test elapsed time, retrospective medication use, and care-instruction timing. Candidates D01–D03 already have pending rows in the log but were not decided in Batch 01; the other selected candidates have no recorded decision. Original annotations remain unchanged.

Offsets are zero-based Python character offsets with an exclusive end. Exact saved text was checked against `source[start:end]`, the copied annotation JSON, and the protected snapshot manifest. “Possible issue” describes a policy question, not a confirmed annotation error.

## Candidate 1 — one-hour. (queue D01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
the past 1 hour, which he states has partially relieved his pain.  The patient ranks his present pain a 4 on a scale of 1-10.  The most recent episode of pain has lasted one-hour.,The patient denies any history of recent surgery, head trauma, recent stroke, abnormal bleeding such as blood in urine or stool or nosebleed.,REVIEW OF SYSTEMS:,  All other systems reviewed & are negative.,PAST
```
- **Original annotation:** `one-hour.` — `[1123,1132)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION; §2.1 exact boundaries. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The interval states how long a pain episode lasted, which is a symptom timeline excluded by §3 DURATION. The stored span also includes a period before a comma in the source; the semantic exclusion is the primary issue, and the period boundary need not be resolved if the mention is removed.
- **Recommended action (not approved):** Recommend removing this mention from DURATION; do not assign another label under this review candidate.
- **Clarity / edge case:** Low semantic ambiguity: source directly ties the interval to a pain episode. The exact terminal punctuation convention is a separate structural question only if a label is retained.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove from DURATION because it describes the duration of a pain episode.
- **Recorded rationale:** Policy v1.0 §3 DURATION excludes symptom timelines; this interval states how long a pain episode lasted.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 2 — 20 minutes (queue D02)

- **Note ID:** `mtsamples_Tilt_Table_Test_-_1`
- **Source filename:** `mtsamples_Tilt_Table_Test_-_1.txt`
- **Relevant source context (verbatim excerpt):**

```text
dizziness.  She was referred here by Dr. X for tilt table.,TECHNIQUE: , Risks and benefits explained to the patient.  Consent obtained.  She was lying down on her back for 20 minutes and her blood pressure was 111/75 and heart rate 89.  She was standing up on the tilt tablet for 20 minutes and her heart rate went up to 127 and blood pressure was still in 120/80.  Then, the patient received
```
- **Original annotation:** `20 minutes` — `[297,307)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The interval measures time spent lying during a tilt-table test, rather than how long a treatment or care instruction continues. §3 explicitly excludes procedure/test elapsed time.
- **Recommended action (not approved):** Recommend removing this mention from DURATION; do not assign another label under this review candidate.
- **Clarity / edge case:** Low semantic ambiguity: the surrounding text identifies a test technique and elapsed positioning time.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove from DURATION because it describes time spent lying during a tilt-table test.
- **Recorded rationale:** Policy v1.0 §3 DURATION excludes procedure/test elapsed time; this interval measures time spent lying during a tilt-table test.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 3 — 20 minutes (queue D03)

- **Note ID:** `mtsamples_Tilt_Table_Test_-_1`
- **Source filename:** `mtsamples_Tilt_Table_Test_-_1.txt`
- **Relevant source context (verbatim excerpt):**

```text
patient.  Consent obtained.  She was lying down on her back for 20 minutes and her blood pressure was 111/75 and heart rate 89.  She was standing up on the tilt tablet for 20 minutes and her heart rate went up to 127 and blood pressure was still in 120/80.  Then, the patient received sublingual nitroglycerin 0.4 mg.  The patient felt dizzy at that time and heart rate was in the 120 and blood
```
- **Original annotation:** `20 minutes` — `[405,415)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The interval measures time spent standing during the tilt-table test. §3 explicitly excludes procedure/test elapsed time.
- **Recommended action (not approved):** Recommend removing this mention from DURATION; do not assign another label under this review candidate.
- **Clarity / edge case:** Low semantic ambiguity: source directly describes standing during the test. This is a separate original span from D02 in the same note.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove from DURATION because it describes time spent standing during a tilt-table test.
- **Recorded rationale:** Policy v1.0 §3 DURATION excludes procedure/test elapsed time; this interval measures time spent standing during a tilt-table test.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 4 — approximately 10 days (queue D04)

- **Note ID:** `mtsamples_Pectoralis_Tendon_Repair`
- **Source filename:** `mtsamples_Pectoralis_Tendon_Repair.txt`
- **Relevant source context (verbatim excerpt):**

```text
in a shoulder immobilizer with the arm adducted and internally rotated.,Plan for this patient, the patient will remain in the shoulder immobilizer until followup visit in approximately 10 days.  We will then start a gentle Codman type exercises and having limited motion until the 4-6 week point based on the patient's progression.

```
- **Original annotation:** `approximately 10 days` — `[5294,5315)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The source expressly instructs that the patient remain in an immobilizer until a follow-up visit, making it potentially a care-instruction duration. The same phrase also gives the follow-up timing, which §3 excludes. The policy requires clear context for a treatment/care instruction and excludes follow-up timing.
- **Recommended action (not approved):** Recommend DISCUSS: determine whether the phrase expresses how long the immobilizer care instruction continues or only a follow-up interval; record a final choice before any annotation change.
- **Clarity / edge case:** Genuine boundary-of-scope ambiguity: the 10-day interval can be read as the duration of the immobilizer instruction or as timing of the follow-up visit. Avoid inferring any additional treatment plan.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** Leave unresolved. The interval may describe immobilizer duration or follow-up timing.
- **Recorded rationale:** The interval may describe immobilizer duration or follow-up timing; the approved DURATION rule does not settle which reading applies here.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 5 — over the past 1 hour (queue D05)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Relevant source context (verbatim excerpt):**

```text
somewhat worse with walking and seems to be relieved with rest.  There is no change in pain with positioning.  He states that he took 3 nitroglycerin tablets sublingually over the past 1 hour, which he states has partially relieved his pain.  The patient ranks his present pain a 4 on a scale of 1-10.  The most recent episode of pain has lasted one-hour.,The patient denies any history of recent surgery,
```
- **Original annotation:** `over the past 1 hour` — `[948,968)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION; DOSAGE/FREQUENCY boundaries in §3. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The phrase reports a past medication-use interval associated with relief, not clearly how long a medication, treatment, or care instruction is to continue. Policy §3 requires a clear treatment/care target and does not support inferring a regimen from a retrospective interval.
- **Recommended action (not approved):** Recommend removing from DURATION unless human review finds that context explicitly states a treatment/care-instruction duration. Do not automatically relabel as DOSAGE or FREQUENCY.
- **Clarity / edge case:** Some ambiguity remains because the interval modifies taking nitroglycerin, but the sentence describes past use, not a stated ongoing cadence or duration instruction. Human review should decide whether this is simply elapsed history.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** Leave unresolved. The span describes retrospective nitroglycerin use, and the approved policy does not clearly settle this case.
- **Recorded rationale:** The span describes retrospective nitroglycerin use; the approved DURATION policy does not clearly settle this case.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 6 — one month ago (queue D08)

- **Note ID:** `mtsamples_Leaking_Nephrostomy_Tube`
- **Source filename:** `mtsamples_Leaking_Nephrostomy_Tube.txt`
- **Relevant source context (verbatim excerpt):**

```text
The leaking began this a.m.  The patient denies any pain, does not have fever and has no other problems or complaints.  The patient had bilateral nephrostomy tubes placed one month ago secondary to his prostate cancer metastasizing and causing bilateral ureteral obstructions that were severe enough to cause acute renal failure.  The patient states he feels like his usual self and has no other
```
- **Original annotation:** `one month ago` — `[385,398)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The source marks elapsed time since a placement event. The approved DURATION definition covers continuation intervals for treatment/care instructions; it does not make an event date into a duration.
- **Recommended action (not approved):** Recommend removing from DURATION; the phrase indicates when tube placement occurred, not how long treatment or a care instruction is to continue.
- **Clarity / edge case:** Low semantic ambiguity: `ago` anchors the interval to a past event. No further cause or clinical relationship should be inferred.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove from DURATION because it states when tube placement occurred, not how long treatment continues.
- **Recorded rationale:** Policy v1.0 §3 DURATION covers how long treatment or care instructions continue; `one month ago` states when tube placement occurred.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 7 — several minutes (queue D09)

- **Note ID:** `mtsamples_Low-Transverse_C-Section`
- **Source filename:** `mtsamples_Low-Transverse_C-Section.txt`
- **Relevant source context (verbatim excerpt):**

```text
clamped and cut.  The infant was subsequently handed to the awaiting nursery nurse.  Next, cord blood was obtained per the patient's request for cord blood donation, which took several minutes to perform.  Subsequent to the collection of this blood, the placenta was removed spontaneously intact with a 3-vessel cord noted.  The uterus was exteriorized and cleared of all clots and debris.  The uterine
```
- **Original annotation:** `several minutes` — `[2866,2881)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The interval describes elapsed time to perform a procedure, expressly excluded by §3 DURATION.
- **Recommended action (not approved):** Recommend removing from DURATION; do not assign another label under this review candidate.
- **Clarity / edge case:** Low semantic ambiguity: `to perform` directly identifies procedure time.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** Remove from DURATION because it describes procedure elapsed time.
- **Recorded rationale:** Policy v1.0 §3 DURATION excludes procedure elapsed time; this interval describes how long cord blood collection took to perform.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 8 — for 26 years (queue D10)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Relevant source context (verbatim excerpt):**

```text
Colonoscopy.,2.  Right hemicolectomy.,HOSPITAL COURSE: , The patient is a 59-year-old female with multiple medical problems including diabetes mellitus requiring insulin for 26 years, previous MI and coronary artery disease, history of seizure disorder, GERD, bipolar disorder, and anemia.  She was admitted due to a seizure and myoclonic jerks as well as hypoglycemia and anemia.  Regarding the
```
- **Original annotation:** `for 26 years` — `[488,500)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION; §4 item 4. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The source explicitly links the interval to insulin requirement, but describes how long that requirement has existed rather than how long a future treatment or care instruction is to continue. The policy does not explicitly resolve retrospective treatment-history intervals.
- **Recommended action (not approved):** Recommend DISCUSS: decide whether a stated historical/ongoing duration of insulin use falls within the treatment-duration rule. Do not add a target or infer a regimen beyond the source.
- **Clarity / edge case:** Genuine policy edge case: medication treatment is named, yet the temporal frame is historical/ongoing history. Do not infer a stop date, dose, or future instruction.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** Leave unresolved. The span describes historical insulin use, and the approved policy does not explicitly settle retrospective treatment-history intervals.
- **Recorded rationale:** The span describes historical insulin use; the approved DURATION policy does not explicitly settle retrospective treatment-history intervals.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 9 — 24-48 hours (queue D15)

- **Note ID:** `mtsamples_Tenosynovectomy_Cortisone_Injection`
- **Source filename:** `mtsamples_Tenosynovectomy_Cortisone_Injection.txt`
- **Relevant source context (verbatim excerpt):**

```text
medication is Darvocet-N 100, 30 tablets, one to two PO q.4h. p.r.n.  Patient asked to begin gentle active flexion, extension and passive nerve glide exercises beginning 24-48 hours after surgery.  She was asked to keep the dressings clean, dry and intact and follow up in my office.

```
- **Original annotation:** `24-48 hours` — `[3495,3506)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION; §4 item 4. Policy v1.0 §3 DURATION includes how long treatment/care instructions continue, requires a clear target, and excludes symptom timelines, follow-up timing, and procedure/test elapsed time as applicable.
- **Possible issue:** The approved DURATION rule covers how long medication, treatment, or care instructions continue. This phrase gives a start delay after surgery, a temporal instruction that is not itself a duration of continuation.
- **Recommended action (not approved):** Recommend removing from DURATION; the phrase indicates when exercises should begin, not how long an instruction continues.
- **Clarity / edge case:** Low to moderate ambiguity: it is an explicit care instruction, but its temporal role is a start time, not a treatment interval. The policy does not list start delays as DURATION examples.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Confirmed action:** Leave unresolved. The interval specifies when exercises should begin, not how long they continue; the policy interpretation needs confirmation.
- **Recorded rationale:** The interval specifies when exercises should begin, not how long they continue; confirmation is needed on whether this fits the approved DURATION rule.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Batch record

Decisions are recorded for D01–D05, D08–D10, and D15 as shown above. D04, D05, D10, and D15 remain unresolved as DISCUSS. No annotation has been changed; the protected snapshot, manifest, approved policy, and evaluation outputs remain unchanged.
