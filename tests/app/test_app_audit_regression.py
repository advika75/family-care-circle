"""Phase A audit scenarios kept as regression tests (mock backend, throw-away databases).

The full actor x route matrix takes ~half a minute, so it is marked ``slow`` (``make app-test-slow``); the rest of the
audit scenarios live in the other test files (ID indistinguishability and invitations: test_app_security_ids.py and
test_app_circle.py; sessions and injection: test_app_security_review.py; child gate: test_app_safety.py;
job recovery, hangs and queue caps: test_app_notes_jobs.py, test_app_jobs_isolation.py, test_app_queue_caps.py).
"""

from __future__ import annotations

import pytest

import audit_matrix_lib as lib


@pytest.fixture(scope="module")
def matrix():
    return lib.run_matrix()


@pytest.mark.slow
def test_matrix_covers_every_route_and_actor(matrix):
    assert len(matrix["get"]) >= 24 and len(matrix["post"]) >= 18
    assert all(set(row) == set(lib.ACTORS) for row in matrix["get"].values())


@pytest.mark.slow
def test_no_forbidden_string_in_any_response(matrix):
    assert matrix["leaks"] == []


@pytest.mark.slow
def test_no_forbidden_data_reaches_a_low_privilege_template_context(matrix):
    assert matrix["context_leaks"] == []


@pytest.mark.slow
def test_get_requests_never_change_the_database(matrix):
    assert matrix["get_mutated_db"] is False


@pytest.mark.slow
def test_nobody_changes_state_they_are_not_allowed_to(matrix):
    assert matrix["unexpected"] == []


@pytest.mark.slow
def test_logs_never_contain_notes_passwords_or_emails(matrix):
    assert matrix["log_leaks"] == [] and matrix["log_lines"] > 0


def test_leak_detector_has_teeth():
    """Positive control: the detector finds a planted forbidden string, and ignores a viewer's own name."""
    class R:
        text = "hello Amoxicillin"
        headers = type("H", (), {"multi_items": lambda self: []})()
    assert lib.leaks("child", R()) == ["Amoxicillin"]
    R.text = "hello"
    assert lib.leaks("child", R()) == []


# --------------------------------------------------------------------------- patient ID and invitation race
import re
import threading

from app import accounts, circle
from app.db import connect
from app.errors import AppError
from conftest import Site
from fcc_testlib import PASSWORD

_CSRF = re.compile(r'value="[0-9a-f]{64}"')
FAKE_ID = "FCC-AAAA-AAAA"


def test_a_real_patient_id_is_indistinguishable_from_a_fake_one_to_outsiders(full, app):
    """Audit A3: anonymous visitors and strangers get the same status and the same page for a real and a made-up ID."""
    stranger = Site(app); stranger.signup(name="Sam Stranger", email="sam.stranger@example.test")
    paths = ["", "/info", "/circle", "/summaries", "/summaries?tab=caregiver", "/notes", "/created"]
    for who, site in (("anonymous", Site(app)), ("stranger", stranger)):
        for path in paths:
            real = site.get(f"/p/{full.pid}{path}")
            fake = site.get(f"/p/{FAKE_ID}{path}")
            assert real.status_code == fake.status_code, (who, path)
            assert _CSRF.sub("", real.text).replace(full.pid, FAKE_ID) == _CSRF.sub("", fake.text), (who, path)


def test_an_invitation_code_can_be_redeemed_by_exactly_one_of_many_simultaneous_joins(settings, ctx, world):
    """Audit A4: 8 threads race to use one single-use code; the database must let exactly one win."""
    owner = world.user("Owner"); p = world.profile(owner)
    _, code = circle.create_invitation(world.conn, ctx, owner, p, role="caregiver")
    users = [world.user(f"Racer {chr(65 + i)}") for i in range(8)]
    start = threading.Barrier(len(users))
    results: list[str] = []

    def go(u):
        c = connect(settings.db_path)
        start.wait()
        try:
            circle.join(c, ctx, u, patient_id=p["patient_id"], code=code, relationship_label="Other relative")
            results.append("joined")
        except AppError:
            results.append("refused")
        finally:
            c.close()

    threads = [threading.Thread(target=go, args=(u,)) for u in users]
    [t.start() for t in threads]; [t.join(30) for t in threads]
    assert sorted(results) == ["joined"] + ["refused"] * 7
    members = world.conn.execute("SELECT COUNT(*) FROM memberships WHERE profile_id = ? AND role = 'caregiver'", (p["id"],)).fetchone()[0]
    assert members == 1
