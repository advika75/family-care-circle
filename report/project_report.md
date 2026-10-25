# Family Care Circle: Persona-Adapted, Fact-Preserving Simplification of Clinical Notes with Local LLMs

*Authors: TODO · Course: TODO · Date: TODO*

> **Disclaimer:** Family Care Circle is a research prototype built for a course project. It does not provide
> medical advice, is not a medical device, and is not validated for clinical use. The 12 notes in `data/raw/` are
> synthetic; the MTSamples notes used for the public evaluation are real, de-identified public transcriptions.

## Abstract

TODO (150–250 words): problem (clinical notes are hard for patients and families to read), approach (NER-guided,
per-persona prompting of a local open-weight LLM with retry and fallback), evaluation (readability, ROUGE,
first-attempt vs final entity retention, fallback rate, hallucination and repetition checks, NER F1, human ratings),
key results (Tables 1-5), and main limitation.

## 1. Introduction

- Motivation: health literacy; discharge instructions; families (patients, caregivers, children) need different framings.
- Goal: generate three persona outputs from one note while preserving medications, doses, frequencies and durations.
- Constraint: inference runs on hardware you control, with no external model API (privacy; no commercial APIs). The web app is self-hosted.
- Contributions:
  1. A pipeline that combines rule-based clinical NER with per-persona LLM prompting.
  2. A retry-and-fallback mechanism that guarantees required facts are surfaced, with its use measured rather
     than hidden (first-attempt retention and fallback rate).
  3. An evaluation suite covering readability, content overlap, fact retention, unsupported content, repetition,
     truncation, NER quality and blinded human ratings, with multi-seed ablations.

## 2. Related Work

TODO. Suggested threads:
- Medical text simplification and lay summarization (for example, plain-language summaries, discharge-note simplification).
- Readability metrics (Flesch–Kincaid) and their limitations for clinical text.
- Clinical NER (i2b2/n2c2 medication extraction; rule-based systems; biomedical token-classification models).
- Faithfulness and hallucination in LLM summarization; entity-based factuality metrics.
- Persona- and audience-conditioned generation.

## 3. Method

### 3.1 Entity extraction
Rule-based extractor (regex for DOSAGE / FREQUENCY / DURATION; lexicons for MEDICATION / CONDITION / SYMPTOM;
longest-span overlap resolution). Optional HF model merged with rule precedence. Regimen grouping links each
medication to the dose, frequency and duration on its line.

### 3.2 Persona prompting
Shared system prompt (faithfulness rules) + one template per persona; required entities injected as a MUST
INCLUDE list, with abbreviations glossed (BID → twice a day). One generation call per persona. Two child prompts:
v1 (loose: simple words, comforting analogy) and v2 (strict: sentences under 8 words, no medicine names or numbers
beyond "medicine" / "a few days", exactly one analogy).

### 3.3 Post-processing
Cleaning (code fences, preambles, template tokens, stray JSON) → required-entity check → retry with explicit
feedback naming the missing facts (max N) → deterministic fallback that appends missing facts verbatim → schema
validation. Per persona we record the attempts, first-attempt misses, fallback use, and whether generation stopped
at `max_new_tokens` (llama.cpp `finish_reason == "length"`; transformers: token budget used without an EOS).

### 3.4 Models and backends
Qwen2.5-3B-Instruct (default) and Qwen2.5-1.5B-Instruct, via llama.cpp (4-bit GGUF, Q4_K_M) or transformers.
Decoding: temperature 0.2 (child 0.3), top-p 0.9; `max_new_tokens` 512 / 400 / 320 for patient / caregiver / child.

## 4. Experiments

### 4.1 Data
12 synthetic notes (strep throat, type 2 diabetes, hypertension, asthma, post-op appendectomy, UTI, pneumonia,
atrial fibrillation, depression/anxiety, migraine, heart failure, cellulitis). Gold entity annotations for 6
notes (146 entities; guidelines in `data/gold/README.md`).

### 4.2 Metrics
- Readability: FKGL and FRE for source and each persona; FKGL delta.
- ROUGE-1 / ROUGE-L F1 against the source note.
- Entity retention: per-type recall of source MEDICATION / DOSAGE / FREQUENCY / DURATION in patient and caregiver
  outputs, reported on the first attempt (model quality), after retries, and in the final text (after fallback).
