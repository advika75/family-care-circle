"""Report-ready tables and figures assembled only from result files that actually exist.

Every table states its dataset and the number of notes it covers. A missing or empty result file
produces an explicit "not available" table/caption naming what's missing, never a placeholder
number or an invented metric.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from src.plotting import grouped_bars, new_figure, save_figure, style_axes
from src.prompts import PERSONAS
from src.report_tables import ablation_table, main_results_table, md_table, ner_table
from src.reporting import PRETTY

NOT_AVAILABLE = "not available"


def not_available_table(reason: str) -> pd.DataFrame:
    """A one-row DataFrame marking a table as unavailable, with why, instead of a placeholder number."""
    return pd.DataFrame([{"status": NOT_AVAILABLE, "reason": reason}])


def not_available_markdown(title: str, reason: str) -> str:
    return f"**{title}: {NOT_AVAILABLE}.** {reason}"


def write_table(out_dir: str | Path, name: str, df: pd.DataFrame, markdown: str) -> None:
    """Write ``{name}.csv``, ``{name}.md`` and ``{name}.tex`` (LaTeX) for one table."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"{name}.csv", index=False)
    (out_dir / f"{name}.md").write_text(markdown.strip() + "\n", encoding="utf-8")
    (out_dir / f"{name}.tex").write_text(df.to_latex(index=False, escape=True), encoding="utf-8")


# --------------------------------------------------------------------------- ablations (synthetic)

_ABLATION_CSV_COLUMNS = [
    "ablation", "n_notes", "n_seeds", "fkgl_delta_patient_summary", "fkgl_delta_child_explanation",
    "retention_patient_overall", "retention_caregiver_overall", "retention_patient_first_attempt",
    "unsupported_numbers_patient_summary", "fallback_rate", "truncation_rate_patient_summary",
    "json_validity_rate", "mean_retries", "mean_latency_sec",
]


def ablations_synthetic_table(summary: pd.DataFrame, baseline: str = "baseline") -> tuple[pd.DataFrame, str]:
    """Synthetic-dataset ablations: CSV columns plus the existing report-style markdown table."""
    n_notes = int(summary["n_notes"].dropna().iloc[0]) if summary["n_notes"].notna().any() else None
    n_seeds = int(summary["n_seeds"].max()) if "n_seeds" in summary and summary["n_seeds"].notna().any() else 1
    cols = [c for c in _ABLATION_CSV_COLUMNS if c in summary.columns]
    df = summary[cols].copy()
    df.insert(0, "dataset", f"Synthetic ({n_notes} notes x {n_seeds} seeds)" if n_notes else "Synthetic")
    md = (f"**Dataset: synthetic, {n_notes} notes x {n_seeds} seeds**\n\n" if n_notes else "") + ablation_table(
        summary, baseline
    )
    return df, md


# --------------------------------------------------------------------------- generation metrics (MTSamples)

