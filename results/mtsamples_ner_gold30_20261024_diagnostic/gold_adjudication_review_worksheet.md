# MTSamples Gold Adjudication Review Worksheet

**Human review only.** This worksheet records recommendations for review; it does not adjudicate or authorize automatic changes. The approved schema remains exactly `MEDICATION`, `DOSAGE`, `FREQUENCY`, `DURATION`, `CONDITION`, and `SYMPTOM`. All nine original spans below are copied from the prefilled rows in `gold_adjudication_log.csv` and checked against the source slice. Proposed interpretations are suggestions only. Record a decision in the adjudication log after human review.

Source notes are under `data/public/mtsamples/notes/`; the corresponding annotation snapshot is `data/public/mtsamples/gold_adjudication_v1_20261024/`. Offsets are zero-based Python character offsets with an exclusive end.

## Prefilled candidates

### 1. `diabetic` — CONDITION

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** “The patient is diabetic and has a prior history of coronary artery disease.”
- **Original annotation:** `diabetic` — `[169,177)` — `CONDITION`
- **Approved rule:** Policy v1.0 §3 CONDITION: include explicitly stated diagnoses; `diabetic` is CONDITION when it clearly asserts a diagnosed disease state, without expanding the source span.
- **Possible issue:** The word is adjectival shorthand, but this sentence directly asserts the patient's disease state. This is a scope question, not evidence that the saved annotation is wrong.
- **Recommendation for confirmation:** Retain `diabetic` as CONDITION at `[169,177)`, since the sentence asserts that the patient is diabetic. Do not expand the span.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 2. `shortness of breath & diaphoresis` — coordinated SYMPTOM mentions

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** “He ranks the pain a 7 on a scale of 1-10. He admits some shortness of breath & diaphoresis. He states that he has had nausea …”
- **Original annotation:** `shortness of breath & diaphoresis` — `[550,583)` — `SYMPTOM`
- **Approved rule:** Policy v1.0 §§2.2–2.3 and §3 SYMPTOM: use shortest complete meaningful spans, split independent coordinated mentions, omit conjunctions, and keep spans non-overlapping.
- **Possible issue:** This span joins two independently meaningful symptoms with `&`. It may instead be intended as one coordinated phrase, so confirm segmentation against the rule.
- **Recommendation for confirmation:** Split into `shortness of breath` `[550,569)` and `diaphoresis` `[572,583)`, both `SYMPTOM`; omit `&` and intervening whitespace.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 3. `ever or chills` — negated, coordinated SYMPTOM mentions

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** “He denies any fever or chills. He admits prior episodes of similar pain …”
- **Original annotation:** `ever or chills` — `[669,683)` — `SYMPTOM`
- **Approved rule:** Policy v1.0 §§2.1–2.2 and §3 SYMPTOM: include explicit negated mentions; split independent coordinated symptoms; exclude conjunctions and outside context; preserve the full source term.
- **Possible issue:** The span starts one character after the `f` in `fever` and includes `or`. The symptoms are negated, but negation does not itself exclude a mention under policy.
- **Recommendation for confirmation:** Retain two negated symptom mentions as `fever` `[668,673)` and `chills` `[677,683)`, each `SYMPTOM`; omit `or`.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 4. ` episodes of vomiting` — SYMPTOM boundary

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** “He states that he has had nausea & 3 episodes of vomiting tonight. He denies any fever or chills.”
- **Original annotation:** ` episodes of vomiting` — `[622,643)` — `SYMPTOM`
- **Approved rule:** Policy v1.0 §§2.1–2.2 and §3 SYMPTOM: exclude leading whitespace and framing words; use the shortest complete meaningful symptom span.
- **Possible issue:** The saved span includes a leading space and the framing phrase `episodes of`. The number of episodes is context; whether it is needed to express the symptom identity should be confirmed under the shortest-complete rule.
- **Recommendation for confirmation:** Use `vomiting` `[635,643)` as SYMPTOM, with no leading space or framing words.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 5. `one-hour.` — DURATION

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** “The most recent episode of pain has lasted one-hour.” The raw note continues with a comma after the period.
- **Original annotation:** `one-hour.` — `[1123,1132)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION: include treatment and care-instruction durations; exclude symptom timelines. Section §2.1 excludes external sentence punctuation.
- **Possible issue:** This interval describes how long a pain episode lasted, not how long treatment or a care instruction continues. The stored span also includes a period that appears to be sentence punctuation.
- **Recommendation for confirmation:** Remove this mention from DURATION because it is a symptom timeline. If a human determines another label applies, record that separately with rationale; do not reclassify automatically.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 6. `Humulin N. insulin` — MEDICATION boundary

- **Note/source:** `mtsamples_Acute_Inferior_Myocardial_Infarction` / `mtsamples_Acute_Inferior_Myocardial_Infarction.txt`
- **Source context:** Medication list: “Aspirin 81 milligrams QDay. Humulin N. insulin 50 units in a.m. HCTZ 50 mg QDay.”
- **Original annotation:** `Humulin N. insulin` — `[1708,1726)` — `MEDICATION`
- **Approved rule:** Policy v1.0 §3 MEDICATION: include specific products and medication generics/ingredients used as medication; when a generic is only a trailing descriptor, label the product alone; preserve exact name punctuation and refer unclear boundaries for review.
- **Possible issue:** `Humulin N` is the specific product; `insulin` may be a descriptor. The period after `N` is source punctuation and may not belong to the product name. The policy expressly treats this as context-sensitive.
- **Recommendation for confirmation:** Prefer `Humulin N` `[1708,1717)` as MEDICATION if the reviewer confirms `insulin` is only a descriptor; exclude the following period. If context supports a separate insulin mention or a different name boundary, document that rationale instead.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 7. `prophylactic antibiotics` — MEDICATION

- **Note/source:** `mtsamples_Pectoralis_Tendon_Repair` / `mtsamples_Pectoralis_Tendon_Repair.txt`
- **Source context:** “He then received prophylactic antibiotics. A time-out was then undertaken …”
- **Original annotation:** `prophylactic antibiotics` — `[2648,2672)` — `MEDICATION`
- **Approved rule:** Policy v1.0 §3 MEDICATION: include specific products, generics, or ingredients used as medication; exclude broad therapeutic classes. Determine ambiguous cases from context and refer for human review.
- **Possible issue:** The phrase names a class of drugs rather than a specific product or ingredient, but it describes administration. The class-versus-medication-category distinction remains context-sensitive.
- **Recommendation for confirmation:** Favor excluding the phrase as a broad class reference because no agent is named, while explicitly requiring reviewer confirmation under the policy's unresolved case guidance. Do not treat this recommendation as settled.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 8. First `20 minutes` — DURATION

- **Note/source:** `mtsamples_Tilt_Table_Test_-_1` / `mtsamples_Tilt_Table_Test_-_1.txt`
- **Source context:** “Consent obtained. She was lying down on her back for 20 minutes and her blood pressure was 111/75 and heart rate 89.”
- **Original annotation:** `20 minutes` — `[297,307)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION: exclude procedure/test elapsed time, even when the interval is explicit.
- **Possible issue:** The interval measures time spent in a position during a tilt-table test, not a treatment or care instruction.
- **Recommendation for confirmation:** Remove this mention from DURATION as procedure/test elapsed time.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

