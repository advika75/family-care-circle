"""Build gold_adjudicated_v1_2_20261025 from gold_adjudicated_v1_1_20261024 by applying ONLY the Batch 04 ADOPT rows
(log rows dated 2026-10-25). Run from the repo root. Refuses to run if the output directory already exists.
Usage: build_gold_v1_2.py <manifest_csv_out>
"""
import csv, hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path.cwd()
SNAP = ROOT / "data/public/mtsamples/gold_adjudication_v1_20261024"
V11 = ROOT / "data/public/mtsamples/gold_adjudicated_v1_1_20261024"
OUT = ROOT / "data/public/mtsamples/gold_adjudicated_v1_2_20261025"
NOTES = ROOT / "data/public/mtsamples/notes"
LOG = ROOT / "results/mtsamples_ner_gold30_20261024_diagnostic/gold_adjudication_log.csv"
LABELS = {"MEDICATION", "DOSAGE", "FREQUENCY", "DURATION", "CONDITION", "SYMPTOM"}
DATE = "2026-10-25"

CAND = {  # (note, original start or proposed start for additions) -> candidate id
    ("mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064", 85): "Batch04-C1 (queue SC02)",
    ("mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064", 98): "Batch04-C2 (queue SC04)",
    ("mtsamples_Pectoralis_Tendon_Repair", 5294): "Batch04-C3 (queue D04)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 948): "Batch04-C4 (queue D05)",
    ("mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064", 488): "Batch04-C5 (queue D10)",
    ("mtsamples_Tenosynovectomy_Cortisone_Injection", 3495): "Batch04-C6 (queue D15)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 1708): "Batch04-C7 (queue M01)",
    ("mtsamples_Pectoralis_Tendon_Repair", 2648): "Batch04-C8 (queue M02)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 1762): "Batch04-C9 (queue M03)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 141): "Batch04-C10 (queue SC03)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 275): "Batch04-addition (explicit approval)",
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 1800): "Batch04-addition (explicit approval)",
}


