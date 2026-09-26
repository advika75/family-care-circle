"""Run the Family Care Circle pipeline on one note or a folder of notes.

Examples:
    python scripts/run_pipeline.py --input data/raw --backend mock
    python scripts/run_pipeline.py --input data/raw/note_01.txt            # uses config.yaml backend
    python scripts/run_pipeline.py --input data/raw --backend transformers --model-id Qwen/Qwen2.5-7B-Instruct
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import FamilyCarePipeline  # noqa: E402
from src.utils import list_files, load_config, resolve_path, setup_logging, write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=None, help="Note file or folder of .txt notes (default: paths.raw_dir)")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument("--backend", choices=["transformers", "llama_cpp", "mock"], help="Override config backend")
    parser.add_argument("--model-id", help="Override config model_id (transformers backend)")
    parser.add_argument("--gguf-path", help="Override config gguf_path (llama_cpp backend)")
    parser.add_argument("--output-dir", default=None, help="Where to write JSON (default: paths.outputs_dir)")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N notes")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    config = load_config(args.config, {"backend": args.backend, "model_id": args.model_id, "gguf_path": args.gguf_path})
    log = setup_logging(config.get("logging", {}).get("level", "INFO"))
    paths = config.get("paths", {})
    files = list_files(args.input or paths.get("raw_dir", "data/raw"))[: args.limit]
    if not files:
        log.error("No .txt notes found.")
        return 1
    out_dir = resolve_path(args.output_dir or paths.get("outputs_dir", "data/outputs"))

    log.info("Backend=%s model=%s notes=%d", config["backend"], config.get("model_id"), len(files))
    pipeline = FamilyCarePipeline(config)
    n_invalid = 0
    for path in files:
        record = pipeline.run_file(path)
        out = write_json(record, out_dir / f"{path.stem}.json")
        meta = record["metadata"]
        n_invalid += not meta["valid"]
        log.info("Wrote %s (valid=%s, retries=%s, %.2fs)", out.name, meta["valid"],
                 sum(meta["retries"].values()), meta["latency_sec"]["total"])
    log.info("Done: %d notes, %d invalid. Outputs in %s", len(files), n_invalid, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