### 9. Second `20 minutes` — DURATION

- **Note/source:** `mtsamples_Tilt_Table_Test_-_1` / `mtsamples_Tilt_Table_Test_-_1.txt`
- **Source context:** “She was standing up on the tilt tablet for 20 minutes and her heart rate went up to 127 …”
- **Original annotation:** `20 minutes` — `[405,415)` — `DURATION`
- **Approved rule:** Policy v1.0 §3 DURATION: exclude procedure/test elapsed time, even when the interval is explicit.
- **Possible issue:** This is another measured interval within the tilt-table procedure, not treatment duration.
- **Recommendation for confirmation:** Remove this mention from DURATION as procedure/test elapsed time.
- **Final decision:** ____________________  **Reviewer:** ____________________  **Decision date:** ____________________

## Additional candidates from the read-only scan

I scanned all 30 copied annotation JSON files (529 entity spans). The snapshot verification reports exact source slices, valid offsets, and no overlapping spans. The scan found **70 additional candidate spans** for human review, separate from the nine prefilled candidates above. These are possible policy mismatches, not confirmed annotation errors. No span was changed or added to the adjudication log.

### CONDITION candidates (46)

The approved policy includes explicit diagnoses, excludes normal findings, defaults interpreted abnormal findings out of CONDITION unless a separate inclusion rule is approved, and requires `chest pain` to be SYMPTOM. These spans need contextual review; the imaging and measurement examples in particular may be findings rather than diagnoses.

