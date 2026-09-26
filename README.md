# Family Care Circle

> **Disclaimer:** research prototype for an academic NLP project. It is **not medical advice** and is **not
> validated for clinical use**. All clinical notes in this repository are **synthetic**. Generated text can omit,
> distort or invent information; always follow the instructions of a qualified clinician.

Family Care Circle turns a clinical, EHR-style note into three family-friendly versions using **local open-weight
models only** (no commercial LLM API is called at runtime):

| Persona | Output key | Style |
|---|---|---|
| Patient | `patient_summary` | Empathetic, jargon-free, full sentences |
| Caregiver | `caregiver_checklist` | Action-oriented bullet points (JSON list of strings) |
| Child | `child_explanation` | Short sentences, no drug names or numbers, one comforting analogy (~1st grade) |

Medications, dosages, frequencies and durations are extracted first and are never silently dropped: a missing fact
triggers a retry with feedback, and if the model still omits it, a deterministic fallback appends it verbatim.
Everything is measured, including how often that safety net was needed.

## Architecture

```
 clinical note (.txt)
        │
        ▼
 ┌──────────────┐  regex (DOSAGE / FREQUENCY / DURATION) + lexicons (MEDICATION / CONDITION / SYMPTOM),
 │ NER          │  longest-span wins; optional HF token-classification model merged in (off by default)
 │ src/ner.py   │──► entities [{text, label, start, end}] + per-medication regimens
 └──────┬───────┘
        │  "MUST INCLUDE" list, abbreviations glossed (BID → twice a day)
        ▼
 ┌──────────────┐  shared system prompt (faithfulness rules) + one prompt per persona;
 │ Prompts      │  child prompt v1 (loose) or v2 (strict), prompts.child_variant
 └──────┬───────┘
        │  3 separate calls
        ▼
 ┌──────────────┐  llama_cpp (GGUF, default) │ transformers (apply_chat_template) │ mock (no model)
 │ Generator    │  records whether each call stopped at max_new_tokens (truncation)
 └──────┬───────┘
        ▼
 ┌──────────────┐  clean → check required entities → retry with feedback (≤ max_retries)
 │ Postprocess  │  → fallback appends anything still missing → schema validation
 └──────┬───────┘
        ▼
 ┌──────────────┐  JSON per note: personas, entities, regimens, metadata per persona
 │ Pipeline     │  (retries, fallback_used, truncated, first-attempt misses, latency, params)
 └──────┬───────┘
        ▼
 ┌──────────────┐  readability (FK grade, Reading Ease), ROUGE-1/L, entity retention (first attempt,
 │ Evaluator    │  before fallback, final), fallback / truncation / repetition rates, unsupported
 └──────────────┘  numbers & medications, NER P/R/F1 vs gold → metrics.csv, summary, figures
```

## Setup

Python 3.10–3.12. **Keep the project outside iCloud-synced folders** (Desktop, Documents): with "Optimize Mac
Storage", macOS evicts files from `.venv` and `models/` to the cloud, and imports then block for minutes.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt           # enough for tests, the mock backend and all evaluation
```

Real models (pick one backend):

```bash
# llama_cpp: required on 8 GB machines (fp16 transformers models get offloaded to disk there)
CMAKE_ARGS="-DGGML_METAL=on -DGGML_NATIVE=OFF" pip install --no-cache-dir "llama-cpp-python>=0.2.80"
python -c "from huggingface_hub import hf_hub_download as d; [d(r, f, local_dir='models') for r, f in [
  ('Qwen/Qwen2.5-3B-Instruct-GGUF', 'qwen2.5-3b-instruct-q4_k_m.gguf'),
  ('Qwen/Qwen2.5-1.5B-Instruct-GGUF', 'qwen2.5-1.5b-instruct-q4_k_m.gguf')]]"

