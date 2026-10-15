"""Evaluation: readability, ROUGE, entity retention, format validity and NER against gold."""

from __future__ import annotations

import math
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import textstat
from rouge_score import rouge_scorer

import re
from collections import Counter

from src.matching import NUMBER_WORDS, find_missing, frequency_variants, normalize, unique_entities
from src.ner import _LEXICONS
from src.prompts import PERSONAS
from src.utils import list_files, read_json, read_text

RETENTION_LABELS = ("MEDICATION", "DOSAGE", "FREQUENCY", "DURATION")
RETENTION_PERSONAS = ("patient_summary", "caregiver_checklist")


# --------------------------------------------------------------------------- text metrics

def persona_text(record: dict[str, Any], persona: str) -> str:
    """Return a persona's output as plain text (checklists are joined one item per line)."""
    value = record.get(persona, "")
    return "\n".join(value) if isinstance(value, list) else str(value or "")


def readability(text: str) -> dict[str, float]:
    """Flesch-Kincaid Grade Level (lower = easier) and Flesch Reading Ease (higher = easier)."""
    if not text.strip():
        return {"fkgl": math.nan, "fre": math.nan}
    return {"fkgl": textstat.flesch_kincaid_grade(text), "fre": textstat.flesch_reading_ease(text)}


@lru_cache(maxsize=1)
def _scorer() -> rouge_scorer.RougeScorer:
    return rouge_scorer.RougeScorer(["rouge1", "rougeL"], use_stemmer=True)


def rouge(prediction: str, reference: str) -> dict[str, float]:
    """ROUGE-1 and ROUGE-L F1 of ``prediction`` against ``reference``."""
    scores = _scorer().score(reference, prediction)
    return {"rouge1": scores["rouge1"].fmeasure, "rougeL": scores["rougeL"].fmeasure}


def entity_retention(
    entities: Iterable[dict[str, Any]], text: str, labels: Iterable[str] = RETENTION_LABELS
) -> dict[str, Any]:
    """Fraction of unique source entities (of ``labels``) present in ``text``, overall and per label.

    Labels with no source entities get ``NaN`` recall.
    """
    labels = tuple(labels)
    source = unique_entities(entities, labels)
    missing = find_missing(text, source)
    missing_keys = {(m["label"], m["text"]) for m in missing}
    per_label = {}
    for label in labels:
        of_label = [e for e in source if e["label"] == label]
        kept = [e for e in of_label if (e["label"], e["text"]) not in missing_keys]
        per_label[label] = len(kept) / len(of_label) if of_label else math.nan
    overall = (len(source) - len(missing)) / len(source) if source else math.nan
    return {"overall": overall, "per_label": per_label, "missing": [m["text"] for m in missing], "n": len(source)}


def retention_from_missing(
    entities: Iterable[dict[str, Any]], missing_texts: Iterable[str] | None, labels: Iterable[str] = RETENTION_LABELS
) -> dict[str, Any]:
    """Retention computed from a recorded list of missing entity texts (overall and per label).

    Used for what the pipeline logged at generation time (first attempt, after retries) - i.e. the
    model's own text, before the fallback appended anything. ``None`` (not recorded) gives NaN.
    """
    labels = tuple(labels)
    source = unique_entities(entities, labels)
    if missing_texts is None:
        return {"overall": math.nan, "per_label": {label: math.nan for label in labels}}
    missing = {normalize(t) for t in missing_texts}
    per_label = {}
    for label in labels:
        of_label = [e for e in source if e["label"] == label]
        kept = [e for e in of_label if normalize(e["text"]) not in missing]
        per_label[label] = len(kept) / len(of_label) if of_label else math.nan
    kept_all = [e for e in source if normalize(e["text"]) not in missing]
    return {"overall": len(kept_all) / len(source) if source else math.nan, "per_label": per_label}


# --------------------------------------------------------------------------- hallucination checks

_QTY_UNITS = r"mg|mcg|g|ml|meq|iu|unit|puff|tablet|capsule|drop|spray|day|week|month|hour|minute|year|time|lb|degree"
_QUANTITY_RE = re.compile(rf"(?<![\w.])(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s?({_QTY_UNITS})?(?![\w])")
_RANGE_RE = re.compile(rf"(?<![\w.])(\d+(?:\.\d+)?)\s+(?:to\s+|or\s+)?(\d+(?:\.\d+)?)\s?({_QTY_UNITS})(?![\w])")
_UNIT_WORDS = (r"mg|milligrams?|mcg|micrograms?|ml|milliliters?|units?|puffs?|tablets?|tabs?|capsules?|pills?|"
               r"drops?|sprays?|days?|weeks?|months?|hours?|minutes?|years?|times?|doses?")
