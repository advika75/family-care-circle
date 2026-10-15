# Error analysis

Outputs: `data/public/mtsamples/outputs` · 100 notes · backend: llama_cpp (100)
Settings: child max grade 3, minimum 20 words per output.

| Category | Failures | Notes affected | Meaning |
|---|---|---|---|
| missing_entity | 0 | 0 / 100 | Required entity missing from the final output |
| fallback_used | 12 | 11 / 100 | Model omitted required facts; the fallback had to append them |
| format_or_retries | 25 | 21 / 100 | Invalid JSON/format, or all retries used up |
| unsupported_content | 208 | 81 / 100 | Number or medication not supported by the source note (possible hallucination) |
| child_reading_level | 37 | 37 / 100 | Child explanation above the maximum reading grade |
| truncated | 5 | 4 / 100 | Generation stopped at max_new_tokens, so the text is cut off |
| repetition | 25 | 24 / 100 | A bullet (caregiver) or sentence (other personas) duplicates or nearly duplicates an earlier one |
| empty_or_short | 0 | 0 / 100 | Empty or very short output |

Failures are counted per (note, persona), and per item for unsupported content.

## missing_entity (0)

_Required entity missing from the final output._

No failures.

## fallback_used (12)

_Model omitted required facts; the fallback had to append them._

**mtsamples_Acute_Inferior_Myocardial_Infarction · caregiver_checklist**: after 2 retries the model still omitted 50 mg; the fallback appended them

> **Source:** CHIEF COMPLAINT: , Chest pain.,HISTORY OF PRESENT ILLNESS:, The patient is a 40-year-old white male who presents with a chief complaint of "chest pain".,The patient is diabetic and has a prior history of coronary artery …
>
> **Output:** …as any allergic reactions, including an allergic reaction to penicillin. Confirm with the care team: 50 mg (dosage)

**mtsamples_Attempted_Suicide_-_Consult · caregiver_checklist**: after 2 retries the model still omitted 1 mg, 450 mg, 1000 mg; the fallback appended them

> **Source:** IDENTIFYING DATA: , The patient is a 21-year-old Caucasian male, who attempted suicide by trying to jump from a moving car, which was being driven by his mother. Additionally, he totaled his own car earlier in the day, b…
>
> **Output:** … patient's girlfriend to inform her of the discharge and follow-up plan. Confirm with the care team: 1 mg (dosage) Confirm with the care team: 450 mg (dosage) Confirm with the care team: 1000 mg (dosage)

**mtsamples_Foreign_Object_Removal_-_Urethra · caregiver_checklist**: after 2 retries the model still omitted 15 g, 22 g; the fallback appended them

> **Source:** PREOPERATIVE DIAGNOSIS: , Prostate cancer.,POSTOPERATIVE DIAGNOSIS: , Prostate cancer.,OPERATION: , Cystoscopy and removal of foreign objects from the urethra.,BRACHYTHERAPY:, Iodine 125.,ANESTHESIA: , General endotrache…
>
> **Output:** …rsen. Schedule a prostate size measurement 2 months after the procedure. Confirm with the care team: 15 g (dosage) Confirm with the care team: 22 g (dosage)

## format_or_retries (25)

_Invalid JSON/format, or all retries used up._

**mtsamples_Acute_Inferior_Myocardial_Infarction · patient_summary**: used all 2 retries (succeeded on the last attempt)

> **Source:** CHIEF COMPLAINT: , Chest pain.,HISTORY OF PRESENT ILLNESS:, The patient is a 40-year-old white male who presents with a chief complaint of "chest pain".,The patient is diabetic and has a prior history of coronary artery …
>
> **Output:** You're feeling chest pain, and it's been getting worse. You have a history of diabetes, heart problems, and had a heart procedure before. You've been taking some medicine for your heart and diabetes. You also take a spec…

**mtsamples_Attempted_Suicide_-_Consult · caregiver_checklist**: used all 2 retries (fallback used)

> **Source:** IDENTIFYING DATA: , The patient is a 21-year-old Caucasian male, who attempted suicide by trying to jump from a moving car, which was being driven by his mother. Additionally, he totaled his own car earlier in the day, b…
>
> **Output:** Check that the patient has all medications from the hospital bag. Monitor for signs of agitation or psychomotor hyperactivity. Watch for any new or worsening depressive symptoms. Call Dr. X for a follow-up appointment in…

