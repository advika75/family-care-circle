"""Tests for src/demo.py: the Streamlit demo's pure (non-UI) helpers."""

from __future__ import annotations

from src.demo import ENTITY_COLORS, highlight_entities, persona_badges, persona_output_text


def test_highlight_entities_wraps_spans_and_escapes_html():
    text = "Take <Drug> 500 mg BID."
    entities = [{"text": "500 mg", "label": "DOSAGE", "start": 11, "end": 17},
                {"text": "BID", "label": "FREQUENCY", "start": 18, "end": 21}]
    html = highlight_entities(text, entities)
    assert "&lt;Drug&gt;" in html
    assert f'background:{ENTITY_COLORS["DOSAGE"]}' in html and ">500 mg<" in html
    assert f'background:{ENTITY_COLORS["FREQUENCY"]}' in html and ">BID<" in html


def test_highlight_entities_skips_overlapping_span_instead_of_crashing():
    text = "Amoxicillin 500 mg"
    entities = [{"text": "Amoxicillin 500", "label": "MEDICATION", "start": 0, "end": 15},
                {"text": "500 mg", "label": "DOSAGE", "start": 12, "end": 18}]  # overlaps the first
    html = highlight_entities(text, entities)
    assert "Amoxicillin 500" in html  # first span renders; the overlapping one is skipped, not crashed on


def test_persona_output_text_bullets_checklist_but_not_prose():
    record = {"caregiver_checklist": ["Give medicine", "Call doctor"], "patient_summary": "You have a cold."}
    assert persona_output_text(record, "caregiver_checklist") == "- Give medicine\n- Call doctor"
    assert persona_output_text(record, "patient_summary") == "You have a cold."


def _record(**meta_overrides):
    meta = {"retries": {"patient_summary": 0}, "missing_first_attempt": {"patient_summary": []},
            "missing_after_retries": {"patient_summary": []}, "truncated": {"patient_summary": False},
            "redacted_dosages": {"patient_summary": []}}
    meta.update(meta_overrides)
    return {"patient_summary": "Take amoxicillin 500 mg twice a day.", "entities": [
        {"text": "Amoxicillin", "label": "MEDICATION", "start": 0, "end": 0},
        {"text": "500 mg", "label": "DOSAGE", "start": 0, "end": 0},
    ], "metadata": meta}


def test_persona_badges_clean_output_has_no_warning_badges():
    """A clean generation still shows the informational retention badge, but no retry/fallback/flag ones."""
    record = _record()
    badges = persona_badges(record, "patient_summary", "Amoxicillin 500 mg twice a day for 10 days.")
    assert badges == ["✅ retention: 100% (2 required facts, final text)"]


def test_persona_badges_flags_retry_fallback_and_truncation():
    record = _record(retries={"patient_summary": 2}, missing_after_retries={"patient_summary": ["10 days"]},
                      truncated={"patient_summary": True})
    badges = persona_badges(record, "patient_summary", "Amoxicillin 500 mg twice a day for 10 days.")
    assert any("retried 2x" in b for b in badges)
    assert any("fallback-appended: 10 days" in b for b in badges)
    assert any("truncated" in b for b in badges)


def test_persona_badges_flags_redacted_dose_and_hallucinated_medication():
    record = _record(redacted_dosages={"patient_summary": ["20 mg"]})
    record["patient_summary"] = "Take the dose your care team prescribed. Also take aspirin."
    badges = persona_badges(record, "patient_summary", "Amoxicillin 500 mg twice a day for 10 days.")
    assert any("redacted a dose" in b and "20 mg" in b for b in badges)
    assert any("medication not in the note" in b and "aspirin" in b for b in badges)
