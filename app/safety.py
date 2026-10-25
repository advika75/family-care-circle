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

SAFE_CHILD_MESSAGE = "A grown-up will help explain what the doctor said."
MAX_CHILD_SENTENCES = 8
MAX_CHILD_WORDS = 120

REASON_DIGIT = "digit"
REASON_NUMBER_WORD = "number_word"
REASON_UNIT = "unit_word"
REASON_MEDICATION = "medication_name"
REASON_DENYLIST = "denylist"
REASON_TOO_LONG = "too_long"
REASON_EMPTY = "empty"

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


def check_child_text(text: str, medications: Iterable[str]) -> list[str]:
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
    if count_sentences(text) > MAX_CHILD_SENTENCES or count_words(text) > MAX_CHILD_WORDS:
        reasons.append(REASON_TOO_LONG)
    return reasons
