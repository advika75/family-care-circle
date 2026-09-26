"""Tests for src/generator.py: backend selection, mock behavior and truncation detection."""

from __future__ import annotations

from types import SimpleNamespace

from src.generator import LlamaCppGenerator, MockGenerator, TransformersGenerator, build_generator
from src.prompts import build_messages


def test_build_generator_rejects_unknown_backend(mock_config):
    mock_config["backend"] = "gpt"
    try:
        build_generator(mock_config)
    except ValueError as exc:
        assert "Unknown backend" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_mock_backend_is_selected_and_needs_no_model(mock_config):
    gen = build_generator(mock_config)
    assert isinstance(gen, MockGenerator) and gen.backend == "mock" and gen.model_id == "mock"


def test_mock_writes_must_include_facts(sample_note):
    from src.ner import extract_entities, group_regimens

    ents = extract_entities(sample_note)
    labels = ["MEDICATION", "DOSAGE", "FREQUENCY", "DURATION"]
    msgs = build_messages("caregiver_checklist", sample_note, ents, group_regimens(ents, sample_note), labels)
    out = MockGenerator().generate(msgs)
    assert "- Give amoxicillin, 500 mg, twice a day, for 10 days." in out


def test_mock_fail_first_and_truncation():
    gen = MockGenerator({"max_new_tokens": 5}, fail_first=1)
    msgs = [{"role": "user", "content": "AUDIENCE: child\nhello"}]
    assert gen.generate(msgs) == "" and gen.last_truncated is False
    text = gen.generate(msgs)
    assert len(text.split(" ")) == 5 and gen.last_truncated is True
    assert gen.generate(msgs, max_new_tokens=500) and gen.last_truncated is False


def test_configure_resets_defaults_and_seed():
    gen = MockGenerator({"temperature": 0.2, "seed": 1})
    gen.configure({"temperature": 0.7, "seed": 2})
    assert gen.params()["temperature"] == 0.7 and gen.seed == 2
    assert gen.params(temperature=None, top_p=0.5)["top_p"] == 0.5


def test_llama_cpp_finish_reason_sets_flag():
    gen = LlamaCppGenerator.__new__(LlamaCppGenerator)
    gen.configure({})
    gen.llm = SimpleNamespace(create_chat_completion=lambda **kw: {
        "choices": [{"message": {"content": "cut off mid"}, "finish_reason": "length"}]})
    assert gen.generate([{"role": "user", "content": "x"}]) == "cut off mid" and gen.last_truncated is True
    gen.llm = SimpleNamespace(create_chat_completion=lambda **kw: {
        "choices": [{"message": {"content": "done."}, "finish_reason": "stop"}]})
    gen.generate([{"role": "user", "content": "x"}])
    assert gen.last_truncated is False


def test_transformers_limit_detection():
    gen = TransformersGenerator.__new__(TransformersGenerator)
    gen.model = SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=[2, 7]))
    gen.tokenizer = SimpleNamespace(eos_token_id=2)
    assert gen._hit_limit([5, 6, 8, 9], 4) is True       # used every token, no EOS
    assert gen._hit_limit([5, 6, 8, 7], 4) is False      # ended with an EOS id
    assert gen._hit_limit([5, 6], 4) is False            # stopped early
