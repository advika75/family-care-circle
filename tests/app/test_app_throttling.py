"""F-04 (account lockout), F-05 (trusted proxy / client IP), F-06 (memory bound), F-07 (sign-up and login rate limits)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app import accounts
from app.clientip import resolve_client_ip
from app.context import Ctx
from app.errors import InvalidCredentials, Throttled
from app.throttle import Throttle
from conftest import Site
from fcc_testlib import PASSWORD, csrf_from


def fail(conn, ctx, email, ip, n=1):
    for _ in range(n):
        with pytest.raises((InvalidCredentials, Throttled)):
            accounts.login(conn, ctx, email=email, password="definitely wrong one", client_ip=ip)


# ============================================================================================ F-04
def test_a_stranger_cannot_lock_the_owner_out_from_another_address(conn, ctx, world):
    owner = world.user("Owner", email="owner@example.test")
    fail(conn, ctx, "owner@example.test", "203.0.113.9", 5)                       # attacker: 5 wrong guesses
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="203.0.113.9")   # attacker is blocked
    user, token = accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="198.51.100.7")
    assert user["id"] == owner["id"] and token                                    # the real owner, elsewhere, gets in


def test_the_same_address_is_still_limited_per_account(conn, ctx, world):
    world.user("Owner", email="owner@example.test")
    fail(conn, ctx, "owner@example.test", "203.0.113.9", 5)
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="203.0.113.9")


def test_guessing_from_many_addresses_still_trips_an_account_wide_limit(conn, ctx, world):
    world.user("Owner", email="owner@example.test")
    for i in range(25):                                                           # 25 different addresses, 1 guess each
        fail(conn, ctx, "owner@example.test", f"198.51.100.{i + 1}")
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="192.0.2.1")


def test_a_correct_login_clears_only_that_addresses_counter(conn, ctx, world):
    world.user("Owner", email="owner@example.test")
    fail(conn, ctx, "owner@example.test", "198.51.100.7", 4)
    accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="198.51.100.7")
    fail(conn, ctx, "owner@example.test", "198.51.100.7", 4)                      # fresh allowance: not yet blocked


def test_without_a_known_address_the_per_account_limit_still_applies(conn, ctx, world):
    world.user("Owner", email="owner@example.test")
    fail(conn, ctx, "owner@example.test", "", 5)
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="owner@example.test", password=PASSWORD, client_ip="")


# ============================================================================================ F-05
TRUSTED = ("10.0.0.5", "10.0.0.6")


@pytest.mark.parametrize("peer,xff,expected", [
    ("203.0.113.9", "1.2.3.4", "203.0.113.9"),                                    # not a trusted proxy: header is ignored (spoofable)
    ("10.0.0.5", "198.51.100.7", "198.51.100.7"),                                 # trusted proxy: use the forwarded client
    ("10.0.0.5", "6.6.6.6, 198.51.100.7", "198.51.100.7"),                        # client-supplied prefix is ignored: right-most untrusted
    ("10.0.0.5", "198.51.100.7, 10.0.0.6", "198.51.100.7"),                       # a second trusted proxy in the chain is skipped
    ("10.0.0.5", "", ""),                                                         # trusted proxy but no header: unknown
    ("10.0.0.5", "not-an-ip", ""),                                                # garbage: unknown, never trusted
    ("10.0.0.5", "2001:db8::1", "2001:db8::1"),                                   # IPv6
    ("", "1.2.3.4", ""),                                                          # no peer at all
])
def test_client_ip_is_read_from_x_forwarded_for_only_behind_a_trusted_proxy(peer, xff, expected):
    assert resolve_client_ip(peer, xff, TRUSTED) == expected


def test_no_trusted_proxy_configured_means_the_header_is_never_used():
    assert resolve_client_ip("10.0.0.5", "198.51.100.7", ()) == "10.0.0.5"


def test_settings_read_trusted_proxies_from_the_environment():
    from app.config import Settings
    assert Settings.from_env({"APP_TRUSTED_PROXIES": "10.0.0.5, 10.0.0.6"}).trusted_proxies == ("10.0.0.5", "10.0.0.6")
    assert Settings().trusted_proxies == ()


def test_behind_a_trusted_proxy_one_users_failures_do_not_lock_out_another(settings, ctx, runner, world, conn, clock):
    from app.web.main import create_app
    proxied = replace(settings, trusted_proxies=("testclient",))                  # TestClient's peer address is "testclient"
    pctx = Ctx(settings=proxied, clock=clock)
    app = create_app(proxied, ctx=pctx, runner=runner, start_worker=False)
    world.user("Real User", email="real@example.test")
    attacker, victim = Site(app), Site(app)

    def login(site, email, password, ip):
        page = site.get("/login", headers={"x-forwarded-for": ip})
        return site.post("/login", {"email": email, "password": password, "csrf_token": csrf_from(page.text)}, headers={"x-forwarded-for": ip})
    for i in range(20):
        assert login(attacker, f"nobody{i}@example.test", "guess guess guess", "203.0.113.50").status_code in (401, 429)
    assert login(attacker, "real@example.test", PASSWORD, "203.0.113.50").status_code == 429       # the attacker's address is blocked
    assert login(victim, "real@example.test", PASSWORD, "198.51.100.77").status_code == 303        # another client is not


def test_without_the_setting_a_spoofed_header_buys_nothing(app, world):
    world.user("Real User", email="real@example.test")
    s = Site(app)
    for i in range(20):
        page = s.get("/login")
        s.post("/login", {"email": f"n{i}@example.test", "password": "guess guess guess", "csrf_token": csrf_from(page.text)},
               headers={"x-forwarded-for": f"198.51.100.{i}"})                     # rotating fake addresses
    page = s.get("/login")
    r = s.post("/login", {"email": "real@example.test", "password": PASSWORD, "csrf_token": csrf_from(page.text)},
               headers={"x-forwarded-for": "192.0.2.200"})
    assert r.status_code == 429


# ============================================================================================ F-06
def test_the_throttle_never_holds_more_keys_than_its_cap():
    now = [0.0]
    t = Throttle(lambda: now[0], window_seconds=900, max_keys=1000)
    for i in range(20_000):
        t.record_failure(f"login:email:flood{i}@x.example", f"login:ip:10.0.{i // 250}.{i % 250}")
    assert len(t._events) <= 1000


def test_idle_keys_are_swept_once_the_window_has_passed():
    now = [0.0]
    t = Throttle(lambda: now[0], window_seconds=900, max_keys=100_000)
    for i in range(3000):
        t.record_failure(f"k{i}")
    now[0] += 901
    t.record_failure("fresh")                                                     # any later activity triggers the sweep
    assert len(t._events) <= 10


def test_a_cap_never_unblocks_an_actively_attacked_key():
    now = [0.0]
    t = Throttle(lambda: now[0], window_seconds=900, max_keys=100)
    for _ in range(5):
        t.record_failure("victim")
    for i in range(5000):
        t.record_failure(f"noise{i}")
        t.blocked("victim", 5)                                                    # reading keeps it "recent"
    assert t.blocked("victim", 5)


def test_login_flood_of_distinct_emails_is_memory_bounded(conn, ctx):
    ctx.throttle.max_keys = 500
    for i in range(3000):
        with pytest.raises((InvalidCredentials, Throttled)):
            accounts.login(conn, ctx, email=f"flood{i}@x.example", password="x" * 12, client_ip=f"10.1.{i // 250}.{i % 250}")
    assert len(ctx.throttle._events) <= ctx.throttle.max_keys


# ============================================================================================ F-07
def test_signups_are_rate_limited_per_address(conn, ctx):
    for i in range(10):
        accounts.signup(conn, ctx, email=f"s{i}@example.test", display_name=f"Person {i}", password=PASSWORD, client_ip="203.0.113.9")
    with pytest.raises(Throttled):
        accounts.signup(conn, ctx, email="s11@example.test", display_name="Person 11", password=PASSWORD, client_ip="203.0.113.9")
    accounts.signup(conn, ctx, email="other@example.test", display_name="Elsewhere", password=PASSWORD, client_ip="198.51.100.2")
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 11


def test_signup_limit_recovers_after_the_window(conn, ctx, clock):
    for i in range(10):
        accounts.signup(conn, ctx, email=f"s{i}@example.test", display_name=f"Person {i}", password=PASSWORD, client_ip="203.0.113.9")
    clock.advance(minutes=16)
    accounts.signup(conn, ctx, email="later@example.test", display_name="Later", password=PASSWORD, client_ip="203.0.113.9")


def test_failed_signups_also_count_so_validation_probing_is_limited(conn, ctx):
    from app.errors import ValidationFailed
    for _ in range(10):
        with pytest.raises(ValidationFailed):
            accounts.signup(conn, ctx, email="bad", display_name="X", password="short", client_ip="203.0.113.9")
    with pytest.raises(Throttled):
        accounts.signup(conn, ctx, email="ok@example.test", display_name="Ok", password=PASSWORD, client_ip="203.0.113.9")


def test_logins_are_rate_limited_per_address_even_when_they_succeed(conn, ctx, world):
    world.user("Busy", email="busy@example.test")
    for _ in range(60):
        accounts.login(conn, ctx, email="busy@example.test", password=PASSWORD, client_ip="203.0.113.9")
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="busy@example.test", password=PASSWORD, client_ip="203.0.113.9")
    accounts.login(conn, ctx, email="busy@example.test", password=PASSWORD, client_ip="198.51.100.2")


def test_the_signup_page_says_so_with_429(app):
    s = Site(app)
    codes = []
    for i in range(12):
        codes.append(s.signup(name=f"P {i}", email=f"web{i}@example.test").status_code)
        s.client.cookies.delete("fcc_session")
    assert codes[:10] == [303] * 10 and codes[10:] == [429, 429]
