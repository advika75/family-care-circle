# Adjudication Batch 01 — CONDITION Scope

**Human decision record.** Candidates 1–8 have recorded ADOPT decisions dated 2026-10-24; Candidates 9–10 remain recorded as DISCUSS. No gold annotation has been changed. The decision options are defined below for reference:

- **ADOPT** — accept the proposed action below for this candidate.
- **REJECT** — reject the proposed action; record the alternative and rationale.
- **DISCUSS** — defer the decision for further review.

The approved six-label schema remains `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`. Context excerpts below come from the source notes matched to the protected snapshot manifest. Original spans and offsets were checked against the copied JSON and `source[start:end]`.

## Batch selection

The batch takes the diagnostic shorthand, normal and abnormal imaging findings, and symptom-like CONDITION examples from the representative cases near the top of the prioritized queue. It includes six queue-designated representative examples and four related CONDITION-scope cases to compare normal findings and regurgitation findings across the same echocardiogram, plus edema alongside dyspnea. The queue references are included for traceability. No diagnosis beyond what the source states is inferred.

## Candidate 1 — `diabetic` (queue C01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Full relevant source context (verbatim excerpt):** `The patient is a 40-year-old white male who presents with a chief complaint of "chest pain".,The patient is diabetic and has a prior history of coronary artery disease.`
- **Original annotation:** `diabetic` — `[169,177)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: label `diabetic` as CONDITION when the text clearly asserts the patient's diagnosed disease state; preserve the stated word and do not expand it.
- **Proposed action:** Retain `diabetic` as CONDITION at `[169,177)`; do not expand the span.
- **Clarity:** The phrase “The patient is diabetic” directly asserts the disease state. The span is an exact source slice. This is a clear application of the approved shorthand rule.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** retain the exact word `diabetic` as CONDITION without expansion because the source clearly asserts the patient is diabetic, consistent with Policy v1.0 §3 CONDITION.
- **Recorded rationale:** The source clearly asserts that the patient is diabetic; Policy v1.0 §3 CONDITION directs retaining this exact word without expansion.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 2 — Normal ventricular size (queue C02)

- **Note ID:** `mtsamples_2-D_Echocardiogram_-_1`
- **Source filename:** `mtsamples_2-D_Echocardiogram_-_1.txt`
- **Full relevant source context (verbatim excerpt):** `2-D M-MODE: , ,1.  Left atrial enlargement with left atrial diameter of 4.7 cm.,2.  Normal size right and left ventricle.,3.  Normal LV systolic function with left ventricular ejection fraction of 51%.,4.  Normal LV diastolic function.,5.  No pericardial effusion.,6.  Normal morphology of aortic valve, mitral valve, tricuspid valve, and pulmonary valve.`
- **Original annotation:** `Normal size right and left ventricle` — `[84,120)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: exclude normal findings, anatomy alone, and measurements.
- **Proposed action:** Remove this span from CONDITION; do not assign another label.
- **Clarity:** “Normal size” is an explicitly normal imaging finding, not a stated diagnosis. The policy exclusion is direct; no diagnosis needs to be inferred.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION and assign no other label; Policy v1.0 §3 CONDITION excludes normal findings and anatomy alone.
- **Recorded rationale:** Policy v1.0 §3 CONDITION excludes normal findings and anatomy alone.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 3 — Normal systolic function and ejection fraction (queue C05)

- **Note ID:** `mtsamples_2-D_Echocardiogram_-_1`
- **Source filename:** `mtsamples_2-D_Echocardiogram_-_1.txt`
- **Full relevant source context (verbatim excerpt):** `2-D M-MODE: , ,1.  Left atrial enlargement with left atrial diameter of 4.7 cm.,2.  Normal size right and left ventricle.,3.  Normal LV systolic function with left ventricular ejection fraction of 51%.,4.  Normal LV diastolic function.,5.  No pericardial effusion.,6.  Normal morphology of aortic valve, mitral valve, tricuspid valve, and pulmonary valve.`
- **Original annotation:** `Normal LV systolic function with left ventricular ejection fraction of 51` — `[126,199)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: exclude normal findings and measurements.
- **Proposed action:** Remove this span from CONDITION; do not relabel the ejection-fraction measurement as another entity under this candidate.
- **Clarity:** The source explicitly calls the function normal, and the phrase includes an ejection-fraction measurement. The saved span ends before the source `%`, but the main policy issue is that the entire annotation is a normal finding/measurement and outside CONDITION scope.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION and do not relabel the measurement under this candidate; Policy v1.0 §3 CONDITION excludes normal findings and measurements.
- **Recorded rationale:** Policy v1.0 §3 CONDITION excludes normal findings and measurements.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 4 — Normal diastolic function (queue C06)

- **Note ID:** `mtsamples_2-D_Echocardiogram_-_1`
- **Source filename:** `mtsamples_2-D_Echocardiogram_-_1.txt`
- **Full relevant source context (verbatim excerpt):** `2-D M-MODE: , ,1.  Left atrial enlargement with left atrial diameter of 4.7 cm.,2.  Normal size right and left ventricle.,3.  Normal LV systolic function with left ventricular ejection fraction of 51%.,4.  Normal LV diastolic function.,5.  No pericardial effusion.,6.  Normal morphology of aortic valve, mitral valve, tricuspid valve, and pulmonary valve.`
- **Original annotation:** `Normal LV diastolic function` — `[206,234)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: exclude normal findings.
- **Proposed action:** Remove this span from CONDITION; do not assign another label.
- **Clarity:** The report explicitly describes normal function, so the policy exclusion applies without inferring a diagnosis.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION and assign no other label; Policy v1.0 §3 CONDITION excludes normal findings.
- **Recorded rationale:** Policy v1.0 §3 CONDITION excludes normal findings.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 5 — Mitral and tricuspid regurgitation (queue C03)