**mtsamples_Consult_-_Knee_Pain · patient_summary**: used all 2 retries (succeeded on the last attempt)

> **Source:** CHIEF COMPLAINT:, Left knee pain.,SUBJECTIVE: , This is a 36-year-old white female who presents to the office today with a complaint of left knee pain. She is approximately five days after a third Synvisc injection. She …
>
> **Output:** Hello there! I'm here to help you understand what's happening with your knee. You've been having pain in your left knee for about five days. It's a bit better, but you still feel a pinching pain when you put weight on it…

## unsupported_content (208)

_Number or medication not supported by the source note (possible hallucination)._

**mtsamples_2-D_Echocardiogram_-_1 · caregiver_checklist**: number '6 month' is not in the source note

> **Source:** 2-D M-MODE: , ,1. Left atrial enlargement with left atrial diameter of 4.7 cm.,2. Normal size right and left ventricle.,3. Normal LV systolic function with left ventricular ejection fraction of 51%.,4. Normal LV diastoli…
>
> **Output:** …h as shortness of breath, swelling. Schedule follow-up echocardiogram in 6 months. Call if symptoms of heart failure worsen. Check blood pressure and monitor for any changes. Watch for signs of valve regurgitation. Call …

**mtsamples_AV_Fistula_-_1 · caregiver_checklist**: number '6 hour' is not in the source note

> **Source:** PREOPERATIVE DIAGNOSIS,End-stage renal disease.,POSTOPERATIVE DIAGNOSIS,End-stage renal disease.,PROCEDURE,Venogram of the left arm and creation of left brachiocephalic arteriovenous fistula.,ANESTHESIA,General.,DESCRIPT…
>
> **Output:** …of antibiotics. Check the patient’s vital signs every hour for the first 6 hours. Watch for signs of infection such as fever, redness, or swelling. Call the healthcare provider if the patient develops signs of infection.…

**mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit · caregiver_checklist**: number '20 mg' is not in the source note

> **Source:** HISTORY OF PRESENT ILLNESS:, Patient is a three years old male who about 45 minutes prior admission to the emergency room ingested about two to three tablets of Celesta 40 mg per tablets. Mom called to the poison control…
>
> **Output:** Give the patient 20 mg of Celesta in the morning, as prescribed by the doctor. Check the patient's vital signs every hour for the next 12 hours. Watch for signs of nausea, vomiting, or diarrhea. Call the doctor if the pa…

## child_reading_level (37)

_Child explanation above the maximum reading grade._

**mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit · child_explanation**: Flesch-Kincaid grade 3.2 > 3

> **Source:** HISTORY OF PRESENT ILLNESS:, Patient is a three years old male who about 45 minutes prior admission to the emergency room ingested about two to three tablets of Celesta 40 mg per tablets. Mom called to the poison control…
>
> **Output:** You swallowed some pills by accident. Your mom and doctors are taking good care of you. The pills didn't taste good, so you only took a few. The grown-ups are keeping an eye on you and making sure you're okay. You're fee…

**mtsamples_Aortobifemoral_Bypass_-_1 · child_explanation**: Flesch-Kincaid grade 3.1 > 3

> **Source:** PREOPERATIVE DIAGNOSIS,1. Aortoiliac occlusive disease bilaterally.,2. Dementia.,POSTOPERATIVE DIAGNOSIS,1. Aortoiliac occlusive disease bilaterally.,2. Dementia.,OPERATION: , Aortobifemoral bypass surgery utilizing a bi…
>
> **Output:** You had a big operation today, you know. The doctors and grown-ups are taking care of you. They fixed some problems in your body. You got a special new tube to help your blood flow better. The doctors used tiny helpers t…

**mtsamples_Blepharoplasty_-_Direct_Brow_Repair · child_explanation**: Flesch-Kincaid grade 3.3 > 3

> **Source:** PREOPERATIVE DX:, Dermatochalasis, mechanical ptosis, brow ptosis.,POSTOPERATIVE DX:, Same,PROCEDURE:,: Upper lid blepharoplasty and direct brow lift,ANESTHESIA:, Local with sedation,INDICATIONS FOR SURGERY: , In the pre…
>
> **Output:** You had a little surgery today, sweetie. The doctors and grown-ups are taking care of you. They fixed your eyelids and eyebrows to help you see better. Tiny helpers went to work inside your eyes to make things better. Yo…

