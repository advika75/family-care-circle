"""Clinical named-entity recognition.

The default extractor is rule-based (regular expressions plus small lexicons) and needs no
model. Optionally, a Hugging Face token-classification model can be enabled in ``config.yaml``
(``ner.use_hf_model``); its entities are merged with the rule-based ones, and rule-based spans
win on overlap.

Every entity is a dict ``{"text", "label", "start", "end"}`` with character offsets into the input.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

LABELS = ("SYMPTOM", "CONDITION", "MEDICATION", "DOSAGE", "FREQUENCY", "DURATION")
REGIMEN_LABELS = ("DOSAGE", "FREQUENCY", "DURATION")

MEDICATIONS = """
acetaminophen paracetamol ibuprofen naproxen aspirin celecoxib amoxicillin amoxicillin-clavulanate
augmentin azithromycin cephalexin cefdinir ceftriaxone ciprofloxacin levofloxacin doxycycline
nitrofurantoin trimethoprim-sulfamethoxazole clindamycin penicillin metronidazole phenazopyridine
oseltamivir metformin empagliflozin dapagliflozin glipizide sitagliptin insulin insulin_glargine
insulin_lispro semaglutide liraglutide atorvastatin rosuvastatin simvastatin lisinopril losartan
valsartan sacubitril-valsartan amlodipine hydrochlorothiazide chlorthalidone metoprolol
metoprolol_succinate metoprolol_tartrate carvedilol propranolol atenolol diltiazem furosemide
spironolactone potassium_chloride apixaban rivaroxaban warfarin clopidogrel digoxin amiodarone
albuterol levalbuterol fluticasone budesonide montelukast prednisone prednisolone dexamethasone
methylprednisolone ipratropium tiotropium salmeterol formoterol oxycodone hydrocodone morphine
tramadol codeine ondansetron promethazine docusate senna polyethylene_glycol omeprazole
pantoprazole famotidine sertraline fluoxetine escitalopram citalopram bupropion hydroxyzine
melatonin trazodone sumatriptan rizatriptan levothyroxine gabapentin cetirizine loratadine
diphenhydramine benzonatate guaifenesin mupirocin
"""

CONDITIONS = """
strep_throat streptococcal_pharyngitis pharyngitis type_2_diabetes_mellitus type_2_diabetes
type_1_diabetes diabetes_mellitus diabetes hyperlipidemia hypertension essential_hypertension
asthma asthma_exacerbation copd pneumonia community-acquired_pneumonia urinary_tract_infection uti
cystitis pyelonephritis appendicitis acute_appendicitis cellulitis atrial_fibrillation heart_failure
migraine major_depressive_disorder depression generalized_anxiety_disorder otitis_media bronchitis
sinusitis influenza covid-19 gerd hypothyroidism chronic_kidney_disease viral_uri
upper_respiratory_infection viral_upper_respiratory_infection yeast_infection stroke obesity
"""

SYMPTOMS = """
fever sore_throat cough productive_cough wheezing shortness_of_breath chest_pain chest_tightness
headache dizziness nausea vomiting diarrhea constipation fatigue pain abdominal_pain flank_pain
suprapubic_pain back_pain rash dysuria urinary_frequency urgency frequent_urination increased_thirst
palpitations swelling ankle_swelling redness warmth drainage bleeding difficulty_swallowing
trouble_breathing drooling insomnia poor_sleep low_mood anxiety light_sensitivity loss_of_appetite
decreased_appetite itching confusion chills runny_nose congestion burning_with_urination syncope
"""

_DOSAGE_RE = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?\s?"
    r"(?:mg|mcg|µg|g|mL|ml|units?|IU|mEq|puffs?|tablets?|tabs?|capsules?|caps?|drops?|sprays?)\b",
    re.IGNORECASE,
)

_FREQUENCY_RE = re.compile(
    r"\b(?:"
    r"q\s?\d+(?:\s?-\s?\d+)?\s?h(?:ours?|rs?)?"
    r"|every\s+\d+(?:\s?(?:-|to)\s?\d+)?\s+hours?"
    r"|every\s+(?:other\s+day|morning|evening|night|day)"
    r"|(?:once|twice|three\s+times|four\s+times|[1-4]\s*(?:x|times))\s+(?:daily|a\s+day|per\s+day|weekly|a\s+week)"
    r"|at\s+bedtime|as\s+needed|in\s+the\s+morning"
    r"|BID|TID|QID|QD|QHS|QAM|QPM|QOD|PRN|nightly|daily|weekly"
    r")\b",
    re.IGNORECASE,
)

# The DURATION span is the number + unit (e.g. "10 days" in "x 10 days"); the cue word is context.
_DURATION_RE = re.compile(
    r"\b(?:for|x|×)\s*(?:up\s+to\s+|the\s+next\s+|another\s+|a\s+total\s+of\s+)?"
    r"(?P<span>(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:\s?(?:-|to)\s?\d+)?\s+(?:more\s+)?(?:days?|weeks?|months?|wks?))\b"
    r"|\b(?P<span2>\d+-(?:day|week|month))\b",
    re.IGNORECASE,
)


def _lexicon_regex(terms: str) -> re.Pattern[str]:
    """Compile a whitespace-separated lexicon (``_`` joins multiword terms) into one regex."""
    words = sorted({t.replace("_", " ") for t in terms.split()}, key=len, reverse=True)
    alternation = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words)
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternation})(?:s|es)?(?![A-Za-z0-9])", re.IGNORECASE)


_LEXICONS = {
    "MEDICATION": _lexicon_regex(MEDICATIONS),
    "CONDITION": _lexicon_regex(CONDITIONS),
    "SYMPTOM": _lexicon_regex(SYMPTOMS),
}


def _entity(text: str, label: str, start: int, end: int) -> dict[str, Any]:
    return {"text": text[start:end], "label": label, "start": start, "end": end}


def resolve_overlaps(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep a non-overlapping subset, preferring earlier-listed entities, then longer spans.

    Entities are processed in list order within each priority tier, so callers put
    higher-priority sources first.
    """
    kept: list[dict[str, Any]] = []
    for ent in entities:
        if not any(ent["start"] < k["end"] and k["start"] < ent["end"] for k in kept):
            kept.append(ent)
    return sorted(kept, key=lambda e: e["start"])


