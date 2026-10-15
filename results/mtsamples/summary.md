# Evaluation summary

Samples: 100 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 9.821 | 1.959 |
| patient_summary_fkgl | 5.309 | 0.998 |
| caregiver_checklist_fkgl | 8.045 | 3.575 |
| child_explanation_fkgl | 2.770 | 0.969 |
| patient_summary_fkgl_delta | -4.512 | 2.063 |
| caregiver_checklist_fkgl_delta | -1.775 | 3.747 |
| child_explanation_fkgl_delta | -7.050 | 2.299 |
| source_fre | 46.146 | 12.767 |
| patient_summary_fre | 80.690 | 5.353 |
| caregiver_checklist_fre | 58.907 | 10.932 |
| child_explanation_fre | 91.657 | 4.709 |
| patient_summary_rouge1 | 0.254 | 0.080 |
| caregiver_checklist_rouge1 | 0.198 | 0.081 |
| child_explanation_rouge1 | 0.098 | 0.043 |
| patient_summary_rougeL | 0.139 | 0.053 |
| caregiver_checklist_rougeL | 0.107 | 0.044 |
| child_explanation_rougeL | 0.065 | 0.026 |
| patient_summary_retention_first | 0.741 | 0.335 |
| caregiver_checklist_retention_first | 0.435 | 0.403 |
| patient_summary_retention_model | 0.948 | 0.184 |
| caregiver_checklist_retention_model | 0.956 | 0.165 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.390 | 0.733 |
| caregiver_checklist_unsupported_numbers | 1.560 | 1.381 |
| child_explanation_unsupported_numbers | 0.010 | 0.099 |
| patient_summary_unsupported_meds | 0.070 | 0.354 |
| caregiver_checklist_unsupported_meds | 0.050 | 0.218 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.040 | 0.196 |
| caregiver_checklist_truncation_rate | 0.010 | 0.099 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.060 | 0.237 |
| caregiver_checklist_fallback | 0.060 | 0.237 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_repetition | 0.090 | 0.286 |
| caregiver_checklist_repetition | 0.160 | 0.367 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.720 | 0.244 |
| child_explanation_med_names | 0.010 | 0.099 |
| child_explanation_numbers | 0.010 | 0.099 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 1.000 | 1.208 |
| fallbacks | 0.120 | 0.354 |
| latency_total_sec | 62.775 | 38.103 |

## NER vs gold

No completed gold annotations; NER metrics unavailable.
