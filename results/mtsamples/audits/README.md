# MTSamples audits

Evidence samples from `data/public/mtsamples/outputs`; seed `42`. Human labels are blank. No model judge or automatic category assignment was used. These audit tables are unverified by a human.

`retention_audit.csv` samples first-attempt missing entities, stratified by persona and label. The source output files store missing entity lists but not first-attempt prose, so `final_output` is the saved final persona output and must not be mistaken for first-attempt text. Label with true omission / matcher failure / extraction error / unclear.

`unsupported_numbers_sample.csv` labels: true fabrication / equivalent / format mismatch / other. Run `python scripts/audit_mtsamples.py --score-unsupported results/mtsamples/audits/unsupported_numbers_sample.csv` after filling labels; precision is true fabrication divided by nonblank human-labeled rows.

`regimen_candidate_patterns.csv` is a regex candidate list found in source notes without an exact same-label extractor span. Counts are notes containing the form, not recall estimates.
