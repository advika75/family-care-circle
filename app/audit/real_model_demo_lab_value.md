# Real-model run on the local demo app

Synthetic note: `/private/tmp/claude-501/-Users-advikamishra-Projects-family-care-circle/951d6a64-58d8-45ab-85fc-bad7436a5a5e/scratchpad/synthetic_t2dm_lab_note.txt` (672 characters), title "Primary care visit (synthetic, lab value 164 mg/dL)". Real model: Qwen2.5-3B-Instruct Q4_K_M (llama_cpp). **Wait time: 85 s** (includes loading the model in a fresh worker process).

Synthetic data only. Prototype. Not for real patient data.

## The note (input)

```
PRIMARY CARE VISIT (SYNTHETIC)
Patient: 34 y/o female with type 2 diabetes mellitus, diagnosed 2 years ago.
Subjective: Feels well. Occasional missed evening doses. No hypoglycemia. No chest pain.
Objective: Fasting glucose 164 mg/dL. HbA1c 7.9%. BP 118/74. Weight 78 kg.
Assessment: Type 2 diabetes mellitus, above target.
Plan:
- Continue metformin 1000 mg twice daily with meals.
- Start sitagliptin 100 mg once daily in the morning.
- Check fasting blood glucose each morning and record it.
- Diabetes education class next month. Repeat HbA1c in 3 months.
- Call the clinic if glucose is below 70 mg/dL with symptoms or if she is vomiting and cannot keep fluids down.
```

## Patient summary

We could not create a summary. Please ask your care team to go over your visit notes with you.

## Caregiver checklist

1. Give metformin 1000 mg twice daily with meals.
2. Start sitagliptin 100 mg once daily in the morning.
3. Check fasting blood glucose each morning.
4. Record the results of each morning's blood glucose test.
5. Watch for symptoms of hypoglycemia such as shakiness, sweating, or confusion.
6. Call the clinic if glucose is below 70 mg/dL with symptoms or if she is vomiting and cannot keep fluids down.
7. Schedule a diabetes education class next month.
8. Schedule a repeat HbA1c test in 3 months.
9. Watch for warning signs of diabetes complications such as unexplained weight loss or frequent infections.
10. Follow up with the healthcare provider if symptoms persist or worsen.
11. Monitor for fasting blood glucose levels, aiming for a target of 164 mg/dL.

## Child explanation (as shown to the child)

A grown-up will help explain what the doctor said.

Withheld by the safety gate: **True**

## Review flags (creator/caregiver view)

```json
{
  "retries": {
    "patient_summary": 2,
    "caregiver_checklist": 1,
    "child_explanation": 0
  },
  "fallback_used": {
    "patient_summary": true,
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
    "caregiver_checklist": 1,
    "child_explanation": 0
  },
  "appended_by_fallback": {
    "patient_summary": [],
    "caregiver_checklist": [],
    "child_explanation": []
  },
  "retention": {
    "patient_summary": {
      "overall": 0.0,
      "n_required": 9
    },
    "caregiver_checklist": {
      "overall": 1.0,
      "n_required": 9
    }
  },
  "unsupported": {
    "patient_summary": {
      "medications": [],
      "numbers": []
    },
    "caregiver_checklist": {
      "medications": [],
      "numbers": []
    }
  },
  "validation_errors": [],
  "child_gate": {
    "fired": true,
    "reasons": [
      "medication_name",
      "too_long"
    ]
  },
  "model_id": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
  "model_hash": "sha256:626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d",
  "pipeline_created_at": "2026-10-25T09:47:22+00:00"
}
```

## What each role received

| role | HTTP | fields |
|---|---|---|
| creator | 200 | available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at |
| caregiver | 200 | available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at |
| patient | 200 | available, disclaimer, generation, output_id, patient_summary, updated_at |
| child | 200 | available, child_explanation, disclaimer, generation, output_id, updated_at |