- Fallback rate, truncation rate, format validity rate, retries per note, latency.
- Repetition: outputs with a duplicated or near-duplicated bullet/sentence (token overlap > 0.9 and identical
  numbers/frequency words).
- Child-prompt compliance: share of sentences with 8+ words, medicine names and numbers in the child text.
- NER precision / recall / F1 against gold (exact and relaxed span match).
- Unsupported content (hallucination proxy): numbers and medication names in an output that the source
  note does not support, per persona.
- Human evaluation: blinded ratings of clarity, warmth and factual accuracy (1–5) plus free-text safety
  concerns; inter-rater agreement with quadratic-weighted Cohen's kappa.

### 4.3 Setup
Hardware: Apple M1, 8 GB unified memory; Qwen2.5-3B-Instruct Q4_K_M through llama.cpp with Metal (fp16 transformers
does not fit in memory). Each ablation is run with seeds 0, 1 and 2 on all 12 notes; tables report mean ± std across
seeds. TODO: add any further runs.

## 5. Results

**Table 1: Main results.** Readability and overlap with the source for each persona (baseline configuration).

<!-- TABLE:main -->
| Text | FK grade ↓ | Reading Ease ↑ | ROUGE-1 | ROUGE-L |
|---|---|---|---|---|
| Source note | 8.05 ± 1.19 | 54.0 ± 9.4 | – | – |
| Patient | 5.36 ± 0.79 | 79.2 ± 4.2 | 0.29 ± 0.04 | 0.21 ± 0.03 |
| Caregiver | 6.65 ± 1.28 | 65.9 ± 7.2 | 0.46 ± 0.07 | 0.31 ± 0.07 |
| Child | 3.16 ± 1.03 | 89.0 ± 5.5 | 0.19 ± 0.05 | 0.13 ± 0.04 |

_Mean ± SD over 36 outputs (12 notes × 3 seeds). ROUGE is computed against the source note._
<!-- /TABLE:main -->

**Table 2: Entity retention per type.**

<!-- TABLE:retention -->
| Persona | Medication | Dosage | Frequency | Duration | Overall | 1st attempt | Final (with fallback) |
|---|---|---|---|---|---|---|---|
| Patient | 100.0% | 89.3% | 98.1% | 99.1% | 96.3% | 81.0% | 100.0% |
| Caregiver | 99.1% | 100.0% | 100.0% | 100.0% | 99.8% | 83.9% | 100.0% |

_Share of unique source entities kept. Per-type columns and Overall: after retries, before the fallback. Final includes facts appended by the fallback._
<!-- /TABLE:retention -->

**Table 3: Ablations.** Each row changes one setting relative to the baseline.

