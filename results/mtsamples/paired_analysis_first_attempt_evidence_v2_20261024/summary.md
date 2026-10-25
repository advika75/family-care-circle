# Paired MTSamples comparison

Expected IDs: 100 · baseline metrics: 100 · no-injection metrics: 100 · paired: 100
Unparseable output files: baseline 0 · no-injection 0

Differences are no-injection minus baseline. Confidence intervals are percentile bootstrap intervals over paired note differences (10000 resamples, seed 42). Continuous metrics use the exact paired sign test; binary flags use exact McNemar tests.

This is an exploratory comparison of rule-derived metrics, not a clinical safety assessment. Missing IDs are excluded from paired estimates and listed in `unpaired_ids.csv`.

| metric | n_paired | baseline_mean_paired | no_injection_mean_paired | mean_difference_no_injection_minus_baseline | bootstrap_95_ci_low | bootstrap_95_ci_high | paired_test | paired_p_value | n_missing_first_attempt_evidence |
|---|---|---|---|---|---|---|---|---|---|
| patient_summary_retention_first | 62.0000 | 0.7411 | 0.4349 | -0.3061 | -0.4235 | -0.1881 | exact sign test | 0.0000 | 38.0000 |
| patient_summary_retention_model | 62.0000 | 0.9423 | 0.9295 | -0.0128 | -0.0701 | 0.0430 | exact sign test | 0.2266 | nan |
| patient_summary_retention | 62.0000 | 1.0000 | 0.9839 | -0.0161 | -0.0484 | 0.0000 | exact sign test | 1.0000 | nan |
| caregiver_checklist_retention_first | 62.0000 | 0.4352 | 0.2466 | -0.1886 | -0.2934 | -0.0860 | exact sign test | 0.0001 | 38.0000 |
| caregiver_checklist_retention_model | 62.0000 | 0.9403 | 0.9086 | -0.0316 | -0.1025 | 0.0366 | exact sign test | 1.0000 | nan |
| caregiver_checklist_retention | 62.0000 | 0.9839 | 0.9677 | -0.0161 | -0.0806 | 0.0323 | exact sign test | 1.0000 | nan |
| total_retries | 100.0000 | 1.1600 | 1.5100 | 0.3500 | 0.1600 | 0.5500 | exact sign test | 0.0025 | nan |
| fallbacks | 100.0000 | 0.2300 | 0.2500 | 0.0200 | -0.0800 | 0.1200 | exact sign test | 0.8318 | nan |
| latency_total_sec | 100.0000 | 64.9534 | 75.9623 | 11.0089 | 6.3300 | 15.6681 | exact sign test | 0.0000 | nan |
| patient_summary_fkgl | 100.0000 | 5.2766 | 5.3128 | 0.0362 | -0.2122 | 0.2873 | exact sign test | 0.2299 | nan |
| patient_summary_fre | 100.0000 | 80.8112 | 80.4939 | -0.3173 | -1.5149 | 0.9178 | exact sign test | 0.1557 | nan |
| patient_summary_retries | 100.0000 | 0.4500 | 0.6700 | 0.2200 | 0.0900 | 0.3500 | exact sign test | 0.0003 | nan |
| patient_summary_latency_sec | 100.0000 | 32.1594 | 39.5624 | 7.4030 | 4.0489 | 10.7765 | exact sign test | 0.0000 | nan |
| caregiver_checklist_fkgl | 100.0000 | 8.0628 | 7.5264 | -0.5364 | -1.3468 | 0.1730 | exact sign test | 0.0214 | nan |
| caregiver_checklist_fre | 100.0000 | 59.0244 | 60.9245 | 1.9001 | -0.2613 | 4.2303 | exact sign test | 0.1011 | nan |
| caregiver_checklist_retries | 100.0000 | 0.7100 | 0.8400 | 0.1300 | 0.0200 | 0.2500 | exact sign test | 0.0614 | nan |
| caregiver_checklist_latency_sec | 100.0000 | 23.1428 | 26.0337 | 2.8909 | 0.9461 | 4.7296 | exact sign test | 0.0066 | nan |
| child_explanation_fkgl | 100.0000 | 2.7704 | 2.8750 | 0.1046 | -0.0838 | 0.3053 | exact sign test | 0.8176 | nan |
| child_explanation_fre | 100.0000 | 91.6571 | 91.3313 | -0.3258 | -1.4133 | 0.7253 | exact sign test | 1.0000 | nan |
| child_explanation_retries | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact sign test | 1.0000 | nan |
| child_explanation_latency_sec | 100.0000 | 9.6428 | 10.3531 | 0.7103 | 0.2995 | 1.1168 | exact sign test | 0.0066 | nan |
| child_explanation_long_sentence_rate | 100.0000 | 0.7197 | 0.7340 | 0.0143 | -0.0279 | 0.0560 | exact sign test | 0.6989 | nan |
| child_explanation_med_names | 100.0000 | 0.0100 | 0.0000 | -0.0100 | -0.0300 | 0.0000 | exact sign test | 1.0000 | nan |
| child_explanation_numbers | 100.0000 | 0.0100 | 0.0300 | 0.0200 | 0.0000 | 0.0500 | exact sign test | 0.5000 | nan |
| valid | 100.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| patient_summary_fallback | 100.0000 | 0.0700 | 0.1100 | 0.0400 | -0.0200 | 0.1000 | exact McNemar | 0.3438 | nan |
| patient_summary_truncation_rate | 100.0000 | 0.0400 | 0.0600 | 0.0200 | -0.0200 | 0.0600 | exact McNemar | 0.6250 | nan |
| patient_summary_repetition | 100.0000 | 0.0800 | 0.1200 | 0.0400 | -0.0300 | 0.1200 | exact McNemar | 0.4545 | nan |
| caregiver_checklist_fallback | 100.0000 | 0.1600 | 0.1400 | -0.0200 | -0.1000 | 0.0600 | exact McNemar | 0.8036 | nan |
| caregiver_checklist_truncation_rate | 100.0000 | 0.0400 | 0.0300 | -0.0100 | -0.0400 | 0.0200 | exact McNemar | 1.0000 | nan |
| caregiver_checklist_repetition | 100.0000 | 0.1900 | 0.2200 | 0.0300 | -0.0800 | 0.1300 | exact McNemar | 0.7111 | nan |
| child_explanation_fallback | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| child_explanation_truncation_rate | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| child_explanation_repetition | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| patient_summary_unsupported_numbers_flag | 100.0000 | 0.1600 | 0.2000 | 0.0400 | -0.0500 | 0.1300 | exact McNemar | 0.5235 | nan |
| patient_summary_unsupported_meds_flag | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| caregiver_checklist_unsupported_numbers_flag | 100.0000 | 0.6700 | 0.7000 | 0.0300 | -0.0500 | 0.1100 | exact McNemar | 0.6291 | nan |
| caregiver_checklist_unsupported_meds_flag | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| child_explanation_unsupported_numbers_flag | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
| child_explanation_unsupported_meds_flag | 100.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | exact McNemar | 1.0000 | nan |
