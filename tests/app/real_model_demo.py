"""Real-model run of the whole journey on the LOCAL DEMO app (``make app-demo``, then ``make app-demo-seed`` once).

    .venv/bin/python tests/app/real_model_demo.py http://127.0.0.1:8001 data/raw/note_02.txt "Title"

Logs in as the four seeded demo roles (passwords are read from the git-ignored app/var/demo_credentials.txt and are
never printed or written to the report), adds the SYNTHETIC note as the creator, waits for the real model, fetches every
role's view through HTTP, writes app/audit/real_model_demo.md (generated text, gate result, flags) and 1280px screenshots
to app/audit/screenshots/real_demo/. Not collected by pytest (name does not start with test_).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
CRED = ROOT / "app" / "var" / "demo_credentials.txt"
OUT = ROOT / "app" / "audit"
SHOTS = OUT / "screenshots" / "real_demo"
ROLES = ("creator", "caregiver", "patient", "child")


def credentials() -> dict[str, tuple[str, str]]:
    found = {}
    for line in CRED.read_text().splitlines():
        m = re.match(r"\s+(\w+)\s+(\S+@\S+)\s+password:\s+(\S+)", line)
        if m:
            found[m.group(1)] = (m.group(2), m.group(3))
    assert set(found) == set(ROLES), "run `make app-demo-seed` first"
    return found


def login(base: str, email: str, password: str) -> httpx.Client:
    c = httpx.Client(base_url=base, follow_redirects=False, timeout=60)
    t = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', c.get("/login").text).group(1)
    r = c.post("/login", data={"email": email, "password": password, "csrf_token": t})
    assert r.status_code == 303, f"login failed for {email}: {r.status_code}"
    return c


def main(base: str, note_path: str, title: str, report: str = "real_model_demo.md", shots: bool = True) -> None:
    creds = credentials()
    clients = {r: login(base, *creds[r]) for r in ROLES}
    cr = clients["creator"]
    pid = re.search(r"/p/(FCC-[A-Z0-9]{4}-[A-Z0-9]{4})", cr.get("/profiles").text).group(1)
    text = Path(note_path).read_text(encoding="utf-8")
    csrf = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', cr.get("/settings").text).group(1)
    t0 = time.time()
    r = cr.post(f"/api/p/{pid}/notes", data={"title": title, "text": text}, headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    note_id = r.json()["id"]
    state = "queued"
    while time.time() - t0 < 900:
        state = cr.get(f"/api/p/{pid}/status").json()["state"]
        if state in ("done", "failed"):
            break
        time.sleep(3)
    wait = time.time() - t0
    print(f"state={state} wait={wait:.0f}s")
    assert state == "done"

    views = {r: clients[r].get(f"/api/p/{pid}/outputs") for r in ROLES}
    j = {r: v.json() for r, v in views.items()}
    lines = [f"# Real-model run on the local demo app", "",
             f"Synthetic note: `{note_path}` ({len(text)} characters), title \"{title}\". Real model: Qwen2.5-3B-Instruct Q4_K_M "
             f"(llama_cpp). **Wait time: {wait:.0f} s** (includes loading the model in a fresh worker process).", "",
             "Synthetic data only. Prototype. Not for real patient data.", "", "## The note (input)", "", "```", text.strip(), "```", ""]
    c = j["creator"]
    lines += ["## Patient summary", "", c["patient_summary"], "", "## Caregiver checklist", ""]
    items = c["caregiver_checklist"] if isinstance(c["caregiver_checklist"], list) else c["caregiver_checklist"].get("items", [])
    lines += [f"{i + 1}. {it['text'] if isinstance(it, dict) else it}" for i, it in enumerate(items)]
    lines += ["", "## Child explanation (as shown to the child)", "", c["child_explanation"], "",
              f"Withheld by the safety gate: **{c['child_withheld']}**", "", "## Review flags (creator/caregiver view)", "",
              "```json", json.dumps(c["flags"], indent=2), "```", "", "## What each role received", "",
              "| role | HTTP | fields |", "|---|---|---|"]
    for r in ROLES:
        lines.append(f"| {r} | {views[r].status_code} | {', '.join(sorted(j[r]))} |")
    (OUT / report).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if shots:
        from playwright.sync_api import sync_playwright
        SHOTS.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            br = p.chromium.launch()
            for r in ROLES:
                ctx = br.new_context(viewport={"width": 1280, "height": 900})
                pg = ctx.new_page()
                pg.goto(base + "/login")
                pg.fill("input[name=email]", creds[r][0]); pg.fill("input[name=password]", creds[r][1])
                pg.click("button[type=submit]")
                pg.wait_for_url(re.compile(r"/profiles|/p/"))
                pg.goto(base + f"/p/{pid}")
                pg.screenshot(path=str(SHOTS / f"dashboard-{r}-1280.png"), full_page=True)
                if r in ("creator", "caregiver"):
                    pg.goto(base + f"/p/{pid}/summaries?tab=caregiver")
                    pg.screenshot(path=str(SHOTS / f"summaries-{r}-1280.png"), full_page=True)
                ctx.close()
            br.close()
    print("report:", OUT / report, "| note id", note_id)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], *(a[3:4] or ["real_model_demo.md"]), shots=(len(a) < 5))
