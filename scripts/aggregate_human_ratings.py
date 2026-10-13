"""Aggregate completed rater JSON files from scripts/rate_outputs.py into per-condition results.

Reads every results/human_eval/ratings_*.json, joins with the answer key (never shown to raters),
and reports per-condition means for factual accuracy, completeness, readability and persona
suitability, plus inter-rater agreement (quadratic-weighted Cohen's kappa for 2 raters, mean pairwise
kappa for more; "n/a" for 0 or 1 rater). Writes a CSV for the report plus a markdown table.

Example:
    python scripts/aggregate_human_ratings.py
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.human_eval import agreement, condition_ratings_markdown, load_condition_ratings  # noqa: E402
from src.human_eval import RATING_DIMENSIONS, rating_set_paths, summarize_ratings  # noqa: E402
from src.utils import resolve_path, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--glob", default="results/human_eval/ratings_*.json", help="Completed rater files")
    parser.add_argument("--out-dir", default="results/human_eval")
    parser.add_argument("--out", default="report/tables/human_eval_conditions.md")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    pattern = args.glob if Path(args.glob).is_absolute() else str(resolve_path(".") / args.glob)
    paths = sorted(Path(p) for p in glob.glob(pattern))
    _, key_path = rating_set_paths(resolve_path(args.out_dir))
    if not paths:
        log.error("No completed rater files match %s. Run scripts/rate_outputs.py first.", args.glob)
        return 1
    if not key_path.exists():
        log.error("Answer key %s not found. Run scripts/build_rating_set.py first.", key_path)
        return 1
    try:
        ratings, flags = load_condition_ratings(paths, pd.read_csv(key_path, dtype=str))
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    if ratings.empty:
        log.error("The rater file(s) contain no scored ratings yet.")
        return 1
    summary = summarize_ratings(ratings)
    agree = agreement(ratings, RATING_DIMENSIONS)
    n_raters = ratings["rater"].nunique()
    md = condition_ratings_markdown(summary, agree, flags, n_raters)
    out = resolve_path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md + "\n", encoding="utf-8")
    out_dir = resolve_path(args.out_dir)
    summary.to_csv(out_dir / "condition_ratings_summary.csv", index=False)
    if not flags.empty:
        flags.to_csv(out_dir / "condition_ratings_flags.csv", index=False)
    print(md)
    log.info("Wrote %s and %s (%d raters, %d ratings)", out, out_dir / "condition_ratings_summary.csv",
             n_raters, len(ratings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
