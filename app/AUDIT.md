# Audit of the Family Care Circle web app (`app/`)

**Phase A was a read-only audit; Phase B (below) fixed the findings you approved.** The Phase A text underneath is left as it was written, so each row still shows the evidence at the time. The status of every finding is in the next table.

Audited commit state: the working tree after the build (718 tests passing: 235 research + 483 app). Date of audit: 2026-10-25.

## Phase B: status of every finding

Each fix was written test-first (the new test failed first), then the whole `tests/app` suite was run. "Verified by" names the test or run. Nothing is claimed fixed that a test or run did not show.

| ID | Status | What was done | Verified by |
|---|---|---|---|
| F-01 | **Fixed** | The real model runs in a separate process (`app/worker_process.py`); a generation over `APP_JOB_TIMEOUT_SECONDS` (default 900) is killed and the note marked failed with a clear message; the queue moves on. The mock backend stays in a thread. A worker process exits if its parent dies | `test_app_jobs_isolation.py` (hang killed and next note served; child process gone; orphan check is belt-and-braces, see its docstring) |
| F-02 | **Fixed** | Limit lowered 20,000 to **6,000** characters, from a measured cut-off (see README "Note length"). Notes over it are refused up front with *"This note is too long for the local model. Shorten it to about 6,000 characters."*; a context-overflow failure no longer says "try adding it again" | `test_app_notes_jobs.py`, `test_app_jobs_isolation.py`; real model: `test_app_realmodel_limits.py` (result in the final report) |
| F-03 | **Fixed** | At most 3 waiting/running notes per care circle and 20 in total (`APP_MAX_PENDING_*`); the 429 page explains why | `test_app_queue_caps.py` |
| F-04 | **Fixed** | Wrong-password limits are per (account, address) 5, per account across addresses 25, per address 20. The owner can log in from another address while someone else is being throttled | `test_app_throttling.py`, `test_app_accounts.py` |
| F-05 | **Fixed (not tested against a real proxy)** | `APP_TRUSTED_PROXIES`; `X-Forwarded-For` only believed from a listed proxy, right-most untrusted hop, malformed gives unknown | `test_app_throttling.py` (parametrised cases, end-to-end through the test client) |
| F-06 | **Fixed** | Throttle memory is bounded (20,000 keys, idle sweep, actively attacked keys are not evictable by junk) | `test_app_throttling.py` |
| F-07 | **Fixed** | 10 sign-up attempts and 60 login attempts per address per 15 minutes | `test_app_throttling.py` |
| F-08 | **Fixed** | Expired sessions are purged on every successful login | `test_app_accounts.py` |
| F-09 | **Fixed** | Changing the password issues a new session token and ends all others; the page redirects so the new cookie is used | `test_app_accounts.py`, `test_app_pages_features.py` |
| F-10 | **Kept** (your decision) | Expired / used codes keep their specific messages | n/a |
| F-11 | **Fixed (rename only)** | "email label" is now "Note for yourself" in UI, code, tests and the database (migration 3); still not enforced | `test_app_circle.py` |
| F-12 | **Fixed** | Names with control, bidi-override, zero-width or other invisible format characters are refused; members who share a name (case/spacing-insensitive) are flagged to the people who can see both | `test_app_circle.py` |
| F-13 | **Fixed** | Invitation notes reject control characters | `test_app_circle.py` |
| F-14 | **Fixed (scoped)** | Child gate extended as you specified (see README for the list and for what it still cannot catch). Of the 22 crafted outputs, undesired ones that passed went from **14 to 5**: 4 documented gaps plus the 7-sentence case, which is allowed because the limit is 8 (F-15). On the 100 stored real-model child outputs the gate now withholds **33** (it was 17): 17 too long, 13 for a frightening word (surgery 11, cancer 5, tumor 1 in notes about those things), 4 number words, 1 unit word, 1 medicine name | `test_app_safety.py`, `test_app_docs.py` (gaps pinned), re-run of the 22 cases and the 100 outputs |
| F-15 | **Kept at 8** | README now records that a limit of 6 withheld 65 of 100 real outputs | `test_app_docs.py` |
| F-16 | **Kept** | n/a | n/a |
| F-17 | **Fixed** | Every text size is at least 1rem except status chips (0.875rem, always paired with an icon or colour) | `test_app_visual_rules.py` (with a positive control) |
| F-18 | **Fixed** | Primary button first in the DOM, Back shown first by CSS | `test_app_visual_rules.py`, browser keyboard test |
| F-19 | **Fixed** | The four inline links got a 44px target (`.tap-link`) | `test_app_visual_rules.py`, browser test (measured height) |
| F-20 | **Verified in a real browser** | 360px menu fits (no sideways scroll); **Escape and outside click did NOT close the menu, now fixed in `app.js`**; copy button says "Copied" and the clipboard holds the code; polling reloads the page when a note finishes; tabs work with Enter; keyboard-only stepper moves forward with Enter | `test_app_browser.py` (Chromium via Playwright) |
| F-21 | **Kept** | Dead code left, as decided (`purge_expired_sessions` is now used) | n/a |
| F-22 | **Kept** | Documented | n/a |
| F-23 | **Done** | `pip-audit` run, see the final report: no known vulnerabilities in the pinned app dependencies; one advisory in a transitive test-only package (certifi) | run |
| F-24 | **Kept** | n/a | n/a |

