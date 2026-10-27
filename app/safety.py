"""Child-explanation safety gate (server-side, runs before a child output is stored as displayable).

The child text is REJECTED, and the generic safe message shown instead, if any of these hold:

* a digit of any kind (decimal digits in any script, and circled, superscript or fraction forms such as ``①`` ``²`` ``½``),
* a spelled-out number or dose word (``zero`` to ``ninety-nine``, ``hundred``, ``thousand``, ``dozen``, ``half``,
  ``once``/``twice``/``thrice``, ...),
* a unit word (``mg``, ``mcg``, ``ml``, milligram(s), tablet(s), capsule(s), pill(s), unit(s), ...),
* a medication name extracted from that note (case-insensitive; plurals and possessives included; zero-width and soft
  hyphen characters are ignored, so ``amoxi<ZWSP>cillin`` is still ``amoxicillin``),
* a word on the frightening-words denylist (die, death, dying, cancer, tumour/tumor, fatal, terminal, surgery,
  "hospital stay"),
* a health statement addressed to the child as if they were the patient ("you have diabetes", "your medicine",
  "the doctors are taking care of you"), or the research pipeline's generic empty-output child text, which does that,
* more than ``MAX_CHILD_SENTENCES`` sentences, or more than ``MAX_CHILD_WORDS`` words (a long run-on with no
  punctuation counts as one sentence, so the word cap closes that gap).

Only the child output is gated. (The patient and caregiver outputs are deliberately not checked this way.)

This is a RULE-BASED gate and does not understand language. What it cannot catch is listed in ``app/README.md``:
brand names it has never seen (``Tylenol`` when the note says ``paracetamol``), misspellings of a drug name
(``amoxicilin``), paraphrased fears with none of the listed words, and a chain of short clauses joined only by commas.

The sentence limit is 8 to match the pipeline's own child prompt ("5 to 8 sentences", ``src/prompts.py``); the project
owner chose this over the 6 in the first draft of the specification (F-15).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from app.clinical_safety import unsupported_claims

SAFE_CHILD_MESSAGE = ("The note has information about someone's health. Their care team can explain what it means. "
                      "You can ask a trusted adult if you have questions.")
MAX_CHILD_SENTENCES = 8
MAX_CHILD_WORDS = 120

REASON_DIGIT = "digit"
REASON_NUMBER_WORD = "number_word"
REASON_UNIT = "unit_word"
REASON_MEDICATION = "medication_name"
REASON_DENYLIST = "denylist"
REASON_TOO_LONG = "too_long"
REASON_EMPTY = "empty"
REASON_UNSUPPORTED_CLAIM = "unsupported_clinical_claim"
REASON_CHILD_AS_PATIENT = "child_as_patient"
REASON_GENERIC_FALLBACK = "generic_fallback"

# Sentence ends: . ! ? … ; : (a run of them, with or without a space after) and line breaks. Deliberately generous:
# counting too many sentences only withholds more.
_SENTENCE_SPLIT = re.compile(r"[.!?…;:]+|\n+")
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)

_NUMBER_WORDS = frozenset("""
zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen
eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million dozen half halves
quarter once twice thrice double triple single first second third fourth fifth
""".split())
# "single", "first", "second" and the like are ordinary words that are almost never a dose; they are NOT in the list
# below. Kept out of the active set on purpose so the gate does not reject harmless sentences.
_NUMBER_WORDS = _NUMBER_WORDS - {"single", "first", "second", "third", "fourth", "fifth", "double", "triple", "quarter"}

_UNIT_WORDS = frozenset("""
mg mcg ug ml mls cc iu milligram milligrams microgram micrograms milliliter milliliters millilitre millilitres
gram grams tablet tablets tab tabs capsule capsules caplet caplets pill pills unit units teaspoon teaspoons
tablespoon tablespoons drop drops puff puffs
""".split())
_UNIT_WORDS = _UNIT_WORDS - {"drop", "drops", "puff", "puffs", "gram", "grams", "tab", "tabs"}

# Frightening words, matched as whole words (inflections listed explicitly). "surgeon" etc. do not match "surgery".
_DENYLIST = re.compile(
    r"(?<!\w)(?:die|dies|died|dying|death|deaths|dead|cancer|cancers|tumou?rs?|fatal|fatally|terminal|terminally|"
    r"surgery|surgeries|hospital[\s\-]+stays?)(?!\w)", re.IGNORECASE)


# The child reading the explanation is not assumed to be the patient. Health statements written to "you" are withheld:
# a possessive health noun ("your body", "your medicine", "your doctor"), a second-person state or action followed in
# the same sentence by a health word or a condition/symptom the research lexicon knows ("you have diabetes", "you feel
# dizzy"), or care aimed at "you" ("the doctors are taking care of you"). "You can ask ...", "if you have questions" and
# "you are loved" carry no health word and pass.
_HEALTH_WORDS = (r"sick|ill|unwell|hurts?|hurting|pain|sore|dizzy|dizziness|diabetes|sugar|blood|pressure|fever|cough|"
                 r"cold|flu|infection|asthma|allerg(?:y|ies)|rash|medicines?|medications?|pills?|doctors?|nurses?|"
                 r"hospital|condition|disease|illness|sickness|symptoms?|treatment|better|checked|numbers")
_YOUR_HEALTH = re.compile(
    r"\byour\s+(?:own\s+)?(?:body|blood|sugar|heart|lungs?|tummy|stomach|belly|brain|kidneys?|liver|skin|throat|"
    r"medicines?|medications?|pills?|treatment|illness|sickness|condition|disease|health|doctors?|nurses?|care\s+team|"
    r"symptoms?|diabetes|infection|check-?ups?|appointments?|numbers)\b", re.IGNORECASE)
_YOU_STATE = re.compile(
    r"\byou(?:\s+(?:have|had|got|get|are|were|feel|felt|take|took|need|must|should)|['’](?:re|ve))\b([^.!?\n]{0,60})",
    re.IGNORECASE)
_HEALTH_WORD = re.compile(rf"\b(?:{_HEALTH_WORDS})\b", re.IGNORECASE)
_CARE_FOR_YOU = re.compile(
    r"\b(?:doctors?|nurses?|medicines?|care\s+team)\b[^.!?\n]{0,60}\b(?:care\s+of|caring\s+for|help(?:s|ing)?|"
    r"treat(?:s|ing)?|check(?:s|ing|ed)?\s+on|fix(?:es|ing)?)\s+you\b", re.IGNORECASE)


def _treats_child_as_patient(text: str) -> bool:
    from src.ner import extract_entities   # research lexicons, called not edited

    if _YOUR_HEALTH.search(text) or _CARE_FOR_YOU.search(text):
        return True
    for match in _YOU_STATE.finditer(text):
        rest = match.group(1)
        if _HEALTH_WORD.search(rest) or any(e["label"] in ("CONDITION", "SYMPTOM") for e in extract_entities(rest)):
            return True
    return False


def _is_research_empty_fallback(text: str) -> bool:
    """The research retry loop's text for an all-empty child output; it speaks to the child as the patient."""
    from src.postprocess import EMPTY_FALLBACK   # called not edited

    return " ".join(text.split()) == " ".join(EMPTY_FALLBACK["child_explanation"].split())


