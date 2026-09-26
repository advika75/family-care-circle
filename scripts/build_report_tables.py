"""Build ready-to-paste markdown tables and fill them into report/project_report.md.

Reads results/ablations/summary.csv plus the baseline's metrics.csv and ner_metrics.csv, writes
report/tables/{main,ablations,retention,ner}.md, then replaces the contents between marker comments
(<!-- TABLE:main --> ... <!-- /TABLE:main -->, etc.) in the report. Re-running updates in place.
If report/tables/human_eval.md exists (from aggregate_ratings.py) it is filled in too.

Examples:
    python scripts/build_report_tables.py
    python scripts/build_report_tables.py --ablations-root results/ablations_mock --tables-dir /tmp/t --report /tmp/r.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.report_tables import (  # noqa: E402
    TABLE_NAMES,
    ablation_table,
    fill_marker,
    main_results_table,
    ner_table,
    retention_table,
)
from src.utils import resolve_path, setup_logging  # noqa: E402


def baseline_run_dirs(baseline_root: Path, summary: pd.DataFrame | None, baseline: str) -> list[Path]:
    """Result folders of the baseline: its seeds from summary.csv (seed<k>/), else the single-run folder."""
    if summary is not None and "seeds" in summary:
        row = summary[summary["ablation"] == baseline]
        seeds = str(row.iloc[0]["seeds"]).split() if not row.empty and pd.notna(row.iloc[0]["seeds"]) else []
        dirs = [baseline_root / f"seed{s}" for s in seeds if (baseline_root / f"seed{s}" / "metrics.csv").exists()]
        if dirs:
            return dirs
    return [baseline_root] if (baseline_root / "metrics.csv").exists() else []


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ablations-root", default="results/ablations", help="Folder with summary.csv and <name>/")
    parser.add_argument("--baseline", default="baseline", help="Ablation used for the per-sample tables")
    parser.add_argument("--tables-dir", default="report/tables")
    parser.add_argument("--report", default="report/project_report.md")
    parser.add_argument("--no-fill", action="store_true", help="Only write report/tables/*.md")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    root = resolve_path(args.ablations_root)
    summary_path = root / "summary.csv"
    summary = pd.read_csv(summary_path, dtype={"seeds": str}) if summary_path.exists() else None
    run_dirs = baseline_run_dirs(root / args.baseline, summary, args.baseline)
    if not run_dirs:
        log.error("No metrics.csv for '%s' under %s. Run scripts/run_ablations.py first (or pass --ablations-root).",
                  args.baseline, root)
        return 1
    # Per-note tables pool every seed of the baseline (the seeds listed in summary.csv), else the single run.
    metrics = pd.concat([pd.read_csv(d / "metrics.csv") for d in run_dirs], ignore_index=True)
    baseline_dir = run_dirs[0]
    pooled = f"{metrics['id'].nunique()} notes × {len(run_dirs)} seeds" if len(run_dirs) > 1 else None
    mock = set(metrics["backend"].astype(str)) == {"mock"}
    if mock:
        log.warning("These results come from the MOCK backend; the tables will carry a warning banner.")

    tables = {"main": main_results_table(metrics, mock, pooled), "retention": retention_table(metrics, mock)}
    if summary is not None:
        tables["ablations"] = ablation_table(summary, args.baseline, mock)
    else:
        log.warning("%s not found; skipping the ablation table.", summary_path)
    ner_path = baseline_dir / "ner_metrics.csv"
    if ner_path.exists():
        tables["ner"] = ner_table(pd.read_csv(ner_path))
    else:
        log.warning("%s not found; skipping the NER table.", ner_path)

    tables_dir = resolve_path(args.tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    for name, content in tables.items():
        (tables_dir / f"{name}.md").write_text(content + "\n", encoding="utf-8")
    human_eval = tables_dir / "human_eval.md"
    if human_eval.exists() and "human_eval" not in tables:
        tables["human_eval"] = human_eval.read_text(encoding="utf-8")
    log.info("Wrote %s to %s", ", ".join(f"{n}.md" for n in tables if n != "human_eval"), tables_dir)

    if args.no_fill:
        return 0
    report_path = resolve_path(args.report)
    report = report_path.read_text(encoding="utf-8")
    filled, missing = [], []
    for name in TABLE_NAMES:
        if name not in tables:
            continue
        report, found = fill_marker(report, name, tables[name])
        (filled if found else missing).append(name)
    report_path.write_text(report, encoding="utf-8")
    log.info("Filled %s in %s", ", ".join(filled) or "nothing", report_path)
    if missing:
        log.warning("No <!-- TABLE:x --> markers for: %s (add them to the report to fill these).", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
