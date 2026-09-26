# Evaluation summary

Samples: 12 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 5.221 | 0.546 |
| caregiver_checklist_fkgl | 6.775 | 1.230 |
| child_explanation_fkgl | 4.407 | 0.789 |
| patient_summary_fkgl_delta | -2.831 | 0.939 |
| caregiver_checklist_fkgl_delta | -1.277 | 1.383 |
| child_explanation_fkgl_delta | -3.645 | 1.018 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 80.114 | 3.007 |
| caregiver_checklist_fre | 65.739 | 6.127 |
| child_explanation_fre | 85.157 | 4.335 |
| patient_summary_rouge1 | 0.277 | 0.035 |
| caregiver_checklist_rouge1 | 0.451 | 0.071 |
| child_explanation_rouge1 | 0.215 | 0.045 |
| patient_summary_rougeL | 0.209 | 0.025 |
| caregiver_checklist_rougeL | 0.309 | 0.061 |
| child_explanation_rougeL | 0.147 | 0.041 |
| patient_summary_retention_first | 0.810 | 0.133 |
| caregiver_checklist_retention_first | 0.854 | 0.139 |
| patient_summary_retention_model | 0.963 | 0.045 |
| caregiver_checklist_retention_model | 1.000 | 0.000 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.083 | 0.276 |
| caregiver_checklist_unsupported_numbers | 0.167 | 0.373 |
| child_explanation_unsupported_numbers | 0.083 | 0.276 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.000 | 0.000 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.417 | 0.493 |
| caregiver_checklist_fallback | 0.000 | 0.000 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.000 | 0.000 |
| caregiver_checklist_repetition | 0.167 | 0.373 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.892 | 0.105 |
| child_explanation_med_names | 1.917 | 1.320 |
| child_explanation_numbers | 2.417 | 1.891 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 2.167 | 1.213 |
| fallbacks | 0.417 | 0.493 |
| latency_total_sec | 74.746 | 20.545 |

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
