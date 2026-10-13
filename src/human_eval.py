"""Blinded human-evaluation kit: build rating sheets, then aggregate completed ones."""

from __future__ import annotations

import itertools
import json
import logging
import math
import random
import warnings
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.evaluator import persona_text
from src.prompts import PERSONAS
from src.reporting import PRETTY

logger = logging.getLogger(__name__)

RATING_METRICS = ("clarity", "warmth", "factual_accuracy")
SHEET_COLUMNS = ["sample_id", "persona", "source_note", "text", *RATING_METRICS, "safety_concerns"]
KEY_COLUMNS = ["sample_id", "system", "note_id", "persona"]
SCALE = (1, 2, 3, 4, 5)

# Dimensions for the UI-based condition rating set (build_condition_rating_set / rate_outputs.py), distinct
# from the older clarity/warmth/factual_accuracy CSV sheet above, which make_rating_sheet still serves as-is.
RATING_DIMENSIONS = ("factual_accuracy", "completeness", "readability", "persona_suitability")


def _sample_blinded_items(
    systems: dict[str, list[dict[str, Any]]], n_notes: int, seed: int, personas: Iterable[str] = PERSONAS
) -> tuple[list[tuple[str, str, str]], dict[str, dict[str, dict[str, Any]]]]:
    """Notes present in every system, sampled and shuffled into ``(system, note_id, persona)`` triples.

    Shared by :func:`make_rating_sheet` and :func:`build_condition_rating_set` so both blind and shuffle
    the same way. Also returns ``by_system`` (``{system: {note_id: record}}``) for looking up the text.
    """
    by_system = {name: {r["id"]: r for r in records} for name, records in systems.items()}
    common = sorted(set.intersection(*(set(v) for v in by_system.values()))) if by_system else []
    if not common:
        raise ValueError("No note ids are shared by all systems.")
    rng = random.Random(seed)
    notes = sorted(rng.sample(common, min(n_notes, len(common))))
    items = [(system, note, persona) for system in by_system for note in notes for persona in personas]
    rng.shuffle(items)
    return items, by_system


