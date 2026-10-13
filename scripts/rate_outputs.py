"""Run the local blinded rating UI for a rating set built by scripts/build_rating_set.py.

Shows one blinded sample (persona output + source note) at a time; never loads or shows the answer
key, so condition labels stay hidden at the code level, not just in the UI. Each rater runs their own
instance (``--rater``) and their ratings are saved incrementally to their own JSON file, so two raters
can work independently and either can stop and resume.

Run from the project root:
    python scripts/rate_outputs.py --rater alice
Then open http://127.0.0.1:8766/ in a browser. A second rater runs the same command with a different
--rater (and --port, if running at the same time) and a different browser tab/window.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.human_eval import RATING_DIMENSIONS, rater_json_path, read_rater_ratings, write_rater_rating  # noqa: E402
from src.utils import resolve_path  # noqa: E402

LOGGER = logging.getLogger("rate_outputs")


class RatingStore:
    """Serves blinded items from a rating set and saves one rater's ratings. Never reads the answer key."""

    def __init__(self, set_path: str | Path, out_dir: str | Path, rater: str) -> None:
        self.set_path = Path(set_path)
        if not self.set_path.is_file():
            raise FileNotFoundError(f"Missing rating set: {self.set_path}. Run scripts/build_rating_set.py first.")
        self.items = json.loads(self.set_path.read_text(encoding="utf-8"))
        if not isinstance(self.items, list) or not self.items:
            raise ValueError(f"{self.set_path}: expected a non-empty list of items")
        self._by_id = {item["sample_id"]: item for item in self.items}
        self.rater = rater
        self.rating_path = rater_json_path(out_dir, rater)
        self._lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        ratings = read_rater_ratings(self.rating_path)
        return {
            "rater": self.rater,
            "count": len(self.items),
            "items": [{"sample_id": i["sample_id"], "persona": i["persona"], "rated": i["sample_id"] in ratings}
                      for i in self.items],
        }

    def item(self, sample_id: str) -> dict[str, Any]:
        if sample_id not in self._by_id:
            raise KeyError(f"Unknown sample id: {sample_id}")
        base = self._by_id[sample_id]
        rating = read_rater_ratings(self.rating_path).get(sample_id)
        return {**base, "rating": rating}

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        sample_id = payload.get("sample_id")
        if sample_id not in self._by_id:
            raise ValueError(f"Unknown sample id: {sample_id}")
        scores_in = payload.get("scores")
        if not isinstance(scores_in, dict):
            raise ValueError("scores must be an object")
        scores = {}
        for dim in RATING_DIMENSIONS:
            if dim not in scores_in or scores_in[dim] in (None, ""):
                continue
            try:
                value = int(scores_in[dim])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{dim} must be an integer 1-5") from exc
            if value not in (1, 2, 3, 4, 5):
                raise ValueError(f"{dim} must be between 1 and 5")
            scores[dim] = value
        flagged = bool(payload.get("missing_or_wrong_fact", False))
        note = str(payload.get("missing_or_wrong_fact_note", "")).strip()
        entry = {"scores": scores, "missing_or_wrong_fact": flagged, "missing_or_wrong_fact_note": note}
        with self._lock:
            write_rater_rating(self.rating_path, sample_id, entry)
        return {"ok": True, "sample_id": sample_id}


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Family Care Circle · Rating</title>
<style>
:root { color-scheme: light; --ink:#172033; --muted:#5c667a; --line:#d8deea; --blue:#2558a8; --pale:#eef4ff; }
* { box-sizing:border-box; } body { margin:0; font:15px system-ui,-apple-system,sans-serif; color:var(--ink); background:#f7f9fc; }
header { padding:18px 28px; background:#172b4d; color:#fff; } header h1 { margin:0 0 5px; font-size:21px; }
header p { margin:0; color:#dce7f8; } main { display:grid; grid-template-columns:230px minmax(0,1fr) 300px; min-height:calc(100vh - 85px); gap:0; }
aside, section { background:#fff; border-right:1px solid var(--line); padding:18px; } section { min-width:0; } aside:last-child { border-right:0; border-left:1px solid var(--line); }
h2 { margin:0 0 12px; font-size:16px; } h3 { margin:16px 0 8px; font-size:14px; } .muted { color:var(--muted); font-size:13px; }
#item-list { max-height:calc(100vh - 170px); overflow:auto; } .item-row { width:100%; text-align:left; padding:9px 8px; border:0; border-bottom:1px solid #edf0f5; background:#fff; cursor:pointer; color:var(--ink); }
.item-row.current { background:var(--pale); color:var(--blue); } .item-row.done::after { content:" ✓"; color:#1a8a4c; }
.toolbar { display:flex; flex-wrap:wrap; gap:7px; align-items:center; margin-bottom:12px; } button, input, textarea, select { font:inherit; } button { border:1px solid #b9c7dc; background:#fff; border-radius:5px; padding:7px 10px; cursor:pointer; } button.primary { background:var(--blue); color:#fff; border-color:var(--blue); }
#note, #text { white-space:pre-wrap; word-break:break-word; line-height:1.6; border:1px solid var(--line); border-radius:6px; padding:14px; max-height:32vh; overflow:auto; margin-bottom:12px; }
label { display:block; font-size:13px; color:var(--muted); margin:10px 0 3px; } select, textarea { width:100%; padding:7px; border:1px solid #b9c7dc; border-radius:4px; }
.scale { display:flex; gap:6px; } .scale label { display:flex; align-items:center; gap:4px; font-size:13px; margin:0; border:1px solid var(--line); border-radius:4px; padding:5px 8px; cursor:pointer; }
.scale input:checked + span, .scale label:has(input:checked) { color:var(--blue); font-weight:600; }
.flagwrap { display:flex; align-items:center; gap:7px; margin-top:14px; } .error { color:#a21d2b; margin:8px 0; } .ok { color:#1a8a4c; margin:8px 0; }
@media (max-width:1000px) { main { grid-template-columns:180px minmax(0,1fr); } aside:last-child { grid-column:1/-1; border-left:0; border-top:1px solid var(--line); } }
</style></head><body>
<header><h1>Family Care Circle</h1><p>Blinded rating · rater <strong id="rater"></strong> · <span id="progress">Loading…</span></p></header>
<main><aside><h2>Samples</h2><div class="muted">Condition labels are hidden.</div><div id="item-list"></div></aside>
<section><div class="toolbar"><button id="prev">← Previous</button><button id="next">Next →</button><span class="muted" id="current"></span></div>
<h3>Source note</h3><div id="note"></div><h3 id="persona-label"></h3><div id="text"></div></section>
<aside><h2>Rate this output</h2><div id="scales"></div>
<div class="flagwrap"><input type="checkbox" id="flag"><label for="flag" style="margin:0;display:inline">Missing or wrong medical fact</label></div>
<label for="flagnote">Details (if flagged)</label><textarea id="flagnote" rows="3"></textarea>
<button class="primary" id="save" style="margin-top:12px">Save rating</button><div id="message"></div></aside></main>
<script>
const DIMENSIONS=[["factual_accuracy","Factual accuracy"],["completeness","Completeness"],["readability","Readability"],["persona_suitability","Persona suitability"]];
let state,current=null,currentIndex=0;
const $=id=>document.getElementById(id);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function api(url, opts){return fetch(url,opts).then(r=>r.ok?r.json():r.json().then(x=>Promise.reject(new Error(x.error||'Request failed'))));}
function renderList(){$('item-list').innerHTML=state.items.map((it,i)=>`<button class="item-row ${i===currentIndex?'current':''} ${it.rated?'done':''}" data-i="${i}">${i+1}. ${esc(it.persona)}</button>`).join('');document.querySelectorAll('.item-row').forEach(b=>b.onclick=()=>loadItem(Number(b.dataset.i)));}
function renderScales(prior){$('scales').innerHTML=DIMENSIONS.map(([key,label])=>`<label>${label}</label><div class="scale">`+[1,2,3,4,5].map(v=>`<label><input type="radio" name="${key}" value="${v}" ${prior&&prior.scores&&prior.scores[key]===v?'checked':''}><span>${v}</span></label>`).join('')+`</div>`).join('');}
function render(){renderList();$('note').textContent=current.source_note||'(no source note)';$('persona-label').textContent=current.persona;$('text').textContent=Array.isArray(current.text)?current.text.map(t=>'- '+t).join('\n'):current.text;$('current').textContent=`${currentIndex+1} / ${state.count}`;$('progress').textContent=`Rated: ${state.items.filter(i=>i.rated).length} / ${state.count}`;renderScales(current.rating);$('flag').checked=!!(current.rating&&current.rating.missing_or_wrong_fact);$('flagnote').value=(current.rating&&current.rating.missing_or_wrong_fact_note)||'';$('message').innerHTML='';}
function loadItem(i){currentIndex=i;api('/api/item?sample_id='+encodeURIComponent(state.items[i].sample_id)).then(it=>{current=it;render();}).catch(showError);}
function showError(e){$('message').innerHTML=`<p class="error">${esc(e.message||e)}</p>`;}
$('save').onclick=()=>{const scores={};for(const [key] of DIMENSIONS){const el=document.querySelector(`input[name="${key}"]:checked`);if(el)scores[key]=Number(el.value);}
  api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:current.sample_id,scores,missing_or_wrong_fact:$('flag').checked,missing_or_wrong_fact_note:$('flagnote').value})}).then(()=>api('/api/state')).then(s=>{state=s;render();$('message').innerHTML='<p class="ok">Saved.</p>';}).catch(showError);};
$('prev').onclick=()=>loadItem(Math.max(0,currentIndex-1));$('next').onclick=()=>loadItem(Math.min(state.count-1,currentIndex+1));
api('/api/state').then(s=>{state=s;$('rater').textContent=s.rater;renderList();loadItem(0);}).catch(showError);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    store: RatingStore

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
            elif parsed.path == "/api/item":
                sample_id = parse_qs(parsed.query).get("sample_id", [""])[0]
                self._send(self.store.item(sample_id))
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rater", required=True, help="Rater id; ratings are saved to ratings_<rater>.json")
    parser.add_argument("--set-path", default="results/human_eval/rating_set.json")
    parser.add_argument("--out-dir", default="results/human_eval")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        store = RatingStore(resolve_path(args.set_path), resolve_path(args.out_dir), args.rater)
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    Handler.store = store
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    LOGGER.info("Rater '%s' - open http://%s:%d/", args.rater, args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping rating UI")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