- **Note ID:** `mtsamples_2-D_Echocardiogram_-_1`
- **Source filename:** `mtsamples_2-D_Echocardiogram_-_1.txt`
- **Full relevant source context (verbatim excerpt):** `DOPPLER: , ,1.  Mild mitral and tricuspid regurgitation.,2.  Trace aortic and pulmonary regurgitation.`
- **Original annotation:** `Mild mitral and tricuspid regurgitation` — `[409,448)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: interpreted abnormal findings, including regurgitation, are excluded by default unless a precise, separately approved scope rule includes them consistently.
- **Proposed action:** Remove this interpreted finding from CONDITION unless the source elsewhere explicitly states it as a diagnosis under an approved scope rule.
- **Clarity:** The phrase appears in an echocardiogram Doppler findings list. Policy specifically names regurgitation as an example governed by the default exclusion. The source does not, in this excerpt, state a separate diagnosis.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION; Policy v1.0 §3 CONDITION excludes interpreted abnormal findings such as regurgitation by default absent a separately approved consistent scope rule.
- **Recorded rationale:** Policy v1.0 §3 CONDITION excludes interpreted abnormal findings such as regurgitation by default absent a separately approved consistent scope rule.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 6 — Aortic and pulmonary regurgitation (queue C09)

- **Note ID:** `mtsamples_2-D_Echocardiogram_-_1`
- **Source filename:** `mtsamples_2-D_Echocardiogram_-_1.txt`
- **Full relevant source context (verbatim excerpt):** `DOPPLER: , ,1.  Mild mitral and tricuspid regurgitation.,2.  Trace aortic and pulmonary regurgitation.`
- **Original annotation:** `Trace aortic and pulmonary regurgitation.` — `[454,495)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: interpreted abnormal findings, including regurgitation, are excluded by default unless covered by a precise, separately approved scope rule. Policy §2.1 excludes external punctuation.
- **Proposed action:** Remove this interpreted finding from CONDITION unless a separate approved scope rule applies. If a human elects to retain a diagnosis mention, review whether the final period belongs outside the entity span.
- **Clarity:** “Trace” is a reported degree of a Doppler finding. The default CONDITION scope excludes this category. The saved span also includes a terminal period, which is a distinct boundary question if the entity is retained.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION under the default exclusion for interpreted abnormal findings in Policy v1.0 §3 CONDITION. The external terminal period is separately excluded by §2.1 if any span is retained.
- **Recorded rationale:** Policy v1.0 §3 CONDITION excludes interpreted abnormal findings such as regurgitation by default; §2.1 excludes external punctuation.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 7 — Greater than 50% stenosis phrase (queue C04)