## truncated (5)

_Generation stopped at max_new_tokens, so the text is cut off._

**mtsamples_Infantile_Spasms · patient_summary**: hit max_new_tokens (512); raise personas.patient_summary.max_new_tokens

> **Source:** CHIEF COMPLAINT:, Arm and leg jerking.,HISTORY OF PRESENT ILLNESS: ,The patient is a 10-day-old Caucasian female here for approximately 1 minute bilateral arm and leg jerks, which started at day of life 1 and have occurr…
>
> **Output:** …have any of these symptoms: - Fever - Congestion - Vomiting - Diarrhea - Rashes - Cough - Runny nose - Any other new symptoms You should tell your mommy or the doctors right away. They will check you and decide what to

**mtsamples_Multiple_Medical_Problems · patient_summary**: hit max_new_tokens (512); raise personas.patient_summary.max_new_tokens

> **Source:** SUBJECTIVE:, The patient was seen today by me at Nursing Home for her multiple medical problems. The nurses report that she has been confused at times, having incontinent stool in the sink one time but generally she does…
>
> **Output:** …6, which you take every day. You have vitamin B6, which you take every day. You have vitamin B6, which you take every day. You have vitamin B6, which you take every day. You have vitamin B6, which you take every day. You

**mtsamples_Multiple_Medical_Problems_-_Discharge_Summary · patient_summary**: hit max_new_tokens (512); raise personas.patient_summary.max_new_tokens

> **Source:** ADMISSION DIAGNOSES:,1. Seizure.,2. Hypoglycemia.,3. Anemia.,4. Hypotension.,5. Dyspnea.,6. Edema.,DISCHARGE DIAGNOSES:,1. Colon cancer, status post right hemicolectomy.,2. Anemia.,3. Hospital-acquired pneumonia.,4. Hype…
>
> **Output:** …be site. - You have a problem with your heart that causes you to have seizures. You're taking Lamictal. Your doctor will help you increase the dose to 200 mg twice a day, but you'll need to talk to them about this first.

## repetition (25)

_A bullet (caregiver) or sentence (other personas) duplicates or nearly duplicates an earlier one._

**mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit · caregiver_checklist**: 1 repeated bullet(s); e.g. bullet 9 repeats bullet 5 (overlap 1.00)

> **Source:** HISTORY OF PRESENT ILLNESS:, Patient is a three years old male who about 45 minutes prior admission to the emergency room ingested about two to three tablets of Celesta 40 mg per tablets. Mom called to the poison control…
>
> **Output:** “Schedule a follow-up appointment with the primary care physician in the morning.” … later: “Schedule a follow-up appointment with the primary care physician in the morning.”

**mtsamples_Attempted_Suicide_-_Consult · caregiver_checklist**: 1 repeated bullet(s); e.g. bullet 10 repeats bullet 8 (overlap 1.00)

> **Source:** IDENTIFYING DATA: , The patient is a 21-year-old Caucasian male, who attempted suicide by trying to jump from a moving car, which was being driven by his mother. Additionally, he totaled his own car earlier in the day, b…
>
> **Output:** “Call the patient's girlfriend to inform her of the discharge and follow-up plan.” … later: “Call the patient's girlfriend to inform her of the discharge and follow-up plan.”

**mtsamples_Bunionectomy_Osteotomy · caregiver_checklist**: 1 repeated bullet(s); e.g. bullet 10 repeats bullet 7 (overlap 1.00)

> **Source:** PREOPERATIVE DIAGNOSES:,1. Hallux valgus, right foot.,2. Hallux interphalangeus, right foot.,POSTOPERATIVE DIAGNOSES:,1. Hallux valgus, right foot.,2. Hallux interphalangeus, right foot.,PROCEDURES PERFORMED:,1. Bunionec…
>
> **Output:** “Call if the patient experiences any signs of nerve damage, such as numbness or tingling.” … later: “Call if the patient experiences any signs of nerve damage, such as numbness or tingling.”

## empty_or_short (0)

_Empty or very short output._

No failures.
