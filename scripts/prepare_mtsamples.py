"""Prepare a small local subset from a separately obtained MTSamples CSV.

Example: python scripts/prepare_mtsamples.py --input data/public/mtsamples/source.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.datasets import prepare_mtsamples  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/public/mtsamples/source.csv", help="User-provided CSV")
    parser.add_argument("--output-dir", default="data/public/mtsamples/notes")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    files = prepare_mtsamples(args.input, args.output_dir, args.limit, args.seed)
    print(f"Prepared {len(files)} notes in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
