# Evaluation summary

Samples: 12 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 5.490 | 0.885 |
| caregiver_checklist_fkgl | 7.011 | 1.109 |
| child_explanation_fkgl | 3.148 | 1.011 |
| patient_summary_fkgl_delta | -2.562 | 1.203 |
| caregiver_checklist_fkgl_delta | -1.041 | 0.729 |
| child_explanation_fkgl_delta | -4.904 | 1.144 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 79.489 | 4.882 |
| caregiver_checklist_fre | 64.148 | 7.049 |
| child_explanation_fre | 88.748 | 6.162 |
| patient_summary_rouge1 | 0.282 | 0.042 |
| caregiver_checklist_rouge1 | 0.479 | 0.067 |
| child_explanation_rouge1 | 0.160 | 0.060 |
| patient_summary_rougeL | 0.212 | 0.046 |
| caregiver_checklist_rougeL | 0.281 | 0.086 |
| child_explanation_rougeL | 0.115 | 0.039 |
| patient_summary_retention_first | 0.681 | 0.116 |
| caregiver_checklist_retention_first | 0.560 | 0.083 |
| patient_summary_retention_model | 0.876 | 0.143 |
| caregiver_checklist_retention_model | 0.878 | 0.163 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.083 | 0.276 |
| caregiver_checklist_unsupported_numbers | 0.333 | 0.624 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.000 | 0.000 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.500 | 0.500 |
| caregiver_checklist_fallback | 0.417 | 0.493 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.000 | 0.000 |
| caregiver_checklist_repetition | 0.083 | 0.276 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.741 | 0.215 |
| child_explanation_med_names | 0.417 | 0.862 |
| child_explanation_numbers | 0.333 | 0.471 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 3.500 | 0.500 |
| fallbacks | 0.917 | 0.640 |
| latency_total_sec | 84.884 | 13.913 |

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
