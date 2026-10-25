"""Compare paired MTSamples baseline and no-NER-injection result tables.

This script consumes existing per-note ``metrics.csv`` and ``run_info.json`` files. It does not run
inference or produce metrics for notes missing from either condition.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PERSONAS = ("patient_summary", "caregiver_checklist", "child_explanation")
RETENTION_PERSONAS = ("patient_summary", "caregiver_checklist")
CONTINUOUS_METRICS = [
    "patient_summary_retention_first", "patient_summary_retention_model", "patient_summary_retention",
    "caregiver_checklist_retention_first", "caregiver_checklist_retention_model", "caregiver_checklist_retention",
    "total_retries", "fallbacks", "latency_total_sec",
    *[f"{p}_{m}" for p in PERSONAS for m in ("fkgl", "fre", "retries", "latency_sec")],
    "child_explanation_long_sentence_rate", "child_explanation_med_names", "child_explanation_numbers",
    *[f"{p}_{m}" for p in PERSONAS for m in ("rouge1", "rougeL")],
]
BINARY_METRICS = [
    "valid",
    *[f"{p}_{m}" for p in PERSONAS for m in ("fallback", "truncation_rate", "repetition")],
    *[f"{p}_unsupported_{kind}_flag" for p in PERSONAS for kind in ("numbers", "meds")],
]


def _read_metrics(results_dir: Path) -> pd.DataFrame:
    path = results_dir / "metrics.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing per-note metrics: {path}")
    df = pd.read_csv(path)
    if "id" not in df:
        raise ValueError(f"Metrics file has no stable note id column: {path}")
    df["id"] = df["id"].astype(str)
    if df["id"].duplicated().any():
        raise ValueError(f"Duplicate note ids in {path}")
    return df.set_index("id", drop=False)


def _read_run_info(results_dir: Path) -> dict[str, Any] | None:
    path = results_dir / "run_info.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Invalid run metadata: {path}")
    return value


def _without_injection(config: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(config)
    prompts = normalized.get("prompts")
    if isinstance(prompts, dict):
        prompts.pop("inject_entities", None)
    return normalized


def validate_pair(baseline_info: dict[str, Any] | None, no_injection_info: dict[str, Any] | None) -> list[str] | None:
    """Validate recorded run parity when both runs have the current run-info schema."""
    if baseline_info is None or no_injection_info is None:
        raise ValueError("Both runs need run_info.json to verify paired experiment parity")
    for info in (baseline_info, no_injection_info):
        if info.get("dataset") != "mtsamples":
            raise ValueError(f"Expected MTSamples run metadata, got dataset {info.get('dataset')!r}")
    baseline_ids = baseline_info.get("source_note_ids")
    no_injection_ids = no_injection_info.get("source_note_ids")
    if not isinstance(baseline_ids, list) or not isinstance(no_injection_ids, list):
        raise ValueError("Both MTSamples run_info.json files must record source_note_ids")
    if len(set(baseline_ids)) != len(baseline_ids) or len(set(no_injection_ids)) != len(no_injection_ids):
        raise ValueError("Run metadata contains duplicate source note IDs")
    if baseline_ids != no_injection_ids:
        raise ValueError("Run metadata has different planned source note IDs")
    for key in ("dataset", "backend", "model", "generation_seed", "child_variant"):
        left, right = baseline_info.get(key), no_injection_info.get(key)
        if left is None or right is None:
            raise ValueError(f"Both MTSamples runs must record {key}")
        if left != right:
            raise ValueError(f"Paired runs differ in {key}: {left!r} != {right!r}")
    baseline_hashes, no_injection_hashes = baseline_info.get("model_hashes"), no_injection_info.get("model_hashes")
    if not baseline_hashes or not no_injection_hashes:
        raise ValueError("Both runs must record model hashes")
    if baseline_hashes != no_injection_hashes:
        raise ValueError("Paired runs use different model hashes")
    baseline_config = baseline_info.get("effective_config")
    no_injection_config = no_injection_info.get("effective_config")
    if not isinstance(baseline_config, dict) or not isinstance(no_injection_config, dict):
        raise ValueError("Both runs must record effective_config")
    if _without_injection(baseline_config) != _without_injection(no_injection_config):
        raise ValueError("Paired run configurations differ beyond prompts.inject_entities")
    if baseline_config.get("prompts", {}).get("inject_entities") is not True:
        raise ValueError("Baseline run metadata must enable entity injection")
    if no_injection_config.get("prompts", {}).get("inject_entities") is not False:
        raise ValueError("No-injection run metadata must disable entity injection")
    return list(baseline_ids)


def _exact_sign_test_p(differences: list[float]) -> float | None:
    """Two-sided exact paired sign test; zero differences are omitted."""
    nonzero = [value for value in differences if value != 0]
    n = len(nonzero)
    if not n:
        return 1.0 if differences else None
    positive = sum(value > 0 for value in nonzero)
    tail = min(positive, n - positive)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2 ** n)
    return min(1.0, 2 * probability)


def _bootstrap_mean_ci(differences: list[float], samples: int, seed: int) -> tuple[float | None, float | None]:
    if not differences:
        return None, None
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(sum(rng.choices(differences, k=n)) / n for _ in range(samples))
    return means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]


def _paired_values(left: pd.Series, right: pd.Series) -> tuple[list[float], list[float]]:
    pairs = pd.concat([left, right], axis=1).apply(pd.to_numeric, errors="coerce").dropna()
    return pairs.iloc[:, 0].astype(float).tolist(), pairs.iloc[:, 1].astype(float).tolist()


def _summarize_metric(name: str, baseline: pd.Series, no_injection: pd.Series,
                      bootstrap_samples: int, seed: int, binary: bool = False) -> dict[str, Any]:
    left, right = _paired_values(baseline, no_injection)
    differences = [b - a for a, b in zip(left, right)]
    ci_low, ci_high = _bootstrap_mean_ci(differences, bootstrap_samples, seed)
    row: dict[str, Any] = {
        "metric": name,
        "n_paired": len(differences),
        "baseline_mean_paired": sum(left) / len(left) if left else math.nan,
        "no_injection_mean_paired": sum(right) / len(right) if right else math.nan,
        "mean_difference_no_injection_minus_baseline": sum(differences) / len(differences) if differences else math.nan,
        "bootstrap_95_ci_low": ci_low,
        "bootstrap_95_ci_high": ci_high,
    }
    if binary:
        baseline_only = sum(a == 1 and b == 0 for a, b in zip(left, right))
        no_injection_only = sum(a == 0 and b == 1 for a, b in zip(left, right))
        row.update({"baseline_only": baseline_only, "no_injection_only": no_injection_only,
                    "paired_test": "exact McNemar", "paired_p_value": _exact_sign_test_p(differences)})
    else:
        row.update({"baseline_only": math.nan, "no_injection_only": math.nan,
                    "paired_test": "exact sign test", "paired_p_value": _exact_sign_test_p(differences)})
    return row


def compare_runs(baseline_dir: str | Path, no_injection_dir: str | Path, out_dir: str | Path,
                 bootstrap_samples: int = 10000, seed: int = 42) -> pd.DataFrame:
    """Write paired metrics and missing IDs from two existing ablation result directories."""
    baseline_dir, no_injection_dir, out_dir = map(Path, (baseline_dir, no_injection_dir, out_dir))
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    baseline_info, no_injection_info = _read_run_info(baseline_dir), _read_run_info(no_injection_dir)
    expected_ids = validate_pair(baseline_info, no_injection_info)
    baseline, no_injection = _read_metrics(baseline_dir), _read_metrics(no_injection_dir)
    baseline_ids, no_injection_ids = set(baseline.index), set(no_injection.index)
    expected = set(expected_ids) if expected_ids is not None else baseline_ids | no_injection_ids
    unexpected = (baseline_ids | no_injection_ids) - expected
    if unexpected:
        raise ValueError(f"Metrics contain ids outside run metadata: {sorted(unexpected)[:5]}")
    paired = sorted(baseline_ids & no_injection_ids)
    missing = pd.DataFrame([
        {"id": note_id, "baseline_present": note_id in baseline_ids,
         "no_injection_present": note_id in no_injection_ids}
        for note_id in sorted(expected) if note_id not in baseline_ids or note_id not in no_injection_ids
    ], columns=["id", "baseline_present", "no_injection_present"])

    metric_names = [name for name in CONTINUOUS_METRICS if name in baseline and name in no_injection]
    first_retention_names = [f"{persona}_retention_first" for persona in RETENTION_PERSONAS]
    metric_names.extend(name for name in first_retention_names if name not in metric_names)
    binary_names = [name for name in BINARY_METRICS if name in baseline and name in no_injection]
    for persona in PERSONAS:
        for kind in ("numbers", "meds"):
            source = f"{persona}_unsupported_{kind}"
            derived = f"{source}_flag"
            if source in baseline and source in no_injection:
                baseline[derived] = (pd.to_numeric(baseline[source], errors="coerce") > 0).astype(float)
                no_injection[derived] = (pd.to_numeric(no_injection[source], errors="coerce") > 0).astype(float)
                binary_names.append(derived)
    baseline_present, no_injection_present = baseline.loc[paired], no_injection.loc[paired]
    rows = []
    for index, name in enumerate(metric_names):
        baseline_values = baseline_present[name] if name in baseline_present else pd.Series(
            math.nan, index=baseline_present.index)
        no_injection_values = no_injection_present[name] if name in no_injection_present else pd.Series(
            math.nan, index=no_injection_present.index)
        first_attempt_metric = name.endswith("_retention_first")
        if first_attempt_metric:
            evidence_column = f"{name}_evidence_available"
            # Missing availability fields are not evidence. Historical retention values are never trusted
            # as a substitute for captured first-attempt text.
            if evidence_column in baseline_present and evidence_column in no_injection_present:
                available = (
                    pd.to_numeric(baseline_present[evidence_column], errors="coerce").eq(1)
                    & pd.to_numeric(no_injection_present[evidence_column], errors="coerce").eq(1)
                )
            else:
                available = pd.Series(False, index=baseline_present.index)
            values_present = (pd.to_numeric(baseline_values, errors="coerce").notna()
                              & pd.to_numeric(no_injection_values, errors="coerce").notna())
            missing_evidence = int((~available).sum())
            inapplicable = int((available & ~values_present).sum())
            eligible = available & values_present
            baseline_values, no_injection_values = baseline_values[eligible], no_injection_values[eligible]
        summary_row = _summarize_metric(name, baseline_values, no_injection_values,
                                        bootstrap_samples, seed + index)
        if first_attempt_metric:
            summary_row["n_missing_first_attempt_evidence"] = missing_evidence
            summary_row["n_inapplicable_retention"] = inapplicable
        rows.append(summary_row)
    offset = len(rows)
    for index, name in enumerate(dict.fromkeys(binary_names)):
        rows.append(_summarize_metric(name, baseline_present[name], no_injection_present[name], bootstrap_samples,
                                      seed + offset + index, binary=True))
    summary = pd.DataFrame(rows)
    if out_dir.exists():
        raise FileExistsError(f"Refusing to replace existing paired analysis directory: {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir()
    summary.to_csv(out_dir / "paired_metrics.csv", index=False)
    missing.to_csv(out_dir / "unpaired_ids.csv", index=False)
    (out_dir / "summary.md").write_text(_markdown_summary(
        summary, len(expected), len(baseline_ids), len(no_injection_ids), len(paired), seed, bootstrap_samples,
        (baseline_info or {}).get("unparseable_outputs"),
        (no_injection_info or {}).get("unparseable_outputs"),
    ), encoding="utf-8")
    return summary


def _markdown_summary(summary: pd.DataFrame, expected: int, baseline_n: int, no_injection_n: int,
                      paired_n: int, seed: int, bootstrap_samples: int,
                      baseline_parse_failures: Any = None, no_injection_parse_failures: Any = None) -> str:
    lines = [
        "# Paired MTSamples comparison", "",
        f"Expected IDs: {expected} · baseline metrics: {baseline_n} · no-injection metrics: {no_injection_n} · paired: {paired_n}",
        "", "Differences are no-injection minus baseline. Confidence intervals are percentile bootstrap intervals "
        f"over paired note differences ({bootstrap_samples} resamples, seed {seed}). Continuous metrics use the "
        "exact paired sign test; binary flags use exact McNemar tests.", "",
        "This is an exploratory comparison of rule-derived metrics, not a clinical safety assessment. "
        "Missing IDs are excluded from paired estimates and listed in `unpaired_ids.csv`. "
        "For first-attempt retention, missing captured evidence is counted separately from notes that have "
        "captured text but no eligible source entity for that retention category; the latter are inapplicable "
        "and excluded only from that category's retention estimate.", "",
    ]
    if baseline_parse_failures is not None or no_injection_parse_failures is not None:
        lines.insert(3, f"Unparseable output files: baseline {baseline_parse_failures or 0} · "
                     f"no-injection {no_injection_parse_failures or 0}")
    if summary.empty:
        lines.append("No shared metric columns were available.")
    else:
        columns = ["metric", "n_paired", "baseline_mean_paired", "no_injection_mean_paired",
                   "mean_difference_no_injection_minus_baseline", "bootstrap_95_ci_low",
                   "bootstrap_95_ci_high", "paired_test", "paired_p_value"]
        if "n_missing_first_attempt_evidence" in summary:
            columns.append("n_missing_first_attempt_evidence")
            columns.append("n_inapplicable_retention")
        view = summary[columns]
        headers = list(view.columns)
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for values in view.itertuples(index=False, name=None):
            cells = [f"{value:.4f}" if isinstance(value, (int, float)) and not pd.isna(value) else str(value)
                     for value in values]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-results-dir", default="results/mtsamples/baseline")
    parser.add_argument("--no-injection-results-dir", default="results/mtsamples/no_injection")
    parser.add_argument("--out-dir", default="results/mtsamples/paired_analysis")
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        summary = compare_runs(args.baseline_results_dir, args.no_injection_results_dir, args.out_dir,
                               args.bootstrap_samples, args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Wrote paired comparison for {int(summary['n_paired'].max()) if len(summary) else 0} paired notes to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
