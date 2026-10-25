# Real-model run on the local demo app

Synthetic note: `data/raw/note_02.txt` (742 characters), title "Primary care follow-up (synthetic type 2 diabetes)". Real model: Qwen2.5-3B-Instruct Q4_K_M (llama_cpp). **Wait time: 52 s** (includes loading the model in a fresh worker process).

Synthetic data only. Prototype. Not for real patient data.

## The note (input)

```
PRIMARY CARE FOLLOW-UP (SYNTHETIC)
Patient: 58 y/o female with type 2 diabetes mellitus and hyperlipidemia.
Subjective: Reports fatigue, increased thirst and frequent urination over the past month. Diet adherence inconsistent.
Objective: HbA1c 8.9% (prior 7.6%). BP 128/80. BMI 33.
Assessment: Type 2 diabetes mellitus, suboptimally controlled. Hyperlipidemia.
Plan:
- Increase metformin from 500 mg BID to 1000 mg BID with meals.
- Start empagliflozin 10 mg once daily in the morning.
- Continue atorvastatin 20 mg nightly.
- Check fasting blood glucose daily for 2 weeks and bring log to next visit.
- Referral to diabetes education. Repeat HbA1c in 3 months.
Counseled on hydration and signs of genital yeast infection with empagliflozin.
```

## Patient summary

Hello there! I'm here to help you understand what's going on with your health. You have type 2 diabetes and high cholesterol. Over the past month, you've been feeling tired, thirsty, and urinating more often. Your doctor wants to help you feel better.

Here are the changes to your medicines:

1. Metformin: You'll be taking this medicine more often now. You'll take 500 mg twice a day (BID) with your meals. Starting next week, you'll take 1000 mg twice a day (BID) with your meals. This will help your body use sugar better.

2. Empagliflozin: This is a new medicine that helps your body get rid of extra sugar in your urine. You'll take 10 mg once a day in the morning. Your doctor wants you to check your blood sugar levels every day for the next two weeks. Write down your results and bring them to your next visit.

3. Atorvastatin: You've been taking this medicine to help with your cholesterol. You'll continue taking 20 mg at bedtime.

Your doctor also wants you to drink more water and be careful for any signs of a yeast infection. If you have any of these symptoms, you should call your doctor right away.

Remember, it's important to keep track of your blood sugar levels and come back for a check-up in three months. Your doctor will check your blood sugar again then to see if everything is working well.

You're doing a great job taking care of yourself. If you have any questions or concerns, don't hesitate to ask your doctor or nurse. They're here to help!

## Caregiver checklist

1. Give metformin 500 mg BID with meals for 2 weeks.
2. Give metformin 1000 mg BID with meals for 2 weeks.
3. Check fasting blood glucose daily for 2 weeks.
4. Schedule a log of blood glucose readings to bring to next visit.
5. Start empagliflozin 10 mg once daily in the morning for 2 weeks.
6. Continue atorvastatin 20 mg nightly for 2 weeks.
7. Watch for signs of genital yeast infection with empagliflozin.
8. Call if blood glucose readings are consistently above 180 mg/dL or below 70 mg/dL.
9. Call if symptoms of fatigue, increased thirst, or frequent urination persist or worsen.
10. Schedule a follow-up appointment in 3 months for HbA1c test.
11. Referral to diabetes education for support in managing diabetes.

## Child explanation (as shown to the child)

You have a bit of trouble with your body lately. You feel tired and need to drink more water. Your feet and hands are getting bigger because of the sugar in your body. The doctors are helping you by giving you more medicine. They also want you to drink more water and watch for a special kind of yeast. You're doing well, and the doctors are taking good care of you.

Withheld by the safety gate: **False**

## Review flags (creator/caregiver view)

```json
{
  "retries": {
    "patient_summary": 0,
    "caregiver_checklist": 0,
    "child_explanation": 0
  },
  "fallback_used": {
    "patient_summary": false,
    "caregiver_checklist": false,
    "child_explanation": false
  },
  "truncated": {
    "patient_summary": false,
    "caregiver_checklist": false,
    "child_explanation": false
  },
  "redacted_dosages": {
    "patient_summary": [],
    "caregiver_checklist": [],
    "child_explanation": []
  },
  "missing_first_attempt_count": {
    "patient_summary": 0,
    "caregiver_checklist": 0,
    "child_explanation": 0
  },
  "appended_by_fallback": {
    "patient_summary": [],
    "caregiver_checklist": [],
    "child_explanation": []
  },
  "retention": {
    "patient_summary": {
      "overall": 1.0,
      "n_required": 13
    },
    "caregiver_checklist": {
      "overall": 1.0,
      "n_required": 13
    }
  },
  "unsupported": {
    "patient_summary": {
      "medications": [],
      "numbers": []
    },
    "caregiver_checklist": {
      "medications": [],
      "numbers": [
        "180 mg",
        "70 mg"
      ]
    }
  },
  "validation_errors": [],
  "child_gate": {
    "fired": false,
    "reasons": []
  },
  "model_id": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
  "model_hash": "sha256:626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d",
  "pipeline_created_at": "2026-10-25T09:45:27+00:00"
}
```

## What each role received

| role | HTTP | fields |
|---|---|---|
| creator | 200 | available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at |
| caregiver | 200 | available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at |
| patient | 200 | available, disclaimer, generation, output_id, patient_summary, updated_at |
| child | 200 | available, child_explanation, disclaimer, generation, output_id, updated_at |