Design decisions: PDF/photo upload, activity feed and per-role refresh checkboxes were **dropped** (never built; documented in README). Rose `#8E3D4E` kept. Optional items: **"Pause new invitations" done** (creator only; a paused circle refuses codes with the generic message and creates none; `test_app_circle.py`, `test_app_pages_features.py`); **"Bigger words" done** (client-side, localStorage; `test_app_visual_rules.py`, `test_app_browser.py`). "Read it out loud" **not done**.

Regression tests added from the audit scripts: authorization matrix and leak hunt (`test_app_audit_regression.py`, slow), patient-ID indistinguishability and the invitation race (same file, the race test was mutation-checked), and the rest already live in `test_app_security_review.py`, `test_app_security_ids.py`, `test_app_safety.py`, `test_app_notes_jobs.py` and `test_app_jobs_isolation.py`.

Screenshots at 360, 768 and 1280px are in `app/audit/screenshots/` (30 views, 90 files).

## How this audit was done, and what it cannot show

Every number below comes from a script that **called the real app** (FastAPI test client, real `FamilyCarePipeline` on the mock backend, throw-away SQLite databases), or from a real server/process run. The scripts live **outside the repository** in the session scratchpad (`.../scratchpad/audit/a1_matrix.py`, `a3_id_invites.py`, `a5_sessions_inject.py`, `a7_gate.py`, `a8_jobs.py`, `a9_real_long.py`); say so if you want them added to `tests/app/` as regression tests in Phase B.

