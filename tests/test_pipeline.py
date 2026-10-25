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
    meta = record["metadata"]
    assert set(meta["first_attempt_text"]) == {"patient_summary", "caregiver_checklist", "child_explanation"}
    for persona, evidence in meta["first_attempt_evidence"].items():
        assert evidence["note_id"] == "t2" and evidence["persona"] == persona
        assert evidence["attempt_count"] == 2 and evidence["retry_status"] and evidence["retry_count"] == 1
        assert evidence["model_config"]["backend"] == "mock"
        assert evidence["model_config"]["generation_params"]
        assert evidence["output_references"]["first_attempt_text"].endswith(
            f"#/metadata/first_attempt_text/{persona}")
        assert evidence["output_references"]["final_output"] == f"t2.json#/{persona}"
        assert meta["first_attempt_text"][persona] == ""  # the failed empty draft is preserved exactly
        assert record[persona]  # the later successful retry remains the final output


def test_pipeline_records_truncation_per_persona(sample_note, mock_config):
    cfg = copy.deepcopy(mock_config)
    cfg["personas"]["patient_summary"]["max_new_tokens"] = 10
    record = FamilyCarePipeline(cfg).run(sample_note, "t")
    meta = record["metadata"]
    assert meta["truncated"] == {"patient_summary": True, "caregiver_checklist": False, "child_explanation": False}
    assert all(meta["truncated_attempts"]["patient_summary"])        # every attempt was cut off
    assert meta["missing_first_attempt"]["patient_summary"]           # the cut text lost facts
    assert meta["first_attempt_text"]["patient_summary"]
    assert meta["first_attempt_text"]["patient_summary"] != record["patient_summary"]
    assert meta["first_attempt_evidence"]["patient_summary"]["fallback_status"]


def test_metadata_fields(sample_note, mock_config):
    record = FamilyCarePipeline(mock_config).run(sample_note, "note_x")
    meta = record["metadata"]
    for key in ("backend", "model_id", "model_hash", "generation_params", "seed", "retries", "fallback_used",
                "truncated", "latency_sec", "valid", "missing_first_attempt", "missing_after_retries",
                "child_variant"):
        assert key in meta, key
    assert meta["model_hash"] is None  # mock backend has no model file to fingerprint
    assert set(meta["latency_sec"]) == {"patient_summary", "caregiver_checklist", "child_explanation", "total"}
    assert record["id"] == "note_x" and record["entities"] and record["regimens"]


def test_pipeline_redacts_contradicted_dosage_directive(mock_config):
    """Regression for mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit: a generated caregiver instruction
    asserted "give 20 mg" when the note's only DOSAGE entity is 40 mg; the pipeline must not ship the
    wrong directive, and must record it as a forced fallback."""
    note = "Patient ingested Celesta 40 mg tablets. Mom should watch for drowsiness.\n"

    class WrongDoseGenerator(MockGenerator):
        def generate(self, messages, **overrides):
            prompt = next(m["content"] for m in messages if m["role"] == "user" and "AUDIENCE:" in m["content"])
            if "caregiver" in prompt.lower():
                self.last_truncated = False
                return "- Give the patient 20 mg of Celesta in the morning.\n- Watch for drowsiness."
            return super().generate(messages, **overrides)

    record = FamilyCarePipeline(mock_config, generator=WrongDoseGenerator()).run(note, "celesta")
    checklist_text = " ".join(record["caregiver_checklist"])
    assert "20 mg" not in checklist_text
    assert record["metadata"]["fallback_used"]["caregiver_checklist"]
    assert record["metadata"]["redacted_dosages"]["caregiver_checklist"] == ["20 mg"]


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
