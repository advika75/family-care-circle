# Evaluation summary

Samples: 12 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 5.423 | 0.695 |
| caregiver_checklist_fkgl | 6.494 | 1.138 |
| child_explanation_fkgl | 2.742 | 0.696 |
| patient_summary_fkgl_delta | -2.629 | 1.310 |
| caregiver_checklist_fkgl_delta | -1.557 | 1.273 |
| child_explanation_fkgl_delta | -5.309 | 1.321 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 79.563 | 3.932 |
| caregiver_checklist_fre | 65.953 | 6.369 |
| child_explanation_fre | 90.972 | 3.269 |
| patient_summary_rouge1 | 0.282 | 0.043 |
| caregiver_checklist_rouge1 | 0.499 | 0.098 |
| child_explanation_rouge1 | 0.146 | 0.065 |
| patient_summary_rougeL | 0.197 | 0.036 |
| caregiver_checklist_rougeL | 0.318 | 0.094 |
| child_explanation_rougeL | 0.097 | 0.047 |
| patient_summary_retention_first | 0.724 | 0.149 |
| caregiver_checklist_retention_first | 0.562 | 0.163 |
| patient_summary_retention_model | 0.865 | 0.166 |
| caregiver_checklist_retention_model | 0.928 | 0.136 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.417 | 0.640 |
| caregiver_checklist_unsupported_numbers | 0.333 | 0.471 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.083 | 0.276 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.000 | 0.000 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.667 | 0.471 |
| caregiver_checklist_fallback | 0.417 | 0.493 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.000 | 0.000 |
| caregiver_checklist_repetition | 0.167 | 0.373 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.676 | 0.282 |
| child_explanation_med_names | 0.500 | 0.764 |
| child_explanation_numbers | 0.250 | 0.433 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 3.333 | 0.850 |
| fallbacks | 1.083 | 0.862 |
| latency_total_sec | 70.631 | 17.009 |

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
