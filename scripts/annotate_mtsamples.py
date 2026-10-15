"""Run the local MTSamples manual annotation tool.

The rule-based NER output is displayed as optional suggestions. Suggestions are never written to
gold JSON unless the annotator explicitly adds them to the draft and clicks Save.

Run from the project root:
    python scripts/annotate_mtsamples.py
Then open http://127.0.0.1:8765/ in a browser.
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.datasets import LABELS, load_annotation  # noqa: E402
from src.ner import EntityExtractor  # noqa: E402
from src.utils import resolve_path  # noqa: E402

LOGGER = logging.getLogger("mtsamples_annotation")
MANIFEST_NAME = "annotation_manifest.json"


class AnnotationStore:
    """Read and write the existing manifest and span-based annotation files."""

    def __init__(self, gold_dir: str | Path, notes_dir: str | Path, blind: bool = False) -> None:
        self.gold_dir = resolve_path(gold_dir)
        self.notes_dir = resolve_path(notes_dir)
        self.blind = blind
        self.manifest_path = self.gold_dir / MANIFEST_NAME
        self._lock = threading.Lock()
        self.extractor = EntityExtractor({"use_hf_model": False})
        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Missing annotation manifest: {self.manifest_path}")

    def _manifest(self) -> dict[str, Any]:
        with self.manifest_path.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
        if not isinstance(manifest.get("annotations"), list):
            raise ValueError("Annotation manifest must contain an annotations list")
        return manifest

    def _entry(self, note_id: str) -> dict[str, Any]:
        for entry in self._manifest()["annotations"]:
            if entry.get("id") == note_id:
                return entry
        raise KeyError(f"Unknown annotation note: {note_id}")

    def _paths(self, entry: dict[str, Any]) -> tuple[Path, Path]:
        source_file = Path(str(entry["source_file"]).replace("\\", "/")).name
        note_path = self.notes_dir / source_file
        annotation_path = self.gold_dir / f"{entry['id']}.json"
        return note_path, annotation_path

    def _read_annotation(self, entry: dict[str, Any]) -> dict[str, Any]:
        note_path, annotation_path = self._paths(entry)
        if not note_path.is_file():
            raise FileNotFoundError(f"Missing prepared note: {note_path}")
        return load_annotation(annotation_path, note_path)

    def state(self) -> dict[str, Any]:
        manifest = self._manifest()
        notes = []
        for entry in manifest["annotations"]:
            annotation = self._read_annotation(entry)
            notes.append({
                "id": entry["id"],
                "source_file": entry["source_file"],
                "status": entry.get("status", "pending"),
                "annotator": annotation.get("annotator", ""),
                "entity_count": len(annotation.get("entities", [])),
            })
        return {"seed": manifest.get("seed"), "count": len(notes), "notes": notes,
                "blind_mode": self.blind}

    def note(self, note_id: str) -> dict[str, Any]:
        entry = self._entry(note_id)
        note_path, _ = self._paths(entry)
        text = note_path.read_text(encoding="utf-8")
        annotation = self._read_annotation(entry)
        return {
            "id": entry["id"],
            "source_file": entry["source_file"],
            "text": text,
            "annotation": annotation,
            "suggestions": [] if self.blind else self.extractor.extract(text),
        }

    @staticmethod
    def _validate_entities(text: str, entities: Any) -> list[dict[str, Any]]:
        if not isinstance(entities, list):
            raise ValueError("entities must be a list")
        checked = []
        for entity in entities:
            if not isinstance(entity, dict) or entity.get("label") not in LABELS:
                raise ValueError(f"Entity label must be one of: {', '.join(sorted(LABELS))}")
            start, end, value = entity.get("start"), entity.get("end"), entity.get("text")
            if (not isinstance(start, int) or not isinstance(end, int) or not isinstance(value, str)
                    or start < 0 or end <= start or end > len(text) or text[start:end] != value):
                raise ValueError("Entity offsets/text do not match the selected note")
            item = {"text": value, "label": entity["label"], "start": start, "end": end}
            if "annotation_source" in entity:
                source = entity["annotation_source"]
                if source not in {"accepted_suggestion", "edited_suggestion", "manual"}:
                    raise ValueError("annotation_source must be accepted_suggestion, edited_suggestion, or manual")
                item["annotation_source"] = source
            if "suggestion_reference" in entity:
                item["suggestion_reference"] = entity["suggestion_reference"]
            checked.append(item)
        checked.sort(key=lambda item: (item["start"], item["end"], item["label"]))
        for previous, current in zip(checked, checked[1:]):
            if current["start"] < previous["end"]:
                raise ValueError("Overlapping entities are not supported")
        return checked

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        note_id = payload.get("id")
        if not isinstance(note_id, str):
            raise ValueError("id is required")
        entry = self._entry(note_id)
        note_path, annotation_path = self._paths(entry)
        text = note_path.read_text(encoding="utf-8")
        entities = self._validate_entities(text, payload.get("entities"))
        suggestions = self.extractor.extract(text)
        suggestion_keys = {(e["text"], e["label"], e["start"], e["end"]) for e in suggestions}
        for entity in entities:
            source = entity.get("annotation_source")
            exact = (entity["text"], entity["label"], entity["start"], entity["end"])
            if source == "accepted_suggestion" and (self.blind or exact not in suggestion_keys):
                raise ValueError("accepted_suggestion must exactly match a visible rule-based suggestion")
            if source == "edited_suggestion":
                reference = entity.get("suggestion_reference")
                if self.blind or not isinstance(reference, dict):
                    raise ValueError("edited_suggestion requires a visible suggestion reference")
                ref = (reference.get("text"), reference.get("label"),
                       reference.get("start"), reference.get("end"))
                if ref not in suggestion_keys or exact == ref:
                    raise ValueError("edited_suggestion must differ from a visible suggestion")
            if source != "edited_suggestion":
                entity.pop("suggestion_reference", None)
        annotator = payload.get("annotator", "")
        if not isinstance(annotator, str):
            raise ValueError("annotator must be a string")
        annotation = {"id": note_id, "source_file": entry["source_file"],
                      "annotator": annotator.strip(), "entities": entities}
        with self._lock:
            annotation_path.write_text(json.dumps(annotation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            manifest = self._manifest()
            for item in manifest["annotations"]:
                if item.get("id") == note_id:
                    item["status"] = "annotated"
                    break
            self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"ok": True, "id": note_id, "entity_count": len(entities)}


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Family Care Circle · MTSamples Gold Annotation</title>
<style>
:root { color-scheme: light; --ink:#172033; --muted:#5c667a; --line:#d8deea; --blue:#2558a8; --pale:#eef4ff; }
* { box-sizing:border-box; } body { margin:0; font:15px system-ui,-apple-system,sans-serif; color:var(--ink); background:#f7f9fc; }
header { padding:18px 28px; background:#172b4d; color:#fff; } header h1 { margin:0 0 5px; font-size:21px; }
header p { margin:0; color:#dce7f8; } main { display:grid; grid-template-columns:260px minmax(0,1fr) 320px; min-height:calc(100vh - 85px); gap:0; }
aside, section { background:#fff; border-right:1px solid var(--line); padding:18px; } section { min-width:0; } aside:last-child { border-right:0; border-left:1px solid var(--line); }
h2 { margin:0 0 12px; font-size:16px; } h3 { margin:20px 0 8px; font-size:14px; } .muted { color:var(--muted); font-size:13px; }
#note-list { max-height:calc(100vh - 170px); overflow:auto; } .note-row { width:100%; text-align:left; padding:9px 8px; border:0; border-bottom:1px solid #edf0f5; background:#fff; cursor:pointer; color:var(--ink); }
.note-row.current { background:var(--pale); color:var(--blue); } .note-row small { display:block; color:var(--muted); margin-top:3px; }
.toolbar { display:flex; flex-wrap:wrap; gap:7px; align-items:center; margin-bottom:12px; } button, input { font:inherit; } button { border:1px solid #b9c7dc; background:#fff; border-radius:5px; padding:7px 10px; cursor:pointer; } button.primary { background:var(--blue); color:#fff; border-color:var(--blue); } button:disabled { opacity:.45; cursor:default; }
#text { white-space:pre-wrap; word-break:break-word; line-height:1.65; border:1px solid var(--line); border-radius:6px; padding:18px; min-height:55vh; max-height:calc(100vh - 250px); overflow:auto; user-select:text; }
.entity { border-radius:3px; padding:1px 2px; } .entity-MEDICATION { background:#d9f4e5; } .entity-DOSAGE { background:#ffe6bd; } .entity-FREQUENCY { background:#dceaff; } .entity-DURATION { background:#f0ddff; } .entity-CONDITION { background:#ffd9df; } .entity-SYMPTOM { background:#fff5b8; }
.item { border:1px solid var(--line); border-radius:5px; padding:8px; margin:7px 0; } .item strong { font-size:12px; } .item code { font-size:12px; color:var(--muted); } .suggestion { background:#fbfcff; } .error { color:#a21d2b; margin:8px 0; }
label { display:block; font-size:13px; color:var(--muted); margin:7px 0 3px; } input { width:100%; padding:7px; border:1px solid #b9c7dc; border-radius:4px; }
@media (max-width:1000px) { main { grid-template-columns:210px minmax(0,1fr); } aside:last-child { grid-column:1/-1; border-left:0; border-top:1px solid var(--line); } }
</style></head><body>
<header><h1>Family Care Circle</h1><p>MTSamples Gold Annotation · <span id="progress">Loading…</span></p></header>
<main><aside><h2>Notes</h2><div class="muted">Select a note to annotate.</div><div id="note-list"></div></aside>
<section><div class="toolbar"><button id="prev">← Previous</button><button id="next">Next →</button><span class="muted" id="current"></span></div><div class="toolbar"><button data-label="MEDICATION">Medication</button><button data-label="DOSAGE">Dosage</button><button data-label="FREQUENCY">Frequency</button><button data-label="DURATION">Duration</button><button data-label="CONDITION">Condition</button><button data-label="SYMPTOM">Symptom</button><button class="primary" id="add-selection">Add selected span</button></div><p class="muted">Select text, choose a label, then add it to the draft. Gold entities are reviewed spans.</p><div id="text"></div></section>
<aside id="suggestion-panel"><h2>Draft annotations</h2><label for="annotator">Annotator</label><input id="annotator" placeholder="Your name"><div id="draft"></div><button class="primary" id="save">Save annotation</button><div id="message"></div><div id="suggestion-controls"><h3>Rule-based suggestions</h3><div class="muted">Review each suggestion before adding it.</div><div id="suggestions"></div></div></aside></main>
<script>
let state, currentIndex=0, currentNote=null, draft=[], selectedLabel=null;
const $=id=>document.getElementById(id);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function api(url, opts){return fetch(url,opts).then(r=>r.ok?r.json():r.json().then(x=>Promise.reject(new Error(x.error||'Request failed'))));}
function renderList(){ $('note-list').innerHTML=state.notes.map((n,i)=>`<button class="note-row ${i===currentIndex?'current':''}" data-i="${i}">${esc(n.source_file)}<small>${n.status} · ${n.entity_count} entities</small></button>`).join(''); document.querySelectorAll('.note-row').forEach(b=>b.onclick=()=>loadNote(Number(b.dataset.i))); }
function renderText(){let a=[...draft].sort((x,y)=>x.start-y.start), out='', pos=0; for(const e of a){if(e.start<pos)return; out+=esc(currentNote.text.slice(pos,e.start))+`<span class="entity entity-${e.label}" title="${e.label}">${esc(e.text)}</span>`;pos=e.end;} out+=esc(currentNote.text.slice(pos));$('text').innerHTML=out;}
function renderDraft(){ $('draft').innerHTML=draft.length?draft.map((e,i)=>`<div class="item"><strong>${e.label}</strong><br>${esc(e.text)} <code>[${e.start}, ${e.end})</code><br><small>${esc(e.annotation_source||'provenance unknown')}</small><br><button data-remove="${i}">Remove</button></div>`).join(''):'<p class="muted">No draft entities.</p>'; document.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{draft.splice(Number(b.dataset.remove),1);render();}); }
function renderSuggestions(){ $('suggestions').innerHTML=currentNote.suggestions.length?currentNote.suggestions.map((e,i)=>`<div class="item suggestion"><strong>${e.label}</strong><br>${esc(e.text)} <code>[${e.start}, ${e.end})</code><br><button data-suggest="${i}">Accept suggestion</button><button data-edit-suggest="${i}">Edit suggestion span</button></div>`).join(''):'<p class="muted">No rule-based suggestions.</p>'; document.querySelectorAll('[data-suggest]').forEach(b=>b.onclick=()=>{const e=currentNote.suggestions[Number(b.dataset.suggest)]; if(!draft.some(x=>x.start===e.start&&x.end===e.end&&x.label===e.label))draft.push({...e,annotation_source:'accepted_suggestion'});render();}); document.querySelectorAll('[data-edit-suggest]').forEach(b=>b.onclick=()=>{const e=currentNote.suggestions[Number(b.dataset.editSuggest)]; selectOffsets(e.start,e.end); selectedLabel=e.label; window.pendingSuggestion=e;}); }
function render(){renderList();renderText();renderDraft();renderSuggestions();$('suggestion-panel').classList.toggle('blind-mode',state.blind_mode);$('suggestion-controls').hidden=state.blind_mode; $('current').textContent=`${currentIndex+1} / ${state.count} · ${currentNote.source_file}`; $('progress').textContent=`Annotated: ${state.notes.filter(n=>n.status==='annotated').length} / ${state.count} · Current: ${currentIndex+1} / ${state.count}`;}
function loadNote(i){currentIndex=i;api('/api/note?id='+encodeURIComponent(state.notes[i].id)).then(n=>{currentNote=n;draft=n.annotation.entities.map(e=>({...e}));$('annotator').value=n.annotation.annotator||'';render();}).catch(showError);}
function showError(e){$('message').innerHTML=`<p class="error">${esc(e.message||e)}</p>`;}
function offsets(range,root){let w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),n,start=null,end=null,pos=0,node;while(node=w.nextNode()){if(node===range.startContainer)start=pos+range.startOffset;if(node===range.endContainer)end=pos+range.endOffset;pos+=node.nodeValue.length;}return {start,end};}
function selectOffsets(start,end){let w=document.createTreeWalker($('text'),NodeFilter.SHOW_TEXT),node,pos=0,a=null,b=null,ao=0,bo=0;while(node=w.nextNode()){let next=pos+node.nodeValue.length;if(a===null&&start<=next){a=node;ao=start-pos;}if(end<=next){b=node;bo=end-pos;break;}pos=next;}if(a&&b){let r=document.createRange();r.setStart(a,ao);r.setEnd(b,bo);let s=window.getSelection();s.removeAllRanges();s.addRange(r);}}
$('add-selection').onclick=()=>{if(!selectedLabel){showError(new Error('Choose an entity label first.'));return;}let s=window.getSelection();if(!s.rangeCount||s.isCollapsed){showError(new Error('Select text in the note first.'));return;}let r=s.getRangeAt(0),o=offsets(r,$('text')),text=currentNote.text.slice(o.start,o.end);if(!text.trim()){showError(new Error('Selected text is empty.'));return;}let entity={text,label:selectedLabel,start:o.start,end:o.end,annotation_source:'manual'};if(window.pendingSuggestion){const ref=window.pendingSuggestion;entity.annotation_source=(ref.text===text&&ref.label===selectedLabel&&ref.start===o.start&&ref.end===o.end)?'accepted_suggestion':'edited_suggestion';if(entity.annotation_source==='edited_suggestion')entity.suggestion_reference={text:ref.text,label:ref.label,start:ref.start,end:ref.end};window.pendingSuggestion=null;}draft.push(entity);selectedLabel=null;render();};
document.querySelectorAll('[data-label]').forEach(b=>b.onclick=()=>{selectedLabel=b.dataset.label;document.querySelectorAll('[data-label]').forEach(x=>x.style.outline='');b.style.outline='2px solid #2558a8';});
$('save').onclick=()=>api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:currentNote.id,annotator:$('annotator').value,entities:draft})}).then(()=>api('/api/state')).then(s=>{state=s;render();$('message').innerHTML='<p>Saved locally.</p>';}).catch(showError);
$('prev').onclick=()=>loadNote(Math.max(0,currentIndex-1));$('next').onclick=()=>loadNote(Math.min(state.count-1,currentIndex+1));
api('/api/state').then(s=>{state=s;document.body.classList.toggle('blind-mode',s.blind_mode);renderList();loadNote(0);}).catch(showError);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    store: AnnotationStore

    def _send(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                data = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif parsed.path == "/api/state":
                self._send(self.store.state())
            elif parsed.path == "/api/note":
                note_id = parse_qs(parsed.query).get("id", [""])[0]
                self._send(self.store.note(note_id))
            else:
                self._send({"error": "Not found"}, 404)
        except Exception as exc:  # noqa: BLE001 - return a useful local UI error
            LOGGER.exception("GET failed")
            self._send({"error": str(exc)}, 400)

    def do_POST(self) -> None:  # noqa: N802
        try:
            if urlparse(self.path).path != "/api/save":
                self._send({"error": "Not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            self._send(self.store.save(payload))
        except Exception as exc:  # noqa: BLE001 - return validation errors to the UI
            LOGGER.exception("POST failed")
            self._send({"error": str(exc)}, 400)

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/public/mtsamples/gold")
    parser.add_argument("--notes-dir", default="data/public/mtsamples/notes")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--blind", action="store_true", help="Hide rule-based suggestions while annotating")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    store = AnnotationStore(args.gold_dir, args.notes_dir, blind=args.blind)
    Handler.store = store
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    LOGGER.info("Open http://%s:%d/", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping annotation tool")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
