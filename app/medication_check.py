"""Context-aware "invented medication" check (reference implementation; NOT used by the research retry loop).

The research check ``src.evaluator.unsupported_meds`` counts every medication-like word the note does not support.
A plain-language explanation such as "a hormone called insulin" is therefore counted as an invented drug, which makes
the retry loop discard otherwise usable drafts. This module keeps the research result and removes only mentions that
are clearly explanatory. The pipeline cannot be given this check without a change in ``src/`` (see app/README.md).

Rules (case-insensitive), applied to each mention the research check reports as unsupported:

1. Only names in ``EXPLANATORY_PHRASES`` can be excused (currently: insulin).
2. A mention is excused only if it lies inside one of that name's explanatory phrases:
   "hormone called insulin", "insulin in your/the/her/his/their body", "make/makes/made (enough) insulin",
   "body's insulin".
3. ...and no dosing or taking word occurs in the same sentence within ``NEAR_CHARS`` characters on either side:
   take/takes/taking/took, give/gives/giving, start/starts/starting, dose/doses/dosing, tablet(s), injection(s)/inject,
   mg, mcg, unit(s), daily, twice.
4. The name stays counted if ANY of its mentions is not excused.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

NEAR_CHARS = 40
_DOSING = re.compile(
    r"\b(?:take|takes|taking|took|give|gives|giving|start|starts|starting|dose|doses|dosing|tablets?|injections?|"
    r"inject|mg|mcg|units?|daily|twice)\b", re.IGNORECASE)
EXPLANATORY_PHRASES: dict[str, tuple[re.Pattern[str], ...]] = {
    "insulin": (
        re.compile(r"\bhormone\s+called\s+insulin\b", re.IGNORECASE),
        re.compile(r"\binsulin\s+in\s+(?:your|the|her|his|their)\s+body\b", re.IGNORECASE),
        re.compile(r"\b(?:make|makes|made)\s+(?:enough\s+)?insulin\b", re.IGNORECASE),
        re.compile(r"\bbody['’]s\s+insulin\b", re.IGNORECASE),
    ),
}
_SENTENCE_END = re.compile(r"[.!?\n]")


def _sentence_window(text: str, start: int, end: int) -> str:
    """Up to NEAR_CHARS characters each side of the mention, cut at sentence boundaries."""
    left = text[max(0, start - NEAR_CHARS):start]
    right = text[end:end + NEAR_CHARS]
    cut = list(_SENTENCE_END.finditer(left))
    left = left[cut[-1].end():] if cut else left
    stop = _SENTENCE_END.search(right)
    right = right[:stop.start()] if stop else right
    return left + " " + right


def _excused(text: str, name: str) -> bool:
    phrases = EXPLANATORY_PHRASES.get(name)
    mentions = list(re.finditer(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", text, re.IGNORECASE))
    if not phrases or not mentions:
        return False
    spans = [m.span() for pattern in phrases for m in pattern.finditer(text)]
    for mention in mentions:
        inside = any(s <= mention.start() and mention.end() <= e for s, e in spans)
        if not inside or _DOSING.search(_sentence_window(text, mention.start(), mention.end())):
            return False
    return True


def invented_medications(text: str, source: str, entities: Iterable[dict[str, Any]] = ()) -> list[str]:
    """The research check's unsupported medications, minus names used only in explanatory phrases."""
    from src.evaluator import unsupported_meds   # research code, called not edited

    return [name for name in unsupported_meds(text, source, list(entities))["unsupported"]
            if not _excused(text, name.lower())]
