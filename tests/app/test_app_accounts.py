"""Signup, login, throttling, sessions, password change, account deletion."""

from __future__ import annotations

import logging
import sqlite3

import pytest

from app import accounts, circle, security
from app.errors import (AccountNotCreated, InvalidCredentials, NotAllowed, Throttled, ValidationFailed)
from fcc_testlib import PASSWORD


def signup(conn, ctx, email="a@example.test", name="Ann", password=PASSWORD):
    return accounts.signup(conn, ctx, email=email, display_name=name, password=password)


def test_signup_creates_user_with_scrypt_hash_and_returns_no_hash(conn, ctx):
    u = signup(conn, ctx)
    assert set(u.keys()) == {"id", "email", "display_name", "created_at"}          # no password_hash in the public row
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (u["id"],)).fetchone()[0]
    assert stored.startswith("scrypt$") and PASSWORD not in stored


def test_signup_normalises_email_and_rejects_duplicates_generically(conn, ctx):
    signup(conn, ctx, email="  Ann@Example.TEST ")
    assert conn.execute("SELECT email FROM users").fetchone()[0] == "ann@example.test"
    with pytest.raises(AccountNotCreated) as e:
        signup(conn, ctx, email="ANN@example.test")
    assert e.value.message == AccountNotCreated.message                       # the fixed, generic refusal
    assert "ann@example.test" not in e.value.message.lower()                  # never echoes the address
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("kw,field", [
    ({"email": "not-an-email"}, "email"), ({"email": ""}, "email"), ({"name": "   "}, "display_name"),
    ({"name": "x" * 81}, "display_name"), ({"password": "short"}, "password"), ({"name": "bad\x00name"}, "display_name"),
])
def test_signup_validation_errors_name_the_field(conn, ctx, kw, field):
    with pytest.raises(ValidationFailed) as e:
        signup(conn, ctx, **kw)
    assert field in e.value.errors
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_login_ok_and_session_resolves(conn, ctx):
    u = signup(conn, ctx)
    user, token = accounts.login(conn, ctx, email="A@example.test", password=PASSWORD)
    assert user["id"] == u["id"] and "password_hash" not in user.keys()
    assert accounts.resolve_session(conn, ctx, token)["id"] == u["id"]
    stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored == security.hash_token(token) and stored != token                 # only the digest is stored


def test_wrong_password_and_unknown_email_give_the_same_error(conn, ctx):
    signup(conn, ctx)
    with pytest.raises(InvalidCredentials) as a:
        accounts.login(conn, ctx, email="a@example.test", password="wrong password here")
    with pytest.raises(InvalidCredentials) as b:
        accounts.login(conn, ctx, email="nobody@example.test", password="wrong password here")
    assert a.value.message == b.value.message and a.value.code == b.value.code


def test_login_throttle_per_email_and_address_blocks_even_the_right_password(conn, ctx):
    signup(conn, ctx)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email="a@example.test", password="wrong password here", client_ip="1.1.1.1")
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="a@example.test", password=PASSWORD, client_ip="1.1.1.1")
    accounts.login(conn, ctx, email="a@example.test", password=PASSWORD, client_ip="2.2.2.2")   # F-04: owner is not locked out


def test_login_throttle_applies_to_unknown_emails_too(conn, ctx):
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email="ghost@example.test", password="wrong password here")
    with pytest.raises(Throttled):          # same behaviour as a real account: existence is not revealed
        accounts.login(conn, ctx, email="ghost@example.test", password="wrong password here")


def test_login_throttle_per_ip_across_many_emails(conn, ctx):
    for i in range(20):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email=f"u{i}@example.test", password="wrong password here", client_ip="9.9.9.9")
    with pytest.raises(Throttled):
        accounts.login(conn, ctx, email="fresh@example.test", password="wrong password here", client_ip="9.9.9.9")


def test_login_throttle_recovers_after_the_window(conn, ctx, clock):
    signup(conn, ctx)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email="a@example.test", password="wrong password here")
    clock.advance(minutes=16)
    user, _ = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    assert user["email"] == "a@example.test"


def test_successful_login_resets_the_email_counter(conn, ctx):
    signup(conn, ctx)
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email="a@example.test", password="wrong password here")
    accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            accounts.login(conn, ctx, email="a@example.test", password="wrong password here")


def test_logout_invalidates_the_session(conn, ctx):
    signup(conn, ctx)
    _, token = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    accounts.logout(conn, token)
    assert accounts.resolve_session(conn, ctx, token) is None
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_session_expires(conn, ctx, clock):
    signup(conn, ctx)
    _, token = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    clock.advance(hours=167)
    assert accounts.resolve_session(conn, ctx, token) is not None
    clock.advance(hours=2)
    assert accounts.resolve_session(conn, ctx, token) is None
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0           # expired row is removed


@pytest.mark.parametrize("bad", [None, "", "garbage", "x" * 200])
def test_unknown_session_tokens_resolve_to_nothing(conn, ctx, bad):
    assert accounts.resolve_session(conn, ctx, bad) is None


