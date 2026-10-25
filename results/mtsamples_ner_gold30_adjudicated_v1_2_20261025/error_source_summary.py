"""Describe evaluator errors for one results dir against its gold dir (facts only, no causes). Run from the repo root.
Usage: error_source_summary.py <results_dir> <gold_dir> <notes_dir>
"""
import collections, csv, json, sys

res, gold_dir, notes = sys.argv[1:4]
rows = list(csv.DictReader(open(f"{res}/mtsamples_ner_errors.csv")))
print(len(rows), dict(collections.Counter(r["error_type"] for r in rows)))
src, gold = {}, {}
for r in rows:
    n = r["note_id"]
    if n not in src:
        src[n] = open(f"{notes}/{n}.txt", encoding="utf-8").read()
        gold[n] = json.load(open(f"{gold_dir}/{n}.json"))["entities"]


def txt(r, side):
    s, e = int(float(r[side + "_start"])), int(float(r[side + "_end"]))
    return src[r["note_id"]][s:e]


for lab in ["CONDITION", "MEDICATION", "DURATION", "SYMPTOM", "DOSAGE", "FREQUENCY"]:
    fn = [r for r in rows if r["error_type"] == "FN" and r["label"] == lab]
    fp = [r for r in rows if r["error_type"] == "FP" and r["label"] == lab]
    pairs = 0
    for p in fp:
        for g in fn:
            if p["note_id"] == g["note_id"] and int(float(p["predicted_start"])) < int(float(g["gold_end"])) and int(float(g["gold_start"])) < int(float(p["predicted_end"])):
                pairs += 1
                break
    fp_any, fp_diff = 0, collections.Counter()
    for p in fp:
        ps, pe = int(float(p["predicted_start"])), int(float(p["predicted_end"]))
        ov = [g for g in gold[p["note_id"]] if g["start"] < pe and ps < g["end"]]
        if ov:
            fp_any += 1
            fp_diff[tuple(sorted({g["label"] for g in ov}))] += 1
    print(f"\n{lab}: FN={len(fn)} FP={len(fp)} | FP overlapping a same-label FN gold span: {pairs} | FP overlapping any gold span: {fp_any} {dict(fp_diff)}")
    print("  top FN surface forms:", collections.Counter(txt(r, "gold") for r in fn).most_common(6))
    print("  top FP surface forms:", collections.Counter(txt(r, "predicted") for r in fp).most_common(6))
