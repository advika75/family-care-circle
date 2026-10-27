"""Exploratory batch run of SYNTHETIC notes through the app's Ollama path (job runner -> pipeline -> gates -> store).

Writes only to a scratch database (refuses any path under app/var) and to the Markdown table given by --out.
Extra notes are read from existing databases with an immutable, read-only connection. Never use real patient notes.

    python -m app.tools.ollama_batch --db <scratch.sqlite3> --out app/audit/ollama_batch.md \
        --dump <scratch.json> --extra-note app/var/demo-ollama.sqlite3:2
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from app import accounts, circle, notes, outputs
from app.config import Settings
from app.context import Ctx
from app.db import connect, migrate
from app.jobs import JobRunner

ROOT = Path(__file__).resolve().parents[2]


def _extra_note(spec: str) -> tuple[str, str]:
    path, note_id = spec.rsplit(":", 1)
    conn = sqlite3.connect(f"file:{(ROOT / path).resolve()}?immutable=1", uri=True)
    try:
        row = conn.execute("SELECT text FROM notes WHERE id = ?", (int(note_id),)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise SystemExit(f"note {spec} not found")
    return f"{Path(path).name}#{note_id}", row[0]


def _patient_state(flags: dict) -> str:
    claims = (flags.get("clinical_claim_gate") or {}).get("patient")
    if claims:
        return "replaced by review text (claim gate: " + ", ".join(claims) + ")"
    if flags.get("patient_summary_unavailable"):
        return "unavailable (generic fallback)"
    if flags.get("patient_summary_needs_review"):
        return "draft + review warning"
    return "no fallback"


def _row(name: str, wall: float, child_withheld: bool, flags: dict) -> dict:
    unsupported = flags.get("unsupported", {})
    return {
        "note": name, "wall": wall, "status": "done", "patient": _patient_state(flags),
        "child_withheld": child_withheld, "child_reasons": flags["child_gate"]["reasons"],
        "claim_gate": {k: v for k, v in flags["clinical_claim_gate"].items() if k != "fired" and v},
        "caregiver_fallback": flags.get("caregiver_fallback"),
        "fallback_used": [k for k, v in flags.get("fallback_used", {}).items() if v],
        "redacted": sum(len(v) for v in flags.get("redacted_dosages", {}).values()),
        "numbers": sum(len(v.get("numbers", [])) for v in unsupported.values()),
        "meds": sum(len(v.get("medications", [])) for v in unsupported.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dump", required=True, type=Path)
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--extra-note", action="append", default=[])
    ap.add_argument("--append-version", default=None,
                    help="append a section with this title (gate v3 columns) to --out instead of rewriting it")
    args = ap.parse_args()
    if (ROOT / "app" / "var").resolve() in args.db.resolve().parents or args.db.exists():
        raise SystemExit("--db must be a NEW scratch database outside app/var")

    settings = Settings(backend="ollama", ollama_model=args.model, ollama_timeout_seconds=120, job_timeout_seconds=1200,
                        job_isolation="process", db_path=args.db, secret_key=secrets.token_bytes(32),
                        max_note_chars=20_000)
    ctx = Ctx(settings=settings)
    conn = connect(settings.db_path)
    migrate(conn)
    owner = accounts.signup(conn, ctx, email="batch@example.test", display_name="Batch Runner",
                            password=secrets.token_urlsafe(24))
    profile = circle.create_profile(conn, ctx, owner, display_name="Synthetic Batch", relationship_label="Daughter")
    runner = JobRunner(settings, ctx)

    sources = [(p.name, p.read_text()) for p in sorted((ROOT / "data" / "raw").glob("*.txt"))]
    sources += [_extra_note(spec) for spec in args.extra_note]
    rows, dump = [], []
    scratch = _instrument() if args.append_version else None
    try:
        for name, text in sources:
            if scratch is not None:
                scratch.update(categories=[], research_unsupported=[])
            note = notes.add_note(conn, ctx, runner, owner, profile, title=name, text=text)
            t0 = time.monotonic()
            runner.drain()
            wall = time.monotonic() - t0
            status = conn.execute("SELECT status, error_message FROM notes WHERE id = ?", (note["id"],)).fetchone()
            out = conn.execute("SELECT * FROM outputs WHERE note_id = ?", (note["id"],)).fetchone()
            if out is None:
                rows.append({"note": name, "wall": wall, "status": status["status"], "error": status["error_message"]})
                dump.append({"note": name, "status": status["status"], "error": status["error_message"]})
                print(f"{name}: {status['status']} in {wall:.0f}s", flush=True)
                continue
            flags = json.loads(out["flags"])
            if scratch is not None:
                rows.append(_row_v2(name, wall, out, flags, scratch))
            else:
                rows.append(_row(name, wall, bool(out["child_withheld"]), flags))
            dump.append({"note": name, "wall": wall, "patient_summary": out["patient_summary"],
                         "caregiver_checklist": json.loads(out["caregiver_checklist"]),
                         "child_explanation": out["child_explanation"], "flags": flags})
            print(f"{name}: done in {wall:.0f}s", flush=True)
    finally:
        runner.shutdown()
        conn.close()
    args.dump.write_text(json.dumps(dump, indent=2))
    if args.append_version:
        with args.out.open("a") as handle:
            handle.write(_markdown_v2(rows, args.model, args.append_version))
    else:
        args.out.write_text(_markdown(rows, args.model))
    return 0


def _instrument() -> dict:
    """Scratch-run-only instruments (this process only). They record fixed rule labels and medicine names, never text:
    which recovery rule removed a sentence, and which medicines the research check flagged in the first patient
    attempt (to see whether the insulin false positive caused a generic fallback)."""
    from app import clinical_safety
    from src.evaluator import unsupported_meds

    state: dict = {"categories": [], "research_unsupported": []}
    real_recovery, real_build = outputs.unsupported_recovery_sentence, outputs.build_output

    def recovery(sentence: str, source: str) -> bool:
        hit = real_recovery(sentence, source)
        if hit:
            state["categories"].append(clinical_safety.recovery_category(sentence))
        return hit

    def build(record: dict, source_text: str) -> dict:
        first = (record.get("metadata", {}).get("first_attempt_text") or {}).get("patient_summary") or ""
        state["research_unsupported"] = unsupported_meds(first, source_text, record.get("entities", []))["unsupported"]
        return real_build(record, source_text)

    outputs.unsupported_recovery_sentence = recovery
    outputs.build_output = build
    return state


def _row_v2(name: str, wall: float, out: Any, flags: dict, scratch: dict) -> dict:
    if out["patient_summary"] == outputs.PATIENT_REVIEW_FALLBACK:
        patient = "review text (other claim)"
    elif flags.get("patient_summary_unavailable"):
        patient = "unavailable"
    elif flags.get("patient_summary_needs_review"):
        patient = "generated, sentences removed or facts appended (warning)"
    else:
        patient = "generated"
    dose = flags.get("dose_mismatch", {})
    recovery = flags.get("recovery_removed", {})
    return {
        "note": name, "wall": wall, "status": "done", "patient": patient,
        "recovery": (recovery.get("patient_summary", 0), recovery.get("caregiver_checklist", 0)),
        "categories": [c for c in scratch["categories"] if c],
        "dose": (len(dose.get("patient_summary", [])), len(dose.get("caregiver_checklist", []))),
        "appendix": flags.get("caregiver_appendix_rendered", 0),
        "child_withheld": bool(out["child_withheld"]), "child_reasons": flags["child_gate"]["reasons"],
        "generic_fallback_insulin": bool(flags.get("patient_summary_unavailable") and not recovery.get("patient_summary")
                                         and not dose.get("patient_summary")
                                         and "insulin" in scratch["research_unsupported"]),
        "research_unsupported": list(scratch["research_unsupported"]),
        "numbers": sum(len(v.get("numbers", [])) for v in flags.get("unsupported", {}).values()),
    }


def _markdown_v2(rows: list[dict], model: str, title: str) -> str:
    from collections import Counter

    done = [r for r in rows if r["status"] == "done"]
    n = len(rows)
    generated = sum(r["patient"].startswith("generated") for r in done)
    categories = Counter(c for r in done for c in r["categories"])
    lines = [
        "", f"## {title}", "",
        f"> **Ollama-served model `{model}`, app prompt guard and app gate version {outputs.GATE_VERSION}. "
        "This is NOT the paper's model or the paper's results.** Exploratory, single run, temperature and seed from "
        f"`config.yaml`, **n = {n} notes** (the same 12 `data/raw/` notes and {n - 12} demo-database notes as above). "
        "Synthetic notes only. Nothing here is in `results/`.", "",
        f"Generated by `python -m app.tools.ollama_batch --append-version ...` into a new scratch database on "
        f"{time.strftime('%Y-%m-%d')}. Changes since the table above: dose-to-drug check, recovery phrases remove a "
        "sentence or line instead of the whole text, caregiver appendix rendered from the regimen.", "",
        "* Jobs finished: " + f"{len(done)}/{n}",
        f"* Patient shown a generated summary: {generated}/{len(done)}",
        f"* Sentences or lines removed for an unsupported recovery phrase: patient "
        f"{sum(r['recovery'][0] for r in done)}, caregiver {sum(r['recovery'][1] for r in done)}; by rule: "
        + (", ".join(f"{k} {v}" for k, v in categories.most_common()) or "none"),
        f"* Dose mismatches caught (sentences/lines removed): patient {sum(r['dose'][0] for r in done)}, caregiver "
        f"{sum(r['dose'][1] for r in done)}",
        f"* Caregiver appendix lines rendered from the regimen: {sum(r['appendix'] for r in done)}",
        f"* Child text withheld: {sum(r['child_withheld'] for r in done)}/{len(done)}",
        f"* Patient summary unavailable because the research check flagged \"insulin\" in the first attempt: "
        f"{sum(r['generic_fallback_insulin'] for r in done)}/{len(done)}",
        f"* Wall time per note: {min(r['wall'] for r in done):.0f}-{max(r['wall'] for r in done):.0f} s "
        f"(median {sorted(r['wall'] for r in done)[len(done) // 2]:.0f} s)", "",
        "| Note | Wall (s) | Patient summary | Recovery removed (patient/caregiver) | Dose mismatches (patient/caregiver) | "
        "Appendix rendered | Child withheld | Child gate reasons | Research-flagged medicines, first patient attempt | "
        "Invented numbers |",
        "|---|---:|---|---|---|---:|---|---|---|---:|",
    ]
    for r in rows:
        if r["status"] != "done":
            lines.append(f"| {r['note']} | {r['wall']:.0f} | {r['status']}: {r['error']} | | | | | | | |")
            continue
        lines.append(
            f"| {r['note']} | {r['wall']:.0f} | {r['patient']} | {r['recovery'][0]}/{r['recovery'][1]} | "
            f"{r['dose'][0]}/{r['dose'][1]} | {r['appendix']} | {'yes' if r['child_withheld'] else 'no'} | "
            f"{', '.join(r['child_reasons']) or 'none'} | {', '.join(r['research_unsupported']) or 'none'} | "
            f"{r['numbers']} |")
    lines.append("")
    return "\n".join(lines)


def _markdown(rows: list[dict], model: str) -> str:
    done = [r for r in rows if r["status"] == "done"]
    n = len(rows)

    def rate(k: int, d: int) -> str:
        return f"{k}/{d} ({100 * k / d:.0f}%)" if d else "0/0"

    unavailable = sum(r["patient"].startswith("unavailable") for r in done)
    review = sum(r["patient"].startswith("draft") for r in done)
    replaced = sum(r["patient"].startswith("replaced") for r in done)
    shown = len(done) - unavailable - replaced
    withheld = sum(r["child_withheld"] for r in done)
    lines = [
        "# Ollama batch run (exploratory)",
        "",
        f"> **Ollama-served model `{model}`, app prompt guard and app gate version {outputs.GATE_VERSION}. "
        "This is NOT the paper's model or the paper's results.** Exploratory, single run, temperature and seed from "
        f"`config.yaml`, **n = {n} notes** (12 synthetic notes from `data/raw/` plus {n - 12} synthetic notes from the "
        "demo databases). Synthetic notes only. Nothing here is in `results/`.",
        "",
        f"Generated by `python -m app.tools.ollama_batch` into a scratch database on "
        f"{time.strftime('%Y-%m-%d')}. Jobs: process isolation, 120 s per request, 1200 s per job.",
        "",
        "## Rates",
        "",
        f"* Jobs finished: {rate(len(done), n)}",
        f"* Patient summary replaced by the generic fallback (shown as \"Summary unavailable\"): {rate(unavailable, len(done))}",
        f"* Patient summary kept as a draft with a review warning (missing facts appended or dose redacted): "
        f"{rate(review, len(done))}",
        f"* Patient summary replaced by the claim gate's review text (an unsupported claim phrase was found): "
        f"{rate(replaced, len(done))}",
        f"* Patient sees a generated summary at all: {rate(shown, len(done))}",
        f"* Child explanation withheld (safe message shown): {rate(withheld, len(done))}",
        "",
        "## Per note",
        "",
        "| Note | Wall time (s) | Status | Patient summary | Child withheld | Child gate reasons | Claim gate | "
        "Caregiver fallback | Pipeline fallback used | Redacted doses | Invented numbers | Invented medicines |",
        "|---|---:|---|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for r in rows:
        if r["status"] != "done":
            lines.append(f"| {r['note']} | {r['wall']:.0f} | {r['status']}: {r['error']} | | | | | | | | | |")
            continue
        claims = "; ".join(f"{k}: {', '.join(v)}" for k, v in r["claim_gate"].items()) or "none"
        lines.append(
            f"| {r['note']} | {r['wall']:.0f} | done | {r['patient']} | {'yes' if r['child_withheld'] else 'no'} | "
            f"{', '.join(r['child_reasons']) or 'none'} | {claims} | {'yes' if r['caregiver_fallback'] else 'no'} | "
            f"{', '.join(r['fallback_used']) or 'none'} | {r['redacted']} | {r['numbers']} | {r['meds']} |")
    lines += ["", "\"Invented numbers\" and \"Invented medicines\" are the app's stored `unsupported` flags for the patient "
              "summary and caregiver checklist as displayed (research checks `unsupported_numbers` / `unsupported_meds`). "
              "They are phrase and number matches, not a clinical review.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