def test_logout_all_ends_every_session_but_can_keep_one(conn, ctx):
    u = signup(conn, ctx)
    tokens = [accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)[1] for _ in range(3)]
    assert accounts.logout_all(conn, u["id"], keep_token=tokens[0]) == 2
    assert accounts.resolve_session(conn, ctx, tokens[0]) is not None
    assert accounts.resolve_session(conn, ctx, tokens[1]) is None
    accounts.logout_all(conn, u["id"])
    assert accounts.resolve_session(conn, ctx, tokens[0]) is None


def test_change_password_ends_other_sessions_and_swaps_the_hash(conn, ctx):
    u = signup(conn, ctx)
    keep = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)[1]
    other = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)[1]
    new = accounts.change_password(conn, ctx, u, current_password=PASSWORD, new_password="a brand new passphrase", keep_token=keep)
    assert accounts.resolve_session(conn, ctx, new) is not None and accounts.resolve_session(conn, ctx, other) is None
    with pytest.raises(InvalidCredentials):
        accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    accounts.login(conn, ctx, email="a@example.test", password="a brand new passphrase")


def test_change_password_rejects_wrong_current_and_weak_new(conn, ctx):
    u = signup(conn, ctx)
    with pytest.raises(InvalidCredentials):
        accounts.change_password(conn, ctx, u, current_password="not my password", new_password="a brand new passphrase")
    with pytest.raises(ValidationFailed):
        accounts.change_password(conn, ctx, u, current_password=PASSWORD, new_password="short")


def test_change_password_attempts_are_throttled(conn, ctx):
    u = signup(conn, ctx)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            accounts.change_password(conn, ctx, u, current_password="nope nope nope nope", new_password="a brand new passphrase")
    with pytest.raises(Throttled):
        accounts.change_password(conn, ctx, u, current_password=PASSWORD, new_password="a brand new passphrase")


def test_delete_account_requires_password_and_removes_sessions(conn, ctx):
    u = signup(conn, ctx)
    _, token = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    with pytest.raises(InvalidCredentials):
        accounts.delete_account(conn, ctx, u, password="wrong wrong wrong")
    accounts.delete_account(conn, ctx, u, password=PASSWORD)
    assert accounts.resolve_session(conn, ctx, token) is None
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_delete_account_is_refused_while_creator_of_a_circle(conn, ctx, world):
    u = world.user("Owner")
    world.profile(u)
    with pytest.raises(NotAllowed):
        accounts.delete_account(conn, ctx, u, password=PASSWORD)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_deleting_a_member_account_removes_their_membership_only(conn, ctx, world):
    owner = world.user("Owner"); p = world.profile(owner)
    cg, _ = world.member(p, owner, "caregiver", "Cara")
    accounts.delete_account(conn, ctx, cg, password=PASSWORD)
    assert conn.execute("SELECT COUNT(*) FROM memberships WHERE profile_id = ?", (p["id"],)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1


def test_secrets_are_never_logged(conn, ctx, world, caplog):
    caplog.set_level(logging.DEBUG)
    u = signup(conn, ctx, email="secretly@example.test")
    _, token = accounts.login(conn, ctx, email="secretly@example.test", password=PASSWORD)
    owner = world.user("Owner"); p = world.profile(owner)
    inv, code = circle.create_invitation(conn, ctx, owner, p, role="caregiver")
    circle.join(conn, ctx, u, patient_id=p["patient_id"], code=code, relationship_label="Son")
    with pytest.raises(InvalidCredentials):
        accounts.login(conn, ctx, email="secretly@example.test", password="definitely the wrong one")
    text = "\n".join(r.getMessage() for r in caplog.records)
    for secret in (PASSWORD, token, code, "definitely the wrong one", "secretly@example.test", security.hash_token(token)):
        assert secret not in text


# ------------------------------------------------------------------------------ F-08 / F-09 (Phase B)
def test_expired_sessions_are_purged_when_someone_logs_in(conn, ctx):
    """F-08: purge_expired_sessions was never called, so expired rows piled up."""
    u = signup(conn, ctx)
    for i in range(20):
        accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    ctx.clock.advance(hours=ctx.settings.session_ttl_hours, minutes=1)
    before = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)
    after = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert before == 20 and after == 1                     # the 20 expired rows are gone, only the new session remains


def test_change_password_rotates_the_session_token(conn, ctx):
    """F-09: the session used for the change must not survive; a fresh token is issued instead."""
    u = signup(conn, ctx)
    keep = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)[1]
    other = accounts.login(conn, ctx, email="a@example.test", password=PASSWORD)[1]
    new = accounts.change_password(conn, ctx, u, current_password=PASSWORD, new_password="a brand new passphrase", keep_token=keep)
    assert new and new != keep
    assert accounts.resolve_session(conn, ctx, keep) is None and accounts.resolve_session(conn, ctx, other) is None
    assert accounts.resolve_session(conn, ctx, new) is not None