| Note ID | Original CONDITION span(s) and offsets | Review question |
|---|---|---|
| `mtsamples_2-D_Echocardiogram_-_1` | `[84,120)` `Normal size right and left ventricle`; `[126,199)` `Normal LV systolic function with left ventricular ejection fraction of 51`; `[206,234)` `Normal LV diastolic function`; `[239,263)` ` No pericardial effusion`; `[269,354)` `Normal morphology of aortic valve, mitral valve, tricuspid valve, and pulmonary valve`; `[409,448)` `Mild mitral and tricuspid regurgitation`; `[454,495)` `Trace aortic and pulmonary regurgitation.` | Normal/negative findings appear outside CONDITION scope; regurgitation is an interpreted abnormal finding, excluded by default pending a specific approved scope. |
| `mtsamples_Acute_Inferior_Myocardial_Infarction` | `[19,29)` `Chest pain`; `[141,151)` `chest pain` | The approved rule assigns chest pain to SYMPTOM, including under a diagnosis heading. |
| `mtsamples_Carotid_Cerebral_Arteriograms` | `[264,314)` `Mild stenosis of the right internal carotid artery`; `[1701,1730)` `mild plaque creating stenosis` | Interpreted imaging findings (stenosis/plaque) are CONDITION only if included by a separate approved scope rule. |
| `mtsamples_Carotid_Ultrasound` | `[225,248)` `mild intimal thickening`; `[306,331)` `heterogeneous hard plaque`; `[375,400)` `greater than 50% stenosis`; `[685,701)` `plaque formation`; `[722,747)` `greater than 50% stenosis`; `[1188,1206)` `intimal thickening`; `[1290,1317)` `pronounced plaque formation`; `[1323,1349)` `approximately 50% stenosis`; `[1612,1642)` `prominent focus of hard plaque`; `[1654,1675)` `at least 50% stenosis`; `[2197,2218)` `bilateral hard plaque`; `[2274,2295)` `at least 50% stenosis` | Imaging abnormalities; determine whether each is an explicitly stated diagnosis or an interpreted abnormal finding excluded by default. |
| `mtsamples_Chest_Pulmonary_Angio` | `[641,687)` `very large heterogeneous right chest wall mass`; `[1060,1087)` `bilateral pleural effusions`; `[1149,1160)` `atelectasis`; `[1178,1213)` `extensive right lung consolidations`; `[1692,1757)` `aortic root and arch and descending thoracic aortic calcification`; `[1791,1802)` `soft plaque`; `[2494,2521)` `large right chest wall mass`; `[2751,2781)` `consolidations and infiltrates` | Radiology findings and abnormalities; apply the default exclusion unless the text states a diagnosis or a separate scope rule covers them. |
| `mtsamples_Full-Field_Digital_Mammogram_FFDM_-_2` | `[591,621)` `skin thickening and retraction`; `[936,974)` `postsurgical and postradiation changes`; `[983,1019)` `benign-appearing microcalcifications` | Imaging findings; determine whether any are explicit diagnoses under policy scope. |
| `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064` | `[85,92)` `Dyspnea`; `[98,103)` `Edema`; `[2105,2138)` `mass at the right hepatic flexure` | Dyspnea/edema are symptom-like terms labeled CONDITION; the mass may be a finding rather than an explicit diagnosis. Check source context and approved scope. |
| `mtsamples_Prostate_Adenocarcinoma_-_H_P` | `[415,436)` `right parietal lesion` | Determine whether the note asserts a diagnosis or reports a finding. |
| `mtsamples_Total_Thyroid_Lumpectomy` | `[26,43)` `Left thyroid mass`; `[72,89)` `Left thyroid mass`; `[340,364)` `left thyroid mass nodule` | Mass/nodule may be an abnormal finding; inspect context for an explicit diagnosis. |
| `mtsamples_Transesophageal_Echocardiogram` | `[610,632)` `Left atrium is dilated`; `[1055,1084)` `moderate mitral regurgitation`; `[1297,1316)` `Dilated left atrium`; `[1322,1351)` `Moderate mitral regurgitation`; `[1357,1379)` `Aortic valve sclerosis` | Interpreted abnormal findings; excluded by default absent a separately approved, consistent inclusion rule. |

