"""Ablation runs: config overrides, resumable execution, runtime estimates and cross-run summary."""

from __future__ import annotations

import copy
import gc
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.evaluator import RETENTION_LABELS, RETENTION_PERSONAS
from src.generator import Generator, build_generator
from src.ner import EntityExtractor
from src.pipeline import FamilyCarePipeline
from src.plotting import CATEGORICAL, INK_MUTED, MAX_SERIES, grouped_bars, new_figure, save_figure, style_axes
from src.prompts import PERSONAS
from src.reporting import PRETTY, evaluate_outputs
from src.utils import resolve_path, write_json

logger = logging.getLogger(__name__)

FINGERPRINT_FILE = "ablation_config.yaml"   # not .json, so the evaluator does not read it as an output
RUN_INFO_FILE = "run_info.json"
DEFAULT_SECONDS_PER_NOTE = {"mock": 0.05, "llama_cpp": 70.0, "transformers": 120.0}
_NOT_FINGERPRINTED = ("paths", "logging", "ablations")
_SHORT = {"patient_summary": "patient", "caregiver_checklist": "caregiver"}


# --------------------------------------------------------------------------- config

def set_by_path(config: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set ``config["a"]["b"] = value`` for ``"a.b"``. Every key on the path must already exist."""
    node = config
    parts = dotted_key.split(".")
    for i, part in enumerate(parts):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"Unknown config key '{dotted_key}' (no '{'.'.join(parts[:i + 1])}' in config.yaml)")
        if i == len(parts) - 1:
            node[part] = value
        else:
            node = node[part]


def build_ablation_config(
    base: dict[str, Any], overrides: dict[str, Any] | None, backend: str | None = None, mock: bool = False,
    seed: int | None = None,
) -> dict[str, Any]:
    """Deep-copy ``base``, set the backend, apply dotted ``overrides``; ``mock`` forces the mock backend.

    ``seed`` (multi-seed runs) sets ``generation.seed`` after the overrides.
    """
    config = copy.deepcopy(base)
    config.pop("ablations", None)
    if backend:
        config["backend"] = backend
    for key, value in (overrides or {}).items():
        set_by_path(config, key, value)
    if mock:
        config["backend"] = "mock"
    if seed is not None:
        config.setdefault("generation", {})["seed"] = int(seed)
    return config


def shadowed_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> list[str]:
    """Persona-level settings that would silently win over a ``generation.*`` override.

    E.g. overriding ``generation.temperature`` has no effect on a persona that sets its own
    ``temperature`` unless the ablation also overrides ``personas.<persona>.temperature``.
    """
    shadowed = []
    for key in overrides:
        if not key.startswith("generation."):
            continue
        param = key.split(".", 1)[1]
        for persona, pcfg in (config.get("personas") or {}).items():
            persona_key = f"personas.{persona}.{param}"
            if param in (pcfg or {}) and persona_key not in overrides:
                shadowed.append(persona_key)
    return shadowed


def model_key(config: dict[str, Any]) -> str:
    """The model actually used by the configured backend."""
    backend = config.get("backend")
    if backend == "llama_cpp":
        return str(config.get("gguf_path"))
    if backend == "mock":
        return "mock"
    return str(config.get("model_id"))


def fingerprint(config: dict[str, Any]) -> dict[str, Any]:
    """Everything that affects generated outputs (paths/logging excluded; unused backend settings dropped)."""
    fp = {k: v for k, v in config.items() if k not in _NOT_FINGERPRINTED}
    backend = config.get("backend")
    unused = {"transformers": ("gguf_path", "llama_cpp", "mock"),
              "llama_cpp": ("model_id", "transformers", "mock"),
              "mock": ("model_id", "gguf_path", "transformers", "llama_cpp")}.get(backend, ())
    for key in unused:
        fp.pop(key, None)
    return json.loads(json.dumps(fp))  # normalize (e.g. tuples -> lists) so comparisons are stable


# --------------------------------------------------------------------------- paths & resume

def ablation_dirs(name: str, mock: bool = False, seed: int | None = None,
                  dataset: str = "synthetic", run_tag: str | None = None) -> tuple[Path, Path]:
    """(outputs_dir, results_dir) for an ablation run. Mock runs never share folders with real runs.

    Without a seed: data/outputs_<name>/ and results/ablations/<name>/ (single-seed layout).
    With a seed: data/outputs_<name>_seed<k>/ and results/ablations/<name>/seed<k>/.
    """
    prefix = "outputs_mock_" if mock else "outputs_"
    suffix = f"_seed{seed}" if seed is not None else ""
    if dataset == "mtsamples":
        if run_tag is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_tag):
            raise ValueError("MTSamples run tag must contain only letters, numbers, underscores, or hyphens")
        run_name = "no_injection" if name == "no_ner_injection" else name
        if run_tag:
            run_name = f"{run_name}_{run_tag}"
        outputs = resolve_path(f"data/public/mtsamples/{prefix}{run_name}{suffix}")
        results = resolve_path(f"results/mtsamples/{run_name}")
    elif dataset == "synthetic":
        outputs = resolve_path(f"data/{prefix}{name}{suffix}")
        results = ablations_root(mock) / name
    else:
        raise ValueError(f"Unsupported ablation dataset: {dataset}")
    return outputs, (results / f"seed{seed}" if seed is not None else results)


def ablations_root(mock: bool = False, dataset: str = "synthetic", run_tag: str | None = None) -> Path:
    """Folder that holds per-ablation results plus the cross-ablation summary."""
    if dataset == "mtsamples":
        if run_tag is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_tag):
            raise ValueError("MTSamples run tag must contain only letters, numbers, underscores, or hyphens")
        suffix = f"_{run_tag}" if run_tag else ""
        return resolve_path(f"results/mtsamples/ablation_summary{suffix}")
    return resolve_path("results/ablations_mock" if mock else "results/ablations")


def fingerprint_state(outputs_dir: Path, fp: dict[str, Any]) -> str:
    """'new' (no outputs yet), 'match' (same config) or 'mismatch' (outputs made with another config)."""
    path = outputs_dir / FINGERPRINT_FILE
    has_outputs = outputs_dir.exists() and any(outputs_dir.glob("*.json"))
    if not path.exists():
        return "mismatch" if has_outputs else "new"
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    return "match" if saved == fp else "mismatch"


def pending_notes(notes: list[Path], outputs_dir: Path) -> list[Path]:
    """Notes that do not have an output JSON yet."""
    return [n for n in notes if not (outputs_dir / f"{n.stem}.json").exists()]


def estimate_seconds_per_note(config: dict[str, Any], search_root: str | Path = "data") -> tuple[float, str]:
    """Mean per-note latency from earlier outputs of the same backend and model, else a default guess."""
    backend, key = config.get("backend"), model_key(config)
    latencies = []
    for path in resolve_path(search_root).glob("outputs*/*.json"):
        try:
            meta = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if meta.get("backend") == backend and str(meta.get("model_id")) == key:
            total = meta.get("latency_sec", {}).get("total")
            if isinstance(total, (int, float)):
                latencies.append(float(total))
    if latencies:
        return sum(latencies) / len(latencies), f"measured on {len(latencies)} earlier notes"
    return DEFAULT_SECONDS_PER_NOTE.get(backend, 120.0), "default guess (no earlier runs of this model)"


# --------------------------------------------------------------------------- running

class GeneratorCache:
    """Keeps one loaded model and reuses it while consecutive ablations use the same backend + model."""

    def __init__(self) -> None:
        self._key: str | None = None
        self._generator: Generator | None = None

    def get(self, config: dict[str, Any]) -> Generator:
        """Return a generator for ``config``, reusing the loaded model when possible."""
        if config.get("backend") == "mock":
            return build_generator(config)  # cheap, and keeps per-run mock state fresh
        backend = config["backend"]
        key = json.dumps([backend, model_key(config), config.get(backend, {})], sort_keys=True, default=str)
        if key != self._key or self._generator is None:
            self.release()
            self._generator = build_generator(config)
            self._key = key
        else:
            logger.info("Reusing loaded model %s", model_key(config))
            self._generator.configure(config.get("generation", {}))
        return self._generator

    def release(self) -> None:
        """Drop the loaded model and free accelerator memory."""
        self._generator, self._key = None, None
        gc.collect()
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001 - freeing memory is best effort
            pass


def run_ablation(
    name: str,
    config: dict[str, Any],
    overrides: dict[str, Any],
    notes: list[Path],
    outputs_dir: Path,
    results_dir: Path,
    cache: GeneratorCache,
    force: bool = False,
    run_tag: str | None = None,
) -> dict[str, Any]:
    """Generate outputs for the pending notes (all with ``force``), then evaluate. Returns run info.

    Failures are recorded in the returned info (``status="failed"``) instead of raised, so the
    remaining ablations still run. Outputs written before a failure are kept for resuming.
    """
    t0 = time.perf_counter()
    info: dict[str, Any] = {
        "name": name, "overrides": overrides, "backend": config["backend"], "model": model_key(config),
        "dataset": config.get("dataset", "synthetic"), "source_note_ids": [note.stem for note in notes],
        "run_tag": run_tag,
        "effective_config": fingerprint(config),
        "generation_seed": config.get("generation", {}).get("seed"),
        "inject_entities": config.get("prompts", {}).get("inject_entities", True),
        "child_variant": config.get("prompts", {}).get("child_variant", "v2"),
        "notes_total": len(notes), "notes_generated": 0, "status": "ok", "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    outputs_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for old in outputs_dir.glob("*.json"):
            old.unlink()
    (outputs_dir / FINGERPRINT_FILE).write_text(yaml.safe_dump(fingerprint(config), sort_keys=True), encoding="utf-8")

    todo = pending_notes(notes, outputs_dir)
    info["notes_skipped"] = len(notes) - len(todo)
    try:
        if todo:
            pipeline = FamilyCarePipeline(config, generator=cache.get(config))
            for i, note in enumerate(todo, 1):
                record = pipeline.run_file(note)
                write_json(record, outputs_dir / f"{note.stem}.json")
                info["notes_generated"] += 1
                logger.info("[%s] %d/%d %s (%.1fs)", name, i, len(todo), note.stem, record["metadata"]["latency_sec"]["total"])
        info["generation_sec"] = round(time.perf_counter() - t0, 1)
        evaluation = evaluate_outputs(
            outputs_dir, results_dir, config, extract_fn=EntityExtractor(config.get("ner", {})).extract,
            overwrite_results=True,
        )
        if isinstance(evaluation, dict):
            info["unparseable_outputs"] = evaluation.get("unparseable_outputs", 0)
    except Exception as exc:  # noqa: BLE001 - one broken ablation must not stop the others
        logger.exception("Ablation '%s' failed", name)
        info.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    model_hashes = set()
    for output_path in outputs_dir.glob("*.json"):
        try:
            model_hash = json.loads(output_path.read_text(encoding="utf-8")).get("metadata", {}).get("model_hash")
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if model_hash:
            model_hashes.add(model_hash)
    info["model_hashes"] = sorted(model_hashes)
    info["runtime_sec"] = round(time.perf_counter() - t0, 1)
    write_json(info, results_dir / RUN_INFO_FILE)
    return info


# --------------------------------------------------------------------------- summary

def _mean(df: pd.DataFrame, column: str) -> float:
    return float(df[column].mean()) if column in df else float("nan")


def metrics_row(m: pd.DataFrame) -> dict[str, float]:
    """Headline metrics for one run (one ablation, one seed): means over its notes."""
    row: dict[str, float] = {"n_notes": float(len(m))}
    for p in PERSONAS:
        row[f"fkgl_delta_{p}"] = _mean(m, f"{p}_fkgl_delta")
        row[f"rouge1_{p}"] = _mean(m, f"{p}_rouge1")
        row[f"rougeL_{p}"] = _mean(m, f"{p}_rougeL")
    for p in RETENTION_PERSONAS:
        s = _SHORT[p]
        for lbl in RETENTION_LABELS:
            row[f"retention_{s}_{lbl.lower()}"] = _mean(m, f"{p}_retention_model_{lbl.lower()}")
        row[f"retention_{s}_overall"] = _mean(m, f"{p}_retention_model")
        row[f"retention_{s}_first_attempt"] = _mean(m, f"{p}_retention_first")
        row[f"retention_{s}_final_with_fallback"] = _mean(m, f"{p}_retention")
    for p in PERSONAS:
        for kind in ("numbers", "meds"):
            row[f"unsupported_{kind}_{p}"] = _mean(m, f"{p}_unsupported_{kind}")
            row[f"unsupported_{kind}_rate_{p}"] = _mean(m, f"{p}_unsupported_{kind}_rate")
        row[f"truncation_rate_{p}"] = _mean(m, f"{p}_truncation_rate")
        row[f"fallback_rate_{p}"] = _mean(m, f"{p}_fallback")
    per_persona = [row[f"fallback_rate_{p}"] for p in PERSONAS if row[f"fallback_rate_{p}"] == row[f"fallback_rate_{p}"]]
    # Share of all persona outputs (3 per note) that needed the fallback.
    row["fallback_rate"] = sum(per_persona) / len(per_persona) if per_persona else float("nan")
    for p in PERSONAS:
        row[f"repetition_rate_{p}"] = _mean(m, f"{p}_repetition")
    reps = [row[f"repetition_rate_{p}"] for p in PERSONAS if row[f"repetition_rate_{p}"] == row[f"repetition_rate_{p}"]]
    # Share of all persona outputs (3 per note) that repeat a bullet or sentence.
    row["repetition_rate"] = sum(reps) / len(reps) if reps else float("nan")
    for key in ("long_sentence_rate", "med_names", "numbers"):
        row[f"child_{key}"] = _mean(m, f"child_explanation_{key}")
    row["json_validity_rate"] = float(m["valid"].astype(float).mean())
    row["mean_retries"] = _mean(m, "total_retries")
    row["mean_fallbacks"] = _mean(m, "fallbacks")
    row["mean_latency_sec"] = _mean(m, "latency_total_sec")
    return row


def summarize_ablations(
    names: list[str], mock: bool = False, seeds: list[int] | None = None, dataset: str = "synthetic",
    run_tag: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summaries across ablations: (one row per ablation, one row per ablation and seed).

    With ``seeds``, each metric column holds the mean across seeds and ``<metric>_std`` the sample
    standard deviation (NaN with a single seed). Without seeds, the single-run layout is read.
    """
    seed_list: list[int | None] = list(seeds) if seeds else [None]
    per_seed, rows = [], []
    for name in names:
        runs = []
        for seed in seed_list:
            _, results_dir = ablation_dirs(name, mock, seed, dataset, run_tag)
            info_path, metrics_path = results_dir / RUN_INFO_FILE, results_dir / "metrics.csv"
            info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
            run = {"ablation": name, "seed": seed, "status": info.get("status", "missing"),
                   "backend": info.get("backend"), "model": info.get("model"), "runtime_sec": info.get("runtime_sec")}
            if metrics_path.exists():
                run.update(metrics_row(pd.read_csv(metrics_path)))
            runs.append(run)
        per_seed += runs
        done = [r for r in runs if "n_notes" in r]
        row: dict[str, Any] = {
            "ablation": name,
            "status": "ok" if all(r["status"] == "ok" for r in runs) else
                      ("missing" if not done else f"partial ({len(done)}/{len(runs)} seeds)"),
            "backend": next((r["backend"] for r in runs if r["backend"]), None),
            "model": next((r["model"] for r in runs if r["model"]), None),
            "n_seeds": len(done),
            "seeds": " ".join(str(r["seed"]) for r in done if r["seed"] is not None),
            "runtime_sec": sum(r["runtime_sec"] or 0 for r in runs) or None,
        }
        if done:
            frame = pd.DataFrame(done).drop(columns=["ablation", "seed", "status", "backend", "model", "runtime_sec"])
            for col in frame.columns:
                row[col] = float(frame[col].mean())
                row[f"{col}_std"] = float(frame[col].std(ddof=1)) if len(frame) > 1 else float("nan")
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(per_seed)


def _errors(df: pd.DataFrame, names: list[str], cols: list[str], scale: float = 1.0) -> dict[str, list[float]] | None:
    """Per-series std values for error bars, or None when there is no across-seed spread to show."""
    if not all(f"{c}_std" in df for c in cols):
        return None
    errors = {n: [df.loc[n, f"{c}_std"] * scale for c in cols] for n in names}
    return errors if any(v == v and v > 0 for vals in errors.values() for v in vals) else None


def plot_ablation_summary(summary: pd.DataFrame, figures_dir: Path) -> list[Path]:
    """Grouped bar charts comparing ablations (error bars = std across seeds). Returns the written paths."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    if "n_notes" not in summary:
        return []
    df = summary[summary["n_notes"].notna()]  # ablations that produced metrics
    if df.empty:
        return []
    names = list(df["ablation"])[:MAX_SERIES]
    df = df.set_index("ablation").loc[names]
    n_seeds = int(df["n_seeds"].max()) if "n_seeds" in df else 1
    caption = f"Mean across {n_seeds} seeds; error bars = std across seeds" if n_seeds > 1 else None
    personas = [PRETTY[p] for p in PERSONAS]
    written = []

    cols = [f"fkgl_delta_{p}" for p in PERSONAS]
    fig, (ax,) = new_figure(1, width_per_panel=8)
    style_axes(ax, "Grade-level change vs source (lower = simpler)", "Δ Flesch-Kincaid grade")
    grouped_bars(ax, personas, {n: [df.loc[n, c] for c in cols] for n in names}, fmt="{:.1f}",
                 errors=_errors(df, names, cols))
    written.append(figures_dir / "readability_delta.png")
    save_figure(fig, written[-1], caption)

    fig, axes = new_figure(2, width_per_panel=6)
    for ax, metric, title in zip(axes, ("rouge1", "rougeL"), ("ROUGE-1 vs source", "ROUGE-L vs source")):
        cols = [f"{metric}_{p}" for p in PERSONAS]
        style_axes(ax, title, "F1")
        grouped_bars(ax, personas, {n: [df.loc[n, c] for c in cols] for n in names}, errors=_errors(df, names, cols))
        ax.set_ylim(0, 1)
    written.append(figures_dir / "rouge.png")
    save_figure(fig, written[-1], caption)

    categories = [*(lbl.title() for lbl in RETENTION_LABELS), "Overall", "1st try"]
    fig, axes = new_figure(2, width_per_panel=7)
    for ax, p in zip(axes, RETENTION_PERSONAS):
        s = _SHORT[p]
        cols = [*(f"retention_{s}_{lbl.lower()}" for lbl in RETENTION_LABELS), f"retention_{s}_overall",
                f"retention_{s}_first_attempt"]
        style_axes(ax, f"{PRETTY[p]}: entity retention (%)", "Retention (%)")
        grouped_bars(ax, categories, {n: [df.loc[n, c] * 100 for c in cols] for n in names}, fmt="{:.0f}",
                     errors=_errors(df, names, cols, 100))
        ax.set_ylim(0, 110)
    written.append(figures_dir / "retention.png")
    save_figure(fig, written[-1], "Retention of the model's own text: after retries, before the fallback; "
                                  "'1st try' = first attempt only" + (f". {caption}" if caption else ""))

    fig, axes = new_figure(4, width_per_panel=3.8)
    for ax, (col, title, ylabel, scale) in zip(axes, [
        ("json_validity_rate", "JSON validity", "%", 100),
        ("fallback_rate", "Fallback rate", "% of outputs", 100),
        ("mean_retries", "Retries per note", "count", 1),
        ("mean_latency_sec", "Latency per note", "seconds", 1),
    ]):
        values = [df.loc[n, col] * scale for n in names]
        err = _errors(df, names, [col], scale)
        yerr = [err[n][0] for n in names] if err else None
        bars = ax.bar(range(len(names)), values, color=CATEGORICAL[:len(names)], width=0.7, yerr=yerr,
                      error_kw={"ecolor": INK_MUTED, "elinewidth": 1, "capsize": 3})
        ax.bar_label(bars, labels=[f"{v:.1f}" if abs(v) >= 1 or v == 0 else f"{v:.2g}" for v in values],
                     padding=3, fontsize=8)
        ax.set_xticks(range(len(names)), names, rotation=30, ha="right")
        style_axes(ax, title, ylabel)
        ax.margins(y=0.15)
    written.append(figures_dir / "reliability.png")
    save_figure(fig, written[-1], caption)
    return written
