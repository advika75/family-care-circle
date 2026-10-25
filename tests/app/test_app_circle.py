"""Profiles, patient IDs, invitations, joining, approval and member management."""

from __future__ import annotations

import sqlite3

import pytest

from app import circle, ids, permissions as P, security
from app.errors import (AlreadyMember, InvalidIdOrCode, InvitationExpired, InvitationUsed, MembershipPending,
                        MembershipRevoked, NotAllowed, NotFound, Throttled, ValidationFailed)


def join(conn, ctx, user, profile, code, label="Son", **kw):
    return circle.join(conn, ctx, user, patient_id=kw.pop("patient_id", profile["patient_id"]), code=code,
                       relationship_label=label, **kw)


# --- profiles -------------------------------------------------------------------------------------
def test_create_profile_makes_creator_membership_and_patient_id(conn, world):
    u = world.user("Owner")
    p = world.profile(u, "Pat Example", preferred_name="Patty", year_of_birth=1950, care_notes="Likes tea.")
    assert ids.PATIENT_ID_RE.match(p["patient_id"])
    m = P.get_membership(conn, u["id"], p["id"])
    assert (m["role"], m["status"], m["can_add_notes"], m["relationship_label"]) == ("creator", "active", 1, "Daughter")
    assert (p["preferred_name"], p["year_of_birth"], p["care_notes"]) == ("Patty", 1950, "Likes tea.")


