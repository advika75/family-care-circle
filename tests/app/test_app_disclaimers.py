"""The visible prototype notice: on every page footer (public and signed-in) and on the welcome page."""

from __future__ import annotations

import pytest

from conftest import Site
from test_app_security_review import routes_of

NOTICE = "Prototype. Not for real patient data."
PUBLIC = ("/", "/login", "/signup")
ROLES = ("owner", "caregiver", "patient", "child")


def _html_get_routes(app) -> list[str]:
    return sorted(p for m, p in routes_of(app) if m == "GET" and not p.startswith("/api/"))


def _footer(html: str) -> str:
    assert "<footer" in html
    return html.split("<footer", 1)[1]


def test_every_public_page_has_the_notice_in_its_footer(app):
    s = Site(app)
    for url in PUBLIC:
        r = s.get(url)
        assert r.status_code == 200 and NOTICE in _footer(r.text), url


def test_welcome_page_states_the_notice_in_its_body_too(app):
    html = Site(app).get("/").text
    body = html.split("<footer", 1)[0]
    assert NOTICE in body and "not for real patient data" in body


@pytest.mark.parametrize("role", ROLES)
def test_every_signed_in_html_page_has_the_notice_in_its_footer(full, app, role):
    seen = 0
    for path in _html_get_routes(app):
        url = path.replace("{patient_id}", full.pid)
        r = full.site[role].get(url)
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        assert NOTICE in _footer(r.text), (role, url, r.status_code)
        seen += 1
    assert seen >= 8, (role, seen)


def test_the_route_list_covers_the_known_pages(app):
    paths = _html_get_routes(app)
    for expected in ("/", "/login", "/signup", "/profiles", "/settings", "/join", "/p/{patient_id}",
                     "/p/{patient_id}/summaries", "/p/{patient_id}/notes", "/p/{patient_id}/circle"):
        assert expected in paths
