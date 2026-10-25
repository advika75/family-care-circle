"""Care circles: profiles, memberships and invitations.

Profile fields are exactly: display name, preferred name (for the child view), year of birth, care notes and the
creator's relationship label (stored on the creator's membership). Nothing else is collected about the patient.

Joining requires (a) the user's own account, (b) a valid, unexpired, unused, unrevoked invitation code issued
for THIS profile, and (c) approval. The patient ID alone grants nothing. Every mutating function re-checks
permission through ``permissions.can`` so that a route that forgets to check still cannot act.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import timedelta
from typing import Any

from app import ids, permissions as perm, security
from app.accounts import _CONTROL, clean_name, name_key
from app.context import Ctx, JOIN_FAILURES_PER_IP, JOIN_FAILURES_PER_USER
from app.db import iso, parse_iso, transaction
from app.errors import (AlreadyMember, InvalidIdOrCode, InvitationExpired, InvitationUsed, MembershipPending,
                        MembershipRevoked, NotAllowed, NotFound, Throttled, ValidationFailed)

log = logging.getLogger("app.circle")  # never log invitation codes or note text

RELATIONSHIP_LABELS = ("Patient (myself)", "Spouse or partner", "Daughter", "Son", "Other relative",
                       "Friend or paid carer")
MAX_CARE_NOTES = 2000
YEAR_MIN = 1900


# --------------------------------------------------------------------------------------- profiles
def _validate_profile(ctx: Ctx, display_name: str, preferred_name: str | None, year_of_birth: Any,
                      care_notes: str | None, relationship_label: str) -> dict[str, Any]:
    errors: dict[str, str] = {}
    out: dict[str, Any] = {}
    try:
        out["display_name"] = clean_name(display_name, "display_name")
    except ValidationFailed as exc:
        errors.update(exc.errors)
    pn = (preferred_name or "").strip()
    if pn:
        try:
            out["preferred_name"] = clean_name(pn, "preferred_name", maximum=40)
        except ValidationFailed as exc:
            errors.update(exc.errors)
    else:
        out["preferred_name"] = None
    yob = year_of_birth
    if yob in (None, ""):
        out["year_of_birth"] = None
    else:
        try:
            yob = int(str(yob).strip())
            if not YEAR_MIN <= yob <= ctx.now().year:
                raise ValueError
            out["year_of_birth"] = yob
        except ValueError:
            errors["year_of_birth"] = f"Enter a year between {YEAR_MIN} and {ctx.now().year}, or leave it blank."
    cn = (care_notes or "").strip()
    if len(cn) > MAX_CARE_NOTES:
        errors["care_notes"] = f"Use at most {MAX_CARE_NOTES} characters."
    out["care_notes"] = cn or None
    if relationship_label not in RELATIONSHIP_LABELS:
        errors["relationship_label"] = "Choose how you are related to the patient."
    out["relationship_label"] = relationship_label
    if errors:
        raise ValidationFailed(errors)
    return out


def check_profile_fields(ctx: Ctx, values: dict[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    """Validate only ``fields`` (used by the step-by-step form). Returns {field: message}; empty means OK."""
    try:
        _validate_profile(ctx, values.get("display_name", ""), values.get("preferred_name"), values.get("year_of_birth"),
                          values.get("care_notes"), values.get("relationship_label", ""))
    except ValidationFailed as exc:
        return {k: v for k, v in exc.errors.items() if k in fields}
    return {}


def create_profile(conn: sqlite3.Connection, ctx: Ctx, user: sqlite3.Row, *, display_name: str,
                   preferred_name: str | None = None, year_of_birth: Any = None, care_notes: str | None = None,
                   relationship_label: str) -> sqlite3.Row:
    """Create a profile with a fresh patient ID and the creator's (active) membership, atomically."""
    v = _validate_profile(ctx, display_name, preferred_name, year_of_birth, care_notes, relationship_label)
    now = iso(ctx.now())
    with transaction(conn):
        for _ in range(20):
            patient_id = ids.new_patient_id()
            try:
                cur = conn.execute(
                    "INSERT INTO profiles(patient_id, display_name, preferred_name, year_of_birth, care_notes, "
                    "created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                    (patient_id, v["display_name"], v["preferred_name"], v["year_of_birth"], v["care_notes"],
                     user["id"], now))
                break
            except sqlite3.IntegrityError:  # patient ID collision (vanishingly rare): draw again
                continue
        else:  # pragma: no cover
            raise RuntimeError("could not allocate a unique patient ID")
        conn.execute(
            "INSERT INTO memberships(profile_id, user_id, role, status, can_add_notes, relationship_label, "
            "created_at, updated_at) VALUES (?,?,?,?,1,?,?,?)",
            (cur.lastrowid, user["id"], perm.CREATOR, perm.ACTIVE, v["relationship_label"], now, now))
    log.info("profile created profile_id=%s by user_id=%s", cur.lastrowid, user["id"])
    return conn.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone()


