# Family Care Circle — multi-user web app (`app/`)

> **Prototype. Not for real patient data.** Research prototype. Not medical advice. Check doses and instructions with the care team.

A self-hosted web application in which a **profile creator** makes a patient profile, gets a patient ID, and invites family members. Each member sees only the AI-generated output suited to their role: a **patient summary**, a **caregiver checklist**, and a **child explanation**. The text is produced by the research pipeline in `src/` (called, never modified), running locally. No outbound network calls and no commercial LLM API are made at runtime.

Stack: FastAPI + Uvicorn, SQLite (stdlib `sqlite3`), Jinja2 server-rendered templates, static CSS, a small vanilla-JavaScript file. No Node toolchain.

## Run it

```bash
.venv/bin/python -m pip install -r requirements-app.txt     # fastapi, uvicorn, jinja2, python-multipart, httpx (tests)
make app-run                                                # http://127.0.0.1:8000  (mock backend, no model needed)
make app-seed                                               # optional: SYNTHETIC demo accounts, on an EMPTY database
make app-test                                               # the app's own tests
```

`make` calls `python`, so activate the project's environment first (`source .venv/bin/activate`) or put `.venv/bin` on your `PATH`.

**With the real model** (the local Qwen2.5-3B GGUF configured in `config.yaml`, via `llama-cpp-python` as described in the main README):

```bash
APP_BACKEND=llama_cpp make app-run
```

The model is loaded lazily by the single worker thread when the first note is processed. In the one real-model run made while building this (one synthetic note from `data/raw`, scripted through `python -m app.dev_seed --notes 1`), generation took **81 s**, and the stored model hash was identical to the one recorded in the research runs. Pages show a "being prepared" state and update on their own.

With the **mock** backend the child explanation is always withheld by the safety gate (the mock writes 9 sentences and the limit is 8). That is expected, not a bug; use the real model to see child text.

### Configuration (environment variables; nothing secret lives in the repo)

| Variable | Default | Meaning |
|---|---|---|
| `APP_BACKEND` | `mock` | `mock` or `llama_cpp` |
| `APP_DB_PATH` | `app/var/familycare.sqlite3` | SQLite file (created `0600`, directory `0700`; `app/var/` is git-ignored) |
| `APP_HTTPS` | `0` | `1` marks cookies `Secure` and sends HSTS. The app does **not** terminate TLS itself |
| `APP_SECRET_KEY` | random per process | key for CSRF tokens; if unset, anonymous (login/signup) tokens stop working after a restart |
| `APP_SESSION_TTL_HOURS` | `168` | absolute session lifetime |
| `APP_INVITE_TTL_DAYS` | `7` | invitation lifetime |
| `APP_TRUSTED_PROXIES` | none | comma-separated **exact addresses** of reverse proxies whose `X-Forwarded-For` header may be believed (no CIDR ranges). Leave empty unless you run behind a proxy; see "What is NOT secured" |
| `APP_JOB_ISOLATION` | `auto` | `auto` = the real model runs in a separate process that is killed on timeout; the mock runs in a thread. `process` or `thread` to force one |
| `APP_JOB_TIMEOUT_SECONDS` | `900` | a generation running longer than this is stopped and the note marked failed (process isolation only) |
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

* One **worker thread** runs one job at a time (the pipeline keeps per-instance state), first in first out, with the pipeline built once per process. States: queued, running, done, failed. A failed job stores a fixed, safe message (never exception text). After a restart, notes left queued or running are re-queued.
* For each note the app stores the three outputs plus the pipeline's own flags (retries, fallback used, truncated, redacted doses, retention, unsupported medicines/numbers, validation errors, model id and hash). The source text lives only in the `notes` table. Creators and caregivers see these flags (with plain-language explanations); patients and children never do.
* Every output view shows: *Research prototype. Not medical advice. Check doses and instructions with the care team.*
* **Child safety gate** (`app/safety.py`): before a child explanation is stored as displayable it is rejected, and the fixed message *A grown-up will help explain what the doctor said.* is shown instead, if it contains **a digit of any kind** (including circled, superscript and fraction forms), **a spelled-out number or dose word** (zero to ninety-nine, hundred, thousand, dozen, half, once, twice, thrice), **a unit word** (mg, mcg, ml, milligram, tablet, capsule, pill, unit and similar), **a medication name extracted from that note** (any case, plurals and possessives included, invisible zero-width characters ignored), **a frightening word** (die, death, dying, cancer, tumour/tumor, fatal, terminal, surgery, hospital stay), **more than 8 sentences** (sentences end at `. ! ? … ; :` or a line break), or **more than 120 words** (so a long run-on with no punctuation cannot count as one sentence). The limit of 8 matches the pipeline's own prompt of "5 to 8 sentences"; the first draft of the spec said 6. **At 6 the gate withheld 65 of the 100 stored real-model child outputs; at 8 it withheld 17** (measured before the F-14 rules were added), which is why 8 was kept. The reason is recorded in the flags, visible to creators and caregivers only, and the rejected text is not stored.

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
