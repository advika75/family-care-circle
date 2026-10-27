# Convenience targets. All of these are local-only; nothing here calls a commercial API or downloads a model.

REPRODUCE_SMALL_DIR := .reproduce_small

.PHONY: test reproduce-small clean-reproduce-small

test:
	pytest -q

# A fast, fully local sanity check: the full test suite, then one pass of the real pipeline code paths
# (generation -> postprocess -> evaluation) on the mock backend, so a broken wire-up is caught even when
# nobody has the quantized model downloaded. Not a substitute for a real run; see README "Running the real
# pipeline" for that.
reproduce-small: test
	rm -rf $(REPRODUCE_SMALL_DIR)
	python scripts/run_pipeline.py --input data/raw --backend mock --output-dir $(REPRODUCE_SMALL_DIR)/outputs
	python scripts/run_evaluation.py --outputs-dir $(REPRODUCE_SMALL_DIR)/outputs --results-dir $(REPRODUCE_SMALL_DIR)/results
	@echo "reproduce-small OK: tests passed; mock pipeline + evaluation ran end-to-end."

clean-reproduce-small:
	rm -rf $(REPRODUCE_SMALL_DIR)

# ---- Family Care Circle web app (app/). Local only; see app/README.md. ----
# app-run uses the backend selected in the environment (mock by default).
.PHONY: app-run app-test app-demo

app-run:
	python -m uvicorn app.web.main:create_app --factory --host 127.0.0.1 --port 8000 --no-server-header

app-test:
	python -m pytest tests/app -q

# Create SYNTHETIC demo accounts + notes from data/raw in an EMPTY database (refuses otherwise). See app/dev_seed.py.
.PHONY: app-seed

app-seed:
	python -m app.dev_seed

# Slow, browser (Playwright) and real-model tests of the web app; skipped by `make app-test`.
.PHONY: app-test-slow

app-test-slow:
	APP_RUN_SLOW=1 python -m pytest tests/app -q -m "slow or browser or realmodel"

# Fixed-port mock demo. No model service or model download is needed.
app-demo: export APP_BACKEND := mock
app-demo: export APP_DB_PATH := app/var/demo.sqlite3
app-demo:
	@echo "Backend: mock | Model: none | URL: http://127.0.0.1:8000"
	python -m uvicorn app.web.main:create_app --factory --host 127.0.0.1 --port 8000 --no-server-header

.PHONY: app-demo-seed

# Creates creator/caregiver/patient/child demo accounts (SYNTHETIC) in an EMPTY app/var/demo.sqlite3 and saves the
# one-time passwords to app/var/demo_credentials.txt (git-ignored).
app-demo-seed:
	python scripts/app_demo.py --seed

# Local Ollama demo. The service must already be running and the selected model pulled.
APP_OLLAMA_MODEL ?= qwen2.5:3b
APP_OLLAMA_URL ?= http://127.0.0.1:11434
APP_OLLAMA_TIMEOUT_SECONDS ?= 120
# 1200 s >= 3 personas x 3 attempts x 120 s per request, so retries are not cut off (checked at preflight).
APP_JOB_TIMEOUT_SECONDS ?= 1200
.PHONY: app-demo-ollama
app-demo-ollama: export APP_BACKEND := ollama
app-demo-ollama: export APP_OLLAMA_MODEL := $(APP_OLLAMA_MODEL)
app-demo-ollama: export APP_OLLAMA_URL := $(APP_OLLAMA_URL)
app-demo-ollama: export APP_OLLAMA_TIMEOUT_SECONDS := $(APP_OLLAMA_TIMEOUT_SECONDS)
app-demo-ollama: export APP_JOB_TIMEOUT_SECONDS := $(APP_JOB_TIMEOUT_SECONDS)
app-demo-ollama: export APP_JOB_ISOLATION := process
app-demo-ollama: export APP_DB_PATH := app/var/demo-ollama.sqlite3
app-demo-ollama:
	python -m app.ollama_demo
