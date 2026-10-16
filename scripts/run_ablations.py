"""Run the ablations defined under ``ablations:`` in config.yaml, then summarize them.

For each ablation: apply its overrides to a copy of the config, generate outputs for data/raw into
data/outputs_<name>/, evaluate into results/ablations/<name>/. Finally write
results/ablations/summary.csv and grouped bar charts in results/ablations/figures/.

Resumable: notes that already have an output are skipped, so an interrupted run continues where it
stopped. If an ablation's config changed since its outputs were made, the run stops unless --force
(which regenerates that ablation from scratch).

Examples:
    python scripts/run_ablations.py --mock                          # whole flow, no model
    python scripts/run_ablations.py                                  # real run (config backend)
    python scripts/run_ablations.py --backend llama_cpp --only baseline,no_retry
    python scripts/run_ablations.py --force --only temp_0.7          # redo one ablation
    python scripts/run_ablations.py --backend llama_cpp --seeds 0 1 2  # 3 seeds; summary = mean ± std

With --seeds, each (ablation, seed) run has its own data/outputs_<name>_seed<k>/ and
results/ablations/<name>/seed<k>/, and summary.csv reports mean and std across seeds
(per-seed rows in summary_by_seed.csv). Without --seeds, one run per ablation uses generation.seed.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ablations import (  # noqa: E402
    GeneratorCache,
    ablation_dirs,
    ablations_root,
    build_ablation_config,
    shadowed_overrides,
    estimate_seconds_per_note,
    fingerprint,
    fingerprint_state,
    model_key,
    pending_notes,
    plot_ablation_summary,
    run_ablation,
    summarize_ablations,
)
from src.datasets import dataset_config, select_note_files  # noqa: E402
from src.utils import list_files, load_config, setup_logging  # noqa: E402

WARN_ABOVE_SEC = 3600


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", choices=["synthetic", "mtsamples"], default=None,
                        help="Use a configured dataset; MTSamples writes to separate dataset-specific paths")
    parser.add_argument("--input", default=None, help="Notes file/folder (default: paths.raw_dir)")
    parser.add_argument("--backend", default=None, choices=["transformers", "llama_cpp", "mock"],
                        help="Backend for all ablations (default: `backend` in the config)")
    parser.add_argument("--mock", action="store_true",
                        help="Same as --backend mock: no model, no network; separate output folders")
    parser.add_argument("--only", default=None, help="Comma-separated ablation names to run")
    parser.add_argument("--force", action="store_true", help="Regenerate selected ablations even if outputs exist")
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N notes")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation on long runs")
    parser.add_argument("--seeds", type=int, nargs="+", default=None,
                        help="Run every ablation once per seed (e.g. --seeds 0 1 2); default: one run, config seed")
    return parser.parse_args()


def _fmt(seconds: float) -> str:
    return f"{seconds / 3600:.1f} h" if seconds >= 3600 else f"{seconds / 60:.1f} min" if seconds >= 60 else f"{seconds:.0f} s"


def main() -> int:
    """Entry point."""
    args = parse_args()
    if args.backend == "mock":  # --backend mock and --mock are equivalent
        args.mock = True
    sys.stdout.reconfigure(line_buffering=True)  # keep the plan table in order with log lines
    base = load_config(args.config, {"dataset": args.dataset})
    dataset = base.get("dataset", "synthetic")
    log = setup_logging(base.get("logging", {}).get("level", "INFO"))
    if dataset == "mtsamples" and args.force:
        log.error("--force is disabled for MTSamples to protect existing outputs.")
        return 2
    if dataset == "mtsamples" and (args.mock or args.backend not in (None, "llama_cpp")):
        log.error("MTSamples ablations require the local llama_cpp backend.")
        return 2
    if dataset == "mtsamples" and args.seeds not in (None, [42]):
        log.error("MTSamples ablations require seed 42.")
        return 2
    paths = dataset_config(base)
    log = setup_logging(base.get("logging", {}).get("level", "INFO"))
    for noisy in ("httpx", "absl", "src.postprocess"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    ablations = base.get("ablations") or {}
    if not ablations:
        log.error("No 'ablations:' section in %s.", args.config)
        return 1
    names = list(ablations)
    if args.only:
        wanted = [n.strip() for n in args.only.split(",") if n.strip()]
        unknown = [n for n in wanted if n not in ablations]
        if unknown:
            log.error("Unknown ablation(s): %s. Defined: %s", ", ".join(unknown), ", ".join(names))
            return 1
        names = wanted
    input_path = args.input or paths.get("raw_dir", "data/raw")
    if dataset == "mtsamples":
        requested = paths.get("max_notes")
        if args.limit is not None:
            requested = min(args.limit, requested) if requested is not None else args.limit
        notes = select_note_files(input_path, requested, paths.get("seed", base.get("generation", {}).get("seed", 42)))
    else:
        notes = list_files(input_path)[: args.limit]
    if dataset == "mtsamples" and not notes:
        log.error("No MTSamples note files found in %s.", input_path)
        return 1
    root = ablations_root(args.mock, dataset)
    if dataset == "mtsamples" and root.exists():
        log.error("Refusing to write MTSamples ablation summary into existing directory %s.", root)
        return 2

    # Plan everything first, so config errors and conflicts surface before any model is loaded.
    plans, conflicts, total_est = [], [], 0.0
    print(f"\n{'run':<26} {'backend':<10} {'model':<36} {'todo':>7} {'est/note':>9} {'est total':>10}")
    seeds: list[int | None] = list(args.seeds) if args.seeds else [None]
    for name in names:
        for key in shadowed_overrides(base, ablations[name] or {}):
            log.warning("Ablation '%s': %s is set in config.yaml and overrides the ablation's generation "
                        "setting for that persona. Add it to the ablation to change it too.", name, key)
        for seed in seeds:
            try:
                config = build_ablation_config(base, ablations[name], backend=args.backend, mock=args.mock, seed=seed)
            except KeyError as exc:
                log.error("Ablation '%s': %s", name, exc.args[0])
                return 1
            if dataset == "mtsamples" and (
                    config.get("backend") != "llama_cpp"
                    or config.get("generation", {}).get("seed") != 42
                    or config.get("gguf_path") != "models/qwen2.5-3b-instruct-q4_k_m.gguf"):
                log.error("MTSamples inference requires llama_cpp, seed 42, and the configured Qwen2.5-3B Q4_K_M GGUF.")
                return 2
            label = name if seed is None else f"{name} [seed {seed}]"
            outputs_dir, results_dir = ablation_dirs(name, args.mock, seed, dataset)
            if dataset == "mtsamples" and results_dir.exists() and any(results_dir.iterdir()):
                log.error("Refusing to overwrite MTSamples results in %s.", results_dir)
                return 2
            state = fingerprint_state(outputs_dir, fingerprint(config))
            if state == "mismatch" and not args.force:
                conflicts.append((label, outputs_dir))
            todo = notes if args.force else pending_notes(notes, outputs_dir)
            per_note, source = estimate_seconds_per_note(config)
            est = per_note * len(todo)
            total_est += est
            plans.append((name, label, config, outputs_dir, results_dir))
            print(f"{label[:26]:<26} {config['backend']:<10} {model_key(config)[:36]:<36} {len(todo):>3}/{len(notes):<3} "
                  f"{per_note:>8.1f}s {_fmt(est):>10}   ({source})")
    print(f"{'estimated total':>91} {_fmt(total_est):>10}\n")

    if conflicts:
        for name, outputs_dir in conflicts:
            log.error("Ablation '%s': outputs in %s were made with a different config.", name, outputs_dir)
        log.error("Refusing to mix outputs. Re-run with --force (regenerates those ablations) or change --only.")
        return 2

    if total_est > WARN_ABOVE_SEC and not args.yes:
        print(f"WARNING: estimated total runtime is {_fmt(total_est)} (over 1 hour). Estimates without earlier "
              "runs of a model are rough guesses.")
        if not sys.stdin.isatty():
            log.error("Not running interactively; re-run with --yes to start anyway.")
            return 3
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 0

    cache = GeneratorCache()
    t_all = time.perf_counter()
    for name, label, config, outputs_dir, results_dir in plans:
        log.info("=== %s: %s ===", label, ablations[name] or "no overrides")
        info = run_ablation(name, config, ablations[name] or {}, notes, outputs_dir, results_dir, cache, args.force)
        log.info("=== %s %s in %s (generated %d, skipped %d)%s ===", label, info["status"], _fmt(info["runtime_sec"]),
                 info["notes_generated"], info["notes_skipped"], f": {info['error']}" if info["error"] else "")
        if dataset == "mtsamples" and (info["status"] != "ok" or
                                         info["notes_generated"] + info["notes_skipped"] != len(notes)):
            cache.release()
            log.error("Stopping MTSamples ablations because the run did not complete every note.")
            return 1
    cache.release()

    if dataset == "mtsamples":
        root.mkdir(parents=True, exist_ok=False)
    # Every defined ablation (including ones run earlier), for the seeds of this invocation.
    summary, by_seed = summarize_ablations(list(ablations), args.mock, args.seeds, dataset)
    summary = summary[summary["status"] != "missing"]  # keep failed/partial runs, drop never-run ablations
    by_seed = by_seed[by_seed["status"] != "missing"]
    summary.to_csv(root / "summary.csv", index=False)
    by_seed.to_csv(root / "summary_by_seed.csv", index=False)
    figures = plot_ablation_summary(summary, root / "figures")
    log.info("All ablations done in %s. Summary: %s; %d figures in %s", _fmt(time.perf_counter() - t_all),
             root / "summary.csv", len(figures), root / "figures")

    cols = ["ablation", "status", "n_seeds", "fkgl_delta_patient_summary", "fkgl_delta_child_explanation",
            "retention_patient_overall", "retention_patient_first_attempt", "fallback_rate",
            "truncation_rate_patient_summary", "child_long_sentence_rate", "mean_retries", "mean_latency_sec"]
    print(summary[[c for c in cols if c in summary]].round(3).to_string(index=False))
    return 1 if (summary["status"] == "failed").any() else 0


if __name__ == "__main__":
    sys.exit(main())
