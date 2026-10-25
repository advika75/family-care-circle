"""Create evidence-only, seeded MTSamples audit samples from existing local outputs.

No audit category is assigned by this script. Human labels start blank. Generation refuses
to replace an existing audit directory; use --summarize-* to inspect filled audit CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluator import RETENTION_LABELS, RETENTION_PERSONAS, persona_text, unsupported_meds, unsupported_numbers  # noqa: E402
from src.matching import normalize  # noqa: E402
from src.ner import extract_rule_based  # noqa: E402
from src.postprocess import find_contradicted_dosages  # noqa: E402

MANUAL_JUDGMENTS = ("true_issue", "false_positive", "uncertain")
SAFETY_NOTE_IDS = {
    "mtsamples_Accidental_Celesta_Ingestion_-_ER_Visit",
    "mtsamples_Aortobifemoral_Bypass_-_1", "mtsamples_Arterial_Imaging",
    "mtsamples_Carotid_Cerebral_Arteriograms", "mtsamples_Epididymectomy",
    "mtsamples_Escharotomy", "mtsamples_Laminotomy_Facetectomy_Foraminotomy",
    "mtsamples_Shunt_Revision", "mtsamples_Total_Knee_Replacement",
    "mtsamples_Umbilical_Hernia_Repair", "mtsamples_Weight_Gain_and_Edema",
}
NUMBER_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|half|quarter|several|a|an)"
CANDIDATE_PATTERNS = (
    ("DOSAGE", re.compile(rf"\b{NUMBER_WORD}\s+(?:milligrams?|mcg|micrograms?|grams?|g|milliliters?|ml|units?|tablets?|tabs?|capsules?|caps?|teaspoons?| tsp)\b", re.I)),
    ("DOSAGE", re.compile(r"\b\d+\s*/\s*\d+\s*(?:tablet|tab|capsule|cap)s?\b", re.I)),
    ("DOSAGE", re.compile(r"\b\d+\s*[-–/]\s*\d+\s*[-–/]\s*\d+\b")),
    ("FREQUENCY", re.compile(rf"\bevery\s+{NUMBER_WORD}\s+(?:to\s+{NUMBER_WORD}\s+)?hours?\b", re.I)),
    ("FREQUENCY", re.compile(r"\b(?:b\s*\.\s*i\s*\.\s*d\s*\.|t\s*\.\s*i\s*\.\s*d\s*\.|q\s*\.\s*\d+\s*h)\b", re.I)),
    ("DURATION", re.compile(rf"\b(?:for|x|×)\s+(?:{NUMBER_WORD})\s+(?:days?|weeks?|months?|years?)\b", re.I)),
)


def read_records(outputs_dir: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(outputs_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("id", path.stem)
        records.append(record)
    if not records:
        raise ValueError(f"No output JSON files in {outputs_dir}")
    return records


def source_context(source: str, start: int, end: int, radius: int = 100) -> str:
    left, right = max(0, start - radius), min(len(source), end + radius)
    return source[left:right].replace("\n", " ")


def retention_candidates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows, unmapped = [], 0
    for record in records:
        metadata = record.get("metadata", {})
        source = record.get("source_text", "")
        entities = record.get("entities", [])
        first_attempt_texts = metadata.get("first_attempt_text", {})
        for persona in RETENTION_PERSONAS:
            missing = metadata.get("missing_first_attempt", {}).get(persona) or []
            seen: set[tuple[str, str]] = set()
            for value in missing:
                norm = normalize(str(value))
                entity = next((e for e in entities if e.get("label") in RETENTION_LABELS
                               and normalize(e.get("text", "")) == norm), None)
                if entity is None:
                    unmapped += 1
                    continue
                key = (entity["label"], norm)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "note_id": record["id"], "persona": persona, "label": entity["label"],
                    "entity": entity["text"],
                    "source_ref": f"data/public/mtsamples/notes/{record['id']}.txt",
                    "output_ref": f"data/public/mtsamples/outputs/{record['id']}.json#{persona}",
                    "first_attempt_output_ref": (f"data/public/mtsamples/outputs/{record['id']}.json"
                                                  f"#/metadata/first_attempt_text/{persona}"
                                                  if persona in first_attempt_texts else ""),
                    "first_attempt_output": first_attempt_texts.get(persona, ""),
                    "first_attempt_evidence_available": persona in first_attempt_texts,
                    "source_context": source_context(source, entity["start"], entity["end"]),
                    "first_attempt_missing_entity": str(value),
                    "final_output": persona_text(record, persona),
                    "detector_decision": f"metadata.missing_first_attempt[{persona}] contains {value!r}",
                    "manual_judgment": "", "reason": "",
                })
    return rows, unmapped


def stratified_sample(rows: list[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["persona"], row["label"])].append(row)
    keys = sorted(groups)
    target = min(size, len(rows))
    quotas = {key: (1 if target >= len(keys) else 0) for key in keys}
    remaining = target - sum(quotas.values())
    while remaining:
        capacity = {key: len(groups[key]) - quotas[key] for key in keys}
        total = sum(capacity.values())
        if not total:
            break
        exact = {key: remaining * capacity[key] / total for key in keys}
        added = 0
        for key in keys:
            take = min(capacity[key], int(exact[key]))
            quotas[key] += take
            added += take
        remaining -= added
        if remaining:
            eligible = [key for key in keys if quotas[key] < len(groups[key])]
            eligible.sort(key=lambda key: (-(exact[key] - int(exact[key])), key))
            for key in eligible[:remaining]:
                quotas[key] += 1
                remaining -= 1
        if added == 0 and not eligible:
            break
    rng = random.Random(seed)
    sampled = []
    for key in keys:
        bucket = sorted(groups[key], key=lambda row: (row["note_id"], row["entity"], row["first_attempt_missing_entity"]))
        sampled.extend(rng.sample(bucket, quotas[key]))
    return sampled


def unsupported_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        source, entities = record.get("source_text", ""), record.get("entities", [])
        for persona in ("patient_summary", "caregiver_checklist", "child_explanation"):
            output = persona_text(record, persona)
            for item in unsupported_numbers(output, source, entities)["unsupported"]:
                match = re.search(re.escape(item.split()[0]), output, re.I)
                context = output[max(0, match.start() - 80):min(len(output), match.end() + 100)] if match else ""
                rows.append({"note_id": record["id"], "persona": persona, "flagged_item": item,
                             "source_ref": f"data/public/mtsamples/notes/{record['id']}.txt",
                             "output_ref": f"data/public/mtsamples/outputs/{record['id']}.json#{persona}",
                             "source_context": source[:250].replace("\n", " "),
                             "output_context": context,
                             "detector_decision": f"unsupported_numbers flagged {item!r}",
                             "manual_judgment": "", "reason": ""})
    return rows


def regimen_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        source = record.get("source_text", "")
        extracted = extract_rule_based(source)
        spans = {(e["label"], e["start"], e["end"]) for e in extracted}
        for label, pattern in CANDIDATE_PATTERNS:
            for match in pattern.finditer(source):
                if (label, match.start(), match.end()) in spans:
                    continue
                found[(label, match.group(0))].add(record["id"])
    return [{"candidate_label": label, "candidate_form": form, "count": len(note_ids),
             "note_ids": ";".join(sorted(note_ids)), "interpretation": "candidate pattern only; not recall"}
            for (label, form), note_ids in sorted(found.items(), key=lambda item: (item[0][0], item[0][1].lower()))]


def safety_candidates(records: list[dict[str, Any]], postfix_records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """List before/after medication and dose flags for the fixed 11-note safety set; never assign judgments."""
    by_id = {record["id"]: record for record in (postfix_records or [])}
    rows = []
    for record in records:
        if record["id"] not in SAFETY_NOTE_IDS:
            continue
        note_id = record["id"]
        source = record.get("source_text", "")
        after = by_id.get(note_id, {})
        for persona in ("patient_summary", "caregiver_checklist", "child_explanation"):
            before_text = persona_text(record, persona)
            after_text = persona_text(after, persona) if after else ""
            before_meds = unsupported_meds(before_text, source, record.get("entities", []))["unsupported"]
            after_meds = unsupported_meds(after_text, source, after.get("entities", []))["unsupported"] if after else []
            before_doses = [f["dose"] for f in find_contradicted_dosages(before_text, source)]
            after_doses = [f["dose"] for f in find_contradicted_dosages(after_text, source)] if after else []
            for flag_type, before, after_flags in (("unsupported medication", before_meds, after_meds),
                                                    ("contradicted directive dose", before_doses, after_doses)):
                for item in dict.fromkeys([*before, *after_flags]):
                    rows.append({"note_id": note_id, "persona": persona, "flag_type": flag_type,
                                 "flagged_item": item,
                                 "source_ref": f"data/public/mtsamples/notes/{note_id}.txt",
                                 "output_ref": f"data/public/mtsamples/outputs/{note_id}.json#{persona}",
                                 "postfix_output_ref": (f"data/public/mtsamples/outputs_postfix/{note_id}.json#{persona}"
                                                        if after else ""),
                                 "detector_decision": (
                                     f"before: {'flagged' if item in before else 'not flagged'}; "
                                     f"after: {'flagged' if item in after_flags else 'not flagged'} by "
                                     f"{'unsupported_meds' if flag_type == 'unsupported medication' else 'find_contradicted_dosages'}"),
                                 "manual_judgment": "", "reason": ""})
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: "\n".join(line.rstrip() for line in str(row.get(key, "")).splitlines())
                          for key in fields} for row in rows)


def category_counts(rows: list[dict[str, Any]], categories: tuple[str, ...], kind: str) -> list[dict[str, Any]]:
    counts = Counter(row.get("manual_judgment", "").strip() for row in rows)
    result = [{"kind": kind, "category": category, "count": counts[category]} for category in categories]
    result.append({"kind": kind, "category": "pending / blank", "count": counts[""]})
    return result


def score_unsupported(path: Path) -> tuple[int, int, int, int, float | None]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = [row.get("manual_judgment", "").strip() for row in rows]
    invalid = sorted(set(label for label in labels if label and label not in MANUAL_JUDGMENTS))
    if invalid:
        raise ValueError(f"Unsupported manual_judgment values: {', '.join(invalid)}")
    judged = [label for label in labels if label]
    true_positive = sum(label == "true_issue" for label in judged)
    false_positive = sum(label == "false_positive" for label in judged)
    uncertain = sum(label == "uncertain" for label in judged)
    decisive = true_positive + false_positive
    return true_positive, false_positive, uncertain, len(judged), true_positive / decisive if decisive else None


def summarize_retention(path: Path) -> Counter[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = [row.get("manual_judgment", "").strip() for row in rows]
    invalid = sorted(set(label for label in labels if label and label not in MANUAL_JUDGMENTS))
    if invalid:
        raise ValueError(f"Unsupported manual_judgment values: {', '.join(invalid)}")
    return Counter(label or "pending / blank" for label in labels)


def literal_spans(text: str, needle: str) -> list[dict[str, Any]]:
    """Return exact, case-insensitive text spans with offsets for audit review."""
    if not needle:
        return []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return [{"start": match.start(), "end": match.end(), "text": match.group(0)}
            for match in pattern.finditer(text)]


def export_case_evidence(audit_dir: Path, outputs_dir: Path, output_path: Path) -> int:
    """Export preserved audit cases with source/output spans; never edit judgments."""
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence report: {output_path}")
    rows: list[dict[str, Any]] = []
    for filename, selector in (
        ("retention_audit.csv", lambda row: row.get("manual_judgment", "").strip() in ("", "uncertain")),
        ("unsupported_numbers_sample.csv", lambda row: row.get("note_id") == "mtsamples_Weight_Gain_and_Edema"
         and row.get("flagged_item") == "10 mg"),
        ("safety_audit.csv", lambda row: True),
    ):
        audit_path = audit_dir / filename
        with audit_path.open(encoding="utf-8-sig", newline="") as stream:
            audit_rows = list(csv.DictReader(stream))
        for audit_row in audit_rows:
            if not selector(audit_row):
                continue
            note_id = audit_row["note_id"]
            record_path = outputs_dir / f"{note_id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            source = record.get("source_text", "")
            persona = audit_row.get("persona", "")
            output = persona_text(record, persona)
            first_texts = record.get("metadata", {}).get("first_attempt_text", {})
            first_attempt_output = (first_texts[persona] if persona in first_texts
                                    else audit_row.get("first_attempt_output", ""))
            expected = audit_row.get("entity") or audit_row.get("flagged_item", "")
            # Entity and number matches are literal offsets; hold/negation context is included below.
            source_spans = literal_spans(source, expected)
            output_spans = literal_spans(output, expected)
            postfix_output = ""
            postfix_ref = audit_row.get("postfix_output_ref", "")
            if postfix_ref:
                postfix_path = Path(postfix_ref.split("#", 1)[0])
                if postfix_path.exists():
                    post = json.loads(postfix_path.read_text(encoding="utf-8"))
                    postfix_output = persona_text(post, persona)
            proposed, proposed_reason = "", ""
            if filename == "unsupported_numbers_sample.csv" and note_id == "mtsamples_Weight_Gain_and_Edema":
                proposed = "true_issue"
                proposed_reason = ("Generated checklist assigns lisinopril 10 mg daily; source says lisinopril is on hold "
                                   "and provides no lisinopril dose. Proposal only; existing label is unchanged.")
            elif filename == "retention_audit.csv":
                proposed_reason = (
                    "First-attempt prose is not stored in this legacy output, so the miss list cannot establish "
                    "whether equivalent wording appeared. Manual decision required."
                    if persona not in first_texts else
                    "Captured first-attempt prose is included for comparison; no judgment is assigned automatically."
                )
            rows.append({
                "audit_file": filename, "note_id": note_id, "persona": persona,
                "expected_entity_or_number": expected, "detector_or_matcher_decision": audit_row.get("detector_decision", ""),
                "existing_judgment": audit_row.get("manual_judgment", ""), "proposed_judgment": proposed,
                "proposal_reason": proposed_reason, "source_ref": audit_row.get("source_ref", ""),
                "source_entity_offsets": json.dumps(source_spans, ensure_ascii=False),
                "source_context": audit_row.get("source_context", ""), "source_text": source,
                "first_attempt_output_ref": audit_row.get("first_attempt_output_ref", (
                    f"{record_path}#/metadata/first_attempt_text/{persona}" if persona in first_texts else "")),
                "first_attempt_output": first_attempt_output,
                "first_attempt_output_spans": json.dumps(literal_spans(first_attempt_output, expected), ensure_ascii=False),
                "output_ref": audit_row.get("output_ref", ""), "output_spans": json.dumps(output_spans, ensure_ascii=False),
                "generated_output": output, "postfix_output_ref": postfix_ref, "postfix_output": postfix_output,
                "first_attempt_prose_available": str(persona in first_texts).lower(),
            })
    fields = list(rows[0]) if rows else []
    if not fields:
        raise ValueError(f"No cases found in audits under {audit_dir}")
    write_csv(output_path, rows, fields)
    return len(rows)


def generate(outputs_dir: Path, output_dir: Path, seed: int) -> tuple[int, int, int, int, int]:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit directory: {output_dir}")
    records = read_records(outputs_dir)
    retention, unmapped = retention_candidates(records)
    sampled_retention = stratified_sample(retention, 40, seed)
    unsupported = unsupported_candidates(records)
    postfix_dir = Path("data/public/mtsamples/outputs_postfix")
    postfix = read_records(postfix_dir) if postfix_dir.exists() else []
    safety = safety_candidates(records, postfix)
    rng = random.Random(seed)
    sampled_unsupported = rng.sample(unsupported, min(60, len(unsupported)))
    candidates = regimen_candidates(records)

    output_dir.mkdir(parents=True)
    write_csv(output_dir / "retention_audit.csv", sampled_retention,
              ["note_id", "persona", "label", "entity", "source_ref", "output_ref", "first_attempt_output_ref",
               "first_attempt_output", "first_attempt_evidence_available", "source_context",
               "first_attempt_missing_entity", "final_output", "detector_decision", "manual_judgment", "reason"])
    write_csv(output_dir / "unsupported_numbers_sample.csv", sampled_unsupported,
              ["note_id", "persona", "flagged_item", "source_ref", "output_ref", "source_context",
               "output_context", "detector_decision", "manual_judgment", "reason"])
    write_csv(output_dir / "safety_audit.csv", safety,
              ["note_id", "persona", "flag_type", "flagged_item", "source_ref", "output_ref", "postfix_output_ref",
               "detector_decision", "manual_judgment", "reason"])
    write_csv(output_dir / "regimen_candidate_patterns.csv", candidates,
              ["candidate_label", "candidate_form", "count", "note_ids", "interpretation"])
    counts = category_counts(sampled_retention, MANUAL_JUDGMENTS, "retention")
    counts += category_counts(sampled_unsupported, MANUAL_JUDGMENTS, "unsupported_numbers")
    for (persona, label), n in sorted(Counter((r["persona"], r["label"]) for r in sampled_retention).items()):
        counts.append({"kind": "retention_stratum", "category": f"{persona}:{label}", "count": n})
    write_csv(output_dir / "audit_category_counts.csv", counts, ["kind", "category", "count"])
    (output_dir / "README.md").write_text(
        "# MTSamples audits\n\n"
        f"Evidence samples from `{outputs_dir}`; seed `{seed}`. Manual judgments start blank. "
        "No model judge or automatic category assignment is used. Allowed `manual_judgment` values "
        "are `true_issue`, `false_positive`, and `uncertain`; record a brief reason.\n\n"
        "`retention_audit.csv` samples first-attempt missing entities, stratified by persona and label. "
        "New pipeline outputs include `first_attempt_output` and its JSON reference. Legacy outputs without "
        "captured prose leave this field empty; `final_output` is never substituted for it. The detector "
        "decision and source/output references are included in each row.\n\n"
        "`unsupported_numbers_sample.csv` records the detector decision and source/output references. "
        "Run `python scripts/audit_mtsamples.py --score-unsupported "
        "results/mtsamples/audits/unsupported_numbers_sample.csv` after filling labels. Precision is "
        "true issues divided by decisive reviewed flags (`true_issue` + `false_positive`); uncertain "
        "rows are reported separately. False negatives are not measurable from this flagged-only sample.\n\n"
        "`safety_audit.csv` lists unsupported-medication and contradicted-dose flags from the fixed 11-note "
        "safety set. It does not assign judgments; compare each source note and generated output.\n\n"
        "`regimen_candidate_patterns.csv` is a regex candidate list found in source notes without an "
        "exact same-label extractor span. Counts are notes containing the form, not recall estimates.\n",
        encoding="utf-8")
    return len(records), len(sampled_retention), len(sampled_unsupported), len(candidates), unmapped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs-dir", type=Path, default=Path("data/public/mtsamples/outputs"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/mtsamples/audits"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--score-unsupported", type=Path, help="Score a filled unsupported_numbers_sample.csv")
    parser.add_argument("--summarize-retention", type=Path, help="Count labels in a filled retention_audit.csv")
    parser.add_argument("--export-case-evidence", type=Path,
                        help="Export uncertain/pending retention, the Weight Gain 10 mg conflict, and safety cases")
    args = parser.parse_args()
    try:
        if args.score_unsupported:
            tp, fp, uncertain, reviewed, precision = score_unsupported(args.score_unsupported)
            if precision is None:
                print(f"Unsupported-number audit: TP={tp}, FP={fp}, uncertain={uncertain}, "
                      f"reviewed={reviewed}; precision unavailable (no decisive judgments).")
            else:
                print(f"Unsupported-number audit: TP={tp}, FP={fp}, uncertain={uncertain}, "
                      f"reviewed={reviewed}; precision among decisive flags={tp}/{tp + fp}={precision:.3f}. "
                      "False negatives are not measurable from this flagged-only sample.")
            return 0
        if args.summarize_retention:
            counts = summarize_retention(args.summarize_retention)
            print("; ".join(f"{label}: {counts[label]}" for label in (*MANUAL_JUDGMENTS, "pending / blank")))
            return 0
        if args.export_case_evidence:
            count = export_case_evidence(args.output_dir, args.outputs_dir, args.export_case_evidence)
            print(f"Exported {count} review cases with source/output text and literal spans; existing labels unchanged.")
            return 0
        n_records, n_retention, n_unsupported, n_patterns, unmapped = generate(
            args.outputs_dir, args.output_dir, args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Audited {n_records} notes; retention sample {n_retention}; unsupported-number sample {n_unsupported}; "
          f"unmatched candidate forms {n_patterns}; unmapped misses {unmapped}; seed {args.seed}.")
    print("Manual judgments start blank; no automatic judgments assigned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
