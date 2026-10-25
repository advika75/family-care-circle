"""Password hashing, tokens, patient IDs, invitation codes, CSRF tokens, throttle."""

from __future__ import annotations

import re

import pytest

from app import csrf, ids, security
from app.config import Settings
from app.errors import ValidationFailed
from app.throttle import Throttle


def test_hash_roundtrip_and_parameters_are_stored(settings):
    h = security.hash_password("a long enough password", settings)
    assert h.startswith("scrypt$16$8$1$")                       # N, r, p stored in the hash
    assert security.verify_password("a long enough password", h)
    assert not security.verify_password("a long enough passwore", h)


def test_each_hash_has_its_own_salt(settings):
    assert security.hash_password("same password here", settings) != security.hash_password("same password here", settings)


def test_hash_does_not_contain_the_password(settings):
    assert "hunter2hunter2hunter2" not in security.hash_password("hunter2hunter2hunter2", settings)


def test_verify_uses_stored_parameters_not_current_settings(settings):
    old = security.hash_password("a long enough password", settings)
    # Raising the cost later must not break old hashes: verify_password takes no settings at all.
    assert security.verify_password("a long enough password", old)


@pytest.mark.parametrize("bad", ["", "scrypt", "scrypt$x$8$1$aa$bb", "md5$1$2$3$4$5", "scrypt$16$8$1$!!$!!"])
def test_malformed_hashes_fail_closed(bad):
    assert security.verify_password("anything at all", bad) is False


def test_password_rules_are_length_only(settings):
    with pytest.raises(ValidationFailed):
        security.validate_password("short", settings)
    with pytest.raises(ValidationFailed):
        security.validate_password("x" * 1025, settings)
    security.validate_password("aaaaaaaaaaaa", settings)         # 12 chars, no composition rules
    security.validate_password("only lowercase words here", settings)


def test_default_production_cost_is_at_least_2_14():
    s = Settings()
    assert s.scrypt_n >= 2 ** 14 and s.min_password_length == 12


def test_tokens_are_random_and_stored_as_digests():
    a, b = security.new_token(), security.new_token()
    assert a != b and len(a) >= 40
    assert security.hash_token(a) != a and len(security.hash_token(a)) == 64


def test_constant_time_equals():
    assert security.constant_time_equals("abc", "abc") and not security.constant_time_equals("abc", "abd")


# --- ids ---------------------------------------------------------------------------------------------
def test_patient_id_format_and_alphabet():
    for _ in range(200):
        pid = ids.new_patient_id()
        assert ids.PATIENT_ID_RE.match(pid) and re.fullmatch(r"FCC-[A-Z2-9]{4}-[A-Z2-9]{4}", pid)
        assert not set(pid.replace("FCC-", "").replace("-", "")) & set("ILOU01")


def test_patient_ids_do_not_repeat_in_a_sample():
    assert len({ids.new_patient_id() for _ in range(2000)}) == 2000


@pytest.mark.parametrize("text,expected", [
    ("fcc-abcd-efgh", "FCC-ABCD-EFGH"), (" FCC ABCD EFGH ", "FCC-ABCD-EFGH"), ("FCCABCDEFGH", "FCC-ABCD-EFGH"),
    ("ABCDEFGH", "FCC-ABCD-EFGH"), ("FCC-ABCD-EFG", None), ("FCC-ABCD-EFGI", None), ("", None), ("FCC-0000-0000", None),
])
def test_patient_id_normalisation(text, expected):
    assert ids.normalize_patient_id(text) == expected


def test_invite_code_format_and_normalisation():
    code = ids.new_invite_code()
    assert ids.INVITE_CODE_RE.match(code) and len(code) == 19
    assert ids.normalize_invite_code(code.lower().replace("-", " ")) == code
    assert ids.normalize_invite_code(code[:-1]) is None and ids.normalize_invite_code("") is None


def test_ids_use_secrets_not_random():
    import inspect
    src = inspect.getsource(ids)
    assert "import secrets" in src and "import random" not in src and "random." not in src.replace("secrets.", "")


# --- csrf --------------------------------------------------------------------------------------------
def test_csrf_token_is_bound_to_the_session_and_the_key():
    key = b"k" * 32
    t = csrf.make_token(key, "session-digest-A")
    assert csrf.verify_token(key, "session-digest-A", t)
    assert not csrf.verify_token(key, "session-digest-B", t)           # another session's token is useless
    assert not csrf.verify_token(b"z" * 32, "session-digest-A", t)     # forged with another key
    assert not csrf.verify_token(key, "session-digest-A", t[:-1] + ("0" if t[-1] != "0" else "1"))
    assert not csrf.verify_token(key, "session-digest-A", None) and not csrf.verify_token(key, "", t)


# --- throttle ----------------------------------------------------------------------------------------
def test_throttle_blocks_after_limit_and_recovers_after_window():
    now = [0.0]
    t = Throttle(lambda: now[0], window_seconds=100)
    for _ in range(4):
        t.record_failure("k")
    assert not t.blocked("k", 5)
    t.record_failure("k")
    assert t.blocked("k", 5) and not t.blocked("other", 5)
    now[0] = 101.0
    assert not t.blocked("k", 5)


def test_throttle_reset():
    t = Throttle(lambda: 0.0)
    for _ in range(5):
        t.record_failure("k")
    t.reset("k")
    assert not t.blocked("k", 5)
