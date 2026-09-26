# Evaluation summary

Samples: 12 | backend(s): mock

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 4.959 | 0.799 |
| caregiver_checklist_fkgl | 3.821 | 1.113 |
| child_explanation_fkgl | 2.646 | 0.000 |
| patient_summary_fkgl_delta | -3.092 | 1.012 |
| caregiver_checklist_fkgl_delta | -4.231 | 1.281 |
| child_explanation_fkgl_delta | -5.406 | 1.192 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 78.535 | 4.991 |
| caregiver_checklist_fre | 83.836 | 7.169 |
| child_explanation_fre | 89.155 | 0.000 |
| patient_summary_rouge1 | 0.284 | 0.041 |
| caregiver_checklist_rouge1 | 0.329 | 0.039 |
| child_explanation_rouge1 | 0.070 | 0.025 |
| patient_summary_rougeL | 0.224 | 0.041 |
| caregiver_checklist_rougeL | 0.213 | 0.047 |
| child_explanation_rougeL | 0.044 | 0.011 |
| patient_summary_retention_first | 1.000 | 0.000 |
| caregiver_checklist_retention_first | 1.000 | 0.000 |
| patient_summary_retention_model | 1.000 | 0.000 |
| caregiver_checklist_retention_model | 1.000 | 0.000 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.000 | 0.000 |
| caregiver_checklist_unsupported_numbers | 0.000 | 0.000 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.000 | 0.000 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.000 | 0.000 |
| caregiver_checklist_fallback | 0.000 | 0.000 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.000 | 0.000 |
| caregiver_checklist_repetition | 0.000 | 0.000 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.444 | 0.000 |
| child_explanation_med_names | 0.000 | 0.000 |
| child_explanation_numbers | 0.000 | 0.000 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 0.000 | 0.000 |
| fallbacks | 0.000 | 0.000 |
| latency_total_sec | 0.002 | 0.001 |

## NER vs gold (6 docs)

| label | precision_exact | precision_relaxed | recall_exact | recall_relaxed | f1_exact | f1_relaxed |
|---|---|---|---|---|---|---|
| CONDITION | 0.765 | 0.941 | 0.812 | 1.000 | 0.788 | 0.970 |
| DOSAGE | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| DURATION | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| FREQUENCY | 0.966 | 0.966 | 1.000 | 1.000 | 0.982 | 0.982 |
| MEDICATION | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MICRO | 0.959 | 0.979 | 0.959 | 0.979 | 0.959 | 0.979 |
| SYMPTOM | 0.978 | 0.978 | 0.938 | 0.938 | 0.957 | 0.957 |
