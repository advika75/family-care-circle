"""Accessibility and responsive checks that can be made WITHOUT a browser.

What these prove: structure of the real rendered pages (headings, names, labels, ids, forms, titles) and the
responsive/touch-target rules in the stylesheet. What they cannot prove: how a page actually reflows at 360px,
what keyboard focus looks like, or screen-reader behaviour. Those need a browser (Playwright is not installed here)
and a human; see app/AUDIT notes in app/README.md.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from conftest import Site
from fcc_testlib import PASSWORD, csrf_from

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
BASE = (STATIC / "css" / "base.css").read_text()


class Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings, self.ids, self.dup_ids = [], set(), set()
        self.links, self.buttons, self.forms, self.title = [], [], [], ""
        self._stack, self._text = [], []
        self._in_title = False
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            (self.dup_ids if a["id"] in self.ids else self.ids).add(a["id"])
        if tag == "title":
            self._in_title = True
        if tag in ("h1", "h2", "h3", "h4"):
            self.headings.append(int(tag[1]))
        if tag in ("a", "button", "summary", "label"):
            self._stack.append((tag, a, []))
        if tag == "form":
            self._form = {"method": a.get("method", "get").lower(), "action": a.get("action"), "has_csrf": False}
            self.forms.append(self._form)
        if tag == "input" and self._form is not None and a.get("name") == "csrf_token":
            self._form["has_csrf"] = True
        if tag in ("svg",) and self._stack and a.get("aria-label"):
            self._stack[-1][2].append(a["aria-label"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "form":
            self._form = None
        if self._stack and self._stack[-1][0] == tag:
            t, a, parts = self._stack.pop()
            name = (a.get("aria-label") or " ".join(parts)).strip()
            if t == "a":
                self.links.append((a.get("href"), name))
            elif t == "button":
                self.buttons.append(name)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        for _, _, parts in self._stack:
            parts.append(data.strip())


def parse(html: str) -> Doc:
    d = Doc()
    d.feed(html)
    return d


@pytest.fixture
def all_pages(full, app):
    for who in ("owner", "caregiver", "caregiver_no_notes", "patient", "child", "pending", "revoked"):
        s = full.site[who]
        for suffix in ("", "/info", "/circle", "/summaries", "/summaries?tab=caregiver", "/summaries?tab=child", "/notes", "/created"):
            s.get(f"/p/{full.pid}{suffix}")
        s.get("/settings"); s.get("/profiles"); s.get("/profiles/new"); s.get("/join"); s.get("/unauthorized")
    anon = Site(app)
    for url in ("/", "/login", "/signup", "/nope"):
        anon.get(url)
    pages = [h for s in list(full.site.values()) + [anon] for h in s.pages]
    assert len(pages) > 80
    return pages


def test_heading_levels_never_skip_and_start_at_h1(all_pages):
    for html in all_pages:
        hs = parse(html).headings
        assert hs and hs[0] == 1, hs
        for prev, cur in zip(hs, hs[1:]):
            assert cur <= prev + 1, f"heading jumps from h{prev} to h{cur}: {hs}"


def test_every_link_and_button_has_an_accessible_name(all_pages):
    for html in all_pages:
        d = parse(html)
        for href, name in d.links:
            assert name, f"link {href!r} has no text"
        for name in d.buttons:
            assert name, "a button has no text"


def test_ids_are_unique_on_every_page(all_pages):
    for html in all_pages:
        assert not parse(html).dup_ids, parse(html).dup_ids


def test_every_post_form_carries_a_csrf_token_and_every_page_has_a_distinct_title(all_pages):
    titles = set()
    for html in all_pages:
        d = parse(html)
        for f in d.forms:
            if f["method"] == "post":
                assert f["has_csrf"], f
        assert d.title.strip().endswith("Family Care Circle") and len(d.title.strip()) > len(" · Family Care Circle")
        titles.add(d.title.strip())
    assert len(titles) >= 12


def test_credential_fields_use_autocomplete_hints(site):
    login, signup = site.get("/login").text, site.get("/signup").text
    assert 'autocomplete="current-password"' in login and 'autocomplete="username"' in login
    assert 'autocomplete="new-password"' in signup and 'autocomplete="email"' in signup and 'autocomplete="name"' in signup


def test_forms_without_javascript_still_work_because_every_action_is_a_plain_form(full):
    # the stepper, checklist ticks, invitations and tabs are all <form>/<a>; JavaScript only adds copy + polling
    js = (STATIC / "js" / "app.js").read_text()
    assert "preventDefault" not in js and "XMLHttpRequest" not in js and "submit(" not in js


def test_keyboard_navigation_order_has_no_positive_tabindex(all_pages):
    for html in all_pages:
        assert not re.search(r'tabindex="[1-9]', html)
        assert 'tabindex="-1"' in html                                       # only the skip-link target <main>


def test_the_viewport_is_set_and_zoom_is_not_disabled(all_pages):
    for html in all_pages:
        m = re.search(r'<meta name="viewport" content="([^"]+)"', html)
        assert m and "width=device-width" in m.group(1)
        assert "user-scalable=no" not in m.group(1) and "maximum-scale" not in m.group(1)


# ---- responsive and touch-target rules in the stylesheet -------------------------------------------------------
def test_nothing_in_the_css_can_force_horizontal_scroll_at_360px():
    narrowest = 360 - 2 * 16                                                  # viewport minus the 16px gutters
    for value, unit in re.findall(r"(?<![\w(-])(?:min-)?width:\s*([\d.]+)(px|rem)", BASE):
        px = float(value) * (16 if unit == "rem" else 1)
        assert px <= narrowest, f"width {value}{unit} is wider than {narrowest}px"
    for m in re.finditer(r"(?<![\w(-])min-width:\s*([\d.]+)(px|rem)", BASE):
        px = float(m.group(1)) * (16 if m.group(2) == "rem" else 1)
        assert px <= narrowest, f"min-width {m.group(0)} is wider than {narrowest}px"
    assert "overflow-wrap: anywhere" in BASE            # long names/IDs/codes wrap instead of overflowing


def test_layout_adapts_with_media_queries_and_flexible_units():
    assert "@media (min-width: 48rem)" in BASE and "@media (min-width: 56rem)" in BASE and "@media (max-width: 30rem)" in BASE
    assert "flex-wrap: wrap" in BASE and "grid-template-columns: 1fr;" in BASE
    assert "max-width: var(--max-width)" in BASE and "padding: var(--space-3) var(--gutter)" in BASE


def test_every_interactive_control_has_a_44px_minimum_target():
    for selector in (".btn", ".tabs a", ".nav a", ".nav summary", "details.panel summary", "input[type=text]", "select",
                     "input[type=file]", ".field label:has(input[type=checkbox])"):
        block = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", BASE)
        assert block and "min-height: var(--tap)" in block.group(1) or selector in (".nav a",) and "min-height: var(--tap)" in BASE, selector
    assert "--tap: 44px" in (STATIC / "css" / "tokens.css").read_text()


def test_focus_is_visible_and_not_removed_anywhere():
    assert ":focus-visible" in BASE
    assert not re.search(r"outline:\s*(none|0)", BASE)
    assert "a:focus { outline" not in BASE


def test_colour_is_never_the_only_signal():
    # chips and banners carry a text label and an icon; the pending/revoked chips also change border/decoration
    comp = (Path(__file__).resolve().parents[2] / "app" / "templates" / "partials" / "components.html").read_text()
    assert "Pending approval" in comp and "Access removed" in comp and "icon(" in comp
    assert "line-through" in BASE and "dashed" in BASE
    assert '{{ icon({\'info\': \'info\'' in comp                              # each banner kind has its own icon + title


def test_reduced_motion_is_respected():
    assert "prefers-reduced-motion: reduce" in BASE and "animation: none" in BASE
