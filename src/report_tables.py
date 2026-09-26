"""Markdown tables for the report and in-place filling of marker blocks in the report file.

A table named ``main`` goes into the report between ``<!-- TABLE:main -->`` and
``<!-- /TABLE:main -->``; re-running replaces the block's contents rather than appending.
"""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from src.evaluator import RETENTION_LABELS, RETENTION_PERSONAS
from src.prompts import PERSONAS
from src.reporting import PRETTY

TABLE_NAMES = ("main", "ablations", "retention", "ner", "human_eval")
MOCK_WARNING = "> ⚠️ **Mock data**: generated from template outputs with no model. Replace before submission."


def _num(x: Any, digits: int = 2) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def _pct(x: Any) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"


def _mean_sd(series: pd.Series, digits: int = 2) -> str:
    s = series.dropna()
    return "–" if s.empty else f"{s.mean():.{digits}f} ± {s.std(ddof=0):.{digits}f}"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    """Plain GitHub-flavored markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _with_note(table: str, note: str, mock: bool) -> str:
    parts = [MOCK_WARNING, ""] if mock else []
    return "\n".join([*parts, table, "", note])


def main_results_table(metrics: pd.DataFrame, mock: bool = False, pooled: str | None = None) -> str:
    """Source vs each persona: FK grade, Reading Ease, ROUGE-1/L (mean ± SD over notes).

    ``pooled`` (e.g. "12 notes × 3 seeds") describes rows pooled across seeds.
    """
    rows = [["Source note", _mean_sd(metrics["source_fkgl"]), _mean_sd(metrics["source_fre"], 1), "–", "–"]]
    for p in PERSONAS:
        rows.append([PRETTY[p], _mean_sd(metrics[f"{p}_fkgl"]), _mean_sd(metrics[f"{p}_fre"], 1),
                     _mean_sd(metrics[f"{p}_rouge1"]), _mean_sd(metrics[f"{p}_rougeL"])])
    table = md_table(["Text", "FK grade ↓", "Reading Ease ↑", "ROUGE-1", "ROUGE-L"], rows)
    over = f"{len(metrics)} outputs ({pooled})" if pooled else f"{len(metrics)} notes"
    return _with_note(table, f"_Mean ± SD over {over}. ROUGE is computed against the source note._", mock)


_ABLATION_COLUMNS = [
    # (summary.csv column, header, kind): kind "pct" = rate shown in %, "num" = plain number, "sec" = seconds
    ("fkgl_delta_patient_summary", "ΔFK patient", "num"),
    ("fkgl_delta_child_explanation", "ΔFK child", "num"),
    ("child_long_sentence_rate", "Child sentences ≥8 words", "pct"),
    ("rougeL_patient_summary", "ROUGE-L patient", "num"),
    ("retention_patient_overall", "Retention patient", "pct"),
    ("retention_caregiver_overall", "Retention caregiver", "pct"),
    ("retention_patient_first_attempt", "1st-try retention patient", "pct"),
    ("unsupported_numbers_patient_summary", "Unsupported numbers / note (patient)", "num"),
    ("fallback_rate", "Fallback rate", "pct"),
    ("truncation_rate_patient_summary", "Truncated (patient)", "pct"),
    ("json_validity_rate", "JSON valid", "pct"),
    ("mean_retries", "Retries / note", "num"),
    ("mean_latency_sec", "Latency / note (s)", "sec"),
]


def _cell(value: Any, std: Any, kind: str, show_std: bool) -> str:
    """Format a value (and its std across seeds, if shown)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    scale, digits, suffix = (100, 1, "%") if kind == "pct" else (1, 1 if kind == "sec" else 2, "")
    text = f"{scale * value:.{digits}f}{suffix}"
    has_std = show_std and std is not None and not (isinstance(std, float) and math.isnan(std))
    return f"{text} ± {scale * std:.{digits}f}" if has_std else text


