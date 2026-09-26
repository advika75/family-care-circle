"""Tests for the rule-based NER and regimen grouping."""

from __future__ import annotations

from src.ner import EntityExtractor, extract_entities, group_regimens, merge_entities


def _pairs(entities):
    return {(e["text"], e["label"]) for e in entities}


def test_extracts_core_regimen_entities(sample_note):
    pairs = _pairs(extract_entities(sample_note))
    assert ("Amoxicillin", "MEDICATION") in pairs
    assert ("500 mg", "DOSAGE") in pairs
    assert ("BID", "FREQUENCY") in pairs
    assert ("10 days", "DURATION") in pairs
    assert ("q6h", "FREQUENCY") in pairs
    assert ("PRN", "FREQUENCY") in pairs


def test_extracts_conditions_and_symptoms(sample_note):
    pairs = _pairs(extract_entities(sample_note))
    assert ("Streptococcal pharyngitis", "CONDITION") in pairs
    assert ("strep throat", "CONDITION") in pairs
    assert ("sore throat", "SYMPTOM") in pairs


def test_offsets_match_text(sample_note):
    for ent in extract_entities(sample_note):
        assert sample_note[ent["start"]:ent["end"]] == ent["text"]
        assert set(ent) == {"text", "label", "start", "end"}


def test_no_overlapping_spans():
    text = "Take metformin 1000 mg twice daily for 2 weeks, then once daily."
    ents = sorted(extract_entities(text), key=lambda e: e["start"])
    for a, b in zip(ents, ents[1:]):
        assert a["end"] <= b["start"]
    pairs = _pairs(ents)
    assert ("twice daily", "FREQUENCY") in pairs and ("once daily", "FREQUENCY") in pairs
    assert ("daily", "FREQUENCY") not in pairs  # longest match wins


def test_dosage_and_frequency_variants():
    text = "Albuterol 90 mcg 2 puffs every 4 hours as needed; sacubitril-valsartan 24/26 mg q4-6h; 500mg QID."
    pairs = _pairs(extract_entities(text))
    for expected in [("90 mcg", "DOSAGE"), ("2 puffs", "DOSAGE"), ("24/26 mg", "DOSAGE"), ("500mg", "DOSAGE"),
                     ("every 4 hours", "FREQUENCY"), ("as needed", "FREQUENCY"), ("q4-6h", "FREQUENCY"),
                     ("QID", "FREQUENCY"), ("sacubitril-valsartan", "MEDICATION")]:
        assert expected in pairs, expected


def test_duration_patterns():
    text = "Prednisolone daily for 4 more days. Oxycodone for up to 3 days. A 10-day course. Nitrofurantoin x 5 days."
    durations = {e["text"] for e in extract_entities(text) if e["label"] == "DURATION"}
    assert durations == {"4 more days", "3 days", "10-day", "5 days"}


def test_ignores_vitals_and_labs():
    text = "Fever to 101.8 F. HbA1c 8.9%. BP 154/96. No lifting over 10 lbs."
    assert not [e for e in extract_entities(text) if e["label"] == "DOSAGE"]


def test_group_regimens(sample_note):
    regimens = group_regimens(extract_entities(sample_note), sample_note)
    amox = next(r for r in regimens if r["medication"] == "Amoxicillin")
    assert amox == {"medication": "Amoxicillin", "dosages": ["500 mg"], "frequencies": ["BID"], "durations": ["10 days"]}
    ibu = next(r for r in regimens if r["medication"] == "Ibuprofen")
    assert ibu["frequencies"] == ["q6h", "PRN"]


def test_group_regimens_drops_bare_repeat_mentions():
    text = "Ibuprofen 200 mg q6h.\nAcetaminophen 325 mg if ibuprofen not tolerated."
    meds = [r["medication"] for r in group_regimens(extract_entities(text), text)]
    assert meds == ["Ibuprofen", "Acetaminophen"]


def test_group_regimens_drops_repeat_mentions_with_known_details():
    text = "Albuterol 90 mcg every 4 hours as needed.\nCall if albuterol needed more often than every 4 hours."
    regimens = group_regimens(extract_entities(text), text)
    assert [r["medication"] for r in regimens] == ["Albuterol"]


def test_merge_prefers_primary_on_overlap():
    primary = [{"text": "500 mg", "label": "DOSAGE", "start": 0, "end": 6}]
    secondary = [{"text": "500", "label": "DOSAGE", "start": 0, "end": 3},
                 {"text": "rash", "label": "SYMPTOM", "start": 10, "end": 14}]
    merged = merge_entities(primary, secondary)
    assert [e["text"] for e in merged] == ["500 mg", "rash"]


def test_extractor_defaults_to_rules(sample_note):
    assert EntityExtractor({"use_hf_model": False}).extract(sample_note) == extract_entities(sample_note)
