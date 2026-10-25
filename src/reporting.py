"""Evaluate a folder of pipeline outputs and write metrics, a summary table and figures."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.evaluator import RETENTION_LABELS, RETENTION_PERSONAS, evaluate_ner_against_gold, evaluate_record, summarize
from src.plotting import CATEGORICAL, INK, INK_MUTED, NEUTRAL, SURFACE, grouped_bars, new_figure, save_figure, style_axes
from src.prompts import PERSONAS
from src.utils import list_files, read_json, resolve_path

logger = logging.getLogger(__name__)

PRETTY = {"source": "Source note", "patient_summary": "Patient", "caregiver_checklist": "Caregiver",
          "child_explanation": "Child"}


def load_records(outputs_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Load output JSONs. Returns (records, number of files that failed to parse)."""
    records, broken = [], 0
    for path in list_files(outputs_dir, (".json",)):
        try:
            records.append(read_json(path))
        except (json.JSONDecodeError, UnicodeDecodeError):
            broken += 1
    return records, broken


def markdown_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table (no extra dependency)."""
    df = df.reset_index()
    header = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = []
    for _, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, float) else str(v) for v in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def plot_readability(metrics: pd.DataFrame, path: Path) -> None:
    """Bar chart of mean FKGL and FRE for the source note vs each persona (mean ± SD)."""
    groups = ["source", *PERSONAS]
    fig, axes = new_figure(2, width_per_panel=5)
    for ax, (metric, title, ylabel) in zip(axes, [
        ("fkgl", "Grade level (lower is easier)", "Flesch-Kincaid grade"),
        ("fre", "Reading ease (higher is easier)", "Flesch Reading Ease"),
    ]):
        means = [metrics[f"{g}_{metric}"].mean() for g in groups]
        stds = [metrics[f"{g}_{metric}"].std(ddof=0) for g in groups]
        colors = [NEUTRAL] + [CATEGORICAL[0]] * len(PERSONAS)
        bars = ax.bar([PRETTY[g] for g in groups], means, width=0.6, color=colors, edgecolor=SURFACE, linewidth=2,
                      yerr=stds, error_kw={"ecolor": INK_MUTED, "elinewidth": 1, "capsize": 3})
        for bar, mean, std in zip(bars, means, stds):  # label above the error bar, not on it
            ax.annotate(f"{mean:.1f}", (bar.get_x() + bar.get_width() / 2, mean + std), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom", color=INK, fontsize=9)
        ax.margins(y=0.12)
        style_axes(ax, title, ylabel)
    save_figure(fig, path, "Readability: source note (gray) vs persona outputs (blue); mean ± SD")


def plot_retention(metrics: pd.DataFrame, path: Path) -> None:
    """Per-entity-type retention of the model's own text (after retries, before the fallback)."""
    categories = [*(lbl.title() for lbl in RETENTION_LABELS), "Overall"]
    series = {}
    for persona in RETENTION_PERSONAS:
        cols = [f"{persona}_retention_model_{lbl.lower()}" for lbl in RETENTION_LABELS] + [f"{persona}_retention_model"]
        series[PRETTY[persona]] = [metrics[c].mean() * 100 if c in metrics else float("nan") for c in cols]
    fig, (ax,) = new_figure(1, width_per_panel=8)
    style_axes(ax, "Entity retention before fallback (% of source entities)", "Retention (%)")
    grouped_bars(ax, categories, series, fmt="{:.0f}")
    ax.set_ylim(0, 110)
    save_figure(fig, path)


