"""Pure helpers for scripts/demo_app.py, kept dependency-free of streamlit so they're unit-testable."""

from __future__ import annotations

from html import escape
from typing import Any

from src.evaluator import persona_text

ENTITY_COLORS = {  # same palette as scripts/annotate_mtsamples.py, for a consistent visual language
    "MEDICATION": "#d9f4e5", "DOSAGE": "#ffe6bd", "FREQUENCY": "#dceaff",
    "DURATION": "#f0ddff", "CONDITION": "#ffd9df", "SYMPTOM": "#fff5b8",
}


def highlight_entities(text: str, entities: list[dict[str, Any]]) -> str:
    """Render ``text`` as HTML with each entity span wrapped in a colored tag."""
    ordered = sorted(entities, key=lambda e: e["start"])
    parts, pos = [], 0
    for e in ordered:
        if e["start"] < pos:
            continue  # overlapping span from an upstream extractor bug; skip rather than render garbled HTML
        parts.append(escape(text[pos:e["start"]]))
        color = ENTITY_COLORS.get(e["label"], "#eee")
        parts.append(f'<span style="background:{color};border-radius:3px;padding:1px 3px" '
                      f'title="{escape(e["label"])}">{escape(e["text"])}</span>')
        pos = e["end"]
    parts.append(escape(text[pos:]))
    return "".join(parts)


def persona_output_text(record: dict[str, Any], persona: str) -> str:
    """Caregiver checklist as a bulleted block; other personas as-is."""
    if persona == "caregiver_checklist":
        return "\n".join(f"- {item}" for item in record.get(persona, []))
    return persona_text(record, persona)


def persona_badges(record: dict[str, Any], persona: str, source: str) -> list[str]:
    """Status badges for one persona's output: retries, fallback, truncation, redaction, hallucination flags."""
    from src.evaluator import entity_retention, unsupported_meds, unsupported_numbers

    meta = record.get("metadata", {})
    text_out = persona_output_text(record, persona)
    badges: list[str] = []
    first_missing = meta.get("missing_first_attempt", {}).get(persona, [])
    if first_missing:
        badges.append(f"ℹ️ model missed on first attempt: {', '.join(first_missing)}")
    if meta.get("retries", {}).get(persona):
        badges.append(f"\U0001f501 retried {meta['retries'][persona]}x")
    fallback_facts = meta.get("missing_after_retries", {}).get(persona, [])
    if fallback_facts:
        badges.append(f"\U0001fa79 fallback-appended: {', '.join(fallback_facts)}")
    if meta.get("truncated", {}).get(persona):
        badges.append("✂️ generation was truncated (hit max_new_tokens)")
    redacted = meta.get("redacted_dosages", {}).get(persona, [])
    if redacted:
        badges.append(f"\U0001f6d1 redacted a dose not in the note: {', '.join(redacted)}")
    hallucinated_meds = unsupported_meds(text_out, source, record.get("entities", []))["unsupported"]
    if hallucinated_meds:
        badges.append(f"\U0001f6a9 medication not in the note: {', '.join(hallucinated_meds)}")
    hallucinated_nums = unsupported_numbers(text_out, source, record.get("entities", []))["unsupported"]
    if hallucinated_nums:
        badges.append(f"\U0001f6a9 number not in the note: {', '.join(hallucinated_nums)}")
    if persona in ("patient_summary", "caregiver_checklist"):
        ret = entity_retention(record.get("entities", []), text_out)
        if ret["n"]:
            badges.append(f"✅ retention: {ret['overall'] * 100:.0f}% ({ret['n']} required facts, final text)")
    return badges
