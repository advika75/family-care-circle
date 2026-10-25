# End-to-end transcript (real model, brand-new database)

Status codes and field names only. No note text, cookies, CSRF tokens, passwords or invitation codes are recorded.

Backend: llama_cpp (real model). Database: new, empty, in a fresh temporary directory (e2e.sqlite3). Synthetic note: `data/raw/note_01.txt` (774 characters).

## a. Sign up A, create the profile through the stepper
- a `POST /signup` -> 303
  - PASS: A signed up (303 to a page)
- a `POST /profiles/new (step 1)` -> 200
  - PASS: stepper step 1 -> 200
- a `POST /profiles/new (step 2)` -> 200
  - PASS: stepper step 2 -> 200
- a `POST /profiles/new (step 3)` -> 200
  - PASS: stepper step 3 -> 200
- a `POST /profiles/new (create)` -> 303
  - PASS: server returned a patient ID in the redirect (not hardcoded)
- a `GET /p/{id}/created` -> 200
  - PASS: created page shows the same ID
- a `GET /api/p/{id}/circle` -> 200 fields: can_add_notes, display_name, email, is_creator, membership_id, relationship_label, role, same_name, status
  - PASS: A is the only member and is the creator

## b. B, C, D sign up, are invited, join (pending), A approves
- b `POST /signup` -> 303
- b `POST /signup` -> 303
- b `POST /signup` -> 303
- b `POST /p/{id}/circle/invite (role=caregiver)` -> 200
  - PASS: invitation for caregiver created, code shown once
- b `POST /p/{id}/circle/invite (role=patient)` -> 200
  - PASS: invitation for patient created, code shown once
- b `POST /p/{id}/circle/invite (role=child)` -> 200
  - PASS: invitation for child created, code shown once
- b `POST /join` -> 303
- b `GET /api/p/{id}/outputs (pending caregiver)` -> 403
  - PASS: caregiver is pending and sees no data (API refused: 403; page does not show the profile name)
- b `POST /join` -> 303
- b `GET /api/p/{id}/outputs (pending patient)` -> 403
  - PASS: patient is pending and sees no data (API refused: 403; page does not show the profile name)
- b `POST /join` -> 303
- b `GET /api/p/{id}/outputs (pending child)` -> 403
  - PASS: child is pending and sees no data (API refused: 403; page does not show the profile name)
  - PASS: A sees caregiver as pending
- b `POST /p/{id}/circle/members/{n}/approve` -> 200
  - PASS: A approved caregiver
  - PASS: A sees patient as pending
- b `POST /p/{id}/circle/members/{n}/approve` -> 200
  - PASS: A approved patient
  - PASS: A sees child as pending
- b `POST /p/{id}/circle/members/{n}/approve` -> 200
  - PASS: A approved child
  - PASS: all three are active
- b `POST /p/{id}/circle/members/{n}/notes` -> 200

## c. A adds the synthetic note and waits for the real model
- c `POST /api/p/{id}/notes` -> 201 fields: id, status, title
  - PASS: note accepted (201, queued)
- c `GET /api/p/{id}/status (polled)` -> 200 fields: created_at, finished_at, note, state
  - **real-model wait time: 97 s**, final state: done
  - PASS: generation finished as done

## d. Each user's view
  - (extractor found 4 medication name(s) in the source; names not recorded here)
- d `GET /api/p/{id}/outputs (creator)` -> 200 fields: available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at
- d `GET /api/p/{id}/notes/{n}/source (creator)` -> 200
- d `GET /api/p/{id}/outputs (caregiver)` -> 200 fields: available, caregiver_checklist, checklist_progress, child_explanation, child_withheld, disclaimer, flags, generation, note, output_id, patient_summary, updated_at
- d `GET /api/p/{id}/notes/{n}/source (caregiver)` -> 200
- d `GET /api/p/{id}/outputs (patient)` -> 200 fields: available, disclaimer, generation, output_id, patient_summary, updated_at
- d `GET /api/p/{id}/notes/{n}/source (patient)` -> 403
- d `GET /api/p/{id}/outputs (child)` -> 200 fields: available, child_explanation, disclaimer, generation, output_id, updated_at
- d `GET /api/p/{id}/notes/{n}/source (child)` -> 403
  - PASS: creator sees all three outputs
  - PASS: creator sees the source note
  - PASS: creator sees flags
  - PASS: caregiver sees all three outputs
  - PASS: caregiver sees the source note
  - PASS: caregiver sees flags
  - PASS: patient gets only the patient summary
  - PASS: patient is refused the source note
  - PASS: child gets only the child explanation
  - PASS: child is refused the source note
  - PASS: patient: no source-note text in any response
  - PASS: patient: no flags / retention data in any response
  - PASS: patient: no checklist/child text keys
  - PASS: child: no source-note text in any response
  - PASS: child: no flags / retention data in any response
  - PASS: child: no medication name in any response
  - PASS: child: no digit followed by a unit (API body)
  - child output: **WITHHELD by the safety gate (safe message shown)**

## e. B ticks a checklist item; A sees who and when
- e `POST /api/p/{id}/checklist/{n}/0` -> 200 fields: done, index, ticked, ticked_at, ticked_by, total
  - PASS: B's tick accepted
- e `GET /api/p/{id}/outputs (A, after tick)` -> 200 fields: index, text, ticked, ticked_at, ticked_by
  - PASS: A sees ticked_by = B and a ticked_at time

## screenshots (1280 px, each role's dashboard, via the login form)
  - 4 screenshots written to `app/audit/screenshots/e2e/` (they show synthetic generated text)

## f. A revokes B; B is locked out; A deletes the note
- f `POST /p/{id}/circle/members/{n}/revoke` -> 200
- f `GET /api/p/{id}/outputs (B after revoke)` -> 403
- f `GET /p/{id} (B after revoke)` -> 200
  - PASS: B's next API request is refused
  - PASS: B's next page request shows only the 'Access removed' page, with no profile name, note title or generated text
- f `POST /api/p/{id}/notes/{n}/delete` -> 200
  - PASS: note deleted
- f `GET /api/p/{id}/notes/{n}/outputs (after delete)` -> 404
- f `GET /api/p/{id}/outputs (after delete)` -> 200 fields: available, disclaimer, generation
  - PASS: deleted note's outputs are gone (404)
  - PASS: latest outputs no longer contain any generated text
  - PASS: note list is empty

## Result

ALL CHECKS PASSED. Real-model wait: 97 s.