def evaluate_outputs(
    outputs_dir: str | Path,
    results_dir: str | Path,
    config: dict[str, Any],
    figures_dir: str | Path | None = None,
    extract_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    overwrite_results: bool = False,
) -> dict[str, Any]:
    """Evaluate every output JSON in ``outputs_dir``; write CSVs, summary.md and figures.

    ``extract_fn`` enables NER-vs-gold scoring (pass ``EntityExtractor(...).extract``); ``None`` skips it.
    Returns ``{"metrics", "summary", "key", "ner", "n_records"}``.
    """
    outputs_dir, results_dir = resolve_path(outputs_dir), resolve_path(results_dir)
    figures_dir = resolve_path(figures_dir) if figures_dir else results_dir / "figures"
    targets = [results_dir / "metrics.csv", results_dir / "summary.csv", results_dir / "summary.md",
               figures_dir / "readability_before_after.png", figures_dir / "entity_retention.png"]
    if extract_fn is not None:
        targets.append(results_dir / "ner_metrics.csv")
    collisions = [path for path in targets if path.exists()]
    if collisions and not overwrite_results:
        raise FileExistsError(f"Refusing to replace existing evaluation results: {', '.join(map(str, collisions))}; "
                              "choose a new --results-dir or pass --force")
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    records, broken = load_records(outputs_dir)
    if not records:
        raise FileNotFoundError(f"No output JSON files in {outputs_dir}")
    metrics = pd.DataFrame([evaluate_record(r) for r in records])
    metrics.to_csv(results_dir / "metrics.csv", index=False)

    summary = summarize(metrics)
    summary.loc["json_parse_rate"] = [len(records) / (len(records) + broken), float("nan")]
    summary.to_csv(results_dir / "summary.csv")

    key_rows = [
        "source_fkgl", *[f"{p}_fkgl" for p in PERSONAS], *[f"{p}_fkgl_delta" for p in PERSONAS],
        "source_fre", *[f"{p}_fre" for p in PERSONAS], *[f"{p}_rouge1" for p in PERSONAS],
        *[f"{p}_rougeL" for p in PERSONAS],
        *[f"{p}_retention{s}" for s in ("_first", "_model", "") for p in RETENTION_PERSONAS],
        *[f"{p}_retention_first_evidence_available" for p in RETENTION_PERSONAS],
        *[f"{p}_unsupported_{k}" for k in ("numbers", "meds") for p in PERSONAS],
        *[f"{p}_truncation_rate" for p in PERSONAS], *[f"{p}_fallback" for p in PERSONAS],
        *[f"{p}_retries" for p in PERSONAS], *[f"{p}_latency_sec" for p in PERSONAS],
        *[f"{p}_repetition" for p in PERSONAS],
        "child_explanation_long_sentence_rate", "child_explanation_med_names", "child_explanation_numbers",
        "format_validity_rate", "json_parse_rate", "total_retries", "fallbacks", "latency_total_sec",
    ]
    key = summary.loc[[r for r in key_rows if r in summary.index]]
    backends = ", ".join(sorted(set(map(str, metrics["backend"]))))
    lines = [
        f"# Evaluation summary\n\nSamples: {len(records)} | backend(s): {backends}\n",
        "Retention: `_first` = first attempt, `_model` = after retries but before the fallback, "
        "no suffix = final text (includes the fallback, so it is 100% by construction when a fallback was used).\n",
        "## Generation metrics (mean ± std over samples)\n", markdown_table(key),
    ]

    ner = None
    if extract_fn is not None:
        from src.datasets import dataset_config
        paths = dataset_config(config)
        gold_dir = resolve_path(paths.get("gold_dir", "data/gold"))
        if gold_dir.is_dir() and list_files(gold_dir, (".json",)):
            ner = evaluate_ner_against_gold(gold_dir, resolve_path(paths.get("raw_dir", "data/raw")), extract_fn)
            ner.to_csv(results_dir / "ner_metrics.csv", index=False)
            if not ner.empty:
                table = ner.pivot(index="label", columns="mode", values=["precision", "recall", "f1"])
                table.columns = [f"{metric}_{mode}" for metric, mode in table.columns]
                lines += [f"\n## NER vs gold ({int(ner['n_docs'].iloc[0])} docs)\n", markdown_table(table)]
            else:
                lines += ["\n## NER vs gold\n\nNo completed gold annotations; NER metrics unavailable.\n"]

    plot_readability(metrics, figures_dir / "readability_before_after.png")
    plot_retention(metrics, figures_dir / "entity_retention.png")
    (results_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"metrics": metrics, "summary": summary, "key": key, "ner": ner, "n_records": len(records),
            "unparseable_outputs": broken}
