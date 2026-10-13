"""Prompt templates: one shared system prompt plus one user template per persona.

Each persona is generated in its own call. Extracted entities are injected as a
"MUST INCLUDE" block so the model keeps medications, doses, frequencies and durations.
The block has a fixed line format (``- Medication: X | dose: Y | how often: Z | how long: W``)
which the mock backend also parses.
"""

from __future__ import annotations

from typing import Any

from src.matching import normalize, plain_frequency, unique_entities

PERSONAS = ("patient_summary", "caregiver_checklist", "child_explanation")

SYSTEM_PROMPT = (
    "You are a careful medical communication assistant. You rewrite clinical notes so that "
    "patients and families can understand them.\n"
    "Rules:\n"
    "1. Use only facts that are in the note. Never invent medicines, doses, tests or advice.\n"
    "2. Keep every medicine name, dose, frequency and duration exactly correct. You may explain "
    "abbreviations in plain words (for example BID means twice a day).\n"
    "3. Do not change the treatment plan. If something is unclear, tell the reader to ask their care team.\n"
    "4. Output only the requested text: no preamble, no JSON, no code fences."
)

PERSONA_INSTRUCTIONS = {
    "patient_summary": (
        "AUDIENCE: patient\n"
        "Write a warm, empathetic summary for the patient in plain language (about a 6th-grade reading level). "
        "Avoid medical jargon; if you must use a medical word, explain it. Use short paragraphs: what is going on, "
        "what medicines to take and how, and when to get help. Speak directly to the patient as \"you\". "
        "Keep it under 250 words."
    ),
    "caregiver_checklist": (
        "AUDIENCE: caregiver\n"
        "Write an action-oriented checklist for the family member or caregiver. Output ONLY bullet points, one "
        "action per line, each starting with \"- \" and a verb (Give, Check, Watch for, Call, Schedule). Include "
        "one bullet per medicine with its dose, how often and for how long, then bullets for monitoring, "
        "warning signs and follow-up. 6 to 12 bullets."
    ),
}

# Child prompt variants (prompts.child_variant in config.yaml). v1 is the original prompt, kept for the
# v1-vs-v2 ablation; v2 states hard, checkable rules.
CHILD_INSTRUCTIONS = {
    "v1": (
        "AUDIENCE: child\n"
        "Explain what is happening to a young child (about 1st-grade reading level). Use very short sentences "
        "and simple words. Use one or two gentle, comforting analogies (for example, medicine as helpers or "
        "a superhero team). Be reassuring and never scary. Do not list doses or numbers. Mention that the "
        "grown-ups and doctors are taking care of them. Keep it under 120 words."
    ),
    "v2": (
        "AUDIENCE: child\n"
        "Explain what is happening to a young child (5 to 7 years old). Follow every rule:\n"
        "- Every sentence has fewer than 8 words.\n"
        "- Never name a medicine. Say \"medicine\" instead.\n"
        "- Never write a number or a dose. For time, only say \"a few days\" or \"some days\".\n"
        "- Use exactly one comforting analogy (for example, medicine is like a team of tiny helpers).\n"
        "- Talk to the child as \"you\". Be warm and never scary.\n"
        "- Say that the grown-ups and doctors are taking care of them.\n"
        "Write 5 to 8 sentences."
    ),
}
PERSONA_INSTRUCTIONS["child_explanation"] = CHILD_INSTRUCTIONS["v2"]


def _regimen_line(regimen: dict[str, Any]) -> str:
    parts = [f"- Medication: {regimen['medication']}"]
    if regimen["dosages"]:
        parts.append(f"dose: {', '.join(regimen['dosages'])}")
    if regimen["frequencies"]:
        freqs = []
        for f in regimen["frequencies"]:
            plain = plain_frequency(f)
            freqs.append(f"{f} ({plain})" if plain else f)
        parts.append(f"how often: {', '.join(freqs)}")
    if regimen["durations"]:
        parts.append(f"how long: {', '.join(regimen['durations'])}")
    return " | ".join(parts)