def get_profile(conn: sqlite3.Connection, patient_id: str) -> sqlite3.Row | None:
    """Look a profile up by patient ID. This is an internal lookup: callers MUST still check membership."""
    pid = ids.normalize_patient_id(patient_id)
    return conn.execute("SELECT * FROM profiles WHERE patient_id = ?", (pid,)).fetchone() if pid else None


def list_profiles_for_user(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT p.patient_id, p.display_name, p.preferred_name, m.role, m.status FROM memberships m "
        "JOIN profiles p ON p.id = m.profile_id WHERE m.user_id = ? ORDER BY p.created_at, p.id", (user_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        preferred = d.pop("preferred_name")
        if d["status"] != perm.ACTIVE:      # pending and revoked members must not learn anything about the patient
            d["display_name"] = f"Care circle {d['patient_id']}"
        elif d["role"] == perm.CHILD:       # children only ever get the preferred name (or a first name)
            d["display_name"] = preferred or first_name(d["display_name"])
        out.append(d)
    return out


def delete_profile(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> None:
    if not perm.can(conn, actor, profile, perm.DELETE_PROFILE):
        raise NotAllowed()
    with transaction(conn):
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile["id"],))  # memberships, invitations, notes cascade
    log.info("profile deleted profile_id=%s by user_id=%s", profile["id"], actor["id"])


# ------------------------------------------------------------------------------------ invitations
def create_invitation(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, *, role: str,
                      note: str | None = None) -> tuple[dict[str, Any], str]:
    """Issue an invitation. Returns (metadata, plaintext_code). The code is shown once and stored only hashed.

    ``note`` is a private reminder for the inviter ("note for yourself"); it is NOT enforced at join time.
    """
    if not perm.can(conn, actor, profile, perm.INVITE_MEMBER):
        raise NotAllowed()
    if role not in perm.INVITABLE_ROLES:
        raise ValidationFailed({"role": "Choose caregiver, patient or child."})
    if conn.execute("SELECT invitations_paused FROM profiles WHERE id = ?", (profile["id"],)).fetchone()[0]:
        raise ValidationFailed({"role": "New invitations are paused for this care circle. Resume them first."})
    label = (note or "").strip() or None
    if label is not None and len(label) > 254:
        raise ValidationFailed({"note": "That note is too long."})
    if label is not None and _CONTROL.search(label):                 # F-13: same rule as names (also rejects newlines/tabs)
        raise ValidationFailed({"note": "That note contains characters that are not allowed."})
    code = ids.new_invite_code()
    now = ctx.now()
    cur = conn.execute(
        "INSERT INTO invitations(profile_id, role, code_hash, note, created_by, created_at, expires_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (profile["id"], role, security.hash_token(code), label, actor["id"], iso(now),
         iso(now + timedelta(days=ctx.settings.invite_ttl_days))))
    log.info("invitation created id=%s profile_id=%s role=%s", cur.lastrowid, profile["id"], role)
    return _invitation_meta(conn, ctx, cur.lastrowid), code


def _invitation_meta(conn: sqlite3.Connection, ctx: Ctx, invitation_id: int) -> dict[str, Any]:
    r = conn.execute("SELECT id, role, note, created_at, expires_at, used_at, revoked_at FROM invitations "
                     "WHERE id = ?", (invitation_id,)).fetchone()
    d = dict(r)
    d["state"] = ("revoked" if r["revoked_at"] else "used" if r["used_at"]
                  else "expired" if parse_iso(r["expires_at"]) <= ctx.now() else "open")
    return d


def list_invitations(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row) -> list[dict[str, Any]]:
    """Invitation metadata for the creator. Codes are never returned (they are not stored)."""
    if not perm.can(conn, actor, profile, perm.INVITE_MEMBER):
        raise NotAllowed()
    rows = conn.execute("SELECT id FROM invitations WHERE profile_id = ? ORDER BY id DESC", (profile["id"],)).fetchall()
    return [_invitation_meta(conn, ctx, r["id"]) for r in rows]


def set_invitations_paused(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, paused: bool) -> None:
    """Creator only. While paused, no invitation can be created and no existing code can be redeemed."""
    if not perm.can(conn, actor, profile, perm.INVITE_MEMBER):
        raise NotAllowed()
    conn.execute("UPDATE profiles SET invitations_paused = ? WHERE id = ?", (1 if paused else 0, profile["id"]))
    log.info("invitations %s profile_id=%s", "paused" if paused else "resumed", profile["id"])


