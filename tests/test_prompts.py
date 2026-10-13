"""Tests for src/prompts.py."""

from __future__ import annotations

import pytest

from src.ner import extract_entities, group_regimens
from src.prompts import CHILD_INSTRUCTIONS, SYSTEM_PROMPT, build_messages, build_retry_messages, format_must_include

LABELS = ["MEDICATION", "DOSAGE", "FREQUENCY", "DURATION"]


def test_must_include_lists_regimens_with_glosses(sample_note):
    ents = extract_entities(sample_note)
    block = format_must_include(ents, group_regimens(ents, sample_note), LABELS)
    assert block.startswith("MUST INCLUDE")
    assert "- Medication: Amoxicillin | dose: 500 mg | how often: BID (twice a day) | how long: 10 days" in block
    assert "q6h (every 6 hours)" in block
    assert format_must_include(ents, [], []) == ""        # nothing required (child persona)


def test_one_prompt_per_persona_with_system_prompt(sample_note):
    ents = extract_entities(sample_note)
    regs = group_regimens(ents, sample_note)
    for persona, audience in (("patient_summary", "patient"), ("caregiver_checklist", "caregiver"),
                              ("child_explanation", "child")):
        msgs = build_messages(persona, sample_note, ents, regs, LABELS)
        assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert f"AUDIENCE: {audience}" in msgs[1]["content"] and sample_note.strip() in msgs[1]["content"]
    with pytest.raises(ValueError):
        build_messages("doctor", sample_note, ents, regs, LABELS)


def test_inject_entities_false_removes_entity_blocks(sample_note):
    ents = extract_entities(sample_note)
    user = build_messages("patient_summary", sample_note, ents, group_regimens(ents, sample_note), LABELS,
                          inject_entities=False)[1]["content"]
    assert "MUST INCLUDE" not in user and "Health problems:" not in user


def test_retry_messages_name_missing_facts():
    msgs = [{"role": "user", "content": "x"}]
    retry = build_retry_messages(msgs, "draft", [{"text": "10 days", "label": "DURATION"}])
    assert retry[-2] == {"role": "assistant", "content": "draft"} and "10 days (duration)" in retry[-1]["content"]
    assert "empty" in build_retry_messages(msgs, "", [])[-1]["content"]


def test_retry_messages_name_hallucinated_medication():
    msgs = [{"role": "user", "content": "x"}]
    retry = build_retry_messages(msgs, "draft", [], ["aspirin"])
    assert "aspirin" in retry[-1]["content"] and "not in the patient's note" in retry[-1]["content"]


def test_child_prompt_variants(sample_note):
    v1 = build_messages("child_explanation", sample_note, [], [], [], child_variant="v1")[1]["content"]
    v2 = build_messages("child_explanation", sample_note, [], [], [], child_variant="v2")[1]["content"]
    assert CHILD_INSTRUCTIONS["v1"] in v1 and CHILD_INSTRUCTIONS["v2"] in v2
    assert "fewer than 8 words" in v2 and "Never name a medicine" in v2 and "exactly one comforting analogy" in v2
    assert build_messages("patient_summary", sample_note, [], [], [], child_variant="v1") == \
        build_messages("patient_summary", sample_note, [], [], [], child_variant="v2")
    with pytest.raises(ValueError, match="child_variant"):
        build_messages("child_explanation", sample_note, [], [], [], child_variant="v3")