def sha_tree(d):
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def main():
    manifest_out = Path(sys.argv[1])
    assert not OUT.exists(), f"refusing: {OUT} exists"
    before_snap, before_v11 = sha_tree(SNAP), sha_tree(V11)
    shutil.copytree(V11, OUT)

    rows = list(csv.DictReader(open(LOG, newline="", encoding="utf-8")))
    b4 = [(i + 2, r) for i, r in enumerate(rows) if r["Decision date"] == DATE]
    assert len(b4) == 12, len(b4)  # 8 existing + 4 new rows
    adopt = [(n, r) for n, r in b4 if r["Decision"] == "ADOPT"]
    discuss = [(n, r) for n, r in b4 if r["Decision"] == "DISCUSS"]
    assert len(adopt) == 11 and len(discuss) == 1 and discuss[0][1]["Original span text"] == "Edema", (len(adopt), len(discuss))

    by_note, counts = {}, dict(relabel=0, removed=0, shrink=0, trim=0, added=0, retained=0)
    for n, r in adopt:
        by_note.setdefault(r["Note ID"], []).append((n, r))
    changes = []
    total_before = total_after = 0
    for note, items in by_note.items():
        path = OUT / f"{note}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        src = (NOTES / data["source_file"]).read_text(encoding="utf-8")
        ents = data["entities"]
        touched = []
        for n, r in items:
            o_text, o_s, o_e, o_l = r["Original span text"], r["Original start offset"], r["Original end offset"], r["Original label"]
            p_text, p_s, p_e, p_l = r["Proposed span text"], r["Proposed start offset"], r["Proposed end offset"], r["Proposed label"]
            key = int(o_s) if o_s != "" else int(p_s)
            cid = CAND[(note, key)]
            srcdesc = f"adjudication_batch_04_open_items.md; gold_adjudication_log.csv row {n}"
            if o_s == "":  # addition
                ne = {"text": p_text, "label": p_l, "start": int(p_s), "end": int(p_e), "annotation_source": "manual"}
                assert not [e for e in ents if e["start"] < ne["end"] and ne["start"] < e["end"]], ("addition overlaps", note, ne)
                ents.append(ne); touched.append(ne); counts["added"] += 1
                changes.append((note, "added", "", "", "", "", p_text, p_s, p_e, p_l, cid, srcdesc))
                continue
            idx = [i for i, e in enumerate(ents) if e["start"] == int(o_s) and e["end"] == int(o_e)]
            assert len(idx) == 1, (note, o_s)
            old = ents[idx[0]]
            assert (old["text"], old["label"]) == (o_text, o_l), (note, old)
            if p_text == "":
                ents.pop(idx[0]); counts["removed"] += 1
                changes.append((note, "removed", o_text, o_s, o_e, o_l, "", "", "", "", cid, srcdesc))
                continue
            if (p_text, p_s, p_e, p_l) == (o_text, o_s, o_e, o_l):
                counts["retained"] += 1
                changes.append((note, "retained_no_change", o_text, o_s, o_e, o_l, p_text, p_s, p_e, p_l, cid, srcdesc))
                continue
            ne = dict(old); ne.update(text=p_text, label=p_l, start=int(p_s), end=int(p_e))
            ents[idx[0]] = ne; touched.append(ne)
            if (p_s, p_e) == (o_s, o_e):
                counts["relabel"] += 1; kind = "relabeled"
            elif p_text == o_text.strip():
                counts["trim"] += 1; kind = "trimmed"
            else:
                counts["shrink"] += 1; kind = "shrunk"
            changes.append((note, kind, o_text, o_s, o_e, o_l, p_text, p_s, p_e, p_l, cid, srcdesc))
        for e in touched:
            assert src[e["start"]:e["end"]] == e["text"], (note, e)
            assert e["label"] in LABELS, e
            assert e["text"] == e["text"].strip() and e["text"], (note, e)
        s = sorted(ents, key=lambda e: (e["start"], e["end"]))
        for a, b in zip(s, s[1:]):
            assert b["start"] >= a["end"], ("overlap", note, a, b)
        for e in s:
            assert src[e["start"]:e["end"]] == e["text"] and e["label"] in LABELS
        data["entities"] = s
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for p in sorted(V11.glob("mtsamples_*.json")):
        total_before += len(json.loads(p.read_text(encoding="utf-8"))["entities"])
    for p in sorted(OUT.glob("mtsamples_*.json")):
        total_after += len(json.loads(p.read_text(encoding="utf-8"))["entities"])

    expected = dict(relabel=2, removed=4, shrink=1, trim=1, added=2, retained=1)
    assert counts == expected, ("COUNTS DIFFER FROM EXPECTATION", counts, expected)
    assert (total_before, total_after) == (520, 518), (total_before, total_after)

    # specific guard checks
    mm = json.loads((OUT / "mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064.json").read_text(encoding="utf-8"))["entities"]
    assert any((e["text"], e["label"], e["start"], e["end"]) == ("insulin", "MEDICATION", 480, 487) for e in mm), "insulin [480,487) changed"
    ai = json.loads((OUT / "mtsamples_Acute_Inferior_Myocardial_Infarction.json").read_text(encoding="utf-8"))["entities"]
    assert not [e for e in ai if e["start"] < 1726 and 1717 < e["end"]], "something now covers the '. insulin' region"

    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["note_id", "change_type", "old_text", "old_start", "old_end", "old_label", "new_text", "new_start", "new_end", "new_label", "candidate_id", "decision_source"])
        w.writerows(changes)

    assert sha_tree(SNAP) == before_snap, "SNAPSHOT CHANGED"
    assert sha_tree(V11) == before_v11, "V1.1 CHANGED"
    print("snapshot sha256 identical:", True, len(before_snap), "files; v1.1 sha256 identical:", True, len(before_v11), "files")
    print("spans v1.1:", total_before, "-> v1.2:", total_after, counts)


main()
