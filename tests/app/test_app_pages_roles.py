"""Every circle page for every kind of visitor, and proof that the server never hands forbidden data to a template."""

from __future__ import annotations

import re

import pytest

from app import circle, notes
from app.web import render as render_mod
from conftest import Site
from fcc_testlib import PASSWORD, SOURCE_TEXT, assert_clean_page, csrf_from

from fcc_testlib import PATIENT_NAME, SOURCE_MARK, TITLE


PAGES = ["", "/info", "/circle", "/summaries", "/notes"]
ACTIVE = ["owner", "caregiver", "caregiver_no_notes", "patient", "child"]
# expected status of each page by role: dashboard, info, circle, summaries, notes
EXPECT = {
    "owner": [200, 200, 200, 200, 200],
    "caregiver": [200, 200, 200, 200, 200],
    "caregiver_no_notes": [200, 200, 200, 200, 403],
    "patient": [200, 200, 200, 200, 403],
    "child": [200, 403, 200, 200, 403],
}


@pytest.mark.parametrize("who", ACTIVE)
def test_page_access_by_role(full, who):
    got = [full.site[who].get(f"/p/{full.pid}{suffix}").status_code for suffix in PAGES]
    assert got == EXPECT[who], (who, got)


def test_pending_and_revoked_members_only_ever_see_their_status_page(full):
    for who, headline in (("pending", "Waiting for approval"), ("pending_child", "Waiting for approval"), ("revoked", "Access removed")):
        for suffix in PAGES + ["/created"]:
            r = full.site[who].get(f"/p/{full.pid}{suffix}")
            if suffix == "/created":
                assert r.status_code == 404
                continue
            assert r.status_code == 200 and headline in r.text, (who, suffix)
            for leak in (PATIENT_NAME, "Grandma", SOURCE_MARK, TITLE, "Olivia", "Cara", "Amoxicillin", "Review flags"):
                assert leak not in r.text, (who, suffix, leak)


def test_strangers_and_unknown_ids_get_the_same_404_everywhere(full):
    strip = lambda t: re.sub(r'value="[0-9a-f]{64}"', "", t)
    for suffix in PAGES + ["/created", "/summaries?tab=child"]:
        real = full.site["stranger"].get(f"/p/{full.pid}{suffix}")
        fake = full.site["stranger"].get(f"/p/FCC-AAAA-AAAA{suffix}")
        assert real.status_code == fake.status_code == 404, suffix
        assert strip(real.text) == strip(fake.text) and PATIENT_NAME not in real.text


def test_anonymous_visitors_are_sent_to_login(full):
    for suffix in PAGES + ["/created"]:
        r = full.anon.get(f"/p/{full.pid}{suffix}")
        assert r.status_code == 303 and r.headers["location"] == "/login", suffix
    assert full.anon.get("/settings").status_code == 303


def test_unauthorized_page(full):
    r = full.site["child"].get("/unauthorized")
    assert r.status_code == 403 and "do not have access" in r.text
    assert_clean_page(r.text)
    r = full.site["child"].get(f"/p/{full.pid}/info")
    assert r.status_code == 403 and "do not have access" in r.text and PATIENT_NAME not in r.text.split("<main")[1]


# --- nothing forbidden is rendered ---------------------------------------------------------------------------
CHILD_FORBIDDEN = [SOURCE_MARK, "Amoxicillin", "Ibuprofen", "500 mg", "200 mg", TITLE, "Review flags", "retention", "model_id",
                   "olivia@example.test", "@example.test", "Patient summary", "Caregiver checklist", "Giving", "Give ",
                   PATIENT_NAME, "Olivia Owner", "Cara Carer", "Dan Danielson", "Pat Patientson", "Kid Kidson", "Wendy", "Rex", "Pip"]
PATIENT_FORBIDDEN = [SOURCE_MARK, TITLE, "Review flags", "retention", "model_id", "Caregiver checklist", "Give Amoxicillin",
                     "Child explanation", "@example.test", "Wendy", "Rex", "Pip"]


