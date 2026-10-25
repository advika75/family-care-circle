"""Score the same rule-based extractor against two gold directories (exact and relaxed) using src.evaluator.ner_scores.

Run from project root: python compare_gold_versions.py <baseline_gold_dir> <adjudicated_gold_dir> <notes_dir> <out_json>
Same code path as src/public_ner_evaluation.py (extract_rule_based + ner_scores); relaxed mode is src.evaluator's existing 'relaxed' (overlap) matching.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.ner import extract_rule_based
from src.evaluator import ner_scores

def load(gold_dir, notes_dir):
    docs = []
    man = json.loads((Path(gold_dir) / "annotation_manifest.json").read_text())
    for e in man["annotations"]:
        if e.get("status") != "complete":
            continue
        a = json.loads((Path(gold_dir) / f"{e['id']}.json").read_text())
        text = (Path(notes_dir) / e["source_file"]).read_text(encoding="utf-8")
        gold = [{k: x[k] for k in ("text", "label", "start", "end")} for x in a["entities"]]
        docs.append((extract_rule_based(text), gold))
    return docs

out = {}
for name, gd in (("baseline", sys.argv[1]), ("adjudicated", sys.argv[2])):
    docs = load(gd, sys.argv[3])
    out[name] = {mode: ner_scores(docs, mode) for mode in ("exact", "relaxed")}
    out[name]["n_docs"] = len(docs)
Path(sys.argv[4]).write_text(json.dumps(out, indent=2))
