"""Build gold_adjudicated_v1_1_20261024 from the protected snapshot by applying ONLY ADOPT rows in the adjudication log.

Run from the project root. Refuses to run if the output directory already exists.
"""
import csv, hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path.cwd()
SNAP = ROOT / "data/public/mtsamples/gold_adjudication_v1_20261024"
OUT = ROOT / "data/public/mtsamples/gold_adjudicated_v1_1_20261024"
NOTES = ROOT / "data/public/mtsamples/notes"
LOG = ROOT / "results/mtsamples_ner_gold30_20261024_diagnostic/gold_adjudication_log.csv"
RES = ROOT / "results/mtsamples_ner_gold30_adjudicated_v1_1_20261024"
LABELS = {"MEDICATION", "DOSAGE", "FREQUENCY", "DURATION", "CONDITION", "SYMPTOM"}

# (note id, original start) -> (candidate id, worksheet)
CAND = {
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 169): ("Batch01-C1 (queue C01)", "adjudication_batch_01_condition.md"),
    ("mtsamples_2-D_Echocardiogram_-_1", 84): ("Batch01-C2 (queue C02)", "adjudication_batch_01_condition.md"),
    ("mtsamples_2-D_Echocardiogram_-_1", 126): ("Batch01-C3 (queue C05)", "adjudication_batch_01_condition.md"),
    ("mtsamples_2-D_Echocardiogram_-_1", 206): ("Batch01-C4 (queue C06)", "adjudication_batch_01_condition.md"),
    ("mtsamples_2-D_Echocardiogram_-_1", 409): ("Batch01-C5 (queue C03)", "adjudication_batch_01_condition.md"),
    ("mtsamples_2-D_Echocardiogram_-_1", 454): ("Batch01-C6 (queue C09)", "adjudication_batch_01_condition.md"),
    ("mtsamples_Carotid_Ultrasound", 375): ("Batch01-C7 (queue C04)", "adjudication_batch_01_condition.md"),
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 19): ("Batch01-C8 (queue SC01)", "adjudication_batch_01_condition.md"),
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 1123): ("Batch02-C1 (queue D01)", "adjudication_batch_02_duration.md"),
    ("mtsamples_Tilt_Table_Test_-_1", 297): ("Batch02-C2 (queue D02)", "adjudication_batch_02_duration.md"),
    ("mtsamples_Tilt_Table_Test_-_1", 405): ("Batch02-C3 (queue D03)", "adjudication_batch_02_duration.md"),
    ("mtsamples_Leaking_Nephrostomy_Tube", 385): ("Batch02-C6 (queue D08)", "adjudication_batch_02_duration.md"),
    ("mtsamples_Low-Transverse_C-Section", 2866): ("Batch02-C7 (queue D09)", "adjudication_batch_02_duration.md"),
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 550): ("Batch03-C3 (queue PC01)", "adjudication_batch_03_boundaries.md"),
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 622): ("Batch03-C4 (queue PC02)", "adjudication_batch_03_boundaries.md"),
    ("mtsamples_Acute_Inferior_Myocardial_Infarction", 669): ("Batch03-C5 (queue PC03)", "adjudication_batch_03_boundaries.md"),
}


def sha_tree(d):
    h = {}
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            h[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return h


def main():
    before = sha_tree(SNAP)
    shutil.copytree(SNAP, OUT, dirs_exist_ok=True)  # idempotent: re-copies snapshot bytes over any partial earlier run

    rows = list(csv.DictReader(open(LOG, newline="", encoding="utf-8")))
    adopt = [r for r in rows if r["Decision"] == "ADOPT"]
    groups = {}
    for r in adopt:
        groups.setdefault((r["Note ID"], int(r["Original start offset"])), []).append(r)
    missing = set(groups) - set(CAND)
    extra = set(CAND) - set(groups)
    assert not missing and not extra, (missing, extra)

    changes, stats = [], dict(removed=0, modified=0, added=0, unchanged_adopt=0)
    by_note = {}
    for (note, start), rs in groups.items():
        by_note.setdefault(note, []).append((start, rs))

    total_before = total_after = 0
    for note, items in by_note.items():
        path = OUT / f"{note}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        src = (NOTES / data["source_file"]).read_text(encoding="utf-8")
        ents = data["entities"]
        total_before += len(ents)
        for start, rs in items:
            ostart, oend, olabel, otext = int(rs[0]["Original start offset"]), int(rs[0]["Original end offset"]), rs[0]["Original label"], rs[0]["Original span text"]
            idx = [i for i, e in enumerate(ents) if e["start"] == ostart and e["end"] == oend]
            assert len(idx) == 1, (note, start)
            i = idx[0]
            old = ents[i]
            assert (old["text"], old["label"]) == (otext, olabel), (note, start, old)
            cid, ws = CAND[(note, start)]
            props = [r for r in rs if r["Proposed span text"] != "" or r["Proposed label"] != ""]
            log_rows = ",".join(str(rows.index(r) + 2) for r in rs)
            source = f"{ws}; {LOG.name} row(s) {log_rows}"
            if not props:  # removal
                ents.pop(i)
                stats["removed"] += 1
                changes.append((note, "removed", otext, ostart, oend, olabel, "", "", "", "", cid, source))
                continue
            new_ents = []
            for r in props:
                ne = dict(old)
                ne.update(text=r["Proposed span text"], label=r["Proposed label"], start=int(r["Proposed start offset"]), end=int(r["Proposed end offset"]))
                new_ents.append(ne)
            if len(new_ents) == 1 and (new_ents[0]["text"], new_ents[0]["label"], new_ents[0]["start"], new_ents[0]["end"]) == (old["text"], old["label"], old["start"], old["end"]):
                stats["unchanged_adopt"] += 1
                changes.append((note, "retained_no_change", otext, ostart, oend, olabel, otext, ostart, oend, olabel, cid, source))
                continue
            for ne in new_ents:
                assert ne["text"] == ne["text"].strip() and ne["text"], (note, ne)
            ents[i:i + 1] = new_ents
            stats["modified"] += 1
            stats["added"] += len(new_ents) - 1
            for k, ne in enumerate(new_ents):
                kind = "modified" if k == 0 else "added"
                changes.append((note, kind, otext, ostart, oend, olabel, ne["text"], ne["start"], ne["end"], ne["label"], cid, source))
        # validation
        for e in ents:
            assert e["label"] in LABELS, e
            assert src[e["start"]:e["end"]] == e["text"], (note, e)
        s = sorted(ents, key=lambda e: (e["start"], e["end"]))
        for a, b in zip(s, s[1:]):
            assert b["start"] >= a["end"], (note, a, b)
        data["entities"] = s
        total_after += len(s)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # count spans in untouched notes
    for p in sorted(SNAP.glob("mtsamples_*.json")):
        if p.stem not in by_note:
            n = len(json.loads(p.read_text(encoding="utf-8"))["entities"])
            total_before += n
            total_after += n

    RES.mkdir(parents=True, exist_ok=True)
    with open(RES / "gold_change_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["note_id", "change_type", "old_text", "old_start", "old_end", "old_label", "new_text", "new_start", "new_end", "new_label", "candidate_id", "decision_source"])
        w.writerows(changes)

    after = sha_tree(SNAP)
    assert before == after, "SNAPSHOT CHANGED"
    print("snapshot sha256 identical:", before == after, len(before), "files")
    print("spans before", total_before, "after", total_after, stats)
    assert total_after == total_before - stats["removed"] + stats["added"]


main()
