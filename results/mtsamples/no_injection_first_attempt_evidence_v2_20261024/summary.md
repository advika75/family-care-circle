# Evaluation summary

Samples: 100 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 9.821 | 1.959 |
| patient_summary_fkgl | 5.313 | 1.135 |
| caregiver_checklist_fkgl | 7.526 | 2.105 |
| child_explanation_fkgl | 2.875 | 1.097 |
| patient_summary_fkgl_delta | -4.508 | 2.063 |
| caregiver_checklist_fkgl_delta | -2.294 | 2.716 |
| child_explanation_fkgl_delta | -6.946 | 2.370 |
| source_fre | 46.146 | 12.767 |
| patient_summary_fre | 80.494 | 6.178 |
| caregiver_checklist_fre | 60.924 | 9.496 |
| child_explanation_fre | 91.331 | 5.352 |
| patient_summary_rouge1 | 0.261 | 0.092 |
| caregiver_checklist_rouge1 | 0.203 | 0.081 |
| child_explanation_rouge1 | 0.097 | 0.041 |
| patient_summary_rougeL | 0.146 | 0.071 |
| caregiver_checklist_rougeL | 0.113 | 0.046 |
| child_explanation_rougeL | 0.066 | 0.026 |
| patient_summary_retention_first | 0.435 | 0.393 |
| caregiver_checklist_retention_first | 0.247 | 0.354 |
| patient_summary_retention_model | 0.930 | 0.197 |
| caregiver_checklist_retention_model | 0.909 | 0.240 |
| patient_summary_retention | 0.984 | 0.126 |
| caregiver_checklist_retention | 0.968 | 0.177 |
| patient_summary_retention_first_evidence_available | 1.000 | 0.000 |
| caregiver_checklist_retention_first_evidence_available | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.270 | 0.598 |
| caregiver_checklist_unsupported_numbers | 1.570 | 1.387 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.060 | 0.237 |
| caregiver_checklist_truncation_rate | 0.030 | 0.171 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.110 | 0.313 |
| caregiver_checklist_fallback | 0.140 | 0.347 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_retries | 0.670 | 0.749 |
| caregiver_checklist_retries | 0.840 | 0.784 |
| child_explanation_retries | 0.000 | 0.000 |
| patient_summary_latency_sec | 39.562 | 25.611 |
| caregiver_checklist_latency_sec | 26.034 | 15.294 |
| child_explanation_latency_sec | 10.353 | 4.045 |
| patient_summary_repetition | 0.120 | 0.325 |
| caregiver_checklist_repetition | 0.220 | 0.414 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.734 | 0.240 |
| child_explanation_med_names | 0.000 | 0.000 |
| child_explanation_numbers | 0.030 | 0.171 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 1.510 | 1.389 |
| fallbacks | 0.250 | 0.536 |
| latency_total_sec | 75.962 | 41.769 |

## NER vs gold

No completed gold annotations; NER metrics unavailable.

