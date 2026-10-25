# Evaluation summary

Samples: 100 | backend(s): llama_cpp

Retention: `_first` = first attempt, `_model` = after retries but before the fallback, no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).

## Generation metrics (mean ± std over samples)

| metric | mean | std |
|---|---|---|
| source_fkgl | 9.821 | 1.959 |
| patient_summary_fkgl | 5.277 | 1.027 |
| caregiver_checklist_fkgl | 8.063 | 3.602 |
| child_explanation_fkgl | 2.770 | 0.969 |
| patient_summary_fkgl_delta | -4.544 | 2.111 |
| caregiver_checklist_fkgl_delta | -1.758 | 3.784 |
| child_explanation_fkgl_delta | -7.050 | 2.299 |
| source_fre | 46.146 | 12.767 |
| patient_summary_fre | 80.811 | 5.468 |
| caregiver_checklist_fre | 59.024 | 11.377 |
| child_explanation_fre | 91.657 | 4.709 |
| patient_summary_rouge1 | 0.250 | 0.083 |
| caregiver_checklist_rouge1 | 0.194 | 0.080 |
| child_explanation_rouge1 | 0.098 | 0.043 |
| patient_summary_rougeL | 0.137 | 0.054 |
| caregiver_checklist_rougeL | 0.106 | 0.043 |
| child_explanation_rougeL | 0.065 | 0.026 |
| patient_summary_retention_first | 0.741 | 0.335 |
| caregiver_checklist_retention_first | 0.435 | 0.403 |
| patient_summary_retention_model | 0.942 | 0.192 |
| caregiver_checklist_retention_model | 0.940 | 0.160 |
| patient_summary_retention | 1.000 | 0.000 |
| caregiver_checklist_retention | 0.984 | 0.126 |
| patient_summary_retention_first_evidence_available | 1.000 | 0.000 |
| caregiver_checklist_retention_first_evidence_available | 1.000 | 0.000 |
| patient_summary_unsupported_numbers | 0.220 | 0.540 |
| caregiver_checklist_unsupported_numbers | 1.390 | 1.295 |
| child_explanation_unsupported_numbers | 0.000 | 0.000 |
| patient_summary_unsupported_meds | 0.000 | 0.000 |
| caregiver_checklist_unsupported_meds | 0.000 | 0.000 |
| child_explanation_unsupported_meds | 0.000 | 0.000 |
| patient_summary_truncation_rate | 0.040 | 0.196 |
| caregiver_checklist_truncation_rate | 0.040 | 0.196 |
| child_explanation_truncation_rate | 0.000 | 0.000 |
| patient_summary_fallback | 0.070 | 0.255 |
| caregiver_checklist_fallback | 0.160 | 0.367 |
| child_explanation_fallback | 0.000 | 0.000 |
| patient_summary_retries | 0.450 | 0.698 |
| caregiver_checklist_retries | 0.710 | 0.778 |
| child_explanation_retries | 0.000 | 0.000 |
| patient_summary_latency_sec | 32.159 | 20.911 |
| caregiver_checklist_latency_sec | 23.143 | 15.225 |
| child_explanation_latency_sec | 9.643 | 3.417 |
| patient_summary_repetition | 0.080 | 0.271 |
| caregiver_checklist_repetition | 0.190 | 0.392 |
| child_explanation_repetition | 0.000 | 0.000 |
| child_explanation_long_sentence_rate | 0.720 | 0.244 |
| child_explanation_med_names | 0.010 | 0.099 |
| child_explanation_numbers | 0.010 | 0.099 |
| format_validity_rate | 1.000 | nan |
| json_parse_rate | 1.000 | nan |
| total_retries | 1.160 | 1.239 |
| fallbacks | 0.230 | 0.507 |
| latency_total_sec | 64.953 | 35.768 |

## NER vs gold

No completed gold annotations; NER metrics unavailable.

