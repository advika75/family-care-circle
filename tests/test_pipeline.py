"""Tests for src/pipeline.py with the mock backend."""

from __future__ import annotations

import copy
import json

from src.generator import MockGenerator
from src.pipeline import FamilyCarePipeline
from src.prompts import CHILD_INSTRUCTIONS


def test_mock_pipeline_end_to_end(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "t1")
    json.dumps(record)
    assert record["metadata"]["valid"], record["metadata"]["validation_errors"]
    assert record["metadata"]["backend"] == "mock"
    assert isinstance(record["caregiver_checklist"], list) and len(record["caregiver_checklist"]) >= 3
    assert "500 mg" in record["patient_summary"] and "twice a day" in record["patient_summary"]
    assert sum(record["metadata"]["retries"].values()) == 0
    assert not any(record["metadata"]["fallback_used"].values())


def test_mock_failures_trigger_retries(sample_note, mock_config):
    mock_config["mock"]["fail_first"] = 1
    pipeline = FamilyCarePipeline(mock_config)
    assert isinstance(pipeline.generator, MockGenerator)
    record = pipeline.run(sample_note, "t2")
    assert record["metadata"]["retries"] == {"patient_summary": 1, "caregiver_checklist": 1, "child_explanation": 1}
    assert record["metadata"]["valid"]


def test_pipeline_records_truncation_per_persona(sample_note, mock_config):
    cfg = copy.deepcopy(mock_config)
    cfg["personas"]["patient_summary"]["max_new_tokens"] = 10
    meta = FamilyCarePipeline(cfg).run(sample_note, "t")["metadata"]
    assert meta["truncated"] == {"patient_summary": True, "caregiver_checklist": False, "child_explanation": False}
    assert all(meta["truncated_attempts"]["patient_summary"])        # every attempt was cut off
    assert meta["missing_first_attempt"]["patient_summary"]           # the cut text lost facts


def test_metadata_fields(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "note_x")
    meta = record["metadata"]
    for key in ("backend", "model_id", "generation_params", "seed", "retries", "fallback_used", "truncated",
                "latency_sec", "valid", "missing_first_attempt", "missing_after_retries", "child_variant"):
        assert key in meta, key
    assert set(meta["latency_sec"]) == {"patient_summary", "caregiver_checklist", "child_explanation", "total"}
    assert record["id"] == "note_x" and record["entities"] and record["regimens"]


def test_pipeline_uses_configured_child_variant(sample_note, mock_config):
    seen = []

    class Spy(MockGenerator):
        def generate(self, messages, **overrides):
            seen.append(messages[1]["content"])
            return super().generate(messages, **overrides)

    cfg = copy.deepcopy(mock_config)
    cfg["prompts"] = {"child_variant": "v1"}
    record = FamilyCarePipeline(cfg, generator=Spy()).run(sample_note, "t")
    assert record["metadata"]["child_variant"] == "v1"
    assert any(CHILD_INSTRUCTIONS["v1"] in s for s in seen) and not any(CHILD_INSTRUCTIONS["v2"] in s for s in seen)
