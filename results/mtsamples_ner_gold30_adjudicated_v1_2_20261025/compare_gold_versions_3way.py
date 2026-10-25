"""Score the same rule-based extractor against several gold directories (exact and relaxed) using src.evaluator.ner_scores.

Run from the project root:
  python compare_gold_versions_3way.py <notes_dir> <out_json> <name1>=<gold_dir1> <name2>=<gold_dir2> ...
Same code path as src/public_ner_evaluation.py (extract_rule_based + ner_scores). 'relaxed' is src.evaluator's existing overlap matching.
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


notes_dir, out = sys.argv[1], sys.argv[2]
res = {}
for spec in sys.argv[3:]:
    name, gd = spec.split("=", 1)
    docs = load(gd, notes_dir)
    res[name] = {mode: ner_scores(docs, mode) for mode in ("exact", "relaxed")}
    res[name]["n_docs"] = len(docs)
Path(out).write_text(json.dumps(res, indent=2))
