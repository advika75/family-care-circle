"""Find and describe failure cases in a folder of pipeline outputs."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from src.evaluator import (
    RETENTION_PERSONAS,
    entity_retention,
    persona_text,
    readability,
    repeated_units,
    unsupported_meds,
    unsupported_numbers,
)
from src.matching import contains_entity
from src.prompts import PERSONAS

CATEGORIES = {
    "missing_entity": "Required entity missing from the final output",
    "fallback_used": "Model omitted required facts; the fallback had to append them",
    "format_or_retries": "Invalid JSON/format, or all retries used up",
    "unsupported_content": "Number or medication not supported by the source note (possible hallucination)",
    "child_reading_level": "Child explanation above the maximum reading grade",
    "truncated": "Generation stopped at max_new_tokens, so the text is cut off",
    "repetition": "A bullet (caregiver) or sentence (other personas) duplicates or nearly duplicates an earlier one",
    "empty_or_short": "Empty or very short output",
}
EXCERPT_CHARS = 220


def excerpt(text: str, term: str | None = None, width: int = EXCERPT_CHARS) -> str:
    """One-line excerpt of ``text``, centred on ``term`` (case-insensitive, number-aware) when found."""
    flat = re.sub(r"\s+", " ", text).strip()
    start = 0
    if term:
        head = re.escape(term.split()[0]) if term[0].isdigit() else re.escape(term)
        m = re.search(rf"(?<![\w.]){head}", flat, re.IGNORECASE)
        if m:
            start = max(0, m.start() - width // 3)
    snippet = flat[start:start + width]
    return ("…" if start > 0 else "") + snippet + ("…" if start + width < len(flat) else "")


def source_line(source: str, term: str | None) -> str:
    """The source line mentioning ``term`` (falls back to the start of the note)."""
    if term:
        entity = {"text": term, "label": "OTHER"}
        for line in source.splitlines():
            if contains_entity(line, entity):
                return excerpt(line)
    return excerpt(source)


def _failure(record: dict[str, Any], category: str, persona: str, problem: str,
             source_term: str | None = None, output_term: str | None = None) -> dict[str, Any]:
    text = persona_text(record, persona) if persona in PERSONAS else ""
    out = excerpt(text, output_term)
    return {"category": category, "id": record.get("id"), "persona": persona, "problem": problem,
            "source_excerpt": source_line(record.get("source_text", ""), source_term), "output_excerpt": out}


def analyze_record(record: dict[str, Any], max_child_grade: float = 3.0, min_words: int = 20) -> list[dict[str, Any]]:
    """All failures found in one output record."""
    meta = record.get("metadata", {})
    source, entities = record.get("source_text", ""), record.get("entities", [])
    max_retries = meta.get("max_retries")
    failures = []
    if not meta.get("valid", True):
        failures.append(_failure(record, "format_or_retries", "record",
                                 "invalid format: " + "; ".join(meta.get("validation_errors", []))))
    for persona in PERSONAS:
        text = persona_text(record, persona)
        words = len(text.split())
        if words < min_words:
            failures.append(_failure(record, "empty_or_short", persona, f"only {words} words (minimum {min_words})"))
        if persona in RETENTION_PERSONAS:
            missing = entity_retention(entities, text)["missing"]
            if missing:
                failures.append(_failure(record, "missing_entity", persona, "missing: " + ", ".join(missing),
                                         source_term=missing[0]))
        if meta.get("fallback_used", {}).get(persona):
            omitted = meta.get("missing_after_retries", {}).get(persona, [])
            failures.append(_failure(
                record, "fallback_used", persona,
                f"after {meta.get('retries', {}).get(persona, '?')} retries the model still omitted "
                f"{', '.join(omitted) or '(empty output)'}; the fallback appended them",
                source_term=omitted[0] if omitted else None,
                output_term="Confirm with the care team" if persona == "caregiver_checklist" else "Important details"))
        retries = meta.get("retries", {}).get(persona)
        if max_retries and retries is not None and retries >= max_retries:
            outcome = "fallback used" if meta.get("fallback_used", {}).get(persona) else "succeeded on the last attempt"
            failures.append(_failure(record, "format_or_retries", persona,
                                     f"used all {max_retries} retries ({outcome})"))
        for kind, check in (("number", unsupported_numbers), ("medication", unsupported_meds)):
            for item in check(text, source, entities)["unsupported"]:
                failures.append(_failure(record, "unsupported_content", persona,
                                         f"{kind} '{item}' is not in the source note",
                                         source_term=item if kind == "medication" else None, output_term=item))
        if meta.get("truncated", {}).get(persona):
            limit = meta.get("generation_params", {}).get(persona, {}).get("max_new_tokens", "?")
            before_fallback = re.split(r"\n*(?:Important details from your care team's note:|- Confirm with the care team:)",
                                       text)[0]
            failures.append({**_failure(record, "truncated", persona,
                                        f"hit max_new_tokens ({limit}); raise personas.{persona}.max_new_tokens"),
                             "output_excerpt": "…" + excerpt(before_fallback[-EXCERPT_CHARS:])})
        repeats = repeated_units(text, persona)
        if repeats:
            unit = "bullet" if persona == "caregiver_checklist" else "sentence"
            first = repeats[0]
            failures.append({**_failure(
                record, "repetition", persona,
                f"{len(repeats)} repeated {unit}(s); e.g. {unit} {first['index'] + 1} repeats {unit} "
                f"{first['earlier_index'] + 1} (overlap {first['overlap']:.2f})"),
                "output_excerpt": f"“{excerpt(first['earlier'], width=150)}” … later: “{excerpt(first['text'], width=150)}”"})
        if persona == "child_explanation":
            grade = readability(text)["fkgl"]
            if grade == grade and grade > max_child_grade:
                failures.append(_failure(record, "child_reading_level", persona,
                                         f"Flesch-Kincaid grade {grade:.1f} > {max_child_grade:g}"))
    return failures


def pick_examples(failures: list[dict[str, Any]], k: int = 3) -> list[dict[str, Any]]:
    """Up to ``k`` examples, preferring different notes."""
    chosen, seen = [], set()
    for f in failures:
        if f["id"] not in seen:
            chosen.append(f)
            seen.add(f["id"])
        if len(chosen) == k:
            return chosen
    return (chosen + [f for f in failures if f not in chosen])[:k]


def analyze(records: Iterable[dict[str, Any]], max_child_grade: float = 3.0, min_words: int = 20,
            max_examples: int = 3) -> dict[str, Any]:
    """Run all checks. Returns counts, notes affected, examples and every failure (machine-readable)."""
    records = sorted(records, key=lambda r: str(r.get("id")))
    failures = [f for r in records for f in analyze_record(r, max_child_grade, min_words)]
    by_cat = {c: [f for f in failures if f["category"] == c] for c in CATEGORIES}
    backends = Counter(r.get("metadata", {}).get("backend") for r in records)
    return {
        "n_records": len(records),
        "backends": dict(backends),
        "settings": {"max_child_grade": max_child_grade, "min_words": min_words, "max_examples": max_examples},
        "counts": {c: len(v) for c, v in by_cat.items()},
        "notes_affected": {c: len({f["id"] for f in v}) for c, v in by_cat.items()},
        "examples": {c: pick_examples(v, max_examples) for c, v in by_cat.items()},
        "failures": failures,
    }


def to_markdown(result: dict[str, Any], outputs_dir: str) -> str:
    """Human-readable report: counts table plus concrete examples per category."""
    backends = ", ".join(f"{b} ({n})" for b, n in result["backends"].items())
    s = result["settings"]
    lines = [
        "# Error analysis", "",
        f"Outputs: `{outputs_dir}` · {result['n_records']} notes · backend: {backends}  ",
        f"Settings: child max grade {s['max_child_grade']:g}, minimum {s['min_words']} words per output.", "",
    ]
    if "mock" in result["backends"]:
        lines += ["> ⚠️ These are **mock** outputs (template text, no model). Counts only test the tooling.", ""]
    lines += ["| Category | Failures | Notes affected | Meaning |", "|---|---|---|---|"]
    for c, desc in CATEGORIES.items():
        lines.append(f"| {c} | {result['counts'][c]} | {result['notes_affected'][c]} / {result['n_records']} | {desc} |")
    lines += ["", "Failures are counted per (note, persona), and per item for unsupported content.", ""]
    for c, desc in CATEGORIES.items():
        lines += [f"## {c} ({result['counts'][c]})", "", f"_{desc}._", ""]
        if not result["examples"][c]:
            lines += ["No failures.", ""]
            continue
        for ex in result["examples"][c]:
            lines += [f"**{ex['id']} · {ex['persona']}**: {ex['problem']}", "",
                      f"> **Source:** {ex['source_excerpt']}", ">",
                      f"> **Output:** {ex['output_excerpt'] or '(empty)'}", ""]
    return "\n".join(lines)
