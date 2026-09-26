"""Aggregate completed human-evaluation sheets into report/tables/human_eval.md.

Reads every completed sheet matching --glob (one per rater, e.g. results/human_eval/ratings_alice.csv),
joins them with the answer key, and reports mean ± SD per persona and metric, plus inter-rater
agreement (quadratic-weighted Cohen's kappa for 2 raters, mean pairwise kappa for more).

Example:
    python scripts/aggregate_ratings.py
    python scripts/build_report_tables.py        # copies the table into the report
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.human_eval import agreement, load_ratings, ratings_markdown, summarize_ratings  # noqa: E402
from src.utils import resolve_path, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--glob", default="results/human_eval/ratings_*.csv", help="Completed rating sheets")
    parser.add_argument("--key", default="results/human_eval/answer_key.csv")
    parser.add_argument("--out", default="report/tables/human_eval.md")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    pattern = args.glob if Path(args.glob).is_absolute() else str(resolve_path(".") / args.glob)
    paths = sorted(Path(p) for p in glob.glob(pattern))
    key_path = resolve_path(args.key)
    if not paths:
        log.error("No completed sheets match %s.", args.glob)
        return 1
    if not key_path.exists():
        log.error("Answer key %s not found.", key_path)
        return 1
    try:
        ratings, concerns = load_ratings(paths, pd.read_csv(key_path, dtype=str))
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    if ratings.empty:
        log.error("The sheets contain no ratings yet.")
        return 1
    summary = summarize_ratings(ratings)
    agree = agreement(ratings)
    md = ratings_markdown(summary, agree, concerns, ratings["rater"].nunique())
    out = resolve_path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md + "\n", encoding="utf-8")
    summary.to_csv(key_path.parent / "ratings_summary.csv", index=False)
    if not concerns.empty:
        concerns.to_csv(key_path.parent / "safety_concerns.csv", index=False)
    print(md)
    log.info("Wrote %s (%d raters, %d ratings)", out, ratings["rater"].nunique(), len(ratings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
