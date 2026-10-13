"""Headless smoke test for scripts/demo_app.py using Streamlit's AppTest (no browser, no model)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="streamlit is an optional dependency, only needed for the demo")
from streamlit.testing.v1 import AppTest  # noqa: E402

DEMO_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo_app.py"


def _app(monkeypatch) -> AppTest:
    monkeypatch.setattr("sys.argv", ["scripts/demo_app.py", "--mock-backend"])
    return AppTest.from_file(str(DEMO_SCRIPT), default_timeout=30)


def test_demo_loads_with_mock_backend(monkeypatch):
    at = _app(monkeypatch).run()
    assert not at.exception
    assert "Mock backend" in at.caption[0].value
    assert at.sidebar.selectbox[0].options[0] == "(paste your own)"


def test_demo_golden_path_generates_without_crashing(monkeypatch):
    at = _app(monkeypatch).run()
    at.sidebar.selectbox[0].set_value("note_01.txt").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    # entities section + 3 persona columns render as markdown blocks
    assert len(at.markdown) >= 4
    assert any("retention" in c.value for c in at.caption)


def test_demo_errors_cleanly_when_generate_clicked_with_no_note(monkeypatch):
    at = _app(monkeypatch).run()
    at.sidebar.selectbox[0].set_value("(paste your own)").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert any("first" in e.value for e in at.sidebar.error)
