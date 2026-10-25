"""F-17, F-18, F-19: readable type, a safe Enter key in the stepper, and 44 px tap targets for the important links."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import Site
from fcc_testlib import csrf_from

CSS = (Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "base.css").read_text()
TOKENS = (Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "tokens.css").read_text()
VALID = {"display_name": "Pat Example", "preferred_name": "Grandma", "year_of_birth": "1948",
         "care_notes": "Likes tea.", "relationship_label": "Daughter"}

# Only these may be smaller than 1rem: status chips are short labels that always have an icon or colour as well.
SMALL_ALLOWED = {".chip"}


def _declared_sizes():
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        for m in re.finditer(r"(?<![-\w])font-size:\s*([\d.]+)(rem|px)", body):
            value = float(m.group(1)) / (16 if m.group(2) == "px" else 1)
            yield sel.strip(), value


def test_no_text_below_one_rem_except_status_chips():
    small = [(sel, size) for sel, size in _declared_sizes() if size < 1 and sel not in SMALL_ALLOWED]
    assert small == [], small


def test_the_mandatory_disclaimer_hints_and_footer_are_at_least_1rem():
    wanted = {".disclaimer", ".hint", ".site-footer", ".updated", ".check-meta", ".member-email"}
    seen = {sel: size for sel, size in _declared_sizes() if sel in wanted}
    assert wanted <= set(seen) and all(v >= 1 for v in seen.values()), seen


def test_the_size_check_has_teeth():
    """Positive control: the detector really notices a too-small rule."""
    global CSS
    saved = CSS
    try:
        CSS = saved + "\n.sneaky { font-size: .9rem; }\n"
        assert (".sneaky", 0.9) in list(_declared_sizes())
    finally:
        CSS = saved


@pytest.fixture
def me(app):
    s = Site(app)
    assert s.signup(name="Olivia Owner", email="olivia@example.test").status_code == 303
    return s


def _step(me, n, action="next"):
    return me.post("/profiles/new", {**VALID, "step": str(n), "action": action, "csrf_token": csrf_from(me.get("/profiles/new").text)})


@pytest.mark.parametrize("n", [1, 2, 3])
def test_the_primary_button_comes_first_in_every_stepper_form(me, n):
    """F-18: pressing Enter in a field submits the FIRST submit button, so it must never be "Back"."""
    html = _step(me, n).text           # the page for step n+1
    form = html[html.index('action="/profiles/new"'):]
    form = form[:form.index("</form>")]
    submits = re.findall(r"<button[^>]*>", form)
    primary = 'value="create"' if n + 1 == 4 else 'value="next"'
    assert primary in submits[0], submits
    assert any('value="back"' in b for b in submits)          # Back still exists, just later in the DOM


def test_inline_links_that_matter_have_a_44px_tap_target_class(app):
    assert re.search(r"\.tap-link\s*\{[^}]*min-height:\s*var\(--tap\)", CSS)
    assert re.search(r"--tap:\s*(44px|2\.75rem)", TOKENS)
    html = " ".join(p.read_text() for p in (Path(__file__).resolve().parents[2] / "app" / "templates").rglob("*.html"))
    for text in ("Refresh now", "Open the checklist", "Read the full summary", "Go back to the latest"):
        assert re.search(rf'<a [^>]*class="[^"]*tap-link[^"]*"[^>]*>{text}</a>', html), text


# ------------------------------------------------------------------ optional item: "Bigger words" on the child view
JS = (Path(__file__).resolve().parents[2] / "app" / "static" / "js" / "app.js").read_text()


def test_bigger_words_button_is_on_child_text_only_and_hidden_until_javascript_runs(full):
    child = full.site["child"].get(f"/p/{full.pid}").text
    assert child.count("data-bigger-words") == 1 and 'aria-pressed="false"' in child
    assert re.search(r"<button[^>]*data-bigger-words[^>]*data-needs-js[^>]*hidden|<button[^>]*data-needs-js[^>]*hidden[^>]*data-bigger-words", child)
    assert "data-bigger-words" not in full.site["patient"].get(f"/p/{full.pid}").text
    assert "data-bigger-words" not in full.site["owner"].get(f"/p/{full.pid}/summaries?tab=patient").text


def test_bigger_words_is_client_side_only_and_tolerates_blocked_storage():
    assert re.search(r"\.bigger-words[^{]*\.persona-child[^{]*\{[^}]*font-size:\s*(1\.[5-9]|2)", CSS)
    assert "localStorage" in JS and JS.count("try") >= 1 and "fcc-bigger-words" in JS
    block = JS.split("// --- bigger words")[1].split("// --- end bigger words")[0]
    assert "fetch(" not in block and "XMLHttpRequest" not in block                       # nothing is sent to the server