- **Note ID:** `mtsamples_Carotid_Ultrasound`
- **Source filename:** `mtsamples_Carotid_Ultrasound.txt`
- **Full relevant source context (verbatim excerpt):** `At the level of the carotid bifurcation, there is heterogeneous hard plaque present, but without grayscale evidence of greater than 50% stenosis.  Right common carotid waveform is normal with a peak systolic velocity of 0.474 m/second and an end-diastolic velocity of 0.131 m/second.`
- **Original annotation:** `greater than 50% stenosis` — `[375,400)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: exclude normal/negative findings and interpreted abnormal findings by default absent a precise approved inclusion rule.
- **Proposed action:** Remove this span from CONDITION because the source says there is *no* grayscale evidence of the stated stenosis threshold; do not infer stenosis from the phrase alone.
- **Clarity:** The negation is explicit in the source context. The span itself is an exact slice, but its placement as CONDITION appears inconsistent with both the negative context and default interpreted-finding scope.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** remove the annotation from CONDITION because the source explicitly states there is no grayscale evidence of this stenosis threshold. Policy v1.0 §3 excludes interpreted abnormal findings by default; §4 item 4 forbids inferring unstated concepts.
- **Recorded rationale:** The source explicitly says there is no grayscale evidence of this stenosis threshold; Policy v1.0 §3 CONDITION excludes interpreted abnormal findings by default.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 8 — Chief-complaint chest pain (queue SC01)

- **Note ID:** `mtsamples_Acute_Inferior_Myocardial_Infarction`
- **Source filename:** `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Full relevant source context (verbatim excerpt):** `CHIEF COMPLAINT: , Chest pain.,HISTORY OF PRESENT ILLNESS:,  The patient is a 40-year-old white male who presents with a chief complaint of "chest pain".`
- **Original annotation:** `Chest pain` — `[19,29)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 SYMPTOM and §4 conflict resolution: chest pain is SYMPTOM, including under a diagnosis heading or as a chief complaint; do not assign both CONDITION and SYMPTOM to one span.
- **Proposed action:** Change the label to `SYMPTOM`, keeping the exact span `[19,29)`.
- **Clarity:** The heading and surrounding text identify it as a patient complaint. The approved policy explicitly resolves this exact label distinction.
- **Recorded human decision:** [x] ADOPT  [ ] REJECT  [ ] DISCUSS
- **Confirmed action:** change the label to SYMPTOM and preserve [19,29). Policy v1.0 §3 SYMPTOM and §4 item 3 explicitly classify chest pain as SYMPTOM, including as a chief complaint, with no duplicate CONDITION label.
- **Recorded rationale:** Policy v1.0 §3 SYMPTOM and §4 item 3 explicitly classify chest pain as SYMPTOM, including as a chief complaint, while prohibiting a duplicate CONDITION label.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 9 — Dyspnea in admission diagnoses (queue SC02)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Full relevant source context (verbatim excerpt):** `ADMISSION DIAGNOSES:,1.  Seizure.,2.  Hypoglycemia.,3.  Anemia.,4.  Hypotension.,5.  Dyspnea.,6.  Edema.,DISCHARGE DIAGNOSES:,1.  Colon cancer, status post right hemicolectomy.,2.  Anemia.,3.  Hospital-acquired pneumonia.,4.  Hypertension.,5.  Congestive heart failure.,6.  Seizure disorder.`
- **Original annotation:** `Dyspnea` — `[85,92)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: a symptom does not become CONDITION solely because it appears under a diagnosis heading. Policy §3 SYMPTOM covers symptoms the patient experiences or reports.
- **Proposed action:** Favor `SYMPTOM` if this item denotes the patient's breathing complaint; do not infer a distinct disease. If the project treats this diagnosis-list entry itself as an explicit diagnosis, document why before retaining CONDITION.
- **Clarity:** “Dyspnea” ordinarily names a symptom, but this note supplies it only as an item under “ADMISSION DIAGNOSES” without a narrative assertion. The heading alone cannot settle the label under policy, so reviewer judgment is needed.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Recorded rationale:** The complete source note lists this term only under `ADMISSION DIAGNOSES`. The note does not resolve whether the entry represents an explicitly asserted diagnosis, a patient-experienced symptom, or an objective finding. No cause or clinical relationship is inferred.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Candidate 10 — Edema in admission diagnoses (queue SC04)

- **Note ID:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064`
- **Source filename:** `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.txt`
- **Full relevant source context (verbatim excerpt):** `ADMISSION DIAGNOSES:,1.  Seizure.,2.  Hypoglycemia.,3.  Anemia.,4.  Hypotension.,5.  Dyspnea.,6.  Edema.,DISCHARGE DIAGNOSES:,1.  Colon cancer, status post right hemicolectomy.,2.  Anemia.,3.  Hospital-acquired pneumonia.,4.  Hypertension.,5.  Congestive heart failure.,6.  Seizure disorder.`
- **Original annotation:** `Edema` — `[98,103)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: include explicitly stated diagnoses, but do not infer disease; §3 SYMPTOM: include reported symptoms and exclude objective findings unless wording independently describes a patient symptom. A section heading alone is not sufficient to turn a symptom into CONDITION.
- **Proposed action:** **DISCUSS.** Decide from the note whether `Edema` is an explicitly asserted diagnosis, a patient-reported symptom, or an objective finding. Do not infer a cause or expand the span.
- **Clarity:** “Edema” may be used as a diagnosis or as a finding; the excerpt gives no details that distinguish those uses. This case remains genuinely context-dependent.
- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [x] DISCUSS
- **Recorded rationale:** The complete source note lists this term only under `ADMISSION DIAGNOSES`. The note does not resolve whether the entry represents an explicitly asserted diagnosis, a patient-experienced symptom, or an objective finding. No cause or clinical relationship is inferred.
- **Reviewer:** Advika Mishra  **Decision date:** 2026-10-24

## Batch decision record

Candidates 1–8 are recorded as **ADOPT** by Advika Mishra on 2026-10-24, with the confirmed actions and policy-based rationales shown in each entry. Candidates 9 (`Dyspnea`) and 10 (`Edema`) remain **DISCUSS** with their recorded rationale. These decisions record human review only; the protected snapshot annotations remain unchanged. Other candidates remain pending. The log uses gold version reference `gold_adjudication_v1_20261024`.
