"""Evaluate rule-based NER against completed MTSamples annotations.

Run from the project root with ``python scripts/evaluate_mtsamples_ner.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.public_ner_evaluation import evaluate_mtsamples, write_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/public/mtsamples/gold")
    parser.add_argument("--notes-dir", default="data/public/mtsamples/notes")
    parser.add_argument("--results-dir", default="results/mtsamples")
    args = parser.parse_args()
    try:
        summary, metrics, errors = evaluate_mtsamples(args.gold_dir, args.notes_dir)
        write_results(summary, metrics, errors, args.results_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Evaluated {summary['evaluated_note_count']} completed note(s); skipped {summary['skipped_note_count']}.")
    if summary["evaluated_note_count"] == 0:
        print("No completed gold annotations; metrics unavailable.")
    else:
        micro = summary["metrics"]["MICRO"]
        print(f"Exact-span micro P/R/F1: {micro['precision']:.3f} / {micro['recall']:.3f} / {micro['f1']:.3f}")
    print(f"Results written to {Path(args.results_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