def revoke_invitation(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row, invitation_id: int, ctx: Ctx) -> None:
    if not perm.can(conn, actor, profile, perm.REVOKE_INVITATION):
        raise NotAllowed()
    cur = conn.execute(
        "UPDATE invitations SET revoked_at = ? WHERE id = ? AND profile_id = ? AND used_at IS NULL AND revoked_at IS NULL",
        (iso(ctx.now()), invitation_id, profile["id"]))
    if cur.rowcount == 0:
        raise NotFound("That invitation is not open any more.")


# ------------------------------------------------------------------------------------------- join
def join(conn: sqlite3.Connection, ctx: Ctx, user: sqlite3.Row, *, patient_id: str, code: str,
         relationship_label: str, client_ip: str = "") -> sqlite3.Row:
    """Redeem an invitation: creates a PENDING membership with the invitation's role. Returns the membership.

    Wrong ID, wrong code, malformed input, a code issued for another circle and revoked codes all give the
    same ``InvalidIdOrCode`` error and count towards the throttle.
    """
    if relationship_label not in RELATIONSHIP_LABELS:
        raise ValidationFailed({"relationship_label": "Choose how you are related to the patient."})
    user_key, ip_key = f"join:user:{user['id']}", f"join:ip:{client_ip}"
    if ctx.throttle.blocked(user_key, JOIN_FAILURES_PER_USER) or (client_ip and ctx.throttle.blocked(ip_key, JOIN_FAILURES_PER_IP)):
        raise Throttled()

    def fail() -> None:
        ctx.throttle.record_failure(user_key, *([ip_key] if client_ip else []))
        raise InvalidIdOrCode()

    pid, norm_code = ids.normalize_patient_id(patient_id), ids.normalize_invite_code(code)
    if pid is None or norm_code is None:
        fail()
    inv = conn.execute("SELECT * FROM invitations WHERE code_hash = ?", (security.hash_token(norm_code),)).fetchone()
    if inv is None:
        fail()
    profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (inv["profile_id"],)).fetchone()
    if (profile is None or not security.constant_time_equals(profile["patient_id"], pid) or inv["revoked_at"]
            or profile["invitations_paused"]):
        fail()                                   # a paused circle looks exactly like a wrong code
    # From here on the caller has proven they hold a matching ID and code for this circle.
    existing = perm.get_membership(conn, user["id"], profile["id"])
    if existing is not None:
        raise {perm.PENDING: MembershipPending, perm.ACTIVE: AlreadyMember, perm.REVOKED: MembershipRevoked}[existing["status"]]()
    if inv["used_at"]:
        raise InvitationUsed()
    if parse_iso(inv["expires_at"]) <= ctx.now():
        raise InvitationExpired()
    now = iso(ctx.now())
    try:
        with transaction(conn):
            cur = conn.execute(
                "UPDATE invitations SET used_at = ?, used_by = ? WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL "
                "AND expires_at > ?", (now, user["id"], inv["id"], now))
            if cur.rowcount != 1:
                raise InvitationUsed()
            conn.execute(
                "INSERT INTO memberships(profile_id, user_id, role, status, can_add_notes, relationship_label, created_at, "
                "updated_at) VALUES (?,?,?,?,0,?,?,?)",
                (profile["id"], user["id"], inv["role"], perm.PENDING, relationship_label, now, now))
    except sqlite3.IntegrityError:
        raise AlreadyMember() from None
    ctx.throttle.reset(user_key)
    log.info("join requested profile_id=%s user_id=%s role=%s", profile["id"], user["id"], inv["role"])
    return perm.get_membership(conn, user["id"], profile["id"])


# ------------------------------------------------------------------------------ member management
def _target(conn: sqlite3.Connection, profile: sqlite3.Row, membership_id: int) -> sqlite3.Row:
    t = conn.execute("SELECT * FROM memberships WHERE id = ? AND profile_id = ?", (membership_id, profile["id"])).fetchone()
    if t is None:
        raise NotFound()
    return t


def approve_member(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, membership_id: int) -> None:
    """Activate a pending membership. Creator: any role. Caregiver: pending child requests only."""
    t = _target(conn, profile, membership_id)
    if not perm.can(conn, actor, profile, perm.APPROVE_MEMBER, t):
        raise NotAllowed()
    conn.execute("UPDATE memberships SET status = 'active', updated_at = ? WHERE id = ? AND status = 'pending'",
                 (iso(ctx.now()), t["id"]))
    log.info("member approved membership_id=%s by user_id=%s", t["id"], actor["id"])


def revoke_member(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, membership_id: int) -> None:
    """Remove access (also used to decline a pending request). The creator's membership cannot be revoked."""
    t = _target(conn, profile, membership_id)
    if not perm.can(conn, actor, profile, perm.REVOKE_MEMBER, t) or t["status"] == perm.REVOKED:
        raise NotAllowed()
    conn.execute("UPDATE memberships SET status = 'revoked', can_add_notes = 0, updated_at = ? WHERE id = ?",
                 (iso(ctx.now()), t["id"]))
    log.info("member revoked membership_id=%s by user_id=%s", t["id"], actor["id"])


