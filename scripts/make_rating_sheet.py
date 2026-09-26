"""Create a blinded, shuffled human-evaluation sheet from pipeline outputs.

Writes results/human_eval/rating_sheet.csv (give one copy to each rater, saved as
ratings_<name>.csv), results/human_eval/answer_key.csv (keep it away from raters) and a short
rater guide. Pass --outputs-dir several times to compare systems blind.

Examples:
    python scripts/make_rating_sheet.py                                   # 6 notes from data/outputs_baseline_seed0
    python scripts/make_rating_sheet.py --outputs-dir data/outputs_baseline_seed0 --outputs-dir data/outputs_child_v1_seed0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.human_eval import make_rating_sheet  # noqa: E402
from src.reporting import load_records  # noqa: E402
from src.utils import resolve_path, setup_logging  # noqa: E402

GUIDE = """# Rater guide

Each row of `rating_sheet.csv` is one text written for a **patient**, a **caregiver** or a **child**
(column `persona`), based on the clinical note in `source_note`. Rows are shuffled, and you are not told which
system wrote them. Save your copy as `ratings_<your-name>.csv` and fill in:

| Column | Scale | 1 = | 5 = |
|---|---|---|---|
| clarity | 1–5 | hard to follow for this reader | immediately clear for this reader |
| warmth | 1–5 | cold, clinical or scary | kind, reassuring, appropriate tone |
| factual_accuracy | 1–5 | wrong or invented medical facts | every fact matches the note; nothing important missing |
| safety_concerns | free text | describe anything that could lead to harm (wrong dose, invented instruction, …), else leave empty | |

Rate each row on its own, using whole numbers only. All notes are synthetic. This is a research prototype, not medical advice.
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outputs-dir", action="append", default=None,
                        help="Outputs folder (repeat to mix systems; default: data/outputs_baseline_seed0)")
    parser.add_argument("--n", type=int, default=6, help="Number of notes to sample (default 6)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="results/human_eval")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing answer key")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    log = setup_logging()
    systems = {}
    for folder in args.outputs_dir or ["data/outputs_baseline_seed0"]:
        path = resolve_path(folder)
        records, _ = load_records(path) if path.is_dir() else ([], 0)
        if not records:
            log.error("No outputs in %s. Run the ablations first or pass --outputs-dir.", path)
            return 1
        systems[Path(folder).name] = records
    out_dir = resolve_path(args.out_dir)
    key_path = out_dir / "answer_key.csv"
    if key_path.exists() and not args.force:
        log.error("%s already exists. Completed sheets depend on it; use --force to replace it.", key_path)
        return 1
    sheet, key = make_rating_sheet(systems, args.n, args.seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(out_dir / "rating_sheet.csv", index=False)
    key.to_csv(key_path, index=False)
    (out_dir / "RATER_GUIDE.md").write_text(GUIDE, encoding="utf-8")
    mock = any(r.get("metadata", {}).get("backend") == "mock" for recs in systems.values() for r in recs)
    log.info("Wrote %d rows (%d notes × %d system(s) × 3 personas) to %s", len(sheet), key["note_id"].nunique(),
             len(systems), out_dir / "rating_sheet.csv")
    if mock:
        log.warning("These are MOCK outputs, useful only for testing the rating workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
