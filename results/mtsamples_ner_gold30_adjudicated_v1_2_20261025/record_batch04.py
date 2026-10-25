"""Record Batch 04 decisions in the worksheet and the adjudication log. Run from the repo root."""
import csv, re
from pathlib import Path

D = "2026-10-25"
REV = "Advika Mishra"
R = Path("results/mtsamples_ner_gold30_20261024_diagnostic")
AI = "mtsamples_Acute_Inferior_Myocardial_Infarction"
MM = "mtsamples_Multiple_Medical_Problems_-_Discharge_Summary_064"
PEC = "mtsamples_Pectoralis_Tendon_Repair"
TENO = "mtsamples_Tenosynovectomy_Cortisone_Injection"

# (worksheet candidate number) -> (decision, confirmed action, one-line policy rationale)
WS = {
    1: ("ADOPT", "Relabel `Dyspnea` [85,92) from CONDITION to SYMPTOM; keep the same span.",
        "Policy v1.0 §3 CONDITION: a symptom is not labelled CONDITION merely because it appears under a diagnosis heading."),
    2: ("DISCUSS", "none; remains DISCUSS. No gold change.",
        "The note does not settle whether `Edema` is a stated diagnosis, a symptom or an objective finding (Policy v1.0 §3 CONDITION and SYMPTOM; §4 item 4)."),
    3: ("ADOPT", "Retain `approximately 10 days` [5294,5315) as DURATION. No gold change.",
        "Policy v1.0 §3 DURATION includes how long a care instruction continues; the sentence ties the interval to remaining in the shoulder immobilizer."),
    4: ("ADOPT", "Remove `over the past 1 hour` [948,968) from DURATION; assign no other label.",
        "Policy v1.0 §3 DURATION covers how long treatment continues; this span is a retrospective window of nitroglycerin use."),
    5: ("ADOPT", "Remove `for 26 years` [488,500) from DURATION; assign no other label. `insulin` [480,487) stays MEDICATION.",
        "Policy v1.0 §3 DURATION covers how long treatment continues; this span is the historical length of insulin use."),
    6: ("ADOPT", "Remove `24-48 hours` [3495,3506) from DURATION; assign no other label.",
        "Policy v1.0 §3 DURATION covers how long a care instruction continues; this span states when the exercises begin."),
    7: ("ADOPT", "Shrink to `Humulin N` [1708,1717), MEDICATION; `insulin` stays unlabelled.",
        "Policy v1.0 §3 MEDICATION: label the product name alone when the following generic term is only a descriptor; §2.1 excludes external punctuation."),
    8: ("ADOPT", "Remove `prophylactic antibiotics` [2648,2672) from MEDICATION; assign no other label. The unannotated `antibiotics` at [2785,2796) stays unannotated.",
        "Policy v1.0 §3 MEDICATION excludes broad therapeutic classes used as class references; the span names no specific drug."),
    9: ("ADOPT", "Trim to `Nitroglycerin` [1763,1776), MEDICATION.",
        "Policy v1.0 §2.1 excludes leading and trailing whitespace."),
    10: ("ADOPT", "Relabel `chest pain` [141,151) from CONDITION to SYMPTOM; keep the same span.",
         "Policy v1.0 §3 SYMPTOM and §4 item 3: chest pain is SYMPTOM, including as a chief complaint, and quotation alone does not disqualify a symptom."),
}

# ---------------------------------------------------------------- worksheet
p = R / "adjudication_batch_04_open_items.md"
t = p.read_text(encoding="utf-8")
parts = re.split(r"(?=^## )", t, flags=re.M)
out = []
for s in parts:
    m = re.match(r"## Candidate (\d+)", s)
    if m:
        n = int(m.group(1))
        d, act, rat = WS[n]
        box = {"ADOPT": "[x] ADOPT  [ ] REJECT  [ ] DISCUSS", "DISCUSS": "[ ] ADOPT  [ ] REJECT  [x] DISCUSS"}[d]
        for old, new in (
            ("- **Recorded human decision:** [ ] ADOPT  [ ] REJECT  [ ] DISCUSS", "- **Recorded human decision:** " + box),
            ("- **Confirmed action:**\n", "- **Confirmed action:** " + act + "\n"),
            ("- **Recorded rationale:**\n", "- **Recorded rationale:** " + rat + "\n"),
            ("- **Reviewer:**  **Decision date:**", f"- **Reviewer:** {REV}  **Decision date:** {D}"),
        ):
            assert s.count(old) == 1, (n, old)
            s = s.replace(old, new)
    out.append(s)
