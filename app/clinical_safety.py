"""Conservative app-layer checks for unsupported high-impact clinical claims.

These phrase checks catch a small set of serious diagnoses, procedures and events. They are not
semantic verification and do not guarantee that generated text is medically accurate.
"""

from __future__ import annotations

import re


_CLAIMS: dict[str, tuple[str, ...]] = {
    "heart_attack": (r"\bheart attacks?\b", r"\bmyocardial infarctions?\b", r"\bMIs?\b"),
    "stroke": (r"\bstrokes?\b", r"\bcerebrovascular accidents?\b"),
    "heart_failure": (r"\bheart failure\b", r"\bcongestive heart failure\b", r"\bCHF\b"),
    "cardiac_arrest": (r"\bcardiac arrests?\b", r"\bheart stopped\b"),
    "stent_or_implant": (
        r"\bstents?\b", r"\bstenting\b", r"\bpacemakers?\b", r"\bdefibrillators?\b",
        r"\bimplants?\b", r"\bimplant(?:ed|ing)\b",
        r"\b(?:tiny|small|little)\s+(?:helper|device|tube|mesh)(?:\s+\w+){0,4}\s+(?:in|inside|into)\s+(?:your\s+)?heart\b",
        r"\b(?:put|placed|inserted|implanted)\b.{0,45}\b(?:in|inside|into)\b.{0,20}\b(?:heart|artery|vein)\b",
    ),
    "cardiac_procedure": (
        r"\b(?:heart|cardiac) surgeries\b", r"\b(?:heart|cardiac) surgery\b", r"\bbypasses\b",
        r"\bangioplast(?:y|ies)\b", r"\bcatheterizations?\b", r"\bheart transplants?\b",
    ),
    "hospital_event": (
        r"\bhospitali[sz]ed\b", r"\badmitted to (?:the )?hospital\b", r"\bICU\b",
        r"\bintensive care\b", r"\bhospital stays?\b",
    ),
    "cancer": (r"\bcancers?\b", r"\bmalignan(?:t|cy|cies)\b", r"\btumou?rs?\b"),
}
_NEGATION_BEFORE = re.compile(r"\b(?:no|not|den(?:y|ies|ied)|without|negative for|rule(?:d)? out)\b[^.!?]{0,45}$", re.I)
_NEGATION_AFTER = re.compile(r"^\s*(?:was|were|has been|have been)?\s*(?:ruled out|excluded|not present|negative)\b", re.I)
_OTHER_PERSON = re.compile(r"\b(?:family history|father|mother|parent|sister|brother|grandmother|grandfather|aunt|uncle|caregiver)\b[^.!?]{0,55}$", re.I)
_RECOVERY = re.compile(r"\b(?:feeling better|feel(?:s|ing)? better|getting better|recover(?:ed|ing)?|improv(?:ed|ing)|resolved)\b", re.I)
_MEDICATION_CHANGE = re.compile(
    r"\b(?:stop|stopping|discontinue|discontinuing|start|starting|change|changing|adjust|adjusting|take|takes|taking|give|giving|prescribe|prescribed|"
    r"skip|skipping|hold|holding|increase|increasing|decrease|decreasing)\b"
    r"[^.!?]{0,70}\b(?:medicine|medication|drug|pill|dose|treatment)\b|"
    r"\b(?:medicine|medication|drug|pill|dose|treatment)\b[^.!?]{0,70}\b"
    r"(?:stop|stopping|discontinue|discontinuing|start|starting|change|changing|adjust|adjusting|take|takes|taking|give|giving|prescribe|prescribed|"
    r"skip|skipping|hold|holding|increase|increasing|decrease|decreasing)\b", re.I)
_CHILD_AS_PATIENT = re.compile(
    r"\byou\s+(?:have|had|have had|got|suffered|experienced)\b[^.!?]{0,80}\b"
    r"(?:heart attack|myocardial infarction|stroke|heart failure|stent|surgery|cancer|tumou?r|"
    r"hospital|cardiac arrest|heart transplant)\b", re.I)


def _confirmed(patterns: tuple[str, ...], source: str) -> bool:
    for pattern in patterns:
        for match in re.finditer(pattern, source, re.I):
            before = source[max(0, match.start() - 55):match.start()]
            after = source[match.end():match.end() + 45]
            if (not _NEGATION_BEFORE.search(before) and not _NEGATION_AFTER.search(after)
                    and not _OTHER_PERSON.search(before)):
                return True
    return False


# The alternatives of _RECOVERY, named, so a run can report WHICH rule matched without recording any text.
_RECOVERY_CATEGORIES = (
    ("feel better", re.compile(r"\b(?:feeling better|feel(?:s|ing)? better)\b", re.I)),
    ("getting better", re.compile(r"\bgetting better\b", re.I)),
    ("recover", re.compile(r"\brecover(?:ed|ing)?\b", re.I)),
    ("improve", re.compile(r"\bimprov(?:ed|ing)\b", re.I)),
    ("resolved", re.compile(r"\bresolved\b", re.I)),
)


def recovery_category(text: str) -> str | None:
    """Name of the first recovery rule that matches ``text`` (a fixed label, never the text itself)."""
    return next((name for name, pattern in _RECOVERY_CATEGORIES if pattern.search(text or "")), None)


def unsupported_recovery_sentence(sentence: str, source: str) -> bool:
    """True if the sentence claims recovery or improvement that the note does not affirm."""
    return bool(_RECOVERY.search(sentence or "")) and not _confirmed((_RECOVERY.pattern,), source or "")


def unsupported_claims(text: str, source: str, *, persona: str) -> list[str]:
    """Return conservative claim categories not affirmatively found in the source note."""
    if not isinstance(text, str) or not text.strip():
        return []
    reasons = [name for name, patterns in _CLAIMS.items()
               if any(re.search(pattern, text, re.I) for pattern in patterns)
               and not _confirmed(patterns, source or "")]
    if _RECOVERY.search(text) and not _confirmed((_RECOVERY.pattern,), source or ""):
        reasons.append("unsupported_recovery")
    if persona == "child":
        if _CHILD_AS_PATIENT.search(text):
            reasons.append("child_subject_assumption")
        if _MEDICATION_CHANGE.search(text):
            reasons.append("medication_change_advice")
    return reasons
