"""Formatting helpers for templates. Pure text shaping: NO permission decisions are made here, and nothing here
can add data that the service layer did not already return for the viewer's role."""

from __future__ import annotations

from typing import Any

PERSONA_NAMES = {"patient_summary": "Patient summary", "caregiver_checklist": "Caregiver checklist",
                 "child_explanation": "Child explanation"}
GATE_REASONS = {"digit": "it contained a number", "medication_name": "it named a medicine",
                "too_long": "it was too long", "empty": "it was empty",
                "number_word": "it contained a spelled-out number or dose word", "unit_word": "it contained a unit such as mg or tablet",
                "denylist": "it contained a frightening word"}


def paragraphs(text: str | None) -> list[str]:
    """Split generated text into paragraphs (blank lines separate them; single line breaks are kept inside one)."""
    blocks, current = [], []
    for line in (text or "").splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return blocks


def _pct(value: Any) -> str:
    return "not measured" if value is None else f"{round(float(value) * 100)}%"


def flag_summary(flags: dict[str, Any]) -> dict[str, Any]:
    """Turn the stored review flags into (a) things a reviewer should look at and (b) a plain table of facts."""
    attention: list[str] = []
    for persona, used in (flags.get("fallback_used") or {}).items():
        if used:
            added = (flags.get("appended_by_fallback") or {}).get(persona) or []
            extra = f" ({', '.join(added)})" if added else ""
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: details were added automatically because the draft "
                             f"left them out{extra}. Check them against the note.")
    for persona, cut in (flags.get("truncated") or {}).items():
        if cut:
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: the text was cut off at the length limit.")
    for persona, doses in (flags.get("redacted_dosages") or {}).items():
        if doses:
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: a dose that contradicted the note was removed "
                             f"({', '.join(doses)}). Check the dose.")
    for persona, found in (flags.get("unsupported") or {}).items():
        if found.get("medications"):
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: mentions a medicine that is not in the note "
                             f"({', '.join(found['medications'])}).")
        if found.get("numbers"):
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: contains numbers that are not in the note "
                             f"({', '.join(found['numbers'])}).")
    for persona, ret in (flags.get("retention") or {}).items():
        if ret.get("overall") is not None and ret["overall"] < 1:
            attention.append(f"{PERSONA_NAMES.get(persona, persona)}: only {_pct(ret['overall'])} of the medicines, doses, "
                             f"timings and durations in the note appear in the text.")
    gate = flags.get("child_gate") or {}
    if gate.get("fired"):
        why = ", ".join(GATE_REASONS.get(r, r) for r in gate.get("reasons", []))
        attention.append(f"The child explanation was withheld by the safety check ({why}). The child sees a short, "
                         "general message instead.")
    for err in flags.get("validation_errors") or []:
        attention.append(f"Format problem: {err}")

    rows: list[tuple[str, str]] = []
    retries = flags.get("retries") or {}
    for persona in ("patient_summary", "caregiver_checklist", "child_explanation"):
        if persona in retries:
            rows.append((f"{PERSONA_NAMES[persona]}: retries", str(retries[persona])))
    for persona, ret in (flags.get("retention") or {}).items():
        rows.append((f"{PERSONA_NAMES.get(persona, persona)}: facts kept", f"{_pct(ret.get('overall'))} of {ret.get('n_required', 0)}"))
    rows.append(("Child safety check", "Withheld" if gate.get("fired") else "Passed"))
    rows.append(("Model", str(flags.get("model_id") or "unknown")))
    if flags.get("model_hash"):
        rows.append(("Model file hash", str(flags["model_hash"])[:23] + "…"))
    return {"attention": attention, "rows": rows}