def format_must_include(
    entities: list[dict[str, Any]], regimens: list[dict[str, Any]], required_labels: list[str]
) -> str:
    """Render the MUST INCLUDE block: medication regimens plus any required entities not covered by them."""
    if not required_labels:
        return ""
    lines = []
    covered: set[str] = set()
    if "MEDICATION" in required_labels:
        for reg in regimens:
            lines.append(_regimen_line(reg))
            covered.update(normalize(t) for t in [reg["medication"], *reg["dosages"], *reg["frequencies"], *reg["durations"]])
    for ent in unique_entities(entities, required_labels):
        if normalize(ent["text"]) not in covered:
            text = ent["text"]
            if ent["label"] == "FREQUENCY" and plain_frequency(text):
                text = f"{text} ({plain_frequency(text)})"
            lines.append(f"- Other {ent['label'].lower()}: {text}")
    if not lines:
        return ""
    return "MUST INCLUDE (every item below must appear in your answer):\n" + "\n".join(lines)


def format_context(entities: list[dict[str, Any]]) -> str:
    """One line listing the health problems (conditions and symptoms) found in the note."""
    names = [e["text"] for e in unique_entities(entities, ["CONDITION"])]
    symptoms = [e["text"] for e in unique_entities(entities, ["SYMPTOM"])]
    lines = []
    if names:
        lines.append(f"Health problems: {'; '.join(names)}")
    if symptoms:
        lines.append(f"Symptoms mentioned: {'; '.join(symptoms)}")
    return "\n".join(lines)


def build_messages(
    persona: str,
    note: str,
    entities: list[dict[str, Any]],
    regimens: list[dict[str, Any]],
    required_labels: list[str],
    inject_entities: bool = True,
    child_variant: str = "v2",
) -> list[dict[str, str]]:
    """Build chat messages (system + user) for one persona.

    With ``inject_entities=False`` (ablation) the prompt contains only the instructions and the note.
    ``child_variant`` picks the child prompt (``v1`` original, ``v2`` strict rules).
    """
    if persona not in PERSONA_INSTRUCTIONS:
        raise ValueError(f"Unknown persona: {persona}")
    if persona == "child_explanation":
        if child_variant not in CHILD_INSTRUCTIONS:
            raise ValueError(f"Unknown child_variant '{child_variant}'. Use one of {sorted(CHILD_INSTRUCTIONS)}.")
        instructions = CHILD_INSTRUCTIONS[child_variant]
    else:
        instructions = PERSONA_INSTRUCTIONS[persona]
    sections = [
        instructions,
        f"CLINICAL NOTE:\n\"\"\"\n{note.strip()}\n\"\"\"",
        format_context(entities) if inject_entities else "",
        format_must_include(entities, regimens, required_labels) if inject_entities else "",
        "Now write your answer.",
    ]
    user = "\n\n".join(s for s in sections if s)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def build_retry_messages(
    messages: list[dict[str, str]], previous_output: str, missing: list[dict[str, Any]],
    hallucinated: list[str] = (),
) -> list[dict[str, str]]:
    """Extend a conversation with the previous attempt and feedback about what was missing or invented."""
    parts = []
    if missing:
        items = ", ".join(f"{m['text']} ({m['label'].lower()})" for m in missing)
        parts.append(f"Your answer left out these required facts: {items}.")
    if hallucinated:
        items = ", ".join(hallucinated)
        parts.append(
            f"Your answer mentions medication(s) that are not in the patient's note: {items}. Remove any "
            "medication, dose or instruction that the note does not actually state."
        )
    if parts:
        feedback = " ".join(parts) + " Rewrite the whole answer so that it follows the same instructions."
    else:
        feedback = "Your answer was empty. Please write the full answer following the instructions."
    return [
        *messages,
        {"role": "assistant", "content": previous_output or "(empty)"},
        {"role": "user", "content": feedback},
    ]
