"""Dose-to-drug consistency check for generated patient and caregiver text (app layer; src/ is not changed).

Number-matching checks only ask whether a dose appears somewhere in the note, so "the 2.5 mg dose of glyceryl
trinitrate" passes when 2.5 mg belongs to ramipril. This check asks whether the dose belongs to THAT medicine.

Rules
1. The note's medicine -> doses map is the union of
   a. the pipeline's extracted regimens (``medication`` -> ``dosages``), and
   b. medicine-list lines in the note: a line starting with ``1.``/``1)``/``-``/``*``/``•`` whose first dose is
      directly preceded by one to four words (the name); every dose on that line belongs to that name.
   Names are compared case-insensitively.
2. A dose is a number with a mass/volume/unit word: mg, mcg/µg, g, mL, unit(s), IU, mEq, and spelled-out
   milligram(s)/microgram(s)/gram(s)/milliliter(s). A dose followed by a lab denominator (/dL, /L, per dL...) is a
   measurement and is ignored. Counts such as "2 puffs" or "2 tablets" are not doses here.
3. Text is split into sentences (patient summary) or lines (caregiver checklist). Inside one segment each dose is
   attached to the NEAREST medicine name within ``WINDOW`` characters (ties go to the name before the dose).
   Medicine names are the map's names plus names the research ``medication_mentions`` finds.
4. Mismatch: the attached medicine is in the map and the dose is not one of its doses (including a medicine whose
   doses in the note are empty), or the attached medicine is not supported by the note at all.
   A dose with no medicine name within the window, or attached to a brand name of a note medicine, is left alone.

Limitations: pronouns ("take this, the dose is 40 mg") are not resolved; medicine names neither in the map nor known
to the research lexicon/suffix rules are invisible; a wrong frequency or duration is not checked; equivalent doses in
different units (0.5 g vs 500 mg) count as different; the nearest-name rule can attach a dose to the wrong medicine in
a sentence that lists several.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

WINDOW = 50
_UNIT_ALIASES = {"milligram": "mg", "milligrams": "mg", "microgram": "mcg", "micrograms": "mcg", "µg": "mcg",
                 "gram": "g", "grams": "g", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml",
                 "millilitres": "ml", "units": "unit"}
_DOSE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s?(mg|mcg|µg|g|ml|units?|iu|meq|milligrams?|micrograms?|grams?|milli(?:liter|litre)s?)"
    r"(?![A-Za-z])(?!\s*(?:/|\bper\s+)\s*(?:dL|L|deciliters?|decilitres?|liters?|litres?)(?![A-Za-z]))",
    re.IGNORECASE)
_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+((?:[A-Za-z][A-Za-z'-]*\s+){0,3}[A-Za-z][A-Za-z'-]*)\s+(?=\d)")
_SENTENCE_SPLIT = re.compile(r"((?<=[.!?])\s+|\n+)")


def _norm_dose(number: str, unit: str) -> tuple[str, str]:
    value = float(number)
    num = str(int(value)) if value.is_integer() else str(value)
    unit = unit.lower()
    return num, _UNIT_ALIASES.get(unit, unit)


def _doses(text: str) -> list[tuple[int, int, tuple[str, str]]]:
    return [(m.start(), m.end(), _norm_dose(m.group(1), m.group(2))) for m in _DOSE.finditer(text)]


def note_dose_map(source: str, regimens: Iterable[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    """Medicine name (lower case) -> the doses the note gives for it (rule 1)."""
    out: dict[str, set[tuple[str, str]]] = {}
    for reg in regimens or []:
        name = str(reg.get("medication", "")).strip().lower()
        if name:
            out.setdefault(name, set()).update(d for dosage in reg.get("dosages", []) for *_, d in _doses(str(dosage)))
    for line in source.splitlines():
        match = _LIST_LINE.match(line)
        if match:
            out.setdefault(match.group(1).strip().lower(), set()).update(d for *_, d in _doses(line))
    return out


def _name_spans(segment: str, names: Iterable[str]) -> list[tuple[int, int, str]]:
    spans = []
    for name in sorted(set(names), key=len, reverse=True):
        body = r"\s+".join(re.escape(part) for part in name.split())
        for m in re.finditer(rf"(?<![A-Za-z]){body}(?:s|es)?(?![A-Za-z])", segment, re.IGNORECASE):
            if not any(s < m.end() and m.start() < e for s, e, _ in spans):
                spans.append((m.start(), m.end(), name))
    return spans


def segment_mismatches(segment: str, dose_map: dict[str, set[tuple[str, str]]], source: str,
                       entities: Iterable[dict[str, Any]] = ()) -> list[dict[str, str]]:
    """Doses in one sentence or line that do not belong to the medicine they are attached to (rules 2-4)."""
    from src.evaluator import medication_mentions, unsupported_meds   # research code, called not edited

    doses = _doses(segment)
    if not doses:
        return []
    found = medication_mentions(segment)
    unsupported = set(unsupported_meds(segment, source, list(entities))["unsupported"]) if found else set()
    spans = _name_spans(segment, [*dose_map, *found])
    out = []
    for d_start, d_end, dose in doses:
        best = None
        for s, e, name in spans:
            gap = d_start - e if e <= d_start else s - d_end if s >= d_end else 0
            key = (gap, 0 if e <= d_start else 1)
            if gap <= WINDOW and (best is None or key < best[0]):
                best = (key, name)
        if best is None:
            continue
        name = best[1]
        if name in dose_map:
            bad = dose not in dose_map[name]
        else:
            bad = name in unsupported
        if bad:
            out.append({"medication": name, "dose": f"{dose[0]} {dose[1]}"})
    return out


def split_sentences(text: str) -> list[str]:
    """Sentences and their separators, alternating, so that ``"".join(...)`` gives the text back."""
    return _SENTENCE_SPLIT.split(text)


def remove_sentences(text: str, drop: Any) -> tuple[str, list[str]]:
    """Remove every sentence for which ``drop(sentence)`` is truthy; return the new text and the removed sentences."""
    parts = split_sentences(text)
    kept, removed = [], []
    for i in range(0, len(parts), 2):
        sentence, sep = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        if sentence.strip() and drop(sentence):
            removed.append(sentence)
            continue
        kept.append(sentence + sep)
    new = re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()
    return new, removed