@pytest.mark.parametrize("suffix", ["", "/circle", "/summaries", "/summaries?tab=patient", "/summaries?tab=caregiver",
                                    "/summaries?tab=child", "/notes", "/info"])
def test_child_pages_contain_nothing_the_child_may_not_see(full, suffix):
    r = full.site["child"].get(f"/p/{full.pid}{suffix}")
    body = r.text.split("<main", 1)[1].split("</main>")[0] if "<main" in r.text else r.text
    for leak in CHILD_FORBIDDEN:
        assert leak not in body, (suffix, leak)
    nav = r.text.split("</header>")[0]
    assert "Grandma" in nav or r.status_code != 200                 # the child sees the preferred name, never the full name
    assert PATIENT_NAME not in r.text


@pytest.mark.parametrize("suffix", ["", "/circle", "/summaries", "/summaries?tab=caregiver", "/summaries?tab=child", "/notes", "/info"])
def test_patient_pages_contain_nothing_the_patient_may_not_see(full, suffix):
    r = full.site["patient"].get(f"/p/{full.pid}{suffix}")
    body = r.text.split("<main", 1)[1].split("</main>")[0] if "<main" in r.text else r.text
    for leak in PATIENT_FORBIDDEN:
        assert leak not in body, (suffix, leak)


def test_the_child_sees_only_the_child_explanation_the_patient_only_the_summary(full):
    child = full.site["child"].get(f"/p/{full.pid}/summaries?tab=patient")
    assert "tiny helpers" in child.text and "Patient summary" not in child.text and "strep throat" not in child.text
    assert "aria-label=\"Choose a version\"" not in child.text                  # only one version: no tabs
    patient = full.site["patient"].get(f"/p/{full.pid}/summaries?tab=child")
    assert "strep throat" in patient.text and "tiny helpers" not in patient.text and "Child explanation" not in patient.text


def test_earlier_notes_are_not_reachable_by_patient_or_child(full):
    nid = full.p["id"]
    for who in ("patient", "child"):
        r = full.site[who].get(f"/p/{full.pid}/summaries?note=1")
        assert r.status_code == 403 and SOURCE_MARK not in r.text and "Amoxicillin" not in r.text


# --- what the server hands to templates -------------------------------------------------------------------------
@pytest.fixture
def contexts(monkeypatch):
    seen: list[dict] = []
    original = render_mod.templates.TemplateResponse

    def spy(request, name, context=None, *a, **kw):
        seen.append({"template": name, **(context or {})})
        return original(request, name, context, *a, **kw)
    monkeypatch.setattr(render_mod.templates, "TemplateResponse", spy)
    return seen


def flatten(obj, depth=0) -> str:
    """Every string reachable from a template context (dicts, lists, rows), including keys."""
    if depth > 6:
        return ""
    if isinstance(obj, dict):
        return " ".join(str(k) + " " + flatten(v, depth + 1) for k, v in obj.items() if k not in ("request",))
    if isinstance(obj, (list, tuple, set)):
        return " ".join(flatten(v, depth + 1) for v in obj)
    if hasattr(obj, "keys") and not isinstance(obj, str):
        return " ".join(str(k) + " " + flatten(obj[k], depth + 1) for k in obj.keys())
    return str(obj)


@pytest.mark.parametrize("suffix", ["", "/circle", "/summaries", "/summaries?tab=child", "/summaries?tab=patient"])
def test_child_template_contexts_never_contain_forbidden_data(full, contexts, suffix):
    contexts.clear()
    full.site["child"].get(f"/p/{full.pid}{suffix}")
    assert contexts, "no template rendered"
    blob = flatten(contexts)
    for leak in (SOURCE_MARK, "Amoxicillin", "500 mg", TITLE, "olivia@example.test", "password_hash", "caregiver_checklist",
                 "patient_summary", "flags", PATIENT_NAME, "Giving", "strep throat"):
        assert leak not in blob, (suffix, leak)
    others = flatten([{k: v for k, v in c.items() if k != "user"} for c in contexts])      # the viewer's own account row is theirs
    assert "@" not in others, "an email address reached a child's template context"


