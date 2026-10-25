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
# APP_BACKEND=mock (default) needs no model; APP_BACKEND=llama_cpp uses the local GGUF from config.yaml.
.PHONY: app-run app-test

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
