# Error analysis

Outputs: `data/outputs_baseline_seed0` · 12 notes · backend: llama_cpp (12)  
Settings: child max grade 3, minimum 20 words per output.

| Category | Failures | Notes affected | Meaning |
|---|---|---|---|
| missing_entity | 0 | 0 / 12 | Required entity missing from the final output |
| fallback_used | 5 | 5 / 12 | Model omitted required facts; the fallback had to append them |
| format_or_retries | 9 | 7 / 12 | Invalid JSON/format, or all retries used up |
| unsupported_content | 3 | 3 / 12 | Number or medication not supported by the source note (possible hallucination) |
| child_reading_level | 5 | 5 / 12 | Child explanation above the maximum reading grade |
| truncated | 0 | 0 / 12 | Generation stopped at max_new_tokens, so the text is cut off |
| repetition | 2 | 2 / 12 | A bullet (caregiver) or sentence (other personas) duplicates or nearly duplicates an earlier one |
| empty_or_short | 0 | 0 / 12 | Empty or very short output |

Failures are counted per (note, persona), and per item for unsupported content.

## missing_entity (0)

_Required entity missing from the final output._

No failures.

## fallback_used (5)

_Model omitted required facts; the fallback had to append them._

**note_01 · patient_summary**: after 2 retries the model still omitted 200 mg; the fallback appended them

> **Source:** 2. Ibuprofen 200 mg PO q6h PRN fever or pain.
>
> **Output:** …ts or the doctor. You're doing great, and you'll be feeling better soon! Important details from your care team's note: 200 mg (dosage).

**note_04 · patient_summary**: after 2 retries the model still omitted as needed; the fallback appended them

> **Source:** - Albuterol HFA 90 mcg, 2 puffs every 4 hours as needed for wheezing or cough.
>
> **Output:** … worried, talk to your parents or the doctors. They're here to help you. Important details from your care team's note: as needed (frequency).

**note_08 · patient_summary**: after 2 retries the model still omitted 50 mg; the fallback appended them

> **Source:** 2. Start metoprolol succinate 50 mg PO once daily for rate control.
>
> **Output:** …ways talk to your healthcare team. They're here to help you feel better. Important details from your care team's note: 50 mg (dosage).

## format_or_retries (9)

_Invalid JSON/format, or all retries used up._

**note_01 · patient_summary**: used all 2 retries (fallback used)

> **Source:** PEDIATRIC URGENT CARE NOTE (SYNTHETIC) Patient: 7 y/o male. Chief complaint: sore throat x 2 days. HPI: Mother reports fever to 101.8 F, sore throat, difficulty swallowing and headache since Monday. No cough. Decreased a…
>
> **Output:** Hello there! I'm here to help you with your health problems. You have a sore throat, fever, trouble swallowing, and a headache. Your mother told me that you've been feeling these symptoms for two days now. The doctor che…

**note_04 · patient_summary**: used all 2 retries (fallback used)

> **Source:** PEDIATRIC EMERGENCY DEPARTMENT DISCHARGE (SYNTHETIC) Patient: 9 y/o female with mild persistent asthma. HPI: 2 days of cough, wheezing and chest tightness after a viral URI. Shortness of breath with activity. ED course: …
>
> **Output:** Hello there! I'm here to help you understand what's going on and what you need to do next. You had a cough, wheezing, and chest tightness for two days after having a viral infection in your nose and throat. Your breathin…

**note_05 · patient_summary**: used all 2 retries (succeeded on the last attempt)

> **Source:** POST-OPERATIVE DISCHARGE INSTRUCTIONS (SYNTHETIC) Patient: 34 y/o female, POD 1 s/p laparoscopic appendectomy for acute appendicitis. Hospital course: Uncomplicated. Tolerating diet, ambulating, pain controlled. Discharg…
>
> **Output:** Hello there! I'm here to help you understand what's happening after your surgery. You had an operation to remove your appendix, and everything went well. You're doing great and can eat and move around now. Here are the i…

## unsupported_content (3)

_Number or medication not supported by the source note (possible hallucination)._

**note_03 · caregiver_checklist**: number '140/90' is not in the source note