def _clean(text: str) -> str:
    """NFKC-normalise, drop invisible format characters (zero-width, soft hyphen, bidi marks) and case-fold."""
    text = unicodedata.normalize("NFKC", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Cf").casefold()


def _has_number_char(text: str) -> bool:
    # category N* covers decimal digits (Nd), letter numbers (Nl) and other numbers (No: circled, superscript, fractions)
    return any(unicodedata.category(c).startswith("N") for c in unicodedata.normalize("NFKC", text) + text)


def count_sentences(text: str) -> int:
    return len([s for s in _SENTENCE_SPLIT.split((text or "").strip()) if _WORD.search(s)])


def count_words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def medication_names(entities: Iterable[dict[str, Any]], regimens: Iterable[dict[str, Any]] = ()) -> list[str]:
    names = {e["text"].strip() for e in entities if e.get("label") == "MEDICATION" and e.get("text", "").strip()}
    names |= {r["medication"].strip() for r in regimens if r.get("medication", "").strip()}
    return sorted(names, key=lambda n: (-len(n), n.lower(), n))      # longest first; ties alphabetical (deterministic)


def _mentions(clean_text: str, name: str) -> bool:
    n = _clean(name).strip()
    if not n:
        return False
    body = r"\s+".join(re.escape(part) for part in n.split())
    return re.search(r"(?<!\w)" + body + r"(?:['’]s|'|’|s|es)?(?!\w)", clean_text) is not None


def check_child_text(text: str, medications: Iterable[str], source_text: str | None = None) -> list[str]:
    """Return the reasons the text must be withheld (empty list = it may be shown)."""
    if not (text or "").strip():
        return [REASON_EMPTY]
    clean = _clean(text)
    reasons: list[str] = []
    if _has_number_char(text):
        reasons.append(REASON_DIGIT)
    words = {w.split("'")[0].split("’")[0] for w in _WORD.findall(clean)}
    if words & _NUMBER_WORDS:
        reasons.append(REASON_NUMBER_WORD)
    if words & _UNIT_WORDS:
        reasons.append(REASON_UNIT)
    if any(_mentions(clean, name) for name in medications):
        reasons.append(REASON_MEDICATION)
    if _DENYLIST.search(clean):
        reasons.append(REASON_DENYLIST)
    if _is_research_empty_fallback(text):
        reasons.append(REASON_GENERIC_FALLBACK)
    if _treats_child_as_patient(unicodedata.normalize("NFKC", text)):
        reasons.append(REASON_CHILD_AS_PATIENT)
    if source_text is not None and unsupported_claims(text, source_text, persona="child"):
        reasons.append(REASON_UNSUPPORTED_CLAIM)
    if count_sentences(text) > MAX_CHILD_SENTENCES or count_words(text) > MAX_CHILD_WORDS:
        reasons.append(REASON_TOO_LONG)
    return reasons