def change_role(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, membership_id: int,
                new_role: str) -> None:
    t = _target(conn, profile, membership_id)
    if not perm.can(conn, actor, profile, perm.CHANGE_ROLE, t) or t["status"] == perm.REVOKED:
        raise NotAllowed()
    if new_role not in perm.INVITABLE_ROLES:
        raise ValidationFailed({"role": "Choose caregiver, patient or child."})
    conn.execute(
        "UPDATE memberships SET role = ?, can_add_notes = CASE WHEN ? = 'caregiver' THEN can_add_notes ELSE 0 END, "
        "updated_at = ? WHERE id = ?", (new_role, new_role, iso(ctx.now()), t["id"]))


def set_can_add_notes(conn: sqlite3.Connection, ctx: Ctx, actor: sqlite3.Row, profile: sqlite3.Row, membership_id: int,
                      allowed: bool) -> None:
    t = _target(conn, profile, membership_id)
    if not perm.can(conn, actor, profile, perm.SET_CAN_ADD_NOTES, t) or t["status"] == perm.REVOKED:
        raise NotAllowed()
    if t["role"] != perm.CAREGIVER:
        raise NotAllowed("Only caregivers can be allowed to add notes.")
    conn.execute("UPDATE memberships SET can_add_notes = ?, updated_at = ? WHERE id = ?",
                 (1 if allowed else 0, iso(ctx.now()), t["id"]))


def first_name(display_name: str) -> str:
    return display_name.split()[0] if display_name.split() else display_name


def list_members(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> list[dict[str, Any]]:
    """Members visible to ``actor``, with only the fields their role may see (filtered here, on the server).

    creator    : everyone incl. pending and revoked, with email, status, permissions
    caregiver  : active members (name, role, relationship) plus pending *child* requests they may approve
    patient    : active members (name, role, relationship)
    child      : active members' first names only
    """
    me = perm.get_membership(conn, actor["id"], profile["id"])
    if me is None or me["status"] != perm.ACTIVE or not perm.can(conn, actor, profile, perm.VIEW_CIRCLE):
        raise NotAllowed()
    rows = conn.execute(
        "SELECT m.id AS membership_id, m.role, m.status, m.can_add_notes, m.relationship_label, m.created_at, "
        "u.display_name, u.email FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.profile_id = ? "
        "ORDER BY (m.role = 'creator') DESC, m.id", (profile["id"],)).fetchall()
    level = perm.circle_view_level(me["role"])
    out: list[dict[str, Any]] = []
    for r in rows:
        if level == "full":
            out.append({"membership_id": r["membership_id"], "display_name": r["display_name"], "email": r["email"],
                        "role": r["role"], "status": r["status"], "can_add_notes": bool(r["can_add_notes"]),
                        "relationship_label": r["relationship_label"], "is_creator": r["role"] == perm.CREATOR})
        elif level == "names_roles":
            if r["status"] == perm.ACTIVE:
                out.append({"display_name": r["display_name"], "role": r["role"],
                            "relationship_label": r["relationship_label"], "is_creator": r["role"] == perm.CREATOR})
            elif me["role"] == perm.CAREGIVER and r["status"] == perm.PENDING and r["role"] == perm.CHILD:
                out.append({"membership_id": r["membership_id"], "display_name": r["display_name"], "role": r["role"],
                            "status": r["status"], "relationship_label": r["relationship_label"], "is_creator": False})
        elif r["status"] == perm.ACTIVE:
            out.append({"first_name": first_name(r["display_name"])})
    if level != "first_names":
        # F-12: flag members who share a name, comparing only the members this viewer can already see
        counts: dict[str, int] = {}
        for m in out:
            counts[name_key(m["display_name"])] = counts.get(name_key(m["display_name"]), 0) + 1
        for m in out:
            m["same_name"] = counts[name_key(m["display_name"])] > 1
    return out


def patient_label(profile: sqlite3.Row, role: str) -> str:
    """How the patient is named to this role: children see the preferred name (or a first name), others the full name."""
    if role == perm.CHILD:
        return profile["preferred_name"] or first_name(profile["display_name"])
    return profile["display_name"]


def get_info(conn: sqlite3.Connection, actor: sqlite3.Row, profile: sqlite3.Row) -> dict[str, Any]:
    """The read-only profile page: only creator, caregiver and patient may see it (never the child role)."""
    if not perm.can(conn, actor, profile, perm.VIEW_INFO):
        raise NotAllowed()
    return {"patient_id": profile["patient_id"], "display_name": profile["display_name"],
            "preferred_name": profile["preferred_name"], "year_of_birth": profile["year_of_birth"],
            "care_notes": profile["care_notes"]}
