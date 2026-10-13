"""Build a blinded rating set for the local rating UI (scripts/rate_outputs.py).

Samples N notes present in both the baseline and no-NER-injection conditions and, per note, every
persona output from each condition. Condition labels are hidden and sample order is randomized.
Writes results/human_eval/rating_set.json (what raters see) and answer_key.csv (kept away from
raters; used only by scripts/aggregate_human_ratings.py).

Example:
    python scripts/build_rating_set.py
    python scripts/build_rating_set.py --outputs-dir data/outputs_baseline_seed0 \
        --outputs-dir data/outputs_no_ner_injection_seed0 --n 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.human_eval import build_condition_rating_set, rating_set_paths  # noqa: E402
from src.reporting import load_records  # noqa: E402
from src.utils import resolve_path, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outputs-dir", action="append", default=None,
                        help="Outputs folder (repeat for each condition; default: baseline and "
                             "no_ner_injection seed0)")
    parser.add_argument("--n", type=int, default=6, help="Number of notes to sample (default 6)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="results/human_eval")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing answer key")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    folders = args.outputs_dir or ["data/outputs_baseline_seed0", "data/outputs_no_ner_injection_seed0"]
    systems = {}
    for folder in folders:
        path = resolve_path(folder)
        records, _ = load_records(path) if path.is_dir() else ([], 0)
        if not records:
            log.error("No outputs in %s. Run scripts/run_pipeline.py or run_ablations.py first.", path)
            return 1
        systems[Path(folder).name] = records
    out_dir = resolve_path(args.out_dir)
    set_path, key_path = rating_set_paths(out_dir)
    if key_path.exists() and not args.force:
        log.error("%s already exists. Completed ratings depend on it; use --force to replace it.", key_path)
        return 1
    try:
        items, key = build_condition_rating_set(systems, args.n, args.seed)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    set_path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    key.to_csv(key_path, index=False)
    mock = any(r.get("metadata", {}).get("backend") == "mock" for recs in systems.values() for r in recs)
    log.info("Wrote %d items (%d notes x %d condition(s) x 3 personas) to %s", len(items),
              key["note_id"].nunique(), len(systems), set_path)
    log.info("Launch the rating UI: python scripts/rate_outputs.py --rater <name>")
    if mock:
        log.warning("These are MOCK outputs, useful only for testing the rating workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