def test_profile_has_only_the_specified_fields(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(profiles)")}
    assert cols == {"id", "patient_id", "display_name", "preferred_name", "year_of_birth", "care_notes", "created_by", "created_at",
                    "invitations_paused"}          # the last one is the creator-only "Pause new invitations" switch


def test_profile_validation_errors(conn, ctx, world):
    u = world.user("Owner")
    with pytest.raises(ValidationFailed) as e:
        circle.create_profile(conn, ctx, u, display_name=" ", year_of_birth="19x0", care_notes="n" * 2001, relationship_label="Cousin")
    assert set(e.value.errors) == {"display_name", "year_of_birth", "care_notes", "relationship_label"}
    with pytest.raises(ValidationFailed):
        circle.create_profile(conn, ctx, u, display_name="Ok", year_of_birth=2999, relationship_label="Son")
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


def test_profile_creation_is_atomic(conn, ctx, world, monkeypatch):
    u = world.user("Owner")
    monkeypatch.setattr(circle.perm, "CREATOR", "not-a-role")           # make the membership insert violate its CHECK
    with pytest.raises(sqlite3.IntegrityError):
        world.profile(u)
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0     # no orphan profile left behind


def test_patient_ids_are_unique_across_profiles(conn, world):
    u = world.user("Owner")
    pids = {world.profile(u, f"P{i}")["patient_id"] for i in range(30)}
    assert len(pids) == 30


def test_get_profile_by_id_normalises_and_rejects_garbage(conn, world):
    u = world.user("Owner"); p = world.profile(u)
    assert circle.get_profile(conn, p["patient_id"].lower())["id"] == p["id"]
    assert circle.get_profile(conn, "FCC-AAAA-AAAA") is None and circle.get_profile(conn, "' OR 1=1 --") is None


def test_list_profiles_for_user(conn, world):
    u = world.user("Owner")
    assert circle.list_profiles_for_user(conn, u["id"]) == []              # empty state for a new user
    p = world.profile(u)
    assert circle.list_profiles_for_user(conn, u["id"]) == [
        {"patient_id": p["patient_id"], "display_name": "Pat Example", "role": "creator", "status": "active"}]


def test_only_creator_can_delete_profile_and_it_cascades(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    circle.create_invitation(conn, world.ctx, owner, p, role="child")
    with pytest.raises(NotAllowed):
        circle.delete_profile(conn, cg, p)
    circle.delete_profile(conn, owner, p)
    for table in ("profiles", "memberships", "invitations"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2        # accounts are untouched


# --- invitations --------------------------------------------------------------------------------------
def test_invitation_code_is_shown_once_and_stored_only_hashed(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    meta, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver", note="cara@example.test")
    assert ids.INVITE_CODE_RE.match(code)
    row = conn.execute("SELECT * FROM invitations").fetchone()
    assert row["code_hash"] == security.hash_token(code) and code not in "|".join(str(v) for v in tuple(row))
    assert code not in str(meta) and "code" not in " ".join(meta.keys())
    assert all(code not in str(x) for x in circle.list_invitations(conn, ctx, owner, p))   # listing never returns codes


def test_invitation_expires_in_seven_days(conn, ctx, world, clock):
    owner = world.user("Owner"); p = world.profile(owner)
    meta, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    assert meta["expires_at"] == "2026-01-22T12:00:00Z" and meta["state"] == "open"
    u = world.user("Cara")
    clock.advance(days=7, seconds=1)
    with pytest.raises(InvitationExpired):
        join(conn, ctx, u, p, code)
    assert circle.list_invitations(conn, ctx, owner, p)[0]["state"] == "expired"
    assert P.get_membership(conn, u["id"], p["id"]) is None


@pytest.mark.parametrize("role", ["caregiver", "patient", "child"])
def test_join_creates_pending_membership_with_the_invitations_role(conn, ctx, world, role):
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(conn, ctx, owner, p, role=role)
    u = world.user("Joiner")
    m = join(conn, ctx, u, p, code, label="Friend or paid carer")
    assert (m["role"], m["status"], m["can_add_notes"], m["relationship_label"]) == (role, "pending", 0, "Friend or paid carer")
    assert not any(P.can(conn, u, p, a) for a in P.ACTIONS if a != P.VIEW_MEMBERSHIP_STATUS)


def test_relationship_label_is_display_only_and_never_changes_permissions(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    u, m = world.member(p, owner, "child", "Kid")
    conn.execute("UPDATE memberships SET relationship_label = 'Patient (myself)' WHERE id = ?", (m["id"],))
    assert P.can(conn, u, p, P.VIEW_CHILD_EXPLANATION) and not P.can(conn, u, p, P.VIEW_PATIENT_SUMMARY)
    assert not P.can(conn, u, p, P.VIEW_SOURCE_NOTE)


def test_join_has_no_role_parameter(conn):
    import inspect
    assert "role" not in inspect.signature(circle.join).parameters


def test_join_rejects_unknown_relationship_label(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    with pytest.raises(ValidationFailed):
        join(conn, ctx, world.user("J"), p, code, label="Overlord")


def test_invitation_is_single_use(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    join(conn, ctx, world.user("First"), p, code)
    with pytest.raises(InvitationUsed):
        join(conn, ctx, world.user("Second"), p, code)
    assert conn.execute("SELECT COUNT(*) FROM memberships WHERE profile_id = ?", (p["id"],)).fetchone()[0] == 2


def test_same_user_joining_twice_sees_pending_then_already_member(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, c1 = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    _, c2 = circle.create_invitation(conn, ctx, owner, p, role="patient")
    u = world.user("Joiner")
    join(conn, ctx, u, p, c1)
    with pytest.raises(MembershipPending):
        join(conn, ctx, u, p, c1)                      # re-submitting the same code shows "pending", not "already used"
    with pytest.raises(MembershipPending):
        join(conn, ctx, u, p, c2)
    circle.approve_member(conn, ctx, owner, p, P.get_membership(conn, u["id"], p["id"])["id"])
    with pytest.raises(AlreadyMember):
        join(conn, ctx, u, p, c2)
    assert P.get_membership(conn, u["id"], p["id"])["role"] == "caregiver"        # the second code changed nothing


def test_creator_cannot_join_their_own_circle(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    with pytest.raises(AlreadyMember):
        join(conn, ctx, owner, p, code)


def test_code_for_another_circle_is_rejected_like_a_wrong_code(conn, ctx, world):
    a, b = world.user("A"), world.user("B")
    pa, pb = world.profile(a, "Alpha"), world.profile(b, "Beta")
    _, code_b = circle.create_invitation(conn, ctx, b, pb, role="caregiver")
    j = world.user("Joiner")
    with pytest.raises(InvalidIdOrCode) as wrong_profile:
        join(conn, ctx, j, pa, code_b)                 # valid code, but issued for Beta, presented with Alpha's ID
    with pytest.raises(InvalidIdOrCode) as wrong_code:
        join(conn, ctx, j, pa, "AAAA-AAAA-AAAA-AAAA")
    with pytest.raises(InvalidIdOrCode) as wrong_id:
        join(conn, ctx, j, pa, code_b, patient_id="FCC-AAAA-AAAA")
    assert wrong_profile.value.message == wrong_code.value.message == wrong_id.value.message
    assert P.get_membership(conn, j["id"], pa["id"]) is None and P.get_membership(conn, j["id"], pb["id"]) is None


def test_patient_id_alone_cannot_join(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    with pytest.raises(InvalidIdOrCode):
        join(conn, ctx, world.user("Stranger"), p, "")
    assert conn.execute("SELECT COUNT(*) FROM memberships").fetchone()[0] == 1


def test_revoked_invitation_cannot_be_used_and_looks_invalid(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    meta, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    circle.revoke_invitation(conn, owner, p, meta["id"], ctx)
    with pytest.raises(InvalidIdOrCode):
        join(conn, ctx, world.user("J"), p, code)
    with pytest.raises(NotFound):
        circle.revoke_invitation(conn, owner, p, meta["id"], ctx)               # already revoked


def test_used_invitation_cannot_be_revoked(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    meta, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    join(conn, ctx, world.user("J"), p, code)
    with pytest.raises(NotFound):
        circle.revoke_invitation(conn, owner, p, meta["id"], ctx)


def test_only_creator_can_invite_list_and_revoke_invitations(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    meta, _ = circle.create_invitation(conn, ctx, owner, p, role="child")
    for fn in (lambda: circle.create_invitation(conn, ctx, cg, p, role="child"),
               lambda: circle.list_invitations(conn, ctx, cg, p),
               lambda: circle.revoke_invitation(conn, cg, p, meta["id"], ctx)):
        with pytest.raises(NotAllowed):
            fn()


def test_creator_role_cannot_be_invited(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    with pytest.raises(ValidationFailed):
        circle.create_invitation(conn, ctx, owner, p, role="creator")
    assert conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0] == 0


def test_invitation_attempts_are_throttled(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, good = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    j = world.user("Joiner")
    for _ in range(5):
        with pytest.raises(InvalidIdOrCode):
            join(conn, ctx, j, p, "AAAA-AAAA-AAAA-AAAA")
    with pytest.raises(Throttled):
        join(conn, ctx, j, p, good)                    # the right code is refused while throttled


def test_join_throttle_by_ip(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    users = [world.user(f"U{i}") for i in range(20)]
    for u in users:
        with pytest.raises(InvalidIdOrCode):
            join(conn, ctx, u, p, "AAAA-AAAA-AAAA-AAAA", client_ip="8.8.8.8")
    with pytest.raises(Throttled):
        join(conn, ctx, world.user("Fresh"), p, "AAAA-AAAA-AAAA-AAAA", client_ip="8.8.8.8")


def test_invitation_race_second_redeem_fails(conn, ctx, world):
    """If two redemptions slip past the pre-checks, the conditional UPDATE lets only one win."""
    owner = world.user("Owner"); p = world.profile(owner)
    meta, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    conn.execute("UPDATE invitations SET used_at = ? WHERE id = ?", ("2026-01-15T12:00:00Z", meta["id"]))
    with pytest.raises(InvitationUsed):
        join(conn, ctx, world.user("Late"), p, code)


# --- approval and member management ----------------------------------------------------------------------
def test_creator_approves_anyone(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    for role in ("caregiver", "patient", "child"):
        u, m = world.member(p, owner, role, role.title(), active=False)
        circle.approve_member(conn, ctx, owner, p, m["id"])
        assert P.get_membership(conn, u["id"], p["id"])["status"] == "active"


def test_caregiver_approves_only_child_requests(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    _, child = world.member(p, owner, "child", "Kid", active=False)
    _, other_cg = world.member(p, owner, "caregiver", "Dan", active=False)
    _, patient = world.member(p, owner, "patient", "Pat", active=False)
    circle.approve_member(conn, ctx, cg, p, child["id"])
    for m in (other_cg, patient):
        with pytest.raises(NotAllowed):
            circle.approve_member(conn, ctx, cg, p, m["id"])
        assert conn.execute("SELECT status FROM memberships WHERE id = ?", (m["id"],)).fetchone()[0] == "pending"


def test_patient_and_child_cannot_approve(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    pt, _ = world.member(p, owner, "patient", "Pat")
    ch, _ = world.member(p, owner, "child", "Kid")
    _, pending = world.member(p, owner, "child", "Kid2", active=False)
    for u in (pt, ch):
        with pytest.raises(NotAllowed):
            circle.approve_member(conn, ctx, u, p, pending["id"])


def test_approve_unknown_or_foreign_membership(conn, ctx, world):
    a, b = world.user("A"), world.user("B")
    pa, pb = world.profile(a, "Alpha"), world.profile(b, "Beta")
    _, foreign = world.member(pb, b, "child", "Kid", active=False)
    with pytest.raises(NotFound):
        circle.approve_member(conn, ctx, a, pa, foreign["id"])
    with pytest.raises(NotFound):
        circle.approve_member(conn, ctx, a, pa, 99999)


def test_revoke_member_removes_access_and_blocks_rejoin(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, m = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    circle.revoke_member(conn, ctx, owner, p, m["id"])
    row = P.get_membership(conn, cg["id"], p["id"])
    assert row["status"] == "revoked" and row["can_add_notes"] == 0
    assert not any(P.can(conn, cg, p, a) for a in P.ACTIONS if a != P.VIEW_MEMBERSHIP_STATUS)
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    with pytest.raises(MembershipRevoked):
        join(conn, ctx, cg, p, code)


def test_can_decline_a_pending_request_by_revoking_it(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    u, m = world.member(p, owner, "caregiver", "Cara", active=False)
    circle.revoke_member(conn, ctx, owner, p, m["id"])
    assert P.get_membership(conn, u["id"], p["id"])["status"] == "revoked"


def test_creator_membership_cannot_be_altered(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    mid = P.get_membership(conn, owner["id"], p["id"])["id"]
    for fn in (lambda: circle.revoke_member(conn, ctx, owner, p, mid),
               lambda: circle.change_role(conn, ctx, owner, p, mid, "child"),
               lambda: circle.set_can_add_notes(conn, ctx, owner, p, mid, False)):
        with pytest.raises(NotAllowed):
            fn()
    assert P.get_membership(conn, owner["id"], p["id"])["role"] == "creator"


def test_non_creators_cannot_manage_members(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    _, target = world.member(p, owner, "patient", "Pat")
    for fn in (lambda: circle.revoke_member(conn, ctx, cg, p, target["id"]),
               lambda: circle.change_role(conn, ctx, cg, p, target["id"], "child"),
               lambda: circle.set_can_add_notes(conn, ctx, cg, p, target["id"], True)):
        with pytest.raises(NotAllowed):
            fn()
    assert P.get_membership(conn, target["user_id"], p["id"])["role"] == "patient"


def test_change_role_resets_note_permission_unless_caregiver(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, m = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    circle.change_role(conn, ctx, owner, p, m["id"], "patient")
    row = P.get_membership(conn, cg["id"], p["id"])
    assert (row["role"], row["can_add_notes"]) == ("patient", 0)
    assert not P.can(conn, cg, p, P.VIEW_SOURCE_NOTE) and P.can(conn, cg, p, P.VIEW_PATIENT_SUMMARY)
    with pytest.raises(ValidationFailed):
        circle.change_role(conn, ctx, owner, p, m["id"], "creator")


def test_can_add_notes_only_for_caregivers(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, patient = world.member(p, owner, "patient", "Pat")
    _, cg = world.member(p, owner, "caregiver", "Cara")
    with pytest.raises(NotAllowed):
        circle.set_can_add_notes(conn, ctx, owner, p, patient["id"], True)
    circle.set_can_add_notes(conn, ctx, owner, p, cg["id"], True)
    circle.set_can_add_notes(conn, ctx, owner, p, cg["id"], False)
    assert conn.execute("SELECT can_add_notes FROM memberships WHERE id = ?", (cg["id"],)).fetchone()[0] == 0


def test_database_enforces_note_permission_and_single_creator(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, patient = world.member(p, owner, "patient", "Pat")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE memberships SET can_add_notes = 1 WHERE id = ?", (patient["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE memberships SET role = 'creator', status = 'active', can_add_notes = 1 WHERE id = ?", (patient["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO memberships(profile_id,user_id,role,status,relationship_label,created_at,updated_at) "
                     "VALUES (?,?,'bogus','active','x','t','t')", (p["id"], owner["id"]))


# --- who sees which members (filtered on the server) -----------------------------------------------------
def build_circle(world):
    owner = world.user("Olivia Owner", email="olivia@example.test"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara Carer")
    pt, _ = world.member(p, owner, "patient", "Pat Patient")
    ch, _ = world.member(p, owner, "child", "Kid Kidson")
    world.member(p, owner, "child", "Pending Kid", active=False)
    world.member(p, owner, "caregiver", "Pending Carer", active=False)
    return p, owner, cg, pt, ch


def test_creator_sees_everyone_with_management_fields(conn, world):
    p, owner, *_ = build_circle(world)
    rows = circle.list_members(conn, owner, p)
    assert len(rows) == 6 and rows[0]["is_creator"] and rows[0]["role"] == "creator"
    assert {"email", "status", "can_add_notes", "membership_id"} <= set(rows[1])
    assert {r["status"] for r in rows} == {"active", "pending"}


def test_caregiver_sees_active_members_plus_pending_children_only(conn, world):
    p, owner, cg, *_ = build_circle(world)
    rows = circle.list_members(conn, cg, p)
    assert {r["display_name"] for r in rows} == {"Olivia Owner", "Cara Carer", "Pat Patient", "Kid Kidson", "Pending Kid"}
    assert all("email" not in r and "can_add_notes" not in r for r in rows)
    assert [r for r in rows if r.get("status") == "pending"] == [r for r in rows if r["display_name"] == "Pending Kid"]


def test_patient_sees_names_and_roles_of_active_members_only(conn, world):
    p, owner, cg, pt, ch = build_circle(world)
    rows = circle.list_members(conn, pt, p)
    assert {r["display_name"] for r in rows} == {"Olivia Owner", "Cara Carer", "Pat Patient", "Kid Kidson"}
    assert all(set(r) == {"display_name", "role", "relationship_label", "is_creator", "same_name"} for r in rows)


def test_child_sees_first_names_only(conn, world):
    p, owner, cg, pt, ch = build_circle(world)
    rows = circle.list_members(conn, ch, p)
    assert rows == [{"first_name": "Olivia"}, {"first_name": "Cara"}, {"first_name": "Pat"}, {"first_name": "Kid"}]
    text = str(rows)
    for leak in ("Owner", "Carer", "Patient", "Kidson", "email", "@", "role", "caregiver", "creator"):
        assert leak not in text


def test_pending_revoked_and_strangers_cannot_list_members(conn, world):
    p, owner, *_ = build_circle(world)
    pending, _ = world.member(p, owner, "caregiver", "Waiting", active=False)
    stranger = world.user("Stranger")
    for u in (pending, stranger):
        with pytest.raises(NotAllowed):
            circle.list_members(conn, u, p)


def test_pending_and_revoked_members_are_never_shown_the_patients_name(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner, "Secret Patient Name")
    pending, _ = world.member(p, owner, "caregiver", "Waiting", active=False)
    revoked, rm = world.member(p, owner, "caregiver", "Removed")
    circle.revoke_member(conn, ctx, owner, p, rm["id"])
    active, _ = world.member(p, owner, "patient", "Pat")
    for user, status in ((pending, "pending"), (revoked, "revoked")):
        (row,) = circle.list_profiles_for_user(conn, user["id"])
        assert row["status"] == status and "Secret Patient Name" not in str(row)
        assert row["display_name"] == f"Care circle {p['patient_id']}"
    (row,) = circle.list_profiles_for_user(conn, active["id"])
    assert row["display_name"] == "Secret Patient Name"                       # active members see it


def test_children_are_only_ever_given_the_preferred_name(conn, world):
    owner = world.user("Owner"); p = world.profile(owner, "Margaret Fullname Smith", preferred_name="Grandma")
    child, _ = world.member(p, owner, "child", "Kid")
    patient, _ = world.member(p, owner, "patient", "Pat")
    (c,) = circle.list_profiles_for_user(conn, child["id"])
    assert c["display_name"] == "Grandma" and "Margaret" not in str(c) and "Smith" not in str(c)
    (pt,) = circle.list_profiles_for_user(conn, patient["id"])
    assert pt["display_name"] == "Margaret Fullname Smith"
    q = world.profile(owner, "Robert Longname Jones")                      # no preferred name: first name only
    ch2, _ = world.member(q, owner, "child", "Kid2")
    rows = {r["patient_id"]: r for r in circle.list_profiles_for_user(conn, ch2["id"])}
    assert rows[q["patient_id"]]["display_name"] == "Robert"


# --- Phase B: F-11 (rename), F-12 (look-alike names), F-13 (control characters) -------------------------
def test_invitation_note_rejects_control_characters(conn, ctx, world):
    """F-13: a NUL (or any control character) in the note is refused, like names and notes already do."""
    owner = world.user("Owner"); p = world.profile(owner)
    for bad in ("for\x00Pat", "tab\there", "line\nbreak", "bell\x07"):
        with pytest.raises(ValidationFailed) as e:
            circle.create_invitation(conn, ctx, owner, p, role="caregiver", note=bad)
        assert "note" in e.value.errors
    assert conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0] == 0


def test_invitation_note_is_stored_in_a_column_called_note(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    meta, _ = circle.create_invitation(conn, ctx, owner, p, role="child", note="for Sam")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(invitations)")}
    assert "note" in cols and "email_label" not in cols and meta["note"] == "for Sam"


@pytest.mark.parametrize("name", ["Evil‮Name", "Zero​Width", "Join⁠er", "Bom﻿Name", "Iso⁦late"])
def test_display_names_with_bidi_or_invisible_characters_are_rejected(conn, ctx, world, name):
    """F-12: bidi overrides and zero-width/format characters let a name look like another or reorder text."""
    from app import accounts
    from fcc_testlib import PASSWORD
    with pytest.raises(ValidationFailed) as e:
        accounts.signup(conn, ctx, email="x@example.test", display_name=name, password=PASSWORD)
    assert "display_name" in e.value.errors


def test_ordinary_international_names_and_emoji_still_work(conn, ctx, world):
    from app import accounts
    from fcc_testlib import PASSWORD
    for i, name in enumerate(["José Núñez", "李小龍", "Zoë O'Brien-Smith", "Dr. Ana 🌻"]):
        accounts.signup(conn, ctx, email=f"ok{i}@example.test", display_name=name, password=PASSWORD)


def test_member_list_flags_members_who_share_a_name(conn, ctx, world):
    """F-12: approvers can see when two members have the same name (case/spacing-insensitive)."""
    owner = world.user("Owner"); p = world.profile(owner)
    a, _ = world.member(p, owner, "caregiver", "Sam Rivera")
    b, _ = world.member(p, owner, "caregiver", "sam  RIVERA", active=False)
    c, _ = world.member(p, owner, "caregiver", "Unique Person")
    rows = {m["display_name"]: m for m in circle.list_members(conn, owner, p)}
    assert rows["Sam Rivera"]["same_name"] and rows["sam  RIVERA"]["same_name"]
    assert not rows["Unique Person"]["same_name"] and not rows["Owner"]["same_name"]


def test_caregiver_approving_a_child_sees_the_duplicate_flag_only_among_visible_members(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Pat Smith")
    world.member(p, owner, "child", "Pat Smith", active=False)           # pending child with the caregiver's own name
    seen = circle.list_members(conn, cg, p)
    pending = [m for m in seen if m.get("status") == "pending"][0]
    assert pending["same_name"] is True


# --- Phase B (optional item): pause new invitations ------------------------------------------------------
def test_only_the_creator_can_pause_or_resume_invitations(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Carla", can_add_notes=True)
    with pytest.raises(NotAllowed):
        circle.set_invitations_paused(conn, ctx, cg, p, True)
    stranger = world.user("Stranger")
    with pytest.raises(NotAllowed):
        circle.set_invitations_paused(conn, ctx, stranger, p, True)
    assert not circle.get_profile(conn, p["patient_id"])["invitations_paused"]
    circle.set_invitations_paused(conn, ctx, owner, p, True)
    assert circle.get_profile(conn, p["patient_id"])["invitations_paused"]
    circle.set_invitations_paused(conn, ctx, owner, p, False)
    assert not circle.get_profile(conn, p["patient_id"])["invitations_paused"]


def test_a_paused_circle_rejects_codes_issued_before_the_pause_with_the_generic_message(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    circle.set_invitations_paused(conn, ctx, owner, p, True)
    joiner = world.user("Joiner")
    with pytest.raises(InvalidIdOrCode) as paused:
        join(conn, ctx, joiner, p, code)
    with pytest.raises(InvalidIdOrCode) as wrong:
        join(conn, ctx, joiner, p, "AAAA-AAAA-AAAA-AAAA")
    assert paused.value.message == wrong.value.message          # a pause is not revealed to someone holding a code
    assert conn.execute("SELECT COUNT(*) FROM memberships WHERE user_id = ?", (joiner["id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT used_at FROM invitations").fetchone()[0] is None      # the code was not burned
    circle.set_invitations_paused(conn, ctx, owner, p, False)
    join(conn, ctx, joiner, p, code)                                                   # and works again after resuming


def test_no_new_invitations_can_be_created_while_paused(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    circle.set_invitations_paused(conn, ctx, owner, p, True)
    with pytest.raises(ValidationFailed) as e:
        circle.create_invitation(conn, ctx, owner, p, role="child")
    assert "paused" in " ".join(e.value.errors.values()).lower()
    assert conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0] == 0