_BARE_NUMBER_WORD_RE = re.compile(
    rf"\b(?:{'|'.join(NUMBER_WORDS)})\b(?!\s*-?\s*(?:{_UNIT_WORDS})\b)", re.IGNORECASE)
_LOOSE_UNITS = {"degree", "lb", "year", "minute"}  # not dosing units: a matching bare number is enough
_LIST_MARKER_RE = re.compile(r"^\s*\d{1,2}[.)]\s+", re.MULTILINE)  # "4. Your doctor ..." is not a quantity
_IGNORED_NUMBERS = {"911", "988"}  # emergency / crisis line numbers

_DRUG_SUFFIXES = (
    "cillin", "mycin", "micin", "cycline", "floxacin", "sartan", "pril", "olol", "statin", "prazole", "tidine",
    "triptan", "gliflozin", "gliptin", "glutide", "formin", "dipine", "azole", "oxetine", "alopram", "azepam",
    "zolam", "codone", "morphone", "profen", "olone", "isone", "lukast", "xaban", "gatran", "semide", "thiazide",
    "parin", "setron", "oxacin", "butamol", "buterol",
)
_NOT_DRUGS = {"april", "cholesterol", "problem", "system", "cyclone", "ozone"}
_BRAND_TO_GENERIC = {
    "tylenol": "acetaminophen", "panadol": "acetaminophen", "advil": "ibuprofen", "motrin": "ibuprofen",
    "aleve": "naproxen", "augmentin": "amoxicillin", "zithromax": "azithromycin", "keflex": "cephalexin",
    "macrobid": "nitrofurantoin", "pyridium": "phenazopyridine", "glucophage": "metformin", "jardiance": "empagliflozin",
    "lipitor": "atorvastatin", "zestril": "lisinopril", "norvasc": "amlodipine", "ventolin": "albuterol",
    "proair": "albuterol", "flovent": "fluticasone", "zofran": "ondansetron", "colace": "docusate",
    "eliquis": "apixaban", "lasix": "furosemide", "zoloft": "sertraline", "imitrex": "sumatriptan",
    "entresto": "sacubitril", "coreg": "carvedilol", "toprol": "metoprolol", "tessalon": "benzonatate",
}
_CAPITALIZED_WITH_DOSE_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{3,})\s+\d+(?:\.\d+)?\s?(?:mg|mcg|ml|units?)\b",
                                       re.MULTILINE)


def _quantities(normalized: str) -> list[tuple[str, str | None]]:
    return [(m.group(1), m.group(2)) for m in _QUANTITY_RE.finditer(normalized)]


def _mask_bare_number_words(text: str) -> str:
    """Drop counting words ("one of your medicines") unless they attach to a unit ("two tablets")."""
    return _BARE_NUMBER_WORD_RE.sub(" ", text)


def source_support(source: str, entities: Iterable[dict[str, Any]] = ()) -> str:
    """Normalized source text plus plain-English variants of its frequencies ("BID" -> "2 time a day")."""
    variants = [v for e in entities if e.get("label") == "FREQUENCY" for v in frequency_variants(e["text"])]
    return " ; ".join([normalize(source), *sorted(set(variants))])