@pytest.mark.parametrize("suffix", ["", "/circle", "/summaries"])
def test_patient_template_contexts_never_contain_forbidden_data(full, contexts, suffix):
    contexts.clear()
    full.site["patient"].get(f"/p/{full.pid}{suffix}")
    blob = flatten(contexts)
    for leak in (SOURCE_MARK, TITLE, "olivia@example.test", "password_hash", "caregiver_checklist", "child_explanation",
                 "'flags'", "tiny helpers", "Give Amoxicillin"):
        assert leak not in blob, (suffix, leak)
    others = flatten([{k: v for k, v in c.items() if k != "user"} for c in contexts])
    assert "@" not in others, "an email address reached a patient's template context"


def test_member_rows_given_to_templates_are_role_filtered_at_the_source(full, contexts):
    contexts.clear()
    full.site["child"].get(f"/p/{full.pid}/circle")
    members = [c for c in contexts if c["template"] == "circle.html"][0]["members"]
    assert members and all(set(m) == {"first_name"} for m in members)
    contexts.clear()
    full.site["patient"].get(f"/p/{full.pid}/circle")
    members = [c for c in contexts if c["template"] == "circle.html"][0]["members"]
    assert all("email" not in m and "membership_id" not in m and "can_add_notes" not in m for m in members)


def test_no_response_header_cookie_or_redirect_leaks_note_data(full):
    for who in ("child", "patient"):
        for suffix in PAGES + ["/summaries?tab=child"]:
            r = full.site[who].get(f"/p/{full.pid}{suffix}")
            haystack = " ".join(f"{k}: {v}" for k, v in r.headers.items()) + " " + " ".join(r.headers.get_list("set-cookie"))
            assert SOURCE_MARK not in haystack and "Amoxicillin" not in haystack and TITLE not in haystack


# --- navigation shows the open circle and only what the role may use --------------------------------------------
@pytest.mark.parametrize("who,links,absent", [
    ("owner", ["Dashboard", "Summaries", "Care circle", "Notes", "Info", "Settings"], []),
    ("caregiver", ["Dashboard", "Summaries", "Care circle", "Notes", "Info"], []),
    ("caregiver_no_notes", ["Dashboard", "Summaries", "Care circle", "Info"], ["Notes"]),
    ("patient", ["Dashboard", "Summaries", "Care circle", "Info"], ["Notes"]),
    ("child", ["Dashboard", "Summaries", "Care circle"], ["Notes", "Info"]),
])
def test_navigation_is_limited_to_what_the_role_can_open(full, who, links, absent):
    html = full.site[who].get(f"/p/{full.pid}").text
    nav = html.split("</header>")[0]
    for label in links:
        assert re.search(rf">\s*{label}\s*<", nav) or label in nav, (who, label)
    for label in absent:
        assert not re.search(rf"</svg>\s*{label}\s*</a>", nav), (who, label)
    role = {"owner": "creator", "caregiver_no_notes": "caregiver"}.get(who, who)
    assert "Care circle:" in nav and f"chip-role-{role}" in nav
    assert 'aria-current="page"' in nav


def test_navigation_names_the_open_circle_per_role_and_lists_my_circles(full):
    nav = full.site["owner"].get(f"/p/{full.pid}").text.split("</header>")[0]
    assert PATIENT_NAME in nav and "All my care circles" in nav
    kid = full.site["child"].get(f"/p/{full.pid}").text.split("</header>")[0]
    assert "Grandma" in kid and PATIENT_NAME not in kid


def test_every_rendered_page_meets_the_structure_accessibility_and_csp_rules(full):
    for who in ACTIVE:
        for suffix in PAGES + ["/summaries?tab=caregiver", "/summaries?tab=child"]:
            full.site[who].get(f"/p/{full.pid}{suffix}")
        full.site[who].get("/settings"); full.site[who].get("/profiles")
    pages = [h for s in full.site.values() for h in s.pages]
    assert len(pages) > 40
    for html in pages:
        assert_clean_page(html)
