"""Evaluate pipeline outputs and NER, then write metrics, a summary table and figures.

Writes:
    results/metrics.csv           per-sample metrics
    results/summary.csv / .md     aggregated means/stds (+ NER table in the .md)
    results/ner_metrics.csv       NER P/R/F1 vs data/gold (exact and relaxed)
    results/figures/readability_before_after.png
    results/figures/entity_retention.png

Example:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --outputs-dir data/outputs_qwen3b --results-dir results/qwen3b
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ner import EntityExtractor  # noqa: E402
from src.reporting import evaluate_outputs  # noqa: E402
from src.utils import load_config, resolve_path, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--outputs-dir", default=None, help="Pipeline JSON outputs (default: paths.outputs_dir)")
    parser.add_argument("--results-dir", default=None, help="Where to write metrics (default: paths.results_dir)")
    parser.add_argument("--skip-ner", action="store_true", help="Skip NER evaluation against gold")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    config = load_config(args.config)
    log = setup_logging(config.get("logging", {}).get("level", "INFO"))
    paths = config.get("paths", {})
    outputs_dir = resolve_path(args.outputs_dir or paths.get("outputs_dir", "data/outputs"))
    results_dir = resolve_path(args.results_dir or paths.get("results_dir", "results"))
    # An explicit --results-dir keeps its figures alongside it instead of in the configured figures_dir.
    figures_dir = results_dir / "figures" if args.results_dir else resolve_path(paths.get("figures_dir", "results/figures"))
    extract_fn = None if args.skip_ner else EntityExtractor(config.get("ner", {})).extract
    try:
        result = evaluate_outputs(outputs_dir, results_dir, config, figures_dir, extract_fn)
    except FileNotFoundError as exc:
        log.error("%s. Run scripts/run_pipeline.py first.", exc)
        return 1

    backends = ", ".join(sorted(set(map(str, result["metrics"]["backend"]))))
    print(f"\nSamples: {result['n_records']}  backend(s): {backends}")
    print(result["key"].round(3).to_string())
    if result["ner"] is not None:
        table = result["ner"].pivot(index="label", columns="mode", values=["precision", "recall", "f1"])
        print("\nNER (vs gold):")
        print(table.round(3).to_string())
    log.info("Wrote metrics.csv, summary.csv, summary.md%s and figures to %s",
             "" if args.skip_ner else ", ner_metrics.csv", results_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
