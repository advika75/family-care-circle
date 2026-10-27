# Family Care Circle — multi-user web app (`app/`)

> **Prototype. Not for real patient data.** Family Care Circle is a research prototype. Generated text may be inaccurate and is not a substitute for professional medical advice. Check doses and instructions with the care team. Use synthetic or practice information only.

A self-hosted web application in which a **profile creator** makes a patient profile, gets a patient ID, and invites family members. Each member sees only the AI-generated output suited to their role: a **patient summary**, a **caregiver checklist**, and a **child explanation**. The text is produced by the research pipeline in `src/` (called, never modified). Mock and llama.cpp modes make no model API calls. The optional Ollama mode sends prompts to the configured Ollama server; it defaults to loopback and refuses remote hosts unless explicitly allowed.

Stack: FastAPI + Uvicorn, SQLite (stdlib `sqlite3`), Jinja2 server-rendered templates, static CSS, a small vanilla-JavaScript file. No Node toolchain.

Account and application data are stored in SQLite. Sessions have a seven-day absolute expiry by default
(`APP_SESSION_TTL_HOURS=168`); expiry removes only the session, and the account can sign in again.

## Run it

```bash
.venv/bin/python -m pip install -r requirements-app.txt     # fastapi, uvicorn, jinja2, python-multipart, httpx (tests)
make app-demo                                               # http://127.0.0.1:8000  (mock backend, no model needed)
make app-demo-seed                                          # optional: SYNTHETIC demo accounts, on an EMPTY demo database
make app-seed                                               # optional: seed the separate APP_DB_PATH database used by app-run
make app-test                                               # the app's own tests
```

`make` calls `python`, so activate the project's environment first (`source .venv/bin/activate`) or put `.venv/bin` on your `PATH`.
`make app-demo` selects the mock backend, uses `app/var/demo.sqlite3`, and binds only to port 8000. It prints the backend and URL, does not start Ollama or a local model, and exits if that port is already in use. For the Ollama demo, Ollama runs separately and the app checks the configured URL and model tag before it starts.

**With the llama.cpp model** (the local Qwen2.5-3B GGUF configured in `config.yaml`, via `llama-cpp-python` as described in the main README):

```bash
APP_BACKEND=llama_cpp make app-run
```

The model is loaded lazily in the isolated worker process when the first note is processed. In the one real-model run made while building this (one synthetic note from `data/raw`, scripted through `python -m app.dev_seed --notes 1`), generation took **81 s**, and the stored model hash was identical to the one recorded in the research runs. Pages show a "being prepared" state and update on their own.

The **mock** backend uses deterministic templates for all three audiences. Its child text only names a topic when that wording appears in the note; otherwise it uses a calm general message. The app adds app-specific grounding rules to model prompts and applies conservative phrase checks before saving text. These checks catch some unsupported claims but cannot establish clinical accuracy.

### Persona-output investigation

The stored field mappings and role-specific API permissions were correct. The earlier mock child template exceeded the sentence limit, and the mock caregiver writer appended generic tasks that were not always supported by the note. The pipeline's structural validation did not check whether a generated diagnosis or procedure was supported by the source. The app now replaces unsupported high-impact claims with calm review text and does not show a previous note's output while a newer note is pending or failed. A screenshot alone cannot establish the origin of an earlier saved claim; the original note and output record are needed for that.

The app supplies its own deterministic mock generator without changing `src/`: caregiver items use extracted note regimens and explicit instructions; the mock child view uses a calm general message rather than naming a diagnosis. A malformed checklist is replaced with note-based review steps or a general request to review the note with the care team. Internal retry counts, model identity, and detailed flags stay out of the ordinary summary UI. These controls are conservative filters, not proof of factual or clinical correctness.

### Optional Ollama backend

