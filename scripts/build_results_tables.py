"""Build report-ready tables (CSV + Markdown + LaTeX) and figures from existing result files only.

Covers the synthetic ablations, the real MTSamples generation metrics, and NER (synthetic, and
MTSamples if any gold annotations are marked 'complete'). Every table states its dataset and note
count. A missing result file writes an explicit "not available" table naming what's missing,
instead of fabricating a placeholder number.

Writes:
    results/tables/ablations_synthetic.{csv,md,tex}
    results/tables/generation_mtsamples.{csv,md,tex}       (or "not available" if results/mtsamples/ wasn't run)
    results/tables/ner_synthetic.{csv,md,tex}
    results/tables/ner_mtsamples.{csv,md,tex}              (currently "not available": no completed gold yet)
    results/tables/figures/{entity_retention_by_condition,fallback_rate_by_condition,fkgl_vs_child_target}.png

Example:
    python scripts/build_results_tables.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.results_report import (  # noqa: E402
    ablations_synthetic_table,
    entity_retention_figure,
    fallback_rate_figure,
    fkgl_vs_child_target_figure,
    mtsamples_generation_table,
    mtsamples_ner_status,
    ner_table_for,
    not_available_markdown,
    not_available_table,
    write_table,
)
from src.utils import resolve_path, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ablations-root", default="results/ablations")
    parser.add_argument("--synthetic-ner", default="results/ner_metrics.csv")
    parser.add_argument("--mtsamples-results-dir", default="results/mtsamples")
    parser.add_argument("--mtsamples-ner-results-dir", default="results/mtsamples_ner")
    parser.add_argument("--out-dir", default="results/tables")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    out_dir = resolve_path(args.out_dir)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # --- synthetic ablations ---
    ablations_summary_path = resolve_path(args.ablations_root) / "summary.csv"
    summary = None
    if ablations_summary_path.exists():
        summary = pd.read_csv(ablations_summary_path, dtype={"seeds": str})
        df, md = ablations_synthetic_table(summary)
        write_table(out_dir, "ablations_synthetic", df, md)
        log.info("Wrote ablations_synthetic.{csv,md,tex}")
    else:
        reason = f"{ablations_summary_path} not found. Run scripts/run_ablations.py first."
        write_table(out_dir, "ablations_synthetic", not_available_table(reason),
                    not_available_markdown("Synthetic ablations", reason))
        log.warning("%s -> wrote 'not available'.", reason)

    # --- MTSamples generation metrics ---
    mtsamples_dir = resolve_path(args.mtsamples_results_dir)
    mtsamples_metrics_path = mtsamples_dir / "metrics.csv"
    mtsamples_metrics = None
    if mtsamples_metrics_path.exists():
        mtsamples_metrics = pd.read_csv(mtsamples_metrics_path)
        df, md = mtsamples_generation_table(mtsamples_metrics)
        write_table(out_dir, "generation_mtsamples", df, md)
        log.info("Wrote generation_mtsamples.{csv,md,tex}")
    else:
        reason = (f"{mtsamples_metrics_path} not found. Run scripts/run_pipeline.py --dataset mtsamples and "
                  "scripts/run_evaluation.py --dataset mtsamples first.")
        write_table(out_dir, "generation_mtsamples", not_available_table(reason),
                    not_available_markdown("MTSamples generation metrics", reason))
        log.warning("%s -> wrote 'not available'.", reason)

    # --- NER: synthetic ---
    synthetic_ner_path = resolve_path(args.synthetic_ner)
    if synthetic_ner_path.exists() and len(pd.read_csv(synthetic_ner_path)):
        ner = pd.read_csv(synthetic_ner_path)
        n_docs = int(ner["n_docs"].iloc[0]) if "n_docs" in ner and len(ner) else 0
        df, md = ner_table_for(ner, f"Synthetic ({n_docs} hand-annotated notes)")
        write_table(out_dir, "ner_synthetic", df, md)
        log.info("Wrote ner_synthetic.{csv,md,tex}")
    else:
        reason = f"{synthetic_ner_path} not found or empty. Run scripts/run_evaluation.py first."
        write_table(out_dir, "ner_synthetic", not_available_table(reason),
                    not_available_markdown("Synthetic NER", reason))
        log.warning("%s -> wrote 'not available'.", reason)

    # --- NER: MTSamples (only if gold annotations are actually complete) ---
    mtsamples_ner_dir = resolve_path(args.mtsamples_ner_results_dir)
    mtsamples_ner_summary_path = mtsamples_ner_dir / "mtsamples_ner_summary.json"
    if mtsamples_ner_summary_path.exists():
        ner_summary = json.loads(mtsamples_ner_summary_path.read_text(encoding="utf-8"))
        status = mtsamples_ner_status(ner_summary)
        if status is None:
            ner = pd.read_csv(mtsamples_ner_dir / "mtsamples_ner_metrics.csv")
            df, md = ner_table_for(ner, f"MTSamples ({ner_summary['evaluated_note_count']} completed gold notes)")
        else:
            df, md = status
        write_table(out_dir, "ner_mtsamples", df, md)
        log.info("Wrote ner_mtsamples.{csv,md,tex} (%s)",
                  "available" if status is None else "not available: 0 completed gold annotations")
    else:
        reason = f"{mtsamples_ner_summary_path} not found. Run scripts/evaluate_mtsamples_ner.py first."
        write_table(out_dir, "ner_mtsamples", not_available_table(reason),
                    not_available_markdown("MTSamples NER", reason))
        log.warning("%s -> wrote 'not available'.", reason)

    # --- figures ---
    if summary is not None:
        entity_retention_figure(summary, figures_dir / "entity_retention_by_condition.png")
        fallback_rate_figure(summary, figures_dir / "fallback_rate_by_condition.png")
        log.info("Wrote entity_retention_by_condition.png and fallback_rate_by_condition.png")
    else:
        log.warning("No ablations summary; skipping entity-retention and fallback-rate figures.")
    synthetic_metrics = None
    synthetic_metrics_path = resolve_path("results/metrics.csv")
    if synthetic_metrics_path.exists():
        synthetic_metrics = pd.read_csv(synthetic_metrics_path)
    fkgl_vs_child_target_figure(synthetic_metrics, mtsamples_metrics, figures_dir / "fkgl_vs_child_target.png")
    log.info("Wrote fkgl_vs_child_target.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
