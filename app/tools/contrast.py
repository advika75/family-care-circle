"""WCAG contrast check for the design tokens.

Run:  .venv/bin/python -m app.tools.contrast        (exit status 1 if any pair fails)

Parses app/static/css/tokens.css, then checks every text/background pair the UI uses against WCAG 2.x
AA: 4.5:1 for normal text, 3:1 for large text and for UI component boundaries / focus indicators.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parent.parent / "static" / "css" / "tokens.css"

# (foreground token, background token, minimum ratio, where it is used)
PAIRS: list[tuple[str, str, float, str]] = [
    ("text", "bg", 4.5, "body text on page"), ("text", "surface", 4.5, "body text on cards/inputs"),
    ("text", "pink", 4.5, "text on child tint"), ("text", "lavender", 4.5, "text on caregiver tint"),
    ("text", "green", 4.5, "text on patient tint"),
    ("muted", "bg", 4.5, "muted text on page"), ("muted", "surface", 4.5, "muted text on cards"),
    ("muted", "pink", 4.5, "muted text on child tint"), ("muted", "lavender", 4.5, "muted text on caregiver tint"),
    ("muted", "green", 4.5, "muted text on patient tint"),
    ("on-primary", "primary", 4.5, "primary button label"), ("on-primary", "primary-hover", 4.5, "primary button hover"),
    ("primary", "bg", 4.5, "secondary button label / links on page"), ("primary", "surface", 4.5, "secondary button on cards"),
    ("primary", "pink", 4.5, "primary text on pink"),
    ("link", "bg", 4.5, "link on page"), ("link", "surface", 4.5, "link on cards"),
    ("link", "pink", 4.5, "link on pink"), ("link", "lavender", 4.5, "link on lavender"), ("link", "green", 4.5, "link on green"),
    ("danger", "bg", 4.5, "danger label on page"), ("danger", "surface", 4.5, "danger label / error text on cards"),
    ("danger", "danger-hover-bg", 4.5, "danger button hover"),
    ("chip-creator-text", "chip-creator-bg", 4.5, "creator chip"),
    ("chip-caregiver-text", "lavender", 4.5, "caregiver chip"), ("chip-patient-text", "green", 4.5, "patient chip"),
    ("chip-child-text", "pink", 4.5, "child chip"),
    ("status-active-text", "green", 4.5, "active status chip"), ("status-pending-text", "lavender", 4.5, "pending status chip"),
    ("status-revoked-text", "error-bg", 4.5, "revoked status chip"),
    ("chip-note-text", "lavender", 4.5, "can-add-notes chip"),
    ("warn-text", "warn-bg", 4.5, "warning banner"), ("error-text", "error-bg", 4.5, "error banner"),
    ("info-text", "lavender", 4.5, "info banner"), ("success-text", "green", 4.5, "success banner"),
    # non-text: control borders and focus ring need 3:1 against what they sit on
    ("control-border", "surface", 3.0, "input border on white"), ("control-border", "bg", 3.0, "input border on cream"),
    ("primary", "surface", 3.0, "outline button border"),
    ("danger", "surface", 3.0, "danger outline border"),
    ("focus", "bg", 3.0, "focus ring on page"), ("focus", "surface", 3.0, "focus ring on cards"),
    ("focus", "pink", 3.0, "focus ring on child tint"), ("focus", "lavender", 3.0, "focus ring on caregiver tint"),
    ("focus", "green", 3.0, "focus ring on patient tint"),
]


def load_tokens(path: Path = TOKENS) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return {name: value.upper() for name, value in re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\b", text)}


def _lin(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def check(tokens: dict[str, str] | None = None) -> list[dict]:
    tokens = tokens or load_tokens()
    rows = []
    for fg, bg, minimum, use in PAIRS:
        r = ratio(tokens[fg], tokens[bg])
        rows.append({"fg": fg, "bg": bg, "min": minimum, "ratio": round(r, 2), "ok": r >= minimum, "use": use})
    return rows


def main() -> int:
    rows = check()
    for r in rows:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['ratio']:>5}:1  (min {r['min']})  {r['fg']} on {r['bg']}  - {r['use']}")
    bad = [r for r in rows if not r["ok"]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} pairs pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