def extract_rule_based(text: str) -> list[dict[str, Any]]:
    """Extract entities with regexes and lexicons. Longer spans win when candidates overlap."""
    candidates: list[dict[str, Any]] = []
    for m in _DOSAGE_RE.finditer(text):
        candidates.append(_entity(text, "DOSAGE", m.start(), m.end()))
    for m in _FREQUENCY_RE.finditer(text):
        candidates.append(_entity(text, "FREQUENCY", m.start(), m.end()))
    x_cued: set[int] = set()
    for m in _DURATION_RE.finditer(text):
        group = "span" if m.group("span") else "span2"
        candidates.append(_entity(text, "DURATION", m.start(group), m.end(group)))
        if m.group(0)[:1].lower() in ("x", "×"):
            x_cued.add(m.start(group))
    for label, pattern in _LEXICONS.items():
        for m in pattern.finditer(text):
            candidates.append(_entity(text, label, m.start(), m.end()))
    candidates.sort(key=lambda e: (-(e["end"] - e["start"]), e["start"]))
    entities = resolve_overlaps(candidates)
    return [e for e in entities if not (e["start"] in x_cued and not _follows_regimen(e, entities, text))]


def _follows_regimen(duration: dict[str, Any], entities: list[dict[str, Any]], text: str) -> bool:
    """True if a MEDICATION/DOSAGE/FREQUENCY precedes ``duration`` on the same line.

    Used for "x N days", which is also how notes write symptom durations ("sore throat x 2 days").
    """
    line_start = text.rfind("\n", 0, duration["start"]) + 1
    return any(
        e["label"] in ("MEDICATION", "DOSAGE", "FREQUENCY") and line_start <= e["start"] < duration["start"]
        for e in entities
    )


