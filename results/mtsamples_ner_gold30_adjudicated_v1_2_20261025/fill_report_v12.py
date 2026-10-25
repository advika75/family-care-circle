"""Render comparison_report.md for the v1.2 results dir from the template and compare3.json. Run from the repo root."""
import collections, glob, json
from pathlib import Path

SP = Path("/private/tmp/claude-501/-Users-advikamishra-Projects-family-care-circle/951d6a64-58d8-45ab-85fc-bad7436a5a5e/scratchpad")
R = Path("results/mtsamples_ner_gold30_adjudicated_v1_2_20261025")
d = json.loads((SP / "compare3.json").read_text())
L = ["CONDITION", "DOSAGE", "DURATION", "FREQUENCY", "MEDICATION", "SYMPTOM", "MICRO"]
V = [("baseline", "Original"), ("v1_1", "v1.1"), ("v1_2", "v1.2")]


def gold_counts():
    out = {}
    for key, g in (("baseline", "gold_adjudication_v1_20261024"), ("v1_1", "gold_adjudicated_v1_1_20261024"), ("v1_2", "gold_adjudicated_v1_2_20261025")):
        c = collections.Counter()
        for p in glob.glob(f"data/public/mtsamples/{g}/mtsamples_*.json"):
            for e in json.loads(Path(p).read_text())["entities"]:
                c[e["label"]] += 1
        out[key] = c
    return out


G = gold_counts()
gt = ["| Label | Original | v1.1 | v1.2 |", "|---|---:|---:|---:|"]
for l in L[:-1]:
    gt.append(f"| {l} | {G['baseline'][l]} | {G['v1_1'][l]} | {G['v1_2'][l]} |")
gt.append(f"| **Total** | **{sum(G['baseline'].values())}** | **{sum(G['v1_1'].values())}** | **{sum(G['v1_2'].values())}** |")


def counts(m):
    o = ["| Label | Original TP/FP/FN | v1.1 TP/FP/FN | v1.2 TP/FP/FN |", "|---|---:|---:|---:|"]
    for l in L:
        def c(v):
            return "{}/{}/{}".format(*(d[v][m][l][k] for k in ("tp", "fp", "fn")))
        o.append(f"| {'**MICRO**' if l == 'MICRO' else l} | {c('baseline')} | {c('v1_1')} | {c('v1_2')} |")
    return "\n".join(o)


def prf(m):
    o = ["| Label | Orig P | Orig R | Orig F1 | v1.1 P | v1.1 R | v1.1 F1 | v1.2 P | v1.2 R | v1.2 F1 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for l in L:
        cells = []
        for v, _ in V:
            x = d[v][m][l]
            cells += [f"{x['precision'] * 100:.1f}%", f"{x['recall'] * 100:.1f}%", f"{x['f1'] * 100:.1f}%"]
        o.append(f"| {'**MICRO**' if l == 'MICRO' else l} | " + " | ".join(cells) + " |")
    return "\n".join(o)


def x(l, k, m="exact"):
    return d["v1_2"][m][l][k]


g2 = G["v1_2"]
ERR = (
    f"- **CONDITION:** {x('CONDITION', 'fn')} exact false negatives out of {g2['CONDITION']} gold spans (TP {x('CONDITION', 'tp')}, FP {x('CONDITION', 'fp')}), the largest share of the {x('MICRO', 'fn')} total. "
    f"Under relaxed matching FN falls only to {x('CONDITION', 'fn', 'relaxed')}. The most frequent missed surface forms are `anemia` ×4, `MGUS` ×3, `dehydration` ×3 and `impending compartment syndrome of the right upper extremity` ×3. "
    f"Of the {x('CONDITION', 'fp')} false positives, 10 overlap a CONDITION gold span with different boundaries; the most frequent are `pneumonia`, `heart failure` and `hypothyroidism`, each ×2.\n"
    f"- **MEDICATION:** {x('MEDICATION', 'fn')} exact FN out of {g2['MEDICATION']} gold spans (TP {x('MEDICATION', 'tp')}, FP {x('MEDICATION', 'fp')}); relaxed FN is {x('MEDICATION', 'fn', 'relaxed')}. "
    f"The most frequent missed forms are `Marcaine` ×4, and `Lamictal`, `Levaquin` and `Synthroid` ×3 each. Eight of the {x('MEDICATION', 'fp')} false positives are `insulin`; the others are `dexamethasone` and `Penicillin`.\n"
    f"- **DURATION:** **0 exact matches** (FP {x('DURATION', 'fp')}, FN {x('DURATION', 'fn')} of {g2['DURATION']} gold spans). The four false positives are `3 days` ×2 and `15-day` ×2; "
    f"two of them overlap a DURATION gold span with different boundaries, which is why relaxed TP is {x('DURATION', 'tp', 'relaxed')}. Missed forms include `three additional days` ×2, `x3 days` ×2 and `one week` ×2.\n"
    f"- **SYMPTOM:** the most false positives of any label: {x('SYMPTOM', 'fp')} (TP {x('SYMPTOM', 'tp')}, FN {x('SYMPTOM', 'fn')}). The most frequent predicted forms are `pain` ×18 and `bleeding` ×15, then `fever`, `vomiting` and `swelling` ×3 each. "
    f"Only 8 of the {x('SYMPTOM', 'fp')} overlap any gold span (6 a SYMPTOM span, 2 a CONDITION span), so 51 overlap no gold span. Relaxed FP is {x('SYMPTOM', 'fp', 'relaxed')}.\n"
    f"- **DOSAGE and FREQUENCY:** {x('DOSAGE', 'fn')} and {x('FREQUENCY', 'fn')} exact FN. Frequent misses are `1%` ×6 and `1 cc` ×4 (DOSAGE), and `b.i.d.` ×5 and `q.d.` ×4 (FREQUENCY). "
    f"No adjudication decision so far touched either label, so their counts are identical across all three versions."
)
t = (SP / "report_v12_template.md").read_text()
for k, v in {"{GOLDTBL}": "\n".join(gt), "{EX_COUNTS}": counts("exact"), "{EX_PRF}": prf("exact"), "{RX_COUNTS}": counts("relaxed"), "{RX_PRF}": prf("relaxed"), "{ERRSEC}": ERR}.items():
    assert k in t, k
    t = t.replace(k, v)
for ph in ("{GOLDTBL}", "{EX_COUNTS}", "{EX_PRF}", "{RX_COUNTS}", "{RX_PRF}", "{ERRSEC}"):
    assert ph not in t
(R / "comparison_report.md").write_text(t, encoding="utf-8")
print("report written", len(t), "chars")
