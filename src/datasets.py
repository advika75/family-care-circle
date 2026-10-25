"""Dataset selection and local MTSamples CSV preparation helpers."""

from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from typing import Any

from src.utils import list_files, read_json, resolve_path

LABELS = {"MEDICATION", "DOSAGE", "FREQUENCY", "DURATION", "CONDITION", "SYMPTOM"}


def dataset_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return paths and subset settings for the selected configured dataset."""
    name = config.get("dataset", "synthetic")
    datasets = config.get("datasets", {})
    if not datasets and name == "synthetic":  # backward compatibility for callers with legacy configs
        return dict(config.get("paths", {}))
    if name not in datasets:
        raise ValueError(f"Unknown dataset {name!r}; configured: {', '.join(datasets)}")
    return {**config.get("paths", {}), **datasets[name]}


def select_note_files(path: str | Path, max_notes: int | None = None, seed: int = 42) -> list[Path]:
    """Select a reproducible random subset, returned in deterministic filename order."""
    files = list_files(path)
    if max_notes is not None and max_notes < 0:
        raise ValueError("max_notes must be non-negative")
    if max_notes is not None and len(files) > max_notes:
        files = random.Random(seed).sample(files, max_notes)
    return sorted(files)


def load_annotation(path: str | Path, note_path: str | Path | None = None) -> dict[str, Any]:
    """Load the project's existing span annotation JSON format and validate its spans."""
    annotation = read_json(path)
    if (not isinstance(annotation, dict) or not isinstance(annotation.get("id"), str)
            or not annotation["id"].strip() or not isinstance(annotation.get("entities"), list)):
        raise ValueError(f"Invalid annotation format: {path}; expected id and entities")
    text = resolve_path(note_path).read_text(encoding="utf-8") if note_path else None
    for entity in annotation["entities"]:
        if not isinstance(entity, dict) or entity.get("label") not in LABELS:
            raise ValueError(f"Invalid entity label in {path}")
        start, end, value = entity.get("start"), entity.get("end"), entity.get("text")
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(value, str) or end <= start:
            raise ValueError(f"Invalid entity span in {path}")
        if text is not None and (end > len(text) or text[start:end] != value):
            raise ValueError(f"Entity span does not match note text in {path}")
    return annotation


def prepare_mtsamples(source: str | Path, output_dir: str | Path, limit: int = 100, seed: int = 42) -> list[Path]:
    """Convert a user-provided MTSamples CSV into a stable local .txt subset."""
    source_path, output_path = resolve_path(source), resolve_path(output_dir)
    if not source_path.is_file():
        raise FileNotFoundError(f"CSV not found: {source_path}; obtain it separately and review its terms.")
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV must have a header row")
        fields = {field.strip().lower(): field for field in reader.fieldnames if field and field.strip()}
        text_col = fields.get("transcription")
        if text_col is None:
            raise ValueError("CSV must contain a 'transcription' column")
        id_col = next((fields[k] for k in ("id", "sample_name", "sample_id") if k in fields), None)
        rows = []
        for i, row in enumerate(reader):
            text = row.get(text_col)
            if not isinstance(text, str) or not text.strip():
                continue
            identifier = row.get(id_col) if id_col else None
            identifier = identifier.strip() if isinstance(identifier, str) else ""
            rows.append((identifier or f"row_{i:06d}", text.strip()))
    if limit < 0:
        raise ValueError("limit must be non-negative")
    chosen = sorted(random.Random(seed).sample(rows, min(limit, len(rows))), key=lambda item: item[0])
    if output_path.exists() and any(output_path.iterdir()):
        raise FileExistsError(
            f"Refusing to replace existing MTSamples preparation files in {output_path}; choose an empty output directory"
        )
    output_path.mkdir(parents=True, exist_ok=True)
    written = []
    used_ids: set[str] = set()
    for i, (identifier, text) in enumerate(chosen):
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier).strip("_.-") or f"row_{i:06d}"
        if safe_id in used_ids:
            safe_id = f"{safe_id}_{i:03d}"
        used_ids.add(safe_id)
        target = output_path / f"mtsamples_{safe_id}.txt"
        target.write_text(text.strip() + "\n", encoding="utf-8")
        written.append(target)
    (output_path / "subset.json").write_text(json.dumps({"source": source_path.name, "seed": seed,
        "limit": limit, "ids": [p.stem for p in written]}, indent=2) + "\n", encoding="utf-8")
    return written
