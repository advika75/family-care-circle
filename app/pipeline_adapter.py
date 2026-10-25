"""Builds the research pipeline for the web app. It only CALLS ``src/``; it never edits or reconfigures it
beyond choosing the backend. The pipeline keeps per-instance state, so one instance is built per process and
used by exactly one worker thread (see jobs.py)."""

from __future__ import annotations

from typing import Any

from app.config import Settings


def build_pipeline(settings: Settings) -> Any:
    from src.pipeline import FamilyCarePipeline  # imported lazily: heavy, and not needed to run most tests
    from src.utils import load_config

    return FamilyCarePipeline(load_config("config.yaml", {"backend": settings.backend}))
