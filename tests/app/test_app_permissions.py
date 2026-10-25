"""The permission table (pure) and can() against real memberships."""

from __future__ import annotations

import itertools

import pytest

from app import permissions as P


# Expected visibility for ACTIVE members. Keep this table in step with the specification, not the code.
EXPECTED_ACTIVE = {
    P.VIEW_DASHBOARD: {"creator", "caregiver", "patient", "child"},
    P.VIEW_INFO: {"creator", "caregiver", "patient"},
    P.VIEW_CIRCLE: {"creator", "caregiver", "patient", "child"},
    P.VIEW_PATIENT_SUMMARY: {"creator", "caregiver", "patient"},
    P.VIEW_CAREGIVER_CHECKLIST: {"creator", "caregiver"},
    P.VIEW_CHILD_EXPLANATION: {"creator", "caregiver", "child"},
    P.VIEW_SOURCE_NOTE: {"creator", "caregiver"},
    P.VIEW_FLAGS: {"creator", "caregiver"},
    P.VIEW_OUTPUT_HISTORY: {"creator", "caregiver"},
    P.VIEW_CHECKLIST_PROGRESS: {"creator", "caregiver"},
    P.TICK_CHECKLIST: {"creator", "caregiver"},
    P.DELETE_NOTE: {"creator"},
    P.INVITE_MEMBER: {"creator"},
    P.REVOKE_INVITATION: {"creator"},
    P.DELETE_PROFILE: {"creator"},
    P.VIEW_MEMBERSHIP_STATUS: {"creator", "caregiver", "patient", "child"},
}


@pytest.mark.parametrize("action,allowed", EXPECTED_ACTIVE.items())
def test_active_role_matrix(action, allowed):
    for role in P.ROLES:
        assert P.decide(role, "active", False, action) == (role in allowed), (role, action)


def test_every_defined_action_is_covered_by_the_tests():
    covered = set(EXPECTED_ACTIVE) | {P.ADD_NOTE, P.APPROVE_MEMBER, P.REVOKE_MEMBER, P.CHANGE_ROLE, P.SET_CAN_ADD_NOTES}
    assert covered == set(P.ACTIONS)


@pytest.mark.parametrize("role,status", list(itertools.product(P.ROLES, ("pending", "revoked"))))
def test_pending_and_revoked_can_only_see_their_status_page(role, status):
    for action in P.ACTIONS:
        assert P.decide(role, status, True, action) == (action == P.VIEW_MEMBERSHIP_STATUS), (role, status, action)


def test_add_note_creator_always_caregiver_only_with_flag():
    assert P.decide("creator", "active", False, P.ADD_NOTE)
    assert P.decide("caregiver", "active", True, P.ADD_NOTE)
    assert not P.decide("caregiver", "active", False, P.ADD_NOTE)
    assert not P.decide("patient", "active", True, P.ADD_NOTE)
    assert not P.decide("child", "active", True, P.ADD_NOTE)


def test_approve_creator_any_pending_caregiver_only_pending_child():
    for target in P.ROLES:
        assert P.decide("creator", "active", True, P.APPROVE_MEMBER, target, "pending")
        assert P.decide("caregiver", "active", True, P.APPROVE_MEMBER, target, "pending") == (target == "child")
        assert not P.decide("creator", "active", True, P.APPROVE_MEMBER, target, "active")       # nothing to approve
        assert not P.decide("patient", "active", False, P.APPROVE_MEMBER, target, "pending")
        assert not P.decide("child", "active", False, P.APPROVE_MEMBER, target, "pending")


@pytest.mark.parametrize("action", [P.REVOKE_MEMBER, P.CHANGE_ROLE, P.SET_CAN_ADD_NOTES])
def test_only_creator_manages_members_and_never_the_creator(action):
    for role in P.ROLES:
        assert P.decide(role, "active", True, action, "caregiver", "active") == (role == "creator")
    assert not P.decide("creator", "active", True, action, "creator", "active")


def test_unknown_values_fail_closed():
    assert not P.decide("admin", "active", True, P.VIEW_DASHBOARD)
    assert not P.decide("creator", "weird", True, P.VIEW_DASHBOARD)
    assert not P.decide("creator", "active", True, "launch_missiles")
    assert not P.decide(None, None, False, P.VIEW_DASHBOARD)


def test_circle_view_levels():
    assert P.circle_view_level("creator") == "full" and P.circle_view_level("child") == "first_names"
    assert P.circle_view_level("caregiver") == P.circle_view_level("patient") == "names_roles"


# --- can() with real database rows ---------------------------------------------------------------
def test_can_requires_membership_and_the_patient_id_alone_grants_nothing(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    stranger = world.user("Stranger")
    assert P.get_membership(conn, stranger["id"], p["id"]) is None
    for action in P.ACTIONS:
        assert not P.can(conn, stranger, p, action), action     # even though `stranger` could look the profile up
    assert not P.can(conn, None, p, P.VIEW_DASHBOARD) and not P.can(conn, stranger, None, P.VIEW_DASHBOARD)


def test_can_for_each_real_role(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    pt, _ = world.member(p, owner, "patient", "Pat")
    ch, _ = world.member(p, owner, "child", "Kid")
    for user, role in ((owner, "creator"), (cg, "caregiver"), (pt, "patient"), (ch, "child")):
        for action, allowed in EXPECTED_ACTIVE.items():
            assert P.can(conn, user, p, action) == (role in allowed), (role, action)


def test_pending_member_has_no_access_in_the_database(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    u, _ = world.member(p, owner, "caregiver", "Cara", active=False)
    assert P.can(conn, u, p, P.VIEW_MEMBERSHIP_STATUS)
    assert not any(P.can(conn, u, p, a) for a in P.ACTIONS if a != P.VIEW_MEMBERSHIP_STATUS)


def test_membership_in_one_circle_grants_nothing_in_another(conn, world):
    a_owner, b_owner = world.user("A"), world.user("B")
    pa, pb = world.profile(a_owner, "Alpha"), world.profile(b_owner, "Beta")
    cg, _ = world.member(pa, a_owner, "caregiver", "Cara")
    assert P.can(conn, cg, pa, P.VIEW_SOURCE_NOTE) and not P.can(conn, cg, pb, P.VIEW_SOURCE_NOTE)


def test_target_from_another_circle_is_refused(conn, world):
    a_owner, b_owner = world.user("A"), world.user("B")
    pa, pb = world.profile(a_owner, "Alpha"), world.profile(b_owner, "Beta")
    _, other = world.member(pb, b_owner, "caregiver", "Cara")
    assert not P.can(conn, a_owner, pa, P.REVOKE_MEMBER, other)


def test_caregiver_with_flag_can_add_notes_in_the_database(conn, world):
    owner = world.user("Owner"); p = world.profile(owner)
    c1, _ = world.member(p, owner, "caregiver", "Cara", can_add_notes=True)
    c2, _ = world.member(p, owner, "caregiver", "Dan", can_add_notes=False)
    assert P.can(conn, c1, p, P.ADD_NOTE) and not P.can(conn, c2, p, P.ADD_NOTE) and P.can(conn, owner, p, P.ADD_NOTE)