# transformers: 16 GB+ RAM or a CUDA GPU; downloads Qwen/Qwen2.5-3B-Instruct (~6 GB) on first use
pip install bitsandbytes                  # optional, 4-bit loading on CUDA only
```

Troubleshooting the llama-cpp-python build on macOS:
- **`'mutex' file not found`:** a stale Command Line Tools install is shadowing the SDK's C++ headers. Prefix the
  install with `CXXFLAGS="-nostdinc++ -isystem $(xcrun --show-sdk-path)/usr/include/c++/v1"`.
- **The build hangs in a cmake feature probe:** keep `-DGGML_NATIVE=OFF`.

## Quick start (no model, no network)

```bash
pytest                                                    # full suite, mock backend
python scripts/run_pipeline.py --input data/raw --backend mock
python scripts/run_evaluation.py                          # → results/metrics.csv, summary.md, figures/
python scripts/run_ablations.py --backend mock --seeds 0 1 2
```

Mock outputs are filled in from the MUST INCLUDE list, so they only prove the plumbing works. Mock ablations write to
`data/outputs_mock_*` and `results/ablations_mock/`, never to the real folders.

## Running the real pipeline

```bash
python scripts/run_pipeline.py --input data/raw/note_01.txt                     # one note, backend from config.yaml
python scripts/run_pipeline.py --input data/raw --output-dir data/outputs_qwen3b
python scripts/run_evaluation.py --outputs-dir data/outputs_qwen3b --results-dir results/qwen3b
python scripts/run_pipeline.py --input data/raw --backend transformers --model-id Qwen/Qwen2.5-1.5B-Instruct
```

## Ablations

Ablations live under `ablations:` in `config.yaml`: a name plus dotted-key overrides of the base config.

```yaml
ablations:
  baseline: {}
  child_v1: {prompts.child_variant: v1}                # loose child prompt (baseline uses the strict v2)
  no_ner_injection: {prompts.inject_entities: false}   # no MUST INCLUDE / entity context in prompts
  temp_0.7:                                            # every persona at 0.7
    generation.temperature: 0.7
    personas.child_explanation.temperature: 0.7
  no_retry: {max_retries: 0}
  model_1.5b: {model_id: Qwen/Qwen2.5-1.5B-Instruct, gguf_path: models/qwen2.5-1.5b-instruct-q4_k_m.gguf}