t = "".join(out)
old_status = t[t.index("**Status: awaiting human review.**"):t.index("Decision options:")]
new_status = ("**Human decision record.** The decisions below were confirmed by Advika Mishra on 2026-10-25. ADOPT records the review decision only; it does not itself change the protected snapshot or any existing gold directory. "
              "Candidate 2 (Edema) remains DISCUSS. Candidate 3 (D04) is an ADOPT that retains the span, so it changes no gold.\n\n")
t = t.replace(old_status, new_status)
i = t.index("## Batch record")
t = t[:i] + """## Batch record

Decisions recorded by Advika Mishra on 2026-10-25.

- **ADOPT, changes gold (8):** Candidate 1 (SC02, relabel to SYMPTOM), 4 (D05, remove), 5 (D10, remove), 6 (D15, remove), 7 (M01, shrink to `Humulin N`), 8 (M02, remove), 9 (M03, trim leading space), 10 (SC03, relabel to SYMPTOM).
- **ADOPT, no gold change (1):** Candidate 3 (D04, retain as DURATION).
- **DISCUSS, unresolved (1):** Candidate 2 (SC04, `Edema`).
- **Additional approved additions (not worksheet candidates):** `chest pain` at [275,285) and `chest pain` at [1800,1810) in `mtsamples_Acute_Inferior_Myocardial_Infarction`, both to be added as SYMPTOM (Policy v1.0 §2.1: annotate each explicit occurrence; §3 SYMPTOM). They are recorded as two new rows in `gold_adjudication_log.csv`.

The protected snapshot, `gold_adjudicated_v1_1_20261024`, the approved policy and all existing results remain unchanged. Gold version reference for these log entries: `gold_adjudicated_v1_1_20261024`.
"""
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------- log
L = R / "gold_adjudication_log.csv"
rows = list(csv.reader(open(L, newline="", encoding="utf-8")))
h = rows[0]
ix = {k: i for i, k in enumerate(h)}
body = rows[1:]


def find(note, start):
    m = [r for r in body if r[ix["Note ID"]] == note and r[ix["Original start offset"]] == str(start)]
    assert len(m) == 1, (note, start, len(m))
    return m[0]


def setp(r, text, s, e, label):
    r[ix["Proposed span text"]], r[ix["Proposed start offset"]], r[ix["Proposed end offset"]], r[ix["Proposed label"]] = text, str(s) if s != "" else "", str(e) if e != "" else "", label


def finish(r, dec, action, rat, supersede=False):
    prefix = r[ix["Rationale"]]
    sup = " Supersedes the 2026-10-24 DISCUSS record." if supersede else ""
    r[ix["Rationale"]] = (prefix + " " if prefix else "") + f"Batch 04 ({D}):{sup} Human decision: {dec}. Human-confirmed action: {action} {rat}"
    r[ix["Reviewer"]], r[ix["Decision"]], r[ix["Decision date"]] = REV, dec, D


changed = []
# existing rows
spec = [
    (MM, 85, "Dyspnea", 85, 92, "SYMPTOM", WS[1], True, "Policy v1.0 §3 CONDITION and §3 SYMPTOM; §4 items 4–5"),
    (MM, 98, None, None, None, None, WS[2], False, None),
    (PEC, 5294, "approximately 10 days", 5294, 5315, "DURATION", WS[3], True, None),
    (AI, 948, None, None, None, None, WS[4], True, None),
    (MM, 488, None, None, None, None, WS[5], True, None),
    (TENO, 3495, None, None, None, None, WS[6], True, None),
    (AI, 1708, "Humulin N", 1708, 1717, "MEDICATION", WS[7], True, None),
    (PEC, 2648, None, None, None, None, WS[8], True, None),
]
for note, start, ptext, ps, pe, pl, (dec, act, rat), sup, rule in spec:
    r = find(note, start)
    assert r[ix["Decision"]] == "DISCUSS"
    if ptext is not None:
        setp(r, ptext, ps, pe, pl)
    finish(r, dec, act, rat, supersede=(sup and dec == "ADOPT") or dec == "DISCUSS" and False)
    if dec == "DISCUSS":
        r[ix["Rationale"]] = r[ix["Rationale"]].replace("Batch 04 (2026-10-25): Human decision: DISCUSS. Human-confirmed action: none; remains DISCUSS. No gold change.",
                                                        "Batch 04 (2026-10-25): Human decision: DISCUSS. Remains unresolved; no gold change.")
    if rule:
        r[ix["Policy rule reference"]] = rule
    changed.append(rows.index(r) + 1)


