"""The documentation makes claims; these tests keep them true."""

from __future__ import annotations

import importlib.metadata as md
import re
from pathlib import Path

import pytest

from app import safety
from app.tools import contrast
from test_app_security_review import routes_of

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "app" / "README.md").read_text()
README = (ROOT / "README.md").read_text()


def test_every_live_route_segment_is_documented(app):
    for _, path in routes_of(app):
        for seg in re.findall(r"/([a-z][a-z-]*)", re.sub(r"\{[^}]+\}", "", path)):
            assert seg in DOC, f"{path}: '{seg}' is not mentioned in app/README.md"


def test_documented_counts_match_the_code(app):
    posts = [r for r in routes_of(app) if r[0] == "POST"]
    assert f"all {len(posts)} `POST` routes" in DOC
    assert f"checks {len(contrast.PAIRS)} text/background" in DOC
    assert "Prototype. Not for real patient data." in DOC and "Prototype. Not for real patient data." in README
    assert "Family Care Circle" in DOC and "Family Care Circle" in README
    assert "not a substitute for professional medical advice" in DOC.lower()


def test_the_not_secured_list_is_present_in_both_documents():
    for text in (DOC, README):
        low = text.lower()
        for phrase in ("NOT secured", "encryption at rest", "rate limiting", "email"):
            assert phrase.lower() in low, phrase
        assert "third-party" in low or "third party" in low
    for phrase in ("No HTTPS termination", "No email delivery", "no password-reset", "unencrypted", "idle timeout"):
        assert phrase.lower() in DOC.lower(), phrase


def test_root_readme_section_was_appended_and_documents_how_to_run():
    assert "## Multi-user web app" in README and README.index("## Multi-user web app") > README.index("## ")
    for cmd in ("make app-run", "make app-seed", "make app-test", "APP_BACKEND=llama_cpp"):
        assert cmd in README and cmd in DOC


def test_makefile_and_gitignore_only_gained_lines():
    make = (ROOT / "Makefile").read_text()
    for target in ("app-run:", "app-test:", "app-seed:", "reproduce-small:", "clean-reproduce-small:", "test:"):
        assert target in make
    assert "--no-server-header" in make and "--host 127.0.0.1" in make
    ignore = (ROOT / ".gitignore").read_text()
    for line in ("app/var/", "*.sqlite3", ".env.*", ".env", "models/"):
        assert line in ignore.splitlines()


def test_requirements_app_pins_match_what_is_installed_and_nothing_extra_is_listed():
    listed = {}
    for line in (ROOT / "requirements-app.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            name, ver = line.split("==")
            listed[name] = ver
    assert set(listed) == {"fastapi", "uvicorn", "jinja2", "python-multipart", "httpx"}
    for name, ver in listed.items():
        assert md.version(name) == ver, name
    assert listed["fastapi"] == "0.141.0"
    # (`requests` is installed too, but only because the existing Streamlit demo needs it; the app never imports it.)
    for unlisted in ("opentelemetry-api", "sqlalchemy", "httpx2"):          # playwright/pip-audit: requirements-app-dev.txt only
        with pytest.raises(md.PackageNotFoundError):
            md.version(unlisted)


# ---- the child gate's documented limits are real, and pinned ------------------------------------------------------
@pytest.mark.parametrize("text,why", [
    ("Your Amoxil helps you. Rest.", "brand name never seen"),
    ("Your amoxicilin helps you. Rest.", "misspelling of a drug name"),
    ("Some Tylenol helps. Rest.", "medicine not extracted from the note"),
    ("The doctors are not sure you will get better. Be afraid.", "paraphrased fear"),
    (", ".join(["you rest"] * 10) + ".", "chain of clauses joined only by commas"),
])
def test_known_gaps_in_the_child_gate_are_exactly_as_documented(text, why):
    assert safety.check_child_text(text, ["Amoxicillin"]) == [], why
    for phrase in ("brand names", "misspellings", "paraphrased", "commas"):
        assert phrase in DOC


def test_the_documented_gate_limit_is_the_implemented_one():
    assert safety.MAX_CHILD_SENTENCES == 8 and "more than 8 sentences" in DOC and safety.MAX_CHILD_WORDS == 120 and "120 words" in DOC
    assert safety.SAFE_CHILD_MESSAGE in DOC
