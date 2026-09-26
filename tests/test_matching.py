"""Tests for entity normalization and presence checks (src/matching.py)."""

from __future__ import annotations

import pytest

from src.matching import contains_entity, find_missing, frequency_variants, normalize, plain_frequency, unique_entities


@pytest.mark.parametrize("entity,text", [
    ({"text": "500 mg", "label": "DOSAGE"}, "take 500mg now"),
    ({"text": "500mg", "label": "DOSAGE"}, "take 500 milligrams now"),
    ({"text": "10 days", "label": "DURATION"}, "for ten days"),
    ({"text": "10-day", "label": "DURATION"}, "for 10 days"),
    ({"text": "BID", "label": "FREQUENCY"}, "twice a day"),
    ({"text": "twice daily", "label": "FREQUENCY"}, "Take it BID."),
    ({"text": "q4-6h", "label": "FREQUENCY"}, "every 4 to 6 hours"),
    ({"text": "q6h", "label": "FREQUENCY"}, "every 6 hours"),
    ({"text": "PRN", "label": "FREQUENCY"}, "only as needed"),
    ({"text": "Amoxicillin", "label": "MEDICATION"}, "AMOXICILLIN"),
])
def test_contains_entity_normalization(entity, text):
    assert contains_entity(text, entity)


@pytest.mark.parametrize("entity,text", [
    ({"text": "50 mg", "label": "DOSAGE"}, "take 500 mg"),
    ({"text": "5 days", "label": "DURATION"}, "for 15 days"),
    ({"text": "BID", "label": "FREQUENCY"}, "three times a day"),
])
def test_contains_entity_no_false_positive(entity, text):
    assert not contains_entity(text, entity)


def test_normalize_and_plain_frequency():
    assert normalize("500 mg") == normalize("500mg") == "500mg"
    assert plain_frequency("BID") == "twice a day"
    assert plain_frequency("q4-6h") == "every 4 to 6 hours"
    assert plain_frequency("twice a day") is None


def test_frequency_variants_and_unique_entities():
    assert {"2 time a day", "bid", "every 12 hour"} <= frequency_variants("twice daily")
    assert "every 4 to 6 hour" in frequency_variants("q4-6h")
    ents = [{"text": "500 mg", "label": "DOSAGE"}, {"text": "500mg", "label": "DOSAGE"},
            {"text": "BID", "label": "FREQUENCY"}]
    assert [e["text"] for e in unique_entities(ents)] == ["500 mg", "BID"]
    assert unique_entities(ents, ["FREQUENCY"]) == [ents[2]]
    assert find_missing("take 500mg", ents) == [ents[2]]