def unsupported_numbers(output: str, source: str, entities: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Numbers (with their unit, if any) in ``output`` that the source note does not support.

    A number with a unit needs the same number+unit in the source (ranges like "48-72 hours" support
    both ends); a bare number, or one with a non-dosing unit (degrees, lb), only needs the number.
    Returns ``{"unsupported": [...], "n_checked": int}``.
    """
    support = source_support(source, entities)
    src_quantities = set(_quantities(support))
    for m in _RANGE_RE.finditer(support):
        src_quantities.update({(m.group(1), m.group(3)), (m.group(2), m.group(3))})
    src_numbers = {num for num, _ in src_quantities}
    cleaned = _LIST_MARKER_RE.sub("", _mask_bare_number_words(output))
    found = [q for q in _quantities(normalize(cleaned)) if q[0] not in _IGNORED_NUMBERS]
    unsupported = []
    for num, unit in found:
        ok = num in src_numbers if unit is None or unit in _LOOSE_UNITS else (num, unit) in src_quantities
        label = f"{num} {unit}" if unit else num
        if not ok and label not in unsupported:
            unsupported.append(label)
    return {"unsupported": unsupported, "n_checked": len(found)}


def medication_mentions(text: str) -> list[str]:
    """Medication-like names in ``text``: lexicon hits, drug-name suffixes, capitalized words followed by a dose."""
    names = [m.group(0).lower() for m in _LEXICONS["MEDICATION"].finditer(text)]
    for word in re.findall(r"[A-Za-z][A-Za-z-]{5,}", text):
        low = word.lower()
        if low.endswith(_DRUG_SUFFIXES) and low not in _NOT_DRUGS:
            names.append(low)
    names += [m.group(1).lower() for m in _CAPITALIZED_WITH_DOSE_RE.finditer(text)]
    names += [w.lower() for w in re.findall(r"[A-Za-z]+", text) if w.lower() in _BRAND_TO_GENERIC]
    return list(dict.fromkeys(names))


def unsupported_meds(output: str, source: str, entities: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Medication-like names in ``output`` that neither the source text nor its MEDICATION entities contain.

    Brand names count as supported when their generic is in the source ("Tylenol" for acetaminophen).
    Returns ``{"unsupported": [...], "n_checked": int}``.
    """
    src = normalize(source)
    src_meds = {normalize(e["text"]) for e in entities if e.get("label") == "MEDICATION"}

    def supported(name: str) -> bool:
        norm = normalize(name)
        generic = _BRAND_TO_GENERIC.get(name)
        return (norm in src_meds or re.search(rf"(?<![a-z0-9]){re.escape(norm)}(?![a-z0-9])", src) is not None
                or (generic is not None and generic in src))

    mentions = medication_mentions(output)
    return {"unsupported": [m for m in mentions if not supported(m)], "n_checked": len(mentions)}


REPETITION_THRESHOLD = 0.9   # Dice token overlap above which two lines count as (near-)duplicates
REPETITION_MIN_TOKENS = 3    # shorter units ("Rest.", "Okay.") are ignored


def _units(text: str, persona: str) -> list[str]:
    """Bullets for the caregiver checklist, sentences for the other personas."""
    if persona == "caregiver_checklist":
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _tokens(unit: str) -> Counter:
    unit = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", unit.lower())
    return Counter(re.findall(r"[a-z0-9]+(?:[.'/][a-z0-9]+)*", unit))


# Tokens that distinguish facts: "take 90 mcg" vs "take 44 mcg", "once a day" vs "twice a day".
_KEY_WORDS = set(NUMBER_WORDS) | {"once", "twice", "thrice", "daily", "weekly", "nightly", "hourly", "morning",
                                  "evening", "night", "bedtime", "hours", "hour", "days", "day", "weeks", "week"}


def _key_tokens(tokens: Counter) -> Counter:
    return Counter({t: n for t, n in tokens.items() if t in _KEY_WORDS or any(c.isdigit() for c in t)})


def token_overlap(a: Counter, b: Counter) -> float:
    """Dice coefficient of two token multisets: 2·|a ∩ b| / (|a| + |b|)."""
    total = sum(a.values()) + sum(b.values())
    return 2 * sum((a & b).values()) / total if total else 0.0


def repeated_units(text: str, persona: str, threshold: float = REPETITION_THRESHOLD) -> list[dict[str, Any]]:
    """Lines (caregiver bullets) or sentences that duplicate or nearly duplicate an earlier one.

    Case, whitespace, punctuation and bullet markers are ignored. A near-duplicate also needs the same
    numbers and frequency words, so parallel sentences about different doses or schedules ("Each pill is
    875 mg" / "Each pill is 500 mg") are not counted. Returns
    ``[{"index", "text", "earlier_index", "earlier", "overlap"}]`` (0-based unit indices).
    """
    units = _units(text, persona)
    seen: list[tuple[int, str, Counter]] = []
    repeats = []
    for i, unit in enumerate(units):
        toks = _tokens(unit)
        if sum(toks.values()) < REPETITION_MIN_TOKENS:
            continue
        keys = _key_tokens(toks)
        best = max(((token_overlap(toks, t), j, u) for j, u, t in seen if _key_tokens(t) == keys), default=None)
        if best and best[0] > threshold:
            repeats.append({"index": i, "text": unit, "earlier_index": best[1], "earlier": best[2],
                            "overlap": round(best[0], 3)})
        seen.append((i, unit, toks))
    return repeats


CHILD_MAX_SENTENCE_WORDS = 8  # the v2 child prompt asks for sentences of fewer than 8 words


def child_rule_checks(text: str) -> dict[str, float]:
    """How well a child text follows the v2 rules: short sentences, no medicine names, no numbers."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if re.search(r"[A-Za-z]", s)]
    long_ones = [s for s in sentences if len(re.findall(r"[A-Za-z0-9'’-]+", s)) >= CHILD_MAX_SENTENCE_WORDS]
    numbers = _quantities(normalize(_LIST_MARKER_RE.sub("", _mask_bare_number_words(text))))
    return {
        "long_sentence_rate": len(long_ones) / len(sentences) if sentences else math.nan,
        "med_names": float(len(medication_mentions(text))),
        "numbers": float(len(numbers)),
    }


def _flag(value: Any) -> float:
    """bool -> 1.0/0.0; None/missing -> NaN (not recorded)."""
    return math.nan if value is None else float(bool(value))


def evaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Compute all per-sample metrics for one pipeline output record. Returns a flat dict."""
    source = record.get("source_text", "")
    meta = record.get("metadata", {})
    src_read = readability(source)
    row: dict[str, Any] = {
        "id": record.get("id"),
        "backend": meta.get("backend"),
        "model_id": meta.get("model_id"),
        "source_fkgl": src_read["fkgl"],
        "source_fre": src_read["fre"],
    }
    for persona in PERSONAS:
        text = persona_text(record, persona)
        read = readability(text)
        row[f"{persona}_fkgl"] = read["fkgl"]
        row[f"{persona}_fre"] = read["fre"]
        row[f"{persona}_fkgl_delta"] = read["fkgl"] - src_read["fkgl"]
        row.update({f"{persona}_{k}": v for k, v in rouge(text, source).items()})
        row[f"{persona}_words"] = len(text.split())
        for kind, check in (("numbers", unsupported_numbers), ("meds", unsupported_meds)):
            res = check(text, source, record.get("entities", []))
            row[f"{persona}_unsupported_{kind}"] = len(res["unsupported"])
            row[f"{persona}_unsupported_{kind}_rate"] = (
                len(res["unsupported"]) / res["n_checked"] if res["n_checked"] else math.nan)
            row[f"{persona}_unsupported_{kind}_list"] = "; ".join(res["unsupported"])
    for persona in RETENTION_PERSONAS:
        ret = entity_retention(record.get("entities", []), persona_text(record, persona))
        row[f"{persona}_retention"] = ret["overall"]
        row.update({f"{persona}_retention_{lbl.lower()}": v for lbl, v in ret["per_label"].items()})
        row[f"{persona}_missing"] = "; ".join(ret["missing"])
        # The model's own text: after retries but before the fallback ("model"), and on the first attempt.
        for suffix, key in (("model", "missing_after_retries"), ("first", "missing_first_attempt")):
            logged = retention_from_missing(record.get("entities", []), meta.get(key, {}).get(persona))
            row[f"{persona}_retention_{suffix}"] = logged["overall"]
            row.update({f"{persona}_retention_{suffix}_{lbl.lower()}": v for lbl, v in logged["per_label"].items()})
    for persona in PERSONAS:
        # 0/1 per sample, so the mean over samples is a rate. NaN when an older output did not record it.
        row[f"{persona}_truncation_rate"] = _flag(meta.get("truncated", {}).get(persona))
        row[f"{persona}_fallback"] = _flag(meta.get("fallback_used", {}).get(persona))
        # 0/1: the output repeats a bullet/sentence (mean over samples = repetition rate).
        row[f"{persona}_repetition"] = float(bool(repeated_units(persona_text(record, persona), persona)))
    for key, value in child_rule_checks(persona_text(record, "child_explanation")).items():
        row[f"child_explanation_{key}"] = value
    retries = meta.get("retries", {})
    row["valid"] = bool(meta.get("valid", False))
    row["total_retries"] = sum(retries.values())
    row["fallbacks"] = sum(bool(v) for v in meta.get("fallback_used", {}).values())
    row["latency_total_sec"] = meta.get("latency_sec", {}).get("total", math.nan)
    return row


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Mean and standard deviation of every numeric metric across samples."""
    numeric = df.select_dtypes(include="number").astype(float)
    summary = pd.DataFrame({"mean": numeric.mean(), "std": numeric.std(ddof=0)})
    if "valid" in df:
        summary.loc["format_validity_rate"] = [df["valid"].astype(float).mean(), math.nan]
    summary.index.name = "metric"
    return summary


# --------------------------------------------------------------------------- NER vs gold

def _overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def match_entities(
    predicted: list[dict[str, Any]], gold: list[dict[str, Any]], mode: str = "exact"
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """One-to-one matching of predicted to gold entities with the same label.

    ``exact`` requires identical offsets; ``relaxed`` requires overlapping spans.
    """
    if mode not in ("exact", "relaxed"):
        raise ValueError("mode must be 'exact' or 'relaxed'")
    pairs, used = [], set()
    for p in predicted:
        for i, g in enumerate(gold):
            if i in used or p["label"] != g["label"]:
                continue
            hit = (p["start"], p["end"]) == (g["start"], g["end"]) if mode == "exact" else _overlaps(p, g)
            if hit:
                pairs.append((p, g))
                used.add(i)
                break
    return pairs


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def ner_scores(
    docs: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]], mode: str = "exact"
) -> dict[str, dict[str, float]]:
    """Per-label and micro-averaged P/R/F1 over ``[(predicted, gold), ...]`` documents."""
    counts: dict[str, list[int]] = {}
    for predicted, gold in docs:
        matched = match_entities(predicted, gold, mode)
        for label in {e["label"] for e in predicted} | {e["label"] for e in gold}:
            tp = sum(1 for p, _ in matched if p["label"] == label)
            c = counts.setdefault(label, [0, 0, 0])
            c[0] += tp
            c[1] += sum(1 for e in predicted if e["label"] == label) - tp
            c[2] += sum(1 for e in gold if e["label"] == label) - tp
    scores = {label: _prf(*c) for label, c in sorted(counts.items())}
    totals = [sum(c[i] for c in counts.values()) for i in range(3)]
    scores["MICRO"] = _prf(*totals)
    return scores


def evaluate_ner_against_gold(
    gold_dir: str | Path, raw_dir: str | Path, extract_fn: Any
) -> pd.DataFrame:
    """Run NER against gold files, using only ``complete`` manifest entries when present."""
    from src.datasets import load_annotation

    gold_dir, raw_dir = Path(gold_dir), Path(raw_dir)
    docs = []
    manifest_path = gold_dir / "annotation_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = read_json(manifest_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read annotation manifest {manifest_path}: {exc}") from exc
        entries = manifest.get("annotations") if isinstance(manifest, dict) else None
        if not isinstance(entries, list):
            raise ValueError(f"Invalid annotation manifest {manifest_path}: expected annotations list")
        sources = [(entry.get("id"), entry.get("source_file")) for entry in entries
                   if isinstance(entry, dict) and entry.get("status") == "complete"]
    else:
        sources = [(p.stem, f"{p.stem}.txt") for p in list_files(gold_dir, (".json",))]
    for note_id, source_file in sources:
        if not isinstance(note_id, str) or not note_id or not isinstance(source_file, str) or not source_file:
            raise ValueError(f"Malformed completed annotation entry in {manifest_path}")
        gold_path = gold_dir / f"{note_id}.json"
        note_path = raw_dir / Path(source_file.replace("\\", "/")).name
        text = read_text(note_path)
        gold = load_annotation(gold_path, note_path)
        if gold["id"] != note_id:
            raise ValueError(f"Completed note {note_id}: annotation id is {gold['id']!r}")
        docs.append((extract_fn(text), gold["entities"]))
    if not docs:
        return pd.DataFrame(columns=["mode", "label", "precision", "recall", "f1", "tp", "fp", "fn", "n_docs"])
    rows = []
    for mode in ("exact", "relaxed"):
        for label, s in ner_scores(docs, mode).items():
            rows.append({"mode": mode, "label": label, **s, "n_docs": len(docs)})
    return pd.DataFrame(rows)