def mtsamples_generation_table(metrics: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Source-vs-persona readability/ROUGE table for the real MTSamples outputs."""
    n_notes = len(metrics)
    rows = [{"text": "Source note", "fkgl_mean": metrics["source_fkgl"].mean(), "fkgl_std": metrics["source_fkgl"].std(),
             "fre_mean": metrics["source_fre"].mean(), "rouge1_mean": math.nan, "rougeL_mean": math.nan}]
    for p in PERSONAS:
        rows.append({
            "text": PRETTY[p], "fkgl_mean": metrics[f"{p}_fkgl"].mean(), "fkgl_std": metrics[f"{p}_fkgl"].std(),
            "fre_mean": metrics[f"{p}_fre"].mean(), "rouge1_mean": metrics[f"{p}_rouge1"].mean(),
            "rougeL_mean": metrics[f"{p}_rougeL"].mean(),
        })
    df = pd.DataFrame(rows)
    df.insert(0, "dataset", f"MTSamples ({n_notes} real clinical notes)")
    backends = ", ".join(sorted(set(metrics["backend"].astype(str)))) if "backend" in metrics else "unknown"
    md = (f"**Dataset: MTSamples, {n_notes} real clinical notes (backend: {backends})**\n\n"
          + main_results_table(metrics))
    return df, md


# --------------------------------------------------------------------------- NER

def ner_table_for(ner_metrics: pd.DataFrame, dataset_label: str) -> tuple[pd.DataFrame, str]:
    df = ner_metrics.copy()
    df.insert(0, "dataset", dataset_label)
    md = f"**Dataset: {dataset_label}**\n\n" + ner_table(ner_metrics)
    return df, md


def mtsamples_ner_status(summary: dict[str, Any]) -> tuple[pd.DataFrame, str] | None:
    """None if MTSamples NER has real evaluated notes (caller should use ner_table_for instead);
    otherwise a "not available" table/markdown explaining why."""
    evaluated = summary.get("evaluated_note_count", 0)
    skipped = summary.get("skipped_note_count", 0)
    if evaluated:
        return None
    reason = (f"{skipped} of {skipped + evaluated} selected notes have gold annotations, but none are marked "
              "'complete' in the annotation manifest. Run scripts/annotate_mtsamples.py to complete some, then "
              "scripts/evaluate_mtsamples_ner.py.")
    return not_available_table(reason), not_available_markdown("MTSamples NER (precision/recall/F1 vs gold)", reason)


# --------------------------------------------------------------------------- figures

CHILD_TARGET_GRADE = 1.0  # the ~1st-grade reading level the child persona aims for


def entity_retention_figure(summary: pd.DataFrame, out_path: Path) -> None:
    """Grouped bars: retention (model's own text, before fallback) per persona, one group per condition."""
    categories = list(summary["ablation"])
    series = {
        "Patient": [100 * v for v in summary["retention_patient_overall"]],
        "Caregiver": [100 * v for v in summary["retention_caregiver_overall"]],
    }
    errors = {}
    if "retention_patient_overall_std" in summary:
        errors["Patient"] = [100 * v for v in summary["retention_patient_overall_std"]]
    if "retention_caregiver_overall_std" in summary:
        errors["Caregiver"] = [100 * v for v in summary["retention_caregiver_overall_std"]]
    n_notes = int(summary["n_notes"].dropna().iloc[0]) if summary["n_notes"].notna().any() else "?"
    n_seeds = int(summary["n_seeds"].max()) if "n_seeds" in summary and summary["n_seeds"].notna().any() else 1
    fig, (ax,) = new_figure(1, width_per_panel=7.0)
    style_axes(ax, f"Entity retention by condition — synthetic, {n_notes} notes x {n_seeds} seeds",
               "Retention % (model, before fallback)")
    grouped_bars(ax, categories, series, fmt="{:.0f}", errors=errors or None)
    save_figure(fig, out_path)


def fallback_rate_figure(summary: pd.DataFrame, out_path: Path) -> None:
    """Bar chart of the overall fallback rate per condition."""
    categories = list(summary["ablation"])
    series = {"Fallback rate": [100 * v for v in summary["fallback_rate"]]}
    errors = ({"Fallback rate": [100 * v for v in summary["fallback_rate_std"]]}
              if "fallback_rate_std" in summary else None)
    n_notes = int(summary["n_notes"].dropna().iloc[0]) if summary["n_notes"].notna().any() else "?"
    n_seeds = int(summary["n_seeds"].max()) if "n_seeds" in summary and summary["n_seeds"].notna().any() else 1
    fig, (ax,) = new_figure(1, width_per_panel=7.0)
    style_axes(ax, f"Fallback rate by condition — synthetic, {n_notes} notes x {n_seeds} seeds",
               "Share of outputs needing the fallback (%)")
    grouped_bars(ax, categories, series, fmt="{:.0f}", errors=errors)
    save_figure(fig, out_path)


def fkgl_vs_child_target_figure(
    synthetic_metrics: pd.DataFrame | None, mtsamples_metrics: pd.DataFrame | None, out_path: Path
) -> None:
    """FK grade per text (source + each persona) for whichever dataset(s) are available, vs. the child target."""
    categories = ["Source", *[PRETTY[p] for p in PERSONAS]]
    series: dict[str, list[float]] = {}
    if synthetic_metrics is not None and len(synthetic_metrics):
        series[f"Synthetic ({len(synthetic_metrics)} notes)"] = [synthetic_metrics["source_fkgl"].mean()] + [
            synthetic_metrics[f"{p}_fkgl"].mean() for p in PERSONAS
        ]
    if mtsamples_metrics is not None and len(mtsamples_metrics):
        series[f"MTSamples ({len(mtsamples_metrics)} notes)"] = [mtsamples_metrics["source_fkgl"].mean()] + [
            mtsamples_metrics[f"{p}_fkgl"].mean() for p in PERSONAS
        ]
    fig, (ax,) = new_figure(1, width_per_panel=7.5)
    style_axes(ax, "FK grade vs. the child persona's ~1st-grade target", "FK grade (lower = simpler)")
    if series:
        grouped_bars(ax, categories, series, fmt="{:.1f}")
    else:
        ax.set_xticks(range(len(categories)), categories)
    ax.axhline(CHILD_TARGET_GRADE, color="#e34948", linewidth=1.2, linestyle="--")
    ax.text(len(categories) - 0.5, CHILD_TARGET_GRADE, " 1st-grade target", color="#e34948", fontsize=8, va="bottom",
            ha="right")
    note = "No data available for either dataset." if not series else None
    save_figure(fig, out_path, note=note)
