"""Find failure cases in pipeline outputs; write results/error_analysis.md and .json.

Categories: missing entity in the final output, fallback used, invalid format or retries used up,
unsupported number/medication, child explanation above a maximum reading grade, empty/short output.

Examples:
    python scripts/error_analysis.py                                     # data/outputs_baseline_seed0
    python scripts/error_analysis.py --outputs-dir data/outputs_qwen3b --max-child-grade 3
    python scripts/error_analysis.py --outputs-dir data/outputs_mock_baseline --results-dir /tmp/ea
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.error_analysis import CATEGORIES, analyze, to_markdown  # noqa: E402
from src.reporting import load_records  # noqa: E402
from src.utils import resolve_path, setup_logging, write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outputs-dir", default="data/outputs_baseline_seed0",
                        help="Pipeline outputs to analyze (default: seed 0 of the baseline ablation)")
    parser.add_argument("--results-dir", default="results", help="Where to write error_analysis.md/.json")
    parser.add_argument("--max-child-grade", type=float, default=3.0, help="Max Flesch-Kincaid grade for the child text")
    parser.add_argument("--min-words", type=int, default=20, help="Outputs with fewer words count as too short")
    parser.add_argument("--max-examples", type=int, default=3, help="Examples per category in the markdown")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    outputs_dir = resolve_path(args.outputs_dir)
    if not outputs_dir.is_dir():
        log.error("%s does not exist. Run the ablations first, or pass --outputs-dir "
                  "(e.g. data/outputs_mock_baseline after `run_ablations.py --mock`).", outputs_dir)
        return 1
    records, broken = load_records(outputs_dir)
    if not records:
        log.error("No output JSON files in %s.", outputs_dir)
        return 1
    result = analyze(records, args.max_child_grade, args.min_words, args.max_examples)
    result["unparseable_files"] = broken
    result["outputs_dir"] = args.outputs_dir

    results_dir = resolve_path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    md = to_markdown(result, args.outputs_dir)
    if broken:
        md = md.replace("\n| Category", f"\n{broken} output file(s) could not be parsed as JSON.\n\n| Category", 1)
    (results_dir / "error_analysis.md").write_text(md + "\n", encoding="utf-8")
    write_json(result, results_dir / "error_analysis.json")

    width = max(map(len, CATEGORIES))
    for c in CATEGORIES:
        print(f"{c:<{width}}  {result['counts'][c]:>4} failures  {result['notes_affected'][c]:>3}/{result['n_records']} notes")
    log.info("Wrote %s and %s", results_dir / "error_analysis.md", results_dir / "error_analysis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
