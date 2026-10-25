"""Patient IDs and invitation codes.

* Patient ID  ``FCC-XXXX-XXXX``: 8 characters from a 30-character unambiguous alphabet (no I, L, O, U, 0, 1),
  drawn with ``secrets`` -> 30**8 ~ 6.6e11 values (~39 bits). It is an IDENTIFIER ONLY. Possessing it grants
  nothing; joining needs an account, a valid invitation code for that profile, and approval.
* Invitation code ``XXXX-XXXX-XXXX-XXXX``: 16 characters from the same alphabet (~78 bits), shown once to the
  inviter and stored only as a SHA-256 digest.
"""

from __future__ import annotations

import re
import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"  # 30 characters; I, L, O, U, 0, 1 removed to avoid mix-ups
PATIENT_ID_RE = re.compile(rf"^FCC-[{ALPHABET}]{{4}}-[{ALPHABET}]{{4}}$")
INVITE_CODE_RE = re.compile(rf"^(?:[{ALPHABET}]{{4}}-){{3}}[{ALPHABET}]{{4}}$")


def _draw(n: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def new_patient_id() -> str:
    raw = _draw(8)
    return f"FCC-{raw[:4]}-{raw[4:]}"


def new_invite_code() -> str:
    raw = _draw(16)
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def _squash(text: str) -> str:
    return re.sub(r"[\s\-_]", "", (text or "")).upper()


def normalize_patient_id(text: str) -> str | None:
    """Accept lower case, spaces or missing dashes; return the canonical form or None if malformed."""
    raw = _squash(text)
    if len(raw) == 11 and raw.startswith("FCC"):
        raw = raw[3:]
    if len(raw) != 8 or any(c not in ALPHABET for c in raw):
        return None
    return f"FCC-{raw[:4]}-{raw[4:]}"


def normalize_invite_code(text: str) -> str | None:
    raw = _squash(text)
    if len(raw) != 16 or any(c not in ALPHABET for c in raw):
        return None
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))