def newrow(note, ofile, otext, os_, oe, ol, ptext, ps, pe, pl, rule, rat, ctx):
    r = [""] * len(h)
    r[ix["Note ID"]], r[ix["Source filename"]] = note, ofile
    r[ix["Original span text"]], r[ix["Original start offset"]], r[ix["Original end offset"]], r[ix["Original label"]] = otext, os_, oe, ol
    r[ix["Proposed span text"]], r[ix["Proposed start offset"]], r[ix["Proposed end offset"]], r[ix["Proposed label"]] = ptext, ps, pe, pl
    r[ix["Policy rule reference"]] = rule
    r[ix["Rationale"]] = ctx
    r[ix["Reviewer"]], r[ix["Decision"]], r[ix["Decision date"]] = REV, "ADOPT", D
    r[ix["Review status"]] = "pending_human_review"
    r[ix["Gold version"]] = "gold_adjudicated_v1_1_20261024"
    return r


f = AI + ".txt"
new = [
    newrow(AI, f, " Nitroglycerin", "1762", "1776", "MEDICATION", "Nitroglycerin", "1763", "1776", "MEDICATION",
           "Policy v1.0 §2.1",
           f"Source context: “Humulin N. insulin 50 units in a.m.  HCTZ 50 mg QDay.  Nitroglycerin 1/150 sublingually PRN chest pain.” Batch 04 ({D}): Human decision: ADOPT. Human-confirmed action: {WS[9][1]} {WS[9][2]}", None),
    newrow(AI, f, "chest pain", "141", "151", "CONDITION", "chest pain", "141", "151", "SYMPTOM",
           "Policy v1.0 §3 SYMPTOM; §4 item 3",
           f"Source context: “presents with a chief complaint of \"chest pain\".” Batch 04 ({D}): Human decision: ADOPT. Human-confirmed action: {WS[10][1]} {WS[10][2]}", None),
    newrow(AI, f, "", "", "", "", "chest pain", "275", "285", "SYMPTOM",
           "Policy v1.0 §2.1; §3 SYMPTOM",
           f"Source context: “The patient presents today stating that his chest pain started yesterday evening”. Batch 04 ({D}): Human decision: ADOPT. Human-confirmed action: add `chest pain` [275,285) as SYMPTOM; the mention has no gold span in gold_adjudicated_v1_1_20261024. Policy v1.0 §2.1 annotates each explicit symptom occurrence and §3 SYMPTOM classifies chest pain as SYMPTOM.", None),
    newrow(AI, f, "", "", "", "", "chest pain", "1800", "1810", "SYMPTOM",
           "Policy v1.0 §2.1; §3 SYMPTOM",
           f"Source context: “Nitroglycerin 1/150 sublingually PRN chest pain.” Batch 04 ({D}): Human decision: ADOPT. Human-confirmed action: add `chest pain` [1800,1810) as SYMPTOM; the mention has no gold span in gold_adjudicated_v1_1_20261024. Policy v1.0 §2.1 annotates each explicit symptom occurrence and §3 SYMPTOM names `PRN chest pain` as SYMPTOM.", None),
]
for r in new:
    rows.append(r)
    changed.append(len(rows))
with open(L, "w", newline="", encoding="utf-8") as fh:
    csv.writer(fh, lineterminator="\n").writerows(rows)
print("log rows changed/added (file line numbers):", sorted(changed))