> **Source:** INTERNAL MEDICINE CLINIC NOTE (SYNTHETIC) Patient: 64 y/o male, hypertension, here for BP recheck. Subjective: Occasional morning headaches and mild dizziness when standing quickly. No chest pain. Objective: BP 154/96 (r…
>
> **Output:** …ness, chest pain. Call if blood pressure readings are consistently above 140/90. Call if dizziness or fainting occurs. Call if new symptoms develop. Schedule follow-up in 2 weeks for BMP.

**note_10 · patient_summary**: number '1 day' is not in the source note

> **Source:** NEUROLOGY CLINIC NOTE (SYNTHETIC) Patient: 31 y/o female with migraine without aura. Subjective: 6-8 migraine days per month with throbbing headache, nausea and light sensitivity. Assessment: Episodic migraine, increasin…
>
> **Output:** …ans you can take it whenever you need it, but you can only take it up to 10 days in a month. This medicine will help make your headache feel better. We also want you to keep a diary of when you have headaches. This will …

**note_12 · caregiver_checklist**: number '4 hour' is not in the source note

> **Source:** FAMILY MEDICINE NOTE (SYNTHETIC) Patient: 52 y/o female. HPI: 3 days of redness, warmth and swelling on the left lower leg after a garden scratch. Mild pain. No fever. Exam: 8 x 6 cm area of erythema, border marked with …
>
> **Output:** Give Cephalexin 500 mg PO four times a day for 7 days. Give Ibuprofen 400 mg PO every 8 hours as needed for pain, taking with food. Check the redness area every 4 hours for any spread beyond the pen line. Watch for fever…

## child_reading_level (5)

_Child explanation above the maximum reading grade._

**note_01 · child_explanation**: Flesch-Kincaid grade 4.2 > 3

> **Source:** PEDIATRIC URGENT CARE NOTE (SYNTHETIC) Patient: 7 y/o male. Chief complaint: sore throat x 2 days. HPI: Mother reports fever to 101.8 F, sore throat, difficulty swallowing and headache since Monday. No cough. Decreased a…
>
> **Output:** You have a sore throat and a fever. You're also having trouble swallowing and feeling a bit achy. The doctors found some tiny white stuff on your tonsils. They tested you and found you have strep throat. You need to take…

**note_02 · child_explanation**: Flesch-Kincaid grade 3.6 > 3

> **Source:** PRIMARY CARE FOLLOW-UP (SYNTHETIC) Patient: 58 y/o female with type 2 diabetes mellitus and hyperlipidemia. Subjective: Reports fatigue, increased thirst and frequent urination over the past month. Diet adherence inconsi…
>
> **Output:** You've been feeling tired, thirsty, and peeing more often. You're getting more help now. Your doctors are making sure you're taking better care of your body. You'll take more of a medicine called metformin. You'll also s…

**note_04 · child_explanation**: Flesch-Kincaid grade 3.5 > 3

> **Source:** PEDIATRIC EMERGENCY DEPARTMENT DISCHARGE (SYNTHETIC) Patient: 9 y/o female with mild persistent asthma. HPI: 2 days of cough, wheezing and chest tightness after a viral URI. Shortness of breath with activity. ED course: …
>
> **Output:** You had a cough, wheezing, and chest tightness. You also had shortness of breath, especially when you ran around. The doctors gave you medicine to help your breathing. They also gave you a little helper called prednisolo…

## truncated (0)

_Generation stopped at max_new_tokens, so the text is cut off._

No failures.

## repetition (2)

_A bullet (caregiver) or sentence (other personas) duplicates or nearly duplicates an earlier one._

**note_05 · caregiver_checklist**: 1 repeated bullet(s); e.g. bullet 10 repeats bullet 5 (overlap 0.93)

> **Source:** POST-OPERATIVE DISCHARGE INSTRUCTIONS (SYNTHETIC) Patient: 34 y/o female, POD 1 s/p laparoscopic appendectomy for acute appendicitis. Hospital course: Uncomplicated. Tolerating diet, ambulating, pain controlled. Discharg…
>
> **Output:** “Watch for nausea and take Ondansetron 4 mg every 8 hours as needed.” … later: “Watch for signs of nausea and take Ondansetron 4 mg every 8 hours as needed.”

**note_09 · caregiver_checklist**: 10 repeated bullet(s); e.g. bullet 12 repeats bullet 7 (overlap 1.00)

> **Source:** BEHAVIORAL HEALTH FOLLOW-UP (SYNTHETIC) Patient: 39 y/o male. Subjective: Low mood, poor sleep, and loss of interest for 2 months. Episodes of anxiety at work. Denies suicidal ideation. Assessment: Major depressive disor…
>
> **Output:** “Call if sleep problems persist or get worse.” … later: “Call if sleep problems persist or get worse.”

## empty_or_short (0)

_Empty or very short output._

No failures.

