# Family Care Circle web app — progress

Self-hosted, multi-user web application. FastAPI + Uvicorn + SQLite + Jinja2, no Node toolchain.
This file is the resume point for a new session. Update it after every stage.

Run the app tests: `.venv/bin/python -m pytest tests/app -q`. Run everything: `.venv/bin/python -m pytest -q`.

## Status

| Stage | Description | State |
|---|---|---|
| 0 | Inspect, dependency list, progress file | **Done** |
| 1 | Data model, auth, sessions, `can()`, invitations, patient IDs (no UI) | **Done** — 149 tests |
| 2 | Notes, job queue, pipeline, child safety gate, role-filtered outputs, checklist | **Done** — 265 app tests, 500 total green |
| 3 | Design system, welcome, signup, login, profiles, stepper, created, join | **Done** — 333 app tests, 568 total green |
| 4 | Dashboard, info, circle, summaries, notes, settings, error pages, all states | **Done** — 432 app tests, 667 total green |
| 5 | Accessibility/contrast, responsive check, security review, `dev_seed.py` | **Done** (no browser screenshots: Playwright not installed) |
| 6 | Docs: README section + `app/README.md` | **Done** — 483 app tests, 718 total green |

## Decisions made by the project owner (Stage 0 gate)

1. **FastAPI pinned to 0.141.0** (newest without the `opentelemetry-api` requirement; works with Starlette 1.8.0 that Streamlit needs). Pydantic and its helpers come with it.
2. **Child safety gate sentence limit: 8** (matches the prompt's "5 to 8 sentences"), not the 6 in the first draft of the spec. Digit and medication-name checks unchanged. Measured on 100 stored real-model outputs: 17 withheld at limit 8 (65 at limit 6). The **mock backend always writes 9 sentences**, so with the mock backend the child view always shows the safe message.
3. **Approvals:** the creator approves any pending membership; a caregiver may approve only pending *child* memberships.
4. **Fonts:** system-font fallback only for now. The stack is declared in `tokens.css` so Fraunces / Nunito Sans files can be dropped into `app/static/fonts` later.

## Environment facts (verified)

- Python 3.12.3 in `.venv`. Existing research suite: 235 tests, must stay green.
- Installed for the app (`requirements-app.txt`): fastapi 0.141.0, uvicorn 0.54.0, jinja2 3.1.6, python-multipart 0.0.32, httpx 0.28.1 (tests only), plus pydantic 2.14.1, pydantic-core 2.50.1, annotated-types 0.8.0, typing-inspection 0.4.4. `pip check` reports no broken requirements; numpy/pandas/torch/transformers/streamlit untouched.
- Pipeline with the mock backend: `FamilyCarePipeline(load_config("config.yaml", {"backend": "mock"}))` builds in ~1.5 s, `run()` ~3 ms. Real backend ~75 s per note. The generator keeps per-instance state, so the pipeline must only be called from one worker thread.
- Playwright and SQLAlchemy are not installed (SQLAlchemy is not needed). Playwright is optional for Stage 5 screenshots.

## Stage 1 — what exists (`app/`)

| Module | Purpose |
|---|---|
| `config.py` | `Settings` from environment variables (`APP_BACKEND`, `APP_DB_PATH`, `APP_HTTPS`, `APP_SECRET_KEY`, `APP_SESSION_TTL_HOURS`, `APP_INVITE_TTL_DAYS`) |
| `errors.py` | User-safe, generic errors |
| `security.py` | `hashlib.scrypt` (N=2^15, r=8, p=1, per-user salt, parameters stored in the hash), constant-time compare, token generation/digest |
| `ids.py` | Patient ID `FCC-XXXX-XXXX` (30-char alphabet, ~39 bits, `secrets`), invitation code `XXXX-XXXX-XXXX-XXXX` (~78 bits) |
| `csrf.py` | HMAC token bound to the session digest (or an anonymous cookie before login) |
| `throttle.py`, `context.py` | In-memory sliding-window throttle; injectable clock |
| `migrations.py`, `db.py` | Schema v1 (users, sessions, profiles, memberships, invitations), WAL, foreign keys, `BEGIN IMMEDIATE` transactions |
| `permissions.py` | `can()` / `decide()` — the single place that decides access; `circle_view_level()` |
| `accounts.py` | signup, login (generic errors, throttling, timing parity), server-side sessions (digest stored), logout, logout-all, change password, delete account |
| `circle.py` | create profile (+creator membership, atomic), invitations (hashed, 7 days, single use, revocable), join (pending), approve / revoke / change role / toggle `can_add_notes`, role-filtered `list_members` |

**Verified by tests (`tests/app/`, 149 tests):** role × action matrix for active members; pending/revoked get only the status page; patient ID alone grants nothing (also across circles); invitation expiry, reuse, wrong circle, wrong ID/code (same generic error), revoked; join always takes the invitation's role; relationship label never changes permissions; caregiver approves only pending children; creator membership immutable; DB CHECK constraints; member list filtered by role (child sees first names only); secrets (passwords, tokens, invitation codes, emails) are not logged; login/join/password-change throttling; session expiry and logout; SQL-injection strings stored as data.

**Mutation check done:** five deliberate breakages (pending gets access, caregiver approves anyone, expiry ignored, child sees full circle, login throttle skipped) were each caught by the tests; the files were restored and verified identical.


## Stage 2 — what exists

| Module | Purpose |
|---|---|
| `migrations.py` (v2) | `notes`, `outputs` (one row per note), `checklist_ticks` (who/when) |
| `safety.py` | Child gate: digit, any extracted medication name of that note, more than 8 sentences -> safe message `A grown-up will help explain what the doctor said.`; reasons recorded in flags; the rejected text is not stored |
| `notes.py` | add (creator, or caregiver with `can_add_notes`), delete (creator), list, source; paste or `.txt` upload only, max 20,000 chars, clear messages |
| `outputs.py` | `build_output` (runs the gate, builds flags from pipeline metadata), role-filtered `latest_outputs` / `outputs_for_note` / `history` / `generation_state`, `set_tick` |
| `jobs.py` | `JobRunner`: one worker thread, FIFO, pipeline built lazily once per process and guarded by a lock, safe failure messages, restart recovery |
| `pipeline_adapter.py` | `FamilyCarePipeline(load_config("config.yaml", {"backend": APP_BACKEND}))` — calls `src/`, never edits it |
| `web/main.py`, `web/deps.py`, `web/api.py`, `web/middleware.py` | App factory, session + CSRF dependencies, JSON API (`/api/p/<id>/...`), security headers (CSP without inline script/style, nosniff, frame denial, no-referrer, no-store; HSTS only with `APP_HTTPS=1`), request-body size limit (256 KB, enforced while streaming) |

**Verified by tests (265 app tests):** per-role JSON responses over HTTP (patient gets only `patient_summary`; child gets only `child_explanation` and no source/doses/medication names/flags/title; creator and caregiver get everything); forbidden endpoints are 403 for patient/child; pending and revoked members get only a status error; a logged-in non-member gets the *same* 404 as for a non-existent ID; CSRF (missing, forged, another session's token, form field vs header) on every state-changing endpoint; security headers on success, error and 404 responses; uploads (bad type, bad UTF-8, both text and file, too long, oversized body -> 413); FIFO and one-at-a-time processing with a real worker thread; polling through queued -> running -> done; failure handling (safe message, exception text never stored or logged, worker survives); deletion while running; restart recovery; deletion cascade; source text exists only in `notes`; end-to-end run of the real `FamilyCarePipeline` on the mock backend.

**Mutation checks:** 12 deliberate breakages (flags to all roles, gate ignores digits, CSRF bypass, pipeline lock removed, non-member distinguishable from unknown ID, CSP inline scripts, history open to all, anyone adds notes, anyone ticks, body limit off, source text copied into outputs, failed job leaks exception text) were each caught; files restored and verified identical.

**Bug found by repeated runs:** `safety.medication_names` ordered equal-length names by hash-seed-dependent set order (a flaky test). Fixed (longest first, ties alphabetical); suite verified stable under 8 different `PYTHONHASHSEED` values.

### More assumptions (Stage 2)

- Checklist items can be unticked (the row is removed); ticking records who and when. Progress is per note's checklist; the latest output's checklist is the "current" one.
- Patients and children can see the *state* of generation (none / queued / running / done / failed) but never the note title or the failure message.
- A failed note is not retried automatically; the creator deletes it and adds it again (no retry feature in the spec).
- Stored `flags` hold counts, retention numbers, the model's own flagged tokens and the model identity — not source text. `appended_by_fallback` lists facts the pipeline appended; they also appear in the output itself.
- Unknown profile IDs and non-members both return 404 on the API so the existence of a care circle is not revealed. Pending/revoked members get 403 with a specific code (they hold a valid invitation).
- The client IP used for throttling is the socket peer address; `X-Forwarded-For` is not trusted (no reverse proxy is assumed).

## Open issues

- Starlette's test client prints a deprecation warning ("install `httpx2` instead"). `httpx2` is not on the approved dependency list, so it is **not installed**; the warning is harmless today but a future Starlette release could drop `httpx` support for `TestClient`.


## Stage 3 — what exists

- **Design system:** `static/css/tokens.css` (all colours, type, radii, 44px targets), `static/css/base.css` (components; no colour literals, no inline styles), `static/js/app.js` (copy button only; no `eval`/`innerHTML`), inline SVG icons (`templates/partials/icons.html`), components (`templates/partials/components.html`: link_button, button, field, textarea_field, select_field, stepper, role_chip, status_chip, banner, empty_state, copy_button, card, csrf_field), nav. System-font fallback stack (decision 4); Fraunces/Nunito Sans are used only if installed on the device.
- **Contrast:** `.venv/bin/python -m app.tools.contrast` checks 43 token pairs against WCAG AA (4.5:1 text, 3:1 controls/focus); all pass; `tests/app/test_app_design.py` runs it.
- **Pages:** `/` welcome (two paths), `/signup`, `/login`, `POST /logout`, `/profiles` (switcher in nav, empty state), `/profiles/new` (4-step stepper that works without JavaScript: values for other steps travel as hidden fields; per-step validation; review), `/p/<id>/created` (ID + copy button, role, "not a password", how to invite), `/join` (all error states), `/p/<id>` (pending / access-removed page for those members; active members are redirected to `/profiles` until Stage 4 adds the dashboard).
- **Security wiring:** anonymous CSRF cookie + signed token for login/signup; session-bound token for every other form; `next=` is an allow-list; session cookie HttpOnly + SameSite=Lax (+ Secure with `APP_HTTPS=1`); HTML error pages for browsers, JSON for `/api`.
- **Makefile / .gitignore:** `app-run`, `app-test` appended (`app-seed` arrives with `dev_seed.py` in Stage 5); `app/var/`, `*.sqlite3*`, `.env.*` appended to `.gitignore`.

**Bugs found and fixed while testing Stage 3**
1. Jinja macros imported without `with context` could not see `csrf_token`, so forms rendered an empty token (found by the first page test). Fixed in the five templates.
2. `nav.items` resolved to the dict method, not my key (renamed `links`).
3. **Leak:** a pending member's nav menu listed the patient's name. Fixed in `circle.list_profiles_for_user`: pending and revoked members now see `Care circle FCC-XXXX-XXXX` instead of the name (test written first and seen failing).
4. The "created" page had no `<h1>`.
5. Starlette's router 404 bypassed the HTML error handler (handler now registered on the base `HTTPException`).

**Verified by running the real server** (`make app-run`, mock backend, scratch database, `curl`): sign-up -> 303 /profiles; profile creation -> 303 to the created page showing a real `FCC-` ID; unauthenticated request -> 303 /login; correct headers; no password or email in the server log. Note: uvicorn's access log records URLs, which contain patient IDs (identifier only, but worth knowing).

**Mutation checks:** 9 breakages tried; 7 caught. The 2 survivors are equivalent mutants (Starlette's `set_cookie` already defaults to `SameSite=lax`; an unused extra form parameter changes nothing).

Playwright is not installed, so no screenshots will be taken unless it is approved and installed in Stage 5.


## Stage 4 — what exists

- **Routes (HTML):** `/p/<id>` dashboard, `/p/<id>/info`, `/p/<id>/circle` (+ invite / approve / decline / change role / allow notes / remove / cancel invitation / delete circle), `/p/<id>/summaries` (tabs Patient / Caregiver / Child as real links, with `?tab=`; history via `?note=`; the checklist is a tab, so there is **no duplicate `/checklist` page**), `POST /p/<id>/checklist/<note>/<n>`, `/p/<id>/notes` (+ upload, delete), `/settings` (change password, log out of all sessions, delete account), `/unauthorized`, error pages.
- **Components added:** `context_bar`, `persona_card`, `checklist_item`, `member_row`, `skeleton`, `gen_chip`, `preparing` (polling block). `app.js` now also polls `/api/p/<id>/status` and reloads when a note finishes (without JavaScript the page shows the state and a Refresh link).
- **Templates only receive role-filtered data.** Keys such as `flags` and `source` are *omitted* from the context for roles that may not see them; a test inspects every template context for the child and patient roles.
- **Navigation** is built with `permissions.decide`, so a role is only offered pages it may open, and it shows the open circle and the viewer's role (the child sees the preferred name only).

**Leaks found by the tests and fixed (test written first each time)**
1. Pending/revoked members saw the patient's name in the nav menu (Stage 3).
2. Children saw the patient's **full** name in the circle switcher; they now get the preferred name (or a first name).
3. `flags=None` / `source=None` were passed to templates for roles that may not see them; the keys are now omitted.

**Other defects fixed:** the delete-account checkbox was flagged by the accessibility audit (wrapping `<label>` is valid; the checker was taught); an `<h1>` was missing on the created page; a weak set of `or True` assertions in my own tests was tightened.

**Verified by running the real server** with `make app-run` (mock backend): create account -> create circle -> upload `data/raw/note_01.txt` -> background job reached `done` -> invite a child -> join -> pending page shows no patient name -> approve -> the child's API response contained only the safe child message; the owner's flags show `child_gate: fired, reasons: [too_long]`; no passwords or emails in the server log.

**Mutation checks:** 13 breakages of the page layer; 12 caught at once; 1 (extra email injected into a child's template context) exposed a gap in my context check, which was generalised ("no `@` anywhere in a child's or patient's context except their own account row") and then caught.


## Stage 5 and 6 — what was done

- **Security review (mechanical, from the live app):** the exact route inventory is pinned (42 routes, only GET and POST); every one of the 21 POST routes is refused without a CSRF token and changes nothing; GET routes never change the database; an AST scan checks that every SQL statement is a literal or a reviewed constant; another checks that no log call can emit text, passwords, tokens, codes or emails; autoescape is never disabled; login never adopts a client-chosen session id; no hard-coded credentials or example IDs; the app imports no network library.
- **Real defects found by the review and fixed (check failing first, then the fix):** (1) the SQLite file was created world-readable — now `0600` in a `0700` directory; (2) the join form's placeholder `FCC-ABCD-2345` was a valid-looking ID — placeholders now use `####`.
- **Accessibility, without a browser:** heading order, accessible names, unique ids, CSRF field on every POST form, distinct titles, credential autocomplete hints, no positive tabindex, viewport/zoom, 44px targets, visible focus, reduced motion, and no CSS width that could force horizontal scroll at 360px. The contrast script checks 44 pairs (all pass). **Not verified:** actual rendering at 360/768/1280px, focus appearance, screen readers.
- **`dev_seed.py` / `make app-seed`:** SYNTHETIC demo data only; four demo accounts and notes from `data/raw`; passwords from `APP_SEED_PASSWORD` or generated and printed once; refuses to run unless the database has no users.
- **Real model checked once by hand:** `APP_BACKEND=llama_cpp python -m app.dev_seed --notes 1` on one synthetic note: job `done` in 81 s, model hash identical to the research runs, flags recorded (fallback used for patient and caregiver, checklist retention 33%, child gate fired for `digit` and `too_long`). Not part of the automated tests.
- **Docs:** `app/README.md` (architecture, roles, ID vs credentials, what is and is not secured, gate limits, routes) and an appended "Multi-user web app" section in `README.md`; `tests/app/test_app_docs.py` keeps the claims true.
- **Child gate limits (documented and pinned by a test):** spelled-out numbers, brand/inflected/misspelled medicine names, medicines not extracted from the note, and frightening wording are NOT caught.

## Recommended next steps (for the project owner to decide)

1. Put a TLS-terminating reverse proxy in front before any use beyond `127.0.0.1`, and set `APP_HTTPS=1`.
2. Decide whether to tighten the child gate (spelled-out numbers, a medicine lexicon incl. brand names) — not done because the spec defined the gate narrowly.
3. Decide on a password-reset path (needs an email channel, which does not exist).
4. Install Playwright (needs approval) to take screenshots at 360/768/1280px and to test keyboard flows in a real browser.
5. Bundle the Fraunces and Nunito Sans font files if the design requires them.

## Open issues

- Starlette's test client warns that `httpx` is deprecated in favour of `httpx2` (not approved, not installed).
- With `APP_BACKEND=mock` the child explanation is always withheld (the mock writes 9 sentences; the limit is 8).

## Stage 7 — optional Ollama backend (implementation ready; security-test update pending approval)

- Added `app/ollama_generator.py`, using only `urllib.request` and `json`; it posts structured messages to Ollama's non-streaming chat API, reads model tags/digests, forwards config sampling/token/context settings, and refuses non-loopback hosts unless explicitly allowed.
- `APP_BACKEND=ollama` keeps the existing single-job queue and records backend, tag and API digest. The saved output disclaimer labels Ollama output as not the model used for the paper's results. Render remains mock-only.
- New isolated tests use a fake loopback HTTP server; no new Python dependency is needed. Focused result: 19 passed, 1 slow real-Ollama test skipped by default. The full suite now passes: 850 passed, 23 skipped.
- With owner approval, the network-import security regression now permits `urllib.request` only in `app/ollama_generator.py`; all other banned clients remain prohibited. Exception and job tests verify that request/response bodies are not exposed in error messages or logs.
- Ollama's server-side chat template is not guaranteed to match llama.cpp's GGUF template; this is documented in `app/README.md`. The opted-in real test passed against the installed `qwen2.5:3b` model using synthetic one-word prompt text; no patient note was sent. The adapter also disables environment proxies and refuses redirects so a loopback URL cannot silently route its request elsewhere.

## Assumptions made where the spec was silent (change if you disagree)

- `delete_note` is creator-only (the spec lists note deletion only under the creator).
- `view_info` (read-only profile page) is allowed for creator, caregiver, patient; not child. There is no profile editing (not in the spec).
- `view_circle` is allowed for every active member, filtered: creator sees all (email, status, permissions); caregiver sees active members plus pending child requests; patient sees active members' names and roles; child sees first names only.
- The invitation's `note` ("Note for yourself") is a private reminder for the inviter; it is **not enforced** at join time (F-11).
- A revoked member cannot rejoin with a new invitation (there is no "reinstate" in the spec).
- Joiners choose their relationship label from the same six options as the creator.
- Account deletion is refused while the user is the creator of a care circle (they must delete the circle first).
- Sessions have an absolute expiry only (default 7 days); changing the password ends all other sessions.
- Database default: `app/var/familycare.sqlite3` (to be added to `.gitignore` in Stage 3 when the Makefile targets are appended).

## Known limitations (to be stated in the docs)

- Signup with an existing email returns a generic refusal; without email delivery this cannot be made fully enumeration-proof.
- Throttling is in-memory and per process; an attacker can temporarily lock a known account by failing logins.
- HTTP-level tests (CSRF rejection through the test client, cookie flags, security headers) arrive with the web layer in Stage 3; Stage 1 tests the CSRF primitive only.


## Phase B — audit fixes (2026-10-25)

Fixed F-01 to F-09, F-11 to F-14, F-17 to F-19; kept F-10, F-15, F-16, F-21 to F-24; F-20 and F-23 verified by a browser run and by `pip-audit`. Status of every finding, with what verified it, is in `AUDIT.md` ("Phase B: status of every finding").

* New modules: `worker_process.py` (killable model worker), `clientip.py` (trusted-proxy client address). Rewritten: `throttle.py` (bounded). New migrations 3 (invitation `note`) and 4 (`profiles.invitations_paused`).
* New settings: `APP_TRUSTED_PROXIES`, `APP_JOB_ISOLATION`, `APP_JOB_TIMEOUT_SECONDS`, `APP_MAX_PENDING_PER_CIRCLE`, `APP_MAX_PENDING_TOTAL`. Note limit now 6,000 characters.
* Tests: `make app-test` runs the fast suite; `make app-test-slow` (`APP_RUN_SLOW=1`) adds Chromium browser tests, the authorization matrix and the real-model test. Dev tooling is in `requirements-app-dev.txt` (Playwright, pip-audit), not in `requirements-app.txt`.
* Optional items done: Pause new invitations; Bigger words. Not done: Read it out loud.
