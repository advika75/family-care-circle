# Evaluation summary

Samples: 12 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 5.519 | 1.030 |
| caregiver_checklist_fkgl | 6.284 | 1.020 |
| child_explanation_fkgl | 3.373 | 1.127 |
| patient_summary_fkgl_delta | -2.533 | 1.219 |
| caregiver_checklist_fkgl_delta | -1.768 | 1.010 |
| child_explanation_fkgl_delta | -4.679 | 1.430 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 78.281 | 4.878 |
| caregiver_checklist_fre | 67.661 | 6.792 |
| child_explanation_fre | 87.542 | 5.711 |
| patient_summary_rouge1 | 0.293 | 0.052 |
| caregiver_checklist_rouge1 | 0.486 | 0.075 |
| child_explanation_rouge1 | 0.185 | 0.033 |
| patient_summary_rougeL | 0.211 | 0.042 |
| caregiver_checklist_rougeL | 0.322 | 0.075 |
| child_explanation_rougeL | 0.127 | 0.028 |
| patient_summary_retention_first | 0.848 | 0.140 |
| caregiver_checklist_retention_first | 0.878 | 0.178 |
| patient_summary_retention_model | 0.982 | 0.045 |
| caregiver_checklist_retention_model | 1.000 | 0.000 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.167 | 0.553 |
| caregiver_checklist_unsupported_numbers | 0.167 | 0.373 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.000 | 0.000 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.167 | 0.373 |
| caregiver_checklist_fallback | 0.000 | 0.000 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.083 | 0.276 |
| caregiver_checklist_repetition | 0.083 | 0.276 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.701 | 0.217 |
| child_explanation_med_names | 0.667 | 1.179 |
| child_explanation_numbers | 0.417 | 0.640 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 1.583 | 0.862 |
| fallbacks | 0.167 | 0.373 |
| latency_total_sec | 85.146 | 26.413 |

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
