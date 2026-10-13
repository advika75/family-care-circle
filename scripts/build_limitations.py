"""Build report/limitations.md from measured evidence in the repo's result files.

Gathers real numbers (note counts, gold-annotation counts, hallucination-check failure counts,
child FKGL, human-eval rater count) from whatever result files currently exist, then renders the
fixed-structure limitations draft in src/limitations.py around them. A number that can't be found
is rendered as "an unmeasured number of" rather than a guess.

Example:
    python scripts/build_limitations.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.limitations import LimitationsContext, build_limitations  # noqa: E402
from src.utils import list_files, resolve_path, setup_logging  # noqa: E402


def _safe_mean(path: Path, column: str) -> float | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return float(df[column].mean()) if column in df and len(df) else None


def gather_context() -> LimitationsContext:
    ctx = LimitationsContext()

    raw_dir = resolve_path("data/raw")
    if raw_dir.is_dir():
        ctx.n_synthetic_notes = len(list_files(raw_dir, (".txt",)))
    gold_dir = resolve_path("data/gold")
    if gold_dir.is_dir():
        gold_files = [p for p in list_files(gold_dir, (".json",))]
        ctx.n_synthetic_gold_notes = len(gold_files)
        total_entities = 0
        for p in gold_files:
            try:
                total_entities += len(json.loads(p.read_text(encoding="utf-8")).get("entities", []))
            except (json.JSONDecodeError, OSError):
                pass
        ctx.n_synthetic_gold_entities = total_entities

    mtsamples_metrics = resolve_path("results/mtsamples/metrics.csv")
    if mtsamples_metrics.exists():
        ctx.n_mtsamples_notes = len(pd.read_csv(mtsamples_metrics))
    manifest_path = resolve_path("data/public/mtsamples/gold/annotation_manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest.get("annotations", [])
        ctx.n_mtsamples_gold_total = len(entries)
        ctx.n_mtsamples_gold_complete = sum(1 for e in entries if e.get("status") == "complete")

    # NER-miss examples named in results/mtsamples_summary.md's Fix-2 writeup (facts in the source that the
    # rule-based extractor does not pick up as DOSAGE entities because they are spelled out, not abbreviated).
    ctx.ner_miss_examples = ('"81 milligrams" (mtsamples_Acute_Inferior_Myocardial_Infarction)',
                             '"One mL" (mtsamples_Carpal_Ligament_Release_-_2)')

    error_analysis_path = resolve_path("results/mtsamples/error_analysis.json")
    if error_analysis_path.exists():
        analysis = json.loads(error_analysis_path.read_text(encoding="utf-8"))
        ctx.unsupported_content_failures = analysis.get("counts", {}).get("unsupported_content")
        ctx.unsupported_content_notes_affected = analysis.get("notes_affected", {}).get("unsupported_content")
        ctx.unsupported_content_notes_total = analysis.get("n_records", ctx.n_mtsamples_notes)

    ctx.child_fkgl_synthetic = _safe_mean(resolve_path("results/metrics.csv"), "child_explanation_fkgl")
    ctx.child_fkgl_mtsamples = _safe_mean(mtsamples_metrics, "child_explanation_fkgl")

    human_eval_dir = resolve_path("results/human_eval")
    rater_files = (glob.glob(str(human_eval_dir / "ratings_*.csv")) + glob.glob(str(human_eval_dir / "ratings_*.json")))
    ctx.n_human_eval_raters = len(rater_files)
    rating_set_path = human_eval_dir / "rating_set.json"
    if rating_set_path.exists():
        items = json.loads(rating_set_path.read_text(encoding="utf-8"))
        ids = {item.get("sample_id") for item in items}
        ctx.n_human_eval_samples = len(ids)

    return ctx


def main() -> int:
    """Entry point."""
    log = setup_logging()
    ctx = gather_context()
    out_path = resolve_path("report/limitations.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_limitations(ctx) + "\n", encoding="utf-8")
    log.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
