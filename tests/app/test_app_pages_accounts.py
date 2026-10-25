"""Public pages, signup, login, logout: behaviour, cookies, CSRF, redirects."""

from __future__ import annotations

import pytest

from fcc_testlib import PASSWORD, assert_clean_page, csrf_from


def cookie_headers(resp) -> list[str]:
    return resp.headers.get_list("set-cookie")


# --- welcome ----------------------------------------------------------------------------------------------
def test_welcome_page_has_the_two_clear_actions_and_the_footer(site):
    r = site.get("/")
    assert r.status_code == 200
    assert 'href="/profiles/new"' in r.text and "Create a Patient Profile" in r.text
    assert 'href="/join"' in r.text and "Join an Existing Care Circle" in r.text
    assert "not for real patient data" in r.text.lower() and "not medical advice" in r.text.lower()
    assert_clean_page(r.text)


@pytest.mark.parametrize("url", ["/", "/signup", "/login", "/nope"])
def test_public_pages_are_clean_html(site, url):
    r = site.get(url)
    assert r.headers["content-type"].startswith("text/html")
    assert_clean_page(r.text)
    assert "unsafe-inline" not in r.headers["content-security-policy"]


def test_static_assets_are_served_with_security_headers(site):
    for path, ctype in (("/static/css/tokens.css", "text/css"), ("/static/css/base.css", "text/css"),
                        ("/static/js/app.js", "javascript"), ("/static/img/favicon.svg", "image/svg")):
        r = site.get(path)
        assert r.status_code == 200 and ctype in r.headers["content-type"], path
        assert r.headers["x-content-type-options"] == "nosniff"
    assert site.get("/static/../app/config.py").status_code in (404, 400)
    assert site.get("/static/%2e%2e/config.py").status_code == 404


def test_javascript_has_no_dynamic_code_execution():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / "app" / "static" / "js" / "app.js").read_text()
    for banned in ("eval(", "new Function", "innerHTML", "document.write", "outerHTML"):
        assert banned not in js, banned


# --- signup -------------------------------------------------------------------------------------------------
def test_signup_logs_you_in_and_lands_on_the_empty_state(site, conn):
    r = site.signup()
    assert r.status_code == 303 and r.headers["location"] == "/profiles"
    cookies = [c for c in cookie_headers(r) if c.startswith("fcc_session=")]
    assert len(cookies) == 1
    flags = cookies[0].lower()
    assert "httponly" in flags and "samesite=lax" in flags and "path=/" in flags and "secure" not in flags and "max-age=" in flags
    page = site.get("/profiles")
    assert page.status_code == 200 and "You are not in a care circle yet" in page.text
    assert 'href="/profiles/new"' in page.text and 'href="/join"' in page.text            # empty state with both actions
    assert_clean_page(page.text)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_session_cookie_is_secure_when_https_is_enabled(settings, ctx, runner):
    from dataclasses import replace
    from app.web.main import create_app
    from conftest import Site
    s = Site(create_app(replace(settings, https=True), ctx=ctx, runner=runner, start_worker=False), https=True)
    r = s.signup()
    assert any("secure" in c.lower() for c in cookie_headers(r) if c.startswith("fcc_session="))
    fresh = Site(s.client.app, https=True)
    anon = [c for c in fresh.get("/signup").headers.get_list("set-cookie") if c.startswith("fcc_anon=")]
    assert anon and "secure" in anon[0].lower()                                  # the anonymous CSRF cookie is Secure too
    assert "strict-transport-security" in r.headers


def test_signup_validation_errors_are_shown_per_field_and_the_password_is_never_echoed(site, conn):
    r = site.signup(name=" ", email="not-an-email", password="short-pw")
    assert r.status_code == 422
    for message in ("Please enter a name.", "Enter a valid email address.", "Use at least 12 characters."):
        assert message in r.text
    assert 'aria-invalid="true"' in r.text and 'role="alert"' in r.text
    assert "short-pw" not in r.text
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert_clean_page(r.text)


def test_signup_keeps_what_you_typed_except_the_password(site):
    r = site.signup(name="Ann <b>Example</b>", email="ann@example.test", password="x")
    assert 'value="Ann &lt;b&gt;Example&lt;/b&gt;"' in r.text and 'value="ann@example.test"' in r.text
    assert "<b>Example</b>" not in r.text


def test_signup_with_an_existing_email_is_a_generic_refusal(site):
    site.signup()
    other = type(site)(site.client.app)
    r = other.signup(name="Someone Else")
    assert r.status_code == 400 and "We could not create that account" in r.text
    assert "sam@example.test" not in r.text.split("<form")[0]


# --- login / logout -----------------------------------------------------------------------------------------
def test_login_success_and_logout_invalidate_the_session(site, app, conn):
    site.signup()
    me = type(site)(app)
    r = me.login("sam@example.test")
    assert r.status_code == 303 and r.headers["location"] == "/profiles"
    assert me.get("/profiles").status_code == 200
    old_cookie = me.client.cookies.get("fcc_session")
    token = csrf_from(me.get("/profiles").text)
    out = me.post("/logout", {"csrf_token": token})
    assert out.status_code == 303 and out.headers["location"] == "/"
    assert 'fcc_session=""' in "".join(cookie_headers(out)) or "max-age=0" in "".join(cookie_headers(out)).lower()
    me.client.cookies.set("fcc_session", old_cookie)                      # replaying the old cookie must fail
    assert me.get("/profiles").status_code == 303


