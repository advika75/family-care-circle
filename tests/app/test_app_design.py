"""Design system: tokens, WCAG contrast, no stray colours, components, accessibility rules in the CSS."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.tools import contrast

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "templates"
TOKENS = (STATIC / "css" / "tokens.css").read_text()
BASE = (STATIC / "css" / "base.css").read_text()


def test_contrast_function_is_correct():
    assert contrast.ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast.ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert contrast.ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.02)      # the well-known AA threshold grey


def test_every_token_pair_meets_wcag_aa():
    rows = contrast.check()
    assert len(rows) >= 40
    failing = [r for r in rows if not r["ok"]]
    assert not failing, failing


def test_the_script_exits_zero_when_everything_passes():
    assert contrast.main() == 0


def test_a_failing_pair_would_be_detected():
    bad = dict(contrast.load_tokens(), text="#CCCCCC")                                  # light grey text on cream
    assert any(not r["ok"] for r in contrast.check(bad))


def test_specified_palette_is_used():
    tokens = contrast.load_tokens()
    assert tokens["bg"] == "#FAF7F2" and tokens["surface"] == "#FFFFFF"
    assert tokens["pink"] == "#F9E6E7" and tokens["lavender"] == "#EEE9F8" and tokens["green"] == "#E2EDE3"
    assert tokens["primary"] == "#8E3D4E" and tokens["on-primary"] == "#FFFFFF"
    assert tokens["text"] == "#2B2A33" and tokens["muted"] == "#5E5C6B" and tokens["line"] == "#E8E2D8"


def test_type_shape_and_touch_target_tokens():
    assert "--radius-card: 18px" in TOKENS and "--radius-control: 12px" in TOKENS and "--tap: 44px" in TOKENS
    assert "--text-base: 1rem" in TOKENS
    assert re.search(r'--font-heading:\s*"Fraunces",.*serif;', TOKENS) and re.search(r'--font-body:\s*"Nunito Sans",.*sans-serif;', TOKENS)
    assert float(re.search(r"--text-child:\s*([\d.]+)rem", TOKENS).group(1)) > 1.0                 # larger type for the child view


def test_no_colour_literals_outside_tokens_css():
    assert not re.findall(r"#[0-9A-Fa-f]{3,8}\b", BASE), "colours must come from tokens.css"
    for t in TEMPLATES.rglob("*.html"):
        assert "style=" not in t.read_text(), t
    # the favicon is an image asset, not a UI colour


def test_no_external_resources_anywhere():
    for f in list((STATIC).rglob("*")) + list(TEMPLATES.rglob("*.html")):
        if f.is_file():
            text = f.read_text(errors="ignore")
            for url in re.findall(r"""(?:src|href|url)\(?=?["']?(https?://[^"')\s>]+)""", text):
                assert "w3.org" in url, (f, url)                                              # only the SVG namespace string
    assert "@import" not in BASE and "fonts.googleapis" not in BASE + TOKENS


def test_focus_ring_touch_targets_and_reduced_motion_are_in_the_css():
    assert ":focus-visible" in BASE and "outline: 3px solid var(--focus)" in BASE
    assert BASE.count("min-height: var(--tap)") >= 4
    assert "prefers-reduced-motion" in BASE
    assert "font-size: var(--text-base)" in BASE


def test_all_specified_components_exist_as_macros():
    src = (TEMPLATES / "partials" / "components.html").read_text()
    macros = set(re.findall(r"{% macro (\w+)\(", src))
    # Stage 3 components; persona card, checklist item, member row, context bar and skeleton arrive in Stage 4
    assert {"link_button", "button", "field", "textarea_field", "select_field", "stepper", "role_chip", "status_chip",
            "banner", "empty_state", "copy_button", "card", "csrf_field"} <= macros
    assert (TEMPLATES / "partials" / "icons.html").exists() and (TEMPLATES / "partials" / "nav.html").exists()


def test_icons_are_inline_svg_not_emoji():
    icons = (TEMPLATES / "partials" / "icons.html").read_text()
    assert "<svg" in icons
    for f in TEMPLATES.rglob("*.html"):
        assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", f.read_text()), f


def test_copy_button_script_is_progressive_enhancement():
    comp = (TEMPLATES / "partials" / "components.html").read_text()
    assert "data-needs-js hidden" in comp and 'aria-live="polite"' in comp
    js = (STATIC / "js" / "app.js").read_text()
    assert "Copied" in js and "clipboard" in js and "fallbackCopy" in js           # works without the async clipboard API too
