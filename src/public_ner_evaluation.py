"""Exact-span evaluation of rule-based NER against completed MTSamples annotations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.datasets import LABELS, load_annotation
from src.evaluator import match_entities, ner_scores
from src.ner import extract_rule_based


def evaluate_mtsamples(gold_dir: str | Path, notes_dir: str | Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Evaluate only manifest entries whose status is exactly ``complete``.

    Returns JSON-serializable summary, six-label plus micro metric rows, and error rows.
    """
    gold_dir, notes_dir = Path(gold_dir), Path(notes_dir)
    manifest_path = gold_dir / "annotation_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read annotation manifest {manifest_path}: {exc}") from exc
    entries = manifest.get("annotations") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"Invalid annotation manifest {manifest_path}: expected annotations list")

    completed = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "complete"]
    skipped = len(entries) - len(completed)
    docs, errors = [], []
    for entry in completed:
        note_id = entry.get("id")
        if not isinstance(note_id, str) or not note_id:
            raise ValueError(f"Malformed completed manifest entry: missing note id ({manifest_path})")
        source_name = Path(str(entry.get("source_file", ""))).name
        if not source_name:
            raise ValueError(f"Completed note {note_id}: missing source_file in manifest")
        note_path = notes_dir / source_name
        annotation_path = gold_dir / f"{note_id}.json"
        try:
            text = note_path.read_text(encoding="utf-8")
            annotation = load_annotation(annotation_path, note_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Completed note {note_id} has invalid or missing source/gold data: {exc}") from exc
        if annotation["id"] != note_id:
            raise ValueError(f"Completed note {note_id}: annotation id is {annotation['id']!r}")
        gold = annotation["entities"]
        seen_entities = set()
        for entity in gold:
            if entity["start"] < 0 or entity["end"] > len(text):
                raise ValueError(f"Completed note {note_id}: entity offsets are outside source text")
            key = (entity["start"], entity["end"], entity["label"])
            if key in seen_entities:
                raise ValueError(f"Completed note {note_id}: duplicate gold entity span and label {key}")
            seen_entities.add(key)
        predicted = extract_rule_based(text)
        docs.append((note_id, predicted, gold))
        pairs = match_entities(predicted, gold, "exact")
        matched_pred = {id(p) for p, _ in pairs}
        matched_gold = {id(g) for _, g in pairs}
        for kind, items, matched, p_side in (
            ("FP", predicted, matched_pred, True), ("FN", gold, matched_gold, False)
        ):
            for entity in items:
                if id(entity) in matched:
                    continue
                errors.append({
                    "error_type": kind, "note_id": note_id, "label": entity["label"],
                    "predicted_start": entity["start"] if p_side else None,
                    "predicted_end": entity["end"] if p_side else None,
                    "gold_start": None if p_side else entity["start"],
                    "gold_end": None if p_side else entity["end"],
                })

    if docs:
        scored = ner_scores([(pred, gold) for _, pred, gold in docs], "exact")
        metrics = {label: scored.get(label, {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                                               "tp": 0, "fp": 0, "fn": 0}) for label in sorted(LABELS)}
        metrics["MICRO"] = scored["MICRO"]
    else:
        metrics = {label: {"precision": None, "recall": None, "f1": None, "tp": 0, "fp": 0, "fn": 0}
                   for label in sorted(LABELS)}
        metrics["MICRO"] = {"precision": None, "recall": None, "f1": None, "tp": 0, "fp": 0, "fn": 0}
    gold_count = sum(len(gold) for _, _, gold in docs)
    predicted_count = sum(len(pred) for _, pred, _ in docs)
    known_provenance = [entity for _, _, gold in docs for entity in gold
                        if entity.get("annotation_source") in {"accepted_suggestion", "edited_suggestion", "manual"}]
    accepted_suggestions = sum(entity.get("annotation_source") == "accepted_suggestion"
                               for entity in known_provenance)
    summary = {
        "dataset": "MTSamples", "matching": "exact (start, end, label)",
        "ner": "rule-based (extract_rule_based)", "evaluated_note_count": len(docs),
        "skipped_note_count": skipped, "gold_entity_count": gold_count,
        "gold_entities_with_known_provenance": len(known_provenance),
        "gold_entities_with_unknown_provenance": gold_count - len(known_provenance),
        "accepted_suggestion_count": accepted_suggestions,
        "accepted_suggestion_share": (accepted_suggestions / len(known_provenance)
                                      if known_provenance else None),
        "predicted_entity_count": predicted_count, "metrics": metrics,
        "evaluated_note_ids": [note_id for note_id, _, _ in docs],
        "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    metric_rows = [{"label": label, **values, "n_docs": len(docs)} for label, values in metrics.items()]
    return summary, pd.DataFrame(metric_rows), pd.DataFrame(errors, columns=[
        "error_type", "note_id", "label", "predicted_start", "predicted_end", "gold_start", "gold_end"
    ])


def write_results(summary: dict[str, Any], metrics: pd.DataFrame, errors: pd.DataFrame,
                  results_dir: str | Path) -> None:
    """Write aggregate JSON and CSVs to a new directory without replacing prior results."""
    output = Path(results_dir)
    if output.exists():
        raise FileExistsError(f"Refusing to write results into existing directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "mtsamples_ner_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    metrics.to_csv(output / "mtsamples_ner_metrics.csv", index=False)
    errors.to_csv(output / "mtsamples_ner_errors.csv", index=False)
