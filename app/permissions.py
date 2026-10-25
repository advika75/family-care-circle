"""The single place that decides who may do what: :func:`can`.

Every route, API response builder and template guard must call ``can(...)`` (or its pure core,
``decide(...)``); nothing else may infer permissions from a role name.

Roles:   creator, caregiver, patient, child
Status:  pending | active | revoked   (pending/revoked members can do nothing except see their own
         "pending approval" / "access removed" page)
Having a patient ID, or being logged in, grants nothing: access always requires an *active membership*.

Assumptions made where the specification was silent (flagged in app/PROGRESS.md):
* Caregivers may approve only *pending child* memberships (decided by the project owner). Creators approve all.
* ``delete_note`` is creator-only (the spec lists note deletion only under the creator).
* ``view_info`` (the read-only profile page) is allowed for creator, caregiver and patient, not child.
* ``view_circle`` is allowed for every active member, but ``circle_view_level`` limits what each role sees.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping

CREATOR, CAREGIVER, PATIENT, CHILD = "creator", "caregiver", "patient", "child"
ROLES = (CREATOR, CAREGIVER, PATIENT, CHILD)
INVITABLE_ROLES = (CAREGIVER, PATIENT, CHILD)
PENDING, ACTIVE, REVOKED = "pending", "active", "revoked"
STATUSES = (PENDING, ACTIVE, REVOKED)

# --- actions -----------------------------------------------------------------------------------------
VIEW_MEMBERSHIP_STATUS = "view_membership_status"  # the pending / access-removed page
VIEW_DASHBOARD = "view_dashboard"
VIEW_INFO = "view_info"
VIEW_CIRCLE = "view_circle"
VIEW_PATIENT_SUMMARY = "view_patient_summary"
VIEW_CAREGIVER_CHECKLIST = "view_caregiver_checklist"
VIEW_CHILD_EXPLANATION = "view_child_explanation"
VIEW_SOURCE_NOTE = "view_source_note"
VIEW_FLAGS = "view_flags"
VIEW_OUTPUT_HISTORY = "view_output_history"
VIEW_CHECKLIST_PROGRESS = "view_checklist_progress"
TICK_CHECKLIST = "tick_checklist"
ADD_NOTE = "add_note"
DELETE_NOTE = "delete_note"
INVITE_MEMBER = "invite_member"
APPROVE_MEMBER = "approve_member"          # target-dependent: see decide()
REVOKE_MEMBER = "revoke_member"
CHANGE_ROLE = "change_role"
SET_CAN_ADD_NOTES = "set_can_add_notes"
REVOKE_INVITATION = "revoke_invitation"
DELETE_PROFILE = "delete_profile"

ACTIONS = frozenset({
    VIEW_MEMBERSHIP_STATUS, VIEW_DASHBOARD, VIEW_INFO, VIEW_CIRCLE, VIEW_PATIENT_SUMMARY,
    VIEW_CAREGIVER_CHECKLIST, VIEW_CHILD_EXPLANATION, VIEW_SOURCE_NOTE, VIEW_FLAGS, VIEW_OUTPUT_HISTORY,
    VIEW_CHECKLIST_PROGRESS, TICK_CHECKLIST, ADD_NOTE, DELETE_NOTE, INVITE_MEMBER, APPROVE_MEMBER,
    REVOKE_MEMBER, CHANGE_ROLE, SET_CAN_ADD_NOTES, REVOKE_INVITATION, DELETE_PROFILE,
})

_ALL = frozenset(ROLES)
_ADULTS = frozenset({CREATOR, CAREGIVER})

#: action -> roles allowed when the membership is ACTIVE (ADD_NOTE and APPROVE_MEMBER have extra conditions)
_ACTIVE_ROLES: dict[str, frozenset[str]] = {
    VIEW_DASHBOARD: _ALL,
    VIEW_INFO: frozenset({CREATOR, CAREGIVER, PATIENT}),
    VIEW_CIRCLE: _ALL,
    VIEW_PATIENT_SUMMARY: frozenset({CREATOR, CAREGIVER, PATIENT}),
    VIEW_CAREGIVER_CHECKLIST: _ADULTS,
    VIEW_CHILD_EXPLANATION: frozenset({CREATOR, CAREGIVER, CHILD}),
    VIEW_SOURCE_NOTE: _ADULTS,
    VIEW_FLAGS: _ADULTS,
    VIEW_OUTPUT_HISTORY: _ADULTS,
    VIEW_CHECKLIST_PROGRESS: _ADULTS,
    TICK_CHECKLIST: _ADULTS,
    ADD_NOTE: _ADULTS,                       # caregivers additionally need can_add_notes
    DELETE_NOTE: frozenset({CREATOR}),
    INVITE_MEMBER: frozenset({CREATOR}),
    APPROVE_MEMBER: _ADULTS,                 # caregivers only for pending *child* targets
    REVOKE_MEMBER: frozenset({CREATOR}),
    CHANGE_ROLE: frozenset({CREATOR}),
    SET_CAN_ADD_NOTES: frozenset({CREATOR}),
    REVOKE_INVITATION: frozenset({CREATOR}),
    DELETE_PROFILE: frozenset({CREATOR}),
}


def decide(role: str | None, status: str | None, can_add_notes: bool, action: str,
           target_role: str | None = None, target_status: str | None = None) -> bool:
    """Pure permission table. ``target_*`` describe the membership being acted on (approve/revoke/...)."""
    if action not in ACTIONS or role not in ROLES or status not in STATUSES:
        return False
    if action == VIEW_MEMBERSHIP_STATUS:
        return True                          # any member, whatever the status
    if status != ACTIVE:
        return False                         # pending and revoked members get nothing else
    if role not in _ACTIVE_ROLES.get(action, frozenset()):
        return False
    if action == ADD_NOTE:
        return role == CREATOR or bool(can_add_notes)
    if action == APPROVE_MEMBER:
        if target_status != PENDING:
            return False
        return role == CREATOR or (role == CAREGIVER and target_role == CHILD)
    if action in (REVOKE_MEMBER, CHANGE_ROLE, SET_CAN_ADD_NOTES):
        return target_role != CREATOR        # the creator's own membership can never be altered
    return True


def circle_view_level(role: str) -> str:
    """How much of the member list a role may see: full | names_roles | first_names."""
    if role == CREATOR:
        return "full"
    if role == CHILD:
        return "first_names"
    return "names_roles"


def get_membership(conn: sqlite3.Connection, user_id: int, profile_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM memberships WHERE user_id = ? AND profile_id = ?", (user_id, profile_id)).fetchone()


def can(conn: sqlite3.Connection, user: Mapping[str, Any] | None, profile: Mapping[str, Any] | None, action: str,
        target: Mapping[str, Any] | None = None) -> bool:
    """May ``user`` perform ``action`` on ``profile``? ``target`` is the membership row acted upon, if any.

    Looks up the user's own membership in the database; a missing user, profile or membership means no.
    """
    if user is None or profile is None:
        return False
    m = get_membership(conn, user["id"], profile["id"])
    if m is None:
        return False
    if target is not None and target["profile_id"] != profile["id"]:
        return False                          # a target from another circle is never actionable here
    return decide(
        m["role"], m["status"], bool(m["can_add_notes"]), action,
        target["role"] if target is not None else None,
        target["status"] if target is not None else None,
    )
