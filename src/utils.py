"""Shared helpers: config loading, logging, file I/O and seeding."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Iterable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path: str | Path) -> Path:
    """Return ``path`` as an absolute path, interpreting relative paths from the project root."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_config(path: str | Path = "config.yaml", overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a YAML config file and shallow-merge ``overrides`` (ignoring ``None`` values) on top."""
    with open(resolve_path(path), encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    for key, value in (overrides or {}).items():
        if value is not None:
            config[key] = value
    return config


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logging once and return the project logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("family_care")


def set_seed(seed: int) -> None:
    """Seed Python, NumPy and (if installed) PyTorch RNGs for reproducibility."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file's contents, streamed in chunks so multi-GB model files don't need to fit in memory."""
    import hashlib

    digest = hashlib.sha256()
    with open(resolve_path(path), "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: str | Path) -> str:
    """Read a UTF-8 text file."""
    return resolve_path(path).read_text(encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Read a JSON file."""
    with open(resolve_path(path), encoding="utf-8") as f:
        return json.load(f)


def write_json(data: Any, path: str | Path) -> Path:
    """Write ``data`` as pretty-printed JSON, creating parent directories. Returns the path."""
    out = resolve_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out


def list_files(path: str | Path, extensions: Iterable[str] = (".txt",)) -> list[Path]:
    """Return ``[path]`` if it is a file, else the sorted files in the folder with the given extensions."""
    p = resolve_path(path)
    if p.is_file():
        return [p]
    if not p.is_dir():
        raise FileNotFoundError(f"No such file or directory: {p}")
    exts = tuple(e.lower() for e in extensions)
    return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in exts)