* The leak detector was validated with a **positive control**: pointed at the creator's pages with the child's forbidden-string list, it found 10, 7, 7 and 10 forbidden strings on four pages. (A first run produced false positives on `/settings` because it counted a user's *own* name and email; the detector, not the app, was corrected.)
* **Not done / not possible here:** no browser was available (Playwright is not installed), so there are **no screenshots at 360/768/1280px**, no real keyboard or screen-reader testing, and the JavaScript (copy button, auto-refresh) was never executed in a browser. **No design canvas exists in the repository** (searched; the five design differences below are taken from your message, not from the canvas). No dependency vulnerability scan was run. The real model was used once for the over-long-note test and once in the build.
* Severity scale: **High** = real-data exposure or privilege escalation; **Medium** = availability, or a gap against your stated requirement; **Low** = hardening or polish; **Info** = no action needed or only a note.

## Headline

* **No High findings.** No role saw anything it should not, in any of 43 route/method combinations across 9 kinds of visitor, in HTML, JSON, error pages, redirects, headers, cookies, template contexts or logs. No unauthorized state change occurred. Writing to the database from a GET never happened.
* **7 Medium findings** (F-01, F-02, F-03, F-04, F-05, F-06, F-14), mostly about **availability and operations**: a hung generation blocks every circle forever (F-01); notes the app accepts cannot be processed by the real model (F-02); one circle can monopolise the single worker (F-03); three throttling weaknesses (F-04, F-05, F-06); and the child safety gate has real, documented gaps (F-14). The rest are Low, Info or Unverified. **Totals: 0 High, 7 Medium, 10 Low, 6 Info, 1 Unverified (24 findings).**

## Findings

| ID | Severity | Area | How reproduced | Evidence (from this audit) | Proposed fix |
|---|---|---|---|---|---|
| F-01 | **Medium** | Jobs | A generator that never returns (A8.5), 2 notes queued | After 3 s: `[(1,'running'), (2,'queued')]`. `grep timeout app/jobs.py` lists only `queue.get(timeout=0.2)`, `stop()` and `wait_idle()`; nothing limits how long a job may run. A restart is handled (A8.3), a **hang is not**. Because the worker is global, one hung job stalls every care circle | Run generation in a killable subprocess with a time limit, or at minimum a sweeper that marks notes `running` longer than N minutes as `failed` and shows an "operator action needed" state. Needs your decision (subprocess = bigger change) |
| F-02 | **Medium** | Notes vs real model | 20,000-char synthetic note with `APP_BACKEND=llama_cpp` (A9) | App accepts it; **job failed after 10 s** with the message *"We could not prepare this note. Please try adding it again."* Token counts: 10,000 chars = 2,964 tokens, **15,000 chars = 4,438 tokens, 20,000 = 5,923**, against a 4,096-token window. Retrying can never succeed, so the message is misleading. The exact cut-off (somewhere between ~10k and 15k characters) was **not measured** | Lower `max_note_chars` to a limit proven to work (conflicts with the spec's 20,000), or check the token budget before queuing and say "this note is too long for the model (max about N characters)". Needs your decision on the number |
| F-03 | **Medium** | Jobs | A permitted caregiver adds 300 notes (A8.6) | All 300 accepted in 0.0 s, queue length 300 = about 6.7 hours of real-model work (80 s each). One global FIFO queue serves all circles, so one circle can starve the rest | Cap queued notes per circle (and per user), reject with a clear message; optionally round-robin between circles |
| F-04 | **Medium** | Auth | 5 wrong passwords for a known email from anywhere, then the real owner logs in with the right password (A4) | Owner gets **429 "Too many attempts"**. Anyone who knows an email can keep an account locked out indefinitely (documented as a trade-off, but it is a real denial of service) | Key lockout on (email, IP) instead of email alone, add backoff, never block a correct password from an already-trusted session/device |
| F-05 | **Medium** | Deployment | 20 failed logins from one IP, then a different legitimate user from the same IP (A4) | 429 for the legitimate user. The throttle uses the socket peer address; **behind a reverse proxy every user shares one IP**, so 20 failures by anyone lock out everyone. Likewise 60 wrong join guesses from one IP blocked a legitimate join | Add an explicit trusted-proxy setting (read `X-Forwarded-For` only from a configured proxy address); raise or drop the per-IP limit when no real client IP is known |
| F-06 | **Medium** | Auth / memory | 20,000 failed logins with distinct emails and IPs (A5) | `ctx.throttle._events` holds **40,000 keys**; entries are pruned only when the same key is seen again, so an attacker can grow process memory without bound | Periodic sweep of idle keys and a hard cap on tracked keys |
| F-07 | Low | Auth | Production cost measured (A5) | Each login/sign-up attempt costs **63 ms of CPU** (about 16 per second per core) and a worker thread; sign-up has **no throttle at all**, so an unauthenticated client can burn CPU and create unlimited accounts. (Login timing parity is good: unknown-email path 62 ms vs 63 ms, difference 0.5 ms.) | Per-IP rate limit on sign-up and login, or a small proof-of-work/delay on repeated attempts |
| F-08 | Low | Sessions | 500 long-expired session rows, then 50 requests (A5) | All 500 remain. `purge_expired_sessions()` exists in `app/accounts.py` but **is never called** (0 references). Rows accumulate (hashed tokens only) | Call it periodically (for example at login and in the worker's idle loop) |
| F-09 | Low | Sessions | Change password with two devices logged in (A5) | Other device is logged out (good) and this session stays valid, but the **session token is not rotated** (`session token rotated: False`) and the CSRF token (derived from it) is unchanged | Issue a fresh session cookie after a password change |
| F-10 | Low | Invitations / IDs | Join with a correct ID and an expired or used code (A3) | Unknown ID, wrong code, other-circle code, revoked code and malformed input all give **one identical message** (verified). But an **expired** code says *"This invitation has expired"* and a used one *"already been used"*, so those cases *can* be told apart, contrary to your audit rule 3. They are reachable **only** by someone presenting the correct ID *and* the exact 78-bit code, so nothing about IDs or circles leaks to a guesser. The build prompt itself lists "expired" and "already used" as join states | Decision needed: keep (my recommendation, matches the build prompt, user-friendly) or merge into the generic message |
| F-11 | Low | Invitations | Code labelled `grandma@example.org` redeemed by `someone-else@audit.example` (A4) | Join accepted (303). The label is display-only, as documented in the UI, but the build prompt says codes are "bound to profile, role and optional email label". Anyone who obtains a code can use it | Decision needed: enforce the label when present (stricter, may block legitimate use) or keep display-only and rename it "note" |
| F-12 | Low | Input handling | Sign-up with names containing U+202E (bidi override), zero-width characters, a Cyrillic look-alike, emoji (A6) | All accepted verbatim and stored. Display names are **not unique** (a second account with the creator's exact name was allowed). Caregivers approving a pending child see names only, so a look-alike name can impersonate an existing member | Reject or strip format/bidi characters, show the email to approvers, or flag duplicate names in the member list |
| F-13 | Low | Input handling | Invitation label containing NUL (A6) | Accepted (200); other control characters except newline are not rejected for this field (names and notes do reject them) | Reuse the existing control-character check |
| F-14 | **Medium** | Child safety gate | 22 crafted outputs through `build_output` (A7) | **14 undesirable outputs pass**: spelled-out numbers ("five milligrams", "ten", "a dozen", "twice a day"), circled/superscript/fraction digits (`①`, `²`, `½`), brand name (`Amoxil`), plural (`amoxicillins`), misspelling (`amoxicilin`), a zero-width split (`amoxi​cillin`), a medicine the extractor did not pick up (`Tylenol`), frightening wording with no digit or name, a **400-word run-on with no punctuation (counts as 1 sentence)**, and a comma-only chain. Caught: digits (incl. full-width and Arabic-Indic), exact medicine names (any case), more than 8 sentences. The rejected text is not stored (verified) | Decision needed. Options: keep the narrow spec'd gate and document it (current); add a number-word list, a character cap, Unicode-aware digit categories (`No`), fuzzy/brand-name matching, and a simple allow-list of words suitable for children |
| F-15 | Info | Child safety gate | Compared limits on the 100 stored real-model child outputs (A7) | Your audit text says **more than 6 sentences**; the build uses **8** (your Stage-0 decision, matching the prompt's "5 to 8 sentences"). At 6 the gate withholds **65 of 100** real outputs; at 8 it withholds **17**. 0 of 100 contain a digit | Please confirm 8, or choose another number |
| F-16 | Info | Mock backend | Run with `APP_BACKEND=mock` | The mock writes 9 sentences, so the child view **always** shows the safe message. Expected, documented | None (use the real model, or I can make the seeder note this) |
| F-17 | Low | Visual / spec | grep of `base.css` | Spec says "Body 16px minimum". Body text is 16px, but secondary text is smaller: **disclaimer 0.95rem (15.2px)**, hints 0.95rem, footer 0.9rem, chips 0.875rem, stepper labels 0.85rem, member email 0.9rem. The mandatory disclaimer is among them | Raise the disclaimer, hints, footer and meta text to at least 1rem (chips are arguably fine) |
| F-18 | Low | Keyboard | Parsed the rendered stepper (A11) | On steps 2-4 the **first submit button in the form is "Back"**, so pressing Enter in a text field would go back instead of forward. **Latent:** those steps have no text `<input>` (only a textarea, a select, or nothing), so I found no way to trigger it today | Put the primary button first in the DOM (reorder visually with CSS) so a future text field cannot hit Back |
| F-19 | Low | Touch targets | Inspection | Buttons, tabs, nav links and inputs meet 44px. **Inline text links** ("Refresh now", "Open the checklist", "Read the full summary", "Go back to the latest") do not; WCAG exempts inline links but the spec says 44px minimum | Add vertical padding or turn the important ones into buttons |
| F-20 | Unverified | Layout / keyboard | Cannot run a browser | At 360px the circle menu (`.menu-panel`, `position:absolute; right:0; min-width:15rem`) might extend off-screen to the left; the native `<details>` menu closes neither on Esc nor on outside click. Copy-button confirmation and auto-refresh JavaScript were never executed in a browser | Install Playwright (needs your approval) and test at 360/768/1280px with keyboard-only navigation |
| F-21 | Info | Dead code | AST/grep scan | Never used: `accounts.purge_expired_sessions` (see F-08), `deps.csrf_token_for`, the `card` template macro | Remove or wire up |
| F-22 | Info | Operations | Real server run | `Server: uvicorn` header is hidden only when started with `make app-run` (`--no-server-header`); the access log records client IPs and URLs containing patient IDs | Document; keep logs access-controlled |
| F-23 | Info | Supply chain | `requirements-app.txt` | FastAPI is pinned to 0.141.0 (to avoid an unapproved package). It is not the latest release and **no vulnerability scan was run** | Run `pip-audit` (needs approval to install) |
| F-24 | Info | Spec | Route table | `/logout` is POST-only (`GET /logout` is 405), which is safer than a GET logout but differs from "a `/logout` route" in a literal reading | None |

(Items checked and found **clean**, with evidence, are listed in the sections below: authorization, leaks, patient ID, forged roles, reuse and races, sessions and CSRF, injection, restart recovery, deletion during a job.)

## 1. Authorization matrix (actual responses)

Produced by `a1_matrix.py`: a fresh circle with a creator, two caregivers (one allowed to add notes, one not), a patient, a child, a **pending** member, a **revoked** member, a **logged-in stranger** and an **anonymous** visitor, one finished note. Every GET cell used one shared database; **every POST cell used its own fresh database** so actions could not interfere. Cell format: HTTP status; `303→/x` is a redirect; `Δ` = the database changed; `⚠LEAK` would mean a forbidden string appeared (none did). 200 on a *POST* by pending/revoked members is the "waiting for approval / access removed" status page (nothing changed).

**GET routes (status; Δ = database changed; ⚠LEAK = a forbidden string was found)**

| route | anonymous | stranger | pending | revoked | child | patient | caregiver_no_notes | caregiver | creator |
|---|---|---|---|---|---|---|---|---|---|
| `/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/signup` | 200 | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles |
| `/login` | 200 | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles | 303→/profiles |
| `/profiles` | 303→/login | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/profiles/new` | 303→/login?next=/profiles/new | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/join` | 303→/login?next=/join | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/settings` | 303→/login | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/unauthorized` | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| `/p/{id}` | 303→/login | 404 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/created` | 303→/login | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 200 |
| `/p/{id}/info` | 303→/login | 404 | 200 | 200 | 403 | 200 | 200 | 200 | 200 |
| `/p/{id}/circle` | 303→/login | 404 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/summaries` | 303→/login | 404 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/summaries?tab=caregiver` | 303→/login | 404 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/summaries?tab=child` | 303→/login | 404 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/summaries?note={n}` | 303→/login | 404 | 200 | 200 | 403 | 403 | 200 | 200 | 200 |
| `/p/{id}/notes` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 200 | 200 |
| `/api/p/{id}/outputs` | 401 | 404 | 403 | 403 | 200 | 200 | 200 | 200 | 200 |
| `/api/p/{id}/status` | 401 | 404 | 403 | 403 | 200 | 200 | 200 | 200 | 200 |
| `/api/p/{id}/history` | 401 | 404 | 403 | 403 | 403 | 403 | 200 | 200 | 200 |
| `/api/p/{id}/notes` | 401 | 404 | 403 | 403 | 403 | 403 | 200 | 200 | 200 |
| `/api/p/{id}/circle` | 401 | 404 | 403 | 403 | 200 | 200 | 200 | 200 | 200 |
| `/api/p/{id}/notes/{n}/outputs` | 401 | 404 | 403 | 403 | 403 | 403 | 200 | 200 | 200 |
| `/api/p/{id}/notes/{n}/source` | 401 | 404 | 403 | 403 | 403 | 403 | 200 | 200 | 200 |

**POST routes (valid CSRF token; each cell is a fresh database)**

| route | anonymous | stranger | pending | revoked | child | patient | caregiver_no_notes | caregiver | creator |
|---|---|---|---|---|---|---|---|---|---|
| `/logout` | 303→/ | 303→/ | 303→/ | 303→/ | 303→/ | 303→/ | 303→/ | 303→/ | 303→/ |
| `/profiles/new` | 303→/login?next=/profiles/new | 303→/p/FCC-ZYDV-X942/created Δ | 303→/p/FCC-RWF4-P4QH/created Δ | 303→/p/FCC-JYDG-HHJM/created Δ | 303→/p/FCC-AYCW-B9FP/created Δ | 303→/p/FCC-QNHG-8CBE/created Δ | 303→/p/FCC-BKPM-9KHD/created Δ | 303→/p/FCC-MHXP-3DJ5/created Δ | 303→/p/FCC-S453-MBGH/created Δ |
| `/join` | 303→/login?next=/join | 303→/p/FCC-G79V-XGD5 Δ | 200 | 403 | 200 | 200 | 200 | 200 | 200 |
| `/p/{id}/circle/invite` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 200 Δ |
| `/p/{id}/circle/invitations/8/revoke` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 200 Δ |
| `/p/{id}/circle/members/7/approve` | 303→/login | 404 | 200 | 200 | 403 | 403 | 200 Δ | 200 Δ | 200 Δ |
| `/p/{id}/circle/members/3/revoke` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 200 Δ |
| `/p/{id}/circle/members/3/role` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 200 Δ |
| `/p/{id}/circle/members/3/notes` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 200 Δ |
| `/p/{id}/delete` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 303→/profiles Δ |
| `/p/{id}/notes` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 303→/p/FCC-TH76-DG3A/notes?added=1 Δ | 303→/p/FCC-V4GQ-T63H/notes?added=1 Δ |
| `/p/{id}/notes/1/delete` | 303→/login | 404 | 200 | 200 | 403 | 403 | 403 | 403 | 303→/p/FCC-33NJ-DS3H/notes Δ |
| `/p/{id}/checklist/1/0` | 303→/login | 404 | 200 | 200 | 403 | 403 | 303→/p/FCC-7Y4V-QYDX/summaries?tab=caregiver#item-0 Δ | 303→/p/FCC-J8Q9-T4MV/summaries?tab=caregiver#item-0 Δ | 303→/p/FCC-SNQH-Q7G3/summaries?tab=caregiver#item-0 Δ |
| `/settings/password` | 303→/login | 401 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| `/settings/logout-all` | 303→/login | 303→/login | 303→/login | 303→/login | 303→/login | 303→/login | 303→/login | 303→/login | 303→/login |
| `/settings/delete` | 303→/login | 401 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| `/api/p/{id}/notes` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 201 Δ | 201 Δ |
| `/api/p/{id}/notes/1/delete` | 401 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 200 Δ |
| `/api/p/{id}/checklist/1/0` | 401 | 404 | 403 | 403 | 403 | 403 | 200 Δ | 200 Δ | 200 Δ |

**Result.** GET routes: 24, POST routes: 19 (sign-up and login are tested separately in section 5). GET requests changed the database: **no**. Responses containing forbidden strings: **0**. Template contexts containing forbidden data for child/patient/pending/revoked/stranger/anonymous: **0**. State changes by an actor not allowed to make them: **0**. Forbidden strings in 8,826 captured log lines (note text, medicine names, passwords, emails, request bodies): **0**.

Reading the matrix:

* A **logged-in stranger gets 404 on every circle URL**, identical to a made-up ID (verified byte-for-byte, section 3). **Pending and revoked** members get 200 with only a status page on pages, and 403 `membership_pending` / `membership_revoked` on the API.
* **Caregiver without notes permission:** `/notes` 403, API note POST 403, but may tick checklist items and approve pending *children* (`approve` Δ), as decided. **Child and patient:** 403 on every adult page and endpoint.
* Only the **creator** changed state on invite, revoke, role, notes-toggle, delete-circle and note-delete. (A pending-child approval by a caregiver is the one allowed exception.)

## 2. Leak hunt

Searched every response (body, headers, `Set-Cookie`, redirect targets), every template context and 8,826 log lines for: the source note text (`ZEBRA-SOURCE-TOKEN`), note title, medicine names (Amoxicillin, Ibuprofen), doses (500 mg, 200 mg), the patient's full name, other members' names and emails, flag/retention text, and the other roles' outputs. Result: **none for child, patient, pending, revoked, stranger or anonymous**, other than each user's *own* name and email on `/settings`. Template contexts for the low-privilege roles never contain the keys `flags`, `source`, `caregiver_checklist` or `patient_summary`.

## 3. Patient ID

* A **real ID behaves exactly like a fake ID** for anonymous and for logged-in non-member visitors on every page and API (status and body identical after removing CSRF tokens): *"where a REAL id behaves differently from a FAKE id … none"*.
* **URLs containing the real ID that return 200 for a non-member: none.**
* Five join failures return **one identical message** ("That ID and code do not match…"): unknown ID, known ID with wrong code, malformed input, a valid code of another circle, a revoked code.
* **Not identical:** an expired code (and a used code) says so (F-10), only after a correct ID and exact code.
* Timing (400 calls each, median): unknown ID + wrong code 10 µs, known ID + wrong code 10 µs, wrong ID + *valid* code 16 µs. The extra 6 µs is not measurable over a network.

## 4. Invitations (A4)

| Attack | Result |
|---|---|
| Reuse a code | Second user: 400 "already been used"; only one membership |
| Expiry | 6 days 23 h 59 m 59 s old: accepted; after 7 days: "expired" |
| Code for a different circle with this circle's ID | Generic "do not match"; nothing created |
| Edit the request to join with another role (`role=creator`, `status=active`, `can_add_notes=1`, also as query string) | Ignored; membership is exactly the invitation's role, `pending`, `can_add_notes=0` |
| Revoked code | Generic "do not match" |
| Brute force | 5 wrong guesses per user then 429; 20 per IP. **60 wrong guesses across 40 throw-away accounts from one IP then locked a legitimate user** (F-05); account creation is unthrottled (F-07). Guessing is hopeless anyway (78-bit codes) |
| Code issued for a different email label | Redeemed by another email (F-11) |
| Joining twice | Pending user with a second code: "waiting for approval"; role unchanged |
| Race: 12 users redeem one code at the same instant | **Exactly 1 joined, 11 got "already used"; 1 membership created** |
| Plaintext codes in the database | **No** (only SHA-256 digests) |

## 5. Sessions and CSRF (A5)

* **Fixation:** a planted session cookie is replaced on login and the planted value is worthless afterwards.
* **Logout:** replaying the old cookie → 303 (rejected). **Log out of all sessions:** all 3 devices → 303.
* **Cookie flags (http):** `fcc_session=<token>; HttpOnly; Max-Age=604800; Path=/; SameSite=lax` (and `Secure` with `APP_HTTPS=1`, tested).
* **CSRF:** all 21 POST routes refuse a request without a token (also enforced by `test_no_state_changing_route_works_without_a_csrf_token`); login/sign-up refuse a missing token and a token from a different cookie (403). `PUT`, `PATCH`, `DELETE` on real routes → **405**; `GET /logout` → 405.
* **Password change:** other devices logged out, this one stays (F-09: token not rotated).
* **Odd values in the `back` redirect parameter** (CR, CRLF, NUL): no header injection; control characters are percent-encoded or rejected.

## 6. Injection (A6)

Hostile values: `<script>`, `"><img onerror>`, an attribute breakout, Jinja syntax (`{{ 7*7 }}`, `{% for %}`, `{{ config }}`, `__mro__`), SQL fragments, HTML entities, bidi override, zero-width, Cyrillic homoglyph, a 300-combining-mark flood, emoji, newline, NUL, and 5,000-character strings, submitted through sign-up names, patient name / preferred name / care notes, note titles and text, invitation labels, query parameters (`tab`, `note`, `next`) and the URL path.

* **No 500 responses.** Overlong, NUL, newline and combining-flood values were rejected with a message; the others stored verbatim and **escaped on output**.
* **Raw hostile HTML on 30 page views (profile fields) and on every page for every role (names, titles, notes, labels): none.** Template syntax stays literal text (`{{ 7*7 }}` is shown, never evaluated).
* **Hostile model output** (a `<script>`, `<img onerror>`, attribute breakout in all three outputs *and* in the review flags): **never rendered unescaped**.
* Markup in query parameters and path IDs is not reflected.
* Weaknesses found: F-12 and F-13 only.

## 7. Child safety gate (A7)

See F-14 and F-15. In one table (gate limit as built: 8 sentences):

| Output | Caught? |
|---|---|
| any digit (`3`, full-width `３`, Arabic-Indic `٣`) | yes |
| exact medicine name from the note, any letter case | yes |
| more than 8 sentences (9) | yes |
| **7 sentences** (would be withheld at your audit's limit of 6) | no |
| "five milligrams", "ten", "a dozen", "twice a day" | **no** |
| `①`, `²`, `½` | **no** |
| brand name (Amoxil), plural, misspelling, zero-width split | **no** |
| medicine the rule-based extractor missed (Tylenol) | **no** |
| frightening wording without digits/names | **no** |
| 400-word run-on without punctuation; comma-only chain | **no** |
| the rejected text kept in the database | **no** (verified) |

## 8. Jobs (A8)

| Scenario | Result |
|---|---|
| Two (here six) notes submitted at the same instant, real worker thread | 6 × 201; **jobs did not overlap; max concurrency in the pipeline 1**; all `done` |
| Failing generator | That note `failed` with the fixed message (no exception text stored or logged); the **next jobs succeeded** |
| **Real `kill -9`** of a process mid-job, then restart | Before kill `[(1,running),(2,queued)]`; after kill they stay so until restart; **after restart both `done`** |
| Delete a note while its job is running | 0 notes, 0 outputs, 0 ticks left |
| Hung generator | **Stays `running` forever; the next note is stuck behind it** (F-01) |
| 300 notes queued | Accepted without limit (F-03) |
| 20,000-character note, mock | `done`; with the real model **fails** (F-02) |

## 9. Spec gaps (build vs your original spec)

Legend: **Done** = built and covered by a test or run; **Partial**; **Missing**; **Extra** = built but not in the build prompt.

| Spec item | Status | Note |
|---|---|---|
| Landing page with two paths | Done | "Create a Patient Profile" / "Join an Existing Care Circle" |
| Sign-up, login, logout, settings (change password, log out of all sessions, delete account with confirmation) | Done | `/logout` is POST-only (F-24) |
| Profiles list, switcher, empty state | Done | switcher is a nav menu (F-20 for 360px) |
| Create-profile stepper, per-step validation, review | Done | works without JavaScript (F-18 latent) |
| ID and sharing screen, copy button, "not a password", how to invite, link to Care Circle | Done | copy confirmation never run in a browser |
| Join page and all error states (invalid, expired, used, pending, success, no permission) | Done | F-10 |
| Dashboard (context bar, overview, circle snapshot, role-limited cards, latest note status, checklist progress) | Done | |
| Info page | Done | |
| Care circle management; invite, approve, revoke, change role, toggle notes; creator visually distinct | Done | caregivers approve pending children only (your decision) |
| Summaries tabs by role; checklist as a tab (no duplicate page) | Done | |
| Notes page: add, list, status, delete (creator and permitted caregivers) | Done | `.txt` upload and paste only |
| Three outputs with the disclaimer on every output view | Done | disclaimer text is below 16px (F-17) |
| Updated "<time> from note <title>"; history for creator and caregivers | Done | |
| Checklist ticks with who and when, visible to creator and caregivers | Done | unticking is an addition |
| Child safety gate: digit, medicine name, length; reason in flags for adults only | Done, **with deviations** | limit 8 not 6 (F-15); gaps (F-14) |
| Roles and visibility rules; one `can()` function | Done | verified by the matrix |
| Patient ID format, random, unique, "identifier only" | Done | |
| Invitation codes: shown once, hashed, bound to profile/role, 7 days, single use, revocable | Done | email-label binding is Partial (F-11) |
| Auth: scrypt, server sessions, CSRF everywhere, throttling, generic errors, headers, autoescape, parameterised SQL, no secrets in logs | Done | gaps F-04..F-09 |
| Jobs: single worker, states, safe errors, polling UI | Done | no timeout (F-01) |
| Design tokens, components list, WCAG AA contrast script | Done | 44/44 pairs pass |
| Fonts Fraunces and Nunito Sans | **Partial** | named but not bundled (your Stage-0 decision) |
| "Body 16px minimum" | **Partial** | F-17 |
| Responsive 360px to desktop; screenshots if Playwright is installed | **Unverified** | not installed (F-20) |
| Tests listed in the spec | Done | 483 app tests |
| `dev_seed.py` synthetic, passwords from env or printed once | Done | |
| Docs: README section and `app/README.md` | Done | |
| **Extra (not in the build prompt)** | | JSON API under `/api/...` (the prompt only says "API response"); typed-ID confirmation to delete a circle; "Decline" for pending requests; "Cancel invitation" (the prompt says revocable); body-size limit 256 KB; anonymous CSRF cookie for login/sign-up; env vars `APP_SESSION_TTL_HOURS`, `APP_INVITE_TTL_DAYS`, `APP_SECRET_KEY`; refusing to delete an account that owns a circle; throttling of password changes; plain-language review-flag summaries; patient and caregiver see a member list and patient role may open the Info page (assumptions); `--no-server-header`; file permissions 0600/0700 |

## 10. Accessibility and contrast (A11)

* **Contrast script:** `44/44 pairs pass` (text ≥ 4.5:1, borders/focus ≥ 3:1). Re-run during this audit.
* **Checked on every rendered page (about 80 views):** one `<h1>`, heading levels never skip, every link and button has an accessible name, every control is labelled, ids are unique, every POST form has a CSRF field, distinct `<title>`s, landmarks and a skip link, `lang="en"`, no inline script/style, no positive `tabindex`, viewport allows zoom.
* **Keyboard (from structure only):** stepper = ordinary buttons (F-18), tabs = links, copy = a real `<button>`, forms are plain. Focus outline is 3px and never removed (CSS check).
* **360px:** CSS contains no width that can force horizontal scroll (checked), text wraps (`overflow-wrap: anywhere`).
* **Not verified:** actual rendering at 360/768/1280px and screenshots (not taken: Playwright is not installed), what focus looks like, screen-reader behaviour (F-20).

## What is NOT secured (unchanged from the build, plus what this audit adds)

1. **No HTTPS termination**; passwords and notes are clear text on the wire unless a TLS proxy is added and `APP_HTTPS=1` is set.
2. **No distributed rate limiting**; in-memory, per process, resets on restart; unbounded memory (F-06); lockout of known accounts (F-04); shared-IP lockout behind a proxy (F-05); **no throttle on sign-up** (F-07).
3. **No audit by a third party** (this review was by the author, with scripts and tests).
4. **No encryption at rest** (file permissions only); no backup handling.
5. **No email delivery, no email verification, no password reset.**
6. **Sign-up can reveal that an email is registered.**
7. **No hang protection for generation** (F-01) and **no limit on queued notes** (F-03).
8. **No idle session timeout**, no list of devices, no audit log of who viewed what; expired sessions are not purged (F-08).
9. **The child safety gate is rule-based and narrow** (F-14); patient and caregiver text is not gated.
10. **Patient IDs appear in URLs and access logs.**
11. **Notes the real model cannot fit are accepted** (F-02).
12. **No dependency vulnerability scan; JavaScript and layout never verified in a real browser** (F-20, F-23).

## Design-difference decisions you need to make

I could **not view the approved canvas** (it is not in the repository), so these are the five differences exactly as you listed them, with what the build does today and my recommendation. **Nothing was implemented.**

| # | Design shows | Build does today | Recommendation |
|---|---|---|---|
| D-1 | Upload screen mentions **PDF and photo** | Accepts pasted text and `.txt` only (with a clear message for anything else) | **Drop.** PDFs and photos need OCR/PDF libraries (new dependencies, much more attack surface: parsers, image bombs) and would send scanned patient documents through the pipeline. If you want it later, add it as its own reviewed feature |
| D-2 | Access screen: **"Pause new invitations"** and a **recent-activity feed** | Neither. Invitations can be created, listed and cancelled individually | **Pause: add (small, useful)**: one flag on the circle that makes joining fail with the generic message. **Activity feed: drop for now**: there is no audit log, and a feed would expose who did what to other members (privacy design needed first) |
| D-3 | Child screen: **"Read it out loud"** and **"Bigger words"** | Neither. Child text is already larger (1.375rem) on the pink tint | **Bigger words: add** (a CSS-only size toggle, no risk). **Read it out loud: add only if** it uses the browser's on-device speech synthesis (no network); it needs real-browser testing, which I cannot do yet |
| D-4 | Note screen: per-role **"who sees the refreshed explanations"** checkboxes | Visibility comes from the role only; every allowed role sees the refresh | **Drop.** Per-note sharing checkboxes would create more ways to show the wrong content to the wrong person, and the role matrix has been tested thoroughly. If a creator needs to hold a note back, a single "hide from patient and child" switch is safer |
| D-5 | Primary colour **deep purple `#51417F`** | Deep rose `#8E3D4E` (from the build prompt) | **Your call; both pass WCAG AA.** Measured: white on rose 7.17:1, white on purple 8.70:1; purple on cream 8.15:1, on lavender 7.31:1. Colours are tokens, so switching is a one-line change plus re-running the contrast script. Note: purple sits in the same hue family as the **caregiver lavender tint**, so caregiver cards and primary buttons would look related; rose keeps roles visually distinct |

## What I need from you

1. **Which findings to fix** (my suggested order if you say "fix the sensible ones": F-01, F-02, F-03, F-08, F-09, F-04/F-05/F-06, F-13, F-17, F-18, with F-14 limited to the cheap, low-risk checks).
2. **Decisions:** F-02 (limit number), F-10 (keep expiry messages?), F-11 (enforce label?), F-14 (how far to extend the gate), F-15 (confirm 8), D-1 to D-5.
3. **Approval to install Playwright** (and to take the missing 360/768/1280px screenshots), and `pip-audit` for F-23.
