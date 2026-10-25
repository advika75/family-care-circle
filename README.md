# Family Care Circle

> **Disclaimer:** research prototype for an academic NLP project. It is **not medical advice** and is **not
> validated for clinical use**. The notes in `data/raw/` are **synthetic**. The MTSamples notes used for the public
> evaluation are **real, de-identified public transcriptions** (not synthetic). Generated text can omit, distort or
> invent information; always follow the instructions of a qualified clinician.

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
 │ Pipeline     │  (exact first-attempt text, retry/fallback status, truncation, latency, params)
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

## Demo

A local Streamlit app: pick a note from `data/raw` or paste your own, see extracted entities highlighted by
label, the three persona outputs side by side, and per-output status (retries, fallback-appended facts,
truncation, redacted contradicted doses, unsupported-medication/number flags).

```bash
pip install streamlit                                      # not needed for the pipeline, evaluation or tests
streamlit run scripts/demo_app.py                          # real model, backend from config.yaml
streamlit run scripts/demo_app.py -- --mock-backend          # no model download or inference, instant UI
```

The model loads once per session (`st.cache_resource`), not on every click, so a real run stays usable on an
8 GB M1 with the default `llama_cpp` backend; the first "Generate" click shows a loading spinner while the
model loads. `--mock-backend` skips the model entirely for fast UI iteration.

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
python scripts/build_results_tables.py      # results/tables/*.{csv,md,tex} + results/tables/figures/*.png
python scripts/build_limitations.py         # report/limitations.md
```

* **Error analysis:** failures fall into `missing_entity`, `fallback_used`, `format_or_retries`,
  `unsupported_content`, `repetition`, `child_reading_level` (above `--max-child-grade`, default 3), `truncated` and
  `empty_or_short`. The markdown gives counts plus up to 3 examples per category (note id, source excerpt, output
  excerpt, problem). The JSON lists every failure.
* **Evaluation output safety:** `run_evaluation.py` refuses to replace existing result files. Choose a fresh
  `--results-dir` for a separate run, or pass `--force` when you intentionally want to regenerate those files.
* **Report tables:** `main`, `retention`, `ablations`, `ner` and `human_eval` replace the text between
  `<!-- TABLE:name -->` and `<!-- /TABLE:name -->`, so re-running never duplicates. With seeds, the per-note tables pool
  all baseline seeds and the ablation table shows mean ± std. Tables built from mock data carry a warning banner.
* **Results tables (CSV/Markdown/LaTeX) and figures:** `build_results_tables.py` covers the synthetic ablations,
  the real MTSamples generation metrics, and NER (synthetic, and MTSamples once any gold annotations are marked
  `complete`) — each table states its dataset and note count, and a missing result file writes an explicit "not
  available" table instead of a placeholder number. Figures: entity retention and fallback rate by condition
  (synthetic), and Flesch-Kincaid grade per persona vs. the child persona's ~1st-grade target (both datasets,
  whichever are available).
* **Limitations draft:** `build_limitations.py` writes `report/limitations.md` from measured evidence (dataset
  sizes, gold-annotation counts, hallucination-check failure counts, child FKGL, human-eval rater count) plus
  fixed structural caveats: the rule-based NER's coverage ceiling (retention only checks what it found, so it can
  overstate true factual coverage), the tiny synthetic set, FKGL as a weak comprehension proxy, the narrow
  lexical hallucination checks, and the small (or not-yet-collected) human-eval sample.
* **Human evaluation (CSV sheet):** raters get shuffled, blinded rows (sample id, persona, source note, text) and
  fill `clarity`, `warmth`, `factual_accuracy` (1–5) and `safety_concerns`. Repeat `--outputs-dir` to compare
  systems blind. Agreement is quadratic-weighted Cohen's κ for 2 raters, or mean pairwise κ for more. The answer
  key is never overwritten without `--force`.
* **Human evaluation (local rating UI):** a second, UI-based workflow for rating the `baseline` vs.
  `no_ner_injection` conditions on `factual_accuracy`, `completeness`, `readability` and `persona_suitability`
  (1–5), plus a "missing or wrong medical fact" checkbox with a free-text note.

  ```bash
  python scripts/build_rating_set.py                         # results/human_eval/rating_set.json + answer_key.csv
  python scripts/rate_outputs.py --rater alice                # open http://127.0.0.1:8766/ ; a second rater
  python scripts/rate_outputs.py --rater bob --port 8767       #   runs this with a different --rater (and --port
                                                                #   if running at the same time)
  python scripts/aggregate_human_ratings.py                  # report/tables/human_eval_conditions.md
  ```

  Each rater's answers are saved incrementally to `results/human_eval/ratings_<rater>.json` (so a rater can stop
  and resume) and the UI never loads the answer key, so condition labels stay hidden at the code level. Aggregation
  reports per-condition-and-persona means, flag counts and quadratic-weighted Cohen's κ (0 or 1 rater: "n/a").

## Metrics

| Metric | Meaning |
|---|---|
| FK grade / Reading Ease | textstat, source vs each persona; `_fkgl_delta` = persona − source |
| ROUGE-1 / ROUGE-L | Lexical overlap F1 against the source note; not a factuality or summary-quality measure |
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

## Reproducibility

* **Pinned dependencies:** `requirements.txt` pins exact versions (not `>=` ranges) last tested together; `pip
  install -r requirements.txt` reproduces that environment. Bump a pin deliberately and re-run the full test
  suite before relying on it.
* **Seeds and model identity in every run's metadata:** each output JSON's `metadata` records `seed` (default
  42; also set via `generation.seed` in `config.yaml`), `model_id`, and `model_hash` — `sha256:<hex>` of the
  exact `.gguf` file for the `llama_cpp` backend, or `hf_commit:<hash>` for `transformers` when the loaded
  model exposes a resolved revision (`None` for the mock backend and for a `transformers` model whose revision
  isn't available offline). This lets you confirm two runs used byte-identical weights, not just the same
  `model_id` string.
* **`make reproduce-small`:** runs the full test suite, then one pass of the real pipeline and evaluation code
  paths on the mock backend (`.reproduce_small/`, git-ignored). Runs entirely on this machine and is fast (no model download); not a
  substitute for a real run, just a sanity check that the wiring isn't broken. `make clean-reproduce-small`
  removes the scratch output.
* **Exact commands for every experiment already run in this repo**, in order:

  ```bash
  pip install -r requirements.txt
  make reproduce-small                                                          # sanity check, no model needed

  # Synthetic ablations (baseline, child_v1, no_ner_injection), 3 seeds each, Qwen2.5-3B-Instruct Q4_K_M:
  python scripts/run_ablations.py --backend llama_cpp --seeds 0 1 2
  python scripts/error_analysis.py                                             # results/error_analysis.{md,json}
  python scripts/build_report_tables.py                                        # fills report/project_report.md

  # MTSamples (100 real, de-identified public notes, seed 42; not synthetic; see "Public Dataset Evaluation" above for obtaining source.csv):
  python scripts/prepare_mtsamples.py
  python scripts/run_pipeline.py --dataset mtsamples --backend llama_cpp       # resumable; --force to redo
  python scripts/run_evaluation.py --dataset mtsamples
  python scripts/evaluate_mtsamples_ner.py                                     # results/mtsamples_ner/{mtsamples_ner_summary.json,mtsamples_ner_metrics.csv,mtsamples_ner_errors.csv}
  python scripts/error_analysis.py --outputs-dir data/public/mtsamples/outputs --results-dir results/mtsamples

  # Human evaluation (UI-based; see "Analysis and reporting" above for the CSV-sheet alternative):
  python scripts/build_rating_set.py
  python scripts/rate_outputs.py --rater <name>                                # repeat per rater, different --port
  python scripts/aggregate_human_ratings.py

  # Report-ready outputs:
  python scripts/build_results_tables.py                                       # results/tables/*
  python scripts/build_limitations.py                                          # report/limitations.md
  ```

  The MTSamples run depends on `data/public/mtsamples/source.csv`, which is not redistributed (see "Public
  Dataset Evaluation"); without it, the MTSamples steps above are not reproducible by someone else from this
  repo alone, and `build_results_tables.py` / `build_limitations.py` will correctly report those tables as "not
  available" instead of fabricating numbers.

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

### Public Dataset Evaluation

The synthetic dataset remains the controlled evaluation set. MTSamples is an external/public source of clinical transcription notes; public evaluation uses a reproducibly selected subset (up to 100 notes). Generation runs on hardware you control, with no external model API. Gold annotations use the existing span-based JSON format and are only used for a manually annotated subset.

Download the Medical Transcriptions CSV from [Kaggle's MTSamples dataset](https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions) (sign in to Kaggle if prompted), then place or rename the CSV to `data/public/mtsamples/source.csv`. Rebuild the prepared notes and `subset.json` with `python scripts/prepare_mtsamples.py --input data/public/mtsamples/source.csv --seed 42`; the default seed is 42. The CSV is not redistributed here.

Place the Qwen GGUF at the `gguf_path` configured in `config.yaml` (the default is `models/qwen2.5-3b-instruct-q4_k_m.gguf`; the alternate 1.5B model is also under `models/`). These GGUF files are not tracked. The checked-in run metadata does not record a GGUF SHA256; to record the exact local file hash, run `shasum -a 256 models/<model-file>.gguf` and retain the output with the run metadata.

Set `dataset: mtsamples` in `config.yaml` to run the configured pipeline and evaluation commands on that subset.

Each newly generated output JSON stores `metadata.first_attempt_text` as an exact raw string for each persona, alongside `metadata.first_attempt_evidence` (note ID, persona, model/config, attempt and retry counts/status, fallback status, and JSON-pointer output references). Retry/fallback output remains in the persona's ordinary top-level output field. Evaluation calculates first-attempt retention from this captured text and final retention from that top-level final output. Older records without captured text report first-attempt retention as missing (`NaN`) plus an evidence-availability metric; the prior `missing_first_attempt` list is not used to reconstruct prose.

For a future MTSamples generation run, use a new output directory so existing experiment outputs remain untouched:

```bash
python scripts/run_pipeline.py --dataset mtsamples --output-dir data/public/mtsamples/outputs_first_attempt_evidence
python scripts/run_evaluation.py --dataset mtsamples --outputs-dir data/public/mtsamples/outputs_first_attempt_evidence --results-dir results/mtsamples_first_attempt_evidence
```

The paired research comparison uses the same configured MTSamples subset, seed 42, local Qwen2.5-3B Q4_K_M
model and decoding settings. The no-injection condition removes the initial extracted-entity context and MUST
INCLUDE block. Retries still give feedback based on missing extracted entities, and the deterministic fallback
still restores them; this estimates the effect of initial entity injection while keeping the retry/fallback
policy shared. The runner records the planned note IDs and effective configuration in each `run_info.json`,
and refuses existing MTSamples ablation result directories instead of overwriting them.

After reviewing the recorded configuration and estimated runtime, run the two conditions together, then analyze
their paired per-note metrics:

```bash
python scripts/run_ablations.py --dataset mtsamples --backend llama_cpp --only baseline,no_ner_injection --run-tag first_attempt_evidence_v1 --yes
python scripts/compare_paired_mtsamples.py --baseline-results-dir results/mtsamples/baseline_first_attempt_evidence_v1 --no-injection-results-dir results/mtsamples/no_injection_first_attempt_evidence_v1 --out-dir results/mtsamples/paired_analysis_first_attempt_evidence_v1
```

For this run tag, baseline outputs/results go to `data/public/mtsamples/outputs_baseline_first_attempt_evidence_v1/` and
`results/mtsamples/baseline_first_attempt_evidence_v1/`; no-injection outputs/results go to
`data/public/mtsamples/outputs_no_injection_first_attempt_evidence_v1/` and
`results/mtsamples/no_injection_first_attempt_evidence_v1/`. The ablation summary is written under
`results/mtsamples/ablation_summary_first_attempt_evidence_v1/`; the paired analysis writes to
`results/mtsamples/paired_analysis_first_attempt_evidence_v1/`. Run tags require fresh output and summary paths.
The comparison reports paired differences with bootstrap intervals, exact paired sign tests for continuous
outcomes and exact McNemar tests for binary flags. It lists missing IDs and does not run inference or fabricate
values for missing outputs. Its detector-derived safety flags are not clinical safety evidence.

shasum -a 256 models/qwen2.5-3b-instruct-q4_k_m.gguf

Annotate without rule-based suggestions visible with `python scripts/annotate_mtsamples.py --blind`. Save gold annotations using the existing span JSON schema; each newly labeled entity records `annotation_source` as `accepted_suggestion`, `edited_suggestion`, or `manual` when applicable. A save leaves the note `annotated`; to include it in NER evaluation, review the original note and saved spans, select the explicit review-confirmation checkbox, then choose **Save and mark complete**. Later edits return its status to `annotated`. The evaluator's default is the dedicated `results/mtsamples_ner/` directory, separate from generation results, and refuses to overwrite it if it exists. After completing the first manually reviewed note, run `python scripts/evaluate_mtsamples_ner.py --results-dir results/mtsamples_ner_reviewed_batch1` to write a fresh evaluation. For another independent run, choose another new `--results-dir`.

## Multi-user web app

> **Prototype. Not for real patient data.** Full documentation: [`app/README.md`](app/README.md). The self-audit of this app (done by its author, not a third-party review), with the status of every finding, is in [`app/AUDIT.md`](app/AUDIT.md).

`app/` is a self-hosted, multi-user web application built around the pipeline above (which it calls and never modifies). A profile creator makes a patient profile, gets a patient ID, and invites family members; each member sees only the output suited to their role. It uses FastAPI, SQLite and server-rendered templates, and makes no outbound network calls.

```bash
.venv/bin/python -m pip install -r requirements-app.txt
make app-run                       # http://127.0.0.1:8000, mock backend (no model needed)
APP_BACKEND=llama_cpp make app-run # the local GGUF model from config.yaml
make app-seed                      # SYNTHETIC demo accounts on an empty database
make app-test                      # the app's tests
```

**Roles.** *Creator*: everything, including inviting, approving and removing members. *Caregiver*: all three outputs, the source note, review flags, ticking the checklist; adds notes only if the creator allows it; may approve pending *child* requests. *Patient*: the patient summary only. *Child*: the child explanation only (first names of the circle, nothing clinical). Pending and removed members see only a status page. Permissions are enforced on the server in one place (`app/permissions.py`).

**The patient ID is an identifier, not a credential.** Knowing it grants nothing. Joining needs your own account, a single-use invitation code issued for that profile (shown once, stored only as a hash, valid for 7 days) and approval by the creator.

**What is NOT secured.** No HTTPS termination (use a TLS proxy and `APP_HTTPS=1`); no distributed rate limiting; no third-party audit; no encryption at rest; no email delivery (invitation codes are passed on out of band) and no password reset; sign-up cannot be made fully enumeration-proof; sessions have no idle timeout. The child safety check is rule-based and misses spelled-out numbers, brand or misspelled medicine names, and frightening wording. See `app/README.md` for the complete list and the evidence for each control.

## Hosting a demo

`deploy/` contains a Dockerfile and a Render blueprint for putting the web app online as a throw-away **demo with the mock backend only** (no model file, placeholder output, data wiped on restart on the free plan). Steps, environment variables, the `APP_TRUSTED_PROXIES` caveat and what was and was not verified are in [`deploy/README.md`](deploy/README.md). **Prototype. Not for real patient data.**
