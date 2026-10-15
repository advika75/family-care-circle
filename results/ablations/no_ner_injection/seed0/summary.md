# Evaluation summary

Samples: 12 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 8.052 | 1.192 |
| patient_summary_fkgl | 5.489 | 0.844 |
| caregiver_checklist_fkgl | 6.679 | 0.906 |
| child_explanation_fkgl | 3.283 | 0.948 |
| patient_summary_fkgl_delta | -2.563 | 1.129 |
| caregiver_checklist_fkgl_delta | -1.373 | 1.120 |
| child_explanation_fkgl_delta | -4.769 | 1.427 |
| source_fre | 54.023 | 9.385 |
| patient_summary_fre | 78.617 | 4.663 |
| caregiver_checklist_fre | 64.755 | 4.691 |
| child_explanation_fre | 89.137 | 5.753 |
| patient_summary_rouge1 | 0.276 | 0.045 |
| caregiver_checklist_rouge1 | 0.474 | 0.069 |
| child_explanation_rouge1 | 0.173 | 0.065 |
| patient_summary_rougeL | 0.193 | 0.033 |
| caregiver_checklist_rougeL | 0.262 | 0.071 |
| child_explanation_rougeL | 0.117 | 0.035 |
| patient_summary_retention_first | 0.672 | 0.117 |
| caregiver_checklist_retention_first | 0.555 | 0.134 |
| patient_summary_retention_model | 0.909 | 0.125 |
| caregiver_checklist_retention_model | 0.923 | 0.115 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.333 | 0.624 |
| caregiver_checklist_unsupported_numbers | 0.250 | 0.595 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.083 | 0.276 |
| caregiver_checklist_truncation_rate | 0.000 | 0.000 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.417 | 0.493 |
| caregiver_checklist_fallback | 0.333 | 0.471 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.083 | 0.276 |
| caregiver_checklist_repetition | 0.000 | 0.000 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.857 | 0.166 |
| child_explanation_med_names | 0.250 | 0.595 |
| child_explanation_numbers | 0.333 | 0.471 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 3.417 | 0.759 |
| fallbacks | 0.750 | 0.722 |
| latency_total_sec | 73.566 | 15.784 |

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
