"""Cleaning, retry loop, fallback and schema validation for generated persona text."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from src.evaluator import unsupported_meds
from src.matching import find_missing, normalize
from src.prompts import PERSONAS, build_retry_messages

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*\n?(.*?)```", re.DOTALL)
_SPECIAL_TOKEN_RE = re.compile(r"<\|[^|>]{1,40}\|>|</?s>")
_PREAMBLE_RE = re.compile(
    r"^\s*(?:sure|certainly|of course|okay|ok|here(?:'s| is| are)|below is)\b[^\n]*?(?::|!|\.)\s*\n",
    re.IGNORECASE,
)
_ROLE_PREFIX_RE = re.compile(r"^\s*(?:assistant|answer|output|response)\s*:\s*", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|\[\s?[xX ]?\s?\])\s+")
_DOSE_UNIT = r"mg|mcg|g|ml|meq|iu|units?"
# A dosing verb followed, within a short gap, by a number + dose unit: "give ... 20 mg", "administer 5mL".
_DOSE_DIRECTIVE_RE = re.compile(
    rf"\b(?:give|administer|take|dose)\b[^.?!\n]{{0,40}}?(\d+(?:\.\d+)?)\s?({_DOSE_UNIT})\b", re.IGNORECASE
)

# Used only when every attempt came back empty.
EMPTY_FALLBACK = {
    "patient_summary": "We could not create a summary. Please ask your care team to go over your visit notes with you.",
    "caregiver_checklist": "- Ask the care team to review the treatment plan and medicines with you.",
    "child_explanation": "Your doctors and grown-ups are taking good care of you. You can ask them any questions.",
}


def clean_output(text: str | None, persona: str | None = None) -> str:
    """Strip code fences, chat-template leftovers, preambles, role prefixes and JSON wrappers."""
    if not text:
        return ""
    t = _SPECIAL_TOKEN_RE.sub("", text)
    fenced = _FENCE_RE.findall(t)
    if fenced:
        t = max(fenced, key=len)
    t = t.replace("```", "")
    t = _unwrap_json(t, persona)
    t = _ROLE_PREFIX_RE.sub("", t)
    t = _PREAMBLE_RE.sub("", t, count=1)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _unwrap_json(text: str, persona: str | None) -> str:
    """If the model returned JSON despite instructions, pull out the relevant string value."""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return text
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    if not isinstance(data, dict) or not data:
        return text
    value = data.get(persona) if persona in data else next(iter(data.values()))
    if isinstance(value, list):
        return "\n".join(f"- {v}" for v in value)
    return str(value)


def parse_checklist(text: str) -> list[str]:
    """Split checklist text into items, dropping bullet markers, headings and blank lines."""
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_bullet = bool(_BULLET_RE.match(line))
        line = _BULLET_RE.sub("", line).strip()
        if not is_bullet and line.endswith(":"):
            continue  # headings such as "Medicines:"
        if line:
            items.append(line)
    return items


def add_fallback(text: str, missing: list[dict[str, Any]], persona: str) -> str:
    """Append the still-missing facts explicitly so no required fact is silently dropped."""
    if not missing:
        return text
    if persona == "caregiver_checklist":
        extra = [f"- Confirm with the care team: {m['text']} ({m['label'].lower()})" for m in missing]
        return "\n".join(filter(None, [text.strip(), *extra]))
    listed = "; ".join(f"{m['text']} ({m['label'].lower()})" for m in missing)
    note = f"Important details from your care team's note: {listed}."
    return f"{text.strip()}\n\n{note}".strip()


def find_contradicted_dosages(text: str, source: str) -> list[dict[str, Any]]:
    """Directive dosing language ("give the patient 20 mg") whose dose appears nowhere in the source.

    Checks the normalized source text directly rather than NER-extracted DOSAGE entities, since the
    rule-based extractor misses spelled-out numbers and units ("81 milligrams", "One mL") that are
    nonetheless genuinely in the note; grounding against entities alone would flag those as
    contradictions and redact a fact that was actually correct.
    """
    if not text or not source:
        return []
    normalized_source = normalize(source)
    found = []
    for m in _DOSE_DIRECTIVE_RE.finditer(text):
        dose = f"{m.group(1)} {m.group(2)}"
        norm_dose = normalize(dose)
        if not re.search(rf"(?<![a-z0-9]){re.escape(norm_dose)}(?![a-z0-9])", normalized_source):
            found.append({"start": m.start(1), "end": m.end(2), "dose": dose})
    return found


def redact_contradicted_dosages(text: str, source: str) -> tuple[str, list[str]]:
    """Replace a directive dose that appears nowhere in the source note with a safe placeholder.

    A hard validation failure, not a retry: this runs on the attempt already kept (first-try success or
    post-fallback), so a wrong dose never reaches the final output even if it slipped past the retry loop.
    Returns the (possibly unchanged) text and the list of doses that were redacted.
    """
    contradictions = find_contradicted_dosages(text, source)
    if not contradictions:
        return text, []
    out = text
    for c in sorted(contradictions, key=lambda c: c["start"], reverse=True):
        out = f"{out[:c['start']]}the dose your care team prescribed{out[c['end']:]}"
    return out, [c["dose"] for c in contradictions]


@dataclass
class GenerationResult:
    """Outcome of generating one persona with retries."""

    text: str
    attempts: int
    retries: int
    first_attempt_text: str = ""
    missing: list[dict[str, Any]] = field(default_factory=list)
    fallback_used: bool = False
    first_missing: list[dict[str, Any]] = field(default_factory=list)
    used_attempt: int | None = None  # 0-based index of the attempt whose text was kept (None: all empty)
    hallucinated_meds: list[str] = field(default_factory=list)


def generate_with_retries(
    generate_fn: Callable[[list[dict[str, str]]], str],
    messages: list[dict[str, str]],
    required: list[dict[str, Any]],
    persona: str,
    max_retries: int = 2,
    source: str = "",
    entities: list[dict[str, Any]] = (),
) -> GenerationResult:
    """Generate, clean and check a persona text, retrying with feedback when it is empty, incomplete or
    mentions a medication the note doesn't.

    Retries happen when the cleaned output is empty, misses any ``required`` entity, or (when ``source``
    is given) names a medication that neither the source text nor ``entities`` supports. After
    ``max_retries`` retries, the attempt with the fewest combined issues is kept and the missing entities
    are appended by :func:`add_fallback`. If every attempt still contains an unsupported medication, a
    persona-specific safe fallback replaces that draft. The ``source``/``entities`` check is only engaged
    when ``source`` is non-empty, so callers that don't pass it see unchanged behavior.
    """
    best: tuple[str, int, list[dict[str, Any]], list[str], int] | None = None
    first_missing: list[dict[str, Any]] | None = None
    first_attempt_text: str | None = None
    convo = messages
    attempts = 0
    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        generated_text = generate_fn(convo)
        if first_attempt_text is None:
            first_attempt_text = generated_text
        text = clean_output(generated_text, persona)
        missing = find_missing(text, required) if text else list(required)
        hallucinated = unsupported_meds(text, source, entities)["unsupported"] if text and source else []
        if first_missing is None:
            first_missing = missing
        issues = len(missing) + len(hallucinated)
        if text and (best is None or issues < best[1]):
            best = (text, issues, missing, hallucinated, attempt)
        if text and not missing and not hallucinated:
            return GenerationResult(text=text, first_attempt_text=first_attempt_text or "", attempts=attempts,
                                    retries=attempt, first_missing=first_missing,
                                    used_attempt=attempt)
        logger.info("%s attempt %d: %s", persona, attempts,
                    "empty output" if not text else f"{len(missing)} missing, {len(hallucinated)} hallucinated")
        convo = build_retry_messages(messages, text, missing if text else [], hallucinated)
    if best:
        text, _, missing, hallucinated, used = best
        if hallucinated:
            # Do not return a known unsupported medication just because retries failed to remove it.
            text = EMPTY_FALLBACK.get(persona, "")
    else:
        text, missing, hallucinated, used = EMPTY_FALLBACK.get(persona, ""), list(required), [], None
    return GenerationResult(
        text=add_fallback(text, missing, persona),
        first_attempt_text=first_attempt_text or "",
        attempts=attempts,
        retries=attempts - 1,
        missing=missing,
        fallback_used=True,
        first_missing=first_missing or [],
        used_attempt=used,
        hallucinated_meds=hallucinated,
    )


def validate_output(record: dict[str, Any]) -> list[str]:
    """Check the final record's schema. Returns a list of error messages (empty means valid)."""
    errors = []
    for key in ("patient_summary", "child_explanation"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"{key} must be a non-empty string")
    checklist = record.get("caregiver_checklist")
    if not isinstance(checklist, list) or not checklist or not all(isinstance(i, str) and i.strip() for i in checklist):
        errors.append("caregiver_checklist must be a non-empty list of non-empty strings")
    missing_keys = [p for p in PERSONAS if p not in record]
    if missing_keys:
        errors.append(f"missing keys: {missing_keys}")
    try:
        json.dumps(record)
    except (TypeError, ValueError) as exc:
        errors.append(f"not JSON-serializable: {exc}")
    return errors
