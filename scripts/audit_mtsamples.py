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

from src.evaluator import RETENTION_LABELS, RETENTION_PERSONAS, persona_text, unsupported_numbers  # noqa: E402
from src.matching import normalize  # noqa: E402
from src.ner import extract_rule_based  # noqa: E402

RETENTION_CATEGORIES = ("true omission", "matcher failure", "extraction error", "unclear")
UNSUPPORTED_CATEGORIES = ("true fabrication", "equivalent", "format mismatch", "other")
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
                    "source_context": source_context(source, entity["start"], entity["end"]),
                    "first_attempt_missing_entity": str(value),
                    "final_output": persona_text(record, persona),
                    "human_label": "",
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
                             "source_context": source[:250].replace("\n", " "),
                             "output_context": context, "human_label": ""})
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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: "\n".join(line.rstrip() for line in str(row.get(key, "")).splitlines())
                          for key in fields} for row in rows)


def category_counts(rows: list[dict[str, Any]], categories: tuple[str, ...], kind: str) -> list[dict[str, Any]]:
    counts = Counter(row.get("human_label", "").strip() for row in rows)
    result = [{"kind": kind, "category": category, "count": counts[category]} for category in categories]
    result.append({"kind": kind, "category": "pending / blank", "count": counts[""]})
    return result


def score_unsupported(path: Path) -> tuple[int, int, float | None]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = [row.get("human_label", "").strip() for row in rows]
    invalid = sorted(set(label for label in labels if label and label not in UNSUPPORTED_CATEGORIES))
    if invalid:
        raise ValueError(f"Unsupported human_label values: {', '.join(invalid)}")
    judged = [label for label in labels if label]
    true_positive = sum(label == "true fabrication" for label in judged)
    return true_positive, len(judged), true_positive / len(judged) if judged else None


def summarize_retention(path: Path) -> Counter[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = [row.get("human_label", "").strip() for row in rows]
    invalid = sorted(set(label for label in labels if label and label not in RETENTION_CATEGORIES))
    if invalid:
        raise ValueError(f"Unsupported human_label values: {', '.join(invalid)}")
    return Counter(label or "pending / blank" for label in labels)


def generate(outputs_dir: Path, output_dir: Path, seed: int) -> tuple[int, int, int, int, int]:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit directory: {output_dir}")
    records = read_records(outputs_dir)
    retention, unmapped = retention_candidates(records)
    sampled_retention = stratified_sample(retention, 40, seed)
    unsupported = unsupported_candidates(records)
    rng = random.Random(seed)
    sampled_unsupported = rng.sample(unsupported, min(60, len(unsupported)))
    candidates = regimen_candidates(records)

    output_dir.mkdir(parents=True)
    write_csv(output_dir / "retention_audit.csv", sampled_retention,
              ["note_id", "persona", "label", "entity", "source_context",
               "first_attempt_missing_entity", "final_output", "human_label"])
    write_csv(output_dir / "unsupported_numbers_sample.csv", sampled_unsupported,
              ["note_id", "persona", "flagged_item", "source_context", "output_context", "human_label"])
    write_csv(output_dir / "regimen_candidate_patterns.csv", candidates,
              ["candidate_label", "candidate_form", "count", "note_ids", "interpretation"])
    counts = category_counts(sampled_retention, RETENTION_CATEGORIES, "retention")
    counts += category_counts(sampled_unsupported, UNSUPPORTED_CATEGORIES, "unsupported_numbers")
    for (persona, label), n in sorted(Counter((r["persona"], r["label"]) for r in sampled_retention).items()):
        counts.append({"kind": "retention_stratum", "category": f"{persona}:{label}", "count": n})
    write_csv(output_dir / "audit_category_counts.csv", counts, ["kind", "category", "count"])
    (output_dir / "README.md").write_text(
        "# MTSamples audits\n\n"
        f"Evidence samples from `{outputs_dir}`; seed `{seed}`. Human labels are blank. "
        "No model judge or automatic category assignment was used. These audit tables are "
        "unverified by a human.\n\n"
        "`retention_audit.csv` samples first-attempt missing entities, stratified by persona and label. "
        "The source output files store missing entity lists but not first-attempt prose, so `final_output` "
        "is the saved final persona output and must not be mistaken for first-attempt text. Label with "
        "true omission / matcher failure / extraction error / unclear.\n\n"
        "`unsupported_numbers_sample.csv` labels: true fabrication / equivalent / format mismatch / other. "
        "Run `python scripts/audit_mtsamples.py --score-unsupported "
        "results/mtsamples/audits/unsupported_numbers_sample.csv` after filling labels; precision is "
        "true fabrication divided by nonblank human-labeled rows.\n\n"
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
    args = parser.parse_args()
    try:
        if args.score_unsupported:
            tp, n, precision = score_unsupported(args.score_unsupported)
            print(f"Human-labeled unsupported-number precision: {tp}/{n} = "
                  f"{precision:.3f}" if precision is not None else "Human-labeled precision: unavailable (no labels).")
            return 0
        if args.summarize_retention:
            counts = summarize_retention(args.summarize_retention)
            print("; ".join(f"{label}: {counts[label]}" for label in (*RETENTION_CATEGORIES, "pending / blank")))
            return 0
        n_records, n_retention, n_unsupported, n_patterns, unmapped = generate(
            args.outputs_dir, args.output_dir, args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Audited {n_records} notes; retention sample {n_retention}; unsupported-number sample {n_unsupported}; "
          f"unmatched candidate forms {n_patterns}; unmapped misses {unmapped}; seed {args.seed}.")
    print("Human category counts: blank/pending for all sampled rows; no automatic judgments assigned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