class HFNERModel:
    """Thin wrapper around a Hugging Face token-classification pipeline (loaded lazily)."""

    def __init__(self, model_id: str, label_map: dict[str, str], min_score: float = 0.6) -> None:
        from transformers import pipeline  # imported here so the rule-based path needs no transformers

        self.label_map = label_map
        self.min_score = min_score
        self._pipe = pipeline("token-classification", model=model_id, aggregation_strategy="simple")

    def extract(self, text: str) -> list[dict[str, Any]]:
        """Run the model and map its labels onto our schema."""
        out = []
        for pred in self._pipe(text):
            label = self.label_map.get(pred.get("entity_group", ""))
            if label and float(pred.get("score", 0.0)) >= self.min_score:
                out.append(_entity(text, label, int(pred["start"]), int(pred["end"])))
        return out


def merge_entities(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union of two entity lists; on overlap the ``primary`` entity is kept."""
    return resolve_overlaps(list(primary) + list(secondary))


class EntityExtractor:
    """Configurable extractor: rule-based by default, optionally merged with a HF model."""

    def __init__(self, ner_config: dict[str, Any] | None = None) -> None:
        cfg = ner_config or {}
        self.hf_model: HFNERModel | None = None
        if cfg.get("use_hf_model"):
            try:
                self.hf_model = HFNERModel(cfg["hf_model_id"], cfg.get("hf_label_map", {}), cfg.get("hf_min_score", 0.6))
            except Exception as exc:  # noqa: BLE001 - fall back to rules rather than crash the pipeline
                logger.warning("Could not load HF NER model (%s); using rule-based NER only.", exc)

    def extract(self, text: str) -> list[dict[str, Any]]:
        """Return the entities found in ``text``, sorted by start offset."""
        entities = extract_rule_based(text)
        if self.hf_model is not None:
            entities = merge_entities(entities, self.hf_model.extract(text))
        return entities


def extract_entities(text: str) -> list[dict[str, Any]]:
    """Convenience wrapper: rule-based extraction with default settings."""
    return extract_rule_based(text)


def group_regimens(entities: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """Attach the DOSAGE/FREQUENCY/DURATION entities that follow each medication.

    A medication "owns" regimen entities up to the next medication or the end of its line.
    Returns ``[{"medication", "dosages", "frequencies", "durations"}]`` (texts only).
    """
    ordered = sorted(entities, key=lambda e: e["start"])
    regimens: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_line_end = -1
    keys = {"DOSAGE": "dosages", "FREQUENCY": "frequencies", "DURATION": "durations"}
    for ent in ordered:
        if ent["label"] == "MEDICATION":
            line_end = text.find("\n", ent["end"])
            current_line_end = len(text) if line_end == -1 else line_end
            current = {"medication": ent["text"], "dosages": [], "frequencies": [], "durations": []}
            regimens.append(current)
        elif ent["label"] in keys and current is not None and ent["start"] < current_line_end:
            bucket = current[keys[ent["label"]]]
            if ent["text"] not in bucket:
                bucket.append(ent["text"])
    # Drop repeat mentions of a drug that add nothing new, e.g. "... if ibuprofen not tolerated" or
    # "call if albuterol needed more often than every 4 hours"; keep the first detailed mention.
    def details(reg: dict[str, Any]) -> set[str]:
        return {t.lower() for key in ("dosages", "frequencies", "durations") for t in reg[key]}

    out: list[dict[str, Any]] = []
    for reg in sorted(regimens, key=lambda r: -len(details(r))):
        name = reg["medication"].lower()
        if any(r["medication"].lower() == name and details(reg) <= details(r) for r in out):
            continue
        out.append(reg)
    return sorted(out, key=regimens.index)