```

```bash
python scripts/run_ablations.py --backend llama_cpp --seeds 0 1 2 --only baseline,no_ner_injection,child_v1
python scripts/run_ablations.py --backend llama_cpp --only no_retry            # one run, config seed
python scripts/run_ablations.py --backend llama_cpp --force --only temp_0.7    # regenerate from scratch
```

* **Layout:** a single run writes `data/outputs_<name>/` and `results/ablations/<name>/`. With `--seeds`, each seed gets
  `data/outputs_<name>_seed<k>/` and `results/ablations/<name>/seed<k>/`. `results/ablations/summary.csv` then has
  the mean across seeds plus a `<metric>_std` column (per-seed rows in `summary_by_seed.csv`), and the charts in
  `results/ablations/figures/` get error bars.
* **Resumable:** notes that already have an output are skipped. Each output folder stores its effective config
  (`ablation_config.yaml`). If the config changed since, the runner refuses to mix old and new outputs until you
  pass `--force`.
* **Runtime:** before starting, the runner prints a plan with per-run estimates, measured on earlier runs of the same
  model. Above 1 hour it asks for confirmation (`--yes` skips the question).
* **Robust:** a loaded model is reused across ablations that share it, and a failed ablation is logged while the
  rest continue.

### Adding an ablation

1. Add an entry under `ablations:` with the settings it changes, e.g. `max_tokens_256: {personas.patient_summary.max_new_tokens: 256}`.
   Every key must already exist in `config.yaml`; a typo is rejected before anything runs.
2. **Persona-level settings win over `generation.*`.** If you change `generation.temperature`, `max_new_tokens` or
   `top_p`, also override every persona that sets its own value. The runner warns when an override is shadowed.
3. For a new behavior (not just a new value), add a config key with its current behavior as the default, read it in
   `src/pipeline.py` or `src/prompts.py`, and test it with the mock backend.
4. Run `python scripts/run_ablations.py --backend mock --only <name>` to check the flow, then the real backend.

## Analysis and reporting

```bash
python scripts/error_analysis.py            # data/outputs_baseline_seed0 → results/error_analysis.{md,json}
python scripts/build_report_tables.py       # report/tables/*.md, filled into report/project_report.md
python scripts/make_rating_sheet.py         # results/human_eval/rating_sheet.csv + answer_key.csv + RATER_GUIDE.md
python scripts/aggregate_ratings.py         # results/human_eval/ratings_*.csv → report/tables/human_eval.md
```

* **Error analysis:** failures fall into `missing_entity`, `fallback_used`, `format_or_retries`,
  `unsupported_content`, `repetition`, `child_reading_level` (above `--max-child-grade`, default 3), `truncated` and
  `empty_or_short`. The markdown gives counts plus up to 3 examples per category (note id, source excerpt, output
  excerpt, problem). The JSON lists every failure.
* **Report tables:** `main`, `retention`, `ablations`, `ner` and `human_eval` replace the text between
  `<!-- TABLE:name -->` and `<!-- /TABLE:name -->`, so re-running never duplicates. With seeds, the per-note tables pool
  all baseline seeds and the ablation table shows mean ± std. Tables built from mock data carry a warning banner.
* **Human evaluation:** raters get shuffled, blinded rows (sample id, persona, source note, text) and fill
  `clarity`, `warmth`, `factual_accuracy` (1–5) and `safety_concerns`. Repeat `--outputs-dir` to compare systems blind.
  Agreement is quadratic-weighted Cohen's κ for 2 raters, or mean pairwise κ for more. The answer key is never
  overwritten without `--force`.

## Metrics

| Metric | Meaning |
|---|---|
| FK grade / Reading Ease | textstat, source vs each persona; `_fkgl_delta` = persona − source |
| ROUGE-1 / ROUGE-L | F1 against the source note |
| Retention `_first` | share of source MEDICATION / DOSAGE / FREQUENCY / DURATION in the **first attempt**: the honest measure of the model |
| Retention `_model` | after retries, before the fallback |
| Retention (final) | final text, including the fallback (100% whenever the fallback ran) |
| Fallback rate | share of persona outputs where the fallback had to append facts |
| Truncation rate | share of outputs whose kept attempt stopped at `max_new_tokens` |
| Unsupported numbers / meds | numbers (value **and** unit) or drug names not supported by the note: a hallucination proxy. Frequencies count in plain form (`q6h` supports "every 6 hours"), brand names map to generics |
| Repetition | a bullet (caregiver) or sentence (others) with Dice token overlap > 0.9 with an earlier one, **and** the same numbers and frequency words, so parallel lines about different doses are not flagged |
| Child rules | share of sentences with 8+ words, medicine names, numbers in the child text |
| NER P/R/F1 | vs `data/gold/`, exact and relaxed (overlapping) span match |

**Known gaps:**
- **Unsupported content:** an invented instruction that reuses a number from the note (e.g. "follow up in 10 days"
  when the note has a 10-day course) is not caught.
- **Retention:** it is measured against the extracted entities, not gold.

## Backends

| Backend | Needs | Config keys |
|---|---|---|
| `llama_cpp` (default) | `llama-cpp-python` + a local `.gguf` | `gguf_path`, `llama_cpp.n_ctx`, `llama_cpp.n_gpu_layers` |
| `transformers` | `torch`, `transformers`, `accelerate` (+ `bitsandbytes` for 4-bit on CUDA) | `model_id`, `transformers.*` |
| `mock` | nothing | `mock.fail_first` (simulate empty outputs to exercise retries) |

Prompts always go through `tokenizer.apply_chat_template`; no model-specific special tokens are hardcoded. The
generation defaults are temperature 0.2, top-p 0.9 and seed 42. The `personas:` section sets `max_new_tokens` per
persona: patient 512 (350 truncated 8 of 12 Qwen2.5-3B summaries), caregiver 400, child 320.

## Project layout

```
config.yaml, requirements.txt, pytest.ini
src/
  utils.py           config, logging, file I/O, seeding
  ner.py             rule-based NER (+ optional HF model), regimen grouping
  matching.py        entity normalization ("500 mg" = "500mg", "BID" = "twice a day")
  prompts.py         system prompt, per-persona prompts (child v1/v2), MUST INCLUDE block, retry feedback
  generator.py       Generator interface: llama_cpp / transformers / mock; truncation flag
  postprocess.py     cleaning, retry loop, fallback, validation
  pipeline.py        orchestration + per-persona metadata
  evaluator.py       all per-sample metrics, NER scoring
  reporting.py       evaluate an outputs folder → CSVs, summary.md, figures
  plotting.py        chart styling, grouped bars with error bars
  ablations.py       overrides, seeds, resume, runtime estimates, cross-ablation summary
  error_analysis.py  failure categories and examples
  report_tables.py   markdown tables + report marker filling
  human_eval.py      blinded rating sheets, rating aggregation, kappa
scripts/             run_pipeline, run_evaluation, run_ablations, error_analysis,
                     build_report_tables, make_rating_sheet, aggregate_ratings
data/raw/            12 synthetic notes
data/gold/           hand-annotated entities for note_01–06 (+ annotation guide)
data/outputs*/       generated JSON (git-ignored)
results/             metrics, ablations/, error_analysis.*, human_eval/
tests/               one test file per src module; mock backend only
report/              project_report.md (+ tables/)
```