def ablation_table(summary: pd.DataFrame, baseline: str = "baseline", mock: bool = False) -> str:
    """One row per ablation; non-baseline cells add the difference from the baseline.

    With several seeds (``n_seeds`` > 1 and ``<metric>_std`` columns) cells show mean ± std across seeds.
    """
    base = summary[summary["ablation"] == baseline]
    base_row = base.iloc[0] if not base.empty else None
    n_seeds = int(summary["n_seeds"].max()) if "n_seeds" in summary and summary["n_seeds"].notna().any() else 1
    show_std = n_seeds > 1
    header = ["Ablation", *(h for _, h, _ in _ABLATION_COLUMNS)]
    rows = []
    for _, r in summary.iterrows():
        if pd.isna(r.get("n_notes")):
            rows.append([f"{r['ablation']} ({r.get('status', 'missing')})", *["–"] * len(_ABLATION_COLUMNS)])
            continue
        cells = [f"**{r['ablation']}**" if r["ablation"] == baseline else str(r["ablation"])]
        for col, _, kind in _ABLATION_COLUMNS:
            value = r.get(col, math.nan)
            cell = _cell(value, r.get(f"{col}_std", math.nan), kind, show_std)
            if base_row is not None and r["ablation"] != baseline and cell != "–":
                diff = value - base_row.get(col, math.nan)
                if diff == diff:
                    cell += f" ({100 * diff:+.1f} pp)" if kind == "pct" else f" ({diff:+.2f})"
            cells.append(cell)
        rows.append(cells)
    spread = f"mean ± std across {n_seeds} seeds" if show_std else "means over notes (single seed)"
    note = (f"_Values are {spread}; parentheses give the difference of means from **{baseline}** "
            "(pp = percentage points). ΔFK = persona grade minus source grade (more negative = simpler). "
            "Retention is the model's own text after retries but before the fallback. 1st-try retention is the "
            "cleanest measure of entity injection, since retries re-inject missing facts. Fallback rate = share "
            "of all persona outputs that needed the fallback. Truncated = generation stopped at max_new_tokens._")
    return _with_note(md_table(header, rows), note, mock)


def retention_table(metrics: pd.DataFrame, mock: bool = False) -> str:
    """Retention per entity type per persona (before fallback), plus first-attempt and final."""
    header = ["Persona", *(lbl.title() for lbl in RETENTION_LABELS), "Overall", "1st attempt", "Final (with fallback)"]
    rows = []
    for p in RETENTION_PERSONAS:
        cells = [PRETTY[p]]
        cells += [_pct(metrics.get(f"{p}_retention_model_{lbl.lower()}", pd.Series(dtype=float)).mean())
                  for lbl in RETENTION_LABELS]
        cells += [_pct(metrics.get(f"{p}_retention_model", pd.Series(dtype=float)).mean()),
                  _pct(metrics.get(f"{p}_retention_first", pd.Series(dtype=float)).mean()),
                  _pct(metrics.get(f"{p}_retention", pd.Series(dtype=float)).mean())]
        rows.append(cells)
    note = ("_Share of unique source entities kept. Per-type columns and Overall: after retries, before the "
            "fallback. Final includes facts appended by the fallback._")
    return _with_note(md_table(header, rows), note, mock)


def ner_table(ner: pd.DataFrame) -> str:
    """NER precision/recall/F1 per label, exact and relaxed span matching."""
    labels = sorted(set(ner["label"]) - {"MICRO"}) + ["MICRO"]
    rows = []
    for label in labels:
        cells = [f"**{label}**" if label == "MICRO" else label]
        for mode in ("exact", "relaxed"):
            r = ner[(ner["label"] == label) & (ner["mode"] == mode)]
            cells += ["–"] * 3 if r.empty else [_num(r.iloc[0][m]) for m in ("precision", "recall", "f1")]
        rows.append(cells)
    header = ["Label", "P (exact)", "R (exact)", "F1 (exact)", "P (relaxed)", "R (relaxed)", "F1 (relaxed)"]
    n_docs = int(ner["n_docs"].iloc[0]) if "n_docs" in ner and len(ner) else 0
    return md_table(header, rows) + (f"\n\n_Rule-based NER vs hand-annotated gold ({n_docs} notes). Relaxed = "
                                     "overlapping span with the same label._")


def fill_marker(report: str, name: str, content: str) -> tuple[str, bool]:
    """Replace the text between ``<!-- TABLE:name -->`` and ``<!-- /TABLE:name -->``. Returns (text, found)."""
    pattern = re.compile(rf"(<!-- TABLE:{re.escape(name)} -->)(.*?)(<!-- /TABLE:{re.escape(name)} -->)", re.DOTALL)
    if not pattern.search(report):
        return report, False
    return pattern.sub(lambda m: f"{m.group(1)}\n{content.strip()}\n{m.group(3)}", report, count=1), True