def test_logout_requires_csrf_and_does_nothing_without_it(site):
    site.signup()
    r = site.post("/logout", {})
    assert r.status_code == 403
    assert site.get("/profiles").status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(site, app):
    site.signup()
    a = type(site)(app).login("sam@example.test", "not the right password")
    b = type(site)(app).login("ghost@example.test", "not the right password")
    assert a.status_code == b.status_code == 401
    msg = "Email or password is not correct."
    assert msg in a.text and msg in b.text
    def body(t):
        import re
        return re.sub(r'value="[0-9a-f]{64}"|value="[^"]*"', "", t)
    assert body(a.text).replace("sam@example.test", "") == body(b.text).replace("ghost@example.test", "")


def test_login_is_throttled_and_says_so(site, app):
    site.signup()
    s = type(site)(app)
    for _ in range(5):
        assert s.login("sam@example.test", "not the right password").status_code == 401
    r = s.login("sam@example.test", PASSWORD)
    assert r.status_code == 429 and "Too many attempts" in r.text


def test_logged_in_users_are_sent_away_from_login_and_signup(site):
    site.signup()
    for url in ("/login", "/signup"):
        assert site.get(url).headers["location"] == "/profiles"


@pytest.mark.parametrize("url,expected", [("/profiles", "/login"), ("/profiles/new", "/login?next=/profiles/new"),
                                          ("/join", "/login?next=/join"), ("/p/FCC-AAAA-AAAA", "/login"),
                                          ("/p/FCC-AAAA-AAAA/created", "/login")])
def test_protected_pages_redirect_to_login(site, url, expected):
    r = site.get(url)
    assert r.status_code == 303 and r.headers["location"] == expected


def test_next_is_an_allow_list_not_an_open_redirect(site, app):
    site.signup()
    for nxt, dest in (("/join", "/join"), ("/profiles/new", "/profiles/new"), ("https://evil.example", "/profiles"),
                      ("//evil.example", "/profiles"), ("/logout", "/profiles"), ("javascript:alert(1)", "/profiles")):
        s = type(site)(app)
        r = s.login("sam@example.test", next_=nxt)
        assert r.status_code == 303 and r.headers["location"] == dest, nxt


def test_login_form_carries_next_only_when_allowed(site):
    assert 'name="next" value="/join"' in site.get("/login?next=/join").text
    bad = site.get("/login?next=https://evil.example").text
    assert "evil.example" not in bad and 'name="next" value="/profiles"' in bad          # falls back to the safe default


# --- CSRF on the public forms -------------------------------------------------------------------------------
def test_anonymous_forms_set_an_httponly_samesite_cookie_and_embed_a_token(site):
    r = site.get("/login")
    anon = [c for c in cookie_headers(r) if c.startswith("fcc_anon=")]
    assert len(anon) == 1 and "httponly" in anon[0].lower() and "samesite=lax" in anon[0].lower()
    assert len(csrf_from(r.text)) == 64


@pytest.mark.parametrize("url", ["/login", "/signup"])
def test_public_posts_without_or_with_a_wrong_csrf_token_are_rejected(site, conn, url):
    data = {"display_name": "X Y", "email": "x@example.test", "password": PASSWORD}
    assert site.post(url, data).status_code == 403                                   # no cookie, no token
    site.get(url)
    assert site.post(url, {**data, "csrf_token": "0" * 64}).status_code == 403       # cookie but forged token
    other = type(site)(site.client.app)
    foreign = csrf_from(other.get(url).text)                                          # a token for someone else's cookie
    assert site.post(url, {**data, "csrf_token": foreign}).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_a_session_bound_token_is_not_valid_for_another_session(site, app):
    site.signup()
    a_token = csrf_from(site.get("/profiles").text)
    other = type(site)(app)
    other.signup(name="Other Person", email="other@example.test")
    r = other.post("/logout", {"csrf_token": a_token})
    assert r.status_code == 403
    assert other.get("/profiles").status_code == 200


def test_csrf_failure_page_is_helpful_html(site):
    r = site.post("/login", {"email": "a@b.test", "password": "x"})
    assert r.status_code == 403 and "could not be verified" in r.text.lower() and "text/html" in r.headers["content-type"]
    assert_clean_page(r.text)


# --- error pages --------------------------------------------------------------------------------------------
def test_unknown_pages_and_wrong_methods_get_friendly_html(site):
    r = site.get("/no/such/page")
    assert r.status_code == 404 and "We could not find that page" in r.text and r.headers["content-type"].startswith("text/html")
    assert site.post("/", {}).status_code == 405
    assert_clean_page(r.text)
    j = site.get("/api/no/such")
    assert j.status_code == 404 and j.headers["content-type"].startswith("application/json")