def make_rating_sheet(
    systems: dict[str, list[dict[str, Any]]], n_notes: int = 6, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sample ``n_notes`` notes present in every system and return (blinded shuffled sheet, answer key).

    ``systems`` maps a system name (e.g. an outputs folder) to its output records. Every sampled note
    contributes one row per system and persona. Sample ids are assigned after shuffling, so they carry
    no information about system, note or order.
    """
    items, by_system = _sample_blinded_items(systems, n_notes, seed)
    sheet_rows, key_rows = [], []
    for i, (system, note, persona) in enumerate(items, 1):
        record = by_system[system][note]
        sample_id = f"S{i:03d}"
        text = persona_text(record, persona)
        if persona == "caregiver_checklist":
            text = "\n".join(f"- {line}" for line in text.splitlines())
        sheet_rows.append({"sample_id": sample_id, "persona": persona, "source_note": record.get("source_text", ""),
                           "text": text, **{m: "" for m in RATING_METRICS}, "safety_concerns": ""})
        key_rows.append({"sample_id": sample_id, "system": system, "note_id": note, "persona": persona})
    return pd.DataFrame(sheet_rows, columns=SHEET_COLUMNS), pd.DataFrame(key_rows, columns=KEY_COLUMNS)


def build_condition_rating_set(
    systems: dict[str, list[dict[str, Any]]], n_notes: int = 6, seed: int = 42
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Blinded items for the local rating UI (``scripts/rate_outputs.py``), plus the answer key.

    Unlike :func:`make_rating_sheet`, items carry no condition/system label at all (not even an empty
    placeholder column for one) — the UI only ever sees ``sample_id``, ``persona``, ``source_note`` and
    ``text``. The answer key (``[sample_id, system, note_id, persona]``) is returned separately and must
    be kept away from raters.
    """
    items, by_system = _sample_blinded_items(systems, n_notes, seed)
    rows, key_rows = [], []
    for i, (system, note, persona) in enumerate(items, 1):
        record = by_system[system][note]
        sample_id = f"S{i:03d}"
        text = persona_text(record, persona)
        if persona == "caregiver_checklist":
            text = "\n".join(f"- {line}" for line in text.splitlines())
        rows.append({"sample_id": sample_id, "persona": persona,
                     "source_note": record.get("source_text", ""), "text": text})
        key_rows.append({"sample_id": sample_id, "system": system, "note_id": note, "persona": persona})
    return rows, pd.DataFrame(key_rows, columns=KEY_COLUMNS)


def rater_name(path: Path) -> str:
    """'ratings_alice.csv' -> 'alice'; otherwise the file stem."""
    stem = path.stem
    return stem[len("ratings_"):] if stem.startswith("ratings_") else stem


def load_ratings(paths: Iterable[Path], key: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read completed sheets into long format ``[rater, sample_id, system, persona, metric, score]``.

    Blank cells are skipped; values outside 1-5 are dropped with a warning. Also returns the
    non-empty safety concerns ``[rater, sample_id, system, persona, safety_concerns]``.
    """
    long_rows, concerns = [], []
    key_idx = key.set_index("sample_id")
    for path in paths:
        rater = rater_name(Path(path))
        sheet = pd.read_csv(path, dtype=str, keep_default_na=False)
        unknown = set(sheet["sample_id"]) - set(key_idx.index)
        if unknown:
            raise ValueError(f"{path}: sample ids not in the answer key: {sorted(unknown)[:5]}")
        dropped = 0
        for _, row in sheet.iterrows():
            info = key_idx.loc[row["sample_id"]]
            for metric in RATING_METRICS:
                raw = str(row.get(metric, "")).strip()
                if not raw:
                    continue
                try:
                    score = float(raw)
                except ValueError:
                    score = math.nan
                if score not in SCALE:
                    dropped += 1
                    continue
                long_rows.append({"rater": rater, "sample_id": row["sample_id"], "system": info["system"],
                                  "persona": info["persona"], "metric": metric, "score": int(score)})
            concern = str(row.get("safety_concerns", "")).strip()
            if concern:
                concerns.append({"rater": rater, "sample_id": row["sample_id"], "system": info["system"],
                                 "persona": info["persona"], "safety_concerns": concern})
        if dropped:
            logger.warning("%s: dropped %d rating(s) outside 1-5 or not numeric.", path, dropped)
    return pd.DataFrame(long_rows), pd.DataFrame(concerns)


def rating_set_paths(out_dir: str | Path) -> tuple[Path, Path]:
    """(rating_set.json, answer_key.csv) paths for a human-eval output directory."""
    out_dir = Path(out_dir)
    return out_dir / "rating_set.json", out_dir / "answer_key.csv"


def rater_json_path(out_dir: str | Path, rater: str) -> Path:
    """Path to one rater's JSON ratings file: ``results/human_eval/ratings_<rater>.json``."""
    return Path(out_dir) / f"ratings_{rater}.json"


def read_rater_ratings(path: str | Path) -> dict[str, dict[str, Any]]:
    """Read one rater's JSON file (``{sample_id: {scores, missing_or_wrong_fact, ...}}``), or ``{}``."""
    path = Path(path)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object keyed by sample_id")
    return data


def write_rater_rating(path: str | Path, sample_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge ``payload`` into one sample's entry in a rater's JSON file and save it (so progress survives
    a restart). Returns the full updated ratings dict."""
    path = Path(path)
    ratings = read_rater_ratings(path)
    ratings[sample_id] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ratings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ratings


def load_condition_ratings(
    paths: Iterable[Path], key: pd.DataFrame, metrics: Iterable[str] = RATING_DIMENSIONS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read completed rater JSON files into long format ``[rater, sample_id, system, persona, metric, score]``.

    Also returns rows with a missing/wrong-fact flag or a non-empty note:
    ``[rater, sample_id, system, persona, flagged, note]``. Missing scores and samples not yet rated by a
    given rater are simply absent, not an error; a score outside 1-5 is dropped with a warning.
    """
    long_rows, flags = [], []
    key_idx = key.set_index("sample_id")
    for path in paths:
        path = Path(path)
        rater = rater_name(path)
        data = read_rater_ratings(path)
        unknown = set(data) - set(key_idx.index)
        if unknown:
            raise ValueError(f"{path}: sample ids not in the answer key: {sorted(unknown)[:5]}")
        dropped = 0
        for sample_id, payload in data.items():
            info = key_idx.loc[sample_id]
            scores = payload.get("scores", {}) if isinstance(payload, dict) else {}
            for metric in metrics:
                if metric not in scores or scores[metric] in (None, ""):
                    continue
                try:
                    score = int(scores[metric])
                except (TypeError, ValueError):
                    score = None
                if score not in SCALE:
                    dropped += 1
                    continue
                long_rows.append({"rater": rater, "sample_id": sample_id, "system": info["system"],
                                  "persona": info["persona"], "metric": metric, "score": score})
            flagged = bool(payload.get("missing_or_wrong_fact")) if isinstance(payload, dict) else False
            note = str(payload.get("missing_or_wrong_fact_note", "")).strip() if isinstance(payload, dict) else ""
            if flagged or note:
                flags.append({"rater": rater, "sample_id": sample_id, "system": info["system"],
                              "persona": info["persona"], "flagged": flagged, "note": note})
        if dropped:
            logger.warning("%s: dropped %d rating(s) outside 1-5 or not numeric.", path, dropped)
    return (pd.DataFrame(long_rows, columns=["rater", "sample_id", "system", "persona", "metric", "score"]),
            pd.DataFrame(flags, columns=["rater", "sample_id", "system", "persona", "flagged", "note"]))


def summarize_ratings(ratings: pd.DataFrame) -> pd.DataFrame:
    """Mean, SD and count per system, persona and metric."""
    grouped = ratings.groupby(["system", "persona", "metric"])["score"]
    return grouped.agg(mean="mean", std="std", n="count").reset_index()


def _kappa(a: list[int], b: list[int]) -> float:
    from sklearn.metrics import cohen_kappa_score

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = cohen_kappa_score(a, b, labels=list(SCALE), weights="quadratic")
    return float(value)


def agreement(ratings: pd.DataFrame, metrics: Iterable[str] = RATING_METRICS) -> pd.DataFrame:
    """Inter-rater agreement per metric: quadratic-weighted Cohen's kappa (2 raters) or mean pairwise kappa.

    Gracefully reports "n/a (needs 2+ raters)" with a NaN kappa for 0 or 1 rater, and NaN for a metric
    with fewer than 2 jointly-rated items, rather than raising.
    """
    rows = []
    raters = sorted(ratings["rater"].unique()) if not ratings.empty else []
    for metric in metrics:
        wide = ratings[ratings["metric"] == metric].pivot_table(index="sample_id", columns="rater", values="score")
        if len(raters) < 2:
            rows.append({"metric": metric, "raters": len(raters), "method": "n/a (needs 2+ raters)",
                         "kappa": math.nan, "items": len(wide)})
            continue
        kappas, items = [], []
        for r1, r2 in itertools.combinations(raters, 2):
            both = wide[[r1, r2]].dropna() if {r1, r2} <= set(wide.columns) else pd.DataFrame()
            if len(both) >= 2:
                k = _kappa(both[r1].astype(int).tolist(), both[r2].astype(int).tolist())
                if k == k:
                    kappas.append(k)
                    items.append(len(both))
        method = ("Cohen's κ (quadratic)" if len(raters) == 2
                  else f"mean pairwise Cohen's κ (quadratic, {len(kappas)} pairs)")
        rows.append({"metric": metric, "raters": len(raters), "method": method,
                     "kappa": sum(kappas) / len(kappas) if kappas else math.nan,
                     "items": min(items) if items else 0})
    return pd.DataFrame(rows)


def ratings_markdown(summary: pd.DataFrame, agree: pd.DataFrame, concerns: pd.DataFrame, n_raters: int) -> str:
    """Markdown tables: ratings per persona (and system, if several) plus agreement."""
    multi = summary["system"].nunique() > 1
    header = [*(["System"] if multi else []), "Persona", "Clarity", "Warmth", "Factual accuracy", "Safety flags"]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for (system, persona), grp in summary.groupby(["system", "persona"], sort=False):
        cells = [system] if multi else []
        cells.append(PRETTY.get(persona, persona))
        for metric in RATING_METRICS:
            r = grp[grp["metric"] == metric]
            if r.empty:
                cells.append("–")
            else:
                m, s, n = r.iloc[0]["mean"], r.iloc[0]["std"], int(r.iloc[0]["n"])
                cells.append(f"{m:.2f} ± {s:.2f} (n={n})" if s == s else f"{m:.2f} (n={n})")
        flags = 0 if concerns.empty else int(((concerns["system"] == system) & (concerns["persona"] == persona)).sum())
        cells.append(str(flags))
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "| Metric | Raters | Agreement | κ | Items |", "|---|---|---|---|---|"]
    for _, r in agree.iterrows():
        kappa = "–" if r["kappa"] != r["kappa"] else f"{r['kappa']:.2f}"
        lines.append(f"| {r['metric']} | {r['raters']} | {r['method']} | {kappa} | {r['items']} |")
    lines += ["", f"_Mean ± SD of 1–5 ratings from {n_raters} rater(s), blinded to system. Safety flags = number of "
                  "non-empty safety-concern comments. κ: quadratic-weighted Cohen's kappa (ordinal scale)._"]
    return "\n".join(lines)


def condition_ratings_markdown(summary: pd.DataFrame, agree: pd.DataFrame, flags: pd.DataFrame, n_raters: int) -> str:
    """Markdown tables for the condition rating set: per-condition means plus agreement and fact-flag counts."""
    header = ["Condition", "Persona", "Factual accuracy", "Completeness", "Readability", "Persona suitability",
              "Missing/wrong-fact flags"]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for (system, persona), grp in summary.groupby(["system", "persona"], sort=False):
        cells = [system, PRETTY.get(persona, persona)]
        for metric in RATING_DIMENSIONS:
            r = grp[grp["metric"] == metric]
            if r.empty:
                cells.append("–")
            else:
                m, s, n = r.iloc[0]["mean"], r.iloc[0]["std"], int(r.iloc[0]["n"])
                cells.append(f"{m:.2f} ± {s:.2f} (n={n})" if s == s else f"{m:.2f} (n={n})")
        n_flags = 0 if flags.empty else int(((flags["system"] == system) & (flags["persona"] == persona)
                                              & flags["flagged"]).sum())
        cells.append(str(n_flags))
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "| Metric | Raters | Agreement | κ | Items |", "|---|---|---|---|---|"]
    for _, r in agree.iterrows():
        kappa = "–" if r["kappa"] != r["kappa"] else f"{r['kappa']:.2f}"
        lines.append(f"| {r['metric']} | {r['raters']} | {r['method']} | {kappa} | {r['items']} |")
    lines += ["", f"_Mean ± SD of 1-5 ratings from {n_raters} rater(s), blinded to condition. "
                  "Missing/wrong-fact flags = number of samples where the rater checked that box. "
                  "κ: quadratic-weighted Cohen's kappa (ordinal scale)._"]
    return "\n".join(lines)