### DURATION candidates (21)

These intervals may describe symptom timelines, elapsed time since an event, procedure/test time, follow-up timing, or historical medication use rather than a treatment/care-instruction duration. Some are ambiguous; verify the full source context before any decision.

| Note ID | Original DURATION span and offsets | Review question |
|---|---|---|
| `mtsamples_Acute_Inferior_Myocardial_Infarction` | `[948,968)` `over the past 1 hour` | Is this a medication dosing window/cadence or another time interval? Do not treat as DURATION without a clear treatment/care-instruction target. |
| `mtsamples_Bunionectomy_Osteotomy` | `[642,669)` `over the past several years` | Symptom history timeline. |
| `mtsamples_EMG_Nerve_Conduction_Study_-_6` | `[209,219)` `four-month` | Pain history/timeline. |
| `mtsamples_Leaking_Nephrostomy_Tube` | `[385,398)` `one month ago` | Time since tube placement, not treatment duration. |
| `mtsamples_Low-Transverse_C-Section` | `[2866,2881)` `several minutes` | Elapsed time to perform cord blood collection. |
| `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064` | `[488,500)` `for 26 years` | Historical duration of insulin use; determine whether policy includes this as treatment duration or excludes history. |
| `mtsamples_Pectoralis_Tendon_Repair` | `[5294,5315)` `approximately 10 days` | Immobilizer instruction until follow-up in 10 days overlaps care-instruction duration and follow-up timing; human interpretation needed. |
| `mtsamples_Psychosocial_Eval_for_Kidney_Transplant` | `[149,158)` `Two weeks`; `[387,395)` `6 months` | “Later” event timelines. |
| `mtsamples_Spinal_fluid_evaluation` | `[5348,5368)` `less than 30 minutes` | Critical-care provider time, not a medication/treatment regimen duration. |
| `mtsamples_Status_Post_T_A` | `[77,90)` `two weeks ago` | Time since surgery. |
| `mtsamples_Tenosynovectomy_Cortisone_Injection` | `[3495,3506)` `24-48 hours` | Time until exercise begins after surgery; distinguish instruction timing from duration. |
| `mtsamples_Tilt_Table_Test_-_1` | `[972,980)` `one week` | Follow-up interval. |
| `mtsamples_Total_Knee_Replacement` | `[341,351)` `76 minutes`; `[981,998)` `for several years`; `[1030,1049)` `past several months` | First is tourniquet/procedure time; latter spans describe pain timelines. |
| `mtsamples_Total_Thyroid_Lumpectomy` | `[4865,4873)` `one week` | Follow-up interval. |
| `mtsamples_Weight_Gain_and_Edema` | `[161,184)` `over the last few weeks`; `[475,484)` `for years`; `[660,683)` `for the last few months`; `[2609,2618)` `six weeks` | Symptom/weight-gain timeline, possible historical medication-use duration, and repeat thyroid-function test timing; inspect each context separately. |

### Other boundary or coordination candidates (3)

| Note ID | Original span and offsets | Label | Review question |
|---|---|---|---|
| `mtsamples_Acute_Inferior_Myocardial_Infarction` | `[1762,1776)` ` Nitroglycerin` | MEDICATION | Leading whitespace conflicts with the exact-boundary rule; confirm the drug span without the space. |
| `mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064` | `[4565,4598)` `Calcium and vitamin D combination` | MEDICATION | Could be a named combination product or coordinated independent ingredients; determine the actual mention and boundary. |
| `mtsamples_Status_Post_T_A` | `[993,1026)` `mouth or jaws are still sensitive` | SYMPTOM | May describe one symptom across alternate sites or coordinated mentions; decide whether segmentation should split while preserving complete symptom meanings. |

## Review record

For each candidate, record the human decision, reviewer, and date in the adjudication log. If a gold change is approved, document the exact old and new spans, rationale, source offsets, policy rule, and gold-version reference; preserve this snapshot and make changes only in a separately versioned gold set. No candidate above has been adjudicated in preparing this worksheet.
