"""Entity normalization and presence checks shared by postprocessing and evaluation.

A generated text "retains" a source entity if a normalized form of the entity appears in the
normalized text. Normalization makes ``"500 mg" == "500mg" == "500 milligrams"``, ``"10-day" ==
"10 days"`` and maps number words to digits. Frequencies also match their plain-English
equivalents (``"BID" == "twice a day"``, ``"q4-6h" == "every 4 to 6 hours"``).
"""

from __future__ import annotations

import re
from typing import Iterable

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "twenty": "20", "thirty": "30",
}
TOKEN_ALIASES = {
    "milligram": "mg", "milligrams": "mg", "microgram": "mcg", "micrograms": "mcg", "ug": "mcg",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "days": "day", "weeks": "week", "months": "month", "hours": "hour", "hrs": "hour", "hr": "hour",
    "wks": "week", "wk": "week", "puffs": "puff", "tablets": "tablet", "tabs": "tablet", "tab": "tablet",
    "capsules": "capsule", "caps": "capsule", "units": "unit", "drops": "drop", "sprays": "spray",
    "times": "time", "minutes": "minute", "mins": "minute", "years": "year", "degrees": "degree",
    "lbs": "lb", "pounds": "lb", "pound": "lb",
}
_JOIN_UNITS = r"(mg|mcg|g|ml|meq|iu|unit)"

# Each group lists interchangeable ways of writing one frequency; the first entry is the
# plain-English form shown to readers.
_FREQUENCY_GROUPS_RAW = [
    ["once a day", "once daily", "daily", "every day", "each day", "once per day", "one time a day", "qd", "od"],
    ["twice a day", "twice daily", "bid", "two times a day", "two times daily", "twice per day", "every 12 hours", "q12h"],
    ["three times a day", "three times daily", "tid", "three times per day"],
    ["four times a day", "four times daily", "qid", "four times per day"],
    ["at bedtime", "nightly", "qhs", "every night", "each night", "at night", "before bed"],
    ["in the morning", "every morning", "qam", "each morning"],
    ["as needed", "prn", "when needed", "if needed", "only when needed", "as necessary"],
    ["every other day", "qod"],
    ["once a week", "weekly", "every week", "once weekly"],
]
_Q_HOURS_RE = re.compile(r"\bq\s*(\d+)\s*(?:-|to)?\s*(\d+)?\s*h(?:ours?|rs?)?\b")
_EVERY_HOURS_RE = re.compile(r"\bevery\s+(\d+)\s*(?:(?:-|to|or)?\s*(\d+))?\s*hours?\b")


def normalize(text: str) -> str:
    """Lowercase and canonicalize units, number words, plurals, hyphens and spacing."""
    t = text.lower().replace("µg", "mcg").replace("×", " x ")
    t = re.sub(r"(?<=[a-z])/(?=[a-z])", " ", t)          # amoxicillin/clavulanate
    t = re.sub(r"[‐-―-]", " ", t)                 # hyphens and dashes
    t = re.sub(r"\.(?!\d)", " ", t)                         # periods that are not decimals
    t = re.sub(r"[^\w\s./%]", " ", t)
    tokens = [TOKEN_ALIASES.get(tok, NUMBER_WORDS.get(tok, tok)) for tok in t.split()]
    t = " ".join(tokens)
    t = re.sub(rf"(\d)\s+{_JOIN_UNITS}\b", r"\1\2", t)       # "500 mg" -> "500mg"
    return t


_FREQUENCY_GROUPS = [[normalize(p) for p in group] for group in _FREQUENCY_GROUPS_RAW]


def _hour_interval(norm: str) -> tuple[str, str | None] | None:
    """Parse ``q4h``/``q4 6h``/``every 4 to 6 hour`` (already normalized) into (low, high)."""
    for pattern in (_Q_HOURS_RE, _EVERY_HOURS_RE):
        m = pattern.search(norm)
        if m:
            return m.group(1), m.group(2)
    return None


def frequency_variants(text: str) -> set[str]:
    """Return all normalized surface forms equivalent to the frequency ``text``."""
    norm = normalize(text)
    variants = {norm}
    for group in _FREQUENCY_GROUPS:
        if norm in group:
            variants.update(group)
    interval = _hour_interval(norm)
    if interval:
        low, high = interval
        if high:
            variants.update({f"q{low} {high}h", f"every {low} to {high} hour", f"every {low} {high} hour",
                             f"every {low} or {high} hour"})
        else:
            variants.update({f"q{low}h", f"every {low} hour"})
    return variants


def plain_frequency(text: str) -> str | None:
    """Plain-English reading of a frequency abbreviation (``"BID"`` -> ``"twice a day"``), or None."""
    norm = normalize(text)
    for raw_group, group in zip(_FREQUENCY_GROUPS_RAW, _FREQUENCY_GROUPS):
        if norm in group and norm != group[0]:
            return raw_group[0]
    interval = _hour_interval(norm)
    if interval and norm.startswith("q"):
        low, high = interval
        return f"every {low} to {high} hours" if high else f"every {low} hours"
    return None


def entity_variants(entity: dict) -> set[str]:
    """Normalized strings any of which counts as the entity being present."""
    if entity.get("label") == "FREQUENCY":
        return frequency_variants(entity["text"])
    return {normalize(entity["text"])}


def contains_entity(text: str, entity: dict, normalized_text: str | None = None) -> bool:
    """True if ``entity`` (a dict with ``text`` and ``label``) appears in ``text`` after normalization."""
    haystack = normalized_text if normalized_text is not None else normalize(text)
    for variant in entity_variants(entity):
        if variant and re.search(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", haystack):
            return True
    return False


def unique_entities(entities: Iterable[dict], labels: Iterable[str] | None = None) -> list[dict]:
    """Deduplicate entities by (label, normalized text), optionally keeping only ``labels``."""
    wanted = set(labels) if labels is not None else None
    seen: set[tuple[str, str]] = set()
    out = []
    for ent in entities:
        if wanted is not None and ent["label"] not in wanted:
            continue
        key = (ent["label"], normalize(ent["text"]))
        if key not in seen:
            seen.add(key)
            out.append(ent)
    return out


def find_missing(text: str, entities: Iterable[dict]) -> list[dict]:
    """Return the entities from ``entities`` that do not appear in ``text``."""
    normalized_text = normalize(text)
    return [e for e in entities if not contains_entity(text, e, normalized_text)]
