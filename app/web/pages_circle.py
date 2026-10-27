"""Pages inside a care circle: dashboard, info, care circle management, summaries, notes.

Template contexts are built ONLY from the role-filtered service functions (``outputs.latest_outputs``,
``circle.list_members`` ...), never from raw database rows, so a field a role may not see is never handed to a
template in the first place. The ``caps`` dict only drives which buttons are drawn; every action is re-checked by
the service layer when it is submitted.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response

from app import circle, notes as notes_svc, outputs, permissions as perm
from app.errors import AppError, NotAllowed, NotFound, QueueFull, ValidationFailed
from app.web import present
from app.web.deps import get_db
from app.web.pages import need_user
from app.web.render import StatusPage, redirect, render, verify_page_csrf

router = APIRouter()


def scope(patient_id: str, conn: sqlite3.Connection = Depends(get_db), user: sqlite3.Row = Depends(need_user)):
    """(user, profile, membership) for an ACTIVE member. Unknown ID and non-member are both 404; pending/revoked
    members get only their status page."""
    profile = circle.get_profile(conn, patient_id)
    m = perm.get_membership(conn, user["id"], profile["id"]) if profile is not None else None
    if profile is None or m is None:
        raise NotFound()
    if m["status"] != perm.ACTIVE:
        raise StatusPage(profile, m)
    return user, profile, m


def caps(conn, user, profile) -> dict[str, bool]:
    c = lambda a: perm.can(conn, user, profile, a)       # noqa: E731
    return {"add_note": c(perm.ADD_NOTE), "delete_note": c(perm.DELETE_NOTE), "invite": c(perm.INVITE_MEMBER),
            "tick": c(perm.TICK_CHECKLIST), "view_info": c(perm.VIEW_INFO), "delete_profile": c(perm.DELETE_PROFILE),
            "history": c(perm.VIEW_OUTPUT_HISTORY), "source": c(perm.VIEW_SOURCE_NOTE)}


def page(request, name, conn, user, profile, m, **ctx):
    ctx.setdefault("caps", caps(conn, user, profile))
    ctx.setdefault("profile_id", profile["patient_id"])
    return render(request, name, conn=conn, user=user, circle_info=(profile, m), **ctx)


# ----------------------------------------------------------------------------------------------- dashboard
@router.get("/p/{patient_id}")
def dashboard(request: Request, s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    out = outputs.latest_outputs(conn, user, profile)
    members = circle.list_members(conn, user, profile)
    people = [x for x in members if x.get("status", "active") == "active"]     # first-name-only entries have no status
    return page(request, "dashboard.html", conn, user, profile, m, out=out, gen=out["generation"], members=members, people=people,
                label=circle.patient_label(profile, m["role"]), role=m["role"], role_label=m["role"].capitalize())


# --------------------------------------------------------------------------------------------------- info
@router.get("/p/{patient_id}/info")
def info(request: Request, s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    data = circle.get_info(conn, user, profile)                     # NotAllowed (403 page) for the child role
    return page(request, "info.html", conn, user, profile, m, info=data)


# ------------------------------------------------------------------------------------------- care circle
def _circle_page(request, conn, user, profile, m, *, notice=None, new_invite=None, status_code=200, values=None, errors=None):
    profile = circle.get_profile(conn, profile["patient_id"]) or profile      # fresh row: a pause may just have changed
    members = circle.list_members(conn, user, profile)
    ctx = request.app.state.ctx
    invitations = circle.list_invitations(conn, ctx, user, profile) if perm.can(conn, user, profile, perm.INVITE_MEMBER) else []
    return page(request, "circle.html", conn, user, profile, m, members=members, level=perm.circle_view_level(m["role"]),
                invitations=invitations, notice=notice, new_invite=new_invite, values=values or {}, errors=errors or {},
                status_code=status_code, label=circle.patient_label(profile, m["role"]),
                invitable_roles=perm.INVITABLE_ROLES, invitations_paused=bool(profile["invitations_paused"]))


@router.get("/p/{patient_id}/circle")
def circle_page(request: Request, s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    return _circle_page(request, conn, user, profile, m)


def _act(request, conn, s, csrf_token, success, fn, *, values=None):
    """Run a management action, then show the circle page with a success or error notice."""
    user, profile, m = s
    verify_page_csrf(request, csrf_token, authenticated=True)
    try:
        result = fn(user, profile)
    except ValidationFailed as exc:
        return _circle_page(request, conn, user, profile, m, notice=("error", "Please check the form", "; ".join(exc.errors.values())),
                            status_code=422, values=values, errors=exc.errors)
    except AppError as exc:
        status = 403 if isinstance(exc, NotAllowed) else 404 if isinstance(exc, NotFound) else 400
        return _circle_page(request, conn, user, profile, m, notice=("error", "That did not work", exc.message), status_code=status)
    return _circle_page(request, conn, user, profile, m, notice=("success", success, ""), new_invite=result if isinstance(result, dict) else None)


@router.post("/p/{patient_id}/circle/invite")
def invite(request: Request, role: str = Form(""), note: str = Form(""), csrf_token: str = Form(""),
           s=Depends(scope), conn=Depends(get_db)) -> Response:
    ctx = request.app.state.ctx

    def run(user, profile):
        meta, code = circle.create_invitation(conn, ctx, user, profile, role=role, note=note)
        return {"code": code, "role": meta["role"], "expires_at": meta["expires_at"], "note": meta["note"],
                "patient_id": profile["patient_id"]}
    return _act(request, conn, s, csrf_token, "Invitation created", run, values={"role": role, "note": note})


@router.post("/p/{patient_id}/circle/pause")
def pause_invitations(request: Request, paused: str = Form(""), csrf_token: str = Form(""), s=Depends(scope),
                      conn=Depends(get_db)) -> Response:
    want = paused == "1"
    return _act(request, conn, s, csrf_token, "Invitations paused" if want else "Invitations resumed",
                lambda u, p: circle.set_invitations_paused(conn, request.app.state.ctx, u, p, want))


@router.post("/p/{patient_id}/circle/invitations/{invitation_id}/revoke")
def revoke_invitation(request: Request, invitation_id: int, csrf_token: str = Form(""), s=Depends(scope),
                      conn=Depends(get_db)) -> Response:
    return _act(request, conn, s, csrf_token, "Invitation cancelled",
                lambda u, p: circle.revoke_invitation(conn, u, p, invitation_id, request.app.state.ctx))


@router.post("/p/{patient_id}/circle/members/{membership_id}/approve")
def approve(request: Request, membership_id: int, csrf_token: str = Form(""), s=Depends(scope), conn=Depends(get_db)) -> Response:
    return _act(request, conn, s, csrf_token, "Request approved",
                lambda u, p: circle.approve_member(conn, request.app.state.ctx, u, p, membership_id))


@router.post("/p/{patient_id}/circle/members/{membership_id}/revoke")
def revoke(request: Request, membership_id: int, csrf_token: str = Form(""), s=Depends(scope), conn=Depends(get_db)) -> Response:
    return _act(request, conn, s, csrf_token, "Access removed",
                lambda u, p: circle.revoke_member(conn, request.app.state.ctx, u, p, membership_id))


@router.post("/p/{patient_id}/circle/members/{membership_id}/role")
def change_role(request: Request, membership_id: int, role: str = Form(""), csrf_token: str = Form(""), s=Depends(scope),
                conn=Depends(get_db)) -> Response:
    return _act(request, conn, s, csrf_token, "Role changed",
                lambda u, p: circle.change_role(conn, request.app.state.ctx, u, p, membership_id, role))


@router.post("/p/{patient_id}/circle/members/{membership_id}/notes")
def toggle_notes(request: Request, membership_id: int, allowed: str = Form("0"), csrf_token: str = Form(""),
                 s=Depends(scope), conn=Depends(get_db)) -> Response:
    return _act(request, conn, s, csrf_token, "Permission updated",
                lambda u, p: circle.set_can_add_notes(conn, request.app.state.ctx, u, p, membership_id, allowed == "1"))


@router.post("/p/{patient_id}/delete")
def delete_profile(request: Request, confirm: str = Form(""), csrf_token: str = Form(""), s=Depends(scope),
                   conn=Depends(get_db)) -> Response:
    user, profile, m = s
    verify_page_csrf(request, csrf_token, authenticated=True)
    if not perm.can(conn, user, profile, perm.DELETE_PROFILE):
        raise NotAllowed()
    if confirm.strip().upper() != profile["patient_id"]:
        return _circle_page(request, conn, user, profile, m, status_code=422,
                            notice=("error", "The care circle was not deleted", "Type the patient ID exactly to confirm."))
    circle.delete_profile(conn, user, profile)
    return redirect("/profiles")


# ---------------------------------------------------------------------------------------------- summaries
TAB_LABELS = {"patient": ("Patient", "heart"), "caregiver": ("Caregiver", "list-check"), "child": ("Child", "sparkle")}
TAB_FIELD = {"patient": "patient_summary", "caregiver": "caregiver_checklist", "child": "child_explanation"}


@router.get("/p/{patient_id}/summaries")
def summaries(request: Request, tab: str = "", note: int = 0, s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    if note:                                                       # an earlier note's outputs (creator/caregiver only)
        out = outputs.outputs_for_note(conn, user, profile, note)
        out["generation"] = outputs.generation_state(conn, user, profile)
    else:
        out = outputs.latest_outputs(conn, user, profile)
    tabs = [t for t, field in TAB_FIELD.items() if field in out]
    current = tab if tab in tabs else (tabs[0] if tabs else "")
    history = outputs.history(conn, user, profile) if perm.can(conn, user, profile, perm.VIEW_OUTPUT_HISTORY) else []
    back = f"/p/{profile['patient_id']}/summaries?tab={current}" + (f"&note={note}" if note else "")
    extra: dict = {}                                             # keys exist ONLY for roles allowed to see them
    if out.get("available") and "note" in out:
        extra["source"] = notes_svc.get_note_source(conn, user, profile, out["note"]["id"])
    return page(request, "summaries.html", conn, user, profile, m, out=out, gen=out.get("generation", {"state": "none"}),
                tabs=tabs, tab=current, tab_labels=TAB_LABELS, history=history, back=back,
                viewing_note=note, label=circle.patient_label(profile, m["role"]), **extra)


@router.post("/p/{patient_id}/checklist/{note_id}/{index}")
def tick(request: Request, note_id: int, index: int, ticked: str = Form("1"), back: str = Form(""),
         csrf_token: str = Form(""), s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    verify_page_csrf(request, csrf_token, authenticated=True)
    outputs.set_tick(conn, request.app.state.ctx, user, profile, note_id, index, ticked == "1")
    base = f"/p/{profile['patient_id']}/summaries"
    target = back if back.startswith(base) and "//" not in back[len(base):] and "\n" not in back else f"{base}?tab=caregiver"
    return redirect(f"{target}#item-{index}")


# ------------------------------------------------------------------------------------------------ notes
def _notes_page(request, conn, user, profile, m, *, values=None, errors=None, notice=None, status_code=200):
    listing = notes_svc.list_notes(conn, user, profile)
    active = next((n for n in listing if n["status"] in ("queued", "running")), None)
    return page(request, "notes.html", conn, user, profile, m, notes=listing, active=active, values=values or {},
                errors=errors or {}, notice=notice, status_code=status_code, max_chars=request.app.state.settings.max_note_chars)


@router.get("/p/{patient_id}/notes")
def notes_page(request: Request, added: int = 0, s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    if not perm.can(conn, user, profile, perm.ADD_NOTE):
        raise NotAllowed()
    notice = ("success", "Note added", "It is being prepared. This page updates by itself, and takes about a minute.") if added else None
    return _notes_page(request, conn, user, profile, m, notice=notice)


@router.post("/p/{patient_id}/notes")
async def add_note(request: Request, title: str = Form(""), text: str = Form(""), file: UploadFile | None = File(None),
                   csrf_token: str = Form(""), s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    verify_page_csrf(request, csrf_token, authenticated=True)
    settings = request.app.state.settings
    try:
        data = await file.read(settings.max_note_chars * 4 + 1) if file is not None and file.filename else None
        t, body = notes_svc.resolve_submission(settings, title=title, text=text, filename=file.filename if file is not None else None, data=data)
        notes_svc.add_note(conn, request.app.state.ctx, request.app.state.runner, user, profile, title=t, text=body)
    except ValidationFailed as exc:
        return _notes_page(request, conn, user, profile, m, values={"title": title, "text": text}, errors=exc.errors, status_code=422)
    except QueueFull as exc:
        return _notes_page(request, conn, user, profile, m, values={"title": title, "text": text},
                           notice=("warning", "Your note was not added yet", exc.message), status_code=429)
    return redirect(f"/p/{profile['patient_id']}/notes?added=1")


@router.post("/p/{patient_id}/notes/{note_id}/delete")
def delete_note(request: Request, note_id: int, csrf_token: str = Form(""), s=Depends(scope), conn=Depends(get_db)) -> Response:
    user, profile, m = s
    verify_page_csrf(request, csrf_token, authenticated=True)
    notes_svc.delete_note(conn, user, profile, note_id)
    return redirect(f"/p/{profile['patient_id']}/notes")