Install Ollama using its [official download instructions](https://ollama.com/download), start the local service if it is not already running (`ollama serve`), and pull a model tag you choose. For example:

```bash
ollama serve                         # in a separate terminal, if Ollama is not already running
ollama pull qwen2.5:3b               # once, before starting the demo
make app-demo-ollama                 # http://127.0.0.1:8001
```

`app-demo-ollama` explicitly selects `APP_BACKEND=ollama`, defaults to `APP_OLLAMA_MODEL=qwen2.5:3b`, `APP_OLLAMA_URL=http://127.0.0.1:11434`, a 120-second per-request timeout, a 1200-second whole-job timeout (at least 3 personas x 3 attempts x 120 s; preflight refuses to start if the job timeout is shorter), process isolation, and fixed web port 8001. Override these Make variables when invoking the target, for example `make app-demo-ollama APP_OLLAMA_MODEL=qwen2.5:7b`. Startup first queries `GET /api/tags` and checks that the exact selected model tag is installed; it sends no note and makes no generation request during preflight. It stops before serving if Ollama is unreachable or the model is missing. Uvicorn binds only to port 8001 and exits with an address-in-use error if another service already owns it; the target never falls back to mock or silently changes ports. See Ollama's [chat API](https://docs.ollama.com/api/chat) and [model tags API](https://docs.ollama.com/api/tags).

| Variable | Default | Meaning |
|---|---|---|
| `APP_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama base URL; non-loopback hosts are refused by default |
| `APP_OLLAMA_MODEL` | unset | Exact installed Ollama tag to use |
| `APP_OLLAMA_TIMEOUT_SECONDS` | `120` | Timeout for each Ollama HTTP request |
| `APP_OLLAMA_ALLOW_REMOTE` | `0` | Set to `1` to permit a non-loopback host. This sends note text over the network and breaks the project's local-processing privacy claim. |

Ollama receives structured system/user messages, with app-specific grounding rules added for child output. The adapter passes configured sampling values, per-persona token limits, and the context size. Ollama applies its installed model's own chat template, so formatting and outputs can differ from the llama.cpp GGUF used for the paper. Backend and model identity are kept in internal output metadata and are not shown in ordinary summary cards; keep Ollama runs separate from research results. The Ollama digest from `/api/tags` is recorded as the model hash.

### Configuration (environment variables; nothing secret lives in the repo)

| Variable | Default | Meaning |
|---|---|---|
| `APP_BACKEND` | `mock` | `mock`, `llama_cpp`, or `ollama` |
| `APP_DB_PATH` | `app/var/familycare.sqlite3` | SQLite file (created `0600`, directory `0700`; `app/var/` is git-ignored) |
| `APP_HTTPS` | `0` | `1` marks cookies `Secure` and sends HSTS. The app does **not** terminate TLS itself |
| `APP_SECRET_KEY` | random per process | key for CSRF tokens; if unset, anonymous (login/signup) tokens stop working after a restart |
| `APP_SESSION_TTL_HOURS` | `168` | absolute session lifetime |
| `APP_INVITE_TTL_DAYS` | `7` | invitation lifetime |
| `APP_TRUSTED_PROXIES` | none | comma-separated **exact addresses** of reverse proxies whose `X-Forwarded-For` header may be believed (no CIDR ranges). Leave empty unless you run behind a proxy; see "What is NOT secured" |
| `APP_JOB_ISOLATION` | `auto` | `auto` = llama.cpp and Ollama run in a separate process that is killed on timeout; the mock runs in a thread. `process` or `thread` to force one |
| `APP_JOB_TIMEOUT_SECONDS` | `900` | a generation running longer than this is stopped and the note marked failed (process isolation only) |
| `APP_OLLAMA_URL` / `APP_OLLAMA_MODEL` / `APP_OLLAMA_TIMEOUT_SECONDS` / `APP_OLLAMA_ALLOW_REMOTE` | loopback URL / unset / `120` / `0` | Ollama connection settings; see the Ollama section above |
| `APP_MAX_PENDING_PER_CIRCLE` / `APP_MAX_PENDING_TOTAL` | `3` / `20` | notes waiting or running per care circle / in the whole app; more are refused with a clear message |
| `APP_SEED_PASSWORD` | generated | only for `dev_seed`: one password (12+ chars) for all demo accounts |

## Roles and what each can see

Permissions are decided in **one place**, `app/permissions.py` (`can()` / `decide()`), and enforced on the server: a response for a role simply does not contain what that role may not see (the tests inspect raw JSON, rendered HTML *and* the data passed to templates).

| | creator | caregiver | patient | child |
|---|---|---|---|---|
| Patient summary | yes | yes | **yes** | no |
| Caregiver checklist (tick items) | yes | yes | no | no |
| Child explanation | yes | yes | no | **yes** |
| Source note, review flags, earlier notes | yes | yes | no | no |
| Add notes | always | only if allowed by the creator | no | no |
| Delete notes | yes | no | no | no |
| Invite, revoke invitations, change roles, remove members, toggle "can add notes", delete the circle | yes | no | no | no |
| Approve a pending request | any role | **pending children only** | no | no |
| Member list | everyone, with email and permissions | active members + pending children | names and roles | **first names only** |
| Profile info page | yes | yes | yes | no |

A member can be `pending` or `revoked`; both see **only** a "waiting for approval" / "access removed" page, with nothing about the patient. The relationship label chosen when joining is display-only and never changes permissions. A child account must be approved by an active adult (creator or caregiver). Children see the patient's preferred name, never the full name.

## Patient ID is an identifier, not a credential

* Format `FCC-XXXX-XXXX` (30-character alphabet without look-alikes, drawn with `secrets`, ~39 bits). It appears in URLs and in the server's access log.
* **Possessing it grants nothing.** To join you need (a) your own account, (b) a valid, unexpired, unused, unrevoked **invitation code** issued for that profile, and (c) approval. Unknown IDs, wrong codes and codes for another circle all produce the same message, and a logged-in non-member gets the same 404 for a real circle as for a made-up ID.
* Invitation codes (`XXXX-XXXX-XXXX-XXXX`, ~78 bits) are shown **once** to the inviter, stored only as a SHA-256 digest, bound to profile and role, expire after 7 days, are single use and revocable. Joining always takes the invitation's role; there is no role field a client could edit. The optional email label is for the inviter's bookkeeping and is **not enforced** at join time.
* The UI says so on the profile-created page, the join page and the info page.

## What IS secured (each item is covered by tests in `tests/app/`)

| Control | Evidence |
|---|---|
| Passwords: `hashlib.scrypt` (N=2^15, r=8, p=1), per-user 16-byte salt, parameters stored in the hash, constant-time compare, 12-character minimum, no composition rules | `test_app_security_ids.py`, `test_app_accounts.py` |
| Server-side sessions: random 256-bit token, only its SHA-256 stored; cookie `HttpOnly`, `SameSite=Lax`, `Secure` with `APP_HTTPS=1`; absolute expiry; logout, log-out-of-all and password change invalidate sessions; login never adopts a client-chosen session id | `test_app_pages_accounts.py`, `test_app_security_review.py` |
| CSRF on **every** state-changing route (all 22 `POST` routes are enumerated from the live app and refused without a token; no other methods exist) | `test_app_security_review.py::test_no_state_changing_route_works_without_a_csrf_token` |
| Throttling of logins (per email and per IP), password-change attempts and invitation-code attempts | `test_app_accounts.py`, `test_app_circle.py` |
| Generic errors: wrong password = unknown email; unknown ID = bad code | `test_app_pages_accounts.py`, `test_app_pages_circle.py` |
| Headers: CSP without `unsafe-inline` (no inline script or style anywhere), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, HSTS only with HTTPS; API docs are off; the `Server` header is suppressed by `make app-run` | `test_app_web_api.py`, `test_app_pages_accounts.py` |
| Jinja autoescape on, never disabled; hostile names/titles/notes/labels render as text | `test_app_security_review.py`, `test_app_pages_features.py` |
| Parameterised SQL only (an AST scan of every `execute` call) | `test_app_security_review.py` |
| Passwords, tokens, codes, emails and note text are never logged (static scan of all log calls plus runtime checks) | `test_app_security_review.py`, `test_app_accounts.py` |
| Request bodies over 256 KB are rejected while streaming; notes are text only, 6,000 characters max (measured model cut-off ≈ 8,000) | `test_app_web_api.py` |
| Database file `0600`, directory `0700` | `test_app_security_review.py` |
| No hard-coded patient IDs, credentials or example IDs in the UI or code; no network libraries imported | `test_app_security_review.py` |

## What is NOT secured

Be plain about this before putting the app in front of anyone:

* **No HTTPS termination.** Run it behind a TLS-terminating reverse proxy and set `APP_HTTPS=1`; otherwise passwords and notes cross the network in clear text. Without a proxy it is only appropriate on `127.0.0.1`.
* **No distributed rate limiting.** Throttling is in memory, per process, and resets on restart; its memory use is capped (20,000 keys). Limits: 5 wrong passwords per (account, address), 25 per account across all addresses, 20 per address, 60 login attempts per address, 10 sign-ups per address, per 15 minutes. A wrong-password flood from one address no longer locks the account owner out when they log in from another address.
* **Behind a reverse proxy, set `APP_TRUSTED_PROXIES`.** Without it every user appears to come from the proxy's address and shares one set of limits. `X-Forwarded-For` is believed **only** when the connecting peer is a listed proxy (the right-most address that is not itself a listed proxy is used); from anyone else the header is ignored, so it cannot be forged to dodge a limit. Not tested against a real proxy, only with the test client.
* **No audit by a third party.** The security review was done by the author of the code, with the tests above. It is not a penetration test.
* **No encryption at rest.** Notes, generated text and accounts are stored unencrypted in the SQLite file (owner-only permissions are access control, not encryption). Backups are not handled.
* **No email delivery.** Invitation codes are shown to the inviter to pass on out of band. There is also no email verification and **no password-reset flow**: a forgotten password cannot be recovered.
* **Sign-up can reveal that an email is registered.** The message is generic, but with no email delivery this cannot be made fully enumeration-proof.
* **Sessions have an absolute lifetime only** (no idle timeout, no list of devices). There is no audit log of who viewed what.
* **Patient IDs appear in URLs and in access logs.** They are identifiers, not secrets, but treat logs as sensitive.
* **Real patient data must not be entered.** The footer says so on every page.

## Note length (F-02)

A note is limited to **6,000 characters**. The model has a 4,096-token window shared by the note, the instructions, the previous attempt (on a retry) and the answer. Measured with the real model's tokenizer on the densest realistic synthetic note (0.34 tokens per character): the first attempt stops fitting between **8,000 and 9,000** characters, and the retry prompt stops fitting between **7,000 and 8,000**; on a real, longer-prose MTSamples note the retry stops fitting between 12,000 and 14,000. The limit is the smallest of those cut-offs (8,000) minus 25%. Longer notes are refused when added with *"This note is too long for the local model. Shorten it to about 6,000 characters."* Earlier the app accepted 20,000 characters and the job then failed with a message that wrongly suggested trying again.

## Features deliberately not built

PDF or photo upload, a recent-activity feed (it would show members what others did, which needs a privacy design first) and per-role "who sees the refreshed text" checkboxes. "Read it out loud" is not built either.

## Known limitations

* **The child safety gate withholds a lot.** Measured on the 100 stored real-model child outputs (one model, Qwen2.5-3B-Instruct Q4_K_M, and one set of notes, the MTSamples subset), the gate withholds **33 of 100**: 17 too long, 13 for a frightening word, 4 for a spelled-out number word, 1 for a unit word and 1 for a medicine name. This is a measured rate on one model and one set of notes, not a general figure; a different model or different notes will give a different rate. In the end-to-end run in `audit/e2e_transcript.md` (one synthetic note) the child text was also withheld. The gate was deliberately kept this strict.
* Notes are limited to 6,000 characters (see "Note length"); generation takes about 1.5 to 2 minutes per note on an 8 GB M1 with the real model; one note is prepared at a time.
* See also "What is NOT secured" above and the gate's blind spots under "The AI-generated text".

## The AI-generated text

* One queue worker runs one job at a time (the pipeline keeps per-instance state), first in first out. Mock mode runs it in a thread; llama.cpp and Ollama use a separate process that can be stopped at the whole-job timeout. States: queued, running, done, failed. A failed job stores a fixed, safe message (never exception text). After a restart, notes left queued or running are re-queued.
* For each note the app stores the three outputs plus the pipeline's own flags (retries, fallback used, truncated, redacted doses, retention, unsupported medicines/numbers, validation errors, model id and hash). The source text lives only in the `notes` table. Creators and caregivers see these flags (with plain-language explanations); patients and children never do.
* **Lab values are not doses** (`app/pipeline_adapter.py`, `AppEntityExtractor`): a dose-like match followed by `/dL`, `/L`, `per dL` or `per liter` (for example `168 mg/dL`, `140 mEq/L`) is dropped from the app pipeline's entities, so it is never a "required dose". Dose rates such as `10 mg/kg` are kept. The research extractor is unchanged.
* **Patient summary after a pipeline fallback** (`app/outputs.py`): if the research pipeline's generic empty-output text replaced the whole draft, the patient sees *Summary unavailable. Please ask your care team to go over the visit notes with you.* and a warning, never the appended "Important details" list. If a real draft was kept but facts were appended or a dose was redacted, the draft is shown with a review warning that the patient also sees.
* **Child perspective**: the child is a separate role from the patient. For the child persona the app replaces the research prompt's "talk to the child as you" rule with a third-person rule (first name only from an explicit `Patient:` or `Name:` line, otherwise "the person"), and the child gate withholds health statements addressed to "you".
* **Dose-to-drug check** (`app/dose_check.py`): in the patient summary and caregiver checklist, each dose is attached to the nearest medicine name in the same sentence or line (within 50 characters) and compared with the doses the note gives for that medicine (extracted regimens plus numbered or bulleted medicine-list lines). A sentence or line whose dose belongs to another medicine, or names a medicine the note does not support, is removed, flagged `dose_mismatch`, and the patient and caregiver roles see *A detail was removed because it did not match the note. Please check doses with your care team.* Pronouns, unknown medicine names, frequencies and unit conversions are not checked.
* **Recovery phrases** in the patient summary and caregiver checklist remove only the offending sentence or line (flag `recovery_removed`); if nothing is left the patient sees "Summary unavailable". The child text is still withheld whole. Other unsupported serious claims still replace the whole patient or caregiver text.
* **Caregiver appendix lines** from the research retry loop ("Confirm with the care team: 30 mg (dosage)") are rendered from the extracted regimen that contains the fact ("Confirm with the care team: Prednisolone, 30 mg, daily, 4 more days."); a fact that matches no regimen is dropped.
* **Outputs saved before the current checks** (flag `gate_version` below `GATE_VERSION`) are shown with the safe child message and a review warning instead of their stored child text.
* **Ollama time budget**: one note can make up to 3 personas x 3 attempts model calls. The Ollama demo preflight refuses to start if `APP_JOB_TIMEOUT_SECONDS` is below that many per-request timeouts; the web app logs a warning. A failed job's log line names the persona and attempt that was running (fixed names and a count, never note text).
* **Known limitation**: the research retry loop counts any medication word the note does not contain as invented, including an explanation such as "a hormone called insulin", and then replaces the draft with its generic text. `app/medication_check.py` is a context-aware reference check, but the pipeline cannot use it without a change in `src/`.
* Every output view clearly states that generated text may be inaccurate and is not a substitute for professional medical advice. Check doses and instructions with the care team.
* **Child safety checks** (`app/safety.py`, `app/clinical_safety.py`): text is replaced with *The note has information about someone's health. Their care team can explain what it means. You can ask a trusted adult if you have questions.* if it contains a digit, dose word, unit, extracted medication name, frightening term, unsupported serious diagnosis/procedure/event, unsupported recovery claim, child-as-patient claim, medication-change advice, more than 8 sentences, or more than 120 words. Phrase checks cover selected terms only and can miss paraphrases, implied claims, negation scope, or incorrect details that use different words. They do not guarantee accuracy; the generated text still needs review by the care team.

**What the gate does not catch** (checked by a run and pinned by a test): brand names it has never seen ("Amoxil" when the note says amoxicillin, "Tylenol" when the extractor found no such medicine); misspellings of a drug name ("amoxicilin"); paraphrased fears that use none of the listed words ("you will not get better"); and a chain of short clauses joined only by commas, which counts as one sentence. It is a narrow, rule-based guard, not a content-safety system, and the patient and caregiver outputs are not gated at all.

## Design system

`static/css/tokens.css` holds every colour, size and font (cream `#FAF7F2`, white surfaces, pink `#F9E6E7`, lavender `#EEE9F8`, light green `#E2EDE3`, deep rose `#8E3D4E` primary). Child output uses larger type on the pink tint; caregiver lavender; patient green. `.venv/bin/python -m app.tools.contrast` checks 44 text/background and control/focus pairs against WCAG AA (all pass, and a test runs it). Fonts: Fraunces and Nunito Sans are named first but **not bundled** (nothing is fetched at runtime), so most devices show the system fallback fonts; drop `.woff2` files into `static/fonts` and add `@font-face` rules to use them.

Accessibility is checked **without a browser**: heading order, accessible names, labels, unique ids, CSRF fields on forms, titles, 44px targets, no removed focus outlines, no CSS width that could force horizontal scroll at 360px. The pages work without JavaScript (stepper, tabs, ticking, invitations are plain forms and links); JavaScript only adds the copy button and the automatic refresh while a note is being prepared. **Not verified:** real rendering at 360/768/1280px, how focus looks, and screen-reader behaviour (Playwright is not installed here, so no screenshots were taken).

## Layout

```
app/
  config.py  context.py  errors.py        settings from the environment, clock + throttle, safe errors
  security.py  ids.py  csrf.py  throttle.py   scrypt + tokens, patient ID / invite code, CSRF tokens, throttle
  db.py  migrations.py                    SQLite connection (0600), transactions, schema v1-v2
  permissions.py                          can() / decide(): the single source of truth for access
  accounts.py  circle.py                  accounts + sessions; profiles, memberships, invitations
  notes.py  outputs.py  safety.py         notes, role-filtered outputs + checklist, child gate
  jobs.py  pipeline_adapter.py            the single-worker queue; builds src.pipeline.FamilyCarePipeline
  dev_seed.py                             SYNTHETIC demo data only, on an empty database
  web/                                    main.py (factory), deps.py, middleware.py, render.py, present.py,
                                          api.py (JSON), pages*.py (HTML)
  templates/  static/  tools/contrast.py
tests/app/                                the app's tests (the research suite is untouched)
```

## Routes

| Method | Path |
|---|---|
| GET | `/` |
| GET, POST | `/signup`, `/login`, `/join`, `/profiles/new` |
| POST | `/logout` |
| GET | `/profiles`, `/settings`, `/unauthorized` |
| POST | `/settings/password`, `/settings/logout-all`, `/settings/delete` |
| GET | `/p/{id}` (dashboard), `/p/{id}/created`, `/p/{id}/info`, `/p/{id}/circle`, `/p/{id}/summaries`, `/p/{id}/notes` |
| POST | `/p/{id}/circle/invite`, `/p/{id}/circle/pause`, `/p/{id}/circle/invitations/{n}/revoke`, `/p/{id}/circle/members/{n}/approve|revoke|role|notes`, `/p/{id}/delete`, `/p/{id}/notes`, `/p/{id}/notes/{n}/delete`, `/p/{id}/checklist/{note}/{item}` |
| GET | `/api/p/{id}/outputs|status|history|notes|circle`, `/api/p/{id}/notes/{n}/outputs|source` |
| POST | `/api/p/{id}/notes`, `/api/p/{id}/notes/{n}/delete`, `/api/p/{id}/checklist/{note}/{item}` |

There is no separate `/checklist` page: the checklist is a tab on the summaries page, so a duplicate page would add nothing.

## Tests

```bash
make app-test                       # tests/app only
.venv/bin/python -m pytest -q       # everything: the research suite (235) + the app suite
```

Tests use the framework's test client (no browser), a temporary database and a tiny scrypt cost. One test builds the real `FamilyCarePipeline` on the mock backend. The real `llama_cpp` backend is **not** exercised by the automated tests (it needs the 2 GB model); it was checked once by hand as described above.