<!-- TABLE:ablations -->
| Ablation | ΔFK patient | ΔFK child | Child sentences ≥8 words | ROUGE-L patient | Retention patient | Retention caregiver | 1st-try retention patient | Unsupported numbers / note (patient) | Fallback rate | Truncated (patient) | JSON valid | Retries / note | Latency / note (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | -2.69 ± 0.15 | -4.89 ± 0.24 | 74.1% ± 4.3 | 0.21 ± 0.00 | 96.3% ± 1.9 | 99.8% ± 0.4 | 81.0% ± 3.8 | 0.14 ± 0.05 | 13.0% ± 7.0 | 0.0% ± 0.0 | 100.0% ± 0.0 | 2.14 ± 0.54 | 98.6 ± 15.3 |
| child_v1 | -2.69 ± 0.15 (+0.00) | -3.67 ± 0.15 (+1.22) | 88.3% ± 4.4 (+14.1 pp) | 0.21 ± 0.00 (+0.00) | 96.3% ± 1.9 (+0.0 pp) | 99.8% ± 0.4 (+0.0 pp) | 81.0% ± 3.8 (+0.0 pp) | 0.14 ± 0.05 (+0.00) | 13.0% ± 7.0 (+0.0 pp) | 0.0% ± 0.0 (+0.0 pp) | 100.0% ± 0.0 (+0.0 pp) | 2.14 ± 0.54 (+0.00) | 73.9 ± 8.0 (-24.68) |
| no_ner_injection | -2.58 ± 0.04 (+0.11) | -4.99 ± 0.28 (-0.10) | 75.8% ± 9.2 (+1.7 pp) | 0.20 ± 0.01 (-0.01) | 88.3% ± 2.3 (-7.9 pp) | 91.0% ± 2.8 (-8.8 pp) | 69.3% ± 2.8 (-11.8 pp) | 0.28 ± 0.17 (+0.14) | 30.6% ± 5.6 (+17.6 pp) | 2.8% ± 4.8 (+2.8 pp) | 100.0% ± 0.0 (+0.0 pp) | 3.42 ± 0.08 (+1.28) | 86.1 ± 8.8 (-12.45) |

_Values are mean ± std across 3 seeds; parentheses give the difference of means from **baseline** (pp = percentage points). ΔFK = persona grade minus source grade (more negative = simpler). Retention is the model's own text after retries but before the fallback. 1st-try retention is the cleanest measure of entity injection, since retries re-inject missing facts. Fallback rate = share of all persona outputs that needed the fallback. Truncated = generation stopped at max_new_tokens._
<!-- /TABLE:ablations -->

**Table 4: NER against gold annotations.**

<!-- TABLE:ner -->
| Label | P (exact) | R (exact) | F1 (exact) | P (relaxed) | R (relaxed) | F1 (relaxed) |
|---|---|---|---|---|---|---|
| CONDITION | 0.76 | 0.81 | 0.79 | 0.94 | 1.00 | 0.97 |
| DOSAGE | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| DURATION | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| FREQUENCY | 0.97 | 1.00 | 0.98 | 0.97 | 1.00 | 0.98 |
| MEDICATION | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| SYMPTOM | 0.98 | 0.94 | 0.96 | 0.98 | 0.94 | 0.96 |
| **MICRO** | 0.96 | 0.96 | 0.96 | 0.98 | 0.98 | 0.98 |

_Rule-based NER vs hand-annotated gold (6 notes). Relaxed = overlapping span with the same label._
<!-- /TABLE:ner -->

**Table 5: Human evaluation** (blinded ratings, 1–5).

<!-- TABLE:human_eval -->
_Run `python scripts/aggregate_ratings.py` after collecting rating sheets, then `python scripts/build_report_tables.py`._
<!-- /TABLE:human_eval -->

**Figure 1:** `results/ablations/baseline/seed0/figures/readability_before_after.png`
**Figure 2:** `results/ablations/figures/retention.png` (retention per ablation, error bars = std across seeds)
**Figure 3:** `results/ablations/figures/reliability.png` (validity, fallback rate, retries, latency per ablation)

Qualitative examples: TODO (one note, all three personas; highlight a retry that fixed an omission).

## 6. Error analysis

TODO: summarize `results/error_analysis.md` (baseline, seed 0): counts per category (missing_entity,
fallback_used, format_or_retries, unsupported_content, repetition, child_reading_level, truncated, empty_or_short)
and 2–3 concrete examples, e.g. unsupported numbers such as invented lab thresholds, facts the model omitted that the
fallback had to append, repeated checklist bullets, child explanations above the target reading level.

## 7. Limitations

- **Medical safety:** outputs can omit, distort or invent information. This system is not validated for
  clinical use and must not replace communication from clinicians. Any real deployment would need
  clinician review, safety testing and regulatory approval.
- Synthetic, small dataset (12 notes; 6 with gold labels annotated by the project team, not clinicians).
- Rule-based NER has limited lexicon coverage; entity retention is measured against extracted (not gold) entities.
- Surface-level retention does not verify that facts are attached to the right medication. The unsupported-number
  and unsupported-medication checks catch only some hallucinations: an invented instruction that reuses a number
  from the note (e.g. "follow up in 10 days" when the note has a 10-day antibiotic course) is not detected.
- Repetition and hallucination checks are lexical heuristics; they miss paraphrased repetition and facts
  attached to the wrong medication.
- Readability formulas are coarse proxies. The human evaluation is small (few raters, not clinicians, not
  actual patients, caregivers or children).
- ROUGE against the source rewards copying, which is in tension with simplification.

## 8. Conclusion

TODO: summary of findings and future work (human evaluation, hallucination detection, larger/real de-identified
datasets, multilingual output).

## References

TODO
